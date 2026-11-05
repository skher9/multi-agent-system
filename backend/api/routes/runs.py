"""Start a pipeline run for a Jira ticket, answer a run paused for plan approval, or
read a run's timeline for the live run window. The run happens in a worker, not here.

Check on it with GET /jobs/{job_id}; its result is where the run ended (e.g. "blocked").
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select

from api.auth import current_user
from api.db import SessionFactory
from api.routes.jobs import JobStarted
from db.models import AgentRun, Feature, LlmCall, RunEvent, Task
from orchestrator.decisions import PlanDecision
from services.jira import TICKET_KEY
from workers.celery_app import celery_app

# Logged-in website users only (api/auth.py)
router = APIRouter(prefix="/runs", tags=["runs"], dependencies=[Depends(current_user)])


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


MAX_EVENTS = 500  # per request; the browser asks again with `after`


class EventOut(BaseModel):
    id: int
    kind: str
    data: dict[str, Any]
    agent_run_id: int | None
    created_at: datetime


class RunTimeline(BaseModel):
    ticket: str
    title: str
    status: str  # the feature's status, e.g. running, in_review, ready_to_merge
    pr_url: str | None
    cost_inr: float  # every model call of this ticket so far
    events: list[EventOut]  # newer than `after`, oldest first


@router.get("/{ticket}/events")
def run_events(
    ticket: Annotated[str, Path(pattern=f"^{TICKET_KEY.pattern}$")],
    factory: SessionFactory,
    after: Annotated[int, Query(ge=0)] = 0,
) -> RunTimeline:
    """A ticket's run timeline, for the live run window. Poll with `after` = the last
    event id you have, and only newer events come back."""
    with factory() as session:
        feature = session.scalars(
            select(Feature).where(Feature.jira_key == ticket).order_by(Feature.id.desc())
        ).first()
        if feature is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"no run for {ticket} yet")
        rows = session.scalars(
            select(RunEvent)
            .where(RunEvent.feature_id == feature.id, RunEvent.id > after)
            .order_by(RunEvent.id)
            .limit(MAX_EVENTS)
        ).all()
        cost = session.scalar(
            select(func.coalesce(func.sum(LlmCall.cost_inr), 0))
            .join(AgentRun, LlmCall.agent_run_id == AgentRun.id)
            .join(Task, AgentRun.task_id == Task.id)
            .where(Task.feature_id == feature.id)
        )
        # The open_pr box records the PR's address when it finishes
        pr_url = session.scalar(
            select(RunEvent.data["pr_url"].astext)
            .where(RunEvent.feature_id == feature.id, RunEvent.data.has_key("pr_url"))
            .order_by(RunEvent.id.desc())
            .limit(1)
        )
        return RunTimeline(
            ticket=ticket,
            title=feature.title,
            status=feature.status,
            pr_url=pr_url,
            cost_inr=float(cost or 0),
            events=[
                EventOut(
                    id=row.id,
                    kind=row.kind,
                    data=row.data,
                    agent_run_id=row.agent_run_id,
                    created_at=row.created_at,
                )
                for row in rows
            ],
        )


@router.post("/{ticket}/plan-decision", status_code=status.HTTP_202_ACCEPTED)
def decide_plan(
    ticket: Annotated[str, Path(pattern=f"^{TICKET_KEY.pattern}$")], body: PlanDecision
) -> JobStarted:
    """Answer a run paused for plan approval: approve, revise (with feedback) or reject.
    The job's result is "not_waiting" if no plan was waiting."""
    job = celery_app.send_task("decide_plan", args=[ticket, body.model_dump()])
    return JobStarted(job_id=job.id)
