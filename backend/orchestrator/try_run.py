"""Run the whole pipeline on one real Jira ticket, in the foreground. SPENDS REAL CREDITS
(stops at the ₹50 story budget) and acts for real: Jira subtasks and comments, a pushed
branch and a PR on AGENT_REPO.

    cd backend && uv run python -m orchestrator.try_run KAN-4

Uses the main database (DATABASE_URL). Needs Docker with the mas-sandbox image and npm-proxy.
"""

import logging
import sys

from api.config import get_settings
from orchestrator.runner import run_ticket
from orchestrator.wiring import open_pipeline


def main(args: list[str]) -> None:
    if len(args) != 1:
        raise SystemExit("Usage: python -m orchestrator.try_run KAN-4")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    # httpx2 logs every request line; keep the output to our own progress
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    with open_pipeline(get_settings()) as pipeline:
        final = run_ticket(pipeline, args[0])
    print(f"\n=== {args[0]}: {final['outcome']}")
    for key in ("subtask_keys", "branch", "pr_url", "reviews", "fixes"):
        if key in final:
            print(f"{key}: {final[key]}")


if __name__ == "__main__":
    main(sys.argv[1:])
