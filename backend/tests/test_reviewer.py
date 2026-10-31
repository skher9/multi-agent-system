"""Reviewer: the Review form, what it sees (the diff), and that it can only look."""

import pytest
from pydantic import ValidationError

from agents.planner import Plan
from agents.reviewer import Review, review_changes, review_markdown
from services.workspace import Workspace
from tests.test_agent_loop import Script, call, reply
from tests.test_developer import fake_checks  # noqa: F401  (fixture)
from tests.test_planner import GOOD_PLAN, SPEC
from tests.test_workspace import git, origin  # noqa: F401  (origin is a fixture)

PLAN = Plan.model_validate(GOOD_PLAN)
ISSUE = {"path": "src/app/contact/page.tsx", "problem": "No thanks message", "fix": "Show it"}
CHECKS = [
    {"number": 1, "met": True, "test": "page.test.tsx: renders the form"},
    {"number": 2, "met": False, "test": ""},
]
CHANGES = {
    "verdict": "changes_requested",
    "summary": "Gap.",
    "issues": [ISSUE],
    "criteria_check": CHECKS,
}


@pytest.mark.parametrize(
    ("review", "message"),
    [
        (
            {"verdict": "approve", "summary": "ok", "issues": [ISSUE], "criteria_check": []},
            "approve means no issues",
        ),
        (
            {"verdict": "changes_requested", "summary": "bad", "issues": [], "criteria_check": []},
            "at least one issue",
        ),
    ],
)
def test_verdict_must_match_issues(review: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Review.model_validate(review)


def test_markdown_lists_each_issue() -> None:
    review = Review.model_validate(CHANGES)
    text = review_markdown(review, 2)
    assert text.startswith("### 🤖 Review 2: 🔧 Changes needed")
    assert "- **`src/app/contact/page.tsx`**: No thanks message" in text
    assert "  - Fix: Show it" in text
    assert "| 1 | ✅ | page.test.tsx: renders the form |" in text
    assert "| 2 | ❌ | — |" in text


def test_reviewer_sees_the_diff_and_can_only_look(origin: str) -> None:  # noqa: F811
    with Workspace.clone(origin) as ws:
        base = ws.head_sha()
        ws.create_branch("agent/KAN-4")
        (ws.path / "contact.tsx").write_text("export const Contact = () => null\n")
        git("add", ".", cwd=ws.path)
        git("commit", "--quiet", "-m", "dev", cwd=ws.path)
        ws.push("agent/KAN-4")

    script = Script(
        reply(call("edit_file", {"path": "contact.tsx", "old_text": "null", "new_text": "1"})),
        reply(call("read_file", {"path": "contact.tsx"})),
        reply(call("finish", {**CHANGES, "criteria_check": CHECKS[:1]})),  # misses criterion 2
        reply(call("finish", CHANGES)),
    )
    previous = Review.model_validate(CHANGES)
    with Workspace.clone(origin) as ws:
        ws.checkout("agent/KAN-4")
        review = review_changes(
            script.router(),
            SPEC,
            PLAN,
            ws,
            base,
            agent_run_id=1,
            dev_summary="Built the contact page",
            previous=previous,
        )
        assert (ws.path / "contact.tsx").read_text() == "export const Contact = () => null\n"

    assert review.verdict == "changes_requested"
    task = script.sent[0]["messages"][1]["content"]
    assert "+export const Contact = () => null" in task  # the diff since the planned commit
    assert "1. Visiting /contact shows a form" in task
    assert "<developer_summary>\nBuilt the contact page\n</developer_summary>" in task
    assert "<previous_review>\n- src/app/contact/page.tsx: No thanks message" in task
    assert "(see src/app/page.tsx)" in task  # the plan's conventions
    rejected = [m["content"] for m in script.sent[-1]["messages"] if m["role"] == "tool"][2]
    assert "criterion 1 to 2 exactly once" in rejected
    results = [m["content"] for m in script.sent[-1]["messages"] if m["role"] == "tool"]
    assert results[0].startswith("ERROR: 'edit_file' is not available to the reviewer")
    assert script.sent[0]["model"] == "minimax/minimax-m3"


def test_developer_fix_mode_gets_the_review_and_needs_no_new_test(
    origin: str,  # noqa: F811
    fake_checks: list[list[str]],  # noqa: F811
) -> None:
    from agents.developer import develop_ticket

    review = Review.model_validate(CHANGES)
    script = Script(
        reply(call("create_file", {"path": "src/thanks.tsx", "content": "thanks\n"})),
        reply(call("finish", {"summary": "Added the thanks message"})),  # no test file: fine
    )
    with Workspace.clone(origin) as ws:
        result = develop_ticket(script.router(), SPEC, PLAN, ws, agent_run_id=1, review=review)
    assert result.summary == "Added the thanks message"
    task = script.sent[0]["messages"][1]["content"]
    assert "<review_comments>" in task
    assert "- src/app/contact/page.tsx: No thanks message Fix: Show it" in task


def test_an_unmet_criterion_cannot_be_approved() -> None:
    from agents.reviewer import _checked_review

    approve = {"verdict": "approve", "summary": "ok", "issues": [], "criteria_check": CHECKS}
    with pytest.raises(ValidationError, match="must be changes_requested"):
        _checked_review(2).model_validate(approve)


def test_diff_base_must_be_a_sha(origin: str) -> None:  # noqa: F811
    with Workspace.clone(origin) as ws, pytest.raises(ValueError):
        ws.diff("HEAD; rm -rf /")
