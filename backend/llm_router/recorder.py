"""Where call records go. The router takes any Recorder, so tests can skip the database."""

from dataclasses import asdict

from sqlalchemy.orm import Session, sessionmaker

from db.models import LlmCall
from llm_router.router import CallRecord, Recorder


def db_recorder(session_factory: sessionmaker[Session]) -> Recorder:
    """Save each call as one llm_calls row, committed right away.

    Committing per call means the cost is saved even if the agent crashes a moment later.
    """

    def record(call: CallRecord) -> None:
        with session_factory.begin() as session:
            session.add(LlmCall(**asdict(call)))

    return record
