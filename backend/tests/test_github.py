"""GitHub client against a fake transport: we control every HTTP response."""

import json
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


def test_open_pull_request_creates_one_when_none_is_open() -> None:
    posted: list[dict[str, str]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/repos/skher9/agent-playground/pulls"
        if request.method == "GET":
            assert request.url.params["head"] == "skher9:agent/KAN-4"
            return httpx2.Response(200, json=[])
        posted.append(json.loads(request.content))
        return httpx2.Response(201, json={"number": 7, "html_url": "https://github.com/x/pull/7"})

    pr = make_client(handler).open_pull_request(
        "skher9/agent-playground", head="agent/KAN-4", base="main", title="T", body="B"
    )
    assert (pr.number, pr.url) == (7, "https://github.com/x/pull/7")
    assert posted == [{"head": "agent/KAN-4", "base": "main", "title": "T", "body": "B"}]


def test_open_pull_request_reuses_the_open_one() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "GET", "must not open a second PR"
        return httpx2.Response(200, json=[{"number": 3, "html_url": "https://github.com/x/pull/3"}])

    pr = make_client(handler).open_pull_request(
        "skher9/agent-playground", head="agent/KAN-4", base="main", title="T", body="B"
    )
    assert pr.number == 3


def test_pull_request_diff_asks_for_the_diff_format() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["accept"] == "application/vnd.github.diff"
        return httpx2.Response(200, text="diff --git a/x b/x")

    assert make_client(handler).pull_request_diff("o/r", 7).startswith("diff --git")


def test_repo_names_are_checked_before_use() -> None:
    client = make_client(lambda _r: pytest.fail("no request should be sent"))
    with pytest.raises(ValueError):
        client.default_branch("../../user")
