"""The pipeline for one ticket, as a LangGraph graph.

    fetch_ticket -> read_ticket -> blocked? -> post_questions -> end
                                      |
                                    ready -> develop (placeholder) -> end

Each box is a node: a function that gets the run's state and returns only the keys it
changes. Routing is plain code (route_after_reader). Agents decide; nodes that act on the
outside world (like posting to Jira) are separate, so actions stay visible in the graph.

Skeleton: develop is a placeholder until the developer agent exists; reviewer and PR
nodes get added after it, one at a time.
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from agents.ticket_reader import TicketSpec, questions_comment, read_ticket
from llm_router.router import LlmRouter
from services.jira import JiraClient, JiraTicket

# A node returns only the keys it changes; LangGraph merges them into RunState.
Update = dict[str, Any]


class RunInput(TypedDict):
    """What a run starts with."""

    ticket_key: str


class RunState(RunInput):
    """Everything the run knows so far. Plain dicts and strings only, so a checkpoint
    can save it to the database and load it back after a crash.

    Each key is filled in by the node that runs before the nodes that read it.
    """

    ticket: dict[str, Any]  # a JiraTicket as a dict
    spec: dict[str, Any]  # a TicketSpec as a dict
    outcome: str  # where the run ended: "blocked", "waiting_for_developer", ...
    comment_id: str  # the Jira comment holding the reader's questions


@dataclass(frozen=True)
class RunContext:
    """Tools the nodes use. Not part of the state: clients can't (and shouldn't) be saved."""

    jira: JiraClient
    router: LlmRouter
    # Creates the agent_runs row for one agent's turn and returns its id
    start_agent_run: Callable[[str], int]


def fetch_ticket(state: RunState, runtime: Runtime[RunContext]) -> Update:
    ticket = runtime.context.jira.get_ticket(state["ticket_key"])
    return {"ticket": asdict(ticket)}


def read(state: RunState, runtime: Runtime[RunContext]) -> Update:
    ctx = runtime.context
    spec = read_ticket(
        ctx.router,
        JiraTicket(**state["ticket"]),
        agent_run_id=ctx.start_agent_run("ticket_reader"),
    )
    return {"spec": spec.model_dump()}


def route_after_reader(state: RunState) -> Literal["post_questions", "develop"]:
    return "post_questions" if state["spec"]["status"] == "blocked" else "develop"


def post_questions(state: RunState, runtime: Runtime[RunContext]) -> Update:
    spec = TicketSpec.model_validate(state["spec"])
    comment_id = runtime.context.jira.add_comment(state["ticket_key"], questions_comment(spec))
    return {"outcome": "blocked", "comment_id": comment_id}


def develop(state: RunState) -> Update:
    """Placeholder: the developer agent plugs in here next."""
    return {"outcome": "waiting_for_developer"}


def build_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[RunState, RunContext, RunInput, RunState]:
    builder = StateGraph(RunState, context_schema=RunContext, input_schema=RunInput)
    builder.add_node("fetch_ticket", fetch_ticket)
    builder.add_node("read_ticket", read)
    builder.add_node("post_questions", post_questions)
    builder.add_node("develop", develop)

    builder.add_edge(START, "fetch_ticket")
    builder.add_edge("fetch_ticket", "read_ticket")
    builder.add_conditional_edges("read_ticket", route_after_reader)
    builder.add_edge("post_questions", END)
    builder.add_edge("develop", END)
    # The checkpointer saves the state after every node, so a run can resume (step 2).
    return builder.compile(checkpointer=checkpointer)
