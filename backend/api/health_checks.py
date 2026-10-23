"""The real check for each service, and the registry /health runs.

Service code (db/, services/) knows nothing about the API. These small wrappers
translate "keys missing" into NotConfiguredError and call the service's own ping.
"""

from api.config import Settings
from api.health import CheckFn, NotConfiguredError
from db import session as db_session
from services import redis_client


def check_database(settings: Settings) -> None:
    if settings.database_url is None:
        raise NotConfiguredError("DATABASE_URL is not set")
    db_session.ping(settings.database_url.get_secret_value())


def check_redis(settings: Settings) -> None:
    # Always "configured": REDIS_URL defaults to the local docker-compose Redis.
    redis_client.ping(settings.redis_url)


CHECKS: dict[str, CheckFn] = {
    "database": check_database,
    "redis": check_redis,
}
