"""Live check of the router against real models. SPENDS REAL CREDITS (well under ₹1).

    cd backend && uv run python -m llm_router.smoke_test

Calls each model twice with the same long opening prompt; the second call should
read most of it from the provider's cache. Writes only to the Neon test branch and
deletes everything it created at the end. Re-run it whenever a model in models.py changes.
"""

import time
from decimal import Decimal

from api.config import get_settings
from db.scratch import scratch_agent_run
from db.session import make_session_factory
from llm_router.budget import db_story_spend
from llm_router.models import Role
from llm_router.recorder import db_recorder
from llm_router.router import CallRecord, LlmRouter
from services.openrouter import OpenRouterClient

# About 2,000 tokens. Caching usually needs a prompt of at least ~1,000 tokens.
SYSTEM_PROMPT = "You are a terse assistant. Follow every rule below.\n" + "\n".join(
    f"Rule {i}: keep answers short, never invent facts, and prefer plain words." for i in range(150)
)

CASES = [
    ("ticket reader", Role.TICKET_READER, False),
    ("developer", Role.DEVELOPER, False),
    ("escalation", Role.DEVELOPER, True),
]


def main() -> None:
    settings = get_settings()
    if settings.database_url_test is None or settings.openrouter_api_key is None:
        raise SystemExit("Needs DATABASE_URL_TEST and OPENROUTER_API_KEY in backend/.env")
    factory = make_session_factory(settings.database_url_test.get_secret_value())

    seen: list[CallRecord] = []
    save = db_recorder(factory)

    def record(call: CallRecord) -> None:
        save(call)
        seen.append(call)

    client = OpenRouterClient(settings.openrouter_api_key.get_secret_value())
    spend = db_story_spend(factory)
    router = LlmRouter(client, record, settings.usd_to_inr, spend, settings.story_budget_inr)

    with scratch_agent_run(factory, role="developer") as run_id:
        print(f"{'case':<14} {'model':<30} {'in':>6} {'cached':>6} {'out':>5} {'₹':>8} {'ms':>6}")
        for label, role, escalate in CASES:
            for attempt in (1, 2):
                router.complete(
                    role=role,
                    escalate=escalate,
                    agent_run_id=run_id,
                    max_tokens=300,  # room for models that reason before answering
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Reply with just: OK {attempt}"},
                    ],
                )
                c = seen[-1]
                print(
                    f"{label:<14} {c.model:<30} {c.input_tokens:>6} {c.cached_tokens:>6} "
                    f"{c.output_tokens:>5} {c.cost_inr:>8} {c.latency_ms:>6}"
                )
                time.sleep(2)  # give the provider a moment to store the cache

        total = sum((c.cost_inr for c in seen), Decimal("0"))
        print(f"\nTotal: ₹{total} | budget guard reads ₹{spend(run_id)} from the database")
    client.close()
    print("Cleaned up test rows.")


if __name__ == "__main__":
    main()
