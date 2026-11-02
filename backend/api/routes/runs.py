"""Start a pipeline run for a Jira ticket, or answer a run paused for plan approval.
The run happens in a worker, not here.

Check on it with GET /jobs/{job_id}; its result is where the run ended (e.g. "blocked").
"""

from typing import Annotated

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, StringConstraints

from api.routes.jobs import JobStarted
from orchestrator.decisions import PlanDecision
from services.jira import TICKET_KEY
from workers.celery_app import celery_app

router = APIRouter(prefix="/runs", tags=["runs"])


# Checked here too, so a bad key gets a 422 now instead of a failed job later
TicketKey = Annotated[str, StringConstraints(pattern=f"^{TICKET_KEY.pattern}$")]


class RunRequest(BaseModel):
    ticket: TicketKey
    approve_plan: bool = False  # pause after planning until a human decides


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def start_run(body: RunRequest) -> JobStarted:
    """Queue a run. 202 = accepted, not finished."""
    job = celery_app.send_task("run_ticket", args=[body.ticket, body.approve_plan])
    return JobStarted(job_id=job.id)


@router.post("/{ticket}/plan-decision", status_code=status.HTTP_202_ACCEPTED)
def decide_plan(
    ticket: Annotated[str, Path(pattern=f"^{TICKET_KEY.pattern}$")], body: PlanDecision
) -> JobStarted:
    """Answer a run paused for plan approval: approve, revise (with feedback) or reject.
    The job's result is "not_waiting" if no plan was waiting."""
    job = celery_app.send_task("decide_plan", args=[ticket, body.model_dump()])
    return JobStarted(job_id=job.id)
