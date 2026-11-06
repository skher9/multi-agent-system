from typing import Any

from api.config import get_settings
from orchestrator.decisions import PlanDecision
from orchestrator.runner import (
    AlreadyRunningError,
    NotMergedError,
    NotWaitingError,
    learn_from_pr,
    run_ticket,
)
from orchestrator.wiring import open_pipeline
from workers.celery_app import celery_app


@celery_app.task(name="ping")
def ping() -> str:
    """Setup test task: proves a worker picked the job off the queue and ran it."""
    return "pong"


@celery_app.task(name="run_ticket")
def run_ticket_task(ticket_key: str, approve_plan: bool = False, figma_url: str = "") -> str:
    """One pipeline run for a Jira ticket. Returns where it ended, e.g. "blocked"."""
    with open_pipeline(get_settings()) as pipeline:
        try:
            return run_ticket(pipeline, ticket_key, approve_plan=approve_plan, figma_url=figma_url)[
                "outcome"
            ]
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


@celery_app.task(name="learn_from_pr")
def learn_from_pr_task(pr_number: int) -> list[str] | str:
    """Rules learned from a merged agent PR's review comments."""
    with open_pipeline(get_settings()) as pipeline:
        try:
            return learn_from_pr(pipeline, pr_number)
        except NotMergedError:
            return "not_merged"
