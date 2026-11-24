"""QA's recordings: the recording config, reading Playwright's report, the video route."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents import recordings
from agents.repo_tools import RepoTools
from api.main import app
from api.routes import recordings as route
from services.sandbox import SandboxResult
from services.workspace import Workspace
from tests.test_workspace import origin  # noqa: F401  (origin is a fixture)

TOKEN = "t" * 32


def test_record_config_extends_the_repos_config() -> None:
    config = recordings.record_config("playwright.config.ts")
    assert 'import base from "./playwright.config";' in config
    assert "...base," in config and 'mode: "on"' in config
    assert '"/mas-recordings/report.json"' in config
    assert 'from "./playwright.config.mjs"' in recordings.record_config("playwright.config.mjs")
    assert 'from "./playwright.config.mjs"' in recordings.record_config("playwright.config.mts")


def test_report_is_read_through_nested_suites_and_videos_stay_inside(tmp_path: Path) -> None:
    video = tmp_path / "results" / "a" / "video.webm"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"webm")
    outside = tmp_path.parent / "secret.webm"
    outside.write_bytes(b"no")

    def spec(title: str, ok: bool, path: str, message: str = "") -> dict[str, object]:
        result = {
            "duration": 2340,
            "errors": [{"message": message}] if message else [],
            "attachments": [{"name": "trace", "path": "x"}, {"name": "video", "path": path}],
        }
        return {"title": title, "file": "a.spec.ts", "ok": ok, "tests": [{"results": [result]}]}

    report = {
        "suites": [
            {
                "specs": [spec("shows the form", True, "/mas-recordings/results/a/video.webm")],
                "suites": [
                    {
                        "specs": [
                            spec(
                                "escapes",
                                False,
                                "/mas-recordings/../secret.webm",
                                "\x1b[31mno\x1b[0m",
                            ),
                            spec("elsewhere", True, "/etc/passwd"),
                        ]
                    }
                ],
            }
        ]
    }
    (tmp_path / "report.json").write_text(json.dumps(report))
    form, escapes, elsewhere = recordings.read_report(tmp_path) or []
    assert (form.title, form.passed, form.seconds, form.video) == (
        "shows the form",
        True,
        2.3,
        video.resolve(),
    )
    assert (escapes.passed, escapes.error, escapes.video) == (False, "no", None)
    assert elsewhere.video is None
    assert recordings.read_report(tmp_path / "nowhere") is None


def test_publish_names_videos_by_position_and_skips_missing_ones(tmp_path: Path) -> None:
    video = tmp_path / "v.webm"
    video.write_bytes(b"webm")
    uploads: dict[str, tuple[bytes, str]] = {}

    class Store:
        def upload(self, key: str, data: bytes, content_type: str = "") -> None:
            uploads[key] = (data, content_type)

    assert recordings.publish(Store(), [None, video], TOKEN) == ["", f"{TOKEN}/2.webm"]
    assert uploads == {f"recordings/{TOKEN}/2.webm": (b"webm", "video/webm")}


def fake_sandbox(monkeypatch: pytest.MonkeyPatch, runs: list[str]) -> None:
    """Fake sandbox: notes each command; a recorded run writes a report unless told not to."""

    def run(
        self: Workspace, command: list[str], limits: object = None, **kwargs: object
    ) -> SandboxResult:
        runs.append(command[-1])
        mounts = kwargs.get("extra_mounts") or ()
        assert (self.path / recordings.RECORD_CONFIG).is_file() == bool(mounts)
        if mounts and "broken" not in runs:
            (mounts[0][0] / recordings.REPORT).write_text("{}")  # type: ignore[index]
        return SandboxResult(0 if "broken" not in runs or not mounts else 1, "ok", "", False)

    monkeypatch.setattr(Workspace, "run", run)


def test_a_recorded_run_uses_a_temporary_config_and_falls_back(
    origin: str,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runs: list[str] = []
    fake_sandbox(monkeypatch, runs)
    with Workspace.clone(origin) as ws:
        tools = RepoTools(ws, typecheck_after_edit=False)
        # No Playwright config in the repo: a plain run
        assert tools.run_e2e(tmp_path) == (0, "ok")
        assert runs == ["pnpm test:e2e"]

        (ws.path / "playwright.config.ts").write_text("export default {}\n")
        (tmp_path / "old.json").write_text("stale")
        assert tools.run_e2e(tmp_path) == (0, "ok")
        assert runs[-1] == "pnpm test:e2e -c playwright.mas.config.ts"
        assert not (ws.path / recordings.RECORD_CONFIG).exists()  # deleted after the run
        assert not (tmp_path / "old.json").exists()  # the folder was emptied first

        # The recording config breaks the run (no report): run again without it
        runs.append("broken")
        assert tools.run_e2e(tmp_path) == (0, "ok")
        assert runs[-2:] == ["pnpm test:e2e -c playwright.mas.config.ts", "pnpm test:e2e"]


def test_recording_route_serves_the_video_with_ranges(monkeypatch: pytest.MonkeyPatch) -> None:
    class Store:
        def download(self, key: str) -> bytes:
            if key != f"recordings/{TOKEN}/1.webm":
                from botocore.exceptions import ClientError

                raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
            return b"0123456789"

    monkeypatch.setattr(route, "r2_from_settings", lambda settings: Store())
    client = TestClient(app)
    whole = client.get(f"/recordings/{TOKEN}/1.webm")
    assert (whole.status_code, whole.content) == (200, b"0123456789")
    assert whole.headers["content-type"] == "video/webm"
    assert whole.headers["accept-ranges"] == "bytes"
    part = client.get(f"/recordings/{TOKEN}/1.webm", headers={"Range": "bytes=2-5"})
    assert (part.status_code, part.content) == (206, b"2345")
    assert part.headers["content-range"] == "bytes 2-5/10"
    tail = client.get(f"/recordings/{TOKEN}/1.webm", headers={"Range": "bytes=-3"})
    assert tail.content == b"789"
    assert client.get(f"/recordings/{TOKEN}/2.webm").status_code == 404
    assert client.get("/recordings/short/1.webm").status_code == 422
    assert client.get(f"/recordings/{TOKEN}/1.mp4").status_code == 422


def test_agent_output_inlines_the_failure_snapshot_and_hides_our_paths(tmp_path: Path) -> None:
    failed = tmp_path / "results" / "footer-home-link-chromium"
    failed.mkdir(parents=True)
    (failed / "error-context.md").write_text('- link "Home" [ref=e3]\n')
    output = (
        "> playwright test -c playwright.mas.config.ts\n"
        "Error Context: ../mas-recordings/results/footer-home-link-chromium/error-context.md\n"
        "1 failed"
    )
    text = recordings.agent_output(output, tmp_path)
    assert "playwright.mas.config.ts" not in text and "mas-recordings" not in text
    assert "> playwright test\n" in text and "1 failed" in text
    assert '--- Page when footer-home-link-chromium failed ---\n- link "Home" [ref=e3]' in text
    assert recordings.agent_output("2 passed", tmp_path / "none") == "2 passed"
