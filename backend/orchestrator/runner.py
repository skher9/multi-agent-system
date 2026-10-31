"""run_ticket(): one full pipeline run for a ticket, with its database records."""

from dataclasses import dataclass
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.orm import Session, sessionmaker

from agents.code_graph import Storage, open_code_graph
from agents.developer import DevResult, develop_ticket
from agents.planner import Plan, plan_ticket
from agents.reviewer import Review, review_changes
from agents.ticket_reader import TicketSpec
from llm_router.router import LlmRouter
from orchestrator.graph import RunContext, RunInput, RunState, build_graph
from orchestrator.records import agent_run, claim_feature, ensure_feature, update_feature
from services.github import GitHubClient
from services.jira import JiraClient
from services.workspace import GitIdentity, Workspace

# Author of the agents' commits. GitHub's noreply domain: no real inbox behind it.
AGENT_AUTHOR = GitIdentity(name="Agent Dev Team", email="agent-dev-team@users.noreply.github.com")


class AlreadyRunningError(Exception):
    """Another run of this ticket is in progress; this one did nothing."""


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


def open_pr(pipeline: Pipeline, branch: str, title: str, body: str) -> tuple[int, str]:
    if pipeline.github is None or not pipeline.repo:
        raise RuntimeError("opening a PR needs the pipeline's github client and repo")
    base = pipeline.github.default_branch(pipeline.repo)
    pr = pipeline.github.open_pull_request(
        pipeline.repo, head=branch, base=base, title=title, body=body
    )
    return pr.number, pr.url


def make_plan(pipeline: Pipeline, spec: TicketSpec, agent_run_id: int) -> tuple[Plan, str]:
    """Clone the repo, load (or build) its code graph, and run the planner on it."""
    if pipeline.storage is None or not pipeline.repo_url:
        raise RuntimeError("planning needs the pipeline's storage and repo_url")
    with (
        Workspace.clone(pipeline.repo_url, pipeline.github_token) as workspace,
        open_code_graph(
            pipeline.factory, pipeline.storage, pipeline.project_id, workspace
        ) as graph,
    ):
        plan = plan_ticket(pipeline.router, spec, workspace, graph, agent_run_id=agent_run_id)
        return plan, graph.commit_sha


def make_code(
    pipeline: Pipeline,
    ticket_key: str,
    spec: TicketSpec,
    plan: Plan,
    commit_sha: str,
    agent_run_id: int,
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
    with Workspace.clone(pipeline.repo_url, pipeline.github_token) as workspace:
        workspace.create_branch(branch, start=commit_sha)
        for subtask in plan.subtasks:
            dev = develop_ticket(
                pipeline.router, spec, plan, workspace, agent_run_id=agent_run_id, subtask=subtask
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
) -> Review:
    """Clone, switch to the agent's branch, and review it against the planned commit."""
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
        )


def make_fix(
    pipeline: Pipeline,
    ticket_key: str,
    spec: TicketSpec,
    plan: Plan,
    review: Review,
    branch: str,
    run_id: int,
) -> tuple[DevResult, str]:
    """Clone the agent's branch, fix the review's issues, commit on top and push."""
    with Workspace.clone(pipeline.repo_url, pipeline.github_token) as workspace:
        workspace.checkout(branch)
        dev = develop_ticket(
            pipeline.router, spec, plan, workspace, agent_run_id=run_id, review=review
        )
        if dev.problem:
            return dev, ""  # stopped for a human: nothing to commit
        head = workspace.commit_all(f"{ticket_key}: review fixes\n\n{dev.summary}", AGENT_AUTHOR)
        if head is None:
            raise RuntimeError("the developer finished the fixes without changing any files")
        workspace.push(branch)  # on top of the reviewed commit: the PR shows the fix
    return dev, head


def comment_pr(pipeline: Pipeline, number: int, body: str) -> None:
    if pipeline.github is None or not pipeline.repo:
        raise RuntimeError("commenting needs the pipeline's github client and repo")
    pipeline.github.comment_on_pull_request(pipeline.repo, number, body)


def run_ticket(pipeline: Pipeline, ticket_key: str) -> RunState:
    """Run the graph for one ticket and save where it ended on the ticket's feature.

    If the ticket's last run stopped partway (a crash), this continues from the node
    that didn't finish. Otherwise it starts from the beginning.
    Raises AlreadyRunningError if another run of the ticket hasn't finished.
    """
    feature_id = ensure_feature(pipeline.factory, pipeline.project_id, ticket_key)
    if not claim_feature(pipeline.factory, feature_id):
        raise AlreadyRunningError(ticket_key)
    context = RunContext(
        jira=pipeline.jira,
        router=pipeline.router,
        agent_run=lambda role: agent_run(pipeline.factory, feature_id, role),
        make_plan=lambda spec, run_id: make_plan(pipeline, spec, run_id),
        make_code=lambda key, spec, plan, sha, run_id: make_code(
            pipeline, key, spec, plan, sha, run_id
        ),
        open_pr=lambda branch, title, body: open_pr(pipeline, branch, title, body),
        make_review=lambda spec, plan, branch, base, summary, previous, run_id: make_review(
            pipeline, spec, plan, branch, base, summary, previous, run_id
        ),
        make_fix=lambda key, spec, plan, review, branch, run_id: make_fix(
            pipeline, key, spec, plan, review, branch, run_id
        ),
        comment_pr=lambda number, body: comment_pr(pipeline, number, body),
    )
    graph = build_graph(pipeline.checkpointer)
    # One thread per feature: every run of this ticket shares its saved state.
    config: RunnableConfig = {"configurable": {"thread_id": f"feature-{feature_id}"}}

    # state.next lists the nodes still waiting to run; non-empty means it stopped partway.
    unfinished = pipeline.checkpointer is not None and bool(graph.get_state(config).next)
    # Input None tells LangGraph "continue from the checkpoint" instead of starting over.
    graph_input: RunInput | None = None if unfinished else {"ticket_key": ticket_key}
    try:
        # invoke() is typed as returning a plain dict; it is the graph's RunState.
        final = cast(RunState, graph.invoke(graph_input, config, context=context))
    except BaseException:
        update_feature(pipeline.factory, feature_id, status="failed")
        raise
    update_feature(
        pipeline.factory,
        feature_id,
        status=final["outcome"],
        title=f"{ticket_key}: {final['ticket']['summary']}",
    )
    return final
