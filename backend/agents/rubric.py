"""The code-quality rubric (rubric.md) as code: its five areas, its two thresholds, and
the evidence rule. Shared by the reviewer (which sends work back) and the grader (which
measures it), so both judge by the same standard.
"""

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RUBRIC = Path(__file__).with_name("rubric.md")
BAR = 7  # every area at or above this: the change meets the bar
FLOOR = 6  # an area below this sends the change back
MIN_QUOTE_CHARS = 8  # shorter quotes match almost anywhere

Area = Literal["correctness", "tests", "readability", "fits_the_repo", "robustness"]
AREAS: tuple[Area, ...] = ("correctness", "tests", "readability", "fits_the_repo", "robustness")
HTML_COMMENT = re.compile(r"<!--.*?-->\n?", re.DOTALL)


class AreaScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    area: Area
    score: int = Field(ge=1, le=10)
    reason: str = Field(min_length=1, max_length=600, description="One or two sentences: why")
    raise_by_one: str = Field(
        min_length=1,
        max_length=600,
        description="The one change that would raise this score by a point",
    )


def rubric_text() -> str:
    """The rubric as the agents read it (notes for people, in HTML comments, left out)."""
    return HTML_COMMENT.sub("", RUBRIC.read_text()).strip()


def find_quote(text: str, quote: str) -> int:
    """The 1-based line where `quote` starts in `text`, comparing with spaces and line
    breaks squeezed (models reflow indentation); 0 if it isn't there."""
    wanted = _squeeze(quote)
    if len(wanted) < MIN_QUOTE_CHARS:
        return 0
    pieces: list[str] = []
    starts: list[tuple[int, int]] = []  # (offset in the squeezed text, line number)
    offset = 0
    for number, line in enumerate(text.splitlines(), start=1):
        squeezed = _squeeze(line)
        if squeezed:
            starts.append((offset, number))
            pieces.append(squeezed)
            offset += len(squeezed) + 1
    found = " ".join(pieces).find(wanted)
    if found < 0:
        return 0
    return max(number for start, number in starts if start <= found)


def _squeeze(text: str) -> str:
    return " ".join(text.split())
