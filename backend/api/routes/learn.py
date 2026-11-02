"""Learn from a merged agent PR: people's review comments become rules the agents follow
on later tickets. The work happens in a worker.

The job's result is the new rules, or "not_merged" if the PR isn't merged yet.
"""

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from api.routes.jobs import JobStarted
from workers.celery_app import celery_app

router = APIRouter(prefix="/learn", tags=["learn"])


class LearnRequest(BaseModel):
    pr: int = Field(ge=1, description="Pull request number in the agent's repo")


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def learn(body: LearnRequest) -> JobStarted:
    job = celery_app.send_task("learn_from_pr", args=[body.pr])
    return JobStarted(job_id=job.id)
