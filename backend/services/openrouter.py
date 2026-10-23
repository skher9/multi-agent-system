"""OpenRouter: one API key for many model providers.

Setup scope: read-only calls that cost no credits. There is deliberately no
"call a model" method here. In M1 the LLM router (llm_router/) becomes the only
code allowed to call models, so every call gets logged with its cost.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx2

API_URL = "https://openrouter.ai/api/v1"


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

    def ping(self) -> None:
        """Raise if the key is invalid. GET /key reads the key's own limits; no credits used."""
        self._http.get("/key").raise_for_status()

    def close(self) -> None:
        self._http.close()
