"""website login

Revision ID: 91f04ecfb962
Revises: 23d3acb25fbe
Create Date: 2026-10-31 18:07:52.225934

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "91f04ecfb962"
down_revision: str | Sequence[str] | None = "23d3acb25fbe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Printed by better-auth 1.7.10 (getMigrations().compileMigrations()) for our config:
# email + password and the jwt plugin. Column names are camelCase, as Better Auth expects.
# If the website's Better Auth version or plugins change, print it again and diff.
BETTER_AUTH_SQL = [
    'create table "user" ("id" text not null primary key, "name" text not null, '
    '"email" text not null unique, "emailVerified" boolean not null, "image" text, '
    '"createdAt" timestamptz default CURRENT_TIMESTAMP not null, '
    '"updatedAt" timestamptz default CURRENT_TIMESTAMP not null)',
    'create table "session" ("id" text not null primary key, '
    '"expiresAt" timestamptz not null, "token" text not null unique, '
    '"createdAt" timestamptz default CURRENT_TIMESTAMP not null, '
    '"updatedAt" timestamptz not null, "ipAddress" text, "userAgent" text, '
    '"userId" text not null references "user" ("id") on delete cascade)',
    'create table "account" ("id" text not null primary key, "accountId" text not null, '
    '"providerId" text not null, '
    '"userId" text not null references "user" ("id") on delete cascade, '
    '"accessToken" text, "refreshToken" text, "idToken" text, '
    '"accessTokenExpiresAt" timestamptz, "refreshTokenExpiresAt" timestamptz, '
    '"scope" text, "password" text, '
    '"createdAt" timestamptz default CURRENT_TIMESTAMP not null, '
    '"updatedAt" timestamptz not null)',
    'create table "verification" ("id" text not null primary key, '
    '"identifier" text not null, "value" text not null, "expiresAt" timestamptz not null, '
    '"createdAt" timestamptz default CURRENT_TIMESTAMP not null, '
    '"updatedAt" timestamptz default CURRENT_TIMESTAMP not null)',
    'create table "jwks" ("id" text not null primary key, "publicKey" text not null, '
    '"privateKey" text not null, "createdAt" timestamptz not null, '
    '"expiresAt" timestamptz, "alg" text, "crv" text)',
    'create index "session_userId_idx" on "session" ("userId")',
    'create index "account_userId_idx" on "account" ("userId")',
    'create index "verification_identifier_idx" on "verification" ("identifier")',
]


def upgrade() -> None:
    """Upgrade schema."""
    for statement in BETTER_AUTH_SQL:
        op.execute(statement)
    op.add_column("users", sa.Column("auth_user_id", sa.String(length=64), nullable=True))
    op.create_unique_constraint(op.f("uq_users_auth_user_id"), "users", ["auth_user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("uq_users_auth_user_id"), "users", type_="unique")
    op.drop_column("users", "auth_user_id")
    # Dependents first: session and account reference user
    for table in ("jwks", "verification", "account", "session", "user"):
        op.execute(f'drop table "{table}"')
