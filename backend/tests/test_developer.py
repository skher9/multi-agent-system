"""Developer: can't finish until checks pass and a test was written. Fake model and checks;
the real template's checks run in the sandbox under `docker`."""

import shutil
import subprocess
from pathlib import Path

import pytest

from agents import developer, quality
from agents.developer import develop_ticket
from agents.planner import Plan
from agents.repo_tools import RepoTools
from agents.ticket_reader import TicketSpec
from services.workspace import Workspace
from tests.test_agent_loop import Script, call, reply
from tests.test_planner import GOOD_PLAN, SPEC
from tests.test_sandbox import docker
from tests.test_workspace import git, origin  # noqa: F401  (origin is a fixture)

PLAN = Plan.model_validate(GOOD_PLAN)
TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "nextjs-starter"


@pytest.fixture
def fake_checks(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Replaces install, the after-edit typecheck and run_checks. Append a list of
    failures to make the next finish fail with them; empty list (default) = all pass."""
    queue: list[list[str]] = []
    monkeypatch.setattr(RepoTools, "install", lambda self: "")
    monkeypatch.setattr(RepoTools, "_after_edit", lambda self: "")
    monkeypatch.setattr(RepoTools, "run_checks", lambda self: queue.pop(0) if queue else [])
    monkeypatch.setattr(quality, "run_scanners", lambda workspace, files: None)  # no sandbox
    return queue


def build(script: Script, ws: Workspace, spec: TicketSpec = SPEC) -> developer.DevResult:
    return develop_ticket(script.router(), spec, PLAN, ws, agent_run_id=1, subtask=PLAN.subtasks[0])


def test_finishes_once_code_and_tests_pass(
    origin: str,  # noqa: F811
    fake_checks: list[list[str]],
) -> None:
    fake_checks.append(["typecheck failed (exit code 2):\npage.tsx: Cannot find name 'x'"])
    script = Script(
        reply(call("create_file", {"path": "src/app/contact/page.tsx", "content": "x\n"})),
        reply(call("create_file", {"path": "src/app/contact/page.test.tsx", "content": "t\n"})),
        reply(call("finish", {"summary": "Contact page"})),  # checks fail
        reply(
            call(
                "edit_file", {"path": "src/app/contact/page.tsx", "old_text": "x", "new_text": "y"}
            )
        ),
        reply(call("finish", {"summary": "Contact page with a form"})),  # checks pass
    )
    with Workspace.clone(origin) as ws:
        result = build(script, ws)
        assert (ws.path / "src/app/contact/page.tsx").read_text() == "y\n"
    assert result.summary == "Contact page with a form"
    assert result.changed_files == ["src/app/contact/page.test.tsx", "src/app/contact/page.tsx"]
    failure = script.sent[3]["messages"][-1]["content"]
    assert "not done yet" in failure and "Cannot find name 'x'" in failure


def test_cannot_finish_without_a_test(origin: str, fake_checks: list[list[str]]) -> None:  # noqa: F811
    script = Script(
        reply(call("finish", {"summary": "nothing"})),
        reply(call("create_file", {"path": "src/app/contact/page.tsx", "content": "x\n"})),
        reply(call("finish", {"summary": "page only"})),
        reply(call("create_file", {"path": "src/app/__tests__/contact.test.tsx", "content": "t"})),
        reply(call("finish", {"summary": "page and test"})),
    )
    with Workspace.clone(origin) as ws:
        assert build(script, ws).summary == "page and test"
    errors = [m["content"] for m in script.sent[-1]["messages"] if m["role"] == "tool"]
    assert "haven't changed any files" in errors[0]
    assert "at least one test file" in errors[2]


def test_failed_install_stops_before_any_model_call(
    origin: str,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(RepoTools, "install", lambda self: "install failed (exit 1)")
    script = Script()
    with Workspace.clone(origin) as ws, pytest.raises(developer.DeveloperError):
        build(script, ws)
    assert script.sent == []


def test_a_problem_skips_the_checks_and_stops(
    origin: str,  # noqa: F811
    fake_checks: list[list[str]],
) -> None:
    fake_checks.append(["would fail"])
    problem = "The plan modifies src/app/page.tsx but the home page lives in src/pages"
    script = Script(reply(call("finish", {"summary": "Stopped", "problem": problem})))
    with Workspace.clone(origin) as ws:
        result = build(script, ws)
    assert result.problem == problem
    assert fake_checks == [["would fail"]]  # checks never ran


def test_subtask_or_review_is_required(origin: str) -> None:  # noqa: F811
    with Workspace.clone(origin) as ws, pytest.raises(ValueError, match="exactly one"):
        develop_ticket(Script().router(), SPEC, PLAN, ws, agent_run_id=1)


def test_task_carries_criteria_and_plan(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts": {"lint": "eslint"}}')
    task = developer._task(SPEC, PLAN, tmp_path, ["package.json"]) + developer._subtask_task(
        PLAN.subtasks[0]
    )
    assert "<project_context>" in task and "lint: eslint" in task
    assert "2. Submitting thanks you" in task
    assert "- create src/app/contact/page.tsx (criteria 1, 2): ContactPage with" in task
    assert "- Pages are default-exported server components (see src/app/page.tsx)" in task
    assert "- The link sits under the page heading" in task
    assert "Your subtask: [FE] Contact page" in task
    assert "- src/app/contact/page.test.tsx" in task


def test_branch_starts_at_a_given_commit_and_replace_push(origin: str) -> None:  # noqa: F811
    with Workspace.clone(origin) as ws:
        first = ws.head_sha()
        (ws.path / "a.txt").write_text("a")
        git("add", ".", cwd=ws.path)
        git("commit", "--quiet", "-m", "later", cwd=ws.path)
        ws.create_branch("agent/KAN-4", start=first)
        assert ws.head_sha() == first  # built on the planned commit, not the latest
        (ws.path / "b.txt").write_text("b")
        git("add", ".", cwd=ws.path)
        git("commit", "--quiet", "-m", "first try", cwd=ws.path)
        ws.push("agent/KAN-4")
    with Workspace.clone(origin) as ws:  # a rerun builds the branch again from scratch
        ws.create_branch("agent/KAN-4", start=first)
        (ws.path / "c.txt").write_text("c")
        git("add", ".", cwd=ws.path)
        git("commit", "--quiet", "-m", "redo", cwd=ws.path)
        with pytest.raises(Exception, match="push failed"):
            ws.push("agent/KAN-4")  # plain push can't overwrite
        ws.push("agent/KAN-4", replace=True)


def test_branch_start_must_be_a_sha(origin: str) -> None:  # noqa: F811
    with Workspace.clone(origin) as ws, pytest.raises(ValueError):
        ws.create_branch("agent/KAN-4", start="main; rm -rf /")


@docker
def test_real_checks_pass_on_the_template_then_catch_a_type_error(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    shutil.copytree(TEMPLATE, repo, ignore=shutil.ignore_patterns("node_modules", ".next"))
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)  # noqa: S607
    tools = RepoTools(Workspace(repo, None), typecheck_after_edit=False)
    assert tools.install() == ""
    assert tools.run_checks() == []
    (repo / "src/app/broken.ts").write_text("export const n: number = 'text'\n")
    [failure] = tools.run_checks()
    assert failure.startswith("typecheck failed")
