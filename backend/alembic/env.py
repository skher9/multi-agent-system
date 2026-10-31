"""Alembic runtime: which database to migrate, and what the schema should look like.

Every command must name its target, so main is never migrated by accident:

    uv run alembic -x target=test upgrade head   # Neon test branch (DATABASE_URL_TEST)
    uv run alembic -x target=main upgrade head   # Neon main branch (DATABASE_URL), after review
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

import db.models  # noqa: F401  (registers every table on Base.metadata)
from alembic import context
from api.config import get_settings
from db.base import Base
from orchestrator.checkpoints import CHECKPOINT_TABLES

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogenerate compares the live database against this.
target_metadata = Base.metadata

TARGETS = ("test", "main")


def database_url() -> str:
    target = context.get_x_argument(as_dictionary=True).get("target")
    if target not in TARGETS:
        raise SystemExit("Pass the database explicitly: alembic -x target=test|main <command>")

    settings = get_settings()
    secret = settings.database_url_test if target == "test" else settings.database_url
    if secret is None:
        name = "DATABASE_URL_TEST" if target == "test" else "DATABASE_URL"
        raise SystemExit(f"{name} is not set in backend/.env")
    return secret.get_secret_value()


def include_name(name: str | None, type_: str, parent_names: object) -> bool:
    """Leave LangGraph's checkpoint tables alone: LangGraph creates and migrates them,
    so autogenerate must not offer to drop them as "unknown" tables."""
    return not (type_ == "table" and name in CHECKPOINT_TABLES)


def run_migrations_offline() -> None:
    """Print the SQL instead of running it (alembic ... upgrade head --sql)."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # NullPool: one short-lived connection for the migration, no pool left behind.
    engine = create_engine(
        database_url(), poolclass=pool.NullPool, connect_args={"prepare_threshold": None}
    )
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # also detect column type changes, not just new columns
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
