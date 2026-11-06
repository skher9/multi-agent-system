"""run_ticket(): one full pipeline run for a ticket, with its database records."""

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command
from sqlalchemy.orm import Session, sessionmaker

from agents.code_graph import Storage, open_code_graph
from agents.developer import DevResult, develop_ticket
from agents.gate import GateResult, VerifyResult, run_gate
from agents.learner import learn_rules
from agents.loop import AgentLoopError, EventSink, ignore_events
from agents.planner import Plan, plan_ticket
from agents.qa import qa_ticket
from agents.repo_tools import RepoTools
from agents.reviewer import Review, review_changes
from agents.ticket_reader import TicketSpec
from db.models import EventKind
from llm_router.models import Role
from llm_router.router import LlmRouter
from orchestrator.decisions import PlanDecision
from orchestrator.graph import RunContext, RunInput, RunState, build_graph
from orchestrator.records import (
    agent_run,
    claim_feature,
    ensure_feature,
    project_rules,
    record_event,
    save_rules,
    update_feature,
)
from orchestrator.routing import planner_tier, reviewer_tier
from services.github import GitHubClient
from services.jira import TICKET_KEY, JiraClient
from services.workspace import GitIdentity, Workspace

# Author of the agents' commits. GitHub's noreply domain: no real inbox behind it.
AGENT_AUTHOR = GitIdentity(name="Agent Dev Team", email="agent-dev-team@users.noreply.github.com")


logger = logging.getLogger(__name__)


class AlreadyRunningError(Exception):
    """Another run of this ticket is in progress; this one did nothing."""


class NotWaitingError(Exception):
    """A plan decision came for a ticket whose run isn't waiting for one."""


@dataclass(frozen=True)
class Pipeline:
    """Everything a run needs, built once (e.g. by the API or a worker)."""

    factory: sessionmaker[Session]
    jira: JiraClient
    router: LlmRouter
    project_id: int
    # Saves the state after every node so a crashed run can resume. None: no resuming.
    checkpointer: BaseCheckpointSaver[Any] | None = None
    # Needed from the planner on: where code graphs are kept, and the repo agents work on
    storage: Storage | None = None
    repo_url: str = ""
    github_token: str | None = None
    # For opening PRs: the API client and the repo as "owner/name"
    github: GitHubClient | None = None
    repo: str = ""
    # Experiments (backend/experiments) measure the planner, developer and reviewer
    # without the QA agent's browser tests
    skip_qa: bool = False


def open_pr(pipeline: Pipeline, branch: str, title: str, body: str) -> tuple[int, str]:
    if pipeline.github is None or not pipeline.repo:
        raise RuntimeError("opening a PR needs the pipeline's github client and repo")
    base = pipeline.github.default_branch(pipeline.repo)
    pr = pipeline.github.open_pull_request(
        pipeline.repo, head=branch, base=base, title=title, body=body
    )
    return pr.number, pr.url


def step(on_event: EventSink, role: str, text: str) -> None:
    """A plain-words progress line for the run window, for work that has no tool calls."""
    on_event(EventKind.STEP, {"role": role, "text": text})


def make_plan(
    pipeline: Pipeline,
    spec: TicketSpec,
    agent_run_id: int,
    feedback: str = "",
    on_event: EventSink = ignore_events,
) -> tuple[Plan, str]:
    """Clone the repo, load (or build) its code graph, and run the planner on it."""
    if pipeline.storage is None or not pipeline.repo_url:
        raise RuntimeError("planning needs the pipeline's storage and repo_url")
    step(on_event, Role.PLANNER, "Cloning the repo")
    with Workspace.clone(pipeline.repo_url, pipeline.github_token) as workspace:
        step(on_event, Role.PLANNER, "Loading the code map (files, functions, imports)")
        with open_code_graph(
            pipeline.factory, pipeline.storage, pipeline.project_id, workspace
        ) as graph:
            step(on_event, Role.PLANNER, "Reading the code to plan the change")
            plan = plan_ticket(
                pipeline.router,
                spec,
                workspace,
                graph,
                agent_run_id=agent_run_id,
                feedback=feedback,
                rules=project_rules(pipeline.factory, pipeline.project_id),
                on_event=on_event,
                strong_reason=planner_tier(spec),
            )
            return plan, graph.commit_sha


def make_code(
    pipeline: Pipeline,
    ticket_key: str,
    spec: TicketSpec,
    plan: Plan,
    commit_sha: str,
    agent_run_id: int,
    on_event: EventSink = ignore_events,
) -> tuple[DevResult, str, str]:
    """Clone at the planned commit and build the plan on agent/<ticket>, one subtask at a
    time (BE before FE, as planned), one commit each; then push.

    If the developer stops with a problem, nothing is pushed and the result carries it.
    """
    if not pipeline.repo_url:
        raise RuntimeError("developing needs the pipeline's repo_url")
    branch = f"agent/{ticket_key}"
    summaries: list[str] = []
    changed: set[str] = set()
    head = ""
    step(on_event, Role.DEVELOPER, "Cloning the repo")
    with Workspace.clone(pipeline.repo_url, pipeline.github_token) as workspace:
        workspace.create_branch(branch, start=commit_sha)
        for number, subtask in enumerate(plan.subtasks, start=1):
            step(
                on_event,
                Role.DEVELOPER,
                f"Building subtask {number} of {len(plan.subtasks)}:"
                f" [{subtask.area}] {subtask.title}",
            )
            dev = develop_ticket(
                pipeline.router,
                spec,
                plan,
                workspace,
                agent_run_id=agent_run_id,
                subtask=subtask,
                rules=project_rules(pipeline.factory, pipeline.project_id),
                earlier=list(summaries),
                on_event=on_event,
            )
            if dev.problem:
                return dev, branch, ""
            label = f"[{subtask.area}] {subtask.title}"
            summaries.append(f"**{label}**\n{dev.summary}")
            changed.update(dev.changed_files)
            head = (
                workspace.commit_all(f"{ticket_key}: {label}\n\n{dev.summary}", AGENT_AUTHOR)
                or head
            )
        if not head:
            raise RuntimeError("the developer finished without changing any files")
        # replace: the branch is ours; a rerun after a crash builds it again from scratch
        step(on_event, Role.DEVELOPER, f"Pushing the branch {branch}")
        workspace.push(branch, replace=True)
    return DevResult(summary="\n\n".join(summaries), changed_files=sorted(changed)), branch, head


def make_review(
    pipeline: Pipeline,
    spec: TicketSpec,
    plan: Plan,
    branch: str,
    base_sha: str,
    dev_summary: str,
    previous: Review | None,
    run_id: int,
    on_event: EventSink = ignore_events,
) -> Review:
    """Clone, switch to the agent's branch, and review it against the planned commit."""
    step(on_event, Role.REVIEWER, f"Reading the changes on {branch}")
    with Workspace.clone(pipeline.repo_url, pipeline.github_token) as workspace:
        workspace.checkout(branch)
        return review_changes(
            pipeline.router,
            spec,
            plan,
            workspace,
            base_sha,
            agent_run_id=run_id,
            dev_summary=dev_summary,
            previous=previous,
            rules=project_rules(pipeline.factory, pipeline.project_id),
            on_event=on_event,
            strong_reason=reviewer_tier(plan, 1 if previous is None else 2),
        )


def make_fix(
    pipeline: Pipeline,
    ticket_key: str,
    spec: TicketSpec,
    plan: Plan,
    review: Review,
    branch: str,
    run_id: int,
    on_event: EventSink = ignore_events,
) -> tuple[DevResult, str]:
    """Clone the agent's branch, fix the review's issues, commit on top and push."""
    step(on_event, Role.DEVELOPER, f"Fixing {len(review.issues)} review comment(s)")
    with Workspace.clone(pipeline.repo_url, pipeline.github_token) as workspace:
        workspace.checkout(branch)
        dev = develop_ticket(
            pipeline.router,
            spec,
            plan,
            workspace,
            agent_run_id=run_id,
            review=review,
            rules=project_rules(pipeline.factory, pipeline.project_id),
            on_event=on_event,
        )
        if dev.problem:
            return dev, ""  # stopped for a human: nothing to commit
        head = workspace.commit_all(f"{ticket_key}: review fixes\n\n{dev.summary}", AGENT_AUTHOR)
        if head is None:
            raise RuntimeError("the developer finished the fixes without changing any files")
        workspace.push(branch)  # on top of the reviewed commit: the PR shows the fix
    return dev, head


def make_verify(
    pipeline: Pipeline,
    ticket_key: str,
    spec: TicketSpec,
    plan: Plan,
    branch: str,
    base_sha: str,
    start_agent: Callable[[str], AbstractContextManager[int]],
    events: Callable[[int], EventSink],
) -> VerifyResult:
    """Clone the agent's branch and check it before a PR opens (see agents/gate.py):
    1. the gate (lint, typecheck, unit tests, placeholder and secret scans);
    2. if it fails, the fixer agent, whose finish must pass the gate;
    3. the QA agent's browser tests, one or more per criterion.
    Each agent's work is its own commit; then one push.
    """
    with Workspace.clone(pipeline.repo_url, pipeline.github_token) as workspace:
        workspace.checkout(branch)
        tools = RepoTools(workspace, typecheck_after_edit=False)
        if error := tools.install():
            raise RuntimeError(error)
        gate = run_gate(tools, workspace, base_sha)
        fixer_summary = ""
        if not gate.ok:
            with start_agent(Role.FIXER) as run_id:
                dev = develop_ticket(
                    pipeline.router,
                    spec,
                    plan,
                    workspace,
                    agent_run_id=run_id,
                    failures=gate.failures,
                    check=lambda: run_gate(tools, workspace, base_sha).failures,
                    role=Role.FIXER,
                    rules=project_rules(pipeline.factory, pipeline.project_id),
                    on_event=events(run_id),
                )
            if dev.problem:
                return VerifyResult(checks=gate.passed, problem=dev.problem)
            fixer_summary = dev.summary
            workspace.commit_all(
                f"{ticket_key}: fix the final checks\n\n{dev.summary}", AGENT_AUTHOR
            )
            # The fixer's finish only passes when the whole gate does
            gate = GateResult(passed=dict.fromkeys(gate.passed, True), failures=[])
        qa = None
        try:
            if pipeline.skip_qa:
                raise _SkipQa
            with start_agent(Role.QA) as run_id:
                qa, qa_files = qa_ticket(
                    pipeline.router,
                    spec,
                    plan,
                    workspace,
                    agent_run_id=run_id,
                    on_event=events(run_id),
                )
            if qa_files:
                workspace.commit_all(f"{ticket_key}: browser tests\n\n{qa.summary}", AGENT_AUTHOR)
        except _SkipQa:
            pass
        except AgentLoopError:
            # QA is evidence, not a gate: the PR opens and says QA couldn't finish
            logger.warning("%s: QA didn't finish", ticket_key, exc_info=True)
            workspace.discard_changes()
        workspace.push(branch)
        return VerifyResult(
            checks=gate.passed, fixer_summary=fixer_summary, qa=qa, head_sha=workspace.head_sha()
        )


class _SkipQa(Exception):  # noqa: N818  (a jump out of the QA block, not an error)
    pass


class NotMergedError(Exception):
    """Rules are learned only from merged PRs: what a human finally accepted."""


def learn_from_pr(pipeline: Pipeline, number: int) -> list[str]:
    """Turn people's comments on a merged agent PR into rules for this project; return
    the new ones. The model call is charged to the PR's ticket (from its title)."""
    if pipeline.github is None or not pipeline.repo:
        raise RuntimeError("learning needs the pipeline's github client and repo")
    pr = pipeline.github.pull_request(pipeline.repo, number)
    if not pr.merged:
        raise NotMergedError(f"PR #{number} isn't merged")
    key = TICKET_KEY.match(pr.title)
    if key is None:
        raise ValueError(f"PR #{number}'s title doesn't start with a ticket key: {pr.title!r}")
    comments = pipeline.github.human_comments(pipeline.repo, number)
    if not comments:
        return []
    feature_id = ensure_feature(pipeline.factory, pipeline.project_id, key.group(0))
    existing = project_rules(pipeline.factory, pipeline.project_id)
    with agent_run(pipeline.factory, feature_id, Role.LEARNER) as run_id:
        rules = learn_rules(pipeline.router, comments, existing, agent_run_id=run_id)
    pairs = [(r.rule, r.why) for r in rules]
    save_rules(pipeline.factory, pipeline.project_id, pairs, pr.url)
    return [r.rule for r in rules]


def comment_pr(pipeline: Pipeline, number: int, body: str) -> None:
    if pipeline.github is None or not pipeline.repo:
        raise RuntimeError("commenting needs the pipeline's github client and repo")
    pipeline.github.comment_on_pull_request(pipeline.repo, number, body)


def run_ticket(
    pipeline: Pipeline,
    ticket_key: str,
    *,
    approve_plan: bool = False,
    plan_decision: PlanDecision | None = None,
) -> RunState:
    """Run the graph for one ticket and save where it ended on the ticket's feature.

    If the ticket's last run stopped partway (a crash), this continues from the node
    that didn't finish. Otherwise it starts from the beginning.
    approve_plan: pause after planning until a human decides; plan_decision is that
    decision, and resumes the paused run. A paused run given no decision stays paused.
    Raises AlreadyRunningError if another run of the ticket hasn't finished, and
    NotWaitingError for a decision when no plan is waiting.
    """
    if (approve_plan or plan_decision) and pipeline.checkpointer is None:
        raise ValueError("pausing for plan approval needs a checkpointer")
    feature_id = ensure_feature(pipeline.factory, pipeline.project_id, ticket_key)
    if not claim_feature(pipeline.factory, feature_id):
        raise AlreadyRunningError(ticket_key)

    def event(kind: EventKind, data: dict[str, Any], run_id: int | None = None) -> None:
        record_event(pipeline.factory, feature_id, kind, data, agent_run_id=run_id)

    def agent_events(run_id: int) -> EventSink:
        """Where one agent's tool calls go: the feature's timeline, tagged with its run."""
        return lambda kind, data: event(kind, data, run_id)

    context = RunContext(
        jira=pipeline.jira,
        router=pipeline.router,
        agent_run=lambda role: agent_run(pipeline.factory, feature_id, role),
        make_plan=lambda spec, feedback, run_id: make_plan(
            pipeline, spec, run_id, feedback, agent_events(run_id)
        ),
        make_code=lambda key, spec, plan, sha, run_id: make_code(
            pipeline, key, spec, plan, sha, run_id, agent_events(run_id)
        ),
        open_pr=lambda branch, title, body: open_pr(pipeline, branch, title, body),
        make_review=lambda spec, plan, branch, base, summary, previous, run_id: make_review(
            pipeline, spec, plan, branch, base, summary, previous, run_id, agent_events(run_id)
        ),
        make_fix=lambda key, spec, plan, review, branch, run_id: make_fix(
            pipeline, key, spec, plan, review, branch, run_id, agent_events(run_id)
        ),
        comment_pr=lambda number, body: comment_pr(pipeline, number, body),
        make_verify=lambda key, spec, plan, branch, base: make_verify(
            pipeline,
            key,
            spec,
            plan,
            branch,
            base,
            lambda role: agent_run(pipeline.factory, feature_id, role),
            agent_events,
        ),
    )
    graph = build_graph(pipeline.checkpointer)
    # One thread per feature: every run of this ticket shares its saved state.
    config: RunnableConfig = {"configurable": {"thread_id": f"feature-{feature_id}"}}

    saved = graph.get_state(config) if pipeline.checkpointer is not None else None
    # state.next lists the nodes still waiting to run; non-empty means it stopped partway.
    unfinished = saved is not None and bool(saved.next)
    waiting = saved is not None and bool(saved.interrupts)  # paused for a plan decision
    if plan_decision is not None and not waiting:
        update_feature(pipeline.factory, feature_id, status=_status(saved))
        raise NotWaitingError(ticket_key)
    if waiting and plan_decision is None:
        update_feature(pipeline.factory, feature_id, status="waiting_for_plan_approval")
        return cast(RunState, saved.values if saved else {})
    graph_input: RunInput | Command[Any] | None
    if plan_decision is not None:
        # The answer becomes what interrupt() returns inside await_plan_approval
        graph_input = Command(resume=plan_decision.model_dump())
        event(EventKind.PLAN_DECIDED, plan_decision.model_dump())
    elif unfinished:
        graph_input = None  # None tells LangGraph "continue from the checkpoint"
    else:
        graph_input = {"ticket_key": ticket_key, "approve_plan": approve_plan}
    final: dict[str, Any] = {}
    event(EventKind.RUN_STARTED, {"resumed": unfinished})
    try:
        # "tasks" says a box started (its finish comes as "updates" too); "updates" says
        # which box just finished; "values" is the state after it.
        for mode, chunk in graph.stream(
            graph_input, config, context=context, stream_mode=["tasks", "updates", "values"]
        ):
            if mode == "tasks":
                task = cast(dict[str, Any], chunk)
                if "result" not in task:  # a start; results are covered by "updates"
                    event(EventKind.NODE_STARTED, {"node": task["name"]})
            elif mode == "updates":
                for node in cast(dict[str, Any], chunk):
                    if node == "__interrupt__":  # the pause itself, not a box
                        continue
                    logger.info("%s: finished %s", ticket_key, node)
                    finished: dict[str, Any] = {"node": node}
                    update = cast(dict[str, Any], chunk)[node]
                    if isinstance(update, dict):
                        finished |= _what_the_window_shows(update)
                        if ticket := update.get("ticket"):
                            # The title shows from the start, not only once the run ends
                            update_feature(
                                pipeline.factory,
                                feature_id,
                                status="running",
                                title=f"{ticket_key}: {ticket['summary']}",
                            )
                    event(EventKind.NODE_FINISHED, finished)
            else:
                final = cast(dict[str, Any], chunk)
    except BaseException as exc:
        update_feature(pipeline.factory, feature_id, status="failed")
        event(EventKind.RUN_FAILED, {"error": type(exc).__name__})
        raise
    if graph.get_state(config).interrupts if pipeline.checkpointer is not None else False:
        event(EventKind.RUN_PAUSED, {"waiting_for": "plan_approval"})
    else:
        event(EventKind.RUN_ENDED, {"outcome": final["outcome"]})
    update_feature(
        pipeline.factory,
        feature_id,
        status=final["outcome"],
        title=f"{ticket_key}: {final['ticket']['summary']}",
    )
    return cast(RunState, final)


def _status(saved: Any) -> str:
    """The feature's status to put back when a call changes nothing."""
    if saved is None or not saved.values:
        return "new"
    return str(saved.values.get("outcome", "failed"))


def _what_the_window_shows(update: dict[str, Any]) -> dict[str, Any]:
    """The few facts from a finished box that the run window prints: the ticket's
    title, the reader's verdict, the PR's address."""
    shown: dict[str, Any] = {}
    if ticket := update.get("ticket"):
        shown["summary"] = ticket["summary"]
    if spec := update.get("spec"):
        shown["ticket_status"] = spec["status"]
        shown["criteria"] = len(spec["acceptance_criteria"])
        shown["questions"] = len(spec["questions"])
    if update.get("pr_url"):
        shown["pr_url"] = update["pr_url"]
    return shown
