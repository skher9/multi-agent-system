from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.config import Settings, get_settings
from api.main import app
from services.realtime import PusherCredentials, Realtime

CREDS = PusherCredentials(app_id="1", key="key", secret="secret", cluster="ap2")


def test_send_passes_channel_event_and_data(monkeypatch: pytest.MonkeyPatch) -> None:
    realtime = Realtime(CREDS)
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(realtime._client, "trigger", lambda *args: calls.append(args))
    realtime.send("project-1", "stage-changed", {"stage": "review"})
    assert calls == [("project-1", "stage-changed", {"stage": "review"})]


def test_test_endpoint_returns_503_when_not_configured() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)  # type: ignore[call-arg]
    try:
        response = TestClient(app).post("/realtime/test")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
