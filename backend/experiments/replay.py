"""Export one benchmark ticket's run as the website's public replay (no login needed).

    cd backend && uv run python -m experiments.replay <round> <ticket-id>

Reads the run's events from the Neon test branch (where benchmark rounds write) and
writes web/src/lib/runs/replay.json in the shape the run window plays. Only the latest
run of the ticket is kept. Run the round with --qa so the replay has test recordings.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select

from api.config import get_settings
from db.models import Feature, RunEvent
from db.session import make_session_factory
from experiments.bench import WORK

OUT = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "runs" / "replay.json"


def latest_run(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The events from the ticket's last run_started on, renumbered from 1."""
    starts = [i for i, event in enumerate(events) if event["kind"] == "run_started"]
    kept = events[starts[-1] :] if starts else events
    return [{**event, "id": number} for number, event in enumerate(kept, start=1)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("round")
    parser.add_argument("ticket", help="ticket id from tickets.json, e.g. like-button")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    result = json.loads((WORK / "rounds" / args.round / "result.json").read_text())
    key = result["tickets"][args.ticket]["key"]
    settings = get_settings()
    if settings.database_url_test is None:
        raise SystemExit("Needs DATABASE_URL_TEST in backend/.env")
    factory = make_session_factory(settings.database_url_test.get_secret_value())
    with factory() as session:
        feature = session.scalars(
            select(Feature).where(
                Feature.project_id == result["project_id"], Feature.jira_key == key
            )
        ).one()
        rows = session.scalars(
            select(RunEvent).where(RunEvent.feature_id == feature.id).order_by(RunEvent.id)
        ).all()
        events = [
            {
                "id": row.id,
                "kind": row.kind,
                "data": row.data,
                "agentRunId": row.agent_run_id,
                "createdAt": row.created_at.isoformat(),
            }
            for row in rows
        ]
        title = feature.title.removeprefix(f"{key}: ")
    replay = {"ticket": key, "title": title, "prUrl": None, "events": latest_run(events)}
    args.out.write_text(json.dumps(replay, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(replay['events'])} events -> {args.out}")


if __name__ == "__main__":
    main()
