"""Model routing: which agents get the stronger model, decided in code from the work
itself, so nobody has to know what a model is.

Every agent starts on the standard model (fast, cheap: DeepSeek V4.1 Flash). The planner
moves to the strong one (DeepSeek V4 Pro) when the work is big or risky, because a wrong
plan costs more than the extra tokens. The reviewer always uses the strong one: it is
the last check before a human, and a missed bug costs the most. The developer
does many small steps, so it stays standard unless it gets into trouble; the agent loop
switches any agent up mid-turn on trouble (rejected answers, a stuck loop).

Rules, not a model call: free, predictable, and every choice comes with its reason,
shown in the run window.
"""

import re

from agents.planner import Plan
from agents.ticket_reader import TicketSpec

# Big tickets: many criteria or requirements mean many moving parts to plan
BIG_TICKET = 6
# Big changes: many files, or backend and frontend that must agree on a contract
BIG_CHANGE = 6
# Paths where a mistake is expensive: logins, money, data, server boundaries
RISKY_PATH = re.compile(r"auth|login|session|security|payment|billing|migrat|/api/|middleware")


def planner_tier(spec: TicketSpec) -> str | None:
    """Why the planner needs the strong model, or None for the standard one."""
    if len(spec.acceptance_criteria) >= BIG_TICKET:
        return f"{len(spec.acceptance_criteria)} acceptance criteria"
    if len(spec.requirements) >= BIG_TICKET:
        return f"{len(spec.requirements)} requirements"
    return None


def reviewer_tier(plan: Plan, review_round: int) -> str:
    """Why the reviewer gets the strong model: always, with the most specific reason."""
    if review_round >= 2:
        return "second review round: the first fix didn't settle it"
    if len(plan.changes) >= BIG_CHANGE:
        return f"{len(plan.changes)} files change"
    areas = {s.area for s in plan.subtasks}
    if {"BE", "FE"} <= areas:
        return "backend and frontend change together"
    risky = [c.path for c in plan.changes if RISKY_PATH.search(c.path)]
    if risky:
        return f"risky code: {risky[0]}"
    # Every review, not only the big ones: on the benchmark the standard model approved
    # a change that didn't build. The review is the last look before a human's.
    return "every review gets the stronger model"
