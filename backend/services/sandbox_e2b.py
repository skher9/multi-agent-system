"""Run agent-written code in E2B cloud sandboxes (Firecracker microVMs) instead of local Docker.

For hosts where the worker can't start containers (Railway). Same contract as the
Docker backend in sandbox.py, and the same layers:
- network: only registry.npmjs.org, everything else denied (E2B's egress rules);
  network="none" turns the internet off completely
- secrets: none. The sandbox gets no environment variables, and only repo files go in
- user: pwuser, not root; one fresh VM per workspace, killed when the workspace closes
- .git (masked paths) never goes in, and nothing under it ever comes back

The host keeps the real copy of the repo (git runs there). One sandbox per workspace
lives as long as the workspace, so packages installed by one command are there for
the next. Before each command, files changed on the host go up; after it, files the
command changed come back (unless read_only). Folders like node_modules stay in the
sandbox only.

Build the sandbox image once: `uv run python -m services.sandbox_e2b` (needs E2B_API_KEY).
"""

import io
import logging
import os
import shlex
import tarfile
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from services.sandbox import NETWORK, SandboxLimits, SandboxResult

CONTAINER_WORKDIR = "/workspace"
USER = "pwuser"  # the non-root user from the Playwright base image
TEMPLATE = "mas-sandbox"
NPM_REGISTRY = "registry.npmjs.org"
ALL_TRAFFIC = "0.0.0.0/0"

# Made and used inside the sandbox; never synced either way
SANDBOX_ONLY = frozenset(
    {"node_modules", ".next", ".pnpm-store", "test-results", "playwright-report", "coverage"}
)
MAX_FILE_BYTES = 5_000_000  # a file the command made bigger than this stays behind
# Kept alive this long after each command; E2B kills it after, if we never do
IDLE_SECONDS = 15 * 60

# `find` prints "<size> <path>" for every file, skipping SANDBOX_ONLY folders
_PRUNE = " -o ".join(f"-name {name}" for name in sorted(SANDBOX_ONLY))
LIST_FILES = f"find . \\( {_PRUNE} \\) -prune -o -type f -printf '%s %T@ %P\\n'"

Manifest = dict[str, tuple[int, int]]  # path -> (size, mtime): enough to see a change
SandboxFactory = Callable[..., Any]  # e2b.Sandbox.create; tests pass a fake

log = logging.getLogger(__name__)


@dataclass
class Config:
    api_key: str
    template: str = TEMPLATE
    create: SandboxFactory | None = None  # None = the real e2b.Sandbox.create


@dataclass
class _Session:
    sandbox: Any
    sent: Manifest = field(default_factory=dict)  # host files as last synced


_config: Config | None = None
_sessions: dict[tuple[str, str], _Session] = {}
_lock = threading.Lock()  # Celery runs jobs in threads


def configure(config: Config | None) -> None:
    """Turn the E2B backend on (or off with None). Called once when the worker starts."""
    global _config
    _config = config


def enabled() -> bool:
    return _config is not None


def run(
    command: list[str],
    workspace: Path | None,
    limits: SandboxLimits,
    masked_paths: tuple[str, ...],
    *,
    read_only: bool,
    network: str,
    extra_mounts: tuple[tuple[Path, str], ...],
) -> SandboxResult:
    from e2b import CommandExitException, TimeoutException

    session = _session(workspace, network)
    box = session.sandbox
    box.set_timeout(max(IDLE_SECONDS, limits.timeout_seconds + 60))
    if workspace is not None:
        _push(session, workspace, masked_paths)
    for host, target in extra_mounts:
        _push_folder(box, host, target)
    before = _remote_files(box) if workspace is not None and not read_only else None

    try:
        result = box.commands.run(
            shlex.join(command),
            cwd=CONTAINER_WORKDIR,
            user=USER,
            timeout=limits.timeout_seconds,
        )
    except CommandExitException as exc:  # a non-zero exit is a normal result here
        result = exc
    except TimeoutException:
        # The command may still be running: throw the whole sandbox away
        close(workspace)
        return SandboxResult(exit_code=-1, stdout="", stderr="", timed_out=True)

    if before is not None and workspace is not None:
        _pull(session, workspace, masked_paths, before)
    for host, target in extra_mounts:
        _pull_folder(box, host, target)
    return SandboxResult(result.exit_code, result.stdout, result.stderr, timed_out=False)


def close(workspace: Path | None) -> None:
    """Kill every sandbox opened for this workspace (Workspace.clone calls this on exit)."""
    key = str(workspace.resolve()) if workspace else ""
    with _lock:
        doomed = [k for k in _sessions if k[0] == key]
        sessions = [_sessions.pop(k) for k in doomed]
    for session in sessions:
        try:
            session.sandbox.kill()
        except Exception as exc:  # noqa: BLE001  (E2B's idle timeout is the backstop)
            log.warning("could not kill E2B sandbox: %s", exc)


def network_options(network: str) -> dict[str, Any]:
    """Sandbox.create arguments for our two network modes."""
    if network == "none":
        return {"allow_internet_access": False}
    if network == NETWORK:
        return {"network": {"allow_out": [NPM_REGISTRY], "deny_out": [ALL_TRAFFIC]}}
    raise ValueError(f"unknown sandbox network: {network!r}")


def _session(workspace: Path | None, network: str) -> _Session:
    if _config is None:
        raise RuntimeError("E2B sandbox backend is not configured")
    key = (str(workspace.resolve()) if workspace else "", network)
    with _lock:
        session = _sessions.get(key)
    if session is not None:
        return session
    create = _config.create
    if create is None:
        from e2b import Sandbox

        create = Sandbox.create
    box = create(
        template=_config.template,
        timeout=IDLE_SECONDS,
        api_key=_config.api_key,
        envs={},
        **network_options(network),
    )
    session = _Session(box)
    with _lock:
        _sessions[key] = session
    return session


def _host_files(workspace: Path, masked_paths: tuple[str, ...]) -> Manifest:
    files: Manifest = {}
    for folder, dirs, names in os.walk(workspace):  # never follows symlinked folders
        here = Path(folder)
        top = here == workspace
        dirs[:] = [d for d in dirs if d not in SANDBOX_ONLY and not (top and d in masked_paths)]
        for name in names:
            path = here / name
            if path.is_symlink() or not path.is_file():
                continue
            stat = path.stat()
            files[path.relative_to(workspace).as_posix()] = (stat.st_size, stat.st_mtime_ns)
    return files


def _push(session: _Session, workspace: Path, masked_paths: tuple[str, ...]) -> None:
    """Send files added or changed on the host since the last sync; delete removed ones."""
    box = session.sandbox
    now = _host_files(workspace, masked_paths)
    changed = [rel for rel, sig in now.items() if session.sent.get(rel) != sig]
    removed = [rel for rel in session.sent if rel not in now]
    if changed:
        box.files.write_files(
            [
                {"path": f"{CONTAINER_WORKDIR}/{rel}", "data": (workspace / rel).read_bytes()}
                for rel in changed
            ],
            user=USER,
        )
    for rel in removed:
        box.files.remove(f"{CONTAINER_WORKDIR}/{rel}", user=USER)
    session.sent = now


def _remote_files(box: Any) -> dict[str, tuple[int, str]]:
    """Every file in the sandbox's workspace: path -> (size, mtime as printed)."""
    out = box.commands.run(LIST_FILES, cwd=CONTAINER_WORKDIR, user=USER).stdout
    files: dict[str, tuple[int, str]] = {}
    for line in out.splitlines():
        size, mtime, rel = line.split(" ", 2)
        files[rel] = (int(size), mtime)
    return files


def _pull(
    session: _Session,
    workspace: Path,
    masked_paths: tuple[str, ...],
    before: dict[str, tuple[int, str]],
) -> None:
    """Bring back what the command added, changed or deleted, e.g. a new pnpm-lock.yaml."""
    box = session.sandbox
    after = _remote_files(box)
    root = workspace.resolve()
    for rel, (size, mtime) in after.items():
        if before.get(rel) == (size, mtime) or size > MAX_FILE_BYTES:
            continue
        target = _safe_target(root, rel, masked_paths)
        if target is None:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(box.files.read(f"{CONTAINER_WORKDIR}/{rel}", format="bytes", user=USER))
    for rel in before.keys() - after.keys():
        target = _safe_target(root, rel, masked_paths)
        if target is not None and target.is_file():
            target.unlink()
    # The host now matches the sandbox: the next push sends only newer host edits
    session.sent = _host_files(workspace, masked_paths)


def _safe_target(root: Path, rel: str, masked_paths: tuple[str, ...]) -> Path | None:
    """Where a sandbox file may land on the host, or None if it must not.

    Sandbox output is untrusted: no absolute paths, no "..", nothing in a masked
    folder like .git (a planted hook would run in host git), no escape via symlinks.
    """
    posix = PurePosixPath(rel)
    if posix.is_absolute() or ".." in posix.parts or not posix.parts:
        return None
    if posix.parts[0] in masked_paths or any(p in SANDBOX_ONLY for p in posix.parts):
        return None
    target = (root / posix).resolve()
    if not target.is_relative_to(root) or (root / posix).is_symlink():
        return None
    return target


def _push_folder(box: Any, host: Path, target: str) -> None:
    """Copy a whole host folder into the sandbox (extra_mounts, e.g. the code graph's cache)."""
    host.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        tar.add(host, arcname=".")
    archive = f"/tmp/mount-{abs(hash(target))}.tgz"  # noqa: S108  (inside the throwaway VM)
    box.files.write(archive, buffer.getvalue(), user=USER)
    box.commands.run(
        f"mkdir -p {shlex.quote(target)} && tar -xzf {archive} -C {shlex.quote(target)}",
        user=USER,
    )


def _pull_folder(box: Any, host: Path, target: str) -> None:
    """Copy a sandbox folder back over the host folder, refusing unsafe archive entries."""
    archive = f"/tmp/out-{abs(hash(target))}.tgz"  # noqa: S108  (inside the throwaway VM)
    box.commands.run(f"tar -czf {archive} -C {shlex.quote(target)} .", user=USER)
    data = box.files.read(archive, format="bytes", user=USER)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        tar.extractall(host, filter="data")  # "data" refuses links out, absolute paths, devices


def build_template(api_key: str) -> str:
    """Build the E2B image: the same tools as sandbox/Dockerfile, minus the npm proxy
    (E2B's egress rules do that job). Returns the build's template id."""
    from e2b import Template

    repo_root = Path(__file__).resolve().parents[2]
    starter = "templates/nextjs-starter"
    template = (
        Template(file_context_path=repo_root)
        # Must match @playwright/test in templates/nextjs-starter/package.json
        .from_image("mcr.microsoft.com/playwright:v1.64.0-noble")
        .run_cmd("npm install -g pnpm@10.30.1 && npm cache clean --force", user="root")
        .run_cmd("command -v curl || (apt-get update && apt-get install -y curl)", user="root")
        .run_cmd(f"mkdir -p /opt/template {CONTAINER_WORKDIR}", user="root")
        .run_cmd(f"chown {USER} /opt/template {CONTAINER_WORKDIR}", user="root")
        .set_user(USER)
        .set_envs({"npm_config_store_dir": f"/home/{USER}/.pnpm-store"})
        .set_workdir("/opt/template")
        .copy(
            [
                f"{starter}/package.json",
                f"{starter}/pnpm-lock.yaml",
                f"{starter}/pnpm-workspace.yaml",
            ],
            "/opt/template/",
            user=USER,
        )
        .run_cmd("pnpm fetch")  # the starter's packages, so installs come from disk
        # Playwright looks for browsers in ~/.cache/ms-playwright unless told otherwise;
        # the base image keeps them in /ms-playwright. A link works with or without env.
        .run_cmd(
            f"mkdir -p /home/{USER}/.cache"
            f" && ln -sfn /ms-playwright /home/{USER}/.cache/ms-playwright"
        )
        # Graphify for the code graph; uv and graphifyy pinned (14-day rule)
        .run_cmd("curl -LsSf https://astral.sh/uv/0.13.1/install.sh | sh")
        .run_cmd(
            f"/home/{USER}/.local/bin/uv tool install graphifyy==0.9.92"
            f" && /home/{USER}/.local/bin/uv cache clean"
        )
        .set_envs(
            {
                "PATH": f"/home/{USER}/.local/bin:/usr/local/sbin:/usr/local/bin"
                ":/usr/sbin:/usr/bin:/sbin:/bin",
                "PYTHONHASHSEED": "0",  # same input -> same graph
                "NEXT_TELEMETRY_DISABLED": "1",
                "CI": "1",
            }
        )
        .set_workdir(CONTAINER_WORKDIR)
    )
    limits = SandboxLimits()
    info = Template.build(
        template,
        alias=TEMPLATE,
        cpu_count=int(limits.cpus),
        memory_mb=int(limits.memory.rstrip("g")) * 1024,
        api_key=api_key,
        on_build_logs=lambda entry: print(entry),
    )
    return str(info.template_id)


if __name__ == "__main__":
    key = os.environ.get("E2B_API_KEY")
    if not key:
        raise SystemExit("Set E2B_API_KEY first.")
    print("Built template:", build_template(key))
