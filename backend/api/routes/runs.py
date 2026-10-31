"""Start a pipeline run for a Jira ticket. The run happens in a worker, not here.

Check on it with GET /jobs/{job_id}; its result is where the run ended (e.g. "blocked").
"""

from typing import Annotated

from fastapi import APIRouter, status
from pydantic import BaseModel, StringConstraints

from api.routes.jobs import JobStarted
from services.jira import TICKET_KEY
from workers.celery_app import celery_app

router = APIRouter(prefix="/runs", tags=["runs"])


class RunRequest(BaseModel):
    # Checked here too, so a bad key gets a 422 now instead of a failed job later
    ticket: Annotated[str, StringConstraints(pattern=f"^{TICKET_KEY.pattern}$")]


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def start_run(body: RunRequest) -> JobStarted:
    """Queue a run. 202 = accepted, not finished."""
    job = celery_app.send_task("run_ticket", args=[body.ticket])
    return JobStarted(job_id=job.id)
