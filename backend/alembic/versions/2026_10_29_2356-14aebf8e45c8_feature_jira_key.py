"""feature jira key

Revision ID: 14aebf8e45c8
Revises: 9c60d8cf64a0
Create Date: 2026-10-29 23:56:35.049040

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "14aebf8e45c8"
down_revision: str | Sequence[str] | None = "9c60d8cf64a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """One feature per Jira ticket per project."""
    op.add_column("features", sa.Column("jira_key", sa.String(length=32), nullable=True))
    op.create_unique_constraint(
        "uq_features_project_id_jira_key", "features", ["project_id", "jira_key"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_features_project_id_jira_key", "features", type_="unique")
    op.drop_column("features", "jira_key")
