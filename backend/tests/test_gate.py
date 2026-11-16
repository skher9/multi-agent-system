"""The gate's scans, the fixer mode, the QA agent and the verify box, without a sandbox."""

import json
from pathlib import Path
from typing import Any

import pytest

from agents.developer import develop_ticket
from agents.gate import added_lines, run_gate, scan
from agents.planner import Plan
from agents.qa import qa_markdown, qa_ticket
from agents.quality import QualityFindings
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


def test_the_gate_builds_the_app_when_the_repo_has_a_build_script(
    origin: str,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agents import quality
    from services.sandbox import SandboxResult

    commands: list[str] = []

    def fake_run(self: Workspace, command: list[str], limits: Any = None) -> SandboxResult:
        commands.append(command[-1])
        failed = command[-1] == "pnpm build"
        return SandboxResult(1 if failed else 0, "Route segment config", "", timed_out=False)

    monkeypatch.setattr(Workspace, "run", fake_run)
    monkeypatch.setattr(quality, "run_scanners", lambda workspace, files: None)
    with Workspace.clone(origin) as ws:
        base = ws.head_sha()
        no_script = run_gate(RepoTools(ws), ws, base)
        (ws.path / "package.json").write_text('{"scripts": {"build": "next build"}}')
        result = run_gate(RepoTools(ws), ws, base)
    assert "build" not in no_script.passed and no_script.ok
    assert commands[-4:] == ["pnpm lint", "pnpm typecheck", "pnpm test", "pnpm build"]
    assert result.passed["build"] is False and result.passed["lint"] is True
    assert result.failures == ["build failed (exit code 1):\nRoute segment config"]


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


CASES = {
    "cases": [
        {
            "criterion": 1,
            "title": "The contact page shows the form",
            "steps": ["Open /contact"],
            "expected": "A form with name, email and message",
        },
        {
            "criterion": 2,
            "title": "Sending the form thanks the user",
            "steps": ["Open /contact", "Fill the form", "Click Send"],
            "expected": "A thank-you message",
        },
    ]
}
QA_DONE = {"summary": "One test per case", "bugs": []}
TEST_FILE = {"path": "e2e/contact.spec.ts", "content": "test()\n"}


def report(folder: Path, failed: tuple[str, ...] = (), skip: tuple[str, ...] = ()) -> None:
    """Write Playwright's JSON report for CASES into the recordings folder, with a video
    per test."""
    specs = []
    for case in CASES["cases"]:
        title = case["title"]
        if title in skip:
            continue
        video = folder / "results" / f"{len(specs)}" / "video.webm"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"webm")
        inside = f"/mas-recordings/{video.relative_to(folder)}"
        result = {
            "duration": 1500,
            "errors": [{"message": "expected thanks"}] if title in failed else [],
            "attachments": [{"name": "video", "path": inside}],
        }
        specs.append(
            {
                "title": title,
                "file": "contact.spec.ts",
                "ok": title not in failed,
                "tests": [{"results": [result]}],
            }
        )
    (folder / "report.json").write_text(json.dumps({"suites": [{"specs": specs}]}))


@pytest.fixture
def e2e(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, str]]:
    """Fake browser test runs: append (exit code, output); default passes."""
    runs: list[tuple[int, str]] = []
    monkeypatch.setattr(RepoTools, "install", lambda self: "")
    monkeypatch.setattr(
        RepoTools, "run_e2e", lambda self, record_to=None: runs.pop(0) if runs else (0, "2 passed")
    )
    return runs


def test_qa_writes_only_e2e_tests_and_they_must_pass(
    origin: str,  # noqa: F811
    e2e: list[tuple[int, str]],
) -> None:
    e2e.append((1, "1 failed: thanks you"))  # the run at its first real finish
    script = Script(
        reply(call("create_file", {"path": "src/app/page.tsx", "content": "hack"})),
        reply(call("finish", QA_DONE)),  # no cases yet
        reply(call("plan_cases", {"cases": CASES["cases"][:1]})),  # misses criterion 2
        reply(call("plan_cases", CASES)),
        reply(call("create_file", TEST_FILE)),
        reply(call("finish", QA_DONE)),  # tests fail, no bugs listed
        reply(call("finish", QA_DONE)),
    )
    events: list[dict[str, Any]] = []
    with Workspace.clone(origin) as ws:
        result, files, videos = qa_ticket(
            script.router(),
            SPEC,
            PLAN,
            ws,
            agent_run_id=1,
            on_event=lambda _kind, data: events.append(data),
        )
        assert not (ws.path / "src/app/page.tsx").exists()
    assert files == ["e2e/contact.spec.ts"]
    assert [case.passed for case in result.cases] == [True, True]
    assert videos == [None, None]  # nothing was recorded here
    results = [m["content"] for m in script.sent[-1]["messages"] if m["role"] == "tool"]
    assert results[0].startswith("ERROR: you can only change files in e2e/")
    assert "save the test cases with plan_cases first" in results[1]
    assert "every criterion (1 to 2) needs at least one case" in results[2]
    assert results[3].startswith("2 test cases saved")
    assert "the browser tests failed" in results[5] and "1 failed: thanks you" in results[5]
    assert any("Planned 2 test cases" in str(e.get("text")) for e in events)
    assert script.sent[0]["model"] == "deepseek/deepseek-v4.1-flash"


def test_qa_reuses_a_browser_run_until_a_test_file_changes(
    origin: str,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs: list[int] = []
    monkeypatch.setattr(RepoTools, "install", lambda self: "")
    monkeypatch.setattr(
        RepoTools, "run_e2e", lambda self, record_to=None: (runs.append(1), (0, "2 passed"))[1]
    )
    spec = "e2e/contact.spec.ts"
    script = Script(
        reply(call("plan_cases", CASES)),
        reply(call("create_file", {"path": spec, "content": "test()\n"})),
        reply(call("run_e2e", {})),  # run 1
        reply(call("run_e2e", {})),  # nothing changed: reused
        reply(call("edit_file", {"path": spec, "old_text": "test()", "new_text": "test(1)"})),
        reply(call("run_e2e", {})),  # run 2
        reply(call("finish", QA_DONE)),  # nothing changed since run 2: reused
    )
    with Workspace.clone(origin) as ws:
        qa_ticket(script.router(), SPEC, PLAN, ws, agent_run_id=1)
    assert len(runs) == 2
    results = [m["content"] for m in script.sent[-1]["messages"] if m["role"] == "tool"]
    assert results[2] == "exit code 0\n2 passed"
    assert results[3].startswith("(no test file changed since the last run: same result)")


def test_qa_results_come_from_the_report_not_the_agent(
    origin: str,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    thanks = CASES["cases"][1]["title"]
    # Run 1: the second case has no test. Run 2: it fails. The agent says nothing failed
    runs: list[dict[str, Any]] = [{"skip": (thanks,)}, {"failed": (thanks,)}, {"failed": (thanks,)}]

    def fake_run(self: RepoTools, record_to: Path | None = None) -> tuple[int, str]:
        assert record_to == tmp_path
        run = runs.pop(0)
        report(tmp_path, **run)
        return (1, "1 failed") if run.get("failed") else (0, "1 passed")

    monkeypatch.setattr(RepoTools, "install", lambda self: "")
    monkeypatch.setattr(RepoTools, "run_e2e", fake_run)
    bug = {"criterion": 2, "problem": "Send does nothing", "test": thanks}
    script = Script(
        reply(call("plan_cases", CASES)),
        reply(call("create_file", TEST_FILE)),
        reply(call("finish", QA_DONE)),  # a case without a test
        reply(
            call("edit_file", {"path": TEST_FILE["path"], "old_text": "test()", "new_text": "t(2)"})
        ),
        reply(call("finish", {**QA_DONE, "bugs": [{**bug, "criterion": 1}]})),  # wrong criterion
        reply(call("finish", {**QA_DONE, "bugs": [bug]})),
    )
    with Workspace.clone(origin) as ws:
        result, _files, videos = qa_ticket(
            script.router(), SPEC, PLAN, ws, agent_run_id=1, record_to=tmp_path
        )
    results = [m["content"] for m in script.sent[-1]["messages"] if m["role"] == "tool"]
    assert "have no browser test with exactly their title" in results[2] and thanks in results[2]
    assert "the tests for criterion [2] fail and no bug explains them" in results[4]
    assert [case.passed for case in result.cases] == [True, False]
    assert result.cases[1].error == "expected thanks" and result.cases[1].seconds == 1.5
    assert [video is not None and video.read_bytes() == b"webm" for video in videos] == [True, True]

    linked = result.model_copy(
        update={
            "cases": [c.model_copy(update={"video": "https://x/t/1.webm"}) for c in result.cases]
        }
    )
    table = qa_markdown(linked, SPEC.acceptance_criteria)
    assert "2 test cases run in a real browser: 1 passed, 1 failed. Each one was recorded" in table
    assert f"| 2 | {thanks} | 2 | ❌ | [▶ Watch (2s)](https://x/t/1.webm) |" in table
    assert "Criterion 2: Submitting thanks you" in table and "3. Click Send" in table
    assert f"- Criterion 2: Send does nothing (`{thanks}`)" in table


def qa_report() -> Any:
    from agents.qa import QaReport

    cases = [{**case, "passed": True} for case in CASES["cases"]]
    return QaReport.model_validate({"summary": "One test per case", "cases": cases})


def test_make_verify_fixes_then_tests_then_pushes(
    origin: str,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import contextmanager

    from agents.developer import DevResult
    from agents.gate import GateResult
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
    notes = QualityFindings(ran=True, notes=["e2e/contact.spec.ts:1-6 repeats itself"])
    monkeypatch.setattr(runner, "scan_code", lambda ws, diff: notes)

    def fake_fixer(*args: Any, **kwargs: Any) -> DevResult:
        assert kwargs["failures"] == ["lint failed"]
        (args[3].path / "a.ts").write_text("fixed\n")
        return DevResult(summary="Fixed lint", changed_files=["a.ts"])

    def fake_qa(router: Any, spec: Any, plan: Any, ws: Workspace, **_: Any) -> Any:
        (ws.path / "e2e").mkdir()
        (ws.path / "e2e/contact.spec.ts").write_text("test()\n")
        videos = [ws.path.parent / "one.webm", None]
        videos[0].write_bytes(b"webm")  # type: ignore[union-attr]
        return qa_report(), ["e2e/contact.spec.ts"], videos

    monkeypatch.setattr(runner, "develop_ticket", fake_fixer)
    monkeypatch.setattr(runner, "qa_ticket", fake_qa)
    roles: list[str] = []

    @contextmanager
    def start_agent(role: str) -> Any:
        roles.append(role)
        yield len(roles)

    uploads: dict[str, bytes] = {}

    class Store:
        def upload(self, key: str, data: bytes, content_type: str = "") -> None:
            assert content_type == "video/webm"
            uploads[key] = data

        def download(self, key: str) -> bytes:
            return uploads[key]

    pipeline = runner.Pipeline(
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        1,
        repo_url=origin,
        storage=Store(),
        recordings_url="https://api.test/recordings/",
    )
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
    assert result.notes == ["e2e/contact.spec.ts:1-6 repeats itself"]  # scanned after QA
    assert result.qa is not None and not result.problem
    (key,) = uploads  # one video uploaded, behind a long random token
    assert key.startswith("recordings/") and key.endswith("/1.webm") and len(key) > 40
    links = [case.video for case in result.qa.cases]
    assert links == [f"https://api.test/{key}", ""]
    remote = Path(origin.removeprefix("file://"))
    log = git("log", "--format=%s", "agent/KAN-4", cwd=remote)
    assert log.splitlines()[:2] == ["KAN-4: browser tests", "KAN-4: fix the final checks"]
    assert result.head_sha == git("rev-parse", "agent/KAN-4", cwd=remote).strip()
