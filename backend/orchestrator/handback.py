"""What the pipeline hands back to people: the PR description and the Jira comment."""

from typing import Any

from agents.developer import MAX_RISKS, DevResult, Risk
from agents.gate import VerifyResult
from agents.planner import MAX_DECISIONS, Plan
from agents.qa import qa_markdown
from agents.ticket_reader import TicketSpec
from orchestrator.routing import RISKY_PATH


def pr_title(ticket_key: str, spec: TicketSpec) -> str:
    return f"{ticket_key}: {spec.title}"


def pr_body(
    ticket_url: str,
    spec: TicketSpec,
    plan: Plan,
    dev: DevResult,
    subtask_keys: list[str],
    verify: VerifyResult | None = None,
) -> str:
    """Markdown for the PR: what was built, against which criteria, where it came from,
    and the evidence it works (the verify box's checks and browser tests)."""
    criteria = "\n".join(f"- [x] {c}" for c in spec.acceptance_criteria)
    subtasks = "\n".join(
        f"- {key}: [{s.area}] {s.title}"
        for key, s in zip(subtask_keys, plan.subtasks, strict=False)
    )
    files = "\n".join(f"- `{f}`" for f in dev.changed_files)
    review_notes = _decisions(plan, dev) + _risks(plan, dev)
    return f"""\
Ticket: {ticket_url}

## What was built
{dev.summary}

## Acceptance criteria
{criteria}

## Subtasks
{subtasks or "- none"}
{review_notes}
## Files changed
{files}

{_evidence(spec, verify)}

🤖 Built by the agent pipeline (planner, developer, fixer, QA)."""


def pr_risks(plan: Plan, dev: DevResult) -> list[Risk]:
    """What a reviewer should look at closely: what our code knows without a model first
    (risky paths, backend and frontend together), then the developer's. At most 3."""
    found: list[Risk] = []
    risky = [p for p in dev.changed_files if RISKY_PATH.search(p)]
    if risky:
        found.append(Risk(where=risky[0], what="touches login, money, data or a server boundary"))
    if {s.area for s in plan.subtasks} >= {"BE", "FE"}:
        found.append(
            Risk(
                where="the contract between backend and frontend",
                what="both sides changed: check they agree on every input and output",
            )
        )
    seen = {r.where for r in found}
    found += [r for r in dev.risks if r.where not in seen]
    return found[:MAX_RISKS]


def _decisions(plan: Plan, dev: DevResult) -> str:
    """The choices the agents made, why, and what they rejected: the plan's first."""
    chosen = [*plan.decisions, *dev.decisions][:MAX_DECISIONS]
    if not chosen:
        return ""
    lines = [f"- {d.choice}. {d.why}\n  Rejected: {d.rejected}" for d in chosen]
    return "\n## Decisions\n" + "\n".join(lines) + "\n"


def _risks(plan: Plan, dev: DevResult) -> str:
    risks = pr_risks(plan, dev)
    if not risks:
        return ""
    lines = [f"- {r.where}: {r.what}" for r in risks]
    return "\n## Look closely at\n" + "\n".join(lines) + "\n"


def _evidence(spec: TicketSpec, verify: VerifyResult | None) -> str:
    if verify is None:
        return "Lint, typecheck and unit tests passed before this PR was opened."
    rows = "\n".join(f"| {name} | {'✅' if ok else '❌'} |" for name, ok in verify.checks.items())
    text = f"## Checks\n| Check | Result |\n|---|---|\n{rows}"
    if verify.fixer_summary:
        text += f"\n\nThe first run failed; the fixer agent fixed it:\n{verify.fixer_summary}"
    text += "\n\n## Browser tests (QA agent)\n"
    text += (
        qa_markdown(verify.qa, spec.acceptance_criteria)
        if verify.qa
        else "QA couldn't finish its browser tests this time; check the criteria by hand."
    )
    return text


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


def problem_comment(problem: str) -> dict[str, Any]:
    """The Jira comment (ADF) when the developer stopped because the plan can't be built."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "🤖 The developer stopped and needs a human:"}
                ],
            },
            {"type": "paragraph", "content": [{"type": "text", "text": problem}]},
        ],
    }
