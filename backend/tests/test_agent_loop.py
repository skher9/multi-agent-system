"""The agent loop against a fake model that replies with scripted tool calls."""

import json
from decimal import Decimal
from typing import Any

import httpx2
import pytest
from pydantic import BaseModel, Field

from agents.loop import AgentLoopError, EventSink, ignore_events, run_agent
from db.models import EventKind
from llm_router.models import Role
from llm_router.router import LlmRouter
from services.openrouter import OpenRouterClient


class Answer(BaseModel):
    """Your final answer."""

    summary: str = Field(min_length=1)


def call(name: str, args: dict[str, Any], call_id: str = "c1") -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


def reply(*tool_calls: dict[str, Any], content: str | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"content": content}
    if tool_calls:
        message["tool_calls"] = list(tool_calls)
    return {
        "model": "minimax/minimax-m3",
        "choices": [{"finish_reason": "tool_calls" if tool_calls else "stop", "message": message}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 10, "cost": 0.0001},
    }


class Script:
    """A fake model: answers with the scripted replies in order, records what it was sent."""

    def __init__(self, *replies: dict[str, Any]) -> None:
        self.replies = list(replies)
        self.sent: list[dict[str, Any]] = []
        self.tool_calls: list[tuple[str, str]] = []

    def router(self) -> LlmRouter:
        def handler(request: httpx2.Request) -> httpx2.Response:
            self.sent.append(json.loads(request.content))
            return httpx2.Response(200, json=self.replies.pop(0))

        client = OpenRouterClient("fake-key", transport=httpx2.MockTransport(handler))
        return LlmRouter(
            client, lambda _c: None, Decimal("96.5"), lambda _r: Decimal(0), Decimal(50)
        )

    def handle(self, name: str, arguments: str) -> str:
        self.tool_calls.append((name, arguments))
        return f"result of {name}"

    def run(
        self, max_tool_calls: int = 25, on_event: EventSink = ignore_events, senior: bool = False
    ) -> Answer:
        return run_agent(
            self.router(),
            role=Role.DEVELOPER,
            agent_run_id=1,
            system="sys",
            user="task",
            tools=[{"type": "function", "function": {"name": "read_file", "parameters": {}}}],
            handle=self.handle,
            answer=Answer,
            max_tool_calls=max_tool_calls,
            on_event=on_event,
            senior=senior,
        )


def test_tools_run_then_finish_returns_the_answer() -> None:
    script = Script(
        reply(call("read_file", {"path": "a.ts"})),
        reply(call("finish", {"summary": "done"})),
    )
    assert script.run() == Answer(summary="done")
    assert script.tool_calls == [("read_file", '{"path": "a.ts"}')]
    # The 2nd request carried the tool's result back to the model
    last = script.sent[1]["messages"][-1]
    assert last == {"role": "tool", "tool_call_id": "c1", "content": "result of read_file"}


def test_finish_tool_is_offered_with_the_answer_schema() -> None:
    script = Script(reply(call("finish", {"summary": "x"})))
    script.run()
    finish = script.sent[0]["tools"][-1]["function"]
    assert finish["name"] == "finish"
    assert finish["description"] == "Your final answer."
    assert finish["parameters"]["required"] == ["summary"]


def test_invalid_answer_goes_back_as_an_error() -> None:
    script = Script(
        reply(call("finish", {"summary": ""})),
        reply(call("finish", {"summary": "fixed"})),
    )
    assert script.run().summary == "fixed"
    assert script.sent[1]["messages"][-1]["content"].startswith("ERROR: your answer is not valid")


def test_tool_limit_refuses_tools_but_allows_finish() -> None:
    script = Script(
        reply(call("read_file", {"path": "a"})),
        reply(call("read_file", {"path": "b"})),
        reply(call("finish", {"summary": "ok"})),
    )
    assert script.run(max_tool_calls=1).summary == "ok"
    assert len(script.tool_calls) == 1  # the second read was refused
    assert "tool limit (1) reached" in script.sent[2]["messages"][-1]["content"]


def test_gives_up_when_the_model_never_finishes() -> None:
    script = Script(*[reply(call("read_file", {"path": "a"})) for _ in range(4)])
    with pytest.raises(AgentLoopError):
        script.run(max_tool_calls=1)


def test_nudges_a_model_that_stops_calling_tools() -> None:
    script = Script(
        reply(content="I think I'm done"),
        reply(call("finish", {"summary": "ok"})),
    )
    assert script.run().summary == "ok"
    assert (
        script.sent[1]["messages"][-1]["content"] == "Use a tool, or call finish with your answer."
    )


def test_gives_up_on_a_model_that_only_talks() -> None:
    script = Script(*[reply(content="hmm") for _ in range(3)])
    with pytest.raises(AgentLoopError, match="stopped calling tools"):
        script.run()


def test_lists_wrapped_as_item_objects_are_unwrapped() -> None:
    from agents.loop import unwrap_lists

    assert unwrap_lists({"criteria": {"item": "2"}}) == {"criteria": ["2"]}
    assert unwrap_lists({"a": {"item": ["1", "2"]}}) == {"a": ["1", "2"]}
    assert unwrap_lists({"changes": {"item": {"path": "x", "criteria": {"item": "1"}}}}) == {
        "changes": [{"path": "x", "criteria": ["1"]}]
    }
    assert unwrap_lists({"item": "x", "other": 1}) == {"item": "x", "other": 1}  # not a wrapper


def test_finish_with_wrapped_lists_is_accepted() -> None:
    class Listy(BaseModel):
        """Answer."""

        numbers: list[int]

    script = Script(reply(call("finish", {"numbers": {"item": "2"}})))
    answer = run_agent(
        script.router(),
        role=Role.PLANNER,
        agent_run_id=1,
        system="s",
        user="u",
        tools=[],
        handle=script.handle,
        answer=Listy,
    )
    assert answer.numbers == [2]


def test_a_cut_off_reply_gets_told_to_be_shorter() -> None:
    cut = reply(content=None)
    cut["choices"][0]["finish_reason"] = "length"
    script = Script(cut, reply(call("finish", {"summary": "ok"})))
    assert script.run().summary == "ok"
    assert "cut off at the output limit" in script.sent[1]["messages"][-1]["content"]


def test_a_rejected_finish_grants_extra_tool_calls() -> None:
    script = Script(
        reply(call("read_file", {"path": "a"})),  # uses the only call
        reply(call("finish", {"summary": ""})),  # rejected: +5 calls
        reply(call("read_file", {"path": "b"})),  # allowed thanks to the grace
        reply(call("finish", {"summary": "fixed"})),
    )
    assert script.run(max_tool_calls=1).summary == "fixed"
    assert [name for name, _ in script.tool_calls] == ["read_file", "read_file"]
    assert "5 extra tool calls granted" in script.sent[2]["messages"][-1]["content"]


def test_reports_each_step_as_an_event() -> None:
    events: list[tuple[EventKind, dict[str, Any]]] = []
    script = Script(
        reply(call("read_file", {"path": "a.ts"})),
        reply(call("finish", {"summary": ""})),  # rejected: too short
        reply(call("finish", {"summary": "done"})),
    )
    script.run(on_event=lambda kind, data: events.append((kind, data)))
    assert [kind for kind, _ in events] == [
        EventKind.TOOL_CALL,
        EventKind.FINISH_REJECTED,
        EventKind.AGENT_FINISHED,
    ]
    assert events[0][1] == {
        "role": Role.DEVELOPER,
        "tool": "read_file",
        "n": 1,
        "limit": 25,
        "arguments": '{"path": "a.ts"}',
    }
    assert "summary" in events[1][1]["error"]
    assert events[2][1] == {"role": Role.DEVELOPER, "tool_calls": 1}


def test_long_tool_arguments_are_shortened_in_events() -> None:
    events: list[dict[str, Any]] = []
    script = Script(
        reply(call("read_file", {"path": "x" * 1000})),
        reply(call("finish", {"summary": "done"})),
    )
    script.run(on_event=lambda _kind, data: events.append(data))
    assert len(events[0]["arguments"]) == 300


def test_ask_senior_sends_the_conversation_to_the_stronger_model() -> None:
    script = Script(
        reply(call("read_file", {"path": "a.ts"})),
        reply(call("ask_senior", {"question": "Why does lint fail?"}, "c2")),
        reply(content="Check the eslint config in a.ts."),  # the senior's answer
        reply(call("finish", {"summary": "done"}, "c3")),
    )
    assert script.run(senior=True) == Answer(summary="done")
    asked = script.sent[2]
    assert asked["model"] == "z-ai/glm-5.2"
    assert "tools" not in asked
    question = asked["messages"][1]["content"]
    assert "[user] task" in question  # the agent's task, in full
    assert "read_file" in question and "result of read_file" in question
    assert question.endswith("<question>\nWhy does lint fail?\n</question>")
    answer = script.sent[3]["messages"][-1]
    assert answer == {
        "role": "tool",
        "tool_call_id": "c2",
        "content": "Check the eslint config in a.ts.",
    }
    assert script.tool_calls == [("read_file", '{"path": "a.ts"}')]  # not a repo tool


def test_ask_senior_is_capped_and_off_by_default() -> None:
    script = Script(
        reply(call("ask_senior", {"question": "Help?"}, "a1")),
        reply(content="Senior 1"),
        reply(call("ask_senior", {"question": "Help?"}, "a2")),
        reply(content="Senior 2"),
        reply(call("ask_senior", {"question": "Help?"}, "a3")),
        reply(call("finish", {"summary": "done"})),
    )
    script.run(senior=True)
    third = script.sent[-1]["messages"][-1]["content"]
    assert third == "ERROR: you've asked the senior 2 times already."

    plain = Script(reply(call("finish", {"summary": "x"})))
    plain.run()
    assert [t["function"]["name"] for t in plain.sent[0]["tools"]] == ["read_file", "finish"]
