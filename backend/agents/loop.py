"""The agent loop: the model calls tools until it calls `finish` with its answer.

Each round sends the conversation so far, runs the tools the model asked for, and
adds their results. The answer is a pydantic form passed as the finish tool's
arguments; a form that doesn't validate goes back to the model as an error to fix.

Limits keep a confused model from spending forever: after max_tool_calls, every
tool except finish is refused, and a few rounds later the loop gives up.
"""

import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from agents.repo_tools import definitions
from llm_router.models import Role
from llm_router.router import LlmRouter

FINISH = "finish"
EXTRA_ROUNDS = 3  # rounds allowed after the tool limit for the model to call finish
MAX_IDLE_ROUNDS = 2  # replies with no tool call before giving up

ToolHandler = Callable[[str, str], str]  # (tool name, JSON arguments) -> text for the model


class AgentLoopError(Exception):
    """The model never produced a valid answer within the limits."""


def run_agent[T: BaseModel](
    router: LlmRouter,
    *,
    role: Role,
    agent_run_id: int,
    system: str,
    user: str,
    tools: list[dict[str, Any]],
    handle: ToolHandler,
    answer: type[T],
    max_tool_calls: int = 25,
    max_tokens: int | None = None,
) -> T:
    """Run the loop and return the model's validated answer."""
    all_tools = [*tools, *definitions({FINISH: answer})]
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    used = idle = 0
    for _ in range(max_tool_calls + EXTRA_ROUNDS):
        response = router.complete(
            role=role,
            messages=messages,
            agent_run_id=agent_run_id,
            tools=all_tools,
            max_tokens=max_tokens,
        )
        messages.append(
            {"role": "assistant", "content": response.content, "tool_calls": response.tool_calls}
            if response.tool_calls
            else {"role": "assistant", "content": response.content or ""}
        )
        if not response.tool_calls:
            idle += 1
            if idle > MAX_IDLE_ROUNDS:
                raise AgentLoopError("the model stopped calling tools without finishing")
            messages.append(
                {"role": "user", "content": f"Use a tool, or call {FINISH} with your answer."}
            )
            continue

        for call in response.tool_calls:
            name = call["function"]["name"]
            arguments = call["function"].get("arguments") or "{}"
            if name == FINISH:
                try:
                    return answer.model_validate(json.loads(arguments))
                except (json.JSONDecodeError, ValidationError) as exc:
                    result = (
                        f"ERROR: your answer is not valid, fix it and call {FINISH} again: {exc}"
                    )
            elif used >= max_tool_calls:
                result = f"ERROR: tool limit ({max_tool_calls}) reached. Call {FINISH} now."
            else:
                used += 1
                result = handle(name, arguments)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
    raise AgentLoopError(f"no valid answer after {max_tool_calls} tool calls")
