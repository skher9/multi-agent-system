from collections.abc import Callable
from decimal import Decimal

import httpx2
import pytest

from services.openrouter import OpenRouterClient


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


def test_client_has_no_model_call_method() -> None:
    """Setup rule: no model calls. Only the M1 LLM router may call models."""
    public = {name for name in dir(OpenRouterClient) if not name.startswith("_")}
    assert public == {"list_models", "ping", "close"}
