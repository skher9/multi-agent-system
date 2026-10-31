"""Planner: the Plan checks, read-only tools, and what it's told. Fake model, local git repo."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from agents.code_graph import CodeGraphFiles
from agents.planner import Plan, _checked_plan, plan_ticket
from agents.ticket_reader import TicketSpec
from services.workspace import Workspace
from tests.test_agent_loop import Script, call, reply
from tests.test_ticket_reader import READY
from tests.test_workspace import git, origin  # noqa: F401  (origin is a fixture)

SPEC = TicketSpec.model_validate(
    {**READY, "acceptance_criteria": ["Visiting /contact shows a form", "Submitting thanks you"]}
)

GOOD_PLAN: dict[str, Any] = {
    "notes": "Next.js app router; pages in src/app; vitest tests in __tests__.",
    "changes": [
        {
            "path": "src/app/contact/page.tsx",
            "action": "create",
            "what": "ContactPage with a name/email/message form and a thank-you state",
            "why": "The contact page with its form",
            "criteria": [1, 2],
        },
        {
            "path": "src/app/contact/page.test.tsx",
            "action": "create",
            "what": "Tests: the form renders (1); submitting shows the thank-you message (2)",
            "why": "Every criterion needs a test",
            "criteria": [1, 2],
        },
        {
            "path": "src/app/page.tsx",
            "action": "modify",
            "what": "Add a link to /contact in Home()",
            "why": "Link to /contact",
            "criteria": [1],
        },
    ],
    "conventions": [
        {"what": "Pages are default-exported server components", "example": "src/app/page.tsx"}
    ],
    "conflicts": [],
    "assumptions": ["The link sits under the page heading, like other links"],
    "contract": "",
    "dependencies": [],
    "unrelated_issues": [],
    "subtasks": [
        {
            "area": "FE",
            "title": "Contact page",
            "description": "Form page and home link",
            "files": [
                "src/app/contact/page.tsx",
                "src/app/contact/page.test.tsx",
                "src/app/page.tsx",
            ],
        }
    ],
}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src/app").mkdir(parents=True)
    (root / "src/app/page.tsx").write_text("export default function Home() {}\n")
    return root


def checked(repo: Path) -> type[Plan]:
    return _checked_plan(len(SPEC.acceptance_criteria), repo)


def test_a_good_plan_passes(repo: Path) -> None:
    plan = checked(repo).model_validate(GOOD_PLAN)
    assert plan.subtasks[0].area == "FE"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"changes": [{**GOOD_PLAN["changes"][0], "criteria": [1]}]}, "criteria [2]"),
        ({"changes": [{**GOOD_PLAN["changes"][0], "criteria": [1, 2, 7]}]}, "numbered [7]"),
        ({"changes": [{**GOOD_PLAN["changes"][2], "action": "create"}]}, "already exists"),
        (
            {"changes": [{**GOOD_PLAN["changes"][0], "action": "modify"}]},
            "doesn't exist",
        ),
        ({"changes": [{**GOOD_PLAN["changes"][0], "path": "../etc/passwd"}]}, "inside the repo"),
        ({"changes": [{**GOOD_PLAN["changes"][0], "path": "/etc/passwd"}]}, "inside the repo"),
        ({"changes": [{**GOOD_PLAN["changes"][0], "path": ".git/config"}]}, "inside the repo"),
        ({"subtasks": []}, "list the changes and the subtasks"),
        (
            {"subtasks": [{**GOOD_PLAN["subtasks"][0], "files": ["src/other.ts"]}]},
            "not in changes",
        ),
        ({"subtasks": [{**GOOD_PLAN["subtasks"][0], "area": "QA"}]}, "FE"),
        (
            {"conventions": [{"what": "x", "example": "src/nope.tsx"}]},
            "convention example src/nope.tsx doesn't exist",
        ),
        (
            {"changes": [{**GOOD_PLAN["changes"][0], "action": "delete"}]},
            "can't delete it",
        ),
        (
            {
                "subtasks": [
                    {**GOOD_PLAN["subtasks"][0], "area": "FE"},
                    {**GOOD_PLAN["subtasks"][0], "area": "BE", "title": "API"},
                ]
            },
            "BE comes first",
        ),
        (
            {
                "subtasks": [
                    {**GOOD_PLAN["subtasks"][0], "area": "BE", "title": "API"},
                    {**GOOD_PLAN["subtasks"][0], "area": "FE"},
                ]
            },
            "define the contract",
        ),
    ],
)
def test_bad_plans_are_rejected(repo: Path, change: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message.replace("[", r"\[").replace("]", r"\]")):
        checked(repo).model_validate({**GOOD_PLAN, **change})


def test_a_plan_with_conflicts_may_skip_changes(repo: Path) -> None:
    plan = checked(repo).model_validate(
        {
            "notes": "Static site, no backend.",
            "changes": [],
            "conventions": [],
            "assumptions": [],
            "contract": "",
            "dependencies": [],
            "unrelated_issues": [],
            "conflicts": [
                {
                    "description": "The form must email support, but there's no backend",
                    "question": "Should submissions go to an email service, and which one?",
                }
            ],
            "subtasks": [],
        }
    )
    assert len(plan.conflicts) == 1


def test_a_plan_with_conflicts_leaves_subtasks_empty(repo: Path) -> None:
    conflict = {"description": "No backend", "question": "Which email service?"}
    with pytest.raises(ValidationError, match="leave subtasks empty"):
        checked(repo).model_validate({**GOOD_PLAN, "conflicts": [conflict]})


def test_planner_can_look_but_not_touch(origin: str, tmp_path: Path) -> None:  # noqa: F811
    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()
    (graph_dir / "GRAPH_REPORT.md").write_text("# Graph Report\nGod nodes: Home()")
    with Workspace.clone(origin) as ws:
        (ws.path / "src/app").mkdir(parents=True)
        (ws.path / "src/app/page.tsx").write_text("export default function Home() {}\n")
        git("add", ".", cwd=ws.path)
        git("commit", "--quiet", "-m", "app", cwd=ws.path)

        script = Script(
            reply(call("read_file", {"path": "src/app/page.tsx"})),
            reply(
                call("edit_file", {"path": "src/app/page.tsx", "old_text": "Home", "new_text": "X"})
            ),
            reply(call("run", {"command": "rm -rf ."})),
            reply(call("finish", GOOD_PLAN)),
        )
        plan = plan_ticket(
            script.router(), SPEC, ws, CodeGraphFiles(graph_dir, "abc"), agent_run_id=1
        )
        assert (ws.path / "src/app/page.tsx").read_text() == "export default function Home() {}\n"

    assert plan.changes[0].path == "src/app/contact/page.tsx"
    results = [m["content"] for m in script.sent[-1]["messages"] if m["role"] == "tool"]
    assert "export default function Home()" in results[0]
    assert results[1].startswith("ERROR: 'edit_file' is not available")
    assert results[2].startswith("ERROR: 'run' is not available")

    # What the planner was told and offered
    first = script.sent[0]
    task = first["messages"][1]["content"]
    assert "1. Visiting /contact shows a form" in task
    assert "src/app/page.tsx" in task  # file tree
    assert "God nodes: Home()" in task  # graph report
    offered = [t["function"]["name"] for t in first["tools"]]
    assert offered == [
        "list_files", "search", "read_file",
        "graph_query", "graph_explain", "graph_affected", "finish",
    ]  # fmt: skip
    assert first["model"] == "minimax/minimax-m3"
    assert json.dumps(first).count("edit_file") == 0
