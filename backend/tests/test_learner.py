"""The learner agent, and rules reaching the agents' tasks (no network, no database)."""

from agents.learner import learn_rules, repo_rules_block
from agents.planner import Plan
from services.workspace import Workspace
from tests.test_agent_loop import Script, call, reply
from tests.test_developer import fake_checks  # noqa: F401  (fixture)
from tests.test_planner import GOOD_PLAN, SPEC
from tests.test_workspace import origin  # noqa: F401  (fixture)

RULE = {"rule": "Use the shared Button component", "why": "Reviewer: no plain <button>"}


def test_no_comments_means_no_model_call() -> None:
    script = Script()
    assert learn_rules(script.router(), [], ["x"], agent_run_id=1) == []
    assert script.sent == []


def test_rules_come_from_the_comments_and_skip_known_ones() -> None:
    script = Script(reply(call("finish", {"rules": [RULE]})))
    rules = learn_rules(
        script.router(),
        ["src/a.tsx: please use our Button, not <button>"],
        ["Dates go through formatDate (reviewer asked)"],
        agent_run_id=1,
    )
    assert [r.rule for r in rules] == ["Use the shared Button component"]
    task = script.sent[0]["messages"][1]["content"]
    assert "<existing_rules>\n- Dates go through formatDate (reviewer asked)" in task
    assert "- src/a.tsx: please use our Button, not <button>" in task
    assert [t["function"]["name"] for t in script.sent[0]["tools"]] == ["finish"]


def test_rules_block_is_empty_without_rules() -> None:
    assert repo_rules_block([]) == ""
    assert repo_rules_block(["Use X (why)"]) == "\n\n<repo_rules>\n- Use X (why)\n</repo_rules>"


def test_the_developer_reads_the_repo_rules(
    origin: str,  # noqa: F811
    fake_checks: list[list[str]],  # noqa: F811
) -> None:
    from agents.developer import develop_ticket

    plan = Plan.model_validate(GOOD_PLAN)
    script = Script(
        reply(call("create_file", {"path": "src/x.ts", "content": "x\n"})),
        reply(call("finish", {"summary": "done"})),
    )
    with Workspace.clone(origin) as ws:
        develop_ticket(
            script.router(),
            SPEC,
            plan,
            ws,
            agent_run_id=1,
            failures=["lint"],
            rules=["Use X (why)"],
        )
    assert script.sent[0]["messages"][1]["content"].endswith(
        "<repo_rules>\n- Use X (why)\n</repo_rules>"
    )
