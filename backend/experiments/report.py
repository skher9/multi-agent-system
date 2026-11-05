"""The waste report for a benchmark round: cost, tokens and every tool call, per agent.

    cd backend && uv run python -m experiments.report <round>        # print it
    uv run python -m experiments.report <round> --json               # also save report.json

Each tool call is sorted into a kind, so waste is counted, not guessed:
- repeat read: a file the same agent already read and nobody changed since
- shell read: `cat`/`head`/`ls`/`find`/`grep`... through `run` instead of the read tools
- library: anything inside node_modules
- config read: a config/meta file (package.json, eslint, tsconfig...) the change didn't touch
- off-target read: a source file that isn't part of the final change
- useful: everything else (files in the change, edits, tests, checks)
Quality comes from tickets.json: the outcome, the files a good change touches, and the
files it should never touch.
"""

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import text

from api.config import get_settings
from db.session import get_engine
from experiments.bench import WORK, load_tickets

CONFIG_FILES = {
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "tsconfig.json",
    "next.config.ts",
    "eslint.config.mjs",
    "vitest.config.mts",
    "playwright.config.ts",
    "postcss.config.mjs",
    "README.md",
    "AGENTS.md",
    ".gitignore",
}
SHELL_READ = re.compile(r"^(cd \S+ && )?(cat|head|tail|sed -n|ls|find|grep|tree|wc)\b")
# Files any change may reasonably look at first (the app's shell)
ALWAYS_CONTEXT = ("src/app/layout", "src/app/page")
WASTE = ("repeat read", "shell read", "library", "config read", "off-target read")


def argument(raw: str, key: str) -> str:
    try:
        return str(json.loads(raw).get(key, ""))
    except (json.JSONDecodeError, AttributeError):
        match = re.search(rf'"{key}"\s*:\s*"([^"]*)', raw or "")
        return match.group(1) if match else ""


def target(raw: str) -> str:
    """What a tool call was about: its path, or the start of its command."""
    return argument(raw, "path") or argument(raw, "command")[:70]


def changed_files(repo: Path, key: str) -> set[str]:
    done = subprocess.run(  # noqa: S603
        ["git", f"--git-dir={repo}", "diff", "--name-only", "main", f"agent/{key}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return set(done.stdout.split()) if done.returncode == 0 else set()


def classify(calls: list[dict[str, Any]], change: set[str]) -> list[tuple[dict[str, Any], str]]:
    """Sort one agent run's tool calls (in order) into kinds."""
    read_at: dict[str, int] = {}
    out = []
    for i, call in enumerate(calls):
        tool, raw = call["tool"], call["arguments"]
        path = argument(raw, "path")
        command = argument(raw, "command")
        if "node_modules" in path or "node_modules" in command:
            kind = "library"
        elif tool == "run" and SHELL_READ.match(command.strip()):
            kind = "shell read"
        elif tool == "read_file":
            if path in read_at:
                kind = "repeat read"
            elif Path(path).name in CONFIG_FILES and path not in change:
                kind = "config read"
            elif (
                change
                and path not in change
                and not path.startswith(("src/app/layout", "src/app/page"))
            ):
                kind = "off-target read"
            else:
                kind = "useful"
            read_at[path] = i
        else:
            kind = "useful"
            if tool in ("edit_file", "create_file", "delete_file"):
                read_at.pop(path, None)  # changed: reading it again is fair
        out.append((call, kind))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("round")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = json.loads((WORK / "rounds" / args.round / "result.json").read_text())
    repo = WORK / "rounds" / args.round / "repo.git"
    expect = {t["id"]: t["expect"] for t in load_tickets()}
    url = get_settings().database_url_test
    if url is None:
        raise SystemExit("Needs DATABASE_URL_TEST in backend/.env")
    engine = get_engine(url.get_secret_value())

    report: dict[str, Any] = {"round": args.round, "tickets": {}}
    totals: dict[str, Counter[str]] = defaultdict(Counter)
    with engine.connect() as c:
        for tid, info in result["tickets"].items():
            key = info["key"]
            feature = c.execute(
                text("select id from features where project_id=:p and jira_key=:k"),
                {"p": result["project_id"], "k": key},
            ).scalar()
            if feature is None:
                continue
            calls = c.execute(
                text(
                    """select ar.id, ar.role, count(l.id), coalesce(sum(l.cost_inr),0),
                       coalesce(sum(l.input_tokens),0), coalesce(sum(l.cached_tokens),0),
                       coalesce(sum(l.output_tokens),0), coalesce(avg(l.latency_ms),0),
                       coalesce(max(l.input_tokens),0)
                       from agent_runs ar join tasks t on t.id=ar.task_id
                       left join llm_calls l on l.agent_run_id=ar.id
                       where t.feature_id=:f group by ar.id, ar.role order by ar.id"""
                ),
                {"f": feature},
            ).all()
            events = c.execute(
                text(
                    """select agent_run_id, kind, data from run_events
                       where feature_id=:f order by id"""
                ),
                {"f": feature},
            ).all()
            change = changed_files(repo, key)
            by_run: dict[int, list[dict[str, Any]]] = defaultdict(list)
            rejected: Counter[int] = Counter()
            fixes = 0
            for run_id, kind, data in events:
                if kind == "tool_call":
                    by_run[run_id].append(
                        {"tool": data["tool"], "arguments": data.get("arguments", "")}
                    )
                elif kind == "finish_rejected":
                    rejected[run_id] += 1
                elif kind == "node_finished" and data.get("node") == "fix":
                    fixes += 1
            agents = []
            for run_id, role, n, cost, tin, cached, tout, latency, biggest in calls:
                kinds = classify(by_run.get(run_id, []), change)
                count = Counter(k for _, k in kinds)
                agents.append(
                    {
                        "role": role,
                        "model_calls": n,
                        "cost_inr": round(float(cost), 2),
                        "input_tokens": int(tin),
                        "cache_pct": round(100 * int(cached) / int(tin)) if tin else 0,
                        "output_tokens": int(tout),
                        "avg_latency_s": round(float(latency) / 1000, 1),
                        "largest_prompt": int(biggest),
                        "tool_calls": len(kinds),
                        "kinds": dict(count),
                        "rejected_finishes": rejected[run_id],
                        "waste": [
                            f"{k}: {c['tool']} {target(c['arguments'])}"
                            for c, k in kinds
                            if k in WASTE
                        ],
                    }
                )
                totals[role]["cost_paise"] += round(float(cost) * 100)
                totals[role]["tool_calls"] += len(kinds)
                totals[role]["waste"] += sum(count[k] for k in WASTE)
                totals[role]["model_calls"] += n
            want = expect[tid]
            quality = {
                "outcome_ok": info["outcome"] == want["outcome"],
                "missing": sorted(set(want["touch"]) - change),
                "forbidden_touched": sorted(set(want["never"]) & change),
                "fix_rounds": fixes,
                "files_changed": sorted(change),
            }
            report["tickets"][tid] = {**info, "agents": agents, "quality": quality}

    print_report(report, totals)
    if args.json:
        out = WORK / "rounds" / args.round / "report.json"
        out.write_text(json.dumps(report, indent=2))
        print(f"\nSaved {out}")


def print_report(report: dict[str, Any], totals: dict[str, Counter[str]]) -> None:
    print(f"# Round {report['round']}\n")
    grand = 0.0
    for tid, t in report["tickets"].items():
        q = t["quality"]
        cost = sum(a["cost_inr"] for a in t["agents"])
        grand += cost
        ok = "✅" if q["outcome_ok"] and not q["missing"] and not q["forbidden_touched"] else "❌"
        print(
            f"## {ok} {tid} ({t['key']}): {t['outcome']}, ₹{cost:.2f},"
            f" {t['seconds']}s, fixes {q['fix_rounds']}"
        )
        if q["missing"] or q["forbidden_touched"]:
            print(f"   quality: missing {q['missing']} forbidden {q['forbidden_touched']}")
        print(f"   changed: {', '.join(q['files_changed']) or '-'}")
        for a in t["agents"]:
            waste = sum(a["kinds"].get(k, 0) for k in WASTE)
            print(
                f"   {a['role']:<13} ₹{a['cost_inr']:<6} calls {a['model_calls']:<3}"
                f" tools {a['tool_calls']:<3}"
                f" waste {waste:<3} cache {a['cache_pct']}% lat {a['avg_latency_s']}s"
                f" prompt≤{a['largest_prompt']} rejected {a['rejected_finishes']}"
            )
            for line in a["waste"]:
                print(f"      - {line}")
        print()
    print("## Totals by agent")
    for role, c in sorted(totals.items(), key=lambda kv: -kv[1]["cost_paise"]):
        share = 100 * c["waste"] / c["tool_calls"] if c["tool_calls"] else 0
        print(
            f"   {role:<13} ₹{c['cost_paise'] / 100:<7.2f} model calls {c['model_calls']:<4}"
            f" tool calls {c['tool_calls']:<4} waste {c['waste']} ({share:.0f}%)"
        )
    print(f"\n   round total ₹{grand:.2f}")


if __name__ == "__main__":
    main()
