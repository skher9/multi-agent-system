"""Model routing: the strong model for big or risky work, and on trouble."""

from decimal import Decimal
from typing import Any

import httpx2
import pytest

from agents.planner import Plan
from agents.ticket_reader import TicketSpec
from llm_router.budget import AgentBudgetExceededError
from llm_router.models import Role
from llm_router.router import LlmRouter
from orchestrator.routing import planner_tier, reviewer_tier
from services.openrouter import OpenRouterClient
from tests.test_agent_loop import Script, call, reply
from tests.test_planner import GOOD_PLAN, SPEC


def spec(criteria: int) -> TicketSpec:
    return SPEC.model_copy(update={"acceptance_criteria": [f"c{i}" for i in range(criteria)]})


def plan(**changes: Any) -> Plan:
    return Plan.model_validate({**GOOD_PLAN, **changes})


def test_planner_gets_the_strong_model_only_for_big_tickets() -> None:
    assert planner_tier(spec(2)) is None
    assert planner_tier(spec(7)) == "7 acceptance criteria"


def test_reviewer_routing_reasons() -> None:
    small = plan()
    assert reviewer_tier(small, 1) is None
    assert reviewer_tier(small, 2) == "second review round: the first fix didn't settle it"
    change = {**GOOD_PLAN["changes"][0], "path": "src/app/api/login/route.ts", "action": "create"}
    assert "risky code" in (reviewer_tier(plan(changes=[change]), 1) or "")
    fe = GOOD_PLAN["subtasks"][0]
    both = plan(subtasks=[{**fe, "area": "BE"}, fe], contract="POST /x")
    assert reviewer_tier(both, 1) == "backend and frontend change together"


def test_two_rejected_answers_switch_the_turn_to_the_strong_model() -> None:
    bad = call("finish", {"summary": ""})  # rejected: too short
    script = Script(reply(bad), reply(bad), reply(call("finish", {"summary": "done"})))
    events: list[tuple[Any, dict[str, Any]]] = []
    script.run(on_event=lambda kind, data: events.append((kind, data)))
    models = [sent["model"] for sent in script.sent]
    assert models == [
        "deepseek/deepseek-v4.1-flash",
        "deepseek/deepseek-v4.1-flash",
        "deepseek/deepseek-v4-pro",
    ]
    assert any("Switching to the stronger model" in str(d.get("text")) for _, d in events)


def test_strong_turns_get_a_bigger_cap() -> None:
    router = LlmRouter(
        OpenRouterClient(
            "k",
            transport=httpx2.MockTransport(lambda r: httpx2.Response(200, json=reply())),
        ),
        lambda _record: None,
        Decimal("96.5"),
        story_spend=lambda _id: Decimal("0"),
        story_budget_inr=Decimal("50"),
        agent_spend=lambda _id: Decimal("6"),  # over the reviewer's ₹5, under 3 x ₹5
    )
    with pytest.raises(AgentBudgetExceededError):
        router.complete(role=Role.REVIEWER, messages=[], agent_run_id=1)
    router.complete(role=Role.REVIEWER, messages=[], agent_run_id=1, strong=True)
