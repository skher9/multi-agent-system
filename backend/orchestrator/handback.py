"""What the pipeline hands back to people: the PR description and the Jira comment."""

from typing import Any

from agents.developer import DevResult
from agents.planner import Plan
from agents.ticket_reader import TicketSpec


def pr_title(ticket_key: str, spec: TicketSpec) -> str:
    return f"{ticket_key}: {spec.title}"


def pr_body(
    ticket_url: str, spec: TicketSpec, plan: Plan, dev: DevResult, subtask_keys: list[str]
) -> str:
    """Markdown for the PR: what was built, against which criteria, and where it came from."""
    criteria = "\n".join(f"- [x] {c}" for c in spec.acceptance_criteria)
    subtasks = "\n".join(
        f"- {key}: [{s.area}] {s.title}"
        for key, s in zip(subtask_keys, plan.subtasks, strict=False)
    )
    files = "\n".join(f"- `{f}`" for f in dev.changed_files)
    return f"""\
Ticket: {ticket_url}

## What was built
{dev.summary}

## Acceptance criteria
{criteria}

## Subtasks
{subtasks or "- none"}

## Files changed
{files}

Lint, typecheck and unit tests passed before this PR was opened.

🤖 Built by the agent pipeline (planner + developer)."""


def pr_comment(pr_url: str) -> dict[str, Any]:
    """The Jira comment (ADF) linking the ticket to its PR."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "🤖 Built and ready for review: "},
                    {
                        "type": "text",
                        "text": pr_url,
                        "marks": [{"type": "link", "attrs": {"href": pr_url}}],
                    },
                ],
            }
        ],
    }
