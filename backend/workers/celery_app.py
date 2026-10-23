"""Celery: runs slow work (agent runs, later) outside the API process.

Start a worker:  uv run celery -A workers.celery_app worker --loglevel=info

Redis plays two roles: the broker (queue of jobs waiting) and the result
backend (where a finished job's return value is kept for a while).
"""

from celery import Celery

from api.config import get_settings

settings = get_settings()

celery_app = Celery(
    "multi_agent_system",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["workers.tasks"],
)

celery_app.conf.update(
    # JSON only: never pickle, which can run code hidden in a message.
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Remove a job from the queue only after it finishes, not when a worker picks it up.
    # If the worker crashes mid-job, the job goes back on the queue instead of vanishing.
    # Caveat with Redis: a job still unacknowledged after the visibility timeout
    # (default 1 hour) is handed out again. Story runs are capped at 30 minutes.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Threads, not the default prefork pool. Prefork breaks on macOS (Python starts child
    # processes with "spawn" there, and Celery's fast task setup assumes "fork").
    # Agent jobs mostly wait on the network (LLM, GitHub, Docker), which threads handle well.
    # Open question for M1: Celery's hard time limits only work with prefork, so the
    # 30-minute story limit will need to be enforced in our own code.
    worker_pool="threads",
    # Agent jobs are long: each worker takes one job at a time
    # instead of reserving a batch it can't start yet.
    worker_prefetch_multiplier=1,
    result_expires=3600,  # keep results for 1 hour
    broker_connection_retry_on_startup=True,
)
