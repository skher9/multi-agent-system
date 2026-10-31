"""Better Auth's tables: the website's login library owns their shape.

The website (web/src/lib/auth.ts) reads and writes them; we create them in an Alembic
migration (SQL printed by Better Auth itself for the pinned version) so one tool owns
every table. They have no SQLAlchemy models, so autogenerate must ignore them.
Our own `users` row links to a Better Auth user through users.auth_user_id.
"""

AUTH_TABLES = frozenset({"user", "session", "account", "verification", "jwks"})
