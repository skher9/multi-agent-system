"""Import every model here so Base.metadata knows all tables (Alembic reads it)."""

from db.models.discovery import ChatMessage, DiscoverySession, Lens, Question
from db.models.projects import CodeGraph, Document, Project, ProjectKind, User
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
    "Lens",
    "LlmCall",
    "Project",
    "ProjectKind",
    "Question",
    "RunEvent",
    "Task",
    "User",
]
