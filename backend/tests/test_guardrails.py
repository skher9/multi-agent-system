"""The shared context and the guardrails added after the base-1 benchmark."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx2
import pytest

from agents.loop import CLEARED, _clear_old_tool_results
from agents.project_context import file_blocks, project_context
from agents.repo_tools import MAX_LIBRARY_READS, RepoTools
from agents.reviewer import changed_paths
from llm_router.budget import AgentBudgetExceededError
from llm_router.models import Role
from llm_router.router import LlmRouter
from services.openrouter import OpenRouterClient
from services.workspace import Workspace
from tests.test_agent_loop import Script, call, reply


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "page.tsx").write_text("export default function Page() {}\n")
    (root / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run"}, "dependencies": {"next": "16.4.1"}})
    )
    (root / "AGENTS.md").write_text("Read the Next.js docs first.\n")
    (root / "node_modules" / "next").mkdir(parents=True)
    (root / "node_modules" / "next" / "index.js").write_text("x\n")
    return root


def tools(root: Path, **kwargs: Any) -> RepoTools:
    t = RepoTools(Workspace(root, token=None), typecheck_after_edit=False, **kwargs)
    t._installed = True  # the fixture's node_modules is on disk already
    return t


def test_project_context_has_stack_and_repo_instructions(repo: Path) -> None:
    text = project_context(repo, ["src/page.tsx", "package.json"])
    assert "test: vitest run" in text and "next@16.4.1" in text
    assert "Read the Next.js docs first." in text  # AGENTS.md, verbatim
    assert "src/page.tsx" in text  # the file tree


def test_context_files_are_answered_from_the_context(repo: Path) -> None:
    t = tools(repo, context_given=True)
    assert "is in <project_context>" in t.call("read_file", '{"path": "AGENTS.md"}')
    t.changed_files.add("AGENTS.md")  # once the agent changes it, the real file
    assert "Read the Next.js docs" in t.call("read_file", '{"path": "AGENTS.md"}')
    # Agents without the context (QA) read it normally
    assert "Read the Next.js docs" in tools(repo).call("read_file", '{"path": "AGENTS.md"}')


def test_repeat_read_of_unchanged_file_is_refused(repo: Path) -> None:
    t = tools(repo)
    assert "Page" in t.call("read_file", '{"path": "src/page.tsx"}')
    assert "unchanged since you read it at tool call 1" in t.call(
        "read_file", '{"path": "src/page.tsx"}'
    )
    (repo / "src" / "page.tsx").write_text("changed\n")
    assert "changed" in t.call("read_file", '{"path": "src/page.tsx"}')


def test_shell_reads_and_developer_e2e_are_redirected(repo: Path) -> None:
    t = tools(repo, browser_tests=False)
    assert "use read_file" in t.call("run", '{"command": "cd /workspace && cat src/page.tsx"}')
    assert "use read_file" in t.call("run", '{"command": "ls -la src"}')
    assert "QA's job" in t.call("run", '{"command": "pnpm test:e2e"}')


def test_library_reads_are_capped(repo: Path) -> None:
    t = tools(repo)
    for _ in range(MAX_LIBRARY_READS):
        t.call("list_files", '{"path": "node_modules/next"}')
    assert "library budget used" in t.call("list_files", '{"path": "node_modules/next"}')


def test_handoff_blocks_and_changed_paths(repo: Path) -> None:
    assert '<file path="src/page.tsx">' in file_blocks(repo, ["src/page.tsx", "../outside"])
    diff = "--- a/x.ts\n+++ b/x.ts\n@@\n--- a/gone.ts\n+++ /dev/null\n"
    assert changed_paths(diff) == ["x.ts"]


def test_old_tool_results_are_cleared_in_one_batch() -> None:
    messages: list[dict[str, Any]] = [{"role": "user", "content": "task"}]
    messages += [{"role": "tool", "content": "x" * 10_000} for _ in range(10)]
    _clear_old_tool_results(messages)
    contents = [m["content"] for m in messages if m["role"] == "tool"]
    assert contents[:4] == [CLEARED] * 4 and all(c.startswith("x") for c in contents[4:])
    small = [{"role": "tool", "content": "x" * 100} for _ in range(10)]
    _clear_old_tool_results(small)
    assert all(m["content"] != CLEARED for m in small)  # under the threshold: untouched


def test_the_same_call_three_times_in_a_row_is_refused() -> None:
    same = call("read_file", {"path": "a.ts"})
    script = Script(reply(same), reply(same), reply(same), reply(call("finish", {"summary": "x"})))
    script.run()
    assert script.tool_calls.count(("read_file", json.dumps({"path": "a.ts"}))) == 2


def test_an_agent_turn_stops_at_its_role_cap() -> None:
    client = OpenRouterClient("k", transport=httpx2.MockTransport(lambda _: httpx2.Response(500)))
    router = LlmRouter(
        client,
        lambda _record: None,
        Decimal("96.5"),
        story_spend=lambda _id: Decimal("0"),
        story_budget_inr=Decimal("50"),
        agent_spend=lambda _id: Decimal("15"),
    )
    with pytest.raises(AgentBudgetExceededError, match="developer budget used"):
        router.complete(role=Role.DEVELOPER, messages=[], agent_run_id=1)
