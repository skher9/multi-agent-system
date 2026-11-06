"""Figma REST client: a design frame's layer tree, and its images and icons as files.

Agents can't use Figma's own MCP server: it only accepts approved apps (Claude Code,
Cursor...) and answers others with 403. The REST API is open to any app with a token
(a personal access token, or an OAuth token once users connect their own Figma).

Links look like https://www.figma.com/design/<file key>/<name>?node-id=12-34 (older
ones say /file/). The URL writes node ids with "-", the API with ":".
"""

import re
from dataclasses import dataclass
from typing import Any

import httpx2

API_URL = "https://api.figma.com"
FIGMA_LINK = re.compile(
    r"https://(?:www\.)?figma\.com/(?:design|file|proto)/([A-Za-z0-9]{10,64})"
    r"(?:/[^\s?#)\]]*)?(?:\?[^\s#)\]]*)?"
)
NODE_ID = re.compile(r"[?&]node-id=(\d+)[-:](\d+)")
MAX_ASSET_BYTES = 5_000_000  # one image or icon; designs don't need bigger files


class FigmaError(Exception):
    """Figma refused or failed the request (bad link, no access, no such frame)."""


@dataclass(frozen=True)
class FigmaFrame:
    document: dict[str, Any]  # the frame's layer tree
    styles: dict[str, str]  # style id -> name, e.g. "Brand/Primary"
    components: dict[str, str]  # component id -> name, e.g. "Button/Primary"


@dataclass(frozen=True)
class FigmaLink:
    url: str
    file_key: str
    node_id: str  # "12:34"; "" = the link points at the whole file


def find_link(text: str) -> FigmaLink | None:
    """The first Figma design link in some text (a ticket), or None."""
    match = FIGMA_LINK.search(text)
    if not match:
        return None
    url = match.group(0)
    node = NODE_ID.search(url)
    return FigmaLink(url, match.group(1), f"{node.group(1)}:{node.group(2)}" if node else "")


class FigmaClient:
    def __init__(self, token: str, transport: httpx2.BaseTransport | None = None) -> None:
        self._http = httpx2.Client(
            base_url=API_URL,
            headers={"X-Figma-Token": token},
            timeout=30,
            transport=transport,  # tests pass a fake transport; None means real network
        )
        # Image files come from Figma's storage (signed URLs): never send them the token
        self._files = httpx2.Client(timeout=60, transport=transport, follow_redirects=True)

    def close(self) -> None:
        self._http.close()
        self._files.close()

    def frame(self, link: FigmaLink) -> FigmaFrame:
        """The linked frame, with the names of its styles and components. A link without
        a node id gets the file's first frame."""
        node_id = link.node_id or self._first_frame(link.file_key)
        data = self._get(f"/v1/files/{link.file_key}/nodes", ids=node_id)
        found = (data.get("nodes") or {}).get(node_id)
        if not found:
            raise FigmaError(f"the Figma file has no frame {node_id}")
        return FigmaFrame(
            found["document"],
            {sid: s.get("name", "") for sid, s in (found.get("styles") or {}).items()},
            {cid: c.get("name", "") for cid, c in (found.get("components") or {}).items()},
        )

    def image_fills(self, file_key: str) -> dict[str, str]:
        """Every image used as a fill in the file: imageRef -> download URL."""
        data = self._get(f"/v1/files/{file_key}/images")
        return (data.get("meta") or {}).get("images") or {}

    def render(self, file_key: str, node_ids: list[str], fmt: str = "svg") -> dict[str, str]:
        """Render layers (icons, the whole frame) as svg or png: node id -> URL."""
        if not node_ids:
            return {}
        params: dict[str, str | int] = {"ids": ",".join(node_ids), "format": fmt}
        if fmt == "png":
            params["scale"] = 2
        data = self._get(f"/v1/images/{file_key}", **params)
        return {k: v for k, v in (data.get("images") or {}).items() if v}

    def download(self, url: str) -> bytes:
        response = self._files.get(url)
        response.raise_for_status()
        if len(response.content) > MAX_ASSET_BYTES:
            raise FigmaError(f"a design file is over {MAX_ASSET_BYTES // 1_000_000} MB")
        return response.content

    def _first_frame(self, file_key: str) -> str:
        data = self._get(f"/v1/files/{file_key}", depth=2)
        for page in data.get("document", {}).get("children", []):
            for child in page.get("children", []):
                if child.get("type") in ("FRAME", "COMPONENT", "SECTION"):
                    return child["id"]
        raise FigmaError("the Figma file has no frames")

    def _get(self, path: str, **params: str | int) -> dict[str, Any]:
        response = self._http.get(path, params=params)
        if response.status_code in (403, 404):
            raise FigmaError(
                "Figma can't open this file: check the link, and that the file is shared "
                "with the account whose token we use"
            )
        response.raise_for_status()
        data = response.json()
        if data.get("err"):
            raise FigmaError(f"Figma: {data['err']}")
        return data
