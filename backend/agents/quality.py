"""Code-quality scans for the gate: what a repo's own lint doesn't ask for. No model calls.

Two scanners run in the sandbox on the files a branch changed, and only findings on
lines the branch added count (old code is not the agents' to answer for):

- code smells: ESLint with SonarSource's rules (eslint-plugin-sonarjs): slow regular
  expressions, functions too tangled to follow, dead stores, duplicate branches.
- duplication: jscpd finds copied blocks. Big copies fail the gate; small repeats
  (common in tests) become notes for the reviewer instead.

The scanners live in the sandbox image at /opt/quality (sandbox/quality), outside the
repo, with their own config: a user's package.json and ESLint setup are never touched,
and nothing leaves the sandbox. An image without them skips the scans.
"""

import json
import logging
import re
import shlex
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from services.sandbox import SandboxLimits
from services.workspace import Workspace

TOOLS = "/opt/quality"
ESLINT = f"{TOOLS}/node_modules/.bin/eslint"
JSCPD = f"{TOOLS}/node_modules/.bin/jscpd"
REPORT_DIR = "/tmp/mas-quality"  # noqa: S108  (inside the throwaway sandbox)
CODE_FILE = re.compile(r"\.(js|jsx|mjs|cjs|ts|tsx|mts|cts)$")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
MAX_FILES = 200  # more changed files than this: scan the first ones
SCAN_TIMEOUT_SECONDS = 5 * 60
NO_TOOLS = "MAS_NO_QUALITY_TOOLS"
SPLIT = "MAS_QUALITY_SPLIT"

# The smallest repeat jscpd reports: becomes a note for the reviewer
NOTE_LINES, NOTE_TOKENS = 5, 40
# A copy this big fails the gate: no reviewer would let it through
BLOCK_LINES, BLOCK_TOKENS = 10, 70
MAX_FINDINGS = 20  # per scan, in what the fixer or reviewer reads

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QualityFindings:
    ran: bool = False  # False: the sandbox has no scanners, or nothing to scan
    smells: list[str] = field(default_factory=list)  # fail the gate
    duplication: list[str] = field(default_factory=list)  # fail the gate
    notes: list[str] = field(default_factory=list)  # small repeats, for the reviewer


def added_line_numbers(diff: str) -> dict[str, set[int]]:
    """For each file a unified diff adds lines to: those lines' numbers in the new file."""
    added: dict[str, set[int]] = {}
    path, line = "", 0
    for text in diff.splitlines():
        if text.startswith("+++ "):
            path = text.removeprefix("+++ ").removeprefix("b/")
        elif hunk := HUNK.match(text):
            line = int(hunk.group(1))
        elif text.startswith("+") and path != "/dev/null":
            added.setdefault(path, set()).add(line)
            line += 1
        elif not text.startswith("-"):
            line += 1  # a context line; removed lines aren't in the new file
    return added


def scan_code(workspace: Workspace, diff: str) -> QualityFindings:
    """Run both scanners on the code files the diff adds lines to."""
    added = added_line_numbers(diff)
    files = sorted(p for p in added if CODE_FILE.search(p) and (workspace.path / p).is_file())
    if not files:
        return QualityFindings()
    raw = run_scanners(workspace, files[:MAX_FILES])
    if raw is None:
        return QualityFindings()
    eslint_json, jscpd_json = raw
    blocking, notes = clone_findings(jscpd_json, added)
    return QualityFindings(
        ran=True,
        smells=smell_findings(eslint_json, added)[:MAX_FINDINGS],
        duplication=blocking[:MAX_FINDINGS],
        notes=notes[:MAX_FINDINGS],
    )


def run_scanners(workspace: Workspace, files: list[str]) -> tuple[Any, Any] | None:
    """ESLint's and jscpd's JSON reports for these files, from one sandbox command.
    None if the scanners aren't in this sandbox image or their output can't be read:
    our tooling failing must not fail someone's run."""
    paths = " ".join(shlex.quote(f) for f in files)
    command = (
        f"test -x {ESLINT} || {{ echo {NO_TOOLS}; exit 0; }}; "
        # --no-inline-config: an eslint-disable comment can't hide a finding
        f"{ESLINT} -c {TOOLS}/eslint.config.mjs --no-inline-config --no-warn-ignored"
        f" -f json {paths}; echo; echo {SPLIT}; "
        f"rm -rf {REPORT_DIR}; {JSCPD} --silent --absolute --min-lines {NOTE_LINES}"
        f" --min-tokens {NOTE_TOKENS} --reporters json --output {REPORT_DIR} {paths}"
        f" >/dev/null 2>&1; cat {REPORT_DIR}/jscpd-report.json 2>/dev/null || echo '{{}}'"
    )
    result = workspace.run(
        ["bash", "-c", command], SandboxLimits(timeout_seconds=SCAN_TIMEOUT_SECONDS)
    )
    if NO_TOOLS in result.stdout:
        logger.warning("quality scanners not in this sandbox image: scans skipped")
        return None
    eslint_out, _, jscpd_out = result.stdout.partition(SPLIT)
    try:
        return json.loads(eslint_out), json.loads(jscpd_out)
    except json.JSONDecodeError:
        logger.warning("quality scanners gave no report: %s", result.stderr[-500:])
        return None


def smell_findings(eslint_json: Any, added: dict[str, set[int]]) -> list[str]:
    """SonarSource rule findings on added lines, as "path:line [rule] message"."""
    found = []
    for file in eslint_json if isinstance(eslint_json, list) else []:
        path = _relative(str(file.get("filePath", "")))
        for message in file.get("messages", []):
            rule = message.get("ruleId") or ""
            if rule.startswith("sonarjs/") and message.get("line") in added.get(path, ()):
                found.append(f"{path}:{message['line']} [{rule}] {message['message']}")
    return found


def clone_findings(jscpd_json: Any, added: dict[str, set[int]]) -> tuple[list[str], list[str]]:
    """Copied blocks that touch added lines: (the big ones, the small ones)."""
    blocking, notes = [], []
    duplicates = jscpd_json.get("duplicates", []) if isinstance(jscpd_json, dict) else []
    for clone in duplicates:
        first, second = clone["firstFile"], clone["secondFile"]
        sides = [(_relative(s["name"]), int(s["start"]), int(s["end"])) for s in (first, second)]
        if not any(added.get(path, set()) & set(range(a, b + 1)) for path, a, b in sides):
            continue
        (path_a, a1, a2), (path_b, b1, b2) = sides
        lines, tokens = int(clone.get("lines", 0)), int(clone.get("tokens", 0))
        text = f"{path_a}:{a1}-{a2} repeats {path_b}:{b1}-{b2} ({lines} lines)"
        if lines >= BLOCK_LINES and tokens >= BLOCK_TOKENS:
            blocking.append(text)
        else:
            notes.append(text)
    return blocking, notes


def _relative(path: str) -> str:
    """A scanner's absolute sandbox path as a repo path: /workspace/src/a.ts -> src/a.ts."""
    posix = PurePosixPath(path)
    return str(posix.relative_to("/workspace")) if posix.is_relative_to("/workspace") else path
