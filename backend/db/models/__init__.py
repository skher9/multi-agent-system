"""Import every model here so Base.metadata knows all tables (Alembic reads it)."""

from db.models.discovery import ChatMessage, DiscoverySession, Lens, Question
from db.models.projects import Document, Project, ProjectKind, User
from db.models.work import Approval, ApprovalKind, Feature, Task

__all__ = [
    "Approval",
    "ApprovalKind",
    "ChatMessage",
    "DiscoverySession",
    "Document",
    "Feature",
    "Lens",
    "Project",
    "ProjectKind",
    "Question",
    "Task",
    "User",
]
