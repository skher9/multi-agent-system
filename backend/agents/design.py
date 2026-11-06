"""Design reader: turns a linked Figma frame into a spec the planner and developer build
from, and puts the design's images and icons into the repo.

Plain code, no model: the numbers must be exact, not guessed. Designs built from Figma
look wrong for a few known reasons, each handled here:
- Fixed pixel positions instead of layout: Figma's auto-layout (direction, gap, padding,
  alignment, fill/hug sizing) maps one-to-one onto CSS flexbox, so the spec says "flex
  column gap 24" rather than coordinates. Only layers without auto-layout get positions.
- Near-duplicate colours and uneven spacing: the tokens section lists every colour, text
  style, gap and radius the design uses (with the designer's style names), so the code
  can use one set of values.
- Redrawn or missing icons: icons and images are exported from Figma as files, and the
  spec says where each one goes.
- Rebuilt components: instances name their Figma component, so the developer can match
  them to the repo's own components.

Layer text and names come from whoever made the design: data, never instructions.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from services.figma import FigmaClient, FigmaError, FigmaFrame, FigmaLink

ASSET_DIR = "public/figma"  # Next.js serves public/ at the site root
MAX_SPEC_CHARS = 30_000
MAX_TEXT_CHARS = 300  # one text layer
MAX_ICON_PX = 96  # a vector-only group up to this size is exported as one icon
MAX_ASSETS = 40
VECTOR_TYPES = {"VECTOR", "BOOLEAN_OPERATION", "STAR", "LINE", "POLYGON", "REGULAR_POLYGON"}
CONTAINER_TYPES = {"FRAME", "GROUP", "INSTANCE", "COMPONENT", "COMPONENT_SET", "SECTION"}
JUSTIFY = {"MIN": "start", "CENTER": "center", "MAX": "end", "SPACE_BETWEEN": "between"}
ALIGN = {"MIN": "start", "CENTER": "center", "MAX": "end", "BASELINE": "baseline"}
IMAGE_TYPES = {b"\x89PNG": "png", b"\xff\xd8\xff": "jpg", b"GIF8": "gif", b"RIFF": "webp"}


@dataclass
class Design:
    link: str
    name: str
    spec: str  # the <design> block's body
    assets: list[str] = field(default_factory=list)  # repo paths written


@dataclass
class _Assets:
    icons: dict[str, str] = field(default_factory=dict)  # node id -> repo path
    images: dict[str, str] = field(default_factory=dict)  # imageRef -> repo path


@dataclass
class _Tokens:
    colours: Counter[str] = field(default_factory=Counter)
    colour_names: dict[str, str] = field(default_factory=dict)
    text: Counter[str] = field(default_factory=Counter)
    text_names: dict[str, str] = field(default_factory=dict)
    spacing: set[float] = field(default_factory=set)
    radii: set[float] = field(default_factory=set)


def read_design(client: FigmaClient, link: FigmaLink, root: Path) -> Design:
    """Fetch the frame, write its images and icons under root/public/figma, and describe
    it. Raises FigmaError if Figma can't give the frame."""
    frame = client.frame(link)
    assets = _export_assets(client, link.file_key, frame.document, root)
    tokens = _Tokens()
    lines: list[str] = []
    _describe(frame.document, frame, assets, tokens, lines, depth=0, parent=None)
    layers = "\n".join(lines)
    if len(layers) > MAX_SPEC_CHARS:
        layers = layers[:MAX_SPEC_CHARS] + "\n… (deeper layers cut: the frame is very large)"
    files = sorted({*assets.icons.values(), *assets.images.values()})
    spec = f"""\
Figma frame "{frame.document.get("name", "")}": {link.url}

Build the screen to match this design. Layouts are Figma auto-layout written as flexbox:
"flex column gap 24 pad 32 48 justify between align center" means display:flex,
flex-direction:column, gap 24px, padding 32px 48px, justify-content:space-between,
align-items:center. "w fill" = stretch to the parent, "w hug" = fit the content, a number
is a fixed size in px. Layers marked "positioned" have no auto-layout: use their position
to work out a flex or grid layout; never absolute-position a whole screen.

Tokens (most used first; the designer's style names in quotes):
{_tokens_text(tokens)}

Assets already in the repo (use them exactly where the layers say; don't redraw them):
{chr(10).join(f"- {f} (served at /{f.removeprefix('public/')})" for f in files) or "- none"}

Layers:
{layers}"""
    return Design(link.url, frame.document.get("name", ""), spec, files)


def design_block(design: Design | None) -> str:
    if design is None:
        return ""
    return f"\n\n<design>\n{design.spec}\n</design>"


# --- assets ---------------------------------------------------------------------------


def _export_assets(
    client: FigmaClient, file_key: str, document: dict[str, Any], root: Path
) -> _Assets:
    icon_nodes: dict[str, str] = {}  # node id -> name
    image_refs: dict[str, str] = {}  # imageRef -> layer name

    def walk(node: dict[str, Any]) -> None:
        if node.get("visible") is False or len(icon_nodes) + len(image_refs) >= MAX_ASSETS:
            return
        for fill in _visible(node.get("fills")):
            if fill.get("type") == "IMAGE" and fill.get("imageRef"):
                image_refs.setdefault(fill["imageRef"], node.get("name", "image"))
        if _is_icon(node):
            icon_nodes[node["id"]] = node.get("name", "icon")
            return
        for child in node.get("children", []):
            walk(child)

    walk(document)
    out = _Assets()
    used: set[str] = set()
    target = root / ASSET_DIR
    if icon_nodes:
        for node_id, url in client.render(file_key, list(icon_nodes), "svg").items():
            path = _unique(f"{ASSET_DIR}/{_slug(icon_nodes[node_id])}", "svg", used)
            target.mkdir(parents=True, exist_ok=True)
            (root / path).write_bytes(client.download(url))
            out.icons[node_id] = path
    if image_refs:
        urls = client.image_fills(file_key)
        for ref, name in image_refs.items():
            if ref not in urls:
                continue
            data = client.download(urls[ref])
            ext = next((e for magic, e in IMAGE_TYPES.items() if data.startswith(magic)), "png")
            path = _unique(f"{ASSET_DIR}/{_slug(name)}", ext, used)
            target.mkdir(parents=True, exist_ok=True)
            (root / path).write_bytes(data)
            out.images[ref] = path
    return out


def _is_icon(node: dict[str, Any]) -> bool:
    kind = node.get("type")
    if kind in VECTOR_TYPES:
        return True
    if kind not in CONTAINER_TYPES or not node.get("children"):
        return False
    box = node.get("absoluteBoundingBox") or {}
    if box.get("width", 1e9) > MAX_ICON_PX or box.get("height", 1e9) > MAX_ICON_PX:
        return False
    return all(_vector_only(c) for c in node["children"])


def _vector_only(node: dict[str, Any]) -> bool:
    if node.get("type") in VECTOR_TYPES | {"ELLIPSE", "RECTANGLE"}:
        return not any(f.get("type") == "IMAGE" for f in _visible(node.get("fills")))
    if node.get("type") in CONTAINER_TYPES:
        return all(_vector_only(c) for c in node.get("children", []))
    return False


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "asset"


def _unique(base: str, ext: str, used: set[str]) -> str:
    path, n = f"{base}.{ext}", 2
    while path in used:
        path, n = f"{base}-{n}.{ext}", n + 1
    used.add(path)
    return path


# --- layers ---------------------------------------------------------------------------


def _describe(
    node: dict[str, Any],
    frame: FigmaFrame,
    assets: _Assets,
    tokens: _Tokens,
    lines: list[str],
    depth: int,
    parent: dict[str, Any] | None,
) -> None:
    if node.get("visible") is False:
        return
    kind = node.get("type", "")
    name = node.get("name", "")
    parts = [f'{kind.lower()} "{name}"']
    if kind == "INSTANCE" and node.get("componentId") in frame.components:
        parts.append(f'(component "{frame.components[node["componentId"]]}")')
    parts.append(_size(node))
    if parent is not None and _positioned(node, parent):
        parts.append(_position(node, parent))
    if node["id"] in assets.icons:
        parts.append(f"icon {assets.icons[node['id']]}")
        lines.append("  " * depth + " ".join(p for p in parts if p))
        return
    parts += _layout(node, tokens)
    parts += _paint(node, frame, assets, tokens)
    if kind == "TEXT":
        parts += _text(node, frame, tokens)
    lines.append("  " * depth + " ".join(p for p in parts if p))
    for child in node.get("children", []):
        _describe(child, frame, assets, tokens, lines, depth + 1, node)


def _size(node: dict[str, Any]) -> str:
    box = node.get("absoluteBoundingBox") or {}
    w = node.get("layoutSizingHorizontal")
    h = node.get("layoutSizingVertical")
    width = {"FILL": "fill", "HUG": "hug"}.get(w or "", _px(box.get("width")))
    height = {"FILL": "fill", "HUG": "hug"}.get(h or "", _px(box.get("height")))
    return f"w {width} h {height}"


def _positioned(node: dict[str, Any], parent: dict[str, Any]) -> bool:
    return parent.get("layoutMode", "NONE") == "NONE" or node.get("layoutPositioning") == "ABSOLUTE"


def _position(node: dict[str, Any], parent: dict[str, Any]) -> str:
    box = node.get("absoluteBoundingBox") or {}
    pbox = parent.get("absoluteBoundingBox") or {}
    x = _px(box.get("x", 0) - pbox.get("x", 0))
    y = _px(box.get("y", 0) - pbox.get("y", 0))
    return f"positioned x {x} y {y}"


def _layout(node: dict[str, Any], tokens: _Tokens) -> list[str]:
    mode = node.get("layoutMode", "NONE")
    if mode == "NONE":
        return []
    parts = ["flex " + ("row" if mode == "HORIZONTAL" else "column")]
    justify = node.get("primaryAxisAlignItems", "MIN")
    gap = node.get("itemSpacing", 0)
    if gap and justify != "SPACE_BETWEEN":
        parts.append(f"gap {_px(gap)}")
        tokens.spacing.add(gap)
    if node.get("layoutWrap") == "WRAP":
        parts.append("wrap")
        if row_gap := node.get("counterAxisSpacing"):
            parts.append(f"row-gap {_px(row_gap)}")
            tokens.spacing.add(row_gap)
    pad = [node.get(f"padding{s}", 0) for s in ("Top", "Right", "Bottom", "Left")]
    if any(pad):
        tokens.spacing.update(p for p in pad if p)
        if pad[0] == pad[2] and pad[1] == pad[3]:
            shown = [pad[0]] if pad[0] == pad[1] else [pad[0], pad[1]]
        else:
            shown = pad
        parts.append("pad " + " ".join(_px(p) for p in shown))
    if justify != "MIN":
        parts.append(f"justify {JUSTIFY.get(justify, 'start')}")
    align = node.get("counterAxisAlignItems", "MIN")
    if align != "MIN":
        parts.append(f"align {ALIGN.get(align, 'start')}")
    return parts


def _paint(node: dict[str, Any], frame: FigmaFrame, assets: _Assets, tokens: _Tokens) -> list[str]:
    parts: list[str] = []
    is_text = node.get("type") == "TEXT"
    style_ids = node.get("styles") or {}
    for fill in _visible(node.get("fills")):
        kind = fill.get("type")
        if kind == "SOLID":
            colour = _colour(fill)
            _count_colour(tokens, colour, frame.styles.get(style_ids.get("fill", "")))
            parts.append(f"{'colour' if is_text else 'bg'} {colour}")
        elif kind and kind.startswith("GRADIENT"):
            stops = ", ".join(_colour(s) for s in fill.get("gradientStops", []))
            parts.append(f"bg {kind.removeprefix('GRADIENT_').lower()}-gradient({stops})")
        elif kind == "IMAGE" and fill.get("imageRef") in assets.images:
            fit = "contain" if fill.get("scaleMode") == "FIT" else "cover"
            parts.append(f"image {assets.images[fill['imageRef']]} fit {fit}")
    strokes = list(_visible(node.get("strokes")))
    if strokes and node.get("strokeWeight"):
        colour = _colour(strokes[0])
        _count_colour(tokens, colour, frame.styles.get(style_ids.get("stroke", "")))
        parts.append(f"border {_px(node['strokeWeight'])} {colour}")
    if radii := node.get("rectangleCornerRadii"):
        if len(set(radii)) == 1:
            radii = radii[:1]
        tokens.radii.update(r for r in radii if r)
        if any(radii):
            parts.append("radius " + " ".join(_px(r) for r in radii))
    elif radius := node.get("cornerRadius"):
        tokens.radii.add(radius)
        parts.append(f"radius {_px(radius)}")
    for effect in _visible(node.get("effects")):
        kind = effect.get("type")
        if kind in ("DROP_SHADOW", "INNER_SHADOW"):
            off = effect.get("offset") or {}
            inset = "inset " if kind == "INNER_SHADOW" else ""
            parts.append(
                f"shadow {inset}{_px(off.get('x', 0))} {_px(off.get('y', 0))} "
                f"{_px(effect.get('radius', 0))} {_px(effect.get('spread', 0))} "
                f"{_colour(effect)}"
            )
        elif kind in ("LAYER_BLUR", "BACKGROUND_BLUR"):
            prefix = "backdrop-" if kind == "BACKGROUND_BLUR" else ""
            parts.append(f"{prefix}blur {_px(effect.get('radius', 0))}")
    opacity = node.get("opacity", 1)
    if opacity < 1:
        parts.append(f"opacity {round(opacity, 2)}")
    return parts


def _text(node: dict[str, Any], frame: FigmaFrame, tokens: _Tokens) -> list[str]:
    style = node.get("style") or {}
    size = style.get("fontSize")
    line = style.get("lineHeightPx")
    font = (
        f"{style.get('fontFamily', '')} {_px(size)}/{_px(line) if line else 'normal'} "
        f"{style.get('fontWeight', 400)}"
    )
    style_name = frame.styles.get((node.get("styles") or {}).get("text", ""))
    tokens.text[font] += 1
    if style_name:
        tokens.text_names[font] = style_name
    parts = [f"font {font}"]
    if spacing := style.get("letterSpacing"):
        parts.append(f"tracking {_px(spacing)}")
    if (align := style.get("textAlignHorizontal")) and align != "LEFT":
        parts.append(f"text-{align.lower()}")
    if style.get("textCase") == "UPPER":
        parts.append("uppercase")
    if style.get("textDecoration") == "UNDERLINE":
        parts.append("underline")
    text = (node.get("characters") or "").replace("\n", "\\n")
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + "…"
    parts.append(f"text {text!r}")
    return parts


def _tokens_text(tokens: _Tokens) -> str:
    def named(value: str, names: dict[str, str], count: int) -> str:
        name = f' "{names[value]}"' if value in names else ""
        return f"{value}{name} ×{count}"

    colours = ", ".join(named(c, tokens.colour_names, n) for c, n in tokens.colours.most_common())
    text = "\n".join(f"  - {named(t, tokens.text_names, n)}" for t, n in tokens.text.most_common())
    return f"""\
- Colours: {colours or "none"}
- Text styles (family size/line-height weight):
{text or "  - none"}
- Spacing (gaps and padding): {", ".join(_px(s) for s in sorted(tokens.spacing)) or "none"}
- Corner radii: {", ".join(_px(r) for r in sorted(tokens.radii)) or "none"}
Map these to the repo's existing tokens where they match; add any missing ones once, in
the repo's theme, instead of repeating raw values."""


# --- helpers --------------------------------------------------------------------------


def _visible(paints: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [p for p in paints or [] if p.get("visible", True)]


def _count_colour(tokens: _Tokens, colour: str, name: str | None) -> None:
    tokens.colours[colour] += 1
    if name:
        tokens.colour_names[colour] = name


def _colour(paint: dict[str, Any]) -> str:
    c = paint.get("color") or {}
    r, g, b = (round(c.get(k, 0) * 255) for k in ("r", "g", "b"))
    alpha = round(c.get("a", 1) * paint.get("opacity", 1), 2)
    if alpha < 1:
        return f"rgba({r},{g},{b},{alpha})"
    return f"#{r:02X}{g:02X}{b:02X}"


def _px(value: float | None) -> str:
    if value is None:
        return "?"
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


__all__ = ["Design", "FigmaError", "design_block", "read_design"]
