"""Recordings of QA's browser tests: a video of every test, with the clicks shown.

The repo's own Playwright config stays untouched. For a recorded run we put a second
config next to it (deleted right after) that imports the repo's and only adds:
- video on for every test, with each click and step drawn on the picture;
- a JSON report, so our code reads which test passed instead of trusting the agent;
- an output folder outside the repo (mounted from the host), so nothing is committed.

After the run: read_report() gives one BrowserTest per test, and publish() uploads the
videos to storage. A repo without a Playwright config, or a Playwright too old for this
config, simply gets an unrecorded run (see RepoTools.run_e2e).
"""

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

MOUNT = "/mas-recordings"  # where the host's recordings folder appears in the sandbox
REPORT = "report.json"
RECORD_CONFIG = "playwright.mas.config.ts"
# The repo's config, in the order Playwright itself looks for it
BASE_CONFIGS = (
    "playwright.config.ts",
    "playwright.config.mts",
    "playwright.config.js",
    "playwright.config.mjs",
    "playwright.config.cjs",
)
VIDEO_TYPE = "video/webm"
MAX_VIDEO_BYTES = 20_000_000  # a longer recording than this isn't uploaded
MAX_ERROR_CHARS = 600
ANSI = re.compile(r"\x1b\[[0-9;]*m")
KEY_PREFIX = "recordings"


class Storage(Protocol):
    """The part of R2Storage this module uses (tests pass an in-memory fake)."""

    def upload(self, key: str, data: bytes, content_type: str = ...) -> None: ...


@dataclass(frozen=True)
class BrowserTest:
    """One Playwright test, as its JSON report describes the last attempt."""

    title: str
    file: str
    passed: bool
    seconds: float = 0.0
    video: Path | None = None  # on the host, inside the recordings folder
    error: str = ""


def base_config(root: Path) -> str | None:
    """The repo's Playwright config file name, or None if it has none."""
    return next((name for name in BASE_CONFIGS if (root / name).is_file()), None)


def record_config(base: str) -> str:
    """The recording config's source: the repo's config plus video and a JSON report."""
    # TypeScript and plain .js resolve without the extension; .mts/.mjs/.cjs need it
    module = base.rsplit(".", 1)[0] if base.endswith((".ts", ".js")) else base
    if base.endswith(".mts"):
        module = base.removesuffix(".mts") + ".mjs"  # how TypeScript spells that import
    return f"""\
// Written for one recorded run by the QA pipeline, then deleted. Not part of the repo.
import base from "./{module}";

export default {{
  ...base,
  outputDir: "{MOUNT}/results",
  reporter: [["list"], ["json", {{ outputFile: "{MOUNT}/{REPORT}" }}]],
  use: {{
    ...(base.use ?? {{}}),
    video: {{
      mode: "on",
      size: {{ width: 1280, height: 720 }},
      // Draw the pointer and each action on the video, and name the step being run
      show: {{
        // At the bottom: page headings and navigation usually sit at the top
        actions: {{ cursor: "pointer", position: "bottom-right" }},
        test: {{ level: "step", position: "bottom-left" }},
      }},
    }},
  }},
}};
"""


def clear(folder: Path) -> None:
    """Empty the recordings folder before a run, so an old report is never read as new."""
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o777)  # the sandbox's non-root user writes here  # noqa: S103
    for child in folder.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def read_report(folder: Path) -> list[BrowserTest] | None:
    """Every test in the run's JSON report, or None if there's no readable report.
    The report comes from the sandbox, so nothing in it is trusted: a video path must
    stay inside the recordings folder."""
    try:
        report = json.loads((folder / REPORT).read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(report, dict):
        return None
    tests: list[BrowserTest] = []
    for suite in report.get("suites", []):
        _collect(suite, folder.resolve(), tests)
    return tests


def _collect(suite: Any, folder: Path, found: list[BrowserTest]) -> None:
    if not isinstance(suite, dict):
        return
    for spec in suite.get("specs", []):
        results = [r for t in spec.get("tests", []) for r in t.get("results", [])]
        last = results[-1] if results else {}
        errors = last.get("errors") or []
        message = str(errors[0].get("message", "")) if errors else ""
        found.append(
            BrowserTest(
                title=str(spec.get("title", "")),
                file=str(spec.get("file", "")),
                passed=bool(spec.get("ok")),
                seconds=round(float(last.get("duration", 0)) / 1000, 1),
                video=_video(last.get("attachments", []), folder),
                error=ANSI.sub("", message).strip()[:MAX_ERROR_CHARS],
            )
        )
    for child in suite.get("suites", []):
        _collect(child, folder, found)


def _video(attachments: Any, folder: Path) -> Path | None:
    for attachment in attachments if isinstance(attachments, list) else []:
        if attachment.get("name") != "video":
            continue
        inside = PurePosixPath(str(attachment.get("path", "")))
        if not inside.is_relative_to(MOUNT):
            continue
        path = (folder / inside.relative_to(MOUNT)).resolve()
        if path.is_relative_to(folder) and path.is_file() and not path.is_symlink():
            return path
    return None


def publish(storage: Storage, videos: list[Path | None], token: str) -> list[str]:
    """Upload each video as recordings/<token>/<n>.webm. Returns, in the same order,
    "<token>/<n>.webm" for each uploaded one and "" for a missing or too-big one."""
    names = []
    for number, video in enumerate(videos, 1):
        if video is None or video.stat().st_size > MAX_VIDEO_BYTES:
            names.append("")
            continue
        name = f"{token}/{number}.webm"
        storage.upload(f"{KEY_PREFIX}/{name}", video.read_bytes(), VIDEO_TYPE)
        names.append(name)
    return names
