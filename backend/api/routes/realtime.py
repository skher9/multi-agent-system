"""Setup test for live updates: the web page listens, this endpoint sends."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.auth import current_user
from api.config import Settings, get_settings
from api.health import NotConfiguredError
from api.health_checks import realtime_from_settings

# Logged-in website users only (api/auth.py)
router = APIRouter(prefix="/realtime", tags=["realtime"], dependencies=[Depends(current_user)])

TEST_CHANNEL = "setup-test"
TEST_EVENT = "ping"


class TestEventSent(BaseModel):
    channel: str
    event: str
    sent_at: datetime


@router.post("/test")
def send_test_event(settings: Annotated[Settings, Depends(get_settings)]) -> TestEventSent:
    try:
        realtime = realtime_from_settings(settings)
    except NotConfiguredError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"Pusher not configured: {exc}"
        ) from exc
    sent_at = datetime.now(UTC)
    realtime.send(TEST_CHANNEL, TEST_EVENT, {"sent_at": sent_at.isoformat()})
    return TestEventSent(channel=TEST_CHANNEL, event=TEST_EVENT, sent_at=sent_at)
