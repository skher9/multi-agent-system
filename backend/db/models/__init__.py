"""Import every model here so Base.metadata knows all tables (Alembic reads it)."""

from db.models.discovery import ChatMessage, DiscoverySession, Lens, Question
from db.models.projects import Document, Project, ProjectKind, User

__all__ = [
    "ChatMessage",
    "DiscoverySession",
    "Document",
    "Lens",
    "Project",
    "ProjectKind",
    "Question",
    "User",
]
