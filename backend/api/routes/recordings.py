"""QA's recordings: the video of each browser test, linked from the agent's PR.

No login: a PR reviewer on GitHub isn't a website user. Each run's videos sit behind a
long random token (192 bits), so a link works for whoever was given it and can't be
guessed. Videos show only the app under test running in the sandbox.
"""

import re
from typing import Annotated

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi import Path as PathParam

from agents.recordings import KEY_PREFIX, VIDEO_TYPE
from api.config import Settings, get_settings
from api.health import NotConfiguredError
from api.health_checks import r2_from_settings

router = APIRouter(prefix="/recordings", tags=["recordings"])

RANGE = re.compile(r"bytes=(\d*)-(\d*)")


@router.get(
    "/{token}/{name}",
    response_class=Response,
    responses={200: {"content": {VIDEO_TYPE: {}}}, 206: {"content": {VIDEO_TYPE: {}}}},
)
def recording(
    token: Annotated[str, PathParam(pattern=r"^[A-Za-z0-9_-]{24,64}$")],
    name: Annotated[str, PathParam(pattern=r"^\d{1,3}\.webm$")],
    settings: Annotated[Settings, Depends(get_settings)],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> Response:
    """One test's video. Answers byte ranges, which browsers need to seek (and Safari
    needs to play at all)."""
    try:
        data = r2_from_settings(settings).download(f"{KEY_PREFIX}/{token}/{name}")
    except (NotConfiguredError, ClientError, BotoCoreError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such recording") from exc
    headers = {
        "Accept-Ranges": "bytes",
        # A recording never changes, and its address is secret: private cache only
        "Cache-Control": "private, max-age=86400, immutable",
        "Content-Disposition": f'inline; filename="{name}"',
        "X-Content-Type-Options": "nosniff",
    }
    wanted = _range(range_header, len(data))
    if wanted is None:
        return Response(data, media_type=VIDEO_TYPE, headers=headers)
    first, last = wanted
    headers["Content-Range"] = f"bytes {first}-{last}/{len(data)}"
    return Response(
        data[first : last + 1],
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        media_type=VIDEO_TYPE,
        headers=headers,
    )


def _range(header: str | None, size: int) -> tuple[int, int] | None:
    """The first and last byte a Range header asks for; None: send the whole file."""
    match = RANGE.fullmatch(header.strip()) if header else None
    if match is None or size == 0:
        return None
    start, end = match.groups()
    if not start and not end:
        return None
    if not start:  # "bytes=-500": the last 500 bytes
        first, last = max(size - int(end), 0), size - 1
    else:
        first, last = int(start), min(int(end), size - 1) if end else size - 1
    return (first, last) if first <= last < size else None
