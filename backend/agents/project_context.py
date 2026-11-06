"""The Project Context: what every agent needs to know about the repo before it starts.

Without it, each agent started blank and rediscovered the same things: the planner,
developer and reviewer each read package.json, tsconfig, eslint, vitest, playwright,
next.config, AGENTS.md and README on every ticket (~100 reads in one benchmark round).
Now they are read once, here, and every agent gets them as <project_context>.

Built from the repo's own files, no model call: free, exact, the same for the same
commit. It sits next to the code graph (structure: where things are) and the repo rules
(learned from reviews): together, one shared context.

Files listed in CONTEXT_FILES are answered from here when an agent asks to read them
(see RepoTools), unless the agent changed them in this run.
"""

import json
from pathlib import Path

from agents import skills

# Small files that describe the project rather than implement it
CONTEXT_FILES = (
    "AGENTS.md",
    "README.md",
    "package.json",
    "tsconfig.json",
    "next.config.ts",
    "next.config.js",
    "next.config.mjs",
    "eslint.config.mjs",
    "vitest.config.mts",
    "vitest.config.ts",
    "playwright.config.ts",
    "postcss.config.mjs",
    "pnpm-workspace.yaml",
)
MAX_FILE_CHARS = 4000  # one file's share; real config files are far smaller
MAX_TREE_FILES = 300


def context_files(root: Path) -> list[str]:
    """The CONTEXT_FILES this repo has, as repo-relative paths."""
    return [name for name in CONTEXT_FILES if (root / name).is_file()]


def project_context(root: Path, tracked_files: list[str]) -> str:
    """The <project_context> block: stack and scripts, the config files themselves,
    the repo's own instructions, and the file tree."""
    parts = ["<project_context>", _stack(root)]
    for name in context_files(root):
        if name == "package.json":
            continue  # summarised in the stack above
        text = (root / name).read_text(errors="replace")
        if len(text) > MAX_FILE_CHARS:
            text = text[:MAX_FILE_CHARS] + f"\n... (cut; read_file {name} for the rest)"
        parts.append(f'<file path="{name}">\n{text.strip()}\n</file>')
    tree = "\n".join(tracked_files[:MAX_TREE_FILES])
    if len(tracked_files) > MAX_TREE_FILES:
        tree += f"\n... ({len(tracked_files) - MAX_TREE_FILES} more; use list_files)"
    parts.append(f"<file_tree>\n{tree}\n</file_tree>")
    if catalog := skills.catalog(root):
        parts.append(catalog)
    parts.append("</project_context>")
    return "\n\n".join(parts)


def _stack(root: Path) -> str:
    """package.json, cut to what agents use: scripts and exact package versions."""
    path = root / "package.json"
    if not path.is_file():
        return "<stack>No package.json.</stack>"
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return f'<file path="package.json">\n{path.read_text()[:MAX_FILE_CHARS]}\n</file>'
    lines = [f"Package manager: {data.get('packageManager', 'see lockfile')}"]
    scripts = data.get("scripts") or {}
    if scripts:
        lines.append("Scripts (pnpm <name>):")
        lines += [f"  {name}: {command}" for name, command in scripts.items()]
    for field in ("dependencies", "devDependencies"):
        packages = data.get(field) or {}
        if packages:
            lines.append(f"{field}: " + ", ".join(f"{n}@{v}" for n, v in packages.items()))
    return "<stack>\n" + "\n".join(lines) + "\n</stack>"


MAX_HANDOFF_CHARS = 40_000  # all handed-over files together (~10k tokens)


def file_blocks(root: Path, paths: list[str]) -> str:
    """Files' current contents as <file> blocks, for handing work from one agent to the
    next. Paths that aren't text files in the repo are skipped."""
    blocks: list[str] = []
    used = 0
    for rel in paths:
        path = (root / rel).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        if used + len(text) > MAX_HANDOFF_CHARS:
            blocks.append(f'<file path="{rel}">(too long to include; read_file it)</file>')
            continue
        used += len(text)
        blocks.append(f'<file path="{rel}">\n{text.rstrip()}\n</file>')
    return "\n".join(blocks)
