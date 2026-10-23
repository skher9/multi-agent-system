"""GitHub client against a fake transport: we control every HTTP response."""

from collections.abc import Callable

import httpx2
import pytest

from services.github import API_VERSION, GitHubClient


def make_client(handler: Callable[[httpx2.Request], httpx2.Response]) -> GitHubClient:
    return GitHubClient("fake-token", "agents-org", transport=httpx2.MockTransport(handler))


def test_sends_auth_and_version_headers() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.update(request.headers)
        seen["path"] = request.url.path
        return httpx2.Response(200, json=[])

    make_client(handler).list_repos()
    assert seen["authorization"] == "Bearer fake-token"
    assert seen["x-github-api-version"] == API_VERSION
    assert seen["path"] == "/orgs/agents-org/repos"


def test_list_repos_follows_pagination() -> None:
    pages = {
        "1": [{"name": f"repo-{i}"} for i in range(100)],
        "2": [{"name": "repo-100"}],
    }

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=pages[request.url.params["page"]])

    repos = make_client(handler).list_repos()
    assert len(repos) == 101
    assert repos[-1] == "repo-100"


def test_ping_raises_on_bad_token() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(401, json={"message": "Bad credentials"})

    with pytest.raises(httpx2.HTTPStatusError):
        make_client(handler).ping()
