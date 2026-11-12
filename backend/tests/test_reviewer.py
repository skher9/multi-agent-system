"""Reviewer: the Review form, what it sees (the diff), and that it can only look."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from agents.planner import Plan
from agents.reviewer import Review, _checked_review, review_changes, review_markdown
from agents.rubric import AREAS
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


def scores(**changed: int) -> list[dict[str, object]]:
    return [
        {"area": a, "score": changed.get(a, 8), "reason": "Fine.", "raise_by_one": "Share setup."}
        for a in AREAS
    ]


SCORED = {**CHANGES, "scores": scores(correctness=4)}  # criterion 2 isn't met


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
        reply(call("finish", {**SCORED, "criteria_check": CHECKS[:1]})),  # misses criterion 2
        reply(call("finish", SCORED)),
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
    assert "<rubric>\n# Code quality rubric" in task
    rejected = [m["content"] for m in script.sent[-1]["messages"] if m["role"] == "tool"][2]
    assert "criterion 1 to 2 exactly once" in rejected
    results = [m["content"] for m in script.sent[-1]["messages"] if m["role"] == "tool"]
    assert results[0].startswith("ERROR: 'edit_file' is not available to the reviewer")
    assert script.sent[0]["model"] == "deepseek/deepseek-v4.1-flash"  # routing is the runner's


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


MET = [{**c, "met": True, "test": "page.test.tsx"} for c in CHECKS]
APPROVE = {"verdict": "approve", "summary": "ok", "issues": [], "criteria_check": MET}


def test_an_unmet_criterion_cannot_be_approved(tmp_path: Path) -> None:
    approve = {**APPROVE, "criteria_check": CHECKS, "scores": scores()}
    with pytest.raises(ValidationError, match="must be changes_requested"):
        _checked_review(2, tmp_path).model_validate(approve)


@pytest.mark.parametrize(
    ("review", "message"),
    [
        (APPROVE, "score each rubric area exactly once"),
        ({**APPROVE, "scores": scores(tests=5)}, "tests scored below 6: that sends the work back"),
        (
            {**CHANGES, "criteria_check": MET, "scores": scores(readability=6)},
            "every area scored 6 or more, so nothing must be fixed",
        ),
    ],
)
def test_the_floor_sends_work_back_and_the_ceiling_stops_taste(
    review: dict[str, object], message: str, tmp_path: Path
) -> None:
    with pytest.raises(ValidationError, match=message):
        _checked_review(2, tmp_path).model_validate(review)


def test_taste_becomes_suggestions_and_quotes_must_be_real(tmp_path: Path) -> None:
    (tmp_path / "page.tsx").write_text(
        "export default function Page() {\n  return <h1>Hi</h1>;\n}\n"
    )
    nit = {
        "path": "page.tsx",
        "problem": "The heading could be a shared component.",
        "fix": "Use it.",
    }
    real = {**nit, "quote": "return <h1>Hi</h1>;"}
    form = _checked_review(2, tmp_path)
    review = form.model_validate({**APPROVE, "scores": scores(), "suggestions": [real]})
    assert review.verdict == "approve" and review.suggestions[0].line == 2
    text = review_markdown(review, 1)
    assert "| fits the repo | 8 | Fine. |" in text
    assert "- `page.tsx:2`: The heading could be a shared component. Use it." in text
    invented = {**nit, "quote": "return <h2>Hello</h2>;"}
    with pytest.raises(ValidationError, match="this quote isn't in the file"):
        form.model_validate({**APPROVE, "scores": scores(), "suggestions": [invented]})
    form.model_validate({**APPROVE, "scores": scores(), "suggestions": [nit]})  # nothing quoted


def test_reviews_saved_before_the_rubric_still_load() -> None:
    old = Review.model_validate(CHANGES)
    assert old.scores == [] and old.suggestions == [] and old.issues[0].quote == ""


def test_diff_base_must_be_a_sha(origin: str) -> None:  # noqa: F811
    with Workspace.clone(origin) as ws, pytest.raises(ValueError):
        ws.diff("HEAD; rm -rf /")
