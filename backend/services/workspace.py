"""A working copy of a repo for one agent run: clone, branch, run commands, commit, push.

Only this code runs git, on the host. Agent-written code runs only in the sandbox,
where .git is masked, so it can never plant a git hook or config that the host's
git would later execute. As a second layer, host git always runs with hooks off.

The GitHub token reaches git through environment variables (GIT_CONFIG_*), never
through command-line arguments (visible to other processes) or .git/config (on disk).
"""

import base64
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from services import sandbox, sandbox_e2b
from services.sandbox import SandboxLimits, SandboxResult

SHA = re.compile(r"[0-9a-f]{40}")  # a full git commit id
GITHUB_REPO = re.compile(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}")  # owner/name, GitHub's limits

# Applied to every host git command. Hooks off: nothing in the repo runs on the host.
SAFE_GIT_CONFIG = ["-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false"]

GIT_TIMEOUT_SECONDS = 120


class GitError(Exception):
    pass


@dataclass(frozen=True)
class GitIdentity:
    """Author of the agent's commits."""

    name: str
    email: str


def github_remote(repo: str) -> str:
    if not GITHUB_REPO.fullmatch(repo):
        raise ValueError(f"not a GitHub owner/name: {repo!r}")
    return f"https://github.com/{repo}.git"


class Workspace:
    def __init__(self, path: Path, token: str | None) -> None:
        self.path = path
        self._token = token
        # Set by the agents' tools once packages are installed: a hash of the lockfile
        # they were installed for, so the next agent on this copy doesn't install again
        self.installed_lock = ""

    @classmethod
    @contextmanager
    def clone(cls, remote_url: str, token: str | None = None) -> Iterator["Workspace"]:
        """Clone into a new temp folder; the folder is deleted on exit, even after a crash."""
        parent = Path(tempfile.mkdtemp(prefix="mas-workspace-"))
        try:
            workspace = cls(parent / "repo", token)
            workspace._git("clone", "--quiet", remote_url, str(workspace.path), cwd=parent)
            yield workspace
        finally:
            sandbox_e2b.close(parent / "repo")  # its cloud sandbox, if E2B is on
            shutil.rmtree(parent, ignore_errors=True)

    def head_sha(self) -> str:
        """The full sha of the commit currently checked out."""
        return self._git("rev-parse", "HEAD").strip()

    def tracked_files(self) -> list[str]:
        """Every file git tracks, as repo-relative paths (no node_modules or build output)."""
        return self._git("ls-files").splitlines()

    def checkout(self, branch: str) -> None:
        """Switch to an existing remote branch (e.g. the agent's, to review or fix it)."""
        self._git("check-ref-format", "--branch", branch)
        self._git("switch", "--quiet", branch)

    def diff(self, base: str, *, uncommitted: bool = False) -> str:
        """Everything changed since commit `base`, as a unified diff. uncommitted=True
        also counts changes and new files not committed yet (an agent's work in
        progress), instead of only what's committed."""
        if not SHA.fullmatch(base):
            raise ValueError(f"not a commit sha: {base!r}")
        if not uncommitted:
            return self._git("diff", f"{base}..HEAD")
        # Marks new files as "will be added" (no content staged), so diff shows them
        self._git("add", "--intent-to-add", "--all")
        return self._git("diff", base)

    def create_branch(self, name: str, start: str | None = None) -> None:
        """Create and switch to a branch, from `start` (a commit sha) or the current commit."""
        # git's own rules for branch names (no spaces, no "..", etc.)
        self._git("check-ref-format", "--branch", name)
        if start is not None and not SHA.fullmatch(start):
            raise ValueError(f"not a commit sha: {start!r}")
        self._git("switch", "--quiet", "-c", name, *([start] if start else []))

    def run(self, command: list[str], limits: SandboxLimits | None = None) -> SandboxResult:
        """Run a command in the sandbox with this repo mounted and .git masked."""
        return sandbox.run(
            command, workspace=self.path, limits=limits or SandboxLimits(), masked_paths=(".git",)
        )

    def discard_changes(self) -> None:
        """Throw away every uncommitted change and new file (ignored ones like
        node_modules stay)."""
        self._git("reset", "--hard", "--quiet")
        self._git("clean", "-d", "--force", "--quiet")

    def commit_all(self, message: str, author: GitIdentity) -> str | None:
        """Commit every change; return the new commit's sha, or None if nothing changed."""
        self._git("add", "--all")
        if not self._git("status", "--porcelain").strip():
            return None
        self._git(
            "-c", f"user.name={author.name}",
            "-c", f"user.email={author.email}",
            "commit", "--quiet", "--no-verify", "-m", message,
        )  # fmt: skip
        return self.head_sha()

    def push(self, branch: str, *, replace: bool = False) -> None:
        """Push HEAD to a branch. replace=True overwrites the branch (the "+" refspec):
        only for branches the agents own, e.g. when a crashed run builds again."""
        self._git("push", "--quiet", "origin", f"{'+' if replace else ''}HEAD:refs/heads/{branch}")

    def _git(self, *args: str, cwd: Path | None = None) -> str:
        try:
            done = subprocess.run(  # noqa: S603  (fixed binary, list args, no shell)
                ["git", *SAFE_GIT_CONFIG, *args],  # noqa: S607  (git from PATH)
                cwd=cwd or self.path,
                env=self._env(),
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise GitError(f"git {args[0]} timed out") from exc
        if done.returncode != 0:
            raise GitError(f"git {args[0]} failed: {done.stderr.strip()[:500]}")
        return done.stdout

    def _env(self) -> dict[str, str]:
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}  # fail instead of asking for a password
        if self._token:
            basic = base64.b64encode(f"x-access-token:{self._token}".encode()).decode()
            env |= {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
                "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {basic}",
            }
        return env
