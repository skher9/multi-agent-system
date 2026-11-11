"""The gate: plain-code checks on the whole branch before a PR opens. No model calls.

Each subtask already passed lint, typecheck and the unit tests on its own; the gate runs
them once more on the finished branch (a later subtask can break an earlier one), and
adds scans of the lines the agents added:

- placeholders: code swapped for "// ... rest of the code" or "TODO: implement", which
  models sometimes write instead of the real thing, silently deleting what was there.
- secrets: API keys or private keys pasted into code.
- code smells and duplication (agents/quality.py): SonarSource's rules and a copied-code
  finder, stricter than most repos' own lint.

Code checks, agents fix and judge: a failure here goes to the fixer agent.
"""

import re
from dataclasses import dataclass

from pydantic import BaseModel

from agents.qa import QaReport
from agents.quality import scan_code
from agents.repo_tools import CHECKS, RepoTools
from services.workspace import Workspace

PLACEHOLDERS = re.compile(
    r"(rest|remainder) of (the )?(code|file|implementation|component)"
    r"|(existing|previous|other) code (here|unchanged|remains|goes)"
    r"|\.\.\.\s*(existing|unchanged|same as before)"
    r"|todo:?\s*implement"
    r"|(implementation|your code) (goes )?here",
    re.IGNORECASE,
)
SECRETS = {
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,}"),
    "API key (sk-...)": re.compile(r"\bsk-(or-|proj-|ant-)?[A-Za-z0-9_-]{24,}"),
    "Stripe live key": re.compile(r"\b[sr]k_live_[A-Za-z0-9]{16,}"),
    "Slack token": re.compile(r"xox[abposr]-[A-Za-z0-9-]{10,}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
SCANS = ("placeholders", "secrets")


@dataclass(frozen=True)
class AddedLine:
    path: str
    text: str


@dataclass(frozen=True)
class GateResult:
    passed: dict[str, bool]  # each check and scan by name -> passed?
    failures: list[str]  # what failed, with output, for the fixer
    notes: tuple[str, ...] = ()  # small things that don't fail the gate, for the reviewer

    @property
    def ok(self) -> bool:
        return not self.failures


class VerifyResult(BaseModel):
    """What the verify box found: the gate, the fixer's work if it ran, the QA report."""

    checks: dict[str, bool]  # the final gate, each check and scan by name
    fixer_summary: str = ""  # empty: the gate passed first time
    qa: QaReport | None = None  # None: QA couldn't finish (the PR says so)
    head_sha: str = ""
    notes: list[str] = []  # the gate's notes for the reviewer (small repeats)
    problem: str = ""  # non-empty: the gate still fails, a human needs to look


def added_lines(diff: str) -> list[AddedLine]:
    """The lines a unified diff adds, with the file each is in."""
    lines, path = [], ""
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line.removeprefix("+++ ").removeprefix("b/")
        elif line.startswith("+") and path != "/dev/null":
            lines.append(AddedLine(path, line[1:]))
    return lines


def scan(added: list[AddedLine]) -> dict[str, list[str]]:
    """Placeholder and secret findings in added lines, by scan name. A secret's value is
    never repeated in a finding, only where it is and what kind."""
    found: dict[str, list[str]] = {name: [] for name in SCANS}
    for line in added:
        if PLACEHOLDERS.search(line.text):
            found["placeholders"].append(f"{line.path}: {line.text.strip()[:160]}")
        for kind, pattern in SECRETS.items():
            if pattern.search(line.text):
                found["secrets"].append(f"{line.path}: looks like a {kind}")
    return found


def run_gate(tools: RepoTools, workspace: Workspace, base_sha: str) -> GateResult:
    """Every check and scan on the branch since base_sha (the planned commit), counting
    work not committed yet: the fixer's finish runs this before its commit."""
    check_failures = tools.run_checks()
    passed = {
        name: not any(f.startswith(f"{name} failed") for f in check_failures) for name in CHECKS
    }
    failures = list(check_failures)
    diff = workspace.diff(base_sha, uncommitted=True)
    found = scan(added_lines(diff))
    quality = scan_code(workspace, diff)
    if quality.ran:
        found |= {"code smells": quality.smells, "duplication": quality.duplication}
    for name, findings in found.items():
        passed[name] = not findings
        if findings:
            failures.append(f"{name} found in added lines:\n" + "\n".join(findings))
    return GateResult(passed=passed, failures=failures, notes=tuple(quality.notes))
