"""GitHub REST client for the agent organization (where generated app repos live).

Setup only lists repos. M1 adds creating repos from the template and opening PRs.
"""

import httpx2

API_URL = "https://api.github.com"
# Pinned API version, so GitHub changes can't silently alter responses.
API_VERSION = "2026-03-10"


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

    def ping(self) -> None:
        """Raise if the token can't read the organization's repos."""
        self._http.get(f"/orgs/{self.org}/repos", params={"per_page": 1}).raise_for_status()

    def close(self) -> None:
        self._http.close()
