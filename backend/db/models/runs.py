"""Observability: what each agent did and what every model call cost.

tasks -> agent_runs -> llm_calls

The LLM router writes one llm_calls row per call. Cost per story, per agent, or per
model is then a SQL query, which is how the ₹50 budget guard and the M4 cost
dashboard will work.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String
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
