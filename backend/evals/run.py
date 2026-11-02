"""Replay the golden tickets through the ticket reader and planner, and score them.

    uv run python -m evals.run              # every case
    uv run python -m evals.run contact-page # one case

Uses the real model (costs money: roughly ₹1-3 per planned case) on our Next.js
template, with no database, Jira or GitHub: the ticket text comes from cases.json.
Scoring is plain code, not a model: did the reader say ready/blocked, did the planner
find the conflict, create/modify the files a human would, and plan a test?
Run it after changing a prompt or a model, and compare with the last run.
Exits 1 if any case fails.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from agents.code_graph import OUT_FOLDER, CodeGraphFiles, build_graph
from agents.planner import Plan, plan_ticket
from agents.repo_tools import TEST_FILE
from agents.ticket_reader import TicketSpec, read_ticket
from api.config import get_settings
from llm_router.router import LlmRouter
from services.jira import JiraTicket
from services.openrouter import OpenRouterClient
from services.workspace import Workspace

CASES = Path(__file__).with_name("cases.json")
TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "nextjs-starter"
COPY_IGNORE = shutil.ignore_patterns("node_modules", ".next", "test-results", "playwright-report")


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    summary: str
    description: str
    status: str  # what the reader must say: "ready" or "blocked"
    conflicts: bool | None = None  # ready tickets: must the planner find conflicts?
    creates: list[str] = []  # files the plan must create
    modifies: list[str] = []  # files the plan must modify
    tests: bool = False  # the plan must include a test file


def load_cases(path: Path = CASES) -> list[Case]:
    return [Case.model_validate(c) for c in json.loads(path.read_text())]


def score(case: Case, spec: TicketSpec, plan: Plan | None) -> list[str]:
    """What the agents got wrong for this case; empty means it passed."""
    if spec.status != case.status:
        return [f"reader said {spec.status}, expected {case.status}"]
    if plan is None:
        return []
    failures = []
    if case.conflicts is not None and bool(plan.conflicts) != case.conflicts:
        found = "found" if plan.conflicts else "missed"
        failures.append(f"planner {found} conflicts (expected conflicts={case.conflicts})")
    actions = {(c.action, c.path) for c in plan.changes}
    failures += [f"plan doesn't create {p}" for p in case.creates if ("create", p) not in actions]
    failures += [f"plan doesn't modify {p}" for p in case.modifies if ("modify", p) not in actions]
    if case.tests and not any(TEST_FILE.search(c.path) for c in plan.changes):
        failures.append("plan has no test file")
    return failures


def main(argv: list[str]) -> int:
    settings = get_settings()
    if settings.openrouter_api_key is None:
        print("OPENROUTER_API_KEY is not set")
        return 2
    cases = [c for c in load_cases() if not argv or c.name in argv]
    spent: list[Decimal] = []
    router = LlmRouter(
        OpenRouterClient(settings.openrouter_api_key.get_secret_value()),
        lambda call: spent.append(call.cost_inr),
        settings.usd_to_inr,
        lambda _run_id: sum(spent, Decimal(0)),
        settings.story_budget_inr,
    )
    failed = 0
    with tempfile.TemporaryDirectory(prefix="evals-") as tmp:
        repo = _template_repo(Path(tmp))
        graph_dir = Path(tmp) / "graph"
        graph_dir.mkdir()
        with Workspace.clone(f"file://{repo}") as ws:
            build_graph(ws, graph_dir)
            graph = CodeGraphFiles(graph_dir / OUT_FOLDER, ws.head_sha())
        for case in cases:
            before = sum(spent, Decimal(0))
            failures = _run_case(case, router, repo, graph)
            cost = sum(spent, Decimal(0)) - before
            mark = "PASS" if not failures else "FAIL"
            print(f"{mark}  {case.name}  (₹{cost:.2f})")
            for failure in failures:
                print(f"      - {failure}")
            failed += bool(failures)
    print(f"\n{len(cases) - failed}/{len(cases)} passed, total ₹{sum(spent, Decimal(0)):.2f}")
    return 1 if failed else 0


def _run_case(case: Case, router: LlmRouter, repo: Path, graph: CodeGraphFiles) -> list[str]:
    ticket = JiraTicket(
        key="EVAL-1",
        issue_type="Story",
        status="To Do",
        summary=case.summary,
        description=case.description,
        labels=[],
    )
    try:
        # agent_run_id 0: no database here, so the id only tags the OpenRouter session
        spec = read_ticket(router, ticket, agent_run_id=0)
        plan = None
        if spec.status == "ready" and case.status == "ready":
            with Workspace.clone(f"file://{repo}") as ws:
                plan = plan_ticket(router, spec, ws, graph, agent_run_id=0)
    except Exception as exc:  # noqa: BLE001  (a crashed case is a failed case; carry on)
        return [f"crashed: {type(exc).__name__}: {str(exc)[:300]}"]
    return score(case, spec, plan)


def _template_repo(tmp: Path) -> Path:
    """The template as a one-commit git repo (agents work on clones of it)."""
    repo = tmp / "repo"
    shutil.copytree(TEMPLATE, repo, ignore=COPY_IGNORE)
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "template"]):
        subprocess.run(  # noqa: S603
            ["git", "-c", "user.name=evals", "-c", "user.email=evals@example.com", *args],  # noqa: S607
            cwd=repo,
            check=True,
        )
    return repo


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
