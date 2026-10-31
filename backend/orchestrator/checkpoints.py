"""LangGraph checkpoints in Postgres: the run's state, saved after every node.

If a run crashes, the next run of the same ticket loads the last checkpoint and
continues from the node that didn't finish, instead of starting (and paying) again.

LangGraph manages its own tables (below), not Alembic; alembic/env.py ignores them.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from psycopg.rows import DictRow, dict_row

CHECKPOINT_TABLES = frozenset(
    {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}
)


@contextmanager
def postgres_checkpointer(database_url: str) -> Iterator[PostgresSaver]:
    """Open a checkpointer on the given database, creating its tables the first time."""
    # The settings URL carries SQLAlchemy's driver prefix; psycopg wants plain postgresql://
    url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    # autocommit and dict_row: required by PostgresSaver (autocommit also lets its
    # CREATE INDEX CONCURRENTLY run). prepare_threshold=None: no prepared statements
    # behind Neon's PgBouncer, as in db/session.py.
    with Connection[DictRow].connect(
        url, autocommit=True, row_factory=dict_row, prepare_threshold=None
    ) as conn:
        saver = PostgresSaver(conn)
        saver.setup()  # creates or migrates its tables; safe to run every time
        yield saver
