"""Which model each agent role uses.

This is the only place model IDs live, so changing a model is a one-line edit.
Docs rule: a new model must pass the eval set before it goes in here.
IDs and prices checked live on OpenRouter on 2026-11-06.
"""

from enum import StrEnum


class Role(StrEnum):
    """Agent roles in the v1 pipeline: Jira ticket -> planner -> developer -> reviewer."""

    TICKET_READER = "ticket_reader"  # no tools: turns a ticket into validated JSON
    PLANNER = "planner"  # read-only tools: understands the code, plans the changes
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    FIXER = "fixer"  # a fresh developer that fixes what the gate found, nothing else
    QA = "qa"  # writes and runs browser tests per acceptance criterion
    LEARNER = "learner"  # turns human review comments into rules for the repo


MODELS: dict[Role, str] = {
    # DeepSeek V4.1 Flash for every role (2026-11-06): on the benchmark (backend/
    # experiments, round ds-deepseek-v4.1-flash) it passed every ticket at about a fifth
    # of MiniMax M3's cost and half the steps, with clean code. A role moves to a
    # stronger DeepSeek model only if the benchmark shows better quality for it.
    Role.TICKET_READER: "deepseek/deepseek-v4.1-flash",
    Role.PLANNER: "deepseek/deepseek-v4.1-flash",
    Role.DEVELOPER: "deepseek/deepseek-v4.1-flash",
    Role.REVIEWER: "deepseek/deepseek-v4.1-flash",
    Role.FIXER: "deepseek/deepseek-v4.1-flash",
    Role.QA: "deepseek/deepseek-v4.1-flash",
    Role.LEARNER: "deepseek/deepseek-v4.1-flash",
}

# Used only when a task has failed twice (System Design doc), for any role.
# How long each role thinks per call. Reasoning is billed as output, ~40% of the cost in
# the benchmark. DeepSeek ignores a reasoning token cap but honours effort: "low" cut a
# planning answer's reasoning from 5,893 to 1,914 tokens with an equally complete
# answer. Judgment-heavy roles keep "medium". The escalation model uses its default.
REASONING_EFFORT: dict[Role, str] = {
    Role.TICKET_READER: "low",
    Role.PLANNER: "medium",
    Role.DEVELOPER: "low",
    Role.REVIEWER: "medium",
    Role.FIXER: "low",
    Role.QA: "low",
    Role.LEARNER: "low",
}

# The strongest DeepSeek model: when a task failed twice, and for ask_senior
ESCALATION_MODEL = "deepseek/deepseek-v4-pro"


# Routing (orchestrator/routing.py) moves big or risky work to the strong model
STRONG_MODEL = ESCALATION_MODEL


def model_for(role: Role, *, escalate: bool = False, strong: bool = False) -> str:
    if escalate:
        return ESCALATION_MODEL
    return STRONG_MODEL if strong else MODELS[role]
