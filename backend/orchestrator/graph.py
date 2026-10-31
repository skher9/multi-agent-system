"""The pipeline for one ticket, as a LangGraph graph.

    fetch_ticket -> read_ticket -> blocked? -> post_questions -> end
                                      |
                                    ready -> plan -> conflicts? -> post_conflicts -> end
                                                        |
                                                       none -> create_subtasks -> develop -> end

Each box is a node: a function that gets the run's state and returns only the keys it
changes. Routing is plain code (route_after_reader). Agents decide; nodes that act on the
outside world (like posting to Jira) are separate, so actions stay visible in the graph.

After develop the code is on a pushed branch; the PR and reviewer nodes come next.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from agents.developer import DevResult
from agents.planner import Plan, conflicts_comment, subtask_description
from agents.ticket_reader import TicketSpec, questions_comment, read_ticket
from llm_router.router import LlmRouter
from services.jira import JiraClient, JiraTicket

# A node returns only the keys it changes; LangGraph merges them into RunState.
Update = dict[str, Any]
# Marks the subtasks we create, so a resumed run finds them instead of making duplicates.
SUBTASK_LABEL = "mas-agent"


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
    comment_id: str  # the Jira comment holding the reader's or planner's questions
    plan: dict[str, Any]  # a Plan as a dict
    commit_sha: str  # the commit the plan was made on; the developer builds on it
    subtask_keys: list[str]  # Jira subtasks created from the plan, e.g. ["KAN-12"]
    branch: str  # where the developer's commit was pushed, e.g. "agent/KAN-4"
    head_sha: str  # the developer's commit
    dev: dict[str, Any]  # a DevResult as a dict: summary and changed files


@dataclass(frozen=True)
class RunContext:
    """Tools the nodes use. Not part of the state: clients can't (and shouldn't) be saved."""

    jira: JiraClient
    router: LlmRouter
    # `with agent_run("ticket_reader") as run_id:` records one agent's turn,
    # marking it done or failed when the block ends (see records.agent_run)
    agent_run: Callable[[str], AbstractContextManager[int]]
    # make_plan(spec, agent_run_id) -> (plan, commit sha): clones the repo, loads its
    # code graph and runs the planner (see runner.py). A function so tests can fake it.
    make_plan: Callable[[TicketSpec, int], tuple[Plan, str]]
    # make_code(ticket_key, spec, plan, commit_sha, agent_run_id) -> (dev result, branch,
    # head sha): clones, builds the plan on a new branch, commits and pushes (runner.py)
    make_code: Callable[[str, TicketSpec, Plan, str, int], tuple[DevResult, str, str]]


def fetch_ticket(state: RunState, runtime: Runtime[RunContext]) -> Update:
    ticket = runtime.context.jira.get_ticket(state["ticket_key"])
    return {"ticket": asdict(ticket)}


def read(state: RunState, runtime: Runtime[RunContext]) -> Update:
    ctx = runtime.context
    with ctx.agent_run("ticket_reader") as run_id:
        spec = read_ticket(ctx.router, JiraTicket(**state["ticket"]), agent_run_id=run_id)
    return {"spec": spec.model_dump()}


def route_after_reader(state: RunState) -> Literal["post_questions", "plan"]:
    return "post_questions" if state["spec"]["status"] == "blocked" else "plan"


def post_questions(state: RunState, runtime: Runtime[RunContext]) -> Update:
    spec = TicketSpec.model_validate(state["spec"])
    comment_id = runtime.context.jira.add_comment(state["ticket_key"], questions_comment(spec))
    return {"outcome": "blocked", "comment_id": comment_id}


def plan(state: RunState, runtime: Runtime[RunContext]) -> Update:
    ctx = runtime.context
    with ctx.agent_run("planner") as run_id:
        result, commit_sha = ctx.make_plan(TicketSpec.model_validate(state["spec"]), run_id)
    return {"plan": result.model_dump(), "commit_sha": commit_sha}


def route_after_plan(state: RunState) -> Literal["post_conflicts", "create_subtasks"]:
    return "post_conflicts" if state["plan"]["conflicts"] else "create_subtasks"


def post_conflicts(state: RunState, runtime: Runtime[RunContext]) -> Update:
    comment = conflicts_comment(Plan.model_validate(state["plan"]))
    comment_id = runtime.context.jira.add_comment(state["ticket_key"], comment)
    return {"outcome": "blocked", "comment_id": comment_id}


def create_subtasks(state: RunState, runtime: Runtime[RunContext]) -> Update:
    """One Jira subtask per planned subtask. Ones that already exist (an earlier run
    crashed partway through) are reused, matched by summary."""
    jira, parent = runtime.context.jira, state["ticket_key"]
    existing = jira.find_subtasks(parent, SUBTASK_LABEL)
    keys = []
    for subtask in Plan.model_validate(state["plan"]).subtasks:
        summary = f"[{subtask.area}] {subtask.title}"
        key = existing.get(summary) or jira.create_subtask(
            parent, summary, subtask_description(subtask), [SUBTASK_LABEL]
        )
        keys.append(key)
    return {"subtask_keys": keys}


def develop(state: RunState, runtime: Runtime[RunContext]) -> Update:
    ctx = runtime.context
    with ctx.agent_run("developer") as run_id:
        dev, branch, head_sha = ctx.make_code(
            state["ticket_key"],
            TicketSpec.model_validate(state["spec"]),
            Plan.model_validate(state["plan"]),
            state["commit_sha"],
            run_id,
        )
    # "pushed" until the PR node exists
    return {"dev": dev.model_dump(), "branch": branch, "head_sha": head_sha, "outcome": "pushed"}


def build_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[RunState, RunContext, RunInput, RunState]:
    builder = StateGraph(RunState, context_schema=RunContext, input_schema=RunInput)
    builder.add_node("fetch_ticket", fetch_ticket)
    builder.add_node("read_ticket", read)
    builder.add_node("post_questions", post_questions)
    builder.add_node("plan", plan)
    builder.add_node("post_conflicts", post_conflicts)
    builder.add_node("create_subtasks", create_subtasks)
    builder.add_node("develop", develop)

    builder.add_edge(START, "fetch_ticket")
    builder.add_edge("fetch_ticket", "read_ticket")
    builder.add_conditional_edges("read_ticket", route_after_reader)
    builder.add_edge("post_questions", END)
    builder.add_conditional_edges("plan", route_after_plan)
    builder.add_edge("post_conflicts", END)
    builder.add_edge("create_subtasks", "develop")
    builder.add_edge("develop", END)
    # The checkpointer saves the state after every node, so a run can resume (step 2).
    return builder.compile(checkpointer=checkpointer)
