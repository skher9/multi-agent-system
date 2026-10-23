"""Job API tests. The queue is faked here; the real worker is checked by hand (see README)."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.main import app
from workers.celery_app import celery_app
from workers.tasks import ping

client = TestClient(app)


def test_ping_task_returns_pong() -> None:
    assert ping() == "pong"  # calling a task directly runs it here, no queue


def test_start_ping_returns_202_and_job_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(celery_app, "send_task", lambda name: SimpleNamespace(id="job-123"))
    response = client.post("/jobs/ping")
    assert response.status_code == 202
    assert response.json() == {"job_id": "job-123"}


def test_get_job_reports_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(
        failed=lambda: False, successful=lambda: True, status="SUCCESS", result="pong"
    )
    monkeypatch.setattr("api.routes.jobs.AsyncResult", lambda *a, **k: fake)
    response = client.get("/jobs/job-123")
    assert response.json() == {"job_id": "job-123", "status": "SUCCESS", "result": "pong"}


def test_get_job_hides_failure_details(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(
        failed=lambda: True, status="FAILURE", result=ValueError("secret-ish detail")
    )
    monkeypatch.setattr("api.routes.jobs.AsyncResult", lambda *a, **k: fake)
    body = client.get("/jobs/job-123").json()
    assert body["result"] == "ValueError"
    assert "secret-ish" not in str(body)
