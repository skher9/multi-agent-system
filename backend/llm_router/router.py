"""complete(): the single doorway every agent uses to call a model.

It refuses calls once the story's budget is used, picks the model for the role,
retries failures that are worth retrying, times the call, converts OpenRouter's
USD cost to ₹, and records one llm_calls row.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from llm_router.budget import (
    AGENT_BUDGETS_INR,
    STRONG_BUDGET_MULTIPLIER,
    AgentBudgetExceededError,
    AgentSpendLookup,
    BudgetExceededError,
    DailyBudgetExceededError,
    DailySpendLookup,
    SpendLookup,
)
from llm_router.models import FIXED_MODEL, REASONING_EFFORT, Role, model_for
from services.openrouter import ChatResponse, OpenRouterClient, OpenRouterError

logger = logging.getLogger(__name__)

# Waits before each retry. About 40s in total: enough to ride out a provider blip
# (seen live: OpenRouter 502 "upstream error" for a few seconds) without hanging a run.
RETRY_WAITS_SECONDS = (1, 2, 5, 10, 20)

# llm_calls.cost_inr is Numeric(12, 4)
PAISA_PRECISION = Decimal("0.0001")


@dataclass(frozen=True)
class CallRecord:
    """One successful model call, ready to save. Field names match the llm_calls table."""

    agent_run_id: int
    model: str
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    cost_inr: Decimal
    latency_ms: int


Recorder = Callable[[CallRecord], None]


class LlmRouter:
    def __init__(
        self,
        client: OpenRouterClient,
        record: Recorder,
        usd_to_inr: Decimal,
        story_spend: SpendLookup,
        story_budget_inr: Decimal,
        sleep: Callable[[float], None] = time.sleep,  # tests pass a no-op
        daily_spend: DailySpendLookup | None = None,
        daily_budget_inr: Decimal | None = None,
        agent_spend: AgentSpendLookup | None = None,
        model_override: str | None = None,
        routing: bool = True,
    ) -> None:
        """model_override: one model for every role (escalation keeps its own), for
        comparing models on the benchmark without touching models.py."""
        self._client = client
        self._record = record
        self._usd_to_inr = usd_to_inr
        self._story_spend = story_spend
        self._story_budget_inr = story_budget_inr
        self._sleep = sleep
        self._daily_spend = daily_spend
        self._daily_budget_inr = daily_budget_inr
        self._agent_spend = agent_spend
        self._model_override = model_override
        self._routing = routing  # False: ignore routing's strong model (benchmark baseline)

    def complete(
        self,
        *,
        role: Role,
        messages: list[dict[str, Any]],
        agent_run_id: int,
        escalate: bool = False,
        strong: bool = False,
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        # Checked before each call, so the call that crosses the budget finishes
        # and the next one is refused.
        if self._daily_spend is not None and self._daily_budget_inr is not None:
            today = self._daily_spend()
            if today >= self._daily_budget_inr:
                raise DailyBudgetExceededError(today, self._daily_budget_inr)
        spent = self._story_spend(agent_run_id)
        if spent >= self._story_budget_inr:
            raise BudgetExceededError(spent, self._story_budget_inr)
        strong = strong and self._routing
        cap = AGENT_BUDGETS_INR.get(str(role))
        if cap is not None and strong:
            cap *= STRONG_BUDGET_MULTIPLIER
        if self._agent_spend is not None and cap is not None and not escalate:
            mine = self._agent_spend(agent_run_id)
            if mine >= cap:
                raise AgentBudgetExceededError(str(role), mine, cap)

        model = model_for(role, escalate=escalate, strong=strong)
        if self._model_override and not escalate and not strong and role not in FIXED_MODEL:
            model = self._model_override
        attempt = 0
        while True:
            started = time.perf_counter()
            try:
                response = self._client.chat(
                    model,
                    messages,
                    tools=tools,
                    response_format=response_format,
                    session_id=f"agent-run-{agent_run_id}",
                    max_tokens=max_tokens,
                    reasoning_effort=None if escalate else REASONING_EFFORT.get(role),
                )
                break
            except OpenRouterError as exc:
                if not exc.retryable or attempt == len(RETRY_WAITS_SECONDS):
                    raise
                wait = RETRY_WAITS_SECONDS[attempt]
                logger.warning("%s; retrying %s in %ss", exc, model, wait)
                self._sleep(wait)
                attempt += 1
        latency_ms = round((time.perf_counter() - started) * 1000)

        usage = response.usage
        self._record(
            CallRecord(
                agent_run_id=agent_run_id,
                model=response.model,  # what actually answered (and was billed)
                input_tokens=usage.prompt_tokens,
                cached_tokens=usage.cached_tokens,
                output_tokens=usage.completion_tokens,
                cost_inr=(usage.cost_usd * self._usd_to_inr).quantize(
                    PAISA_PRECISION, rounding=ROUND_HALF_UP
                ),
                latency_ms=latency_ms,
            )
        )
        return response
