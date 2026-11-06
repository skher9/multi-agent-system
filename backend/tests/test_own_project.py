"""A user's own project: connect Jira and GitHub, run on it, see only your own runs,
disconnect. Fake Jira and GitHub; the real Neon test branch (skipped without it)."""

import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import httpx2
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from api.auth import User, current_user
from api.config import get_settings
from api.db import session_factory
from api.main import app
from api.routes import me
from db.models import Integration
from db.models import User as UserRow
from db.session import make_session_factory
from orchestrator.projects import NotReadyError, credentials, ensure_user
from orchestrator.records import ensure_feature
from services.github import RepoAccess, RepoNotFoundError
from services.jira import JiraProject, TicketNotFoundError
from services.secret_box import SecretBox
from workers.celery_app import celery_app

test_db_url = get_settings().database_url_test
pytestmark = pytest.mark.skipif(test_db_url is None, reason="DATABASE_URL_TEST not set")
client = TestClient(app)
KEY = Fernet.generate_key().decode()
JIRA = {
    "site": "https://acme.atlassian.net/jira/software/projects/ACME/boards/1",
    "email": "me@acme.io",
    "api_token": "jira-token-123456",
    "project_key": "acme",
}
GITHUB = {"token": "github_pat_123456", "repo": "https://github.com/octo/shop"}


class FakeJira:
    def __init__(self, site: str, email: str, token: str) -> None:
        self.token = token

    def myself(self) -> str:
        if self.token == "wrong-token-123":
            request = httpx2.Request("GET", "https://x")
            raise httpx2.HTTPStatusError("401", request=request, response=httpx2.Response(401))
        return "Me"

    def project(self, key: str) -> JiraProject:
        if key != "ACME":
            raise TicketNotFoundError(key)
        return JiraProject("ACME", "Acme", None)

    def close(self) -> None: ...


class FakeGitHub:
    def __init__(self, token: str, org: str) -> None: ...

    def login(self) -> str:
        return "octo"

    def repo_access(self, repo: str) -> RepoAccess:
        if repo == "octo/read-only":
            return RepoAccess(repo, False, False)
        if repo != "octo/shop":
            raise RepoNotFoundError(repo)
        return RepoAccess(repo, True, True)

    def close(self) -> None: ...


@pytest.fixture
def factory(monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker[Session]]:
    assert test_db_url is not None
    made = make_session_factory(test_db_url.get_secret_value())
    app.dependency_overrides[session_factory] = lambda: made
    monkeypatch.setattr(get_settings(), "integrations_key", SecretStr(KEY))
    monkeypatch.setattr(me, "JiraClient", FakeJira)
    monkeypatch.setattr(me, "GitHubClient", FakeGitHub)
    import api.routes.runs as runs

    monkeypatch.setattr(runs, "session_factory", lambda: made)
    yield made
    app.dependency_overrides.pop(session_factory, None)


@pytest.fixture
def users(factory: sessionmaker[Session]) -> Iterator[list[User]]:
    """Two website users; requests act as the first unless a test switches."""
    made = [
        User(id=f"auth-{uuid.uuid4().hex}", email=f"own-{uuid.uuid4().hex}@example.com", name="A")
        for _ in range(2)
    ]
    act_as(made[0])
    yield made
    with factory.begin() as session:
        for row in session.scalars(
            select(UserRow).where(UserRow.email.in_([u.email for u in made]))
        ):
            session.delete(row)


def act_as(user: User) -> None:
    app.dependency_overrides[current_user] = lambda: user


def connect_both() -> dict[str, Any]:
    assert client.put("/me/jira", json=JIRA).status_code == 200
    response = client.put("/me/github", json=GITHUB)
    assert response.status_code == 200
    return response.json()


def test_connecting_both_makes_a_ready_project_with_encrypted_tokens(
    users: list[User], factory: sessionmaker[Session]
) -> None:
    empty = client.get("/me/project").json()
    assert empty == {
        "available": True,
        "jira": None,
        "github": None,
        "project_id": None,
        "ready": False,
    }
    body = connect_both()
    assert body["ready"] is True
    assert body["jira"]["site"] == "https://acme.atlassian.net"  # cut from the board link
    assert body["jira"]["project_key"] == "ACME"
    assert body["github"] == {**body["github"], "login": "octo", "repo": "octo/shop"}
    assert "token" not in str(body).replace("api_token", "")  # no token in any answer

    with factory() as session:
        rows = session.scalars(
            select(Integration).join(UserRow).where(UserRow.email == users[0].email)
        ).all()
        assert {r.kind for r in rows} == {"jira", "github"}
        assert all(b"token" not in r.secret and b"pat" not in r.secret for r in rows)
    found = credentials(factory, body["project_id"], SecretBox(KEY))
    assert (found.jira_token, found.github_token) == (JIRA["api_token"], GITHUB["token"])
    assert (found.repo, found.jira_project_key) == ("octo/shop", "ACME")


@pytest.mark.parametrize(
    ("path", "body", "code"),
    [
        ("/me/jira", {**JIRA, "site": "https://evil.example.com"}, 422),
        ("/me/jira", {**JIRA, "project_key": "a b"}, 422),
        ("/me/jira", {**JIRA, "project_key": "OTHER"}, 400),
        ("/me/jira", {**JIRA, "api_token": "wrong-token-123"}, 400),
        ("/me/github", {**GITHUB, "repo": "octo/missing"}, 400),
        ("/me/github", {**GITHUB, "repo": "octo/read-only"}, 400),
        ("/me/github", {**GITHUB, "repo": "not a repo"}, 422),
        ("/me/github", {**GITHUB, "token": "short"}, 422),
    ],
)
def test_bad_connections_are_refused_and_not_saved(
    users: list[User], path: str, body: dict[str, str], code: int
) -> None:
    assert client.put(path, json=body).status_code == code
    assert client.get("/me/project").json()["jira"] is None
    assert client.get("/me/project").json()["github"] is None


def test_runs_on_own_project_check_ticket_owner_and_budget(
    users: list[User], factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[list[Any]] = []
    monkeypatch.setattr(
        celery_app, "send_task", lambda name, args: sent.append(args) or SimpleNamespace(id="j")
    )
    project = connect_both()["project_id"]
    run = {"ticket": "ACME-3", "project_id": project}
    assert client.post("/runs", json=run).status_code == 202
    assert sent == [["ACME-3", False, "", project]]
    assert client.post("/runs", json={**run, "ticket": "KAN-3"}).status_code == 422

    monkeypatch.setattr(get_settings(), "user_daily_budget_inr", 0)
    assert client.post("/runs", json=run).status_code == 429

    act_as(users[1])  # someone else can't run on it
    assert client.post("/runs", json=run).status_code == 409
    assert len(sent) == 1


def test_only_the_owner_sees_their_runs(users: list[User], factory: sessionmaker[Session]) -> None:
    project = connect_both()["project_id"]
    ensure_feature(factory, project, "ACME-7")
    timeline = client.get("/runs/ACME-7/events", params={"project_id": project}).json()
    assert timeline["demo"] is False
    assert timeline["ticket_url"] == "https://acme.atlassian.net/browse/ACME-7"
    assert timeline["project"]["repo"] == "octo/shop"
    assert any(r["ticket"] == "ACME-7" for r in client.get("/runs").json())

    act_as(users[1])
    assert client.get("/runs/ACME-7/events", params={"project_id": project}).status_code == 404
    assert not any(r["ticket"] == "ACME-7" for r in client.get("/runs").json())
    decision = {"decision": "approve"}
    response = client.post(
        "/runs/ACME-7/plan-decision", params={"project_id": project}, json=decision
    )
    assert response.status_code == 404


def test_disconnect_deletes_the_token_and_stops_runs(
    users: list[User], factory: sessionmaker[Session]
) -> None:
    project = connect_both()["project_id"]
    assert client.delete("/me/jira").status_code == 204
    assert client.delete("/me/jira").status_code == 404
    after = client.get("/me/project").json()
    assert after["jira"] is None and after["ready"] is False
    assert after["project_id"] == project  # the project and its history stay
    with pytest.raises(NotReadyError):
        credentials(factory, project, SecretBox(KEY))
    assert client.delete("/me/github").status_code == 204
    assert client.get("/me/project").json()["project_id"] is None
    assert client.delete("/me/slack").status_code == 422


def test_a_new_login_with_an_old_email_takes_over_without_its_connections(
    users: list[User], factory: sessionmaker[Session]
) -> None:
    connect_both()
    old = ensure_user(factory, users[0].id, users[0].email)
    new_login = f"auth-{uuid.uuid4().hex}"
    assert ensure_user(factory, new_login, users[0].email) == old
    act_as(User(id=new_login, email=users[0].email, name="A"))
    assert client.get("/me/project").json()["jira"] is None
