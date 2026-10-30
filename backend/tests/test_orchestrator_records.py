"""Run records on the real Neon test branch (skipped without DATABASE_URL_TEST).

Each test gets its own owner email and deletes that user at the end, which cascades
to every row it created.
"""

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from api.config import get_settings
from db.models import AgentRun, Feature, Project, Task, User
from db.session import make_session_factory
from orchestrator.records import agent_run, ensure_feature, ensure_project, update_feature
from orchestrator.runner import Pipeline, run_ticket
from tests.test_orchestrator_graph import Fakes
from tests.test_ticket_reader import BLOCKED

test_db_url = get_settings().database_url_test

pytestmark = pytest.mark.skipif(test_db_url is None, reason="DATABASE_URL_TEST not set")

REPO = "https://github.com/skher9/agent-playground.git"


@pytest.fixture
def factory() -> sessionmaker[Session]:
    assert test_db_url is not None
    return make_session_factory(test_db_url.get_secret_value())


@pytest.fixture
def project_id(factory: sessionmaker[Session]) -> Iterator[int]:
    email = f"records-test-{uuid.uuid4().hex}@example.com"
    yield ensure_project(factory, owner_email=email, name="playground", repo_url=REPO)
    with factory.begin() as session:
        session.delete(session.scalars(select(User).where(User.email == email)).one())


def test_ensure_project_finds_the_existing_project(
    factory: sessionmaker[Session], project_id: int
) -> None:
    with factory() as session:
        email = session.scalars(
            select(User.email)
            .join(Project, Project.user_id == User.id)
            .where(Project.id == project_id)
        ).one()
    again = ensure_project(factory, owner_email=email, name="playground", repo_url=REPO)
    assert again == project_id


def test_ensure_feature_gives_one_feature_per_ticket(
    factory: sessionmaker[Session], project_id: int
) -> None:
    first = ensure_feature(factory, project_id, "KAN-4")
    assert ensure_feature(factory, project_id, "KAN-4") == first
    assert ensure_feature(factory, project_id, "KAN-5") != first


def test_agent_run_marks_done_and_counts_attempts(
    factory: sessionmaker[Session], project_id: int
) -> None:
    feature_id = ensure_feature(factory, project_id, "KAN-4")
    with agent_run(factory, feature_id, "ticket_reader") as first_run:
        pass
    with agent_run(factory, feature_id, "ticket_reader"):
        pass

    with factory() as session:
        task = session.scalars(select(Task).where(Task.feature_id == feature_id)).one()
        assert task.attempts == 2
        assert task.status == "done"
        run = session.get_one(AgentRun, first_run)
        assert run.status == "done"
        assert run.model == "minimax/minimax-m3"
        assert run.ended_at is not None and run.started_at is not None


def test_agent_run_marks_failed_when_the_agent_raises(
    factory: sessionmaker[Session], project_id: int
) -> None:
    feature_id = ensure_feature(factory, project_id, "KAN-4")
    with pytest.raises(RuntimeError), agent_run(factory, feature_id, "developer") as run_id:
        raise RuntimeError("agent crashed")

    with factory() as session:
        assert session.get_one(AgentRun, run_id).status == "failed"


def test_update_feature_trims_long_titles(factory: sessionmaker[Session], project_id: int) -> None:
    feature_id = ensure_feature(factory, project_id, "KAN-4")
    update_feature(factory, feature_id, status="blocked", title="x" * 500)
    with factory() as session:
        feature = session.get_one(Feature, feature_id)
        assert (feature.status, len(feature.title)) == ("blocked", 200)


def test_run_ticket_records_the_whole_run(factory: sessionmaker[Session], project_id: int) -> None:
    fakes = Fakes(BLOCKED)  # fake Jira and model; the database is real
    pipeline = Pipeline(factory, fakes.context.jira, fakes.context.router, project_id)

    final = run_ticket(pipeline, "KAN-4")

    assert final["outcome"] == "blocked"
    with factory() as session:
        feature = session.scalars(select(Feature).where(Feature.project_id == project_id)).one()
        assert feature.jira_key == "KAN-4"
        assert feature.status == "blocked"
        assert feature.title == "KAN-4: Add a contact page"
        task = session.scalars(select(Task).where(Task.feature_id == feature.id)).one()
        assert (task.role, task.status) == ("ticket_reader", "done")
