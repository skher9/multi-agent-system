"""Observability: what each agent did and what every model call cost.

tasks -> agent_runs -> llm_calls
features -> run_events (the run's timeline: boxes, tool calls, the outcome)

The LLM router writes one llm_calls row per call. Cost per story, per agent, or per
model is then a SQL query, which is how the ₹50 budget guard and the M4 cost
dashboard will work.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IdMixin, TimestampMixin


class AgentRun(IdMixin, TimestampMixin, Base):
    """One agent working one task. A retried task gets a new run."""

    __tablename__ = "agent_runs"

    task_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(100))  # pinned model version, e.g. from router config
    status: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LlmCall(IdMixin, TimestampMixin, Base):
    __tablename__ = "llm_calls"

    agent_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int]
    # Part of input_tokens served from the prompt cache (much cheaper).
    # Tracking it shows whether the stable-prefix prompt design is working.
    cached_tokens: Mapped[int] = mapped_column(default=0, server_default="0")
    output_tokens: Mapped[int]
    # Money is never a float: 0.1 + 0.2 != 0.3 in floating point.
    # Numeric(12, 4) holds up to ₹99,999,999.9999 exactly.
    cost_inr: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    latency_ms: Mapped[int]


class EventKind(StrEnum):
    """What a run_events row is about. Stored as plain text (not a database enum), so a
    new kind needs no migration."""

    RUN_STARTED = "run_started"  # data: resumed (continuing a crashed run)
    NODE_STARTED = "node_started"  # data: node
    NODE_FINISHED = "node_finished"  # data: node
    TOOL_CALL = "tool_call"  # data: role, tool, n, limit, arguments (shortened)
    FINISH_REJECTED = "finish_rejected"  # data: role, error (shortened)
    AGENT_FINISHED = "agent_finished"  # data: role, tool_calls
    RUN_ENDED = "run_ended"  # data: outcome
    RUN_FAILED = "run_failed"  # data: error (the exception's type)


class RunEvent(IdMixin, TimestampMixin, Base):
    """One thing that happened in a run, in order: a box started or finished, an agent
    called a tool, a finish was rejected, the run ended. The website reads these to show
    a run live and to replay it afterwards.
    """

    __tablename__ = "run_events"
    # The timeline of one feature, oldest first: WHERE feature_id = ? ORDER BY id
    __table_args__ = (Index("ix_run_events_feature_id_id", "feature_id", "id"),)

    feature_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("features.id", ondelete="CASCADE")
    )
    # Set for events inside an agent's turn (tool calls); empty for the run's own events
    agent_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32))  # an EventKind
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
