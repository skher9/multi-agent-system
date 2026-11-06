"""Run the benchmark tickets through the real pipeline, locally, to measure the agents.

    cd backend && uv run python -m experiments.bench                  # every ticket
    uv run python -m experiments.bench --round base-1 footer vague    # some, named round

SPENDS REAL MODEL CREDITS (each ticket stops at the ₹50 story budget). Everything else
is local and fake, so nothing real is touched:
- repo: a local bare copy of the playground; agents clone and push there, not GitHub
- Jira and GitHub: in-memory stand-ins that record what would have been posted
- database: the Neon *test* branch; each round is its own project (bench-<round>@local)
- sandbox: local Docker (needs `docker compose up -d` and the mas-sandbox image)
- QA is off: this measures the reader, planner, developer and reviewer

Then: `uv run python -m experiments.report <round>`.
"""

import argparse
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from api.config import get_settings
from db.session import make_session_factory
from llm_router.budget import db_agent_spend, db_story_spend
from llm_router.recorder import db_recorder
from llm_router.router import LlmRouter
from orchestrator.records import ensure_project
from orchestrator.runner import Pipeline, run_ticket
from services.github import PullRequest
from services.jira import JiraTicket
from services.openrouter import OpenRouterClient

HERE = Path(__file__).resolve().parent
WORK = HERE / ".work"  # gitignored: the local repo copy, code graphs, round results
PLAYGROUND = "https://github.com/skher9/agent-playground.git"
PROJECT_KEY = "BENCH"

logger = logging.getLogger("bench")


def load_tickets() -> list[dict[str, Any]]:
    return json.loads((HERE / "tickets.json").read_text())


@dataclass
class FakeJira:
    """Answers with the benchmark tickets; records comments and subtasks."""

    tickets: dict[str, JiraTicket]
    comments: list[tuple[str, Any]] = field(default_factory=list)
    subtasks: list[tuple[str, str]] = field(default_factory=list)

    def get_ticket(self, key: str) -> JiraTicket:
        return self.tickets[key]

    def add_comment(self, key: str, body: dict[str, Any]) -> str:
        self.comments.append((key, body))
        return str(len(self.comments))

    def browse_url(self, key: str) -> str:
        return f"local://jira/{key}"

    def create_subtask(
        self, parent_key: str, summary: str, description: dict[str, Any], labels: list[str]
    ) -> str:
        self.subtasks.append((parent_key, summary))
        return f"{parent_key}-S{len(self.subtasks)}"

    def find_subtasks(self, parent_key: str, label: str) -> dict[str, str]:
        return {}


@dataclass
class FakeGitHub:
    """Pretends to open PRs and post comments; the branch itself is in the local repo."""

    prs: dict[str, int] = field(default_factory=dict)
    comments: list[tuple[int, str]] = field(default_factory=list)

    def default_branch(self, repo: str) -> str:
        return "main"

    def open_pull_request(
        self, repo: str, *, head: str, base: str, title: str, body: str
    ) -> PullRequest:
        number = self.prs.setdefault(head, len(self.prs) + 1)
        return PullRequest(number, f"local://pr/{number}")

    def comment_on_pull_request(self, repo: str, number: int, body: str) -> None:
        self.comments.append((number, body))


class LocalStorage:
    """Code graphs on disk instead of R2."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)

    def upload(self, key: str, data: bytes, content_type: str = "") -> None:
        path = self.folder / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def download(self, key: str) -> bytes:
        return (self.folder / key).read_bytes()


def local_repo() -> Path:
    """A bare copy of the playground's main branch; each round starts from it fresh."""
    bare = WORK / "playground.git"
    if not bare.exists():
        WORK.mkdir(parents=True, exist_ok=True)
        subprocess.run(  # noqa: S603
            ["git", "clone", "--quiet", "--bare", PLAYGROUND, str(bare)],  # noqa: S607
            check=True,
        )
    return bare


def fresh_round_repo(round_name: str) -> Path:
    """A copy of the bare repo for this round, so branches from other rounds don't clash."""
    copy = WORK / "rounds" / round_name / "repo.git"
    if not copy.exists():
        copy.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(  # noqa: S603
            ["git", "clone", "--quiet", "--bare", str(local_repo()), str(copy)],  # noqa: S607
            check=True,
        )
    return copy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", default=datetime.now(UTC).strftime("r%m%d-%H%M"))
    parser.add_argument(
        "--model", help="one OpenRouter model for every agent, e.g. deepseek/deepseek-v4-flash"
    )
    parser.add_argument(
        "--no-routing", action="store_true", help="standard model only (routing off)"
    )
    parser.add_argument("only", nargs="*", help="ticket ids from tickets.json (default: all)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    settings = get_settings()
    if settings.database_url_test is None or settings.openrouter_api_key is None:
        raise SystemExit("Needs DATABASE_URL_TEST and OPENROUTER_API_KEY in backend/.env")
    factory = make_session_factory(settings.database_url_test.get_secret_value())

    tickets = [t for t in load_tickets() if not args.only or t["id"] in args.only]
    keys = {t["id"]: f"{PROJECT_KEY}-{i}" for i, t in enumerate(load_tickets(), start=1)}
    jira = FakeJira(
        {
            keys[t["id"]]: JiraTicket(
                key=keys[t["id"]],
                issue_type="Task",
                status="To Do",
                summary=t["summary"],
                description=t["description"],
                labels=[],
            )
            for t in tickets
        }
    )
    repo = fresh_round_repo(args.round)
    project_id = ensure_project(
        factory,
        owner_email=f"bench-{args.round}@local",
        name="agent-playground",
        repo_url=str(repo),
    )
    router = LlmRouter(
        OpenRouterClient(settings.openrouter_api_key.get_secret_value()),
        db_recorder(factory),
        settings.usd_to_inr,
        db_story_spend(factory),
        settings.story_budget_inr,
        agent_spend=db_agent_spend(factory),
        model_override=args.model,
        routing=not args.no_routing,
    )
    pipeline = Pipeline(
        factory,
        jira,  # type: ignore[arg-type]  (duck-typed stand-in)
        router,
        project_id,
        storage=LocalStorage(WORK / "graphs"),
        repo_url=str(repo),
        github=FakeGitHub(),  # type: ignore[arg-type]
        repo="local/playground",
        skip_qa=True,
    )

    results: dict[str, Any] = {
        "round": args.round,
        "project_id": project_id,
        "model": args.model or "models.py",
        "routing": not args.no_routing,
        "tickets": {},
    }
    for ticket in tickets:
        key = keys[ticket["id"]]
        logger.info("=== %s (%s): %s", ticket["id"], key, ticket["summary"])
        started = time.monotonic()
        try:
            outcome = run_ticket(pipeline, key)["outcome"]
        except Exception as exc:  # noqa: BLE001  (one ticket failing must not stop the round)
            logger.exception("%s failed", key)
            outcome = f"error: {type(exc).__name__}: {str(exc)[:200]}"
        results["tickets"][ticket["id"]] = {
            "key": key,
            "outcome": outcome,
            "seconds": round(time.monotonic() - started),
        }
        logger.info("=== %s: %s", ticket["id"], outcome)

    out = WORK / "rounds" / args.round / "result.json"
    out.write_text(json.dumps(results, indent=2))
    print(
        f"\nRound {args.round} done: {out}\nNext: uv run python -m experiments.report {args.round}"
    )


if __name__ == "__main__":
    main()
