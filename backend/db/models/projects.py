"""Who owns what: users -> projects -> documents.

Every other table reaches user_id through a project, so one user can never see
another's data once the app opens to more users.
"""

from enum import StrEnum

from sqlalchemy import BigInteger, ForeignKey, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin, TimestampMixin, text_enum


class ProjectKind(StrEnum):
    NEW = "new"
    EXISTING = "existing"


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True)
    # The Better Auth user (website login) this is; set on their first API call
    auth_user_id: Mapped[str | None] = mapped_column(String(64), unique=True)


class Project(IdMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    # ondelete=CASCADE: deleting a user deletes their projects (and everything below).
    # index=True: Postgres does not index foreign keys automatically.
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[ProjectKind] = mapped_column(text_enum(ProjectKind, "project_kind"))
    code_repo_url: Mapped[str | None] = mapped_column(Text)
    context_repo_url: Mapped[str | None] = mapped_column(Text)
    # Where its tickets live, e.g. https://acme.atlassian.net and KAN
    jira_site: Mapped[str | None] = mapped_column(String(200))
    jira_project_key: Mapped[str | None] = mapped_column(String(32))
    # Allowed values are defined when the orchestrator is built (M1).
    status: Mapped[str] = mapped_column(String(32))


class IntegrationKind(StrEnum):
    JIRA = "jira"
    GITHUB = "github"


class Integration(IdMixin, TimestampMixin, Base):
    """A user's own Jira or GitHub, so agents can work on their project.

    The token is encrypted (services/secret_box.py) and never leaves the backend: the
    API answers with everything else. Disconnecting deletes the row.
    """

    __tablename__ = "integrations"
    # One Jira and one GitHub per user. Also serves as the user_id index.
    __table_args__ = (UniqueConstraint("user_id", "kind", name="uq_integrations_user_id_kind"),)

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[IntegrationKind] = mapped_column(text_enum(IntegrationKind, "integration_kind"))
    # Who it signs in as: the Jira email, or the GitHub username
    account: Mapped[str] = mapped_column(String(320))
    site: Mapped[str | None] = mapped_column(String(200))  # Jira: https://acme.atlassian.net
    # What agents work on: the Jira project key (KAN), or the repo (owner/name)
    scope: Mapped[str] = mapped_column(String(200))
    secret: Mapped[bytes] = mapped_column(LargeBinary)  # the encrypted token


class Document(IdMixin, TimestampMixin, Base):
    """An uploaded PRD. The file lives in R2; Postgres keeps only its key."""

    __tablename__ = "documents"

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    r2_key: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(default=1)


class CodeGraph(IdMixin, TimestampMixin, Base):
    """A Graphify map of a project's code at one commit. The files live in R2.

    Built once per repo, then updated for each new commit (only changed files are
    re-read), so later tickets start from a map instead of exploring the code.
    """

    __tablename__ = "code_graphs"
    # One graph per commit. Also serves as the project_id index (leading column).
    __table_args__ = (
        UniqueConstraint("project_id", "commit_sha", name="uq_code_graphs_project_id_commit_sha"),
    )

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE")
    )
    commit_sha: Mapped[str] = mapped_column(String(40))  # full git SHA-1
    r2_key: Mapped[str] = mapped_column(Text)  # zipped graphify-out folder
    graphify_version: Mapped[str] = mapped_column(String(32))  # rebuild if this changes


class RepoRule(IdMixin, TimestampMixin, Base):
    """A lesson from a human's review of an agent PR on this project, e.g. "Use the
    shared Button, never a plain <button>". The planner, developer and reviewer read
    them on every later ticket, so the same comment never has to be made twice.
    """

    __tablename__ = "repo_rules"
    # The same lesson once per project. Also serves as the project_id index.
    __table_args__ = (UniqueConstraint("project_id", "rule", name="uq_repo_rules_project_id_rule"),)

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE")
    )
    rule: Mapped[str] = mapped_column(String(300))
    why: Mapped[str] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(200))  # where it was learned, e.g. a PR link
