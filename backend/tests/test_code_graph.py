"""Code graphs: build once, reuse, update. Real Neon test branch; fake R2 and Graphify.

Tests marked `docker` run the real Graphify in the sandbox image and skip without it.
"""

import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from agents.code_graph import (
    CONTAINER_GRAPH_DIR,
    OUT_FOLDER,
    CodeGraphError,
    open_code_graph,
)
from api.config import get_settings
from db.models import CodeGraph, User
from db.session import make_session_factory
from orchestrator.records import ensure_project
from services.sandbox import SandboxLimits, SandboxResult, build_docker_command
from services.workspace import Workspace
from tests.test_sandbox import docker
from tests.test_workspace import git, origin  # noqa: F401  (origin is a fixture)

test_db_url = get_settings().database_url_test
needs_db = pytest.mark.skipif(test_db_url is None, reason="DATABASE_URL_TEST not set")


class FakeStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def upload(self, key: str, data: bytes, content_type: str = "") -> None:
        self.files[key] = data

    def download(self, key: str) -> bytes:
        return self.files[key]


class FakeGraphify:
    """Stands in for sandbox.run: writes a graph into the mounted folder."""

    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code
        self.calls: list[dict[str, Any]] = []
        self.seeded: list[bool] = []  # was an earlier graph there to update?

    def __call__(self, command: list[str], **kwargs: Any) -> SandboxResult:
        self.calls.append(kwargs)
        host, target = kwargs["extra_mounts"][0]
        assert target == CONTAINER_GRAPH_DIR
        out = Path(host) / OUT_FOLDER
        self.seeded.append((out / "graph.json").exists())
        if self.exit_code == 0:
            out.mkdir(exist_ok=True)
            (out / "graph.json").write_text("{}")
            (out / "GRAPH_REPORT.md").write_text(f"# Graph Report {len(self.calls)}")
        return SandboxResult(self.exit_code, "", "boom", timed_out=False)


@pytest.fixture
def factory() -> sessionmaker[Session]:
    assert test_db_url is not None
    return make_session_factory(test_db_url.get_secret_value())


@pytest.fixture
def project_id(factory: sessionmaker[Session]) -> Iterator[int]:
    email = f"graph-test-{uuid.uuid4().hex}@example.com"
    yield ensure_project(factory, owner_email=email, name="playground", repo_url="x")
    with factory.begin() as session:
        session.delete(session.scalars(select(User).where(User.email == email)).one())


def new_commit(ws: Workspace) -> None:
    (ws.path / "page.tsx").write_text(f"export const v = '{uuid.uuid4().hex}'\n")
    git("add", ".", cwd=ws.path)
    git("commit", "--quiet", "-m", "change", cwd=ws.path)


@needs_db
def test_first_ticket_builds_and_saves_the_graph(
    factory: sessionmaker[Session],
    project_id: int,
    origin: str,  # noqa: F811
) -> None:
    storage, graphify = FakeStorage(), FakeGraphify()
    with (
        Workspace.clone(origin) as ws,
        open_code_graph(factory, storage, project_id, ws, run_sandbox=graphify) as graph,
    ):
        assert graph.report() == "# Graph Report 1"
        assert graph.commit_sha == ws.head_sha()
        folder = graph.folder
    assert not folder.exists()  # temp folder cleaned up

    call = graphify.calls[0]
    assert (call["read_only"], call["network"], call["masked_paths"]) == (True, "none", (".git",))
    with factory() as session:
        row = session.scalars(select(CodeGraph).where(CodeGraph.project_id == project_id)).one()
    assert row.r2_key == f"code-graphs/{project_id}/{graph.commit_sha}.tar.gz"
    assert list(storage.files) == [row.r2_key]


@needs_db
def test_same_commit_reuses_the_saved_graph(
    factory: sessionmaker[Session],
    project_id: int,
    origin: str,  # noqa: F811
) -> None:
    storage, graphify = FakeStorage(), FakeGraphify()
    with Workspace.clone(origin) as ws:
        with open_code_graph(factory, storage, project_id, ws, run_sandbox=graphify):
            pass
        with open_code_graph(factory, storage, project_id, ws, run_sandbox=graphify) as graph:
            assert graph.report() == "# Graph Report 1"  # the saved one, not rebuilt
    assert len(graphify.calls) == 1


@needs_db
def test_new_commit_updates_from_the_last_graph(
    factory: sessionmaker[Session],
    project_id: int,
    origin: str,  # noqa: F811
) -> None:
    storage, graphify = FakeStorage(), FakeGraphify()
    with Workspace.clone(origin) as ws:
        with open_code_graph(factory, storage, project_id, ws, run_sandbox=graphify):
            pass
        new_commit(ws)
        with open_code_graph(factory, storage, project_id, ws, run_sandbox=graphify) as graph:
            assert graph.report() == "# Graph Report 2"
    assert graphify.seeded == [False, True]  # 2nd build started from the 1st graph
    assert len(storage.files) == 2


@needs_db
def test_graphs_from_another_graphify_version_are_not_reused(
    factory: sessionmaker[Session],
    project_id: int,
    origin: str,  # noqa: F811
) -> None:
    storage, graphify = FakeStorage(), FakeGraphify()
    with Workspace.clone(origin) as ws:
        with open_code_graph(factory, storage, project_id, ws, run_sandbox=graphify):
            pass
        with factory.begin() as session:
            session.execute(
                update(CodeGraph)
                .where(CodeGraph.project_id == project_id)
                .values(graphify_version="0.0.1")
            )
        new_commit(ws)
        with open_code_graph(factory, storage, project_id, ws, run_sandbox=graphify):
            pass
    assert graphify.seeded == [False, False]  # fresh build, old graph ignored


@needs_db
def test_failed_build_saves_nothing(
    factory: sessionmaker[Session],
    project_id: int,
    origin: str,  # noqa: F811
) -> None:
    storage = FakeStorage()
    with (
        Workspace.clone(origin) as ws,
        pytest.raises(CodeGraphError, match="exit 1"),
        open_code_graph(factory, storage, project_id, ws, run_sandbox=FakeGraphify(exit_code=1)),
    ):
        pass
    assert storage.files == {}
    with factory() as session:
        assert (
            session.scalars(select(CodeGraph).where(CodeGraph.project_id == project_id)).all() == []
        )


def test_docker_command_for_read_only_offline_runs(tmp_path: Path) -> None:
    cmd = build_docker_command(
        ["true"],
        "n1",
        tmp_path,
        SandboxLimits(),
        read_only=True,
        network="none",
        extra_mounts=((tmp_path, "/graph"),),
    )
    joined = " ".join(cmd)
    assert f"{tmp_path.resolve()}:/workspace:ro" in joined
    assert "--network none" in joined
    assert f"{tmp_path.resolve()}:/graph" in joined


@docker
@needs_db
def test_real_graphify_maps_typescript(
    factory: sessionmaker[Session],
    project_id: int,
    origin: str,  # noqa: F811
) -> None:
    with Workspace.clone(origin) as ws:
        (ws.path / "util.ts").write_text(
            "export function add(a: number, b: number) { return a + b }\n"
        )
        (ws.path / "page.tsx").write_text(
            "import { add } from './util'\nexport const x = add(1, 2)\n"
        )
        git("add", ".", cwd=ws.path)
        git("commit", "--quiet", "-m", "code", cwd=ws.path)
        with open_code_graph(factory, FakeStorage(), project_id, ws) as graph:
            assert graph.graph_json.is_file()
            assert "add()" in graph.graph_json.read_text()
            assert graph.report().startswith("# Graph Report")
        assert not (ws.path / OUT_FOLDER).exists()  # nothing written into the user's repo


@docker
@needs_db
def test_real_graphify_updates_after_a_new_commit(
    factory: sessionmaker[Session],
    project_id: int,
    origin: str,  # noqa: F811
) -> None:
    storage = FakeStorage()
    with Workspace.clone(origin) as ws:
        (ws.path / "util.ts").write_text("export function add(a: number) { return a }\n")
        git("add", ".", cwd=ws.path)
        git("commit", "--quiet", "-m", "first", cwd=ws.path)
        with open_code_graph(factory, storage, project_id, ws):
            pass
        (ws.path / "util.ts").unlink()  # deleted code must leave the graph
        (ws.path / "math.ts").write_text("export function multiply(a: number) { return a }\n")
        git("add", "--all", cwd=ws.path)
        git("commit", "--quiet", "-m", "second", cwd=ws.path)
        with open_code_graph(factory, storage, project_id, ws) as graph:
            text = graph.graph_json.read_text()
    assert "multiply()" in text
    assert "add()" not in text
