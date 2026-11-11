"""Grade a benchmark round's code against the rubric (agents/rubric.md).

    cd backend && uv run python -m experiments.grade sonar-2             # every built ticket
    uv run python -m experiments.grade sonar-1 sonar-2 --only footer     # some tickets
    uv run python -m experiments.grade sonar-2 --no-scan                 # without the sandbox

After `experiments.bench` built a round, this reads each finished ticket's branch from
the round's local repo and asks the grader (a strong model from another family, see
agents/grader.py) for a 1-10 score in each of the rubric's five areas. The scanners
(agents/quality.py) run first, in the local sandbox, and the grader gets their findings.

SPENDS REAL MODEL CREDITS: about ₹10 a ticket. Nothing is written to the database.
Results: .work/rounds/<round>/grades.json, and a table on screen.
"""

import argparse
import json
import logging
from decimal import Decimal
from typing import Any

from agents.grader import Grade, grade_changes
from agents.quality import QualityFindings, scan_code
from agents.rubric import AREAS, BAR
from api.config import get_settings
from experiments.bench import WORK, load_tickets
from llm_router.router import LlmRouter
from services.openrouter import OpenRouterClient
from services.workspace import Workspace

GRADE_BUDGET_INR = Decimal(60)  # per ticket; the router stops a grade that costs more

logger = logging.getLogger("grade")


def ticket_text(ticket: dict[str, Any]) -> str:
    return f"Title: {ticket['summary']}\n\n{ticket['description']}"


def grade_ticket(
    router: LlmRouter, repo_url: str, branch: str, ticket: dict[str, Any], *, scan: bool
) -> tuple[Grade, QualityFindings]:
    with Workspace.clone(repo_url) as workspace:
        base = workspace.ref_sha("origin/main")
        workspace.checkout(branch)
        found = scan_code(workspace, workspace.diff(base)) if scan else QualityFindings()
        # agent_run_id 0: no database here, so the id only tags the OpenRouter session
        grade = grade_changes(
            router, ticket_text(ticket), workspace, base, agent_run_id=0, scan=found
        )
    return grade, found


def table(rows: dict[str, dict[str, Any]]) -> str:
    """One line per ticket: the five scores, the lowest, and whether it meets the bar."""
    short = {"correctness": "corr", "tests": "tests", "readability": "read",
             "fits_the_repo": "fits", "robustness": "robust"}  # fmt: skip
    lines = [f"{'ticket':<18}" + "".join(f"{short[a]:>7}" for a in AREAS) + "    low  bar"]
    for name, row in rows.items():
        if "error" in row:
            lines.append(f"{name:<18} error: {row['error']}")
            continue
        scores = {s["area"]: s["score"] for s in row["grade"]["scores"]}
        low = min(scores.values())
        mark = "✅" if low >= BAR else "❌"
        lines.append(
            f"{name:<18}" + "".join(f"{scores[a]:>7}" for a in AREAS) + f"{low:>7}  {mark}"
        )
    graded = [r for r in rows.values() if "grade" in r]
    if graded:
        averages = [
            sum(s["score"] for r in graded for s in r["grade"]["scores"] if s["area"] == a)
            / len(graded)
            for a in AREAS
        ]
        lines.append(f"{'average':<18}" + "".join(f"{v:>7.1f}" for v in averages))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rounds", nargs="+", help="round names, as given to experiments.bench")
    parser.add_argument("--only", nargs="*", default=[], help="ticket ids (default: all built)")
    parser.add_argument("--no-scan", action="store_true", help="skip the sandbox scanners")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)

    settings = get_settings()
    if settings.openrouter_api_key is None:
        raise SystemExit("Needs OPENROUTER_API_KEY in backend/.env")
    client = OpenRouterClient(settings.openrouter_api_key.get_secret_value())
    tickets = {t["id"]: t for t in load_tickets()}
    total = Decimal(0)

    for round_name in args.rounds:
        folder = WORK / "rounds" / round_name
        result = json.loads((folder / "result.json").read_text())
        saved = folder / "grades.json"
        # Grades from an earlier call stay; a ticket graded again replaces its own
        rows: dict[str, dict[str, Any]] = json.loads(saved.read_text()) if saved.exists() else {}
        for name, run in result["tickets"].items():
            if run["outcome"] not in ("ready_to_merge", "needs_human"):
                continue  # blocked or crashed: no code to grade
            if args.only and name not in args.only:
                continue
            spent: list[Decimal] = []
            router = LlmRouter(
                client,
                lambda call, spent=spent: spent.append(call.cost_inr),
                settings.usd_to_inr,
                lambda _run_id, spent=spent: sum(spent, Decimal(0)),
                GRADE_BUDGET_INR,
            )
            logger.info("grading %s (%s)", name, run["key"])
            try:
                grade, found = grade_ticket(
                    router,
                    f"file://{folder / 'repo.git'}",
                    f"agent/{run['key']}",
                    tickets[name],
                    scan=not args.no_scan,
                )
                rows[name] = {
                    "grade": grade.model_dump(),
                    "scan": {"ran": found.ran, "smells": found.smells,
                             "duplication": found.duplication, "notes": found.notes},
                }  # fmt: skip
            except Exception as exc:  # noqa: BLE001  (carry on with the rest)
                logger.exception("%s failed", name)
                rows[name] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            rows[name]["cost_inr"] = str(sum(spent, Decimal(0)))
            total += sum(spent, Decimal(0))
            # Saved after every ticket: a stalled round keeps what it already graded
            (folder / "grades.json").write_text(json.dumps(rows, indent=2))
        print(f"\n== {round_name}\n{table(rows)}")
    print(f"\ntotal ₹{total:.2f}")


if __name__ == "__main__":
    main()
