"""Which model each agent role uses.

This is the only place model IDs live, so changing a model is a one-line edit.
Docs rule: a new model must pass the eval set before it goes in here.
IDs and prices checked live on OpenRouter on 2026-10-29.
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
    # Was deepseek/deepseek-v4.1-flash, but the live smoke test (2026-10-29) showed it
    # cost about the same as MiniMax per call with no cache hits, so one model is simpler.
    Role.TICKET_READER: "minimax/minimax-m3",
    Role.PLANNER: "minimax/minimax-m3",
    Role.DEVELOPER: "minimax/minimax-m3",
    Role.REVIEWER: "minimax/minimax-m3",
    Role.FIXER: "minimax/minimax-m3",
    Role.QA: "minimax/minimax-m3",
    Role.LEARNER: "minimax/minimax-m3",
}

# Used only when a task has failed twice (System Design doc), for any role.
ESCALATION_MODEL = "z-ai/glm-5.2"


def model_for(role: Role, *, escalate: bool = False) -> str:
    return ESCALATION_MODEL if escalate else MODELS[role]
