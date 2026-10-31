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

    def comment_on_pull_request(self, repo: str, number: int, body: str) -> None:
        # A PR is an issue too; this is the PR's main conversation thread.
        response = self._http.post(
            f"/repos/{_checked(repo)}/issues/{number}/comments", json={"body": body}
        )
        response.raise_for_status()

    def ping(self) -> None:
        """Raise if the token can't read the organization's repos."""
        self._http.get(f"/orgs/{self.org}/repos", params={"per_page": 1}).raise_for_status()

    def close(self) -> None:
        self._http.close()


def _checked(repo: str) -> str:
    if not GITHUB_REPO.fullmatch(repo):
        raise ValueError(f"not a GitHub owner/name: {repo!r}")
    return repo
