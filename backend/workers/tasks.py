from typing import Any

from api.config import get_settings
from orchestrator.decisions import PlanDecision
from orchestrator.runner import AlreadyRunningError, NotWaitingError, run_ticket
from orchestrator.wiring import open_pipeline
from workers.celery_app import celery_app


@celery_app.task(name="ping")
def ping() -> str:
    """Setup test task: proves a worker picked the job off the queue and ran it."""
    return "pong"


@celery_app.task(name="run_ticket")
def run_ticket_task(ticket_key: str, approve_plan: bool = False) -> str:
    """One pipeline run for a Jira ticket. Returns where it ended, e.g. "blocked"."""
    with open_pipeline(get_settings()) as pipeline:
        try:
            return run_ticket(pipeline, ticket_key, approve_plan=approve_plan)["outcome"]
        except AlreadyRunningError:
            return "already_running"  # not a failure: the other run carries on


@celery_app.task(name="decide_plan")
def decide_plan_task(ticket_key: str, decision: dict[str, Any]) -> str:
    """Resume a run paused for plan approval with a human's decision."""
    with open_pipeline(get_settings()) as pipeline:
        try:
            answer = PlanDecision.model_validate(decision)
            return run_ticket(pipeline, ticket_key, plan_decision=answer)["outcome"]
        except AlreadyRunningError:
            return "already_running"
        except NotWaitingError:
            return "not_waiting"
