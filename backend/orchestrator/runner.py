"""run_ticket(): one full pipeline run for a ticket, with its database records."""

from dataclasses import dataclass
from typing import cast

from sqlalchemy.orm import Session, sessionmaker

from llm_router.router import LlmRouter
from orchestrator.graph import RunContext, RunState, build_graph
from orchestrator.records import agent_run, ensure_feature, update_feature
from services.jira import JiraClient


@dataclass(frozen=True)
class Pipeline:
    """Everything a run needs, built once (e.g. by the API or a worker)."""

    factory: sessionmaker[Session]
    jira: JiraClient
    router: LlmRouter
    project_id: int


def run_ticket(pipeline: Pipeline, ticket_key: str) -> RunState:
    """Run the graph for one ticket and save where it ended on the ticket's feature."""
    feature_id = ensure_feature(pipeline.factory, pipeline.project_id, ticket_key)
    update_feature(pipeline.factory, feature_id, status="running")
    context = RunContext(
        jira=pipeline.jira,
        router=pipeline.router,
        agent_run=lambda role: agent_run(pipeline.factory, feature_id, role),
    )
    try:
        # invoke() is typed as returning a plain dict; it is the graph's RunState.
        final = cast(RunState, build_graph().invoke({"ticket_key": ticket_key}, context=context))
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
