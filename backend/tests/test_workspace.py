"""Workspace tests against a local bare repo standing in for GitHub (no network).

Tests marked `docker` start real sandbox containers and skip without them.
"""

import subprocess
from pathlib import Path

import pytest

from services.sandbox import SandboxLimits, build_docker_command
from services.workspace import GitError, GitIdentity, Workspace, github_remote
from tests.test_sandbox import docker

AGENT = GitIdentity(name="Agent Dev Team", email="agents@example.com")


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(  # noqa: S603
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],  # noqa: S607
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


@pytest.fixture
def origin(tmp_path: Path) -> str:
    """A bare repo with one commit on main, like a freshly created GitHub repo."""
    bare = tmp_path / "origin.git"
    git("init", "--quiet", "--bare", "-b", "main", str(bare), cwd=tmp_path)
    seed = tmp_path / "seed"
    git("clone", "--quiet", str(bare), str(seed), cwd=tmp_path)
    (seed / "README.md").write_text("hello\n")
    git("add", ".", cwd=seed)
    git("commit", "--quiet", "-m", "init", cwd=seed)
    git("push", "--quiet", "origin", "main", cwd=seed)
    return bare.as_uri()


def test_clone_gives_a_working_copy_and_cleans_up(origin: str) -> None:
    with Workspace.clone(origin) as ws:
        assert (ws.path / "README.md").read_text() == "hello\n"
        folder = ws.path.parent
    assert not folder.exists()


def test_branch_commit_and_push_reach_the_remote(origin: str, tmp_path: Path) -> None:
    with Workspace.clone(origin) as ws:
        ws.create_branch("agent/KAN-4")
        (ws.path / "contact.txt").write_text("form\n")
        sha = ws.commit_all("feat: contact page (KAN-4)", AGENT)
        assert sha is not None
        ws.push("agent/KAN-4")

    bare = Path(origin.removeprefix("file://"))
    log = git("log", "-1", "--format=%an <%ae>|%s", "agent/KAN-4", cwd=bare)
    assert log.strip() == "Agent Dev Team <agents@example.com>|feat: contact page (KAN-4)"


def test_commit_all_returns_none_when_nothing_changed(origin: str) -> None:
    with Workspace.clone(origin) as ws:
        assert ws.commit_all("nothing", AGENT) is None


def test_git_hooks_in_the_repo_never_run_on_the_host(origin: str, tmp_path: Path) -> None:
    marker = tmp_path / "hook-ran"
    with Workspace.clone(origin) as ws:
        hook = ws.path / ".git" / "hooks" / "pre-commit"
        hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
        hook.chmod(0o755)
        (ws.path / "x.txt").write_text("x")
        ws.commit_all("try to trigger the hook", AGENT)
    assert not marker.exists()


@pytest.mark.parametrize("bad", ["has space", "a..b", "-starts-with-dash", "ends/"])
def test_bad_branch_names_are_rejected(origin: str, bad: str) -> None:
    with Workspace.clone(origin) as ws, pytest.raises(GitError):
        ws.create_branch(bad)


def test_token_goes_in_environment_not_arguments() -> None:
    ws = Workspace(Path("."), token="secret-token")
    env = ws._env()  # noqa: SLF001
    assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
    assert env["GIT_CONFIG_VALUE_0"].startswith("AUTHORIZATION: basic ")
    assert "secret-token" not in env["GIT_CONFIG_VALUE_0"]  # base64-encoded, not raw
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_no_token_means_no_auth_header() -> None:
    assert "GIT_CONFIG_KEY_0" not in Workspace(Path("."), token=None)._env()  # noqa: SLF001


@pytest.mark.parametrize("bad", ["skher9", "skher9/repo/extra", "../etc", "a b/c"])
def test_github_remote_validates_owner_and_name(bad: str) -> None:
    assert github_remote("skher9/agent-playground") == (
        "https://github.com/skher9/agent-playground.git"
    )
    with pytest.raises(ValueError):
        github_remote(bad)


def test_docker_command_masks_git_folder(tmp_path: Path) -> None:
    cmd = build_docker_command(["true"], "n1", tmp_path, SandboxLimits(), masked_paths=(".git",))
    assert "type=tmpfs,destination=/workspace/.git" in cmd


@docker
def test_sandbox_sees_the_code_but_not_git(origin: str) -> None:
    with Workspace.clone(origin) as ws:
        result = ws.run(["bash", "-c", "cat README.md && ls -A .git | wc -l"])
        assert result.exit_code == 0, result.stderr
        assert result.stdout.split() == ["hello", "0"]  # code visible, .git empty


@docker
def test_sandbox_cannot_change_the_real_git_folder(origin: str) -> None:
    with Workspace.clone(origin) as ws:
        ws.run(["bash", "-c", "mkdir -p .git/hooks && echo evil > .git/hooks/pre-commit"])
        assert not (ws.path / ".git" / "hooks" / "pre-commit").exists()
        assert (ws.path / ".git" / "HEAD").exists()  # real .git untouched


def test_discard_changes_drops_edits_and_new_files(origin: str) -> None:
    with Workspace.clone(origin) as ws:
        tracked = ws.tracked_files()[0]
        before = (ws.path / tracked).read_text()
        (ws.path / tracked).write_text("changed\n")
        (ws.path / "e2e").mkdir()
        (ws.path / "e2e/half.spec.ts").write_text("half\n")
        ws.discard_changes()
        assert (ws.path / tracked).read_text() == before
        assert not (ws.path / "e2e").exists()
