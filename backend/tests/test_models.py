"""Schema tests: build every table from the models (no database needed)."""

from sqlalchemy import create_mock_engine
from sqlalchemy.schema import CreateTable

import db.models  # noqa: F401  (registers all tables on Base.metadata)
from db.base import Base


def ddl(table_name: str) -> str:
    engine = create_mock_engine("postgresql+psycopg://", executor=lambda *a, **k: None)
    return str(CreateTable(Base.metadata.tables[table_name]).compile(dialect=engine.dialect))


def reaches_users(table_name: str, seen: frozenset[str] = frozenset()) -> bool:
    """Follow required (NOT NULL) foreign keys upward until we hit users."""
    if table_name == "users":
        return True
    table = Base.metadata.tables[table_name]
    for fk in table.foreign_keys:
        parent = fk.column.table.name
        if not fk.parent.nullable and parent not in seen:
            if reaches_users(parent, seen | {table_name}):
                return True
    return False


def test_every_table_reaches_a_user() -> None:
    """The multi-user rule: every row belongs to exactly one user, via a chain of parents."""
    for name in Base.metadata.tables:
        assert reaches_users(name), f"{name} has no required path to users"


def test_project_kind_is_text_with_check_constraint() -> None:
    sql = ddl("projects")
    assert "kind VARCHAR(8) NOT NULL" in sql
    assert "CONSTRAINT ck_projects_project_kind CHECK (kind IN ('new', 'existing'))" in sql


def test_all_eleven_v1_tables_exist() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "projects",
        "documents",
        "discovery_sessions",
        "questions",
        "chat_messages",
        "features",
        "tasks",
        "approvals",
        "agent_runs",
        "llm_calls",
    }


def test_cost_is_exact_decimal_not_float() -> None:
    assert "cost_inr NUMERIC(12, 4) NOT NULL" in ddl("llm_calls")
