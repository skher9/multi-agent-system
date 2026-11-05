import ast
import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx2
import pytest

from llm_router.budget import BudgetExceededError, DailyBudgetExceededError
from llm_router.models import Role
from llm_router.router import CallRecord, LlmRouter
from services.openrouter import OpenRouterClient, OpenRouterError

BACKEND_DIR = Path(__file__).resolve().parent.parent


def reply(cost: float = 0.001, model: str = "minimax/minimax-m3") -> dict[str, Any]:
    return {
        "model": model,
        "choices": [{"finish_reason": "stop", "message": {"content": "done"}}],
        "usage": {
            "prompt_tokens": 1200,
            "completion_tokens": 30,
            "cost": cost,
            "prompt_tokens_details": {"cached_tokens": 1000},
        },
    }


def make_router(
    handler: Callable[[httpx2.Request], httpx2.Response],
    spent_inr: Decimal = Decimal("0"),
) -> tuple[LlmRouter, list[CallRecord], list[float]]:
    records: list[CallRecord] = []
    waits: list[float] = []
    client = OpenRouterClient("fake-key", transport=httpx2.MockTransport(handler))
    router = LlmRouter(
        client,
        records.append,
        Decimal("96.5"),
        story_spend=lambda _run_id: spent_inr,
        story_budget_inr=Decimal("50"),
        sleep=waits.append,
    )
    return router, records, waits


def test_refuses_calls_once_story_budget_is_used() -> None:
    def handler(_: httpx2.Request) -> httpx2.Response:
        raise AssertionError("no model call should be made over budget")

    router, records, _ = make_router(handler, spent_inr=Decimal("50.0000"))
    with pytest.raises(BudgetExceededError) as exc_info:
        router.complete(role=Role.DEVELOPER, messages=[], agent_run_id=1)
    assert exc_info.value.spent_inr == Decimal("50.0000")
    assert records == []


def test_allows_calls_just_under_budget() -> None:
    router, records, _ = make_router(
        lambda _: httpx2.Response(200, json=reply()), spent_inr=Decimal("49.9999")
    )
    router.complete(role=Role.DEVELOPER, messages=[], agent_run_id=1)
    assert len(records) == 1


def daily_router(spent_today: Decimal) -> tuple[LlmRouter, list[CallRecord]]:
    records: list[CallRecord] = []
    client = OpenRouterClient(
        "fake-key", transport=httpx2.MockTransport(lambda _: httpx2.Response(200, json=reply()))
    )
    router = LlmRouter(
        client,
        records.append,
        Decimal("96.5"),
        story_spend=lambda _run_id: Decimal("0"),
        story_budget_inr=Decimal("50"),
        daily_spend=lambda: spent_today,
        daily_budget_inr=Decimal("300"),
    )
    return router, records


def test_refuses_calls_once_daily_budget_is_used() -> None:
    router, records = daily_router(Decimal("300"))
    with pytest.raises(DailyBudgetExceededError, match="daily budget used"):
        router.complete(role=Role.DEVELOPER, messages=[], agent_run_id=1)
    assert records == []


def test_daily_budget_stop_is_a_budget_stop() -> None:
    # Code that already handles a story budget stop handles the daily one too
    assert issubclass(DailyBudgetExceededError, BudgetExceededError)


def test_allows_calls_under_daily_budget() -> None:
    router, records = daily_router(Decimal("299.99"))
    router.complete(role=Role.DEVELOPER, messages=[], agent_run_id=1)
    assert len(records) == 1


def test_picks_model_by_role_and_sends_run_session() -> None:
    sent: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.append(json.loads(request.content))
        return httpx2.Response(200, json=reply())

    router, _, _ = make_router(handler)
    router.complete(role=Role.TICKET_READER, messages=[], agent_run_id=7)
    router.complete(role=Role.DEVELOPER, messages=[], agent_run_id=7, escalate=True)

    assert sent[0]["model"] == "minimax/minimax-m3"
    assert sent[0]["session_id"] == "agent-run-7"
    assert sent[1]["model"] == "z-ai/glm-5.2"


def test_records_tokens_and_cost_in_rupees() -> None:
    router, records, _ = make_router(lambda _: httpx2.Response(200, json=reply(cost=0.001)))
    router.complete(role=Role.DEVELOPER, messages=[], agent_run_id=7)

    [record] = records
    assert record.agent_run_id == 7
    assert record.model == "minimax/minimax-m3"
    assert record.input_tokens == 1200
    assert record.cached_tokens == 1000
    assert record.output_tokens == 30
    assert record.cost_inr == Decimal("0.0965")  # $0.001 x ₹96.5
    assert record.latency_ms >= 0


def test_cost_is_rounded_to_four_decimal_places() -> None:
    router, records, _ = make_router(lambda _: httpx2.Response(200, json=reply(cost=0.0000017)))
    router.complete(role=Role.DEVELOPER, messages=[], agent_run_id=1)
    # 0.0000017 x 96.5 = 0.00016405 -> 0.0002
    assert records[0].cost_inr == Decimal("0.0002")


def test_retries_temporary_errors_then_succeeds() -> None:
    statuses = iter([429, 503, 200])

    def handler(_: httpx2.Request) -> httpx2.Response:
        status = next(statuses)
        if status == 200:
            return httpx2.Response(200, json=reply())
        return httpx2.Response(status, json={"error": {"code": status, "message": "busy"}})

    router, records, waits = make_router(handler)
    result = router.complete(role=Role.REVIEWER, messages=[], agent_run_id=1)

    assert result.content == "done"
    assert waits == [1, 2]
    assert len(records) == 1  # failed attempts aren't billed, so they aren't recorded


def test_gives_up_after_five_retries() -> None:
    calls = 0

    def handler(_: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return httpx2.Response(502, json={"error": {"code": 502, "message": "down"}})

    router, records, waits = make_router(handler)
    with pytest.raises(OpenRouterError):
        router.complete(role=Role.DEVELOPER, messages=[], agent_run_id=1)
    assert calls == 6
    assert waits == [1, 2, 5, 10, 20]
    assert records == []


def test_does_not_retry_errors_that_would_fail_again() -> None:
    calls = 0

    def handler(_: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return httpx2.Response(402, json={"error": {"code": 402, "message": "no credits"}})

    router, _, waits = make_router(handler)
    with pytest.raises(OpenRouterError, match="no credits"):
        router.complete(role=Role.DEVELOPER, messages=[], agent_run_id=1)
    assert calls == 1
    assert waits == []


def test_only_the_router_calls_models() -> None:
    """Every model call must go through llm_router, or its cost is never logged."""
    allowed = {BACKEND_DIR / "llm_router", BACKEND_DIR / "services" / "openrouter.py"}
    offenders = []
    for path in BACKEND_DIR.rglob("*.py"):
        parts = path.relative_to(BACKEND_DIR).parts
        if parts[0] in {".venv", "tests"} or any(path.is_relative_to(a) for a in allowed):
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Attribute) and node.attr == "chat":
                offenders.append(f"{path.relative_to(BACKEND_DIR)}:{node.lineno}")
    assert offenders == [], f"model calls outside llm_router: {offenders}"
