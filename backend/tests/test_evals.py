"""Golden tickets: the cases load, and scoring catches each kind of miss (no model calls)."""

from typing import Any

from agents.planner import Plan
from agents.ticket_reader import TicketSpec
from evals.run import Case, load_cases, score
from tests.test_planner import GOOD_PLAN
from tests.test_ticket_reader import BLOCKED, READY

CASE = Case(
    name="contact",
    summary="s",
    description="d",
    status="ready",
    conflicts=False,
    creates=["src/app/contact/page.tsx"],
    modifies=["src/app/page.tsx"],
    tests=True,
)


def plan(**changes: Any) -> Plan:
    return Plan.model_validate({**GOOD_PLAN, **changes})


def test_the_golden_cases_load_and_have_unique_names() -> None:
    cases = load_cases()
    assert len(cases) >= 4
    assert len({c.name for c in cases}) == len(cases)
    assert {c.status for c in cases} == {"ready", "blocked"}


def test_a_matching_plan_passes() -> None:
    assert score(CASE, TicketSpec.model_validate(READY), plan()) == []


def test_wrong_reader_status_fails_first() -> None:
    failures = score(CASE, TicketSpec.model_validate(BLOCKED), None)
    assert failures == ["reader said blocked, expected ready"]


def test_missing_files_tests_and_conflicts_are_each_reported() -> None:
    bad = plan(
        changes=[{**GOOD_PLAN["changes"][0], "action": "modify"}],
        conflicts=[{"description": "No backend", "question": "Which?"}],
        subtasks=[],
    )
    failures = score(CASE, TicketSpec.model_validate(READY), bad)
    assert failures == [
        "planner found conflicts (expected conflicts=False)",
        "plan doesn't create src/app/contact/page.tsx",
        "plan doesn't modify src/app/page.tsx",
        "plan has no test file",
    ]
