"""Import every model here so Base.metadata knows all tables (Alembic reads it)."""

from db.models.discovery import ChatMessage, DiscoverySession, Lens, Question
from db.models.projects import (
    CodeGraph,
    Document,
    Integration,
    IntegrationKind,
    Project,
    ProjectKind,
    RepoRule,
    User,
)
from db.models.runs import AgentRun, EventKind, LlmCall, RunEvent
from db.models.work import Approval, ApprovalKind, Feature, Task

__all__ = [
    "AgentRun",
    "Approval",
    "ApprovalKind",
    "ChatMessage",
    "CodeGraph",
    "DiscoverySession",
    "Document",
    "EventKind",
    "Feature",
    "Integration",
    "IntegrationKind",
    "Lens",
    "LlmCall",
    "Project",
    "ProjectKind",
    "Question",
    "RepoRule",
    "RunEvent",
    "Task",
    "User",
]
