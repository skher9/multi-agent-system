"""Who owns what: users -> projects -> documents.

Every other table reaches user_id through a project, so one user can never see
another's data once the app opens to more users.
"""

from enum import StrEnum

from sqlalchemy import BigInteger, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin, TimestampMixin


class ProjectKind(StrEnum):
    NEW = "new"
    EXISTING = "existing"


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True)


class Project(IdMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    # ondelete=CASCADE: deleting a user deletes their projects (and everything below).
    # index=True: Postgres does not index foreign keys automatically.
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    # Stored as text plus a CHECK constraint (not a Postgres ENUM type),
    # so adding a value later is a simple migration.
    kind: Mapped[ProjectKind] = mapped_column(
        Enum(
            ProjectKind,
            name="project_kind",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    code_repo_url: Mapped[str | None] = mapped_column(Text)
    context_repo_url: Mapped[str | None] = mapped_column(Text)
    # Allowed values are defined when the orchestrator is built (M1).
    status: Mapped[str] = mapped_column(String(32))


class Document(IdMixin, TimestampMixin, Base):
    """An uploaded PRD. The file lives in R2; Postgres keeps only its key."""

    __tablename__ = "documents"

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    r2_key: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(default=1)
