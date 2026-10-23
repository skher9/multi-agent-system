"""Import every model here so Base.metadata knows all tables (Alembic reads it)."""

from db.models.projects import Document, Project, ProjectKind, User

__all__ = ["Document", "Project", "ProjectKind", "User"]
