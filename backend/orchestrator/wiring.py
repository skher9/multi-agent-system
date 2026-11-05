"""open_pipeline(): build a real Pipeline from settings, and close everything after."""

from collections.abc import Iterator
from contextlib import contextmanager

from api.config import Settings
from db.session import make_session_factory
from llm_router.budget import db_daily_spend, db_story_spend
from llm_router.recorder import db_recorder
from llm_router.router import LlmRouter
from orchestrator.checkpoints import postgres_checkpointer
from orchestrator.records import ensure_project
from orchestrator.runner import Pipeline
from services import sandbox_e2b
from services.github import GitHubClient
from services.jira import JiraClient
from services.openrouter import OpenRouterClient
from services.r2 import R2Credentials, R2Storage
from services.workspace import github_remote


class NotConfiguredError(Exception):
    """A setting the pipeline needs is missing from backend/.env."""


@contextmanager
def open_pipeline(settings: Settings, *, database_url: str | None = None) -> Iterator[Pipeline]:
    """Connect Jira, OpenRouter and the database, with Postgres checkpoints for resuming.

    database_url overrides settings.database_url (scripts and tests use the test branch).
    """
    db_url = database_url or (
        settings.database_url.get_secret_value() if settings.database_url else None
    )
    missing = [
        name
        for name, value in [
            ("DATABASE_URL", db_url),
            ("OPENROUTER_API_KEY", settings.openrouter_api_key),
            ("JIRA_BASE_URL", settings.jira_base_url),
            ("JIRA_EMAIL", settings.jira_email),
            ("JIRA_API_TOKEN", settings.jira_api_token),
            ("AGENT_REPO", settings.agent_repo),
            ("AGENT_OWNER_EMAIL", settings.agent_owner_email),
            ("GITHUB_TOKEN", settings.github_token),
            ("R2_ACCOUNT_ID", settings.r2_account_id),
            ("R2_ACCESS_KEY_ID", settings.r2_access_key_id),
            ("R2_SECRET_ACCESS_KEY", settings.r2_secret_access_key),
            ("R2_BUCKET", settings.r2_bucket),
        ]
        if not value
    ]
    # Same check as `missing`, spelled out so the type checker knows none are None below
    if not (
        db_url
        and settings.openrouter_api_key
        and settings.jira_base_url
        and settings.jira_email
        and settings.jira_api_token
        and settings.agent_repo
        and settings.agent_owner_email
        and settings.github_token
        and settings.r2_account_id
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
        and settings.r2_bucket
    ):
        raise NotConfiguredError(", ".join(missing))
    if settings.sandbox_backend == "e2b":
        if not settings.e2b_api_key:
            raise NotConfiguredError("E2B_API_KEY (SANDBOX_BACKEND is e2b)")
        sandbox_e2b.configure(sandbox_e2b.Config(settings.e2b_api_key.get_secret_value()))
    else:
        sandbox_e2b.configure(None)

    factory = make_session_factory(db_url)
    repo_url = github_remote(settings.agent_repo)
    project_id = ensure_project(
        factory,
        owner_email=settings.agent_owner_email,
        name=settings.agent_repo.split("/")[1],
        repo_url=repo_url,
    )
    storage = R2Storage(
        R2Credentials(
            account_id=settings.r2_account_id,
            access_key_id=settings.r2_access_key_id.get_secret_value(),
            secret_access_key=settings.r2_secret_access_key.get_secret_value(),
            bucket=settings.r2_bucket,
        )
    )
    jira = JiraClient(
        settings.jira_base_url, settings.jira_email, settings.jira_api_token.get_secret_value()
    )
    client = OpenRouterClient(settings.openrouter_api_key.get_secret_value())
    # The org argument is only used by list_repos/ping; PRs name their repo
    github = GitHubClient(
        settings.github_token.get_secret_value(), settings.agent_repo.split("/")[0]
    )
    router = LlmRouter(
        client,
        db_recorder(factory),
        settings.usd_to_inr,
        db_story_spend(factory),
        settings.story_budget_inr,
        daily_spend=db_daily_spend(factory),
        daily_budget_inr=settings.daily_budget_inr,
    )
    try:
        with postgres_checkpointer(db_url) as checkpointer:
            yield Pipeline(
                factory,
                jira,
                router,
                project_id,
                checkpointer,
                storage=storage,
                repo_url=repo_url,
                github_token=settings.github_token.get_secret_value(),
                github=github,
                repo=settings.agent_repo,
            )
    finally:
        jira.close()
        client.close()
        github.close()
