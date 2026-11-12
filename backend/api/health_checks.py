"""The real check for each service, and the registry /health runs.

Service code (db/, services/) knows nothing about the API. These small wrappers
translate "keys missing" into NotConfiguredError and call the service's own ping.
"""

from api.config import Settings
from api.health import CheckFn, NotConfiguredError
from db import session as db_session
from services import redis_client
from services.github import GitHubClient
from services.jira import JiraClient
from services.openrouter import OpenRouterClient
from services.r2 import R2Credentials, R2Storage
from services.realtime import PusherCredentials, Realtime


def check_database(settings: Settings) -> None:
    if settings.database_url is None:
        raise NotConfiguredError("DATABASE_URL is not set")
    db_session.ping(settings.database_url.get_secret_value())


def check_redis(settings: Settings) -> None:
    # Always "configured": REDIS_URL defaults to the local docker-compose Redis.
    redis_client.ping(settings.redis_url)


def r2_from_settings(settings: Settings) -> R2Storage:
    if not (
        settings.r2_account_id
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
        and settings.r2_bucket
    ):
        raise NotConfiguredError("R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET")
    return R2Storage(
        R2Credentials(
            account_id=settings.r2_account_id,
            access_key_id=settings.r2_access_key_id.get_secret_value(),
            secret_access_key=settings.r2_secret_access_key.get_secret_value(),
            bucket=settings.r2_bucket,
        )
    )


def check_r2(settings: Settings) -> None:
    r2_from_settings(settings).ping()


def check_github(settings: Settings) -> None:
    if not (settings.github_token and settings.github_org):
        raise NotConfiguredError("GITHUB_TOKEN, GITHUB_ORG")
    client = GitHubClient(settings.github_token.get_secret_value(), settings.github_org)
    try:
        client.ping(settings.agent_repo)  # the demo repo the agents push to, if set
    finally:
        client.close()


def realtime_from_settings(settings: Settings) -> Realtime:
    if not (
        settings.pusher_app_id
        and settings.pusher_key
        and settings.pusher_secret
        and settings.pusher_cluster
    ):
        raise NotConfiguredError("PUSHER_APP_ID, PUSHER_KEY, PUSHER_SECRET, PUSHER_CLUSTER")
    return Realtime(
        PusherCredentials(
            app_id=settings.pusher_app_id,
            key=settings.pusher_key,
            secret=settings.pusher_secret.get_secret_value(),
            cluster=settings.pusher_cluster,
        )
    )


def check_pusher(settings: Settings) -> None:
    realtime_from_settings(settings).ping()


def check_openrouter(settings: Settings) -> None:
    if settings.openrouter_api_key is None:
        raise NotConfiguredError("OPENROUTER_API_KEY")
    client = OpenRouterClient(settings.openrouter_api_key.get_secret_value())
    try:
        client.ping()
    finally:
        client.close()


def check_jira(settings: Settings) -> None:
    if not (settings.jira_base_url and settings.jira_email and settings.jira_api_token):
        raise NotConfiguredError("JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN")
    client = JiraClient(
        settings.jira_base_url, settings.jira_email, settings.jira_api_token.get_secret_value()
    )
    try:
        client.ping()
    finally:
        client.close()


CHECKS: dict[str, CheckFn] = {
    "database": check_database,
    "redis": check_redis,
    "r2": check_r2,
    "github": check_github,
    "pusher": check_pusher,
    "openrouter": check_openrouter,
    "jira": check_jira,
}
