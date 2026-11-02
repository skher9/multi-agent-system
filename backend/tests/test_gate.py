"""The gate's scans, the fixer mode, the QA agent and the verify box, without a sandbox."""

import json
from pathlib import Path
from typing import Any

import pytest

from agents.developer import develop_ticket
from agents.gate import added_lines, run_gate, scan
from agents.planner import Plan
from agents.qa import qa_markdown, qa_ticket
from agents.repo_tools import RepoTools
from services.workspace import Workspace
from tests.test_agent_loop import Script, call, reply
from tests.test_developer import fake_checks  # noqa: F401  (fixture)
from tests.test_planner import GOOD_PLAN, SPEC
from tests.test_workspace import git, origin  # noqa: F401  (origin is a fixture)

PLAN = Plan.model_validate(GOOD_PLAN)

DIFF = """\
diff --git a/src/app/page.tsx b/src/app/page.tsx
--- a/src/app/page.tsx
+++ b/src/app/page.tsx
@@ -1,3 +1,3 @@
-export default function Home() { return <main>Hi</main> }
+// ... rest of the code unchanged
+const key = "sk-or-v1-abcdefghijklmnopqrstuvwxyz123456"
 export const x = 1
diff --git a/old.ts b/old.ts
--- a/old.ts
+++ /dev/null
@@ -1 +0,0 @@
-gone
"""


def test_added_lines_know_their_file_and_skip_deletions() -> None:
    lines = added_lines(DIFF)
    assert [(line.path, line.text) for line in lines] == [
        ("src/app/page.tsx", "// ... rest of the code unchanged"),
        ("src/app/page.tsx", 'const key = "sk-or-v1-abcdefghijklmnopqrstuvwxyz123456"'),
    ]


def test_scan_finds_placeholders_and_secrets_without_repeating_the_secret() -> None:
    found = scan(added_lines(DIFF))
    assert found["placeholders"] == ["src/app/page.tsx: // ... rest of the code unchanged"]
    assert found["secrets"] == ["src/app/page.tsx: looks like a API key (sk-...)"]
    assert "abcdefghij" not in json.dumps(found)


@pytest.mark.parametrize(
    "line",
    [
        "// TODO: implement validation",
        "{/* existing code here */}",
        "-----BEGIN RSA PRIVATE KEY-----",
        "token = 'ghp_" + "a" * 36 + "'",
        "AKIAABCDEFGHIJKLMNOP",
    ],
)
def test_scan_catches(line: str) -> None:
    found = scan(added_lines(f"+++ b/a.ts\n+{line}\n"))
    assert found["placeholders"] or found["secrets"]


@pytest.mark.parametrize(
    "line", ["const rest = items.slice(1)", "// the form keeps the existing value", "skip-link"]
)
def test_scan_leaves_ordinary_code_alone(line: str) -> None:
    assert scan(added_lines(f"+++ b/a.ts\n+{line}\n")) == {"placeholders": [], "secrets": []}


def test_run_gate_reports_each_check_and_scan(
    origin: str,  # noqa: F811
    fake_checks: list[list[str]],  # noqa: F811
) -> None:
    fake_checks.append(["lint failed (exit code 1):\nunused variable"])
    with Workspace.clone(origin) as ws:
        base = ws.head_sha()
        (ws.path / "a.ts").write_text("// TODO: implement\n")
        git("add", ".", cwd=ws.path)
        git("commit", "--quiet", "-m", "x", cwd=ws.path)
        result = run_gate(RepoTools(ws), ws, base)
    assert result.passed == {
        "lint": False,
        "typecheck": True,
        "unit tests": True,
        "placeholders": False,
        "secrets": True,
    }
    assert not result.ok
    assert result.failures[1].startswith("placeholders found in added lines:\na.ts:")


def test_the_fixer_gets_only_the_failures_and_must_pass_the_gate(
    origin: str,  # noqa: F811
    fake_checks: list[list[str]],  # noqa: F811
) -> None:
    gate_runs: list[list[str]] = [["secrets found in added lines:\na.ts: looks like a key"], []]
    script = Script(
        reply(call("create_file", {"path": "src/fix.ts", "content": "ok\n"})),
        reply(call("finish", {"summary": "Moved the key to an env var"})),  # gate still fails
        reply(call("finish", {"summary": "Moved the key to an env var"})),
    )
    with Workspace.clone(origin) as ws:
        result = develop_ticket(
            script.router(),
            SPEC,
            PLAN,
            ws,
            agent_run_id=1,
            failures=["lint failed (exit code 1):\nunused variable"],
            check=lambda: gate_runs.pop(0),
        )
    assert result.summary == "Moved the key to an env var"
    task = script.sent[0]["messages"][1]["content"]
    assert (
        "<check_failures>\nlint failed (exit code 1):\nunused variable\n</check_failures>" in task
    )
    assert "Your subtask: [" not in task  # not a build: no subtask
    rejected = [m["content"] for m in script.sent[-1]["messages"] if m["role"] == "tool"][1]
    assert "secrets found" in rejected


QA_OK = {
    "summary": "One test per criterion",
    "results": [
        {"number": 1, "test": "e2e/contact.spec.ts: shows the form", "passed": True},
        {"number": 2, "test": "e2e/contact.spec.ts: thanks you", "passed": True},
    ],
    "bugs": [],
}


@pytest.fixture
def e2e(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, str]]:
    """Fake browser test runs: append (exit code, output); default passes."""
    runs: list[tuple[int, str]] = []
    monkeypatch.setattr(RepoTools, "install", lambda self: "")
    monkeypatch.setattr(RepoTools, "run_e2e", lambda self: runs.pop(0) if runs else (0, "2 passed"))
    return runs


def test_qa_writes_only_e2e_tests_and_they_must_pass(
    origin: str,  # noqa: F811
    e2e: list[tuple[int, str]],
) -> None:
    e2e.append((1, "1 failed: thanks you"))  # the run at its first finish
    script = Script(
        reply(call("create_file", {"path": "src/app/page.tsx", "content": "hack"})),
        reply(call("create_file", {"path": "e2e/contact.spec.ts", "content": "test()\n"})),
        reply(call("finish", {**QA_OK, "results": QA_OK["results"][:1]})),  # misses criterion 2
        reply(call("finish", QA_OK)),  # tests fail, no bugs listed
        reply(call("finish", QA_OK)),
    )
    with Workspace.clone(origin) as ws:
        report, files = qa_ticket(script.router(), SPEC, PLAN, ws, agent_run_id=1)
        assert not (ws.path / "src/app/page.tsx").exists()
    assert files == ["e2e/contact.spec.ts"]
    assert report.results[1].passed
    results = [m["content"] for m in script.sent[-1]["messages"] if m["role"] == "tool"]
    assert results[0].startswith("ERROR: you can only change files in e2e/")
    assert "criterion 1 to 2 exactly once" in results[2]
    assert "the browser tests failed" in results[3] and "1 failed: thanks you" in results[3]
    assert script.sent[0]["model"] == "minimax/minimax-m3"


def test_qa_may_finish_with_failing_tests_when_it_names_the_bugs(
    origin: str,  # noqa: F811
    e2e: list[tuple[int, str]],
) -> None:
    e2e.append((1, "1 failed"))
    bug = {"criterion": 2, "problem": "Submit does nothing", "test": "e2e/contact.spec.ts"}
    results: list[Any] = [QA_OK["results"][0], {**QA_OK["results"][1], "passed": False}]
    script = Script(
        reply(call("create_file", {"path": "e2e/contact.spec.ts", "content": "test()\n"})),
        reply(call("finish", {**QA_OK, "results": results, "bugs": [bug]})),
    )
    with Workspace.clone(origin) as ws:
        report, _files = qa_ticket(script.router(), SPEC, PLAN, ws, agent_run_id=1)
    table = qa_markdown(report, SPEC.acceptance_criteria)
    assert "| 2. Submitting thanks you | ❌ | e2e/contact.spec.ts: thanks you |" in table
    assert "- Criterion 2: Submit does nothing (`e2e/contact.spec.ts`)" in table


def test_make_verify_fixes_then_tests_then_pushes(
    origin: str,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import contextmanager

    from agents.developer import DevResult
    from agents.gate import GateResult
    from agents.qa import QaReport
    from orchestrator import runner

    with Workspace.clone(origin) as ws:
        base = ws.head_sha()
        ws.create_branch("agent/KAN-4")
        (ws.path / "a.ts").write_text("x\n")
        git("add", ".", cwd=ws.path)
        git("commit", "--quiet", "-m", "dev", cwd=ws.path)
        ws.push("agent/KAN-4")

    gates = [GateResult(passed={"lint": False, "secrets": True}, failures=["lint failed"])]
    monkeypatch.setattr(RepoTools, "install", lambda self: "")
    monkeypatch.setattr(runner, "run_gate", lambda tools, ws, base: gates.pop(0))
    monkeypatch.setattr(runner, "project_rules", lambda factory, project_id: [])  # no database

    def fake_fixer(*args: Any, **kwargs: Any) -> DevResult:
        assert kwargs["failures"] == ["lint failed"]
        (args[3].path / "a.ts").write_text("fixed\n")
        return DevResult(summary="Fixed lint", changed_files=["a.ts"])

    def fake_qa(router: Any, spec: Any, plan: Any, ws: Workspace, **_: Any) -> Any:
        (ws.path / "e2e").mkdir()
        (ws.path / "e2e/contact.spec.ts").write_text("test()\n")
        return QaReport.model_validate(QA_OK), ["e2e/contact.spec.ts"]

    monkeypatch.setattr(runner, "develop_ticket", fake_fixer)
    monkeypatch.setattr(runner, "qa_ticket", fake_qa)
    roles: list[str] = []

    @contextmanager
    def start_agent(role: str) -> Any:
        roles.append(role)
        yield len(roles)

    pipeline = runner.Pipeline(None, None, None, 1, repo_url=origin)  # type: ignore[arg-type]
    result = runner.make_verify(
        pipeline,
        "KAN-4",
        SPEC,
        PLAN,
        "agent/KAN-4",
        base,
        start_agent,
        lambda _id: lambda k, d: None,
    )

    assert roles == ["fixer", "qa"]
    assert result.checks == {"lint": True, "secrets": True}
    assert result.fixer_summary == "Fixed lint"
    assert result.qa is not None and not result.problem
    remote = Path(origin.removeprefix("file://"))
    log = git("log", "--format=%s", "agent/KAN-4", cwd=remote)
    assert log.splitlines()[:2] == ["KAN-4: browser tests", "KAN-4: fix the final checks"]
    assert result.head_sha == git("rev-parse", "agent/KAN-4", cwd=remote).strip()
