"""Database rows for runs: who owns the project, which feature a ticket is, which agent ran.

users -> projects -> features (one per Jira ticket) -> tasks (one per role) -> agent_runs
features -> run_events (the run's timeline)
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from db.models import (
    AgentRun,
    EventKind,
    Feature,
    Project,
    ProjectKind,
    RepoRule,
    RunEvent,
    Task,
    User,
)
from llm_router.models import Role, model_for

TITLE_MAX = 200  # features.title is String(200)
# Story runs are capped at 30 minutes, so a run "running" longer than this has died.
STALE_AFTER = timedelta(minutes=30)
MAX_RULES = 20  # rules agents read per project: the newest, so the prompt stays short

logger = logging.getLogger(__name__)


def ensure_project(
    factory: sessionmaker[Session], *, owner_email: str, name: str, repo_url: str
) -> int:
    """Find or create the owner and their project for a repo; return the project id."""
    with factory.begin() as session:
        user = session.scalar(select(User).where(User.email == owner_email))
        if user is None:
            user = User(email=owner_email)
            session.add(user)
            session.flush()  # sends the insert so user.id exists
        project = session.scalar(
            select(Project).where(Project.user_id == user.id, Project.code_repo_url == repo_url)
        )
        if project is None:
            project = Project(
                user_id=user.id,
                name=name,
                kind=ProjectKind.EXISTING,  # the repo already exists; agents change it
                code_repo_url=repo_url,
                status="active",
            )
            session.add(project)
            session.flush()
        return project.id


def ensure_feature(factory: sessionmaker[Session], project_id: int, jira_key: str) -> int:
    """The feature for a ticket. Re-running a ticket reuses it, so its budget adds up."""
    with factory.begin() as session:
        feature = session.scalar(
            select(Feature).where(Feature.project_id == project_id, Feature.jira_key == jira_key)
        )
        if feature is None:
            feature = Feature(
                project_id=project_id, jira_key=jira_key, title=jira_key, status="new"
            )
            session.add(feature)
            session.flush()
        return feature.id


def claim_feature(factory: sessionmaker[Session], feature_id: int) -> bool:
    """Mark the feature running, unless another run already is. True if we got it.

    One UPDATE, so two runs racing for the same feature can't both win: Postgres makes
    the second wait for the first, then re-checks the WHERE and finds it running.
    A "running" left behind by a killed worker counts as dead after STALE_AFTER.
    """
    with factory.begin() as session:
        claimed = session.scalar(
            update(Feature)
            .where(
                Feature.id == feature_id,
                or_(Feature.status != "running", Feature.updated_at < func.now() - STALE_AFTER),
            )
            .values(status="running")  # updated_at refreshes itself (onupdate)
            .returning(Feature.id)
        )
        return claimed is not None


def update_feature(
    factory: sessionmaker[Session], feature_id: int, *, status: str, title: str | None = None
) -> None:
    with factory.begin() as session:
        feature = session.get_one(Feature, feature_id)
        feature.status = status
        if title is not None:
            feature.title = title[:TITLE_MAX]


@contextmanager
def agent_run(factory: sessionmaker[Session], feature_id: int, role: str) -> Iterator[int]:
    """One agent's turn on a feature: yields the agent_run id, then marks it done or failed."""
    with factory.begin() as session:
        task = session.scalar(select(Task).where(Task.feature_id == feature_id, Task.role == role))
        if task is None:
            # attempts=0 explicitly: the column default only applies on insert, so a
            # new object's attempts would be None until then.
            task = Task(feature_id=feature_id, role=role, status="running", attempts=0)
            session.add(task)
        task.attempts += 1
        task.status = "running"
        session.flush()
        run = AgentRun(
            task_id=task.id,
            role=role,
            model=model_for(Role(role)),
            status="running",
            started_at=datetime.now(UTC),
        )
        session.add(run)
        session.flush()
        task_id, run_id = task.id, run.id
    try:
        yield run_id
    except BaseException:
        _finish(factory, task_id, run_id, "failed")
        raise
    _finish(factory, task_id, run_id, "done")


def _finish(factory: sessionmaker[Session], task_id: int, run_id: int, status: str) -> None:
    with factory.begin() as session:
        run = session.get_one(AgentRun, run_id)
        run.status = status
        run.ended_at = datetime.now(UTC)
        session.get_one(Task, task_id).status = status


def record_event(
    factory: sessionmaker[Session],
    feature_id: int,
    kind: EventKind,
    data: dict[str, Any] | None = None,
    *,
    agent_run_id: int | None = None,
) -> None:
    """Add one event to the feature's timeline. Never raises: the timeline is for
    watching a run, so losing an event must not stop the run itself."""
    try:
        with factory.begin() as session:
            session.add(
                RunEvent(
                    feature_id=feature_id, agent_run_id=agent_run_id, kind=kind, data=data or {}
                )
            )
    except SQLAlchemyError:
        logger.warning("could not record a %s event (feature %d)", kind, feature_id, exc_info=True)


def project_rules(factory: sessionmaker[Session], project_id: int) -> list[str]:
    """The project's newest rules learned from human reviews, as "rule (why)" lines."""
    with factory() as session:
        rules = session.scalars(
            select(RepoRule)
            .where(RepoRule.project_id == project_id)
            .order_by(RepoRule.id.desc())
            .limit(MAX_RULES)
        )
        return [f"{r.rule} ({r.why})" for r in rules]


def save_rules(
    factory: sessionmaker[Session], project_id: int, rules: list[tuple[str, str]], source: str
) -> int:
    """Save (rule, why) pairs; a rule the project already has is skipped. Returns how
    many were new."""
    if not rules:
        return 0
    with factory.begin() as session:
        added = session.scalars(
            insert(RepoRule)
            .values(
                [
                    {"project_id": project_id, "rule": rule, "why": why, "source": source}
                    for rule, why in rules
                ]
            )
            .on_conflict_do_nothing(constraint="uq_repo_rules_project_id_rule")
            .returning(RepoRule.id)
        ).all()
        return len(added)
