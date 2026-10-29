"""Jira Cloud REST client: where v1 tickets come from.

Auth is basic auth with the account email + API token (Atlassian's documented way
for scripts). Descriptions arrive in ADF (Atlassian Document Format, a JSON tree);
adf_to_text() flattens that into Markdown-like text an LLM can read.
"""

import re
from dataclasses import dataclass
from typing import Any

import httpx2

# Project key, dash, number: "KAN-4". Checked before the key goes into a URL path.
TICKET_KEY = re.compile(r"[A-Z][A-Z0-9]+-\d+")


class TicketNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class JiraTicket:
    key: str
    issue_type: str  # e.g. Story, Task
    status: str  # e.g. To Do
    summary: str  # the ticket title
    description: str  # plain text; "" when the ticket has none
    labels: list[str]


class JiraClient:
    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self._http = httpx2.Client(
            base_url=base_url,
            auth=(email, api_token),
            headers={"Accept": "application/json"},
            timeout=15,
            transport=transport,  # tests pass a fake transport; None means real network
        )

    def get_ticket(self, key: str) -> JiraTicket:
        # fullmatch, not match + "$": "$" also accepts a trailing newline ("KAN-4\n").
        if not TICKET_KEY.fullmatch(key):
            raise ValueError(f"not a Jira ticket key: {key!r}")
        response = self._http.get(
            f"/rest/api/3/issue/{key}",
            params={"fields": "summary,description,issuetype,status,labels"},
        )
        if response.status_code == 404:
            # Jira also answers 404 when the token can't see the ticket.
            raise TicketNotFoundError(key)
        response.raise_for_status()
        data = response.json()
        fields = data["fields"]
        return JiraTicket(
            key=data["key"],
            issue_type=fields["issuetype"]["name"],
            status=fields["status"]["name"],
            summary=fields["summary"],
            description=adf_to_text(fields.get("description")),
            labels=fields.get("labels") or [],
        )

    def ping(self) -> None:
        """Raise if the email + token can't sign in. GET /myself reads only the caller."""
        self._http.get("/rest/api/3/myself").raise_for_status()

    def close(self) -> None:
        self._http.close()


def adf_to_text(node: dict[str, Any] | None) -> str:
    """Flatten an ADF document into text, keeping headings and lists recognisable."""
    if not node:
        return ""
    return _blocks(node.get("content", []), indent="").strip()


def _blocks(nodes: list[dict[str, Any]], indent: str) -> str:
    return "".join(_block(n, indent) for n in nodes)


def _block(node: dict[str, Any], indent: str) -> str:
    kind = node.get("type")
    children = node.get("content", [])
    if kind == "heading":
        level = node.get("attrs", {}).get("level", 1)
        return f"\n{'#' * level} {_inline(children)}\n"
    if kind == "paragraph":
        return f"{indent}{_inline(children)}\n"
    if kind in ("bulletList", "orderedList"):
        lines = []
        for number, item in enumerate(children, start=1):
            marker = f"{number}." if kind == "orderedList" else "-"
            body = _blocks(item.get("content", []), indent + "  ").strip()
            lines.append(f"{indent}{marker} {body}\n")
        return "".join(lines)
    if kind == "codeBlock":
        return f"```\n{_inline(children)}\n```\n"
    if kind == "rule":
        return "---\n"
    # Anything else (tables, panels, quotes...): keep the text inside, drop the styling.
    return _blocks(children, indent) if children else _inline([node])


def _inline(nodes: list[dict[str, Any]]) -> str:
    parts = []
    for node in nodes:
        kind = node.get("type")
        if kind == "text":
            parts.append(node.get("text", ""))
        elif kind == "hardBreak":
            parts.append("\n")
        elif kind == "mention":
            parts.append(node.get("attrs", {}).get("text", "@someone"))
        elif "content" in node:
            parts.append(_inline(node["content"]))
    return "".join(parts)
