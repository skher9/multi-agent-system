"""Sandbox tests.

Unit tests check the docker command. Tests marked `docker` start real containers;
they need Docker, the mas-sandbox image, and npm-proxy running, and are skipped otherwise.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from services import sandbox
from services.sandbox import SandboxLimits, build_docker_command


def test_command_has_limits_and_locked_down_flags() -> None:
    cmd = build_docker_command(["node", "--version"], "n1", None, SandboxLimits())
    joined = " ".join(cmd)
    for flag in (
        "--rm",
        "--network mas-sandbox",
        "--cpus 2.0",
        "--memory 2g",
        "--memory-swap 2g",
        "--pids-limit 512",
        "--cap-drop ALL",
        "--security-opt no-new-privileges",
    ):
        assert flag in joined
    assert cmd[-3:] == ["mas-sandbox:latest", "node", "--version"]


def test_no_environment_is_passed_in(tmp_path: Path) -> None:
    cmd = build_docker_command(["true"], "n1", tmp_path, SandboxLimits())
    assert not any(arg in ("-e", "--env", "--env-file") for arg in cmd)


def _sandbox_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    checks = [
        ["docker", "image", "inspect", sandbox.IMAGE],
        ["docker", "container", "inspect", "npm-proxy"],
    ]
    return all(subprocess.run(c, capture_output=True).returncode == 0 for c in checks)  # noqa: S603


docker = pytest.mark.skipif(not _sandbox_ready(), reason="sandbox image or npm-proxy missing")


@docker
def test_node_runs_as_non_root() -> None:
    result = sandbox.run(["bash", "-c", "node --version && whoami"])
    assert result.exit_code == 0
    assert result.stdout.startswith("v")
    assert result.stdout.strip().endswith("pwuser")


@docker
def test_npm_registry_is_reachable(tmp_path: Path) -> None:
    result = sandbox.run(["npm", "view", "left-pad@1.3.0", "version"], workspace=tmp_path)
    assert result.exit_code == 0, result.stderr
    assert result.stdout.strip() == "1.3.0"


@docker
@pytest.mark.parametrize(
    "curl_args",
    [
        ["https://example.com"],  # through the proxy: refused
        ["--noproxy", "*", "https://example.com"],  # around the proxy: no route
        ["--noproxy", "*", "https://1.1.1.1"],  # raw IP: no route
        ["http://registry.npmjs.org.evil.example"],  # look-alike domain: refused
    ],
)
def test_everything_else_is_blocked(curl_args: list[str]) -> None:
    result = sandbox.run(["curl", "-sf", "--max-time", "8", *curl_args])
    assert result.exit_code != 0


@docker
def test_host_secrets_are_not_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-must-not-leak")
    result = sandbox.run(["env"])
    assert "sk-or-must-not-leak" not in result.stdout


@docker
def test_timeout_kills_the_container() -> None:
    result = sandbox.run(["sleep", "60"], limits=SandboxLimits(timeout_seconds=3))
    assert result.timed_out
    leftover = subprocess.run(  # noqa: S603
        ["docker", "ps", "-q", "--filter", "name=mas-sandbox-"],  # noqa: S607
        capture_output=True,
        text=True,
    )
    assert leftover.stdout.strip() == ""
