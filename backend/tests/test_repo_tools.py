"""Repo tools on a temp folder. Tests marked `docker` run real sandbox commands."""

import json
import shutil
from pathlib import Path

import pytest

from agents.repo_tools import (
    MAX_OUTPUT_LINES,
    RepoTools,
    clean_output,
    summarise_test_report,
    tool_definitions,
)
from services.workspace import Workspace
from tests.test_sandbox import docker

TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "nextjs-starter"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src" / "app").mkdir(parents=True)
    (root / "src" / "app" / "page.tsx").write_text(
        "export default function Home() {\n  return <h1>Hi</h1>;\n}\n"
    )
    (root / "README.md").write_text("# Demo\n")
    (root / ".env").write_text("SECRET=1\n")
    (root / "node_modules" / "pkg").mkdir(parents=True)
    (root / "node_modules" / "pkg" / "index.js").write_text("Hi\n")
    return root


@pytest.fixture
def tools(repo: Path) -> RepoTools:
    return RepoTools(Workspace(repo, token=None), typecheck_after_edit=False)


def call(tools: RepoTools, name: str, **args: object) -> str:
    return tools.call(name, json.dumps(args))


def test_definitions_cover_every_tool_with_a_schema() -> None:
    defs = {d["function"]["name"]: d["function"] for d in tool_definitions()}
    assert set(defs) == {
        "list_files", "search", "read_file", "edit_file", "create_file", "run", "run_tests",
    }  # fmt: skip
    edit = defs["edit_file"]
    assert "exactly once" in edit["description"]
    assert edit["parameters"]["required"] == ["path", "old_text", "new_text"]
    assert edit["parameters"]["additionalProperties"] is False


def test_list_files_skips_generated_folders(tools: RepoTools) -> None:
    listing = call(tools, "list_files").splitlines()
    assert "src/app/page.tsx" in listing
    assert "README.md" in listing
    assert not any(line.startswith("node_modules") for line in listing)


def test_search_finds_text_with_line_numbers(tools: RepoTools) -> None:
    assert call(tools, "search", text="<h1>") == "src/app/page.tsx:2: return <h1>Hi</h1>;"
    assert call(tools, "search", text="nowhere") == "no matches"


def test_read_file_shows_line_numbers_and_ranges(tools: RepoTools) -> None:
    out = call(tools, "read_file", path="src/app/page.tsx", start_line=2, end_line=2)
    assert out == "    2    return <h1>Hi</h1>;\n(lines 2-2 of 3)"


def test_edit_file_replaces_unique_text_and_tracks_changes(tools: RepoTools, repo: Path) -> None:
    out = call(tools, "edit_file", path="src/app/page.tsx", old_text="Hi", new_text="Hello")
    assert out == "Edited src/app/page.tsx."
    assert "<h1>Hello</h1>" in (repo / "src/app/page.tsx").read_text()
    assert tools.changed_files == {"src/app/page.tsx"}


def test_edit_file_refuses_ambiguous_or_missing_text(tools: RepoTools, repo: Path) -> None:
    (repo / "twice.txt").write_text("a\na\n")
    assert "appears 2 times" in call(
        tools, "edit_file", path="twice.txt", old_text="a", new_text="b"
    )
    assert "appears 0 times" in call(
        tools, "edit_file", path="twice.txt", old_text="z", new_text="b"
    )
    assert tools.changed_files == set()


def test_create_file_makes_folders_but_never_overwrites(tools: RepoTools, repo: Path) -> None:
    out = call(tools, "create_file", path="src/app/contact/page.tsx", content="x")
    assert out == "Created src/app/contact/page.tsx."
    assert (repo / "src/app/contact/page.tsx").read_text() == "x"
    assert "already exists" in call(tools, "create_file", path="README.md", content="y")


@pytest.mark.parametrize(
    "path", ["../outside.txt", "/etc/passwd", "src/../../x", ".git/config", ".env"]
)
def test_paths_outside_repo_git_and_secrets_are_refused(tools: RepoTools, path: str) -> None:
    out = call(tools, "read_file", path=path)
    assert out.startswith("ERROR:")


def test_symlink_pointing_outside_the_repo_is_refused(
    tools: RepoTools, repo: Path, tmp_path: Path
) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("private")
    (repo / "sneaky").symlink_to(secret)
    assert call(tools, "read_file", path="sneaky") == "ERROR: 'sneaky' is outside the repo"


def test_bad_calls_come_back_as_error_text(tools: RepoTools) -> None:
    assert tools.call("delete_everything", "{}").startswith("ERROR: unknown tool")
    assert tools.call("read_file", "not json").startswith("ERROR: bad arguments")
    assert tools.call("read_file", json.dumps({"path": "a", "extra": 1})).startswith(
        "ERROR: bad arguments"
    )


def test_clean_output_strips_colours_and_keeps_the_tail() -> None:
    text = "\x1b[32mok\x1b[0m\n" + "\n".join(f"line {i}" for i in range(200))
    lines = clean_output(text).splitlines()
    assert lines[0].startswith("... (")
    assert lines[-1] == "line 199"
    assert len(lines) == MAX_OUTPUT_LINES + 1
    assert clean_output("\x1b[31mred\x1b[0m") == "red"


def test_test_report_becomes_a_short_list() -> None:
    report = {
        "numPassedTests": 1,
        "numFailedTests": 1,
        "numTotalTests": 2,
        "testResults": [
            {
                "name": "/workspace/a.test.tsx",
                "status": "failed",
                "message": "",
                "assertionResults": [
                    {"fullName": "shows heading", "status": "passed", "failureMessages": []},
                    {
                        "fullName": "shows form",
                        "status": "failed",
                        "failureMessages": ["expected 1 to be 2"],
                    },
                ],
            },
            {
                "name": "/workspace/b.test.tsx",
                "status": "failed",
                "message": "SyntaxError",
                "assertionResults": [],
            },
        ],
    }
    assert summarise_test_report(report) == (
        "1 passed, 1 failed (of 2)\n"
        "PASS  shows heading\n"
        "FAILED  shows form\n"
        "      expected 1 to be 2\n"
        "FAILED TO LOAD  /workspace/b.test.tsx\n"
        "      SyntaxError"
    )


@docker
def test_real_sandbox_run_tests_and_typecheck_after_edit(tmp_path: Path) -> None:
    root = tmp_path / "app"
    shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns("node_modules", ".next"))
    tools = RepoTools(Workspace(root, token=None))
    assert call(tools, "run", command="pnpm install --offline --frozen-lockfile").startswith(
        "exit code 0"
    )

    assert call(tools, "run_tests").startswith("1 passed, 0 failed")

    broken = call(tools, "create_file", path="src/bad.ts", content="const n: number = 'text';\n")
    assert "Type-check FAILED" in broken
    assert "src/bad.ts" in broken
