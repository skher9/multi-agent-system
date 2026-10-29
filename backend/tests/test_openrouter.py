import json
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import httpx2
import pytest

from services.openrouter import OpenRouterClient, OpenRouterError


def make_client(handler: Callable[[httpx2.Request], httpx2.Response]) -> OpenRouterClient:
    return OpenRouterClient("fake-key", transport=httpx2.MockTransport(handler))


def test_list_models_parses_prices_exactly() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/api/v1/models"
        assert request.headers["authorization"] == "Bearer fake-key"
        return httpx2.Response(
            200,
            json={
                "data": [
                    {
                        "id": "deepseek/deepseek-chat",
                        "context_length": 128000,
                        "pricing": {"prompt": "0.00000027", "completion": "0.0000011"},
                    }
                ],
                "total_count": 1,
                "links": {"next": None},
            },
        )

    [model] = make_client(handler).list_models()
    assert model.id == "deepseek/deepseek-chat"
    assert model.prompt_price_usd == Decimal("0.00000027")


def test_ping_hits_key_endpoint_and_raises_on_bad_key() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/api/v1/key"
        return httpx2.Response(401)

    with pytest.raises(httpx2.HTTPStatusError):
        make_client(handler).ping()


def test_chat_is_the_only_method_that_spends_credits() -> None:
    public = {name for name in dir(OpenRouterClient) if not name.startswith("_")}
    assert public == {"chat", "list_models", "ping", "close"}


def chat_reply(**overrides: Any) -> dict[str, Any]:
    """A successful chat completion body, shaped like OpenRouter's docs."""
    body: dict[str, Any] = {
        "id": "gen-1",
        "model": "minimax/minimax-m3",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "hello"},
            }
        ],
        "usage": {
            "prompt_tokens": 2000,
            "completion_tokens": 10,
            "total_tokens": 2010,
            "cost": 0.000612,
            "prompt_tokens_details": {"cached_tokens": 1500},
        },
    }
    body.update(overrides)
    return body


def test_chat_sends_request_and_parses_usage_exactly() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/api/v1/chat/completions"
        sent = json.loads(request.content)
        assert sent == {
            "model": "minimax/minimax-m3",
            "messages": [{"role": "user", "content": "hi"}],
            "provider": {"require_parameters": True},
            "session_id": "run-42",
        }
        return httpx2.Response(200, json=chat_reply())

    result = make_client(handler).chat(
        "minimax/minimax-m3", [{"role": "user", "content": "hi"}], session_id="run-42"
    )
    assert result.content == "hello"
    assert result.tool_calls == []
    assert result.usage.prompt_tokens == 2000
    assert result.usage.cached_tokens == 1500
    assert result.usage.completion_tokens == 10
    assert result.usage.cost_usd == Decimal("0.000612")


def test_chat_returns_tool_calls() -> None:
    call = {"id": "c1", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}
    reply = chat_reply(
        choices=[
            {
                "finish_reason": "tool_calls",
                "message": {"role": "assistant", "content": None, "tool_calls": [call]},
            }
        ]
    )
    result = make_client(lambda _: httpx2.Response(200, json=reply)).chat("m", [])
    assert result.content is None
    assert result.tool_calls == [call]
    assert result.finish_reason == "tool_calls"


def test_missing_cached_tokens_counts_as_zero() -> None:
    reply = chat_reply(usage={"prompt_tokens": 5, "completion_tokens": 1, "cost": 0})
    result = make_client(lambda _: httpx2.Response(200, json=reply)).chat("m", [])
    assert result.usage.cached_tokens == 0


@pytest.mark.parametrize(
    ("status", "retryable"),
    [(400, False), (401, False), (402, False), (429, True), (502, True), (503, True)],
)
def test_http_errors_raise_with_retry_hint(status: int, retryable: bool) -> None:
    body = {"error": {"code": status, "message": "nope"}}
    client = make_client(lambda _: httpx2.Response(status, json=body))
    with pytest.raises(OpenRouterError) as exc_info:
        client.chat("m", [])
    assert exc_info.value.status_code == status
    assert exc_info.value.message == "nope"
    assert exc_info.value.retryable is retryable


def test_error_inside_a_200_body_still_raises() -> None:
    body = {"error": {"code": 502, "message": "provider died mid-generation"}}
    with pytest.raises(OpenRouterError, match="provider died"):
        make_client(lambda _: httpx2.Response(200, json=body)).chat("m", [])


def test_finish_reason_error_raises() -> None:
    reply = chat_reply(choices=[{"finish_reason": "error", "message": {"content": "partial"}}])
    with pytest.raises(OpenRouterError) as exc_info:
        make_client(lambda _: httpx2.Response(200, json=reply)).chat("m", [])
    assert exc_info.value.retryable


def test_reply_without_cost_raises() -> None:
    reply = chat_reply(usage={"prompt_tokens": 5, "completion_tokens": 1})
    with pytest.raises(OpenRouterError, match="no usage or cost"):
        make_client(lambda _: httpx2.Response(200, json=reply)).chat("m", [])


def test_timeout_becomes_retryable_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("slow", request=request)

    with pytest.raises(OpenRouterError) as exc_info:
        make_client(handler).chat("m", [])
    assert exc_info.value.status_code == 408
    assert exc_info.value.retryable
