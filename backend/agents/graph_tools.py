"""Tools that ask a repo's code graph questions: what's related, what depends on what.

The planner uses these with the read-only repo tools: the graph says where to look,
read_file shows the code. Same calling style as RepoTools: call() takes a tool name
and JSON arguments and returns text, with problems as "ERROR: ..." text.

Graphify only exists in the sandbox image, so each call runs there with the graph
folder mounted read-only and no network. The model's text goes in as a plain
argument (no shell), and text starting with "-" is refused so it can't pass options.
"""

import json
from collections.abc import Callable
from typing import Any

from pydantic import Field, ValidationError, field_validator

from agents.code_graph import CodeGraphFiles, RunSandbox
from agents.repo_tools import ToolArgs, clean_output, definitions
from services import sandbox
from services.sandbox import CONTAINER_WORKDIR, SandboxLimits

GRAPH_IN_CONTAINER = f"{CONTAINER_WORKDIR}/graph.json"
QUERY_TOKEN_BUDGET = 1500  # caps one answer at ~₹0.01 of model input
GRAPH_TOOL_LIMITS = SandboxLimits(timeout_seconds=60)
# graphify's exit codes for query, explain and affected
AMBIGUOUS, NO_MATCH = 3, 4


class GraphArgs(ToolArgs):
    @field_validator("*")
    @classmethod
    def _no_options(cls, value: str) -> str:
        if value.lstrip().startswith("-"):
            raise ValueError("must not start with '-'")
        return value


class GraphQuery(GraphArgs):
    """Search the code graph: which files, functions and components relate to a topic."""

    question: str = Field(min_length=1, max_length=300, description="e.g. 'navigation header'")


class GraphExplain(GraphArgs):
    """Show one file, function or component and everything it connects to."""

    name: str = Field(min_length=1, max_length=200, description="e.g. 'Home()' or a file path")


class GraphAffected(GraphArgs):
    """List what would be affected by changing a file, function or component."""

    name: str = Field(min_length=1, max_length=200, description="e.g. 'Header()'")


GRAPH_TOOL_ARGS: dict[str, type[GraphArgs]] = {
    "graph_query": GraphQuery,
    "graph_explain": GraphExplain,
    "graph_affected": GraphAffected,
}


def graph_tool_definitions() -> list[dict[str, Any]]:
    return definitions(GRAPH_TOOL_ARGS)


class GraphTools:
    def __init__(self, graph: CodeGraphFiles, run_sandbox: RunSandbox = sandbox.run) -> None:
        self._graph = graph
        self._run_sandbox = run_sandbox
        self._commands: dict[str, Callable[[Any], list[str]]] = {
            "graph_query": lambda a: ["query", a.question, "--budget", str(QUERY_TOKEN_BUDGET)],
            "graph_explain": lambda a: ["explain", a.name],
            "graph_affected": lambda a: ["affected", a.name],
        }

    def call(self, name: str, arguments: str) -> str:
        """Run one tool call from the model. Always returns text, never raises."""
        args_model = GRAPH_TOOL_ARGS.get(name)
        if args_model is None:
            return f"ERROR: unknown tool {name!r}. Tools: {', '.join(GRAPH_TOOL_ARGS)}"
        try:
            args = args_model.model_validate(json.loads(arguments or "{}"))
        except (json.JSONDecodeError, ValidationError) as exc:
            return f"ERROR: bad arguments for {name}: {exc}"
        return self._graphify(self._commands[name](args))

    def _graphify(self, args: list[str]) -> str:
        result = self._run_sandbox(
            ["graphify", *args, "--graph", GRAPH_IN_CONTAINER],
            workspace=self._graph.folder,
            limits=GRAPH_TOOL_LIMITS,
            read_only=True,
            network="none",
        )
        output = clean_output(result.stdout + result.stderr)
        if result.timed_out:
            return "ERROR: the graph search timed out; try a narrower question"
        if result.exit_code == AMBIGUOUS:
            return f"Several matches; call again with one of these exact names:\n{output}"
        if result.exit_code == NO_MATCH:
            return "No match in the graph. Try other words, or use search / list_files."
        if result.exit_code != 0:
            return f"ERROR: graphify failed (exit {result.exit_code}):\n{output}"
        return output
