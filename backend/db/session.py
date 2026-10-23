"""Database engine and sessions.

The engine is the connection pool; a session is one unit of work on top of it.
"""

from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


@lru_cache
def get_engine(database_url: str) -> Engine:
    """One engine (connection pool) per database URL, created on first use."""
    return create_engine(
        database_url,
        pool_pre_ping=True,  # test a pooled connection before use; Neon closes idle ones
        connect_args={
            # Neon's pooled endpoint runs PgBouncer. Server-side prepared statements
            # can break behind it, so psycopg must not create them.
            "prepare_threshold": None,
        },
    )


def make_session_factory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(database_url), expire_on_commit=False)


def ping(database_url: str) -> None:
    """Raise if the database can't run a trivial query."""
    with get_engine(database_url).connect() as conn:
        conn.execute(text("SELECT 1"))
