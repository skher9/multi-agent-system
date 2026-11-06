"""Whose project a run works on: the demo, or a user's own Jira and GitHub.

Everyone can run tickets on the demo project (the repo and Jira board in settings).
A user who connects their own Jira (site, email, API token, project key) and GitHub
(a token and one repo) also gets their own project: its runs use their tokens, and
only they can see them.

users -> integrations (one Jira, one GitHub; tokens encrypted)
users -> projects (their own project is the one whose repo their GitHub points at)
"""

from dataclasses import dataclass

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from api.config import Settings
from db.models import Integration, IntegrationKind, Project, ProjectKind, User
from services.secret_box import SecretBox
from services.workspace import github_remote


@dataclass(frozen=True)
class Credentials:
    """What a run needs to reach a project's Jira and GitHub."""

    jira_site: str
    jira_email: str
    jira_token: str
    jira_project_key: str  # e.g. KAN: runs only take this project's tickets
    repo: str  # owner/name
    github_token: str


class NotReadyError(Exception):
    """The project can't run: its owner hasn't connected (or has disconnected) Jira or GitHub."""


def ensure_user(factory: sessionmaker[Session], auth_user_id: str, email: str) -> int:
    """Our users row for a website login, made on their first call; return its id.

    A row with the same email but another login id belonged to a deleted website
    account (Better Auth emails are unique): the new login takes it over, without the
    old account's connections. A page's first calls arrive together, so when another
    request made the row first, read theirs.
    """
    try:
        return _ensure_user(factory, auth_user_id, email)
    except IntegrityError:
        return _ensure_user(factory, auth_user_id, email)


def _ensure_user(factory: sessionmaker[Session], auth_user_id: str, email: str) -> int:
    with factory.begin() as session:
        user = session.scalar(select(User).where(User.auth_user_id == auth_user_id))
        if user is not None:
            return user.id
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, auth_user_id=auth_user_id)
            session.add(user)
            session.flush()
            return user.id
        if user.auth_user_id is not None:
            session.execute(delete(Integration).where(Integration.user_id == user.id))
        user.auth_user_id = auth_user_id
        return user.id


def demo_project_id(session: Session, settings: Settings) -> int | None:
    """The demo project (made by the worker's first run), or None before then."""
    if not (settings.agent_repo and settings.agent_owner_email):
        return None
    return session.scalar(
        select(Project.id)
        .join(User, Project.user_id == User.id)
        .where(
            User.email == settings.agent_owner_email,
            Project.code_repo_url == github_remote(settings.agent_repo),
        )
    )


def integrations(session: Session, user_id: int) -> dict[IntegrationKind, Integration]:
    rows = session.scalars(select(Integration).where(Integration.user_id == user_id))
    return {row.kind: row for row in rows}


def own_project(session: Session, user_id: int) -> Project | None:
    """The project the user's GitHub points at, if they have connected one."""
    github = integrations(session, user_id).get(IntegrationKind.GITHUB)
    if github is None:
        return None
    return session.scalar(
        select(Project).where(
            Project.user_id == user_id, Project.code_repo_url == github_remote(github.scope)
        )
    )


def visible_project_ids(session: Session, settings: Settings, user_id: int) -> list[int]:
    """Projects whose runs this user may see: the demo, and every project of their own
    (also ones whose GitHub they have since disconnected: the history is theirs)."""
    demo = demo_project_id(session, settings)
    rows = session.scalars(
        select(Project.id).where(or_(Project.user_id == user_id, Project.id == demo))
    )
    return list(rows)


def connect(
    factory: sessionmaker[Session],
    user_id: int,
    kind: IntegrationKind,
    *,
    account: str,
    site: str | None,
    scope: str,
    sealed_token: bytes,
) -> None:
    """Save (or replace) the user's Jira or GitHub, then bring their project up to date."""
    with factory.begin() as session:
        row = integrations(session, user_id).get(kind)
        if row is None:
            row = Integration(user_id=user_id, kind=kind)
            session.add(row)
        row.account, row.site, row.scope, row.secret = account, site, scope, sealed_token
        session.flush()
        _sync_project(session, user_id)


def disconnect(factory: sessionmaker[Session], user_id: int, kind: IntegrationKind) -> bool:
    """Delete the user's Jira or GitHub (and so its token). False if none was connected.
    Their project and its run history stay; it can't run again until they reconnect."""
    with factory.begin() as session:
        project = own_project(session, user_id)
        row = integrations(session, user_id).get(kind)
        if row is None:
            return False
        session.delete(row)
        if kind == IntegrationKind.JIRA and project is not None:
            project.jira_site = project.jira_project_key = None
        return True


def credentials(factory: sessionmaker[Session], project_id: int, box: SecretBox) -> Credentials:
    """A user project's tokens (decrypted), for a run.
    NotReadyError if its owner's Jira or GitHub is missing, or now points elsewhere."""
    with factory() as session:
        project = session.get(Project, project_id)
        if project is None:
            raise NotReadyError(f"no project {project_id}")
        found = integrations(session, project.user_id)
        jira, github = found.get(IntegrationKind.JIRA), found.get(IntegrationKind.GITHUB)
        if jira is None or github is None or jira.site is None:
            raise NotReadyError("connect both Jira and GitHub first")
        if project.code_repo_url != github_remote(github.scope):
            raise NotReadyError("your GitHub now points at another repo")
        return Credentials(
            jira_site=jira.site,
            jira_email=jira.account,
            jira_token=box.open(jira.secret),
            jira_project_key=jira.scope,
            repo=github.scope,
            github_token=box.open(github.secret),
        )


def _sync_project(session: Session, user_id: int) -> None:
    """Make the project the user's GitHub points at, and point it at their Jira."""
    found = integrations(session, user_id)
    github, jira = found.get(IntegrationKind.GITHUB), found.get(IntegrationKind.JIRA)
    if github is None:
        return
    project = own_project(session, user_id)
    if project is None:
        project = Project(
            user_id=user_id,
            name=github.scope.split("/")[1],
            kind=ProjectKind.EXISTING,
            code_repo_url=github_remote(github.scope),
            status="active",
        )
        session.add(project)
    project.jira_site = jira.site if jira else None
    project.jira_project_key = jira.scope if jira else None
