"""The PR body's decisions and "look closely at" sections."""

from typing import Any

from agents.developer import DevResult, Risk
from agents.planner import Decision, Plan
from orchestrator.handback import pr_body, pr_risks
from tests.test_planner import GOOD_PLAN, SPEC


def decision(n: int) -> dict[str, str]:
    return {"choice": f"Choice {n}", "why": f"Reason {n}", "rejected": f"Other way {n}"}


def plan(**changes: Any) -> Plan:
    return Plan.model_validate({**GOOD_PLAN, **changes})


def body(plan: Plan, dev: DevResult) -> str:
    return pr_body("https://x/browse/KAN-10", SPEC, plan, dev, ["KAN-15"])


def test_nothing_worth_saying_leaves_both_sections_out() -> None:
    text = body(plan(), DevResult(summary="Footer", changed_files=["src/app/layout.tsx"]))
    assert "## Decisions" not in text and "## Look closely at" not in text


def test_decisions_plan_first_capped_at_three_and_above_the_files() -> None:
    dev = DevResult(
        summary="Footer",
        changed_files=["src/app/layout.tsx"],
        decisions=[Decision.model_validate(decision(3)), Decision.model_validate(decision(4))],
        risks=[Risk(where="layout.tsx", what="renders on error pages too")],
    )
    text = body(plan(decisions=[decision(1), decision(2)]), dev)
    assert "## Decisions\n- Choice 1. Reason 1\n  Rejected: Other way 1\n" in text
    assert "Choice 3" in text and "Choice 4" not in text
    assert "## Look closely at\n- layout.tsx: renders on error pages too" in text
    assert text.index("## Look closely at") < text.index("## Files changed")


def test_code_knows_risky_paths_and_both_sides_before_the_developer() -> None:
    fe = GOOD_PLAN["subtasks"][0]
    both = plan(subtasks=[{**fe, "area": "BE"}, fe], contract="POST /api/contact")
    dev = DevResult(
        summary="Contact",
        changed_files=["src/app/api/contact/route.ts", "src/app/contact/page.tsx"],
        risks=[
            Risk(where="route.ts", what="no rate limit"),
            Risk(where="page.tsx", what="double submit"),
        ],
    )
    risks = pr_risks(both, dev)
    assert [r.where for r in risks] == [
        "src/app/api/contact/route.ts",
        "the contract between backend and frontend",
        "route.ts",
    ]
