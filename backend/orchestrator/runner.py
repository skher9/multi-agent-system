"""run_ticket(): one full pipeline run for a ticket, with its database records."""

from dataclasses import dataclass
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.orm import Session, sessionmaker

from llm_router.router import LlmRouter
from orchestrator.graph import RunContext, RunInput, RunState, build_graph
from orchestrator.records import agent_run, claim_feature, ensure_feature, update_feature
from services.jira import JiraClient


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
