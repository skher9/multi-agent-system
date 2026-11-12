"""GitHub REST client: the agent organization's repos, and pull requests on a repo.

Repos are named "owner/name" and checked before they go into a URL path.
"""

from dataclasses import dataclass

import httpx2

from services.workspace import GITHUB_REPO

API_URL = "https://api.github.com"
# Pinned API version, so GitHub changes can't silently alter responses.
API_VERSION = "2026-03-10"


@dataclass(frozen=True)
class PullRequest:
    number: int
    url: str  # the PR's page on github.com


@dataclass(frozen=True)
class PullRequestInfo:
    title: str
    url: str
    merged: bool


@dataclass(frozen=True)
class RepoAccess:
    repo: str  # owner/name, as GitHub spells it
    private: bool
    can_push: bool  # the token's user may push branches (needed to open PRs)


class RepoNotFoundError(Exception):
    """The token can't see the repo (or it doesn't exist: GitHub answers 404 for both)."""


# Comments our own pipeline posts start with this; they're not human feedback
AGENT_MARK = "🤖"


class GitHubClient:
    def __init__(self, token: str, org: str, transport: httpx2.BaseTransport | None = None) -> None:
        self.org = org
        self._http = httpx2.Client(
            base_url=API_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": API_VERSION,
            },
            timeout=10,
            transport=transport,  # tests pass a fake transport; None means real network
        )

    def list_repos(self) -> list[str]:
        """Names of every repo in the organization, following pagination."""
        names: list[str] = []
        page = 1
        while True:
            response = self._http.get(
                f"/orgs/{self.org}/repos", params={"per_page": 100, "page": page}
            )
            response.raise_for_status()
            batch = response.json()
            names.extend(repo["name"] for repo in batch)
            if len(batch) < 100:
                return names
            page += 1

    def default_branch(self, repo: str) -> str:
        response = self._http.get(f"/repos/{_checked(repo)}")
        response.raise_for_status()
        return response.json()["default_branch"]

    def open_pull_request(
        self, repo: str, *, head: str, base: str, title: str, body: str
    ) -> PullRequest:
        """Open a PR from branch `head` into `base`, or return the one already open for it
        (a rerun after a crash must not open a second PR)."""
        owner = _checked(repo).split("/")[0]
        found = self._http.get(
            f"/repos/{repo}/pulls", params={"head": f"{owner}:{head}", "state": "open"}
        )
        found.raise_for_status()
        if found.json():
            pr = found.json()[0]
            return PullRequest(pr["number"], pr["html_url"])
        response = self._http.post(
            f"/repos/{repo}/pulls", json={"head": head, "base": base, "title": title, "body": body}
        )
        response.raise_for_status()
        pr = response.json()
        return PullRequest(pr["number"], pr["html_url"])

    def pull_request_diff(self, repo: str, number: int) -> str:
        """The PR's changes as a unified diff (what a reviewer reads)."""
        response = self._http.get(
            f"/repos/{_checked(repo)}/pulls/{number}",
            headers={"Accept": "application/vnd.github.diff"},
        )
        response.raise_for_status()
        return response.text

    def pull_request(self, repo: str, number: int) -> PullRequestInfo:
        response = self._http.get(f"/repos/{_checked(repo)}/pulls/{number}")
        response.raise_for_status()
        pr = response.json()
        return PullRequestInfo(pr["title"], pr["html_url"], bool(pr.get("merged_at")))

    def human_comments(self, repo: str, number: int) -> list[str]:
        """Every comment people left on a PR: the conversation, review summaries, and
        comments on lines of code (with their file). Our pipeline's own comments
        (starting with 🤖, e.g. "### 🤖 Review 1") are left out."""
        base = f"/repos/{_checked(repo)}"
        found: list[str] = []
        for path, has_file in (
            (f"{base}/issues/{number}/comments", False),
            (f"{base}/pulls/{number}/reviews", False),
            (f"{base}/pulls/{number}/comments", True),
        ):
            response = self._http.get(path, params={"per_page": 100})
            response.raise_for_status()
            for item in response.json():
                body = (item.get("body") or "").strip()
                if not body or body.lstrip("# ").startswith(AGENT_MARK):
                    continue
                found.append(f"{item['path']}: {body}" if has_file else body)
        return found

    def comment_on_pull_request(self, repo: str, number: int, body: str) -> None:
        # A PR is an issue too; this is the PR's main conversation thread.
        response = self._http.post(
            f"/repos/{_checked(repo)}/issues/{number}/comments", json={"body": body}
        )
        response.raise_for_status()

    def repo_access(self, repo: str) -> RepoAccess:
        response = self._http.get(f"/repos/{_checked(repo)}")
        if response.status_code in (403, 404):
            raise RepoNotFoundError(repo)
        response.raise_for_status()
        data = response.json()
        permissions = data.get("permissions") or {}
        return RepoAccess(
            data["full_name"],
            bool(data.get("private")),
            bool(permissions.get("push") or permissions.get("admin")),
        )

    def login(self) -> str:
        """The token's GitHub username. Raises on a bad or expired token (401)."""
        response = self._http.get("/user")
        response.raise_for_status()
        return response.json()["login"]

    def ping(self, repo: str | None = None) -> None:
        """Raise if the token is bad or expired, or (given a repo) can't push to it. Works
        whether the owner is a person or an organization: /orgs/... is 404 for a person."""
        self.login()
        if repo is not None and not self.repo_access(repo).can_push:
            raise PermissionError(f"the token can't push to {repo}")

    def close(self) -> None:
        self._http.close()


def _checked(repo: str) -> str:
    if not GITHUB_REPO.fullmatch(repo):
        raise ValueError(f"not a GitHub owner/name: {repo!r}")
    return repo
