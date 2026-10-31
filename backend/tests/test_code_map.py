"""Ranking a repo's files for one ticket from its code graph."""

import json
from pathlib import Path
from typing import Any

from agents.code_map import ticket_code_map, words
from agents.ticket_reader import TicketSpec
from tests.test_ticket_reader import READY


def node(node_id: str, label: str, path: str) -> dict[str, Any]:
    return {"id": node_id, "label": label, "source_file": path}


def link(source: str, target: str, relation: str = "imports") -> dict[str, Any]:
    return {"source": source, "target": target, "relation": relation, "weight": 1.0}


def write_graph(tmp_path: Path) -> Path:
    graph = {
        "directed": False,
        "multigraph": False,
        "nodes": [
            node("page", "page.tsx", "src/app/page.tsx"),
            node("page_home", "Home()", "src/app/page.tsx"),
            node("form", "ContactForm.tsx", "src/components/ContactForm.tsx"),
            node("form_fn", "ContactForm()", "src/components/ContactForm.tsx"),
            node("button", "Button()", "src/components/ui/button.tsx"),
            node("cn", "cn()", "src/lib/utils.ts"),
            node("config", "next.config.ts", "next.config.ts"),
        ],
        "links": [
            link("page", "page_home", "contains"),
            link("form", "form_fn", "contains"),
            link("form_fn", "button"),
            link("button", "cn"),
            link("page_home", "button"),
        ],
    }
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph))
    return path


def spec(summary: str) -> TicketSpec:
    """A ticket whose every field says only this."""
    return TicketSpec.model_validate(
        {
            **READY,
            "title": summary,
            "summary": summary,
            "requirements": [summary],
            "acceptance_criteria": [summary],
        }
    )


def test_words_split_names_and_fold_plurals() -> None:
    assert words("ContactForm") == {"contact", "form"}
    assert words("src/app/contact-forms/page.tsx") == {"src", "app", "contact", "form", "tsx"}
    assert "the" not in words("the header")


def test_files_matching_the_ticket_come_first_then_what_they_use(tmp_path: Path) -> None:
    ticket = spec("Add a contact form")
    ranked = ticket_code_map(write_graph(tmp_path), ticket).splitlines()
    assert ranked[0].startswith("1. src/components/ContactForm.tsx (matches contact, form")
    assert ranked[0].endswith(": ContactForm()")
    # The button the form uses outranks files the form never touches
    order = [line.split(" ")[1] for line in ranked]
    assert order.index("src/components/ui/button.tsx") < order.index("next.config.ts")


def test_without_a_match_the_most_connected_files_come_first(tmp_path: Path) -> None:
    ranked = ticket_code_map(write_graph(tmp_path), spec("Zebra unicorn")).splitlines()
    assert ranked[0].startswith("1. src/components/ui/button.tsx (linked to 3 files)")


def test_limit_caps_the_list(tmp_path: Path) -> None:
    assert len(ticket_code_map(write_graph(tmp_path), spec("x"), limit=2).splitlines()) == 2


def test_an_empty_graph_gives_an_empty_map(tmp_path: Path) -> None:
    path = tmp_path / "graph.json"
    path.write_text(json.dumps({"nodes": [], "links": []}))
    assert ticket_code_map(path, spec("contact")) == ""
