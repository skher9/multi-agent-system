"""Which model each agent role uses.

This is the only place model IDs live, so changing a model is a one-line edit.
Docs rule: a new model must pass the eval set before it goes in here.
IDs and prices checked live on OpenRouter on 2026-10-29.
"""

from enum import StrEnum


class Role(StrEnum):
    """Agent roles in the v1 pipeline: Jira ticket -> developer -> reviewer."""

    TICKET_READER = "ticket_reader"  # no tools: turns a ticket into validated JSON
    DEVELOPER = "developer"
    REVIEWER = "reviewer"


MODELS: dict[Role, str] = {
    # Cheap and fast; reading a ticket needs no strong reasoning.
    # Undated ID chosen over "deepseek-v4.1-flash-1017", which costs ~3x more per output token.
    Role.TICKET_READER: "deepseek/deepseek-v4.1-flash",
    Role.DEVELOPER: "minimax/minimax-m3",
    Role.REVIEWER: "minimax/minimax-m3",
}

# Used only when a task has failed twice (System Design doc), for any role.
ESCALATION_MODEL = "z-ai/glm-5.2"


def model_for(role: Role, *, escalate: bool = False) -> str:
    return ESCALATION_MODEL if escalate else MODELS[role]
