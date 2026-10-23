from workers.celery_app import celery_app


@celery_app.task(name="ping")
def ping() -> str:
    """Setup test task: proves a worker picked the job off the queue and ran it."""
    return "pong"
