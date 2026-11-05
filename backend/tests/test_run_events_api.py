"""GET /runs/{ticket}/events on the real Neon test branch (skipped without DATABASE_URL_TEST)."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from api.config import get_settings
from api.db import session_factory
from api.main import app
from db.models import EventKind, User
from db.session import make_session_factory
from orchestrator.records import ensure_feature, ensure_project, record_event

test_db_url = get_settings().database_url_test
pytestmark = pytest.mark.skipif(test_db_url is None, reason="DATABASE_URL_TEST not set")
client = TestClient(app)


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    assert test_db_url is not None
    made = make_session_factory(test_db_url.get_secret_value())
    app.dependency_overrides[session_factory] = lambda: made
    yield made
    app.dependency_overrides.pop(session_factory, None)


@pytest.fixture
def ticket(factory: sessionmaker[Session]) -> Iterator[tuple[str, int]]:
    email = f"events-test-{uuid.uuid4().hex}@example.com"
    project = ensure_project(factory, owner_email=email, name="pg", repo_url="https://x.git")
    key = f"EVT-{uuid.uuid4().int % 10**6}"
    yield key, ensure_feature(factory, project, key)
    with factory.begin() as session:
        session.delete(session.scalars(select(User).where(User.email == email)).one())


def test_timeline_in_order_then_only_newer(
    ticket: tuple[str, int], factory: sessionmaker[Session]
) -> None:
    key, feature_id = ticket
    record_event(factory, feature_id, EventKind.RUN_STARTED, {"resumed": False})
    record_event(factory, feature_id, EventKind.NODE_STARTED, {"node": "fetch_ticket"})
    body = client.get(f"/runs/{key}/events").json()
    assert [e["kind"] for e in body["events"]] == ["run_started", "node_started"]
    assert body["pr_url"] is None and body["cost_inr"] == 0

    last = body["events"][-1]["id"]
    url = "https://github.com/o/r/pull/9"
    record_event(factory, feature_id, EventKind.NODE_FINISHED, {"node": "open_pr", "pr_url": url})
    newer = client.get(f"/runs/{key}/events", params={"after": last}).json()
    assert [e["data"]["node"] for e in newer["events"]] == ["open_pr"]
    assert newer["pr_url"] == url


def test_unknown_ticket_is_404(factory: sessionmaker[Session]) -> None:
    assert client.get("/runs/NOPE-424242/events").status_code == 404


def test_bad_ticket_key_is_422() -> None:
    assert client.get("/runs/not-a-key/events").status_code == 422


def test_recent_runs_lists_the_ticket_with_its_pr(
    ticket: tuple[str, int], factory: sessionmaker[Session]
) -> None:
    key, feature_id = ticket
    url = "https://github.com/o/r/pull/3"
    record_event(factory, feature_id, EventKind.NODE_FINISHED, {"node": "open_pr", "pr_url": url})
    runs = client.get("/runs").json()
    mine = next(r for r in runs if r["ticket"] == key)
    assert mine["pr_url"] == url
    assert mine["cost_inr"] == 0


def test_timeline_links_to_ticket_repo_and_branch(
    ticket: tuple[str, int], factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "jira_base_url", "https://site.atlassian.net/")
    monkeypatch.setattr(settings, "agent_repo", "o/r")
    monkeypatch.setattr(settings, "jira_project_key", None)
    key, feature_id = ticket
    body = client.get(f"/runs/{key}/events").json()
    assert body["ticket_url"] == f"https://site.atlassian.net/browse/{key}"
    assert body["branch_url"] is None  # nothing pushed yet
    project = key.split("-")[0]
    assert body["project"]["board_url"].endswith(f"/projects/{project}/boards")
    record_event(factory, feature_id, EventKind.NODE_FINISHED, {"node": "develop"})
    after = client.get(f"/runs/{key}/events").json()
    assert after["branch_url"] == f"https://github.com/o/r/tree/agent/{key}"
