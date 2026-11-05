"""Start background jobs and check on them. The API never waits for a job to finish.

Jobs are sent by name, so the API never imports worker code: it only drops a
message on the queue. Heavy agent code will live in the worker process alone.
"""

from typing import Any, Literal

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from api.auth import current_user
from workers.celery_app import celery_app

# Logged-in website users only (api/auth.py)
router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(current_user)])


class JobStarted(BaseModel):
    job_id: str


class JobStatus(BaseModel):
    job_id: str
    # PENDING also means "unknown id": Celery can't tell the two apart.
    status: Literal["PENDING", "STARTED", "RETRY", "FAILURE", "SUCCESS"]
    result: Any = None


@router.post("/ping", status_code=status.HTTP_202_ACCEPTED)
def start_ping() -> JobStarted:
    """Queue the ping task. 202 = accepted, not finished."""
    job = celery_app.send_task("ping")
    return JobStarted(job_id=job.id)


@router.get("/{job_id}")
def get_job(job_id: str) -> JobStatus:
    job = AsyncResult(job_id, app=celery_app)
    # On failure, show only the error type, never the full traceback.
    if job.failed():
        return JobStatus(job_id=job_id, status="FAILURE", result=type(job.result).__name__)
    result = job.result if job.successful() else None
    return JobStatus(job_id=job_id, status=job.status, result=result)
