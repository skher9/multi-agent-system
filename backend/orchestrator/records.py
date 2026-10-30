"""Database rows for runs: who owns the project, which feature a ticket is, which agent ran.

users -> projects -> features (one per Jira ticket) -> tasks (one per role) -> agent_runs
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from db.models import AgentRun, Feature, Project, ProjectKind, Task, User
from llm_router.models import Role, model_for

TITLE_MAX = 200  # features.title is String(200)


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
