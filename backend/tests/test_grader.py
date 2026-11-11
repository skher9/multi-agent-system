"""Grader: the Grade form's thresholds, the quote check, and what it's shown."""

from typing import Any

import pytest
from pydantic import ValidationError

from agents.grader import Grade, grade_changes, grade_markdown
from agents.quality import QualityFindings
from agents.rubric import AREAS, find_quote, rubric_text
from services.workspace import Workspace
from tests.test_agent_loop import Script, call, reply
from tests.test_workspace import git, origin  # noqa: F401  (origin is a fixture)

PAGE = """\
"use client";

const EMAIL = /^[^\\s@]+@[^\\s@]+$/;

export default function Contact() {
  return <form onSubmit={(e) => e.preventDefault()}>
    <input name="email" />
  </form>;
}
"""


def scores(**changed: int) -> list[dict[str, Any]]:
    return [
        {"area": a, "score": changed.get(a, 8), "reason": "Fine.", "raise_by_one": "Share setup."}
        for a in AREAS
    ]


def point(area: str = "robustness", quote: str = '<input name="email" />') -> dict[str, Any]:
    return {
        "area": area,
        "path": "src/contact.tsx",
        "quote": quote,
        "problem": "The field has no label.",
        "fix": "Add a label.",
    }


GOOD = {"summary": "Solid.", "scores": scores(), "must_fix": [], "suggestions": [point()]}


@pytest.mark.parametrize(
    ("grade", "message"),
    [
        ({**GOOD, "scores": scores()[:4]}, "score each area exactly once"),
        ({**GOOD, "scores": scores(tests=4)}, "tests scored below 6"),
        ({**GOOD, "must_fix": [point()]}, "must_fix is only for areas scored below 6"),
    ],
)
def test_thresholds_tie_scores_to_must_fix(grade: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Grade.model_validate(grade)


def test_the_bar_is_every_area_at_seven() -> None:
    assert Grade.model_validate(GOOD).meets_bar
    low = Grade.model_validate({**GOOD, "scores": scores(readability=6)})
    assert not low.meets_bar and low.lowest == 6 and low.score("tests") == 8
    report = grade_markdown(low)
    assert report.startswith("**Rubric grade: below the bar (lowest 6)**")
    assert "| fits the repo | 8 | Fine. | Share setup. |" in report
    assert "- `src/contact.tsx:0` (robustness): The field has no label. Fix: Add a label." in report


def test_find_quote_ignores_indentation_and_line_breaks() -> None:
    assert find_quote(PAGE, '<input name="email" />') == 7
    assert find_quote(PAGE, "return <form onSubmit={(e) => e.preventDefault()}>\n<input") == 6
    assert find_quote(PAGE, "const EMAIL = /^[^\\s@]+@[^\\s@]+$/;") == 3
    assert find_quote(PAGE, '<input name="phone" />') == 0
    assert find_quote(PAGE, "  }  ") == 0  # too short to mean anything


def test_the_rubric_has_every_area_and_no_notes_for_people() -> None:
    text = rubric_text()
    assert "<!--" not in text and "DRAFT" not in text
    for heading in ("Correctness", "Tests", "Readability", "Fits the repo", "Robustness"):
        assert f". {heading}" in text


def test_grader_must_quote_real_code_from_the_change(origin: str) -> None:  # noqa: F811
    with Workspace.clone(origin) as ws:
        base = ws.head_sha()
        ws.create_branch("agent/KAN-4")
        (ws.path / "src").mkdir(exist_ok=True)
        (ws.path / "src/contact.tsx").write_text(PAGE)
        git("add", ".", cwd=ws.path)
        git("commit", "--quiet", "-m", "dev", cwd=ws.path)
        ws.push("agent/KAN-4")

    invented = {**GOOD, "suggestions": [point(quote="<input name='phone' required />")]}
    elsewhere = {**GOOD, "suggestions": [{**point(), "path": "README.md"}]}
    script = Script(
        reply(call("edit_file", {"path": "src/contact.tsx", "old_text": "a", "new_text": "b"})),
        reply(call("finish", invented)),
        reply(call("finish", elsewhere)),
        reply(call("finish", GOOD)),
    )
    found = QualityFindings(ran=True, smells=["src/contact.tsx:3 [sonarjs/slow-regex] Slow."])
    with Workspace.clone(origin) as ws:
        ws.checkout("agent/KAN-4")
        grade = grade_changes(
            script.router(),
            "Title: Add a contact page",
            ws,
            base,
            agent_run_id=1,
            scan=found,
        )
    assert grade.suggestions[0].line == 7  # filled in from the quote
    assert script.sent[0]["model"] == "anthropic/claude-opus-5.5"
    task = script.sent[0]["messages"][1]["content"]
    assert "<rubric>\n# Code quality rubric" in task
    assert "<ticket>\nTitle: Add a contact page\n</ticket>" in task
    assert "- src/contact.tsx:3 [sonarjs/slow-regex] Slow." in task
    assert '<file path="src/contact.tsx">' in task and "+const EMAIL" in task
    results = [m["content"] for m in script.sent[-1]["messages"] if m["role"] == "tool"]
    assert "not available to the grader" in results[0]
    assert "this quote isn't in the file" in results[1]
    assert "README.md: not a file this change touched" in results[2]
