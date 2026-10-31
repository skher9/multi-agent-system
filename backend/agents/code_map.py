"""A map of the files that matter for one ticket, ranked from its code graph (like Aider's
repo map).

Graphify's report describes the whole repo; on a small repo it's mostly config keys.
This ranks files for the ticket instead, with personalized PageRank:

1. Collapse the graph to files: two files are linked when something in one uses
   something in the other (imports, calls).
2. Give a head start to files whose path or functions share words with the ticket
   ("contact" in the ticket -> src/app/contact/page.tsx, ContactForm()).
3. PageRank spreads that head start along the links, so the files those touch rank
   too (the layout a new page goes in, the component it reuses).

Pure Python on graph.json (networkx's node-link format): no model call, no sandbox.
"""

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from agents.ticket_reader import TicketSpec

MAX_FILES = 15
MAX_NAMES_PER_FILE = 6
DAMPING = 0.5  # PageRank: chance of following a link vs jumping back to a head start. Lower
# than the usual 0.85: graphify links are undirected, so at 0.85 shared components (a
# Button every page uses) outrank the files that actually match the ticket.
ITERATIONS = 40
# "contains" links a file to its own functions; it says nothing about other files
SKIPPED_RELATIONS = {"contains"}
MIN_WORD = 3
STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "when", "then", "than",
    "should", "must", "can", "will", "are", "has", "have", "not", "all", "any", "each",
    "page", "add", "new", "show", "shows", "use", "uses", "using",
}  # fmt: skip


def words(text: str) -> set[str]:
    """Lowercase words in text, split on camelCase, dashes, dots and slashes; plurals
    folded ("forms" -> "form") so a ticket word matches a name either way."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    found = set()
    for word in re.findall(r"[a-z0-9]+", spaced.lower()):
        if word.endswith("s") and len(word) > MIN_WORD + 1:
            word = word[:-1]
        if len(word) >= MIN_WORD and word not in STOP_WORDS:
            found.add(word)
    return found


def ticket_words(spec: TicketSpec) -> set[str]:
    return words(
        " ".join([spec.title, spec.summary, *spec.requirements, *spec.acceptance_criteria])
    )


def ticket_code_map(graph_json: Path, spec: TicketSpec, *, limit: int = MAX_FILES) -> str:
    """The top files for this ticket, one line each: why it ranked and what's in it.
    Empty if the graph has no files."""
    graph: dict[str, Any] = json.loads(graph_json.read_text())
    file_of: dict[str, str] = {}
    names: dict[str, list[str]] = defaultdict(list)
    for node in graph.get("nodes", []):
        path = node.get("source_file")
        if not path:
            continue
        file_of[node["id"]] = path
        label = node.get("label", "")
        if label and label != Path(path).name:  # the file's own node isn't a name in it
            names[path].append(label)
    files = sorted(set(file_of.values()))
    if not files:
        return ""

    links: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for link in graph.get("links", []):
        if link.get("relation") in SKIPPED_RELATIONS:
            continue
        a, b = file_of.get(link["source"]), file_of.get(link["target"])
        if a and b and a != b:
            weight = float(link.get("weight", 1.0))
            links[a][b] += weight  # graphify's graph is undirected: both ways
            links[b][a] += weight

    wanted = ticket_words(spec)
    matches = {f: sorted(wanted & (words(f) | words(" ".join(names[f])))) for f in files}
    head_start = {f: float(len(m)) for f, m in matches.items()}
    rank = _pagerank(files, links, head_start)

    top = sorted(files, key=lambda f: (-rank[f], f))[:limit]
    lines = []
    for n, path in enumerate(top, 1):
        why = []
        if matches[path]:
            why.append("matches " + ", ".join(matches[path]))
        if links[path]:
            why.append(f"linked to {len(links[path])} files")
        shown = ", ".join(names[path][:MAX_NAMES_PER_FILE])
        more = len(names[path]) - MAX_NAMES_PER_FILE
        if more > 0:
            shown += f", +{more} more"
        line = f"{n}. {path}"
        if why:
            line += f" ({'; '.join(why)})"
        if shown:
            line += f": {shown}"
        lines.append(line)
    return "\n".join(lines)


def _pagerank(
    files: list[str], links: dict[str, dict[str, float]], head_start: dict[str, float]
) -> dict[str, float]:
    """Personalized PageRank by power iteration. With no head start anywhere (no word
    matched), every file starts equal: plain PageRank, the most connected files first."""
    total = sum(head_start.values())
    start = (
        {f: head_start[f] / total for f in files} if total else {f: 1 / len(files) for f in files}
    )
    rank = dict(start)
    out_weight = {f: sum(links[f].values()) for f in files}
    for _ in range(ITERATIONS):
        # A file with no links passes its rank back to the head start, so none is lost
        stuck = sum(rank[f] for f in files if not out_weight[f])
        new = {f: (1 - DAMPING + DAMPING * stuck) * start[f] for f in files}
        for f in files:
            if out_weight[f]:
                share = DAMPING * rank[f] / out_weight[f]
                for neighbour, weight in links[f].items():
                    new[neighbour] += share * weight
        rank = new
    return rank
