"""The logged-in user's own project: connect their Jira and GitHub, see what's
connected, disconnect. Tokens are checked against Jira or GitHub before they're saved,
then stored encrypted (services/secret_box.py); no response ever contains one.

Disconnecting deletes our copy of the token. The token itself stays valid until the
user revokes it at Atlassian or GitHub (we can't revoke a token someone made), so the
website links them there.
"""

import re
from datetime import datetime
from typing import Annotated

import httpx2
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, SecretStr, StringConstraints, field_validator
from sqlalchemy.orm import Session, sessionmaker

from api.auth import CurrentUser, current_user
from api.config import get_settings
from api.db import SessionFactory
from db.models import IntegrationKind
from orchestrator.projects import connect, disconnect, ensure_user, integrations, own_project
from services.github import GitHubClient, RepoNotFoundError
from services.jira import PROJECT_KEY, JiraClient, TicketNotFoundError
from services.secret_box import SecretBox
from services.workspace import GITHUB_REPO

router = APIRouter(prefix="/me", tags=["me"], dependencies=[Depends(current_user)])

# Jira Cloud sites only: the token is sent to this address, so it can't be just any host
JIRA_HOST = re.compile(r"[a-z0-9][a-z0-9-]{0,62}\.atlassian\.net")
Token = Annotated[SecretStr, StringConstraints(min_length=10, max_length=400)]


class JiraConnection(BaseModel):
    site: str
    email: str
    project_key: str
    connected_at: datetime


class GitHubConnection(BaseModel):
    login: str
    repo: str
    connected_at: datetime


class OwnProject(BaseModel):
    available: bool  # false: this server can't store tokens (no INTEGRATIONS_KEY)
    jira: JiraConnection | None
    github: GitHubConnection | None
    project_id: int | None  # set once GitHub is connected
    ready: bool  # both connected: runs can use this project


class JiraConnect(BaseModel):
    site: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=320)]
    api_token: Token
    project_key: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True)]

    @field_validator("site")
    @classmethod
    def _jira_cloud_site(cls, value: str) -> str:
        """https://acme.atlassian.net, from whatever the user pasted (a board link too)."""
        host = re.sub(r"^https?://", "", value.lower()).split("/")[0]
        if not JIRA_HOST.fullmatch(host):
            raise ValueError("use your Jira Cloud address, like https://acme.atlassian.net")
        return f"https://{host}"

    @field_validator("project_key")
    @classmethod
    def _project_key(cls, value: str) -> str:
        if not PROJECT_KEY.fullmatch(value) or len(value) > 32:
            raise ValueError("a project key is letters and digits, like KAN")
        return value


class GitHubConnect(BaseModel):
    token: Token
    repo: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]

    @field_validator("repo")
    @classmethod
    def _owner_name(cls, value: str) -> str:
        """owner/name, from that or a github.com link."""
        repo = re.sub(r"^(https?://)?(www\.)?github\.com/", "", value).removesuffix(".git")
        repo = "/".join(repo.strip("/").split("/")[:2])
        if not GITHUB_REPO.fullmatch(repo):
            raise ValueError("use owner/name, like octo/shop")
        return repo


@router.get("/project")
def get_own_project(user: CurrentUser, factory: SessionFactory) -> OwnProject:
    return _own(factory, ensure_user(factory, user.id, user.email))


@router.put("/jira")
def connect_jira(body: JiraConnect, user: CurrentUser, factory: SessionFactory) -> OwnProject:
    box = _box()
    token = body.api_token.get_secret_value()
    jira = JiraClient(body.site, body.email, token)
    try:
        jira.myself()
        jira.project(body.project_key)
    except TicketNotFoundError as exc:
        raise _bad(f"This account can't see a Jira project {body.project_key}.") from exc
    except httpx2.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise _bad("Jira didn't accept that email and API token.") from exc
        raise _unreachable("Jira") from exc
    except httpx2.HTTPError as exc:
        raise _unreachable("Jira") from exc
    finally:
        jira.close()
    user_id = ensure_user(factory, user.id, user.email)
    connect(
        factory,
        user_id,
        IntegrationKind.JIRA,
        account=body.email,
        site=body.site,
        scope=body.project_key,
        sealed_token=box.seal(token),
    )
    return _own(factory, user_id)


@router.put("/github")
def connect_github(body: GitHubConnect, user: CurrentUser, factory: SessionFactory) -> OwnProject:
    box = _box()
    token = body.token.get_secret_value()
    github = GitHubClient(token, body.repo.split("/")[0])
    try:
        login = github.login()
        access = github.repo_access(body.repo)
    except RepoNotFoundError as exc:
        raise _bad(f"This token can't see {body.repo}. Give it access to that repo.") from exc
    except httpx2.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            raise _bad("GitHub didn't accept that token. Check it hasn't expired.") from exc
        raise _unreachable("GitHub") from exc
    except httpx2.HTTPError as exc:
        raise _unreachable("GitHub") from exc
    finally:
        github.close()
    if not access.can_push:
        raise _bad(f"{login} can't push to {access.repo}, so agents couldn't open a PR there.")
    user_id = ensure_user(factory, user.id, user.email)
    connect(
        factory,
        user_id,
        IntegrationKind.GITHUB,
        account=login,
        site=None,
        scope=access.repo,
        sealed_token=box.seal(token),
    )
    return _own(factory, user_id)


@router.delete("/{kind}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_integration(
    kind: IntegrationKind, user: CurrentUser, factory: SessionFactory
) -> Response:
    """Delete our copy of the token. 404 if that wasn't connected."""
    if not disconnect(factory, ensure_user(factory, user.id, user.email), kind):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{kind} isn't connected")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _own(factory: sessionmaker[Session], user_id: int) -> OwnProject:
    with factory() as session:
        found = integrations(session, user_id)
        jira, github = found.get(IntegrationKind.JIRA), found.get(IntegrationKind.GITHUB)
        project = own_project(session, user_id)
        return OwnProject(
            available=get_settings().integrations_key is not None,
            jira=JiraConnection(
                site=jira.site or "",
                email=jira.account,
                project_key=jira.scope,
                connected_at=jira.updated_at,
            )
            if jira
            else None,
            github=GitHubConnection(
                login=github.account, repo=github.scope, connected_at=github.updated_at
            )
            if github
            else None,
            project_id=project.id if project else None,
            ready=bool(jira and github and project),
        )


def _box() -> SecretBox:
    key = get_settings().integrations_key
    if key is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "connecting your own project isn't set up here"
        )
    return SecretBox(key.get_secret_value())


def _bad(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail)


def _unreachable(service: str) -> HTTPException:
    return HTTPException(status.HTTP_502_BAD_GATEWAY, f"Couldn't reach {service}. Try again.")
