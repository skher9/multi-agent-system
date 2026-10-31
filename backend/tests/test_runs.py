"""POST /runs, the run_ticket task, and open_pipeline's settings check. No real queue or network."""

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.main import app
from orchestrator.runner import AlreadyRunningError
from orchestrator.wiring import NotConfiguredError, open_pipeline
from workers import tasks
from workers.celery_app import celery_app

client = TestClient(app)


def test_start_run_queues_the_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[str, list[str]]] = []

    def fake_send(name: str, args: list[str]) -> SimpleNamespace:
        sent.append((name, args))
        return SimpleNamespace(id="job-9")

    monkeypatch.setattr(celery_app, "send_task", fake_send)
    response = client.post("/runs", json={"ticket": "KAN-4"})
    assert response.status_code == 202
    assert response.json() == {"job_id": "job-9"}
    assert sent == [("run_ticket", ["KAN-4"])]


@pytest.mark.parametrize("ticket", ["kan-4", "KAN-4\n", "KAN-4/../x", "", "KAN"])
def test_start_run_rejects_bad_keys(monkeypatch: pytest.MonkeyPatch, ticket: str) -> None:
    monkeypatch.setattr(celery_app, "send_task", lambda *a, **k: pytest.fail("queued"))
    assert client.post("/runs", json={"ticket": ticket}).status_code == 422


def test_run_ticket_task_returns_the_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    @contextmanager
    def fake_open(settings: Any):
        yield "pipeline"

    monkeypatch.setattr(tasks, "open_pipeline", fake_open)
    monkeypatch.setattr(tasks, "run_ticket", lambda p, key: {"outcome": f"{p}:{key}"})
    assert tasks.run_ticket_task("KAN-4") == "pipeline:KAN-4"


def test_run_ticket_task_skips_when_already_running(monkeypatch: pytest.MonkeyPatch) -> None:
    @contextmanager
    def fake_open(settings: Any):
        yield "pipeline"

    def busy(pipeline: Any, key: str) -> None:
        raise AlreadyRunningError(key)

    monkeypatch.setattr(tasks, "open_pipeline", fake_open)
    monkeypatch.setattr(tasks, "run_ticket", busy)
    assert tasks.run_ticket_task("KAN-4") == "already_running"


def test_open_pipeline_names_every_missing_setting() -> None:
    settings = Settings(_env_file=None, openrouter_api_key="k")  # type: ignore[call-arg]
    with pytest.raises(NotConfiguredError) as error, open_pipeline(settings):
        pass
    assert str(error.value) == (
        "DATABASE_URL, JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, AGENT_REPO, AGENT_OWNER_EMAIL"
    )
