"""Free runs: each account may start settings.free_runs runs; the owner has no limit."""

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from api.auth import User
from api.config import get_settings
from api.main import app
from orchestrator.credits import unlimited
from tests.test_own_project import act_as, factory, test_db_url, users  # noqa: F401  (fixtures)
from workers.celery_app import celery_app

client = TestClient(app)
pytestmark = pytest.mark.skipif(test_db_url is None, reason="DATABASE_URL_TEST not set")


@pytest.fixture
def queue(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    sent: list[str] = []
    monkeypatch.setattr(
        celery_app, "send_task", lambda name, args: sent.append(args[0]) or SimpleNamespace(id="j")
    )
    monkeypatch.setattr(get_settings(), "free_runs", 2)
    monkeypatch.setattr(get_settings(), "agent_owner_email", "owner@example.com")
    return sent


def test_each_account_gets_its_free_runs_then_a_clear_no(
    users: list[User],  # noqa: F811
    queue: list[str],
) -> None:
    assert client.get("/me/credits").json() == {"left": 2, "total": 2}
    assert client.post("/runs", json={"ticket": "KAN-4"}).status_code == 202
    assert client.post("/runs", json={"ticket": "KAN-5"}).status_code == 202
    refused = client.post("/runs", json={"ticket": "KAN-6"})
    assert refused.status_code == 403
    assert "used your 2 free runs" in refused.json()["detail"]
    assert queue == ["KAN-4", "KAN-5"]
    assert client.get("/me/credits").json() == {"left": 0, "total": 2}

    act_as(users[1])  # another account has its own runs
    assert client.get("/me/credits").json() == {"left": 2, "total": 2}


def test_a_run_that_cant_be_queued_is_given_back(
    users: list[User],  # noqa: F811
    queue: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(name: str, args: list[Any]) -> None:
        raise ConnectionError("redis down")

    monkeypatch.setattr(celery_app, "send_task", broken)
    with pytest.raises(ConnectionError):
        client.post("/runs", json={"ticket": "KAN-4"})
    assert client.get("/me/credits").json() == {"left": 2, "total": 2}


def test_the_owner_has_no_limit(
    users: list[User],  # noqa: F811
    queue: list[str],
    factory: sessionmaker[Session],  # noqa: F811
) -> None:
    owner = User(id=users[0].id, email="Owner@Example.com", name="Owner")
    act_as(owner)
    for n in range(3):
        assert client.post("/runs", json={"ticket": f"KAN-{n + 1}"}).status_code == 202
    assert client.get("/me/credits").json() == {"left": None, "total": 2}


def test_unlimited_only_for_the_configured_owner() -> None:
    assert unlimited("a@x.com", "A@X.com")
    assert not unlimited("a@x.com", None)
    assert not unlimited("a@x.com", "")
    assert not unlimited("b@x.com", "a@x.com")
