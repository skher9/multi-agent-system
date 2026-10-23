"""Run agent-written code in a throwaway Docker container.

Every developer/tester run gets a fresh container from the mas-sandbox image,
removed afterwards. Defence in layers:
- network: only the internal mas-sandbox network, whose sole way out is the
  npm-only proxy (see docker-compose.yml and sandbox/proxy/squid.conf)
- limits: CPU, memory (no swap), process count, wall-clock time
- privileges: non-root user, all Linux capabilities dropped, no privilege escalation
- secrets: none. `docker run` does not inherit the host environment, and we
  pass no --env flags, so backend/.env never reaches the container.

Requires: `docker compose up -d` (for npm-proxy) and `docker build -t mas-sandbox sandbox`.
"""

import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

IMAGE = "mas-sandbox:latest"
NETWORK = "mas-sandbox"
CONTAINER_WORKDIR = "/workspace"


@dataclass(frozen=True)
class SandboxLimits:
    cpus: float = 2.0
    memory: str = "2g"
    pids: int = 512  # stops fork bombs
    timeout_seconds: int = 30 * 60  # matches the 30-minute story-run limit


@dataclass(frozen=True)
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool


def build_docker_command(
    command: list[str], name: str, workspace: Path | None, limits: SandboxLimits
) -> list[str]:
    """The exact `docker run` invocation. Kept separate so tests can inspect it."""
    args = [
        "docker", "run",
        "--rm",                                    # delete the container when it exits
        "--name", name,
        "--network", NETWORK,                      # internal network: npm proxy only
        "--cpus", str(limits.cpus),
        "--memory", limits.memory,
        "--memory-swap", limits.memory,            # same as memory = no swap
        "--pids-limit", str(limits.pids),
        "--cap-drop", "ALL",                       # no Linux capabilities
        "--security-opt", "no-new-privileges",     # can't regain root via setuid
        "--workdir", CONTAINER_WORKDIR,
    ]  # fmt: skip
    if workspace is not None:
        args += ["--volume", f"{workspace.resolve()}:{CONTAINER_WORKDIR}"]
    return [*args, IMAGE, *command]


def run(
    command: list[str],
    workspace: Path | None = None,
    limits: SandboxLimits = SandboxLimits(),  # noqa: B008  (frozen dataclass: safe default)
) -> SandboxResult:
    """Run `command` (a list, never a shell string) inside a fresh sandbox container."""
    name = f"mas-sandbox-{uuid.uuid4().hex[:12]}"
    docker_cmd = build_docker_command(command, name, workspace, limits)
    try:
        done = subprocess.run(  # noqa: S603  (fixed binary, list args, no shell)
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=limits.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        # Stopping the docker CLI does NOT stop the container. Kill it explicitly.
        subprocess.run(["docker", "kill", name], capture_output=True, check=False)  # noqa: S603, S607
        return SandboxResult(
            exit_code=-1,
            stdout=_text(exc.stdout),
            stderr=_text(exc.stderr),
            timed_out=True,
        )
    return SandboxResult(done.returncode, done.stdout, done.stderr, timed_out=False)


def _text(output: str | bytes | None) -> str:
    if output is None:
        return ""
    return output.decode(errors="replace") if isinstance(output, bytes) else output
