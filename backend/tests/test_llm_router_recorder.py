"""Real database test: writes to the Neon test branch, then deletes what it made.

Skipped when DATABASE_URL_TEST isn't set (for example in CI).
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from api.config import get_settings
from db.models import AgentRun, Feature, LlmCall, Project, ProjectKind, Task, User
from db.session import make_session_factory
from llm_router.recorder import db_recorder
from llm_router.router import CallRecord

test_db_url = get_settings().database_url_test

pytestmark = pytest.mark.skipif(test_db_url is None, reason="DATABASE_URL_TEST not set")


def test_db_recorder_saves_one_llm_calls_row() -> None:
    assert test_db_url is not None
    factory = make_session_factory(test_db_url.get_secret_value())

    # The chain llm_calls needs: user -> project -> feature -> task -> agent_run.
    # flush() sends each insert so the next row can use its id.
    with factory.begin() as session:
        user = User(email=f"recorder-test-{uuid.uuid4().hex}@example.com")
        session.add(user)
        session.flush()
        project = Project(user_id=user.id, name="t", kind=ProjectKind.NEW, status="test")
        session.add(project)
        session.flush()
        feature = Feature(project_id=project.id, title="t", status="test")
        session.add(feature)
        session.flush()
        task = Task(feature_id=feature.id, role="developer", status="test")
        session.add(task)
        session.flush()
        run = AgentRun(task_id=task.id, role="developer", model="m", status="test")
        session.add(run)
        session.flush()
        user_id, run_id = user.id, run.id

    try:
        db_recorder(factory)(
            CallRecord(
                agent_run_id=run_id,
                model="minimax/minimax-m3",
                input_tokens=1200,
                cached_tokens=1000,
                output_tokens=30,
                cost_inr=Decimal("0.0965"),
                latency_ms=850,
            )
        )
        with factory() as session:
            row = session.scalars(select(LlmCall).where(LlmCall.agent_run_id == run_id)).one()
            assert row.cost_inr == Decimal("0.0965")
            assert row.cached_tokens == 1000
    finally:
        # Deleting the user cascades down to every row this test created.
        with factory.begin() as session:
            session.delete(session.get_one(User, user_id))
