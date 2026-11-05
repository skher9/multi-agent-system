# The backend image, for hosts like Railway. One image, two services:
#   API (default):  uvicorn api.main:app on $PORT
#   worker:         celery -A workers.celery_app worker --loglevel=info
# Agent code never runs here: on hosts without Docker, SANDBOX_BACKEND=e2b sends it
# to E2B's microVMs. Secrets come from the host's environment variables, never the image.
#
# Build from backend/:  docker build -t mas-backend .

# Pinned minor version: patch updates only
FROM python:3.12-slim-bookworm

# git: the worker clones the agents' repo and pushes their branches
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# uv, pinned (same version as the sandbox image)
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

# Never run as root
RUN useradd --create-home --uid 10001 app
WORKDIR /app

# Dependencies first, so code changes don't reinstall them. --frozen: exactly uv.lock
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=app . .
RUN uv sync --frozen --no-dev && chown -R app /app/.venv

USER app
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1

# Railway sets $PORT; 8000 locally
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
