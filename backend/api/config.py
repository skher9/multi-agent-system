"""App settings, loaded from backend/.env (or real environment variables).

Every value is optional so the app can start before all accounts exist.
A missing value shows up as "not configured" in /health instead of a crash.
Secrets use SecretStr so they never appear in logs, errors, or repr().
"""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unknown variables instead of failing
    )

    # Browser origins allowed to call the API (the Next.js dev server)
    cors_origins: list[str] = ["http://localhost:3000"]

    # Neon Postgres (connection strings contain the password)
    database_url: SecretStr | None = None
    database_url_test: SecretStr | None = None

    # Redis: local only, no password
    redis_url: str = "redis://localhost:6379/0"

    # Cloudflare R2
    r2_account_id: str | None = None
    r2_access_key_id: SecretStr | None = None
    r2_secret_access_key: SecretStr | None = None
    r2_bucket: str | None = None

    # GitHub agent organization
    github_token: SecretStr | None = None
    github_org: str | None = None

    # Pusher Channels
    pusher_app_id: str | None = None
    pusher_key: str | None = None
    pusher_secret: SecretStr | None = None
    pusher_cluster: str | None = None

    # OpenRouter
    openrouter_api_key: SecretStr | None = None

    # Jira Cloud: where v1 tickets come from (basic auth: account email + API token)
    jira_base_url: str | None = None  # e.g. https://your-site.atlassian.net
    jira_email: str | None = None
    jira_api_token: SecretStr | None = None

    # v1 pipeline: the one repo agents work on, and who owns its project in the database
    agent_repo: str | None = None  # GitHub owner/name, e.g. skher9/agent-playground
    agent_owner_email: str | None = None

    # LLM costs. OpenRouter bills in USD; we log and limit in ₹.
    # Rate from the Services doc (July 2026); update by hand when it drifts.
    usd_to_inr: Decimal = Decimal("96.5")
    # Budget guard: a story run (one feature, all its tasks together) stops past this.
    story_budget_inr: Decimal = Decimal("50")


@lru_cache
def get_settings() -> Settings:
    """Read settings once and reuse them (the .env file is parsed a single time)."""
    return Settings()
