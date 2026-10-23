"""Redis connectivity. Redis is Celery's job queue (broker) and result store."""

import redis


def ping(redis_url: str) -> None:
    """Raise if Redis doesn't answer PING within 3 seconds."""
    client = redis.Redis.from_url(redis_url, socket_connect_timeout=3, socket_timeout=3)
    try:
        client.ping()
    finally:
        client.close()
