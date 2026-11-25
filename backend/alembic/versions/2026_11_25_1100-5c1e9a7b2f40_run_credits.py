"""run credits: count the runs each account has started

Revision ID: 5c1e9a7b2f40
Revises: 34967ed7083f
Create Date: 2026-11-25 11:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5c1e9a7b2f40"
down_revision: str | Sequence[str] | None = "34967ed7083f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("runs_used", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("users", "runs_used")
