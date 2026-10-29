"""The pipeline graph with a fake Jira and a fake model (no network, no database)."""

import json
from decimal import Decimal
from typing import Any

import httpx2
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from llm_router.router import LlmRouter
from orchestrator.graph import RunContext, build_graph
from services.jira import JiraClient
from services.openrouter import OpenRouterClient
from tests.test_ticket_reader import BLOCKED, READY, model_reply

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

    def __init__(self, reader_reply: dict[str, Any]) -> None:
        self.comments: list[dict[str, Any]] = []
        self.agent_runs: list[str] = []

        def jira(request: httpx2.Request) -> httpx2.Response:
            if request.method == "POST":
                self.comments.append(json.loads(request.content))
                return httpx2.Response(201, json={"id": "10001"})
            return httpx2.Response(200, json=ISSUE)

        def model(_: httpx2.Request) -> httpx2.Response:
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
            start_agent_run=self._start_agent_run,
        )

    def _start_agent_run(self, role: str) -> int:
        self.agent_runs.append(role)
        return len(self.agent_runs)


def nodes_visited(fakes: Fakes) -> list[str]:
    graph = build_graph()
    updates = graph.stream({"ticket_key": "KAN-4"}, context=fakes.context, stream_mode="updates")
    return [node for update in updates for node in update]


def test_ready_ticket_goes_to_the_developer() -> None:
    fakes = Fakes(READY)
    assert nodes_visited(fakes) == ["fetch_ticket", "read_ticket", "develop"]
    assert fakes.comments == []
    assert fakes.agent_runs == ["ticket_reader"]


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
    assert saved.values["outcome"] == "waiting_for_developer"
    assert saved.next == ()  # nothing left to run
    # One checkpoint per step, so a crashed run could resume from any of them
    assert len(list(graph.get_state_history(config))) >= 4
