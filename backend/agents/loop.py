"""The agent loop: the model calls tools until it calls `finish` with its answer.

Each round sends the conversation so far, runs the tools the model asked for, and
adds their results. The answer is a pydantic form passed as the finish tool's
arguments; a form that doesn't validate goes back to the model as an error to fix.

Limits keep a confused model from spending forever: after max_tool_calls, every
tool except finish is refused, and a few rounds later the loop gives up.
"""

import json
import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from agents.repo_tools import definitions
from llm_router.models import Role
from llm_router.router import LlmRouter

logger = logging.getLogger(__name__)

FINISH = "finish"
WARN_WHEN_LEFT = 5  # tell the model to wrap up when this many tool calls remain
# Each rejected finish gives back a few tool calls (up to a cap), so the model always has
# room to fix what the checks found, e.g. one lint error found on the last call.
GRACE_PER_REJECTION = 5
MAX_GRACE = 15
EXTRA_ROUNDS = 3  # rounds allowed after the tool limit for the model to call finish
MAX_IDLE_ROUNDS = 2  # replies with no tool call before giving up

ToolHandler = Callable[[str, str], str]  # (tool name, JSON arguments) -> text for the model


def unwrap_lists(value: Any) -> Any:
    """Undo a model quirk: MiniMax sometimes sends a list as {"item": x} or {"item": [x, y]}
    in tool arguments. No form of ours has a field named "item", so this is safe."""
    if isinstance(value, dict):
        if set(value) == {"item"}:
            inner = unwrap_lists(value["item"])
            return inner if isinstance(inner, list) else [inner]
        return {key: unwrap_lists(item) for key, item in value.items()}
    if isinstance(value, list):
        return [unwrap_lists(item) for item in value]
    return value


def _clean_arguments(arguments: str) -> str:
    """Tool arguments with unwrap_lists applied; left as is if they aren't valid JSON."""
    try:
        return json.dumps(unwrap_lists(json.loads(arguments)))
    except json.JSONDecodeError:
        return arguments


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
    used = idle = grace = rounds = 0
    # The round limit grows with the grace actually granted, not the most it could be
    while rounds < max_tool_calls + grace + EXTRA_ROUNDS:
        rounds += 1
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
            logger.info(
                "%s: replied without a tool call (%s): %.200s",
                role,
                response.finish_reason,
                response.content,
            )
            idle += 1
            if idle > MAX_IDLE_ROUNDS:
                raise AgentLoopError("the model stopped calling tools without finishing")
            if response.finish_reason == "length":
                # Hit the output limit mid-reply: the tool call was cut off, not skipped
                nudge = (
                    "Your reply was cut off at the output limit. Think less and keep each "
                    f"field short, then call {FINISH} (or a tool) again."
                )
            else:
                nudge = f"Use a tool, or call {FINISH} with your answer."
            messages.append({"role": "user", "content": nudge})
            continue

        for call in response.tool_calls:
            name = call["function"]["name"]
            arguments = _clean_arguments(call["function"].get("arguments") or "{}")
            if name == FINISH:
                try:
                    result_answer = answer.model_validate(json.loads(arguments))
                    logger.info("%s: finished after %d tool calls", role, used)
                    return result_answer
                except (json.JSONDecodeError, ValidationError) as exc:
                    logger.info("%s: finish rejected: %.3000s", role, exc)
                    extra = min(GRACE_PER_REJECTION, MAX_GRACE - grace)
                    grace += extra
                    result = (
                        f"ERROR: your answer is not valid, fix it and call {FINISH} again: {exc}"
                    )
                    if extra:
                        result += f"\n\n[{extra} extra tool calls granted to fix this.]"
            elif used >= max_tool_calls + grace:
                logger.info("%s: refused %s, tool limit reached", role, name)
                result = f"ERROR: tool limit ({max_tool_calls}) reached. Call {FINISH} now."
            else:
                used += 1
                logger.info("%s: tool %d/%d %s %.120s", role, used, max_tool_calls, name, arguments)
                result = handle(name, arguments)
                left = max_tool_calls + grace - used
                if left <= WARN_WHEN_LEFT:
                    result += (
                        f"\n\n[{left} tool calls left. Call {FINISH} soon with what you know.]"
                    )
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
    raise AgentLoopError(f"no valid answer after {used} tool calls")
