# Agent Dev Team

**A team of AI agents that takes a Jira ticket and delivers a tested, reviewed GitHub pull request.**

You write a ticket the way you would for a developer. The agents read it, ask questions if
it's unclear, study the codebase, plan the work, write the code, test it in a real browser,
review it, and open a PR. A person approves the plan before any code is written, and a
person decides whether to merge.

**Live site:** https://agent-dev-team-jade.vercel.app · **Latest PR written by the agents:**
[skher9/agent-playground#13](https://github.com/skher9/agent-playground/pull/13), with a
video of every browser test

> Built by Shravani Kher. The website runs on Vercel, the API and agent workers on
> Railway, and agent-written code in E2B cloud sandboxes.

---

## What a run looks like

Ticket **KAN-10: "Add a site footer"**, with three acceptance criteria (a copyright line,
a link home, the footer on every page).

1. **Ticket reader** checks the ticket is clear enough to build. If not, it posts questions
   on the ticket and stops.
2. **Planner** reads the code and plans the change: create `src/components/Footer.tsx`,
   modify `src/app/layout.tsx`, add tests. It checks the ticket against the code for
   conflicts, and the plan goes on the ticket for a human to **approve, revise or reject**.
3. **Developer** builds each subtask. It can't say "done" until lint, typecheck and the
   unit tests pass, which our code runs, not the model.
4. **Verify:** the whole branch is checked again: lint, typecheck, unit tests, a production
   build, and scans of the lines the agents added for leaked keys, placeholder code, code
   smells and copied code. If anything fails, a **fixer** must make all of it pass.
5. **QA** writes test cases from the ticket (steps a user takes, what they should see),
   then one Playwright test per case that clicks and types like a person. Every test is
   recorded on video, and pass or fail is read from Playwright's own report, not from the
   agent.
6. **Reviewer**, on a stronger model, scores the change 1 to 10 in five areas
   (correctness, tests, readability, fits the repo, robustness). Any area below 6 goes back
   to the fixer, up to two rounds. The PR opens with the checks, the test cases and a link
   to each recording.

The result for KAN-10: [PR #13](https://github.com/skher9/agent-playground/pull/13), with
5 test cases (two of them edge cases QA thought of itself), all passing, each with a video.
On the website, the run page has a "Watch the testing" player.

## How it works

```mermaid
flowchart LR
    T[Jira ticket] --> R[Ticket reader]
    R -->|unclear| Q[Questions on the ticket]
    R -->|ready| P[Planner]
    P -->|conflict| Q
    P --> A{Human approves plan?}
    A -->|revise| P
    A -->|approve| D[Developer]
    D --> V[Checks + QA in a browser]
    V --> RV[Reviewer]
    RV -->|changes, max 2| F[Fixer] --> RV
    RV --> PR[Pull request]
```

The pipeline is a [LangGraph](https://langchain-ai.github.io/langgraph/) graph
([`orchestrator/graph.py`](backend/orchestrator/graph.py)). Agents make decisions; separate
nodes do anything that touches the outside world, like posting to Jira or opening the PR,
so every action is visible in the graph. Pausing for plan approval uses LangGraph's
interrupt with Postgres checkpoints, saved after every step: a run can wait for days for an
answer, and a run that crashes resumes from the last step instead of starting (and paying)
again.

## Design decisions

- **Code checks, models don't grade themselves.** "Done" means lint, typecheck, unit tests,
  the build and browser tests pass, run by our code. QA's results come from Playwright's
  report, and every reviewer finding must quote real code, which our code verifies.
- **Each agent gets only the tools its job needs.** The ticket reader has none, the planner
  and reviewer can only read, and only the developer can edit. Requests for any other tool
  are refused in code.
- **The agent sees the right files.** Each repo gets a code graph
  ([Graphify](https://pypi.org/project/graphifyy/)), built once and reused. For each
  ticket, a personalized PageRank over that graph ranks the files that matter, like
  Aider's repo map ([`agents/code_map.py`](backend/agents/code_map.py)).
- **It learns from reviews.** When a person leaves review comments on a merged agent PR,
  the learner turns them into short rules ("use the shared Button") that later runs follow
  ([`agents/learner.py`](backend/agents/learner.py)).
- **Cheap models, hard checks.** Most agents run on DeepSeek V4.1 Flash; the reviewer and
  any agent that gets stuck move to DeepSeek V4 Pro. A build costs about ₹8 a ticket.
- **Every model call goes through one router**, which logs the cost in ₹ and stops a run
  at its budget (₹50 by default). Model IDs live in one file, and a new model must pass the
  eval set first ([`evals/`](backend/evals)).

## Security

- **Sandboxed code.** Everything the agents write runs in a throwaway sandbox (Docker
  locally, an E2B microVM in production):
  non-root, all Linux capabilities dropped, CPU, memory, process and time limits, and a
  network that reaches only the npm registry through a proxy
  ([`services/sandbox.py`](backend/services/sandbox.py)).
- **No secrets in the sandbox.** Containers get no environment variables, and the agents'
  file tools refuse `.env` files and any path outside the repo.
- **Prompt injection.** Ticket text is untrusted, so the agent that reads it has no tools,
  and its output is validated against a schema before anything uses it.
- **Leak scan before every PR** for API keys and private keys
  ([`agents/gate.py`](backend/agents/gate.py)).
- **Humans stay in charge:** plan approval before code, and nothing merges automatically.
- **Website:** email verification, rate-limited login stored in Postgres, CSP and security
  headers, and account deletion.

## Tech

| Part         | What                                                                                  |
| ------------ | ------------------------------------------------------------------------------------- |
| Agents       | Python 3.12, LangGraph, OpenRouter (DeepSeek V4.1 Flash, V4 Pro)                      |
| API, workers | FastAPI, Celery, Redis                                                                |
| Data         | Postgres on Neon, SQLAlchemy + Alembic, Cloudflare R2 for code graphs and test videos |
| Website      | Next.js 16, React 19, Tailwind CSS v4, Better Auth, Pusher for live events            |
| Testing      | pytest (412 tests), Playwright, a golden-ticket eval set, a 9-ticket benchmark        |
| Hosting      | Vercel (website), Railway (API, workers), E2B (sandboxes)                             |
| Integrations | Jira, GitHub                                                                          |

## Repo layout

| Folder                      | What lives there                                                |
| --------------------------- | --------------------------------------------------------------- |
| `backend/agents/`           | One file per agent, plus their tools                            |
| `backend/orchestrator/`     | The LangGraph pipeline, run records, plan approval              |
| `backend/llm_router/`       | The only code that calls models: routing, cost logging, budgets |
| `backend/services/`         | Jira, GitHub, sandbox, R2 and workspace clients                 |
| `backend/experiments/`      | The benchmark: fixed tickets, cost and quality per agent        |
| `backend/evals/`            | Golden tickets scored in code after a prompt or model change    |
| `web/`                      | The website: landing page, login, dashboard, run window         |
| `sandbox/`                  | The Docker image agent code runs in, and its npm-only proxy     |
| `templates/nextjs-starter/` | The starter app the agents build on                             |

## Run it locally

Needs Python 3.12 (uv installs it), [uv](https://docs.astral.sh/uv/), Node.js 22+,
pnpm 10.30.1 and Docker Desktop.

```bash
# 1. Secrets: copy the variable names, then fill in real values (never commit these files)
cp .env.example backend/.env        # keep the backend section
cp .env.example web/.env.local      # keep the web section

# 2. Install dependencies
(cd backend && uv sync)
pnpm install

# 3. Local services and the sandbox image
docker compose up -d
docker build -t mas-sandbox -f sandbox/Dockerfile .

# 4. Database (the Neon test branch)
(cd backend && uv run alembic -x target=test upgrade head)

# 5. Run (three terminals)
cd backend && uv run uvicorn api.main:app --reload        # API on :8000
cd backend && uv run celery -A workers.celery_app worker  # background worker
pnpm --filter web dev                                     # website on :3000
```

## Checks

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
pnpm format:check && pnpm --filter web lint && pnpm --filter web typecheck
```

CI runs the same checks on every push. Dependabot, CodeQL and GitHub secret scanning
watch the repo.
