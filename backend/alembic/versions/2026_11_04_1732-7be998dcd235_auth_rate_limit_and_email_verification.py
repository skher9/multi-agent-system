"""auth rate limit and email verification

Revision ID: 7be998dcd235
Revises: 4022cd2d82b7
Create Date: 2026-11-04 17:32:21.611070

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7be998dcd235"
down_revision: str | Sequence[str] | None = "4022cd2d82b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Printed by better-auth 1.7.10 (getMigrations().compileMigrations()) after the website
# moved rate limiting to the database (rateLimit.storage = "database").
RATE_LIMIT_SQL = (
    'create table "rateLimit" ("id" text not null primary key, "key" text not null unique, '
    '"count" integer not null, "lastRequest" bigint not null)'
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(RATE_LIMIT_SQL)
    # Email logins now need a verified address. Accounts made before that rule existed
    # count as verified, so their owners aren't locked out.
    op.execute('update "user" set "emailVerified" = true where "emailVerified" = false')


def downgrade() -> None:
    """Downgrade schema."""
    # The verified flags stay: there's no record of which ones the upgrade set.
    op.execute('drop table "rateLimit"')
