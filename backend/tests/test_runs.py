"""POST /runs, the run_ticket task, and open_pipeline's settings check. No real queue or network."""

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.main import app
from orchestrator.projects import NotReadyError
from orchestrator.runner import AlreadyRunningError
from orchestrator.wiring import NotConfiguredError, open_pipeline
from workers import tasks
from workers.celery_app import celery_app

client = TestClient(app)


def test_start_run_queues_the_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[str, list[Any]]] = []

    def fake_send(name: str, args: list[Any]) -> SimpleNamespace:
        sent.append((name, args))
        return SimpleNamespace(id="job-9")

    monkeypatch.setattr(celery_app, "send_task", fake_send)
    response = client.post("/runs", json={"ticket": "KAN-4"})
    assert response.status_code == 202
    assert response.json() == {"job_id": "job-9"}
    assert sent == [("run_ticket", ["KAN-4", False, "", None])]
    design = "https://www.figma.com/design/AbC123xyz456/Shop?node-id=1-2"
    response = client.post("/runs", json={"ticket": "KAN-4", "figma_url": f" {design} "})
    assert response.status_code == 202
    assert sent[-1] == ("run_ticket", ["KAN-4", False, design, None])


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.io/design/AbC123xyz456",
        "https://www.figma.com/design/AbC123xyz456/x javascript:alert(1)",
        "not a link",
    ],
)
def test_start_run_rejects_non_figma_links(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    monkeypatch.setattr(celery_app, "send_task", lambda *a, **k: pytest.fail("queued"))
    assert client.post("/runs", json={"ticket": "KAN-4", "figma_url": url}).status_code == 422


def test_plan_decision_queues_the_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[str, list[Any]]] = []
    monkeypatch.setattr(
        celery_app,
        "send_task",
        lambda name, args: sent.append((name, args)) or SimpleNamespace(id="j"),
    )
    body = {"decision": "revise", "feedback": "Use the existing Button"}
    assert client.post("/runs/KAN-4/plan-decision", json=body).status_code == 202
    assert sent == [("decide_plan", ["KAN-4", body, None])]


def test_learn_queues_the_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[str, list[Any]]] = []
    monkeypatch.setattr(
        celery_app,
        "send_task",
        lambda name, args: sent.append((name, args)) or SimpleNamespace(id="j"),
    )
    assert client.post("/learn", json={"pr": 3}).status_code == 202
    assert client.post("/learn", json={"pr": 0}).status_code == 422
    assert sent == [("learn_from_pr", [3])]


@pytest.mark.parametrize(
    ("ticket", "body"),
    [("kan-4", {"decision": "approve"}), ("KAN-4", {"decision": "maybe"})],
)
def test_plan_decision_rejects_bad_input(
    monkeypatch: pytest.MonkeyPatch, ticket: str, body: dict[str, str]
) -> None:
    monkeypatch.setattr(celery_app, "send_task", lambda *a, **k: pytest.fail("queued"))
    assert client.post(f"/runs/{ticket}/plan-decision", json=body).status_code == 422


@pytest.mark.parametrize("ticket", ["kan-4", "KAN-4\n", "KAN-4/../x", "", "KAN"])
def test_start_run_rejects_bad_keys(monkeypatch: pytest.MonkeyPatch, ticket: str) -> None:
    monkeypatch.setattr(celery_app, "send_task", lambda *a, **k: pytest.fail("queued"))
    assert client.post("/runs", json={"ticket": ticket}).status_code == 422


def test_run_ticket_task_returns_the_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    @contextmanager
    def fake_open(settings: Any, project_id: int | None = None):
        yield "pipeline"

    monkeypatch.setattr(tasks, "open_pipeline", fake_open)
    monkeypatch.setattr(
        tasks,
        "run_ticket",
        lambda p, key, approve_plan, figma_url: {
            "outcome": f"{p}:{key}:{approve_plan}:{figma_url}"
        },
    )
    assert tasks.run_ticket_task("KAN-4", True) == "pipeline:KAN-4:True:"
    assert tasks.run_ticket_task("KAN-4", False, "f") == "pipeline:KAN-4:False:f"


def test_run_ticket_task_skips_when_already_running(monkeypatch: pytest.MonkeyPatch) -> None:
    @contextmanager
    def fake_open(settings: Any, project_id: int | None = None):
        yield "pipeline"

    def busy(pipeline: Any, key: str, **_: Any) -> None:
        raise AlreadyRunningError(key)

    monkeypatch.setattr(tasks, "open_pipeline", fake_open)
    monkeypatch.setattr(tasks, "run_ticket", busy)
    assert tasks.run_ticket_task("KAN-4") == "already_running"


def test_run_ticket_task_on_a_disconnected_project(monkeypatch: pytest.MonkeyPatch) -> None:
    @contextmanager
    def not_ready(settings: Any, project_id: int | None = None):
        raise NotReadyError("connect both Jira and GitHub first")
        yield

    monkeypatch.setattr(tasks, "open_pipeline", not_ready)
    assert tasks.run_ticket_task("ACME-1", project_id=5) == "not_connected"


def test_open_pipeline_names_every_missing_setting() -> None:
    settings = Settings(_env_file=None, openrouter_api_key="k")  # type: ignore[call-arg]
    with pytest.raises(NotConfiguredError) as error, open_pipeline(settings):
        pass
    assert str(error.value) == (
        "DATABASE_URL, JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, AGENT_REPO, AGENT_OWNER_EMAIL, "
        "GITHUB_TOKEN, R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET"
    )
