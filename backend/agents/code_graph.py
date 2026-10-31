"""A Graphify map of a repo's code, built once per project and reused by later tickets.

open_code_graph() finds the graph for the commit being worked on:
- saved for this exact commit: download it, nothing to build
- saved for an older commit: download it as the starting point; Graphify's cache
  inside it means only files that changed since are re-read
- none yet: build it from scratch
New graphs are zipped to R2, with a code_graphs row pointing at them.

Graphify runs in the sandbox with the repo read-only, no network, and --code-only
(local parsing, no LLM), so building a graph costs nothing.
"""

import io
import shutil
import tarfile
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from db.models import CodeGraph
from services import sandbox
from services.sandbox import CONTAINER_WORKDIR, SandboxLimits, SandboxResult
from services.workspace import Workspace

GRAPHIFY_VERSION = "0.9.92"  # must match sandbox/Dockerfile; graphs from other versions are rebuilt
CONTAINER_GRAPH_DIR = "/graph"
OUT_FOLDER = "graphify-out"  # what Graphify writes inside --out
GRAPH_LIMITS = SandboxLimits(timeout_seconds=10 * 60)
# extract builds (or incrementally updates) graph.json; cluster-only writes GRAPH_REPORT.md.
# A fixed string: nothing from the repo or the ticket goes into this command.
BUILD_COMMAND = (
    f"graphify extract {CONTAINER_WORKDIR} --code-only --out {CONTAINER_GRAPH_DIR}"
    f" && graphify cluster-only {CONTAINER_GRAPH_DIR} --no-label --no-viz"
)

RunSandbox = Callable[..., SandboxResult]  # sandbox.run; tests pass a fake


class Storage(Protocol):
    """The part of R2Storage this module uses (tests pass an in-memory fake)."""

    def upload(self, key: str, data: bytes, content_type: str = ...) -> None: ...
    def download(self, key: str) -> bytes: ...


class CodeGraphError(Exception):
    """Graphify failed to build the graph."""


@dataclass(frozen=True)
class CodeGraphFiles:
    folder: Path  # the graphify-out folder on the host
    commit_sha: str

    @property
    def graph_json(self) -> Path:
        return self.folder / "graph.json"

    def report(self) -> str:
        """GRAPH_REPORT.md: Graphify's plain-text summary of the code."""
        return (self.folder / "GRAPH_REPORT.md").read_text()


@contextmanager
def open_code_graph(
    factory: sessionmaker[Session],
    storage: Storage,
    project_id: int,
    workspace: Workspace,
    *,
    run_sandbox: RunSandbox = sandbox.run,
) -> Iterator[CodeGraphFiles]:
    """The graph for the workspace's current commit, in a temp folder deleted on exit."""
    sha = workspace.head_sha()
    parent = Path(tempfile.mkdtemp(prefix="mas-graph-"))
    try:
        exact_key, latest_key = _find(factory, project_id, sha)
        if exact_key is not None:
            _unpack(storage.download(exact_key), parent)
        else:
            if latest_key is not None:
                _unpack(storage.download(latest_key), parent)  # seeds Graphify's cache
            _build(workspace, parent, run_sandbox)
            key = f"code-graphs/{project_id}/{sha}.tar.gz"
            storage.upload(key, _pack(parent), "application/gzip")
            _save(factory, project_id, sha, key)
        yield CodeGraphFiles(parent / OUT_FOLDER, sha)
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def _find(
    factory: sessionmaker[Session], project_id: int, sha: str
) -> tuple[str | None, str | None]:
    """R2 keys of (this commit's graph, the newest graph) for the current Graphify version."""
    current = select(CodeGraph.r2_key).where(
        CodeGraph.project_id == project_id, CodeGraph.graphify_version == GRAPHIFY_VERSION
    )
    with factory() as session:
        exact = session.scalar(current.where(CodeGraph.commit_sha == sha))
        latest = session.scalar(
            current.order_by(CodeGraph.created_at.desc(), CodeGraph.id.desc()).limit(1)
        )
    return exact, latest


def _build(workspace: Workspace, parent: Path, run_sandbox: RunSandbox) -> None:
    result = run_sandbox(
        ["sh", "-c", BUILD_COMMAND],
        workspace=workspace.path,
        limits=GRAPH_LIMITS,
        masked_paths=(".git",),
        read_only=True,  # Graphify reads the user's code; it never changes it
        network="none",  # not even the npm proxy: nothing to download
        extra_mounts=((parent, CONTAINER_GRAPH_DIR),),
    )
    if result.timed_out or result.exit_code != 0:
        raise CodeGraphError(f"graphify failed (exit {result.exit_code}): {result.stderr[-500:]}")
    if not (parent / OUT_FOLDER / "graph.json").is_file():
        raise CodeGraphError("graphify finished but wrote no graph.json")


def _pack(parent: Path) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        tar.add(parent / OUT_FOLDER, arcname=OUT_FOLDER)
    return buffer.getvalue()


def _unpack(data: bytes, parent: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        # filter="data" refuses absolute paths, "../" escapes, links and devices
        tar.extractall(parent, filter="data")


def _save(factory: sessionmaker[Session], project_id: int, sha: str, key: str) -> None:
    with factory.begin() as session:
        # Two tickets on the same commit may build at once; the first row wins and
        # the other's upload just overwrote the same key with the same graph.
        session.execute(
            insert(CodeGraph)
            .values(
                project_id=project_id,
                commit_sha=sha,
                r2_key=key,
                graphify_version=GRAPHIFY_VERSION,
            )
            .on_conflict_do_nothing(constraint="uq_code_graphs_project_id_commit_sha")
        )
