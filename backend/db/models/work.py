"""The work itself: projects -> features -> tasks, plus human approvals.

A task is one unit of agent work (one role, one job). Tasks can wait on other tasks.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin, TimestampMixin, text_enum


class ApprovalKind(StrEnum):
    """The two human checkpoints in the v1 pipeline."""

    REQUIREMENTS = "requirements"
    MERGE = "merge"


class Feature(IdMixin, TimestampMixin, Base):
    """One story. In v1 a story is one Jira ticket, so its budget and runs add up per ticket."""

    __tablename__ = "features"
    # One feature per ticket per project. Postgres allows many NULLs, so features
    # that don't come from Jira are unaffected.
    __table_args__ = (
        UniqueConstraint("project_id", "jira_key", name="uq_features_project_id_jira_key"),
    )

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32))
    spec_path: Mapped[str | None] = mapped_column(Text)  # where the spec lives in the context repo
    jira_key: Mapped[str | None] = mapped_column(String(32))  # e.g. KAN-4


class Task(IdMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    feature_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("features.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32))  # which agent does it, e.g. developer
    status: Mapped[str] = mapped_column(String(32))
    # IDs of tasks that must finish first. A plain array is enough for v1;
    # Postgres can't enforce foreign keys inside an array, so code must check them.
    depends_on: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), server_default="{}")
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    # The agent's structured handoff (validated by Pydantic before it is saved)
    handoff: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Approval(IdMixin, TimestampMixin, Base):
    __tablename__ = "approvals"

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[ApprovalKind] = mapped_column(text_enum(ApprovalKind, "approval_kind"))
    status: Mapped[str] = mapped_column(String(32))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
