"""run_ticket(): one full pipeline run for a ticket, with its database records."""

from dataclasses import dataclass
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.orm import Session, sessionmaker

from agents.code_graph import Storage, open_code_graph
from agents.planner import Plan, plan_ticket
from agents.ticket_reader import TicketSpec
from llm_router.router import LlmRouter
from orchestrator.graph import RunContext, RunInput, RunState, build_graph
from orchestrator.records import agent_run, claim_feature, ensure_feature, update_feature
from services.jira import JiraClient
from services.workspace import Workspace


class AlreadyRunningError(Exception):
    """Another run of this ticket is in progress; this one did nothing."""


@dataclass(frozen=True)
class Pipeline:
    """Everything a run needs, built once (e.g. by the API or a worker)."""

    factory: sessionmaker[Session]
    jira: JiraClient
    router: LlmRouter
    project_id: int
    # Saves the state after every node so a crashed run can resume. None: no resuming.
    checkpointer: BaseCheckpointSaver[Any] | None = None
    # Needed from the planner on: where code graphs are kept, and the repo agents work on
    storage: Storage | None = None
    repo_url: str = ""
    github_token: str | None = None


def make_plan(pipeline: Pipeline, spec: TicketSpec, agent_run_id: int) -> tuple[Plan, str]:
    """Clone the repo, load (or build) its code graph, and run the planner on it."""
    if pipeline.storage is None or not pipeline.repo_url:
        raise RuntimeError("planning needs the pipeline's storage and repo_url")
    with (
        Workspace.clone(pipeline.repo_url, pipeline.github_token) as workspace,
        open_code_graph(
            pipeline.factory, pipeline.storage, pipeline.project_id, workspace
        ) as graph,
    ):
        plan = plan_ticket(pipeline.router, spec, workspace, graph, agent_run_id=agent_run_id)
        return plan, graph.commit_sha


def run_ticket(pipeline: Pipeline, ticket_key: str) -> RunState:
    """Run the graph for one ticket and save where it ended on the ticket's feature.

    If the ticket's last run stopped partway (a crash), this continues from the node
    that didn't finish. Otherwise it starts from the beginning.
    Raises AlreadyRunningError if another run of the ticket hasn't finished.
    """
    feature_id = ensure_feature(pipeline.factory, pipeline.project_id, ticket_key)
    if not claim_feature(pipeline.factory, feature_id):
        raise AlreadyRunningError(ticket_key)
    context = RunContext(
        jira=pipeline.jira,
        router=pipeline.router,
        agent_run=lambda role: agent_run(pipeline.factory, feature_id, role),
        make_plan=lambda spec, run_id: make_plan(pipeline, spec, run_id),
    )
    graph = build_graph(pipeline.checkpointer)
    # One thread per feature: every run of this ticket shares its saved state.
    config: RunnableConfig = {"configurable": {"thread_id": f"feature-{feature_id}"}}

    # state.next lists the nodes still waiting to run; non-empty means it stopped partway.
    unfinished = pipeline.checkpointer is not None and bool(graph.get_state(config).next)
    # Input None tells LangGraph "continue from the checkpoint" instead of starting over.
    graph_input: RunInput | None = None if unfinished else {"ticket_key": ticket_key}
    try:
        # invoke() is typed as returning a plain dict; it is the graph's RunState.
        final = cast(RunState, graph.invoke(graph_input, config, context=context))
    except BaseException:
        update_feature(pipeline.factory, feature_id, status="failed")
        raise
    update_feature(
        pipeline.factory,
        feature_id,
        status=final["outcome"],
        title=f"{ticket_key}: {final['ticket']['summary']}",
    )
    return final
