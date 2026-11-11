"""The gate's code-quality scans: reading the scanners' reports without a sandbox, and
one real run in the sandbox under `docker`."""

from typing import Any

import pytest

from agents import quality
from agents.gate import run_gate
from agents.quality import added_line_numbers, clone_findings, scan_code, smell_findings
from agents.repo_tools import RepoTools
from services.workspace import Workspace
from tests.test_developer import fake_checks  # noqa: F401  (fixture)
from tests.test_sandbox import docker
from tests.test_workspace import git, origin  # noqa: F401  (origin is a fixture)

DIFF = """\
diff --git a/src/a.ts b/src/a.ts
--- a/src/a.ts
+++ b/src/a.ts
@@ -1,3 +1,4 @@
 const one = 1;
-const two = 2;
+const two = 22;
+const three = 3;
 export { one };
@@ -10 +11,2 @@ function later() {
 context
+added far down
diff --git a/old.ts b/old.ts
--- a/old.ts
+++ /dev/null
@@ -1 +0,0 @@
-gone
"""
ADDED = {"src/a.ts": {2, 3, 12}}


def clone(a: tuple[str, int, int], b: tuple[str, int, int], lines: int, tokens: int) -> Any:
    side = lambda s: {"name": f"/workspace/{s[0]}", "start": s[1], "end": s[2]}  # noqa: E731
    return {"firstFile": side(a), "secondFile": side(b), "lines": lines, "tokens": tokens}


def test_added_line_numbers_are_the_new_files_line_numbers() -> None:
    assert added_line_numbers(DIFF) == ADDED


def test_smells_count_only_sonar_rules_on_added_lines() -> None:
    report = [
        {
            "filePath": "/workspace/src/a.ts",
            "messages": [
                {"ruleId": "sonarjs/super-linear-regex", "line": 3, "message": "Slow regex."},
                {"ruleId": "sonarjs/no-dead-store", "line": 7, "message": "Old code."},
                {"ruleId": None, "line": 2, "message": "Parsing error"},
                {"ruleId": "no-unused-vars", "line": 2, "message": "Not ours to judge."},
            ],
        },
        {"filePath": "/workspace/src/untouched.ts", "messages": []},
    ]
    assert smell_findings(report, ADDED) == ["src/a.ts:3 [sonarjs/super-linear-regex] Slow regex."]
    assert smell_findings({"not": "a list"}, ADDED) == []


def test_big_copies_block_and_small_repeats_become_notes() -> None:
    report = {
        "duplicates": [
            clone(("src/a.ts", 1, 14), ("src/b.ts", 30, 43), lines=14, tokens=120),
            clone(("src/a.ts", 10, 15), ("src/a.ts", 20, 25), lines=6, tokens=45),
            clone(("src/old.ts", 1, 40), ("src/older.ts", 1, 40), lines=40, tokens=300),
        ]
    }
    blocking, notes = clone_findings(report, ADDED)
    assert blocking == ["src/a.ts:1-14 repeats src/b.ts:30-43 (14 lines)"]
    assert notes == ["src/a.ts:10-15 repeats src/a.ts:20-25 (6 lines)"]  # touches line 12
    assert clone_findings({}, ADDED) == ([], [])


def test_scan_skips_when_nothing_to_scan_or_no_scanners(
    origin: str,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[list[str]] = []
    monkeypatch.setattr(
        quality, "run_scanners", lambda workspace, files: asked.append(files) or None
    )
    with Workspace.clone(origin) as ws:
        (ws.path / "src").mkdir(exist_ok=True)
        (ws.path / "src/a.ts").write_text("x\n")
        assert not scan_code(ws, "").ran
        assert not scan_code(ws, DIFF.replace("src/a.ts", "README.md")).ran
        assert asked == []  # no code files: the sandbox is never started
        assert not scan_code(ws, DIFF).ran  # the image has no scanners
        assert asked == [["src/a.ts"]]  # old.ts was deleted: nothing to scan there


def test_the_gate_fails_on_smells_and_big_copies_and_passes_notes_on(
    origin: str,  # noqa: F811
    fake_checks: list[list[str]],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eslint = [
        {
            "filePath": "/workspace/a.ts",
            "messages": [{"ruleId": "sonarjs/no-dead-store", "line": 1, "message": "Unused."}],
        }
    ]
    jscpd = {"duplicates": [clone(("a.ts", 1, 6), ("a.ts", 8, 13), lines=6, tokens=44)]}
    monkeypatch.setattr(quality, "run_scanners", lambda workspace, files: (eslint, jscpd))
    with Workspace.clone(origin) as ws:
        base = ws.head_sha()
        (ws.path / "a.ts").write_text("let x = 1;\n")  # not committed: still scanned
        result = run_gate(RepoTools(ws), ws, base)
    assert result.passed["code smells"] is False
    assert result.passed["duplication"] is True
    assert result.failures == [
        "code smells found in added lines:\na.ts:1 [sonarjs/no-dead-store] Unused."
    ]
    assert result.notes == ("a.ts:1-6 repeats a.ts:8-13 (6 lines)",)


SLOW_REGEX = "export const EMAIL = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;\n"
COPIED = "".join(
    f"export function total{n}(items: number[]): number {{\n"
    "  let sum = 0;\n"
    "  for (const item of items) {\n"
    "    if (item > 10) {\n"
    "      sum += item * 2;\n"
    "    } else if (item > 5) {\n"
    "      sum += item + 1;\n"
    "    } else {\n"
    "      sum -= item;\n"
    "    }\n"
    "  }\n"
    "  return sum > 100 ? 100 : sum;\n"
    "}\n\n"
    for n in (1, 2)
)


@docker
def test_real_scanners_find_a_slow_regex_and_a_copied_function(
    origin: str,  # noqa: F811
) -> None:
    with Workspace.clone(origin) as ws:
        base = ws.head_sha()
        (ws.path / "email.ts").write_text(SLOW_REGEX)
        (ws.path / "totals.ts").write_text(COPIED)
        git("add", ".", cwd=ws.path)
        git("commit", "--quiet", "-m", "x", cwd=ws.path)
        found = scan_code(ws, ws.diff(base))
    assert found.ran
    assert any("email.ts:1 [sonarjs/super-linear-regex]" in s for s in found.smells)
    assert any(d.startswith("totals.ts:") and "repeats totals.ts:" in d for d in found.duplication)
