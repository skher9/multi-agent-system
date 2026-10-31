"""The pipeline graph with a fake Jira and a fake model (no network, no database)."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any

import httpx2
import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from agents.developer import DevResult
from agents.planner import Plan
from agents.reviewer import Review
from agents.ticket_reader import TicketSpec
from llm_router.router import LlmRouter
from orchestrator.graph import RunContext, build_graph
from services.jira import JiraClient
from services.openrouter import OpenRouterClient
from tests.test_planner import GOOD_PLAN
from tests.test_ticket_reader import BLOCKED, READY, model_reply

APPROVE = {
    "verdict": "approve",
    "summary": "Meets every criterion.",
    "issues": [],
    "criteria_check": [{"number": 1, "met": True, "test": "page.test.tsx: renders the form"}],
}
CHANGES = {
    "verdict": "changes_requested",
    "summary": "One criterion isn't met.",
    "issues": [{"path": "src/app/contact/page.tsx", "problem": "No thanks", "fix": "Add it"}],
    "criteria_check": [{"number": 1, "met": False, "test": ""}],
}

CONFLICT_PLAN = {
    **GOOD_PLAN,
    "changes": [],
    "subtasks": [],
    "conflicts": [{"description": "No backend to send email", "question": "Which service?"}],
}

ISSUE = {
    "key": "KAN-4",
    "fields": {
        "summary": "Add a contact page",
        "description": None,
        "issuetype": {"name": "Story"},
        "status": {"name": "To Do"},
        "labels": [],
    },
}


class Fakes:
    """A fake Jira and model; records what the graph did to them."""

    def __init__(
        self,
        reader_reply: dict[str, Any],
        fail_posts: int = 0,
        plan: dict[str, Any] = GOOD_PLAN,
        existing_subtasks: tuple[str, ...] = (),
        reviews: tuple[dict[str, Any], ...] = (APPROVE,),
        dev_problem: str = "",
        fix_problem: str = "",
    ) -> None:
        """fail_posts: how many comment posts fail (HTTP 500) before they work, to
        simulate a run crashing partway. existing_subtasks: summaries already in Jira."""
        self.comments: list[dict[str, Any]] = []
        self.subtasks: list[dict[str, Any]] = []
        self.agent_runs: list[str] = []
        self.model_calls = 0
        self.plans = 0
        self._fail_posts = fail_posts
        self._plan = plan
        self._reviews = list(reviews)
        self.fixed: list[str] = []  # branches the developer fixed
        self.review_inputs: list[tuple[str, Review | None]] = []  # (summary, previous)
        self._dev_problem = dev_problem
        self._fix_problem = fix_problem
        self.pr_comments: list[str] = []

        def jira(request: httpx2.Request) -> httpx2.Response:
            if request.url.path == "/rest/api/3/search/jql":
                issues = [
                    {"key": f"KAN-{50 + i}", "fields": {"summary": summary}}
                    for i, summary in enumerate(existing_subtasks)
                ]
                return httpx2.Response(200, json={"issues": issues})
            if request.url.path == "/rest/api/3/issue":
                self.subtasks.append(json.loads(request.content)["fields"])
                return httpx2.Response(201, json={"key": f"KAN-{10 + len(self.subtasks)}"})
            if request.method == "POST":
                if self._fail_posts > 0:
                    self._fail_posts -= 1
                    return httpx2.Response(500)
                self.comments.append(json.loads(request.content))
                return httpx2.Response(201, json={"id": "10001"})
            return httpx2.Response(200, json=ISSUE)

        def model(_: httpx2.Request) -> httpx2.Response:
            self.model_calls += 1
            return model_reply(json.dumps(reader_reply))

        router = LlmRouter(
            OpenRouterClient("k", transport=httpx2.MockTransport(model)),
            lambda _call: None,
            Decimal("96.5"),
            story_spend=lambda _run_id: Decimal("0"),
            story_budget_inr=Decimal("50"),
        )
        self.context = RunContext(
            jira=JiraClient("https://x.atlassian.net", "e", "t", httpx2.MockTransport(jira)),
            router=router,
            agent_run=self._agent_run,
            make_plan=self._make_plan,
            make_code=self._make_code,
            open_pr=self._open_pr,
            make_review=self._make_review,
            make_fix=self._make_fix,
            comment_pr=lambda number, body: self.pr_comments.append(body),
        )

    def _make_plan(self, spec: TicketSpec, agent_run_id: int) -> tuple[Plan, str]:
        self.plans += 1
        return Plan.model_validate(self._plan), "abc123"

    def _make_code(
        self, key: str, spec: TicketSpec, plan: Plan, sha: str, agent_run_id: int
    ) -> tuple[DevResult, str, str]:
        self.built = (key, sha, [c.path for c in plan.changes])
        dev = DevResult(
            summary="Added the contact page",
            changed_files=["src/app/page.tsx"],
            problem=self._dev_problem,
        )
        return dev, f"agent/{key}", "" if self._dev_problem else "def456"

    def _open_pr(self, branch: str, title: str, body: str) -> tuple[int, str]:
        self.pr = (branch, title, body)
        return 7, "https://github.com/skher9/agent-playground/pull/7"

    def _make_review(
        self,
        spec: TicketSpec,
        plan: Plan,
        branch: str,
        base: str,
        summary: str,
        previous: Review | None,
        agent_run_id: int,
    ) -> Review:
        assert (branch, base) == ("agent/KAN-4", "abc123")
        self.review_inputs.append((summary, previous))
        return Review.model_validate(self._reviews.pop(0))

    def _make_fix(
        self, key: str, spec: TicketSpec, plan: Plan, review: Review, branch: str, run_id: int
    ) -> tuple[DevResult, str]:
        assert review.issues[0].problem == "No thanks"
        self.fixed.append(branch)
        dev = DevResult(summary="Added thanks", changed_files=[], problem=self._fix_problem)
        return dev, f"fix{len(self.fixed)}"

    @contextmanager
    def _agent_run(self, role: str) -> Iterator[int]:
        self.agent_runs.append(role)
        yield len(self.agent_runs)


def nodes_visited(fakes: Fakes) -> list[str]:
    graph = build_graph()
    updates = graph.stream({"ticket_key": "KAN-4"}, context=fakes.context, stream_mode="updates")
    return [node for update in updates for node in update]


def test_ready_ticket_is_planned_split_into_subtasks_then_developed() -> None:
    fakes = Fakes(READY)
    assert nodes_visited(fakes) == [
        "fetch_ticket", "read_ticket", "plan", "create_subtasks", "develop", "open_pr",
        "review", "post_review",
    ]  # fmt: skip
    assert fakes.agent_runs == ["ticket_reader", "planner", "developer", "reviewer"]
    # The developer built the plan on the commit the planner looked at
    assert fakes.built == (
        "KAN-4",
        "abc123",
        ["src/app/contact/page.tsx", "src/app/contact/page.test.tsx", "src/app/page.tsx"],
    )
    [subtask] = fakes.subtasks
    assert subtask["summary"] == "[FE] Contact page"
    assert subtask["parent"] == {"key": "KAN-4"}
    assert subtask["issuetype"] == {"name": "Subtask"}
    assert subtask["labels"] == ["mas-agent"]
    assert "src/app/contact/page.tsx" in json.dumps(subtask["description"])


def test_final_state_holds_plan_commit_and_subtasks() -> None:
    final = build_graph().invoke({"ticket_key": "KAN-4"}, context=Fakes(READY).context)
    assert final["plan"]["changes"][0]["path"] == "src/app/contact/page.tsx"
    assert final["commit_sha"] == "abc123"
    assert final["subtask_keys"] == ["KAN-11"]
    assert (final["branch"], final["head_sha"]) == ("agent/KAN-4", "def456")
    assert final["dev"]["summary"] == "Added the contact page"
    assert final["pr_url"] == "https://github.com/skher9/agent-playground/pull/7"
    assert final["outcome"] == "ready_to_merge"


def test_pr_describes_the_work_and_jira_links_to_it() -> None:
    fakes = Fakes(READY)
    build_graph().invoke({"ticket_key": "KAN-4"}, context=fakes.context)
    branch, title, body = fakes.pr
    assert (branch, title) == ("agent/KAN-4", "KAN-4: Add a contact page")
    assert "Ticket: https://x.atlassian.net/browse/KAN-4" in body
    assert "- [x] Visiting /contact shows a form" in body
    assert "- KAN-11: [FE] Contact page" in body
    assert "Added the contact page" in body
    [comment] = fakes.comments
    assert "https://github.com/skher9/agent-playground/pull/7" in json.dumps(comment)


def test_conflicts_go_back_to_jira_and_stop() -> None:
    fakes = Fakes(READY, plan=CONFLICT_PLAN)
    assert nodes_visited(fakes) == ["fetch_ticket", "read_ticket", "plan", "post_conflicts"]
    [comment] = fakes.comments
    assert "No backend to send email — Which service?" in json.dumps(comment, ensure_ascii=False)
    assert fakes.subtasks == []


def test_existing_subtasks_are_reused_not_duplicated() -> None:
    fakes = Fakes(READY, existing_subtasks=("[FE] Contact page",))
    final = build_graph().invoke({"ticket_key": "KAN-4"}, context=fakes.context)
    assert final["subtask_keys"] == ["KAN-50"]
    assert fakes.subtasks == []


def test_blocked_ticket_gets_questions_posted_and_stops() -> None:
    fakes = Fakes(BLOCKED)
    assert nodes_visited(fakes) == ["fetch_ticket", "read_ticket", "post_questions"]
    [comment] = fakes.comments
    assert "Which pages are in scope?" in json.dumps(comment)


def test_final_state_holds_spec_and_outcome() -> None:
    final = build_graph().invoke({"ticket_key": "KAN-4"}, context=Fakes(BLOCKED).context)
    assert final["ticket"]["summary"] == "Add a contact page"
    assert final["spec"]["status"] == "blocked"
    assert final["outcome"] == "blocked"
    assert final["comment_id"] == "10001"


def test_checkpointer_saves_state_after_every_node() -> None:
    graph = build_graph(checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "run-1"}}
    graph.invoke({"ticket_key": "KAN-4"}, config, context=Fakes(READY).context)

    saved = graph.get_state(config)
    assert saved.values["outcome"] == "ready_to_merge"
    assert saved.next == ()  # nothing left to run
    # One checkpoint per step, so a crashed run could resume from any of them
    assert len(list(graph.get_state_history(config))) >= 4


def test_a_crashed_run_resumes_without_redoing_finished_nodes() -> None:
    fakes = Fakes(BLOCKED, fail_posts=1)
    graph = build_graph(checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "run-2"}}

    with pytest.raises(httpx2.HTTPStatusError):
        graph.invoke({"ticket_key": "KAN-4"}, config, context=fakes.context)
    assert graph.get_state(config).next == ("post_questions",)  # where it stopped

    final = graph.invoke(None, config, context=fakes.context)  # None = continue

    assert final["outcome"] == "blocked"
    assert fakes.model_calls == 1  # the reader was not paid for twice
    assert len(fakes.comments) == 1


def test_approved_review_is_posted_on_the_pr() -> None:
    fakes = Fakes(READY)
    build_graph().invoke({"ticket_key": "KAN-4"}, context=fakes.context)
    [comment] = fakes.pr_comments
    assert comment.startswith("### 🤖 Review 1: ✅ Approved")


def test_changes_are_fixed_then_reviewed_again() -> None:
    fakes = Fakes(READY, reviews=(CHANGES, APPROVE))
    final = build_graph().invoke({"ticket_key": "KAN-4"}, context=fakes.context)
    assert final["outcome"] == "ready_to_merge"
    assert (final["reviews"], final["fixes"], final["head_sha"]) == (2, 1, "fix1")
    assert fakes.fixed == ["agent/KAN-4"]
    assert fakes.pr_comments[0].startswith("### 🤖 Review 2: ✅ Approved")


def test_a_human_takes_over_after_two_fix_rounds() -> None:
    fakes = Fakes(READY, reviews=(CHANGES, CHANGES, CHANGES))
    graph = build_graph()
    updates = graph.stream({"ticket_key": "KAN-4"}, context=fakes.context, stream_mode="updates")
    visited = [node for update in updates for node in update]
    assert visited[-6:] == ["review", "fix", "review", "fix", "review", "post_review"]
    [comment] = fakes.pr_comments
    assert "Review 3: 🔧 Changes needed" in comment
    assert "**`src/app/contact/page.tsx`**: No thanks" in comment


def test_reviewer_gets_only_summaries_and_the_previous_review() -> None:
    fakes = Fakes(READY, reviews=(CHANGES, APPROVE))
    build_graph().invoke({"ticket_key": "KAN-4"}, context=fakes.context)
    (first_summary, first_previous), (second_summary, second_previous) = fakes.review_inputs
    assert (first_summary, first_previous) == ("Added the contact page", None)
    assert second_summary == "Added the contact page\n\nLatest fixes:\nAdded thanks"
    assert second_previous is not None and second_previous.issues[0].problem == "No thanks"


def test_developer_problem_stops_the_run_for_a_human() -> None:
    fakes = Fakes(READY, dev_problem="The plan's /api/contact route doesn't exist")
    updates = build_graph().stream(
        {"ticket_key": "KAN-4"}, context=fakes.context, stream_mode="updates"
    )
    visited = [node for update in updates for node in update]
    assert visited[-2:] == ["develop", "post_problem"]
    [comment] = fakes.comments
    assert "/api/contact route doesn't exist" in json.dumps(comment)


def test_a_problem_during_a_fix_also_stops_for_a_human() -> None:
    fakes = Fakes(READY, reviews=(CHANGES,), fix_problem="The review asks for a backend")
    final = build_graph().invoke({"ticket_key": "KAN-4"}, context=fakes.context)
    assert final["outcome"] == "needs_human"
    assert "asks for a backend" in json.dumps(fakes.comments[-1])
