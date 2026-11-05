"""Skills: short, checked know-how an agent loads only when it needs it (progressive
disclosure, as in Anthropic's Agent Skills).

Every agent sees the catalogue (a name and one line each, in <project_context>); the
full text comes from the load_skill tool. In the benchmark, agents read up to ~110
pages of node_modules docs per round because the repo's AGENTS.md tells them to; a skill
gives the few facts a ticket needs, already verified (e.g. next/link needs no mock in
unit tests, which several agents worried about).

A skill is a Markdown file in agents/skills/ with frontmatter: name, description, and
`when`: the package in package.json that makes it relevant.
"""

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent / "skills"
FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
WHEN = re.compile(r"^\"?([@\w./-]+)\"? in package\.json$")


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    when: str  # package name; "" = always
    body: str


@cache
def all_skills() -> tuple[Skill, ...]:
    skills = []
    for path in sorted(SKILLS_DIR.glob("*.md")):
        text = path.read_text()
        match = FRONTMATTER.match(text)
        if not match:
            continue
        meta = dict(line.split(":", 1) for line in match.group(1).splitlines() if ":" in line)
        when = WHEN.match(meta.get("when", "").strip())
        skills.append(
            Skill(
                name=meta["name"].strip(),
                description=meta["description"].strip(),
                when=when.group(1) if when else "",
                body=text[match.end() :].strip(),
            )
        )
    return tuple(skills)


def skills_for(root: Path) -> list[Skill]:
    """The skills that apply to this repo (their package is in package.json)."""
    packages: set[str] = set()
    path = root / "package.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text())
            for field in ("dependencies", "devDependencies"):
                packages |= set(data.get(field) or {})
        except json.JSONDecodeError:
            pass
    return [s for s in all_skills() if not s.when or s.when in packages]


def catalog(root: Path) -> str:
    """The <skills> block for <project_context>: names and one line each."""
    skills = skills_for(root)
    if not skills:
        return ""
    lines = "\n".join(f"- {s.name}: {s.description}" for s in skills)
    return (
        "<skills>\nChecked know-how for this repo. Load one with load_skill before reading "
        "library docs in node_modules: it has what tickets here usually need, and points "
        f"to the exact docs page when more is needed.\n{lines}\n</skills>"
    )


def load(root: Path, name: str) -> str:
    for skill in skills_for(root):
        if skill.name == name:
            return skill.body
    names = ", ".join(s.name for s in skills_for(root)) or "none"
    raise KeyError(f"no skill {name!r} for this repo; available: {names}")
