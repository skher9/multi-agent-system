# Multi-Agent System

An AI agent team that works like a small software services company. A customer submits a PRD or a change request; agents triage it by size, ask questions, write user stories, build the code in a sandbox, review it, test it in three layers, and deliver a GitHub PR with a delivery report.

> **Status:** setup phase. Nothing runs yet.

## Repo layout

| Folder | What lives there |
|---|---|
| `docs/` | Reference docs: briefing, setup guide, product overview, system design, services |
| `backend/` | Python: FastAPI API, Celery workers, database models, service clients, agents, LLM router |
| `web/` | Next.js + TypeScript frontend |
| `sandbox/` | Docker image that runs agent-written code in isolation |
| `templates/nextjs-starter/` | Starter app every generated project begins from |

## Running locally

Coming in later setup steps.
