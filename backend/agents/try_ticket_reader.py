"""Run the ticket reader on real Jira tickets. SPENDS REAL CREDITS (about ₹0.1 per ticket).

    cd backend && uv run python -m agents.try_ticket_reader KAN-4 KAN-5 [--post]

Prints each ticket's spec and cost. Records calls on the Neon test branch only and
deletes them at the end. Jira is only written to with --post: blocked tickets then
get a comment with the reader's questions.
"""

import sys

from agents.ticket_reader import questions_comment, read_ticket
from api.config import get_settings
from db.scratch import scratch_agent_run
from db.session import make_session_factory
from llm_router.budget import db_story_spend
from llm_router.recorder import db_recorder
from llm_router.router import LlmRouter
from services.jira import JiraClient
from services.openrouter import OpenRouterClient


def main(args: list[str]) -> None:
    post = "--post" in args
    keys = [a for a in args if a != "--post"]
    s = get_settings()
    if not (
        keys
        and s.database_url_test
        and s.openrouter_api_key
        and s.jira_base_url
        and s.jira_email
        and s.jira_api_token
    ):
        raise SystemExit(
            "Usage: python -m agents.try_ticket_reader KAN-4 [KAN-5 ...] [--post]\n"
            "Needs DATABASE_URL_TEST, OPENROUTER_API_KEY and JIRA_* in backend/.env"
        )
    factory = make_session_factory(s.database_url_test.get_secret_value())
    jira = JiraClient(s.jira_base_url, s.jira_email, s.jira_api_token.get_secret_value())
    client = OpenRouterClient(s.openrouter_api_key.get_secret_value())
    spend = db_story_spend(factory)
    router = LlmRouter(client, db_recorder(factory), s.usd_to_inr, spend, s.story_budget_inr)

    try:
        for key in keys:
            ticket = jira.get_ticket(key)
            with scratch_agent_run(factory, role="ticket_reader") as run_id:
                spec = read_ticket(router, ticket, agent_run_id=run_id)
                print(f"\n=== {key}: {spec.status.upper()} (cost ₹{spend(run_id)})")
                print(spec.model_dump_json(indent=2))
            if post and spec.status == "blocked":
                comment_id = jira.add_comment(key, questions_comment(spec))
                print(f"Posted questions on {key} (comment {comment_id})")
    finally:
        jira.close()
        client.close()


if __name__ == "__main__":
    main(sys.argv[1:])
