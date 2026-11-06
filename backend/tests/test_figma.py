"""Figma: finding links, the design spec, exported assets. Fake Figma API, no network."""

from pathlib import Path
from typing import Any

import httpx2
import pytest

from agents.design import read_design
from agents.ticket_reader import TicketSpec, design_link, with_design_link
from services.figma import FigmaClient, FigmaError, find_link
from services.jira import JiraTicket, adf_to_text
from tests.test_ticket_reader import READY

URL = "https://www.figma.com/design/AbC123xyz456/Shop?node-id=1-2&t=x"
PNG = b"\x89PNG\r\n\x1a\nfake"
SVG = b'<svg width="24" height="24"></svg>'


def solid(r: float, g: float, b: float, a: float = 1) -> dict[str, Any]:
    return {"type": "SOLID", "color": {"r": r, "g": g, "b": b, "a": a}}


def box(x: float, y: float, w: float, h: float) -> dict[str, float]:
    return {"x": x, "y": y, "width": w, "height": h}


FRAME: dict[str, Any] = {
    "id": "1:2",
    "name": "Home",
    "type": "FRAME",
    "absoluteBoundingBox": box(0, 0, 1440, 900),
    "layoutMode": "VERTICAL",
    "itemSpacing": 24,
    "paddingTop": 32, "paddingBottom": 32, "paddingLeft": 48, "paddingRight": 48,
    "counterAxisAlignItems": "CENTER",
    "fills": [solid(1, 1, 1)],
    "styles": {"fill": "S:bg"},
    "children": [
        {
            "id": "1:3", "name": "Title", "type": "TEXT",
            "absoluteBoundingBox": box(48, 32, 400, 40),
            "layoutSizingHorizontal": "HUG", "layoutSizingVertical": "HUG",
            "characters": "Welcome back",
            "style": {"fontFamily": "Inter", "fontSize": 32, "lineHeightPx": 40,
                      "fontWeight": 600},
            "styles": {"text": "S:h1"},
            "fills": [solid(0.0588, 0.0902, 0.1647)],
        },
        {
            "id": "1:4", "name": "Search icon", "type": "FRAME",
            "absoluteBoundingBox": box(48, 96, 24, 24),
            "children": [{"id": "1:5", "name": "Vector", "type": "VECTOR"}],
        },
        {
            "id": "1:6", "name": "Hero", "type": "RECTANGLE",
            "absoluteBoundingBox": box(48, 144, 600, 400),
            "layoutSizingHorizontal": "FILL",
            "cornerRadius": 12,
            "fills": [{"type": "IMAGE", "imageRef": "ref1", "scaleMode": "FILL"}],
            "effects": [{"type": "DROP_SHADOW", "visible": True, "radius": 8,
                         "offset": {"x": 0, "y": 4}, "color": {"r": 0, "g": 0, "b": 0,
                                                               "a": 0.1}}],
        },
        {
            "id": "1:7", "name": "Buy", "type": "INSTANCE", "componentId": "C:btn",
            "absoluteBoundingBox": box(48, 560, 120, 40),
            "layoutMode": "HORIZONTAL", "primaryAxisAlignItems": "CENTER",
            "paddingTop": 8, "paddingBottom": 8, "paddingLeft": 16, "paddingRight": 16,
            "children": [],
        },
        {"id": "1:8", "name": "Hidden", "type": "TEXT", "visible": False, "characters": "x"},
    ],
}  # fmt: skip


def fake_figma(calls: list[str]) -> FigmaClient:
    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(str(request.url))
        path = request.url.path
        if request.url.host == "files.example":
            assert "X-Figma-Token" not in request.headers  # signed URLs: no token
            return httpx2.Response(200, content=SVG if path.endswith(".svg") else PNG)
        assert request.headers["X-Figma-Token"] == "fake-token"
        if path == "/v1/files/AbC123xyz456/nodes":
            return httpx2.Response(
                200,
                json={
                    "nodes": {
                        "1:2": {
                            "document": FRAME,
                            "styles": {"S:bg": {"name": "Surface"}, "S:h1": {"name": "H1"}},
                            "components": {"C:btn": {"name": "Button/Primary"}},
                        }
                    }
                },
            )
        if path == "/v1/images/AbC123xyz456":
            return httpx2.Response(200, json={"images": {"1:4": "https://files.example/i.svg"}})
        if path == "/v1/files/AbC123xyz456/images":
            return httpx2.Response(
                200, json={"meta": {"images": {"ref1": "https://files.example/h"}}}
            )
        return httpx2.Response(404)

    return FigmaClient("fake-token", transport=httpx2.MockTransport(handler))


def test_find_link() -> None:
    link = find_link(f"Build the shop page.\nDesign: {URL}\nThanks")
    assert link is not None
    assert (link.file_key, link.node_id) == ("AbC123xyz456", "1:2")
    assert link.url == URL
    assert find_link("https://www.figma.com/file/AbC123xyz456/Old").node_id == ""  # type: ignore[union-attr]
    assert find_link("see https://figma.com.evil.io/design/AbC123xyz456") is None
    assert find_link("no design here") is None


def test_read_design_writes_assets_and_describes_layout(tmp_path: Path) -> None:
    calls: list[str] = []
    design = read_design(fake_figma(calls), find_link(URL), tmp_path)  # type: ignore[arg-type]

    assert design.assets == ["public/figma/hero.png", "public/figma/search-icon.svg"]
    assert (tmp_path / "public/figma/search-icon.svg").read_bytes() == SVG
    assert (tmp_path / "public/figma/hero.png").read_bytes() == PNG
    spec = design.spec
    assert 'frame "Home" w 1440 h 900 flex column gap 24 pad 32 48 align center bg #FFFFFF' in spec
    assert "font Inter 32/40 600 colour #0F172A" not in spec  # order: paint then font
    assert "colour #0F172A font Inter 32/40 600 text 'Welcome back'" in spec
    assert 'frame "Search icon" w 24 h 24 icon public/figma/search-icon.svg' in spec
    assert "Vector" not in spec  # inside the icon
    assert "image public/figma/hero.png fit cover radius 12 shadow 0 4 8 0 rgba(0,0,0,0.1)" in spec
    assert "w fill" in spec
    assert '(component "Button/Primary")' in spec
    assert "pad 8 16 justify center" in spec
    assert "Hidden" not in spec
    # Tokens, with the designer's style names
    assert '#FFFFFF "Surface" ×1' in spec
    assert 'Inter 32/40 600 "H1" ×1' in spec
    assert "Spacing (gaps and padding): 8, 16, 24, 32, 48" in spec
    assert "Corner radii: 12" in spec
    assert "public/figma/hero.png (served at /figma/hero.png)" in spec


def test_figma_refusing_access_is_a_clear_error(tmp_path: Path) -> None:
    client = FigmaClient(
        "fake-token", transport=httpx2.MockTransport(lambda r: httpx2.Response(403))
    )
    with pytest.raises(FigmaError, match="shared"):
        read_design(client, find_link(URL), tmp_path)  # type: ignore[arg-type]


def test_jira_keeps_smart_links_and_link_addresses() -> None:
    doc = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "Design: "},
                {"type": "inlineCard", "attrs": {"url": URL}},
            ]},
            {"type": "paragraph", "content": [
                {"type": "text", "text": "mockup",
                 "marks": [{"type": "link", "attrs": {"href": "https://x.io/m"}}]},
            ]},
            {"type": "blockCard", "attrs": {"url": "https://x.io/card"}},
        ],
    }  # fmt: skip
    assert adf_to_text(doc) == f"Design: {URL}\nmockup (https://x.io/m)\nhttps://x.io/card"


def test_a_linked_design_becomes_a_requirement() -> None:
    spec = TicketSpec.model_validate(READY)
    ticket = JiraTicket("KAN-1", "Story", "To Do", "Shop page", f"Build it like {URL}", [])
    with_link = with_design_link(spec, ticket)
    assert with_link.requirements[-1] == f"Match the linked Figma design: {URL}"
    assert design_link(with_link).node_id == "1:2"  # type: ignore[union-attr]
    assert with_design_link(with_link, ticket) == with_link  # not added twice
    other = URL.replace("1-2", "5-6")
    given = with_design_link(spec, ticket, other)  # given with the run: wins over the ticket
    assert given.requirements[-1] == f"Match the linked Figma design: {other}"
    plain = JiraTicket("KAN-1", "Story", "To Do", "Shop page", "no design", [])
    assert with_design_link(spec, plain) == spec
    assert design_link(spec) is None
