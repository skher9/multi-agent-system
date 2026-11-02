"""Answers a human gives a paused run. Its own module, so the API can check them without
importing the agents (the API process stays light; agents run in the worker)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PlanDecision(BaseModel):
    """A human's answer to a paused plan."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "revise", "reject"]
    feedback: str = Field(default="", max_length=4000)  # what to change, for revise
