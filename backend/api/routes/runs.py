"""Start a pipeline run for a Jira ticket, answer a run paused for plan approval, or
read a run's timeline for the live run window. The run happens in a worker, not here.

A run works on the demo project (project_id left out) or on the user's own project
(orchestrator/projects.py). Users see the demo's runs and their own, nobody else's.

Check on it with GET /jobs/{job_id}; its result is where the run ended (e.g. "blocked").
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, StringConstraints, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.auth import CurrentUser, User, current_user
from api.config import get_settings
from api.db import SessionFactory, session_factory
from api.routes.jobs import JobStarted
from db.models import AgentRun, EventKind, Feature, LlmCall, Project, RunEvent, Task
from orchestrator.decisions import PlanDecision
from orchestrator.projects import (
    demo_project_id,
    ensure_user,
    integrations,
    own_project,
    visible_project_ids,
)
from services.figma import find_link
from services.jira import TICKET_KEY
from workers.celery_app import celery_app

# Logged-in website users only (api/auth.py)
router = APIRouter(prefix="/runs", tags=["runs"], dependencies=[Depends(current_user)])


# Checked here too, so a bad key gets a 422 now instead of a failed job later
TicketKey = Annotated[str, StringConstraints(pattern=f"^{TICKET_KEY.pattern}$")]
# Which project: left out = the demo
ProjectId = Annotated[int | None, Query(ge=1)]


class RunRequest(BaseModel):
    ticket: TicketKey
    approve_plan: bool = False  # pause after planning until a human decides
    # A Figma frame to build the screen from (agents/design.py); "" = none
    figma_url: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""
    project_id: int | None = None  # the user's own project; None = the demo

    @field_validator("figma_url")
    @classmethod
    def _a_figma_link(cls, value: str) -> str:
        link = find_link(value)
        if value and (link is None or link.url != value):
            raise ValueError("not a Figma design link")
        return value


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def start_run(body: RunRequest, user: CurrentUser) -> JobStarted:
    """Queue a run. 202 = accepted, not finished. On the user's own project, the ticket
    must be in their Jira project, and their runs share a daily budget (429 past it)."""
    if body.project_id is not None:
        _check_own_run(user, body.project_id, body.ticket)
    job = celery_app.send_task(
        "run_ticket", args=[body.ticket, body.approve_plan, body.figma_url, body.project_id]
    )
    return JobStarted(job_id=job.id)


def _check_own_run(user: User, project_id: int, ticket: str) -> None:
    factory = session_factory()  # only own projects need the database here
    user_id = ensure_user(factory, user.id, user.email)
    with factory() as session:
        project = own_project(session, user_id)
        connected = integrations(session, user_id)
        if project is None or project.id != project_id or len(connected) < 2:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "connect your Jira and GitHub in Settings first"
            )
        key = project.jira_project_key
        if ticket.split("-")[0] != key:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, f"{ticket} isn't in your Jira project {key}"
            )
        budget = get_settings().user_daily_budget_inr
        if _spent_today(session, user_id) >= budget:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"your projects used today's ₹{budget} of runs; try again tomorrow",
            )


def _spent_today(session: Session, user_id: int) -> Decimal:
    """Model spend on the user's own projects, last 24 hours."""
    since = func.now() - timedelta(hours=24)
    return Decimal(
        session.scalar(
            select(func.coalesce(func.sum(LlmCall.cost_inr), 0))
            .join(AgentRun, LlmCall.agent_run_id == AgentRun.id)
            .join(Task, AgentRun.task_id == Task.id)
            .join(Feature, Task.feature_id == Feature.id)
            .join(Project, Feature.project_id == Project.id)
            .where(Project.user_id == user_id, LlmCall.created_at >= since)
        )
        or 0
    )


MAX_EVENTS = 500  # per request; the browser asks again with `after`
RECENT_RUNS = 20


class RunSummary(BaseModel):
    ticket: str
    project_id: int
    demo: bool  # on the demo project, not the user's own
    title: str
    status: str  # running, in_review, ready_to_merge, needs_human, blocked, failed...
    pr_url: str | None
    cost_inr: float
    started_at: datetime
    updated_at: datetime


@router.get("")
def recent_runs(user: CurrentUser, factory: SessionFactory) -> list[RunSummary]:
    """The latest runs the user may see (the demo's and their own), newest first."""
    user_id = ensure_user(factory, user.id, user.email)
    with factory() as session:
        demo = demo_project_id(session, get_settings())
        features = session.scalars(
            select(Feature)
            .where(
                Feature.jira_key.is_not(None),
                Feature.project_id.in_(visible_project_ids(session, get_settings(), user_id)),
            )
            .order_by(Feature.updated_at.desc())
            .limit(RECENT_RUNS)
        ).all()
        ids = [f.id for f in features]
        costs = dict(
            session.execute(
                select(Task.feature_id, func.coalesce(func.sum(LlmCall.cost_inr), 0))
                .join(AgentRun, AgentRun.task_id == Task.id)
                .join(LlmCall, LlmCall.agent_run_id == AgentRun.id)
                .where(Task.feature_id.in_(ids))
                .group_by(Task.feature_id)
            ).all()
        )
        prs = dict(
            session.execute(
                select(RunEvent.feature_id, func.max(RunEvent.data["pr_url"].astext))
                .where(RunEvent.feature_id.in_(ids), RunEvent.data.has_key("pr_url"))
                .group_by(RunEvent.feature_id)
            ).all()
        )
        return [
            RunSummary(
                ticket=f.jira_key or "",
                project_id=f.project_id,
                demo=f.project_id == demo,
                title=f.title.removeprefix(f"{f.jira_key}: "),
                status=f.status,
                pr_url=prs.get(f.id),
                cost_inr=float(costs.get(f.id, 0)),
                started_at=f.created_at,
                updated_at=f.updated_at,
            )
            for f in features
        ]


class EventOut(BaseModel):
    id: int
    kind: str
    data: dict[str, Any]
    agent_run_id: int | None
    created_at: datetime


class ProjectLinks(BaseModel):
    """Where a run's work lives, so the run window can link to it."""

    repo: str | None  # owner/name
    repo_url: str | None
    jira_site: str | None
    jira_project: str | None
    board_url: str | None


class RunTimeline(BaseModel):
    ticket: str
    project_id: int
    demo: bool
    title: str
    ticket_url: str | None
    branch_url: str | None  # once the developer has pushed (agent/<ticket>)
    project: ProjectLinks
    status: str  # the feature's status, e.g. running, in_review, ready_to_merge
    pr_url: str | None
    cost_inr: float  # every model call of this ticket so far
    events: list[EventOut]  # newer than `after`, oldest first


def project_links(jira_project: str | None = None) -> ProjectLinks:
    """The demo project's GitHub repo and Jira board, from settings."""
    settings = get_settings()
    site = (settings.jira_base_url or "").rstrip("/") or None
    return links(settings.agent_repo, site, settings.jira_project_key or jira_project)


def own_links(project: Project) -> ProjectLinks:
    """A user's own project's repo and board, from its row."""
    repo = (project.code_repo_url or "").removeprefix("https://github.com/").removesuffix(".git")
    return links(repo or None, project.jira_site, project.jira_project_key)


def links(repo: str | None, site: str | None, key: str | None) -> ProjectLinks:
    return ProjectLinks(
        repo=repo,
        repo_url=f"https://github.com/{repo}" if repo else None,
        jira_site=site,
        jira_project=key,
        board_url=f"{site}/jira/software/projects/{key}/boards" if site and key else None,
    )


@router.get("/{ticket}/events")
def run_events(
    ticket: Annotated[str, Path(pattern=f"^{TICKET_KEY.pattern}$")],
    user: CurrentUser,
    factory: SessionFactory,
    project_id: ProjectId = None,
    after: Annotated[int, Query(ge=0)] = 0,
) -> RunTimeline:
    """A ticket's run timeline, for the live run window. Poll with `after` = the last
    event id you have, and only newer events come back."""
    user_id = ensure_user(factory, user.id, user.email)
    with factory() as session:
        project, demo = _visible(session, user_id, project_id)
        feature = session.scalars(
            select(Feature).where(Feature.project_id == project, Feature.jira_key == ticket)
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
        found = (
            project_links(ticket.split("-")[0])
            if demo
            else own_links(session.get_one(Project, project))
        )
        developed = session.scalar(
            select(func.count())
            .select_from(RunEvent)
            .where(
                RunEvent.feature_id == feature.id,
                RunEvent.kind == EventKind.NODE_FINISHED,
                RunEvent.data["node"].astext == "develop",
            )
        )
        return RunTimeline(
            ticket=ticket,
            title=feature.title.removeprefix(f"{ticket}: "),
            project_id=project,
            demo=demo,
            ticket_url=f"{found.jira_site}/browse/{ticket}" if found.jira_site else None,
            branch_url=f"{found.repo_url}/tree/agent/{ticket}"
            if found.repo_url and developed
            else None,
            project=found,
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
    ticket: Annotated[str, Path(pattern=f"^{TICKET_KEY.pattern}$")],
    body: PlanDecision,
    user: CurrentUser,
    project_id: ProjectId = None,
) -> JobStarted:
    """Answer a run paused for plan approval: approve, revise (with feedback) or reject.
    The job's result is "not_waiting" if no plan was waiting."""
    if project_id is not None:  # the demo needs no check: anyone may decide its plans
        factory = session_factory()
        user_id = ensure_user(factory, user.id, user.email)
        with factory() as session:
            _visible(session, user_id, project_id)
    job = celery_app.send_task("decide_plan", args=[ticket, body.model_dump(), project_id])
    return JobStarted(job_id=job.id)


def _visible(session: Session, user_id: int, project_id: int | None) -> tuple[int, bool]:
    """The project a request names (None = the demo), as (id, is it the demo).
    404 for a project the user may not see, same as for one that doesn't exist."""
    settings = get_settings()
    demo = demo_project_id(session, settings)
    wanted = project_id or demo
    if wanted is None or wanted not in visible_project_ids(session, settings, user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such project")
    return wanted, wanted == demo
