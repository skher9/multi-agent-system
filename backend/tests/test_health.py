import time

import pytest
from fastapi.testclient import TestClient

from api import health as health_module
from api.config import Settings
from api.health import NotConfiguredError, run_checks
from api.main import app

SETTINGS = Settings(_env_file=None)  # type: ignore[call-arg]


def ok_check(_: Settings) -> None:
    return None


def missing_check(_: Settings) -> None:
    raise NotConfiguredError("FAKE_KEY not set")


def broken_check(_: Settings) -> None:
    raise ConnectionError("connection refused")


def test_all_ok() -> None:
    report = run_checks({"a": ok_check, "b": ok_check}, SETTINGS)
    assert report.status == "ok"
    assert report.services["a"].status == "ok"


def test_one_failure_marks_report_degraded() -> None:
    report = run_checks(
        {"good": ok_check, "missing": missing_check, "broken": broken_check}, SETTINGS
    )
    assert report.status == "degraded"
    assert report.services["good"].status == "ok"
    assert report.services["missing"].status == "not_configured"
    assert report.services["broken"].status == "error"
    assert report.services["broken"].detail == "ConnectionError: connection refused"


def test_slow_check_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_module, "CHECK_TIMEOUT_SECONDS", 0.1)

    def slow_check(_: Settings) -> None:
        time.sleep(0.5)

    report = run_checks({"slow": slow_check}, SETTINGS)
    assert report.services["slow"].detail == "Timed out"


def test_health_endpoint_returns_503_when_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    # The route imported CHECKS by name, so patch it where the route looks it up.
    monkeypatch.setattr("api.routes.health.CHECKS", {"broken": broken_check})
    response = TestClient(app).get("/health")
    assert response.status_code == 503
    assert response.json()["services"]["broken"]["status"] == "error"


def test_openapi_spec_is_served() -> None:
    response = TestClient(app).get("/openapi.json")
    assert response.status_code == 200
    assert "/health" in response.json()["paths"]
