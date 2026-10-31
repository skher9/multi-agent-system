"""Throwaway rows for live scripts: a full parent chain that is deleted afterwards.

Until the orchestrator creates real projects and runs, live scripts use this to get an
agent_run id, which every llm_calls row needs.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker

from db.models import AgentRun, Feature, Project, ProjectKind, Task, User


@contextmanager
def scratch_agent_run(factory: sessionmaker[Session], role: str) -> Iterator[int]:
    """Yield a new agent_run id; delete every row it needed on exit (even after a crash)."""
    with factory.begin() as session:
        user = User(email=f"scratch-{uuid.uuid4().hex}@example.com")
        session.add(user)
        session.flush()  # sends the insert so the next row can use user.id
        project = Project(user_id=user.id, name="scratch", kind=ProjectKind.NEW, status="test")
        session.add(project)
        session.flush()
        feature = Feature(project_id=project.id, title="scratch", status="test")
        session.add(feature)
        session.flush()
        task = Task(feature_id=feature.id, role=role, status="test")
        session.add(task)
        session.flush()
        run = AgentRun(task_id=task.id, role=role, model="scratch", status="test")
        session.add(run)
        session.flush()
        user_id, run_id = user.id, run.id
    try:
        yield run_id
    finally:
        with factory.begin() as session:
            # Deleting the user cascades down to every row above, llm_calls included.
            session.delete(session.get_one(User, user_id))
