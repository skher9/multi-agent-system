from api.config import get_settings
from orchestrator.runner import AlreadyRunningError, run_ticket
from orchestrator.wiring import open_pipeline
from workers.celery_app import celery_app


@celery_app.task(name="ping")
def ping() -> str:
    """Setup test task: proves a worker picked the job off the queue and ran it."""
    return "pong"


@celery_app.task(name="run_ticket")
def run_ticket_task(ticket_key: str) -> str:
    """One pipeline run for a Jira ticket. Returns where it ended, e.g. "blocked"."""
    with open_pipeline(get_settings()) as pipeline:
        try:
            return run_ticket(pipeline, ticket_key)["outcome"]
        except AlreadyRunningError:
            return "already_running"  # not a failure: the other run carries on
