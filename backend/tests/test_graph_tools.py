"""Graph tools: argument checks and graphify's answers (fake sandbox; real one under `docker`)."""

import json
from pathlib import Path
from typing import Any

import pytest

from agents.code_graph import CONTAINER_GRAPH_DIR, CodeGraphFiles
from agents.graph_tools import GraphTools, graph_tool_definitions
from services import sandbox
from services.sandbox import SandboxResult
from tests.test_sandbox import docker


class FakeSandbox:
    def __init__(self, exit_code: int = 0, stdout: str = "NODE Home()") -> None:
        self.result = SandboxResult(exit_code, stdout, "", timed_out=False)
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, command: list[str], **kwargs: Any) -> SandboxResult:
        self.calls.append((command, kwargs))
        return self.result


def tools(fake: FakeSandbox, tmp_path: Path) -> GraphTools:
    return GraphTools(CodeGraphFiles(tmp_path, "abc"), run_sandbox=fake)


def test_query_runs_graphify_read_only_and_offline(tmp_path: Path) -> None:
    fake = FakeSandbox()
    answer = tools(fake, tmp_path).call("graph_query", json.dumps({"question": "home page"}))
    assert answer == "NODE Home()"
    command, kwargs = fake.calls[0]
    assert command == [
        "graphify", "query", "home page", "--budget", "1500",
        "--graph", "/workspace/graph.json",
    ]  # fmt: skip
    assert kwargs["workspace"] == tmp_path
    assert (kwargs["read_only"], kwargs["network"]) == (True, "none")


@pytest.mark.parametrize(
    ("name", "args", "expected"),
    [
        ("graph_explain", {"name": "Home()"}, ["explain", "Home()"]),
        ("graph_affected", {"name": "Header()"}, ["affected", "Header()"]),
    ],
)
def test_explain_and_affected_commands(
    tmp_path: Path, name: str, args: dict[str, str], expected: list[str]
) -> None:
    fake = FakeSandbox()
    tools(fake, tmp_path).call(name, json.dumps(args))
    assert fake.calls[0][0][1:3] == expected


@pytest.mark.parametrize(
    "arguments",
    [
        {"question": "--graph /etc/passwd"},  # tries to pass an option
        {"question": "  -x"},
        {"question": ""},
        {"question": "x" * 301},
        {"question": "ok", "extra": 1},
    ],
)
def test_bad_arguments_never_reach_graphify(tmp_path: Path, arguments: dict[str, Any]) -> None:
    fake = FakeSandbox()
    answer = tools(fake, tmp_path).call("graph_query", json.dumps(arguments))
    assert answer.startswith("ERROR: bad arguments")
    assert fake.calls == []


def test_unknown_tool(tmp_path: Path) -> None:
    assert tools(FakeSandbox(), tmp_path).call("rm", "{}").startswith("ERROR: unknown tool")


@pytest.mark.parametrize(
    ("exit_code", "starts_with"),
    [
        (3, "Several matches"),
        (4, "No match in the graph"),
        (1, "ERROR: graphify failed"),
    ],
)
def test_graphify_exit_codes_become_guidance(
    tmp_path: Path, exit_code: int, starts_with: str
) -> None:
    fake = FakeSandbox(exit_code=exit_code)
    answer = tools(fake, tmp_path).call("graph_explain", json.dumps({"name": "next"}))
    assert answer.startswith(starts_with)


def test_definitions_name_all_three_tools() -> None:
    names = [d["function"]["name"] for d in graph_tool_definitions()]
    assert names == ["graph_query", "graph_explain", "graph_affected"]


@pytest.fixture
def real_graph(tmp_path: Path) -> CodeGraphFiles:
    """A real graph of a two-file TypeScript repo, built by Graphify in the sandbox."""
    repo, out = tmp_path / "repo", tmp_path / "out"
    repo.mkdir()
    out.mkdir()
    (repo / "util.ts").write_text("export function add(a: number, b: number) { return a + b }\n")
    (repo / "page.tsx").write_text("import { add } from './util'\nexport const x = add(1, 2)\n")
    result = sandbox.run(
        ["graphify", "extract", "/workspace", "--code-only", "--out", CONTAINER_GRAPH_DIR],
        workspace=repo,
        read_only=True,
        network="none",
        extra_mounts=((out, CONTAINER_GRAPH_DIR),),
    )
    assert result.exit_code == 0, result.stderr
    return CodeGraphFiles(out / "graphify-out", "abc")


@docker
def test_real_explain_and_affected(real_graph: CodeGraphFiles) -> None:
    graph_tools = GraphTools(real_graph)
    assert "util.ts" in graph_tools.call("graph_explain", json.dumps({"name": "add()"}))
    assert "page.tsx" in graph_tools.call("graph_affected", json.dumps({"name": "util.ts"}))


@docker
def test_real_no_match(real_graph: CodeGraphFiles) -> None:
    answer = GraphTools(real_graph).call("graph_explain", json.dumps({"name": "Nope()"}))
    assert answer.startswith("No match")
