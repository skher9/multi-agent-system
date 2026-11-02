"""The tools a coding agent uses on a repo: look around, change files, run things.

The model asks for a tool by name with JSON arguments; call() checks the arguments,
runs the tool, and returns plain text for the model to read. Problems come back as
"ERROR: ..." text, not exceptions, so the model can correct itself and carry on.

File tools work on the host, locked to the repo folder. Commands run in the sandbox.
"""

import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from services.sandbox import SandboxLimits
from services.workspace import Workspace

# Never listed or searched: generated, huge, or not ours to read.
SKIP_DIRS = {".git", "node_modules", ".next", "test-results", "playwright-report"}
MAX_LIST_ENTRIES = 300
MAX_SEARCH_MATCHES = 100
MAX_READ_LINES = 400
MAX_OUTPUT_LINES = 80  # long command output is cut to its last lines, where errors usually are
COMMAND_TIMEOUT_SECONDS = 5 * 60
E2E_TIMEOUT_SECONDS = 12 * 60  # a production build, a server start, then a browser
E2E = "pnpm test:e2e"
# Inside node_modules: ignored by git, so the report never ends up in a commit.
TEST_REPORT = "node_modules/.cache/vitest-report.json"

# What "done" means for code: every one must pass. Commands in the repo's package.json.
CHECKS = {"lint": "pnpm lint", "typecheck": "pnpm typecheck", "unit tests": "pnpm test"}
INSTALL = "pnpm install --frozen-lockfile --prefer-offline"
TEST_FILE = re.compile(r"(\.test\.|\.spec\.|(^|/)__tests__/)")

ANSI_ESCAPES = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")  # terminal colour codes


class ToolError(Exception):
    """A problem the model should read and fix, e.g. a path outside the repo."""


# One model per tool: its fields are the arguments, its docstring the description
# the model sees, and its JSON schema goes in the tool definition.
class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListFiles(ToolArgs):
    """List files and folders under a path (generated folders like node_modules are skipped)."""

    path: str = Field(default=".", description="Folder relative to the repo root")


class Search(ToolArgs):
    """Find lines containing some exact text, across all files under a path."""

    text: str = Field(description="Exact text to find (case-sensitive, not a regex)")
    path: str = Field(default=".", description="Folder or file to search in")


class ReadFile(ToolArgs):
    """Read a file with line numbers. Large files: read a line range."""

    path: str
    start_line: int = Field(default=1, ge=1)
    end_line: int | None = Field(default=None, ge=1, description="Inclusive; default: up to 400")


class EditFile(ToolArgs):
    """Replace one exact piece of text in a file. old_text must appear exactly once."""

    path: str
    old_text: str = Field(description="Copied exactly from the file, including spaces")
    new_text: str


class CreateFile(ToolArgs):
    """Create a new file (and its folders). Fails if the file exists; use edit_file then."""

    path: str
    content: str


class DeleteFile(ToolArgs):
    """Delete a file the plan says to remove."""

    path: str


class Run(ToolArgs):
    """Run a shell command in the sandbox at the repo root (e.g. "pnpm lint")."""

    command: str


class RunTests(ToolArgs):
    """Run the unit tests and get a pass/fail list with failure messages."""


TOOL_ARGS: dict[str, type[ToolArgs]] = {
    "list_files": ListFiles,
    "search": Search,
    "read_file": ReadFile,
    "edit_file": EditFile,
    "create_file": CreateFile,
    "delete_file": DeleteFile,
    "run": Run,
    "run_tests": RunTests,
}


# The tools that only look: what the planner gets. RepoTools.call runs any tool, so
# the planner's dispatcher checks names against this before calling it.
READ_ONLY_TOOLS = ("list_files", "search", "read_file")


def tool_definitions() -> list[dict[str, Any]]:
    """The tools in the format chat() sends to the model."""
    return definitions(TOOL_ARGS)


def definitions(tools: Mapping[str, type[BaseModel]]) -> list[dict[str, Any]]:
    """Tool definitions for chat() from {name: argument model}."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": (args.__doc__ or "").strip(),
                "parameters": _parameters(args),
            },
        }
        for name, args in tools.items()
    ]


def _parameters(args: type[BaseModel]) -> dict[str, Any]:
    schema = args.model_json_schema()
    schema.pop("title", None)
    schema.pop("description", None)  # already the tool's description
    return schema


class RepoTools:
    def __init__(self, workspace: Workspace, typecheck_after_edit: bool = True) -> None:
        self._ws = workspace
        self._root = workspace.path.resolve()
        self._typecheck_after_edit = typecheck_after_edit
        self.changed_files: set[str] = set()  # for the handoff: what the agent touched
        self._handlers: dict[str, Callable[[Any], str]] = {
            "list_files": self._list_files,
            "search": self._search,
            "read_file": self._read_file,
            "edit_file": self._edit_file,
            "create_file": self._create_file,
            "delete_file": self._delete_file,
            "run": self._run,
            "run_tests": self._run_tests,
        }

    def call(self, name: str, arguments: str) -> str:
        """Run one tool call from the model. Always returns text, never raises."""
        args_model = TOOL_ARGS.get(name)
        if args_model is None:
            return f"ERROR: unknown tool {name!r}. Tools: {', '.join(TOOL_ARGS)}"
        try:
            args = args_model.model_validate(json.loads(arguments or "{}"))
        except (json.JSONDecodeError, ValidationError) as exc:
            return f"ERROR: bad arguments for {name}: {exc}"
        try:
            return self._handlers[name](args)
        except ToolError as exc:
            return f"ERROR: {exc}"

    # --- Paths -------------------------------------------------------------

    def _resolve(self, rel: str) -> Path:
        """Turn a model-given path into a real path, refusing anything outside the repo.

        resolve() follows symlinks and "..", so a link pointing at ~/.ssh is caught too.
        """
        path = (self._root / rel).resolve()
        if not path.is_relative_to(self._root):
            raise ToolError(f"{rel!r} is outside the repo")
        parts = path.relative_to(self._root).parts
        if parts and parts[0] == ".git":
            raise ToolError("the .git folder is off limits")
        if any(p == ".env" or (p.startswith(".env.") and p != ".env.example") for p in parts):
            raise ToolError("secret files (.env) are off limits")
        return path

    def _rel(self, path: Path) -> str:
        return path.relative_to(self._root).as_posix()

    def _walk(self, start: Path) -> list[Path]:
        if start.is_file():
            return [start]
        found = []
        for path in sorted(start.rglob("*")):
            if SKIP_DIRS.intersection(path.relative_to(self._root).parts):
                continue
            found.append(path)
        return found

    # --- Looking around ----------------------------------------------------

    def _list_files(self, args: ListFiles) -> str:
        start = self._resolve(args.path)
        if not start.is_dir():
            raise ToolError(f"{args.path!r} is not a folder")
        entries = [self._rel(p) + ("/" if p.is_dir() else "") for p in self._walk(start)]
        if len(entries) > MAX_LIST_ENTRIES:
            hidden = len(entries) - MAX_LIST_ENTRIES
            entries = [*entries[:MAX_LIST_ENTRIES], f"... {hidden} more; list a subfolder"]
        return "\n".join(entries) or "(empty)"

    def _search(self, args: Search) -> str:
        start = self._resolve(args.path)
        matches = []
        for path in self._walk(start):
            if not path.is_file():
                continue
            try:
                lines = path.read_text().splitlines()
            except (UnicodeDecodeError, OSError):
                continue  # binary or unreadable file
            for number, line in enumerate(lines, start=1):
                if args.text in line:
                    matches.append(f"{self._rel(path)}:{number}: {line.strip()[:200]}")
                    if len(matches) == MAX_SEARCH_MATCHES:
                        return "\n".join([*matches, "... more matches; narrow the search"])
        return "\n".join(matches) or "no matches"

    def _read_file(self, args: ReadFile) -> str:
        path = self._resolve(args.path)
        if not path.is_file():
            raise ToolError(f"{args.path!r} is not a file")
        try:
            lines = path.read_text().splitlines()
        except UnicodeDecodeError as exc:
            raise ToolError(f"{args.path!r} is not a text file") from exc
        end = min(args.end_line or args.start_line + MAX_READ_LINES - 1, len(lines))
        end = min(end, args.start_line + MAX_READ_LINES - 1)
        shown = [f"{n:>5}  {lines[n - 1]}" for n in range(args.start_line, end + 1)]
        footer = f"\n(lines {args.start_line}-{end} of {len(lines)})" if end < len(lines) else ""
        return ("\n".join(shown) or "(empty file)") + footer

    # --- Changing files ----------------------------------------------------

    def _edit_file(self, args: EditFile) -> str:
        path = self._resolve(args.path)
        if not path.is_file():
            raise ToolError(f"{args.path!r} doesn't exist; use create_file")
        text = path.read_text()
        count = text.count(args.old_text)
        if count != 1:
            raise ToolError(
                f"old_text appears {count} times in {args.path}; it must appear exactly once "
                "(include more surrounding lines to make it unique)"
            )
        path.write_text(text.replace(args.old_text, args.new_text))
        self.changed_files.add(self._rel(path))
        return f"Edited {args.path}." + self._after_edit()

    def _create_file(self, args: CreateFile) -> str:
        path = self._resolve(args.path)
        if path.exists():
            raise ToolError(f"{args.path!r} already exists; use edit_file")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args.content)
        self.changed_files.add(self._rel(path))
        return f"Created {args.path}." + self._after_edit()

    def _delete_file(self, args: DeleteFile) -> str:
        path = self._resolve(args.path)
        if not path.is_file():
            raise ToolError(f"{args.path!r} is not a file")
        path.unlink()
        self.changed_files.add(self._rel(path))
        return f"Deleted {args.path}." + self._after_edit()

    def _after_edit(self) -> str:
        """Type-check after every change (System Design doc), so mistakes surface at once."""
        if not self._typecheck_after_edit:
            return ""
        result = self._sandbox("pnpm typecheck")
        return " Type-check passed." if result[0] == 0 else f" Type-check FAILED:\n{result[1]}"

    # --- Running things ----------------------------------------------------

    def _run(self, args: Run) -> str:
        exit_code, output = self._sandbox(args.command)
        return f"exit code {exit_code}\n{output}"

    def _run_tests(self, _args: RunTests) -> str:
        report = self._root / TEST_REPORT
        report.unlink(missing_ok=True)
        exit_code, output = self._sandbox(
            f"pnpm exec vitest run --reporter=json --outputFile={TEST_REPORT}"
        )
        if not report.exists():
            # The tests didn't even start (e.g. a syntax error): show the raw output.
            return f"Tests could not run (exit code {exit_code}):\n{output}"
        return summarise_test_report(json.loads(report.read_text()))

    def install(self) -> str:
        """Install the repo's packages; return "" on success, else the error output."""
        exit_code, output = self._sandbox(INSTALL)
        return "" if exit_code == 0 else f"install failed (exit {exit_code}):\n{output}"

    def run_checks(self) -> list[str]:
        """Run every check in CHECKS; return the failures with their output (empty: all pass)."""
        failures = []
        for name, command in CHECKS.items():
            exit_code, output = self._sandbox(command)
            if exit_code != 0:
                failures.append(f"{name} failed (exit code {exit_code}):\n{output}")
        return failures

    def run_e2e(self) -> tuple[int, str]:
        """The browser tests (Playwright): exit code and output."""
        return self._sandbox(E2E, timeout_seconds=E2E_TIMEOUT_SECONDS)

    def _sandbox(
        self, command: str, timeout_seconds: int = COMMAND_TIMEOUT_SECONDS
    ) -> tuple[int, str]:
        result = self._ws.run(
            ["bash", "-c", command], SandboxLimits(timeout_seconds=timeout_seconds)
        )
        if result.timed_out:
            return -1, f"timed out after {timeout_seconds // 60} minutes"
        return result.exit_code, clean_output(result.stdout + result.stderr)


def clean_output(text: str) -> str:
    """Strip colour codes and keep the last lines, where errors usually are."""
    lines = ANSI_ESCAPES.sub("", text).strip().splitlines()
    if len(lines) > MAX_OUTPUT_LINES:
        cut = len(lines) - MAX_OUTPUT_LINES
        lines = [f"... ({cut} earlier lines cut)", *lines[-MAX_OUTPUT_LINES:]]
    return "\n".join(lines)


def summarise_test_report(report: dict[str, Any]) -> str:
    """vitest's JSON report as a short pass/fail list for the model."""
    lines = [
        f"{report['numPassedTests']} passed, {report['numFailedTests']} failed "
        f"(of {report['numTotalTests']})"
    ]
    for file in report["testResults"]:
        for test in file["assertionResults"]:
            mark = "PASS" if test["status"] == "passed" else test["status"].upper()
            lines.append(f"{mark}  {test['fullName']}")
            for message in test.get("failureMessages", []):
                lines.append("      " + clean_output(message).replace("\n", "\n      ")[:1000])
        # A test file that crashed before its tests ran reports only a message.
        if file["status"] == "failed" and not file["assertionResults"]:
            lines.append(f"FAILED TO LOAD  {file['name']}\n      {clean_output(file['message'])}")
    return "\n".join(lines)
