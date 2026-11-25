"""Free runs: every account may start a few runs (settings.free_runs); the owner has no
limit. The count lives on the user's row and changes in one UPDATE, so two clicks at
once can't both take the last run.

Counted, not a balance: changing free_runs changes everyone's allowance at once.
"""

from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from db.models import User


def unlimited(email: str, owner_email: str | None) -> bool:
    """The account that runs this service (AGENT_OWNER_EMAIL) has no limit."""
    return bool(owner_email) and email.lower() == (owner_email or "").lower()


def runs_left(factory: sessionmaker[Session], user_id: int, free_runs: int) -> int:
    with factory() as session:
        used = session.get_one(User, user_id).runs_used
    return max(free_runs - used, 0)


def take_run(factory: sessionmaker[Session], user_id: int, free_runs: int) -> bool:
    """Count one run if the user has one left; False if they don't."""
    with factory.begin() as session:
        taken = session.execute(
            update(User)
            .where(User.id == user_id, User.runs_used < free_runs)
            .values(runs_used=User.runs_used + 1)
            .returning(User.id)
        ).first()
    return taken is not None


def give_back_run(factory: sessionmaker[Session], user_id: int) -> None:
    """Undo take_run when the run couldn't be queued after all."""
    with factory.begin() as session:
        session.execute(
            update(User)
            .where(User.id == user_id, User.runs_used > 0)
            .values(runs_used=User.runs_used - 1)
        )
