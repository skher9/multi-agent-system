"""GitHub client against a fake transport: we control every HTTP response."""

import json
from collections.abc import Callable

import httpx2
import pytest

from services.github import API_VERSION, GitHubClient, RepoNotFoundError


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


def test_ping_works_for_a_personal_account_and_checks_push_access() -> None:
    asked: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        asked.append(request.url.path)
        if request.url.path == "/user":
            return httpx2.Response(200, json={"login": "skher9"})
        can_push = request.url.path.endswith("/agent-playground")
        body = {"full_name": "skher9/x", "private": False, "permissions": {"push": can_push}}
        return httpx2.Response(200, json=body)

    client = make_client(handler)
    client.ping()
    client.ping("skher9/agent-playground")
    assert asked == ["/user", "/user", "/repos/skher9/agent-playground"]  # never /orgs/...
    with pytest.raises(PermissionError, match="can't push to skher9/read-only"):
        client.ping("skher9/read-only")


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


def test_pull_request_says_whether_it_was_merged() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/repos/skher9/agent-playground/pulls/3"
        pr = {"title": "KAN-4: Add a contact page", "html_url": "https://gh/pr/3"}
        return httpx2.Response(200, json={**pr, "merged_at": "2026-11-02T10:00:00Z"})

    info = make_client(handler).pull_request("skher9/agent-playground", 3)
    assert (info.title, info.url, info.merged) == (
        "KAN-4: Add a contact page",
        "https://gh/pr/3",
        True,
    )


def test_human_comments_leave_out_the_pipelines_own() -> None:
    pages = {
        "/repos/o/r/issues/3/comments": [
            {"body": "### 🤖 Review 1: ✅ Approved"},
            {"body": "Please always use the shared Button."},
        ],
        "/repos/o/r/pulls/3/reviews": [{"body": ""}, {"body": "Looks good, one nit."}],
        "/repos/o/r/pulls/3/comments": [{"path": "src/a.tsx", "body": "Use formatDate here"}],
    }
    client = make_client(lambda request: httpx2.Response(200, json=pages[request.url.path]))
    assert client.human_comments("o/r", 3) == [
        "Please always use the shared Button.",
        "Looks good, one nit.",
        "src/a.tsx: Use formatDate here",
    ]


def test_repo_access_and_login() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/user":
            return httpx2.Response(200, json={"login": "octo"})
        if request.url.path == "/repos/octo/shop":
            return httpx2.Response(
                200,
                json={"full_name": "octo/shop", "private": True, "permissions": {"push": True}},
            )
        return httpx2.Response(404)

    client = GitHubClient("t", "octo", transport=httpx2.MockTransport(handler))
    assert client.login() == "octo"
    access = client.repo_access("octo/shop")
    assert (access.repo, access.private, access.can_push) == ("octo/shop", True, True)
    with pytest.raises(RepoNotFoundError):
        client.repo_access("octo/missing")
    with pytest.raises(ValueError):
        client.repo_access("../etc")
