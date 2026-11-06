"""open_pipeline(): build a real Pipeline from settings, and close everything after.

Runs on the demo project use the Jira and GitHub in settings; runs on a user's own
project use the tokens that user connected (orchestrator/projects.py).
"""

from collections.abc import Iterator
from contextlib import contextmanager

from api.config import Settings
from db.session import make_session_factory
from llm_router.budget import db_agent_spend, db_daily_spend, db_story_spend
from llm_router.recorder import db_recorder
from llm_router.router import LlmRouter
from orchestrator.checkpoints import postgres_checkpointer
from orchestrator.projects import Credentials, credentials
from orchestrator.records import ensure_project
from orchestrator.runner import Pipeline
from services import sandbox_e2b
from services.figma import FigmaClient
from services.github import GitHubClient
from services.jira import JiraClient
from services.openrouter import OpenRouterClient
from services.r2 import R2Credentials, R2Storage
from services.secret_box import SecretBox
from services.workspace import github_remote


class NotConfiguredError(Exception):
    """A setting the pipeline needs is missing from backend/.env."""


@contextmanager
def open_pipeline(
    settings: Settings, *, database_url: str | None = None, project_id: int | None = None
) -> Iterator[Pipeline]:
    """Connect Jira, OpenRouter and the database, with Postgres checkpoints for resuming.

    database_url overrides settings.database_url (scripts and tests use the test branch).
    project_id: a user's own project (NotReadyError if it can't run); None = the demo.
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
    if project_id is None:
        own = Credentials(
            jira_site=settings.jira_base_url,
            jira_email=settings.jira_email,
            jira_token=settings.jira_api_token.get_secret_value(),
            jira_project_key=settings.jira_project_key or "",
            repo=settings.agent_repo,
            github_token=settings.github_token.get_secret_value(),
        )
        project_id = ensure_project(
            factory,
            owner_email=settings.agent_owner_email,
            name=settings.agent_repo.split("/")[1],
            repo_url=github_remote(settings.agent_repo),
        )
    else:
        if not settings.integrations_key:
            raise NotConfiguredError("INTEGRATIONS_KEY (needed for users' own projects)")
        own = credentials(
            factory, project_id, SecretBox(settings.integrations_key.get_secret_value())
        )
    repo_url = github_remote(own.repo)
    storage = R2Storage(
        R2Credentials(
            account_id=settings.r2_account_id,
            access_key_id=settings.r2_access_key_id.get_secret_value(),
            secret_access_key=settings.r2_secret_access_key.get_secret_value(),
            bucket=settings.r2_bucket,
        )
    )
    jira = JiraClient(own.jira_site, own.jira_email, own.jira_token)
    client = OpenRouterClient(settings.openrouter_api_key.get_secret_value())
    # The org argument is only used by list_repos/ping; PRs name their repo
    github = GitHubClient(own.github_token, own.repo.split("/")[0])
    figma = FigmaClient(settings.figma_token.get_secret_value()) if settings.figma_token else None
    router = LlmRouter(
        client,
        db_recorder(factory),
        settings.usd_to_inr,
        db_story_spend(factory),
        settings.story_budget_inr,
        daily_spend=db_daily_spend(factory),
        daily_budget_inr=settings.daily_budget_inr,
        agent_spend=db_agent_spend(factory),
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
                github_token=own.github_token,
                github=github,
                repo=own.repo,
                figma=figma,
            )
    finally:
        jira.close()
        client.close()
        github.close()
        if figma is not None:
            figma.close()
