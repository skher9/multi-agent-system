"""Real database tests: write to the Neon test branch, then delete what they made.

Skipped when DATABASE_URL_TEST isn't set (for example in CI).
"""

import uuid
from collections.abc import Callable, Iterator
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from api.config import get_settings
from db.models import AgentRun, Feature, LlmCall, Project, ProjectKind, Task, User
from db.session import make_session_factory
from llm_router.budget import db_story_spend
from llm_router.recorder import db_recorder
from llm_router.router import CallRecord

test_db_url = get_settings().database_url_test

pytestmark = pytest.mark.skipif(test_db_url is None, reason="DATABASE_URL_TEST not set")

# Makes one agent run under the given feature (None = a new feature) -> (feature_id, run_id)
MakeRun = Callable[[int | None], tuple[int, int]]


@pytest.fixture
def factory() -> sessionmaker[Session]:
    assert test_db_url is not None
    return make_session_factory(test_db_url.get_secret_value())


@pytest.fixture
def make_run(factory: sessionmaker[Session]) -> Iterator[MakeRun]:
    """Builds the chain llm_calls needs: user -> project -> feature -> task -> agent_run.

    Deleting the user afterwards cascades down to every row the test created.
    """
    with factory.begin() as session:
        user = User(email=f"router-test-{uuid.uuid4().hex}@example.com")
        session.add(user)
        session.flush()  # sends the insert so the next row can use user.id
        project = Project(user_id=user.id, name="t", kind=ProjectKind.NEW, status="test")
        session.add(project)
        session.flush()
        user_id, project_id = user.id, project.id

    def make(feature_id: int | None) -> tuple[int, int]:
        with factory.begin() as session:
            if feature_id is None:
                feature = Feature(project_id=project_id, title="t", status="test")
                session.add(feature)
                session.flush()
                feature_id = feature.id
            task = Task(feature_id=feature_id, role="developer", status="test")
            session.add(task)
            session.flush()
            run = AgentRun(task_id=task.id, role="developer", model="m", status="test")
            session.add(run)
            session.flush()
            return feature_id, run.id

    yield make

    with factory.begin() as session:
        session.delete(session.get_one(User, user_id))


def call(run_id: int, cost_inr: str) -> CallRecord:
    return CallRecord(
        agent_run_id=run_id,
        model="minimax/minimax-m3",
        input_tokens=1200,
        cached_tokens=1000,
        output_tokens=30,
        cost_inr=Decimal(cost_inr),
        latency_ms=850,
    )


def test_db_recorder_saves_one_llm_calls_row(
    factory: sessionmaker[Session], make_run: MakeRun
) -> None:
    _, run_id = make_run(None)
    db_recorder(factory)(call(run_id, "0.0965"))

    with factory() as session:
        row = session.scalars(select(LlmCall).where(LlmCall.agent_run_id == run_id)).one()
        assert row.cost_inr == Decimal("0.0965")
        assert row.cached_tokens == 1000


def test_story_spend_sums_every_task_in_the_feature_only(
    factory: sessionmaker[Session], make_run: MakeRun
) -> None:
    record = db_recorder(factory)
    feature_id, developer_run = make_run(None)
    _, reviewer_run = make_run(feature_id)  # same story, another task
    _, other_story_run = make_run(None)

    record(call(developer_run, "10.5000"))
    record(call(developer_run, "4.2500"))
    record(call(reviewer_run, "3.0000"))
    record(call(other_story_run, "99.0000"))

    spent = db_story_spend(factory)
    assert spent(reviewer_run) == Decimal("17.7500")
    assert spent(other_story_run) == Decimal("99.0000")


def test_story_spend_is_zero_before_any_call(
    factory: sessionmaker[Session], make_run: MakeRun
) -> None:
    _, run_id = make_run(None)
    assert db_story_spend(factory)(run_id) == Decimal("0")
