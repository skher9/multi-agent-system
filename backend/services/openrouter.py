"""OpenRouter: one API key for many model providers.

chat() is the one method that spends credits. Only the LLM router (llm_router/)
may call it, so every model call gets logged with its cost.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx2

API_URL = "https://openrouter.ai/api/v1"

# Worth retrying: timeout, rate limit, provider down or overloaded.
# Everything else (bad request, bad key, 402 out of credits) fails the same way again.
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})

# A developer reply can be long; listing models and pinging stay on the 15s default.
CHAT_TIMEOUT_SECONDS = 300


class OpenRouterError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"OpenRouter {status_code}: {message}")
        self.status_code = status_code
        self.message = message

    @property
    def retryable(self) -> bool:
        return self.status_code in RETRYABLE_STATUS


@dataclass(frozen=True)
class ChatUsage:
    prompt_tokens: int
    cached_tokens: int  # part of prompt_tokens read from the provider's cache
    completion_tokens: int
    cost_usd: Decimal  # what OpenRouter actually charged, cache discounts included


@dataclass(frozen=True)
class ChatResponse:
    model: str  # the model that answered, as OpenRouter reports it
    content: str | None  # None when the model only asks for tool calls
    tool_calls: list[dict[str, Any]]
    finish_reason: str  # stop, tool_calls, length, or content_filter
    usage: ChatUsage


@dataclass(frozen=True)
class ModelInfo:
    id: str  # e.g. "deepseek/deepseek-chat"; the router config pins these
    context_length: int | None
    # USD per token, as strings in the API response; kept exact with Decimal
    prompt_price_usd: Decimal | None
    completion_price_usd: Decimal | None


def _price(pricing: dict[str, Any], field: str) -> Decimal | None:
    value = pricing.get(field)
    return Decimal(str(value)) if value is not None else None


def _json_or_empty(response: httpx2.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _error_message(data: dict[str, Any], fallback: str) -> str:
    error = data.get("error")
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    return fallback[:200] or "unknown error"


def _parse_chat(data: dict[str, Any]) -> ChatResponse:
    choice = data["choices"][0]
    if choice.get("finish_reason") == "error":
        raise OpenRouterError(502, _error_message(choice, "generation failed"))
    usage = data.get("usage")
    if not usage or usage.get("cost") is None:
        # The budget guard can't work without a cost, so treat this as a failed call.
        raise OpenRouterError(502, "response had no usage or cost")
    message = choice["message"]
    return ChatResponse(
        model=data["model"],
        content=message.get("content"),
        tool_calls=message.get("tool_calls") or [],
        finish_reason=choice["finish_reason"],
        usage=ChatUsage(
            prompt_tokens=usage["prompt_tokens"],
            cached_tokens=(usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0,
            completion_tokens=usage["completion_tokens"],
            cost_usd=Decimal(str(usage["cost"])),
        ),
    )


class OpenRouterClient:
    def __init__(self, api_key: str, transport: httpx2.BaseTransport | None = None) -> None:
        self._http = httpx2.Client(
            base_url=API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
            transport=transport,
        )

    def list_models(self) -> list[ModelInfo]:
        response = self._http.get("/models")
        response.raise_for_status()
        return [
            ModelInfo(
                id=m["id"],
                context_length=m.get("context_length"),
                prompt_price_usd=_price(m.get("pricing", {}), "prompt"),
                completion_price_usd=_price(m.get("pricing", {}), "completion"),
            )
            for m in response.json()["data"]
        ]

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        session_id: str | None = None,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """One chat completion. Raises OpenRouterError on any failure, even inside a 200."""
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            # Route only to providers that support every parameter sent (e.g. a JSON
            # schema), instead of one that silently ignores it.
            "provider": {"require_parameters": True},
        }
        optional = {
            "tools": tools,
            "response_format": response_format,
            # Keeps calls of one run on the same provider, so its prompt cache gets reused.
            "session_id": session_id,
            "max_tokens": max_tokens,
        }
        body.update({k: v for k, v in optional.items() if v is not None})

        try:
            response = self._http.post("/chat/completions", json=body, timeout=CHAT_TIMEOUT_SECONDS)
        except httpx2.TimeoutException as exc:
            raise OpenRouterError(408, "request timed out") from exc
        data = _json_or_empty(response)
        if response.status_code != 200:
            raise OpenRouterError(response.status_code, _error_message(data, response.text))
        # Once generation starts the status is already 200, so failures arrive in the body.
        if "error" in data:
            error = data["error"]
            code = error.get("code") if isinstance(error, dict) else None
            raise OpenRouterError(int(code or 502), _error_message(data, ""))
        return _parse_chat(data)

    def ping(self) -> None:
        """Raise if the key is invalid. GET /key reads the key's own limits; no credits used."""
        self._http.get("/key").raise_for_status()

    def close(self) -> None:
        self._http.close()
