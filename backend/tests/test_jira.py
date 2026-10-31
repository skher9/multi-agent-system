import base64
import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest

from services.jira import JiraClient, TicketNotFoundError, adf_to_text


def make_client(handler: Callable[[httpx2.Request], httpx2.Response]) -> JiraClient:
    return JiraClient(
        "https://example.atlassian.net",
        "me@example.com",
        "fake-token",
        transport=httpx2.MockTransport(handler),
    )


def p(text: str) -> dict[str, Any]:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def bullets(*items: str) -> dict[str, Any]:
    return {
        "type": "bulletList",
        "content": [{"type": "listItem", "content": [p(i)]} for i in items],
    }


# Same shape as test ticket KAN-4
CONTACT_PAGE_ADF = {
    "type": "doc",
    "version": 1,
    "content": [
        p("Visitors need a way to reach us."),
        {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": "AC"}]},
        bullets("Shows a form", "Invalid email shows an error"),
    ],
}


def issue_json(description: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "key": "KAN-4",
        "fields": {
            "summary": "Add a contact page",
            "description": description,
            "issuetype": {"name": "Story"},
            "status": {"name": "To Do"},
            "labels": ["agent-test"],
        },
    }


def test_get_ticket_parses_fields_and_flattens_description() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/rest/api/3/issue/KAN-4"
        expected = base64.b64encode(b"me@example.com:fake-token").decode()
        assert request.headers["authorization"] == f"Basic {expected}"
        return httpx2.Response(200, json=issue_json(CONTACT_PAGE_ADF))

    ticket = make_client(handler).get_ticket("KAN-4")
    assert ticket.key == "KAN-4"
    assert ticket.issue_type == "Story"
    assert ticket.status == "To Do"
    assert ticket.summary == "Add a contact page"
    assert ticket.labels == ["agent-test"]
    assert ticket.description == (
        "Visitors need a way to reach us.\n\n### AC\n- Shows a form\n- Invalid email shows an error"
    )


def test_ticket_without_description_gives_empty_text() -> None:
    client = make_client(lambda _: httpx2.Response(200, json=issue_json(None)))
    assert client.get_ticket("KAN-4").description == ""


def test_missing_ticket_raises_not_found() -> None:
    client = make_client(lambda _: httpx2.Response(404, json={"errorMessages": ["nope"]}))
    with pytest.raises(TicketNotFoundError):
        client.get_ticket("KAN-999")


@pytest.mark.parametrize("bad_key", ["kan-4", "KAN", "KAN-4/../../myself", "4-KAN", "KAN-4\n", ""])
def test_rejects_bad_keys_before_any_request(bad_key: str) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("no request should be sent for a bad key")

    with pytest.raises(ValueError, match="not a Jira ticket key"):
        make_client(handler).get_ticket(bad_key)


def test_add_comment_posts_adf_body_and_returns_id() -> None:
    body = {"type": "doc", "version": 1, "content": [p("hello")]}

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        assert request.url.path == "/rest/api/3/issue/KAN-5/comment"
        assert json.loads(request.content) == {"body": body}
        return httpx2.Response(201, json={"id": "10042"})

    assert make_client(handler).add_comment("KAN-5", body) == "10042"


def test_add_comment_rejects_bad_keys() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("no request should be sent for a bad key")

    with pytest.raises(ValueError):
        make_client(handler).add_comment("KAN-5/../../x", {})


def test_ping_raises_on_bad_token() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/rest/api/3/myself"
        return httpx2.Response(401)

    with pytest.raises(httpx2.HTTPStatusError):
        make_client(handler).ping()


def test_adf_ordered_lists_nested_lists_and_breaks() -> None:
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "orderedList",
                "content": [
                    {"type": "listItem", "content": [p("First")]},
                    {"type": "listItem", "content": [p("Second"), bullets("nested")]},
                ],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "line one"},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "line two"},
                ],
            },
        ],
    }
    assert adf_to_text(doc) == "1. First\n2. Second\n  - nested\nline one\nline two"


def test_adf_unknown_blocks_keep_their_text() -> None:
    doc = {"type": "doc", "content": [{"type": "panel", "content": [p("inside a panel")]}]}
    assert adf_to_text(doc) == "inside a panel"


def test_create_subtask_posts_parent_type_and_labels() -> None:
    sent: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/rest/api/3/issue"
        sent.append(json.loads(request.content))
        return httpx2.Response(201, json={"id": "10050", "key": "KAN-12"})

    key = make_client(handler).create_subtask(
        "KAN-4", "[FE] Contact page", p("Do it"), ["mas-agent"]
    )
    assert key == "KAN-12"
    fields = sent[0]["fields"]
    assert fields["project"] == {"key": "KAN"}
    assert fields["parent"] == {"key": "KAN-4"}
    assert fields["issuetype"] == {"name": "Subtask"}
    assert fields["labels"] == ["mas-agent"]


def test_find_subtasks_maps_summary_to_key() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.params["jql"] == 'parent = KAN-4 AND labels = "mas-agent"'
        issues = [{"key": "KAN-12", "fields": {"summary": "[FE] Contact page"}}]
        return httpx2.Response(200, json={"issues": issues})

    assert make_client(handler).find_subtasks("KAN-4", "mas-agent") == {
        "[FE] Contact page": "KAN-12"
    }


@pytest.mark.parametrize(
    ("key", "label"), [("KAN-4 OR 1=1", "mas-agent"), ("KAN-4", 'x" OR labels = "y')]
)
def test_find_subtasks_never_builds_jql_from_bad_input(key: str, label: str) -> None:
    client = make_client(lambda _r: pytest.fail("no request should be sent"))
    with pytest.raises(ValueError):
        client.find_subtasks(key, label)
