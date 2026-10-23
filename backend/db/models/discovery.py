"""Discovery: the team asks questions about a PRD before building anything.

documents -> discovery_sessions -> questions (the question ledger)
                                -> chat_messages
"""

from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin, TimestampMixin, text_enum


class Lens(StrEnum):
    """Which point of view raised the question."""

    PM = "pm"
    DEVELOPER = "developer"
    QA = "qa"


class DiscoverySession(IdMixin, TimestampMixin, Base):
    """One review of one document version."""

    __tablename__ = "discovery_sessions"

    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(32))


class Question(IdMixin, TimestampMixin, Base):
    """One entry in the question ledger: asked once, answered once, never lost."""

    __tablename__ = "questions"

    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("discovery_sessions.id", ondelete="CASCADE"), index=True
    )
    lens: Mapped[Lens] = mapped_column(text_enum(Lens, "lens"))
    doc_section: Mapped[str | None] = mapped_column(Text)  # where in the PRD it came from
    text: Mapped[str] = mapped_column(Text)
    # Suggested answers the customer can pick from, e.g. ["Email", "Google login"]
    options: Mapped[list[Any] | None] = mapped_column(JSONB)
    priority: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32))
    answer: Mapped[str | None] = mapped_column(Text)
    answered_via: Mapped[str | None] = mapped_column(String(16))  # e.g. sheet or chat


class ChatMessage(IdMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"

    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("discovery_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # customer or agent
    content: Mapped[str] = mapped_column(Text)
