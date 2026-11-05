"""Budget guards, checked before every model call.

- Story: a story run stops once its model calls have cost the budget (₹50 by default).
  A story is one feature, so every task under it (developer, reviewer, fixes) shares it.
- Daily: all runs together stop once the last 24 hours cost the daily budget. Not shown
  to visitors; it keeps a public demo from running up the bill.
"""

from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from db.models import AgentRun, LlmCall, Task

# Given an agent run, return ₹ already spent on its whole story.
SpendLookup = Callable[[int], Decimal]
# ₹ spent by every run in the last 24 hours.
DailySpendLookup = Callable[[], Decimal]


class BudgetExceededError(Exception):
    def __init__(self, spent_inr: Decimal, budget_inr: Decimal) -> None:
        super().__init__(f"story budget used: ₹{spent_inr} of ₹{budget_inr}")
        self.spent_inr = spent_inr
        self.budget_inr = budget_inr


class DailyBudgetExceededError(BudgetExceededError):
    def __init__(self, spent_inr: Decimal, budget_inr: Decimal) -> None:
        super().__init__(spent_inr, budget_inr)
        self.args = (f"daily budget used: ₹{spent_inr} of ₹{budget_inr} in 24 hours",)


def db_story_spend(session_factory: sessionmaker[Session]) -> SpendLookup:
    def spent(agent_run_id: int) -> Decimal:
        # The feature this run belongs to: agent_run -> task -> feature_id
        feature_id = (
            select(Task.feature_id)
            .join(AgentRun, AgentRun.task_id == Task.id)
            .where(AgentRun.id == agent_run_id)
            .scalar_subquery()
        )
        # Sum every call made by any run of any task in that feature
        total = (
            select(func.coalesce(func.sum(LlmCall.cost_inr), 0))
            .join(AgentRun, LlmCall.agent_run_id == AgentRun.id)
            .join(Task, AgentRun.task_id == Task.id)
            .where(Task.feature_id == feature_id)
        )
        with session_factory() as session:
            return Decimal(session.scalar(total) or 0)

    return spent


def db_daily_spend(session_factory: sessionmaker[Session]) -> DailySpendLookup:
    def spent() -> Decimal:
        since = func.now() - timedelta(hours=24)  # the database's clock, like created_at
        total = select(func.coalesce(func.sum(LlmCall.cost_inr), 0)).where(
            LlmCall.created_at >= since
        )
        with session_factory() as session:
            return Decimal(session.scalar(total) or 0)

    return spent
