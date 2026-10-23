# Multi-Agent System

An AI agent team that works like a small software services company. A customer submits a PRD or a change request; agents triage it by size, ask questions, write user stories, build the code in a sandbox, review it, test it in three layers, and deliver a GitHub PR with a delivery report.

> **Status:** setup phase. The skeleton runs end to end; no agents yet.

## Repo layout

| Folder                      | What lives there                                                                          |
| --------------------------- | ----------------------------------------------------------------------------------------- |
| `backend/`                  | Python: FastAPI API, Celery workers, database models, service clients, agents, LLM router |
| `web/`                      | Next.js + TypeScript frontend                                                             |
| `sandbox/`                  | Docker image that runs agent-written code in isolation, plus its npm-only proxy           |
| `templates/nextjs-starter/` | Starter app every generated project begins from                                           |

## Prerequisites

Python 3.12 (uv installs it), [uv](https://docs.astral.sh/uv/), Node.js 22+, pnpm 10.30.1, Docker Desktop.

## Run everything locally

```bash
# 1. Secrets: copy the variable names, then fill in real values (never commit these files)
cp .env.example backend/.env        # keep the backend section
cp .env.example web/.env.local      # keep the web section

# 2. Install dependencies
(cd backend && uv sync)
pnpm install

# 3. Local services: Redis and the sandbox's npm-only proxy
docker compose up -d

# 4. Database: migrate the Neon test branch (main only after review)
(cd backend && uv run alembic -x target=test upgrade head)

# 5. Run the app (three terminals)
cd backend && uv run uvicorn api.main:app --reload        # API on :8000
cd backend && uv run celery -A workers.celery_app worker  # background worker
pnpm --filter web dev                                     # web on :3000
```

Then open:

- http://localhost:3000/status: every service's health
- http://localhost:3000/realtime-test: Pusher live event test
- http://localhost:8000/docs: interactive API docs

Try the job queue: `curl -X POST localhost:8000/jobs/ping`, then `curl localhost:8000/jobs/<job_id>` shows `"result": "pong"`.

## Sandbox

```bash
docker build -t mas-sandbox -f sandbox/Dockerfile .   # from the repo root
```

Agent code runs only inside throwaway containers from this image: CPU, memory, process, and time limits; no secrets; non-root; and a network that can reach only the npm registry, through `npm-proxy`.

## Checks

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
pnpm format:check && pnpm --filter web lint && pnpm --filter web typecheck
pnpm --filter web gen:api   # regenerate API types after changing the backend API
```

CI runs the same checks on every push.
