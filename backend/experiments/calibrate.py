"""Does the grader agree with a person? Compare its scores with yours.

    cd backend && uv run python -m experiments.calibrate --template sonar-1 sonar-2
    # fill in .work/calibration.json (your 1-10 score per area; leave null to skip), then
    uv run python -m experiments.calibrate

The grader (agents/grader.py) is only useful as a yardstick if its numbers mean what a
person's would. Score the same tickets yourself, without looking at its scores, and this
prints how far apart you are in each area. Within a point is agreement: where it is
further off, the rubric's anchors for that area need sharpening, or the grader needs
your scored tickets as examples.

No model calls: it only reads grades.json files and your scores.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from agents.rubric import AREAS
from experiments.bench import WORK

SCORES = WORK / "calibration.json"
CLOSE = 1  # a person and the grader within this many points agree

HumanScores = dict[str, dict[str, int | None]]  # "round/ticket" -> area -> score


def grader_scores(work: Path, round_name: str) -> dict[str, dict[str, int]]:
    """A round's grades as "round/ticket" -> area -> score (graded tickets only)."""
    grades: dict[str, Any] = json.loads((work / "rounds" / round_name / "grades.json").read_text())
    return {
        f"{round_name}/{ticket}": {s["area"]: s["score"] for s in row["grade"]["scores"]}
        for ticket, row in grades.items()
        if "grade" in row
    }


def template(work: Path, rounds: list[str], existing: HumanScores) -> HumanScores:
    """A blank form with every graded ticket of these rounds; scores already given stay."""
    blank: HumanScores = {}
    for round_name in rounds:
        for key in grader_scores(work, round_name):
            blank[key] = {area: existing.get(key, {}).get(area) for area in AREAS}
    return {**existing, **blank}


def compare(human: HumanScores, grader: dict[str, dict[str, int]]) -> dict[str, Any]:
    """Per area: how many scores were compared, the average gap, the share within a
    point, and whether the grader runs high (+) or low (-); plus the biggest gaps."""
    areas: dict[str, dict[str, float]] = {}
    gaps: list[tuple[int, str, str, int, int]] = []
    for area in AREAS:
        pairs = [
            (key, mine, grader[key][area])
            for key, scores in human.items()
            if (mine := scores.get(area)) is not None and key in grader
        ]
        if not pairs:
            continue
        diffs = [theirs - mine for _, mine, theirs in pairs]
        areas[area] = {
            "compared": len(pairs),
            "average_gap": sum(abs(d) for d in diffs) / len(diffs),
            "within_a_point": sum(abs(d) <= CLOSE for d in diffs) / len(diffs),
            "grader_bias": sum(diffs) / len(diffs),
        }
        gaps += [(abs(t - m), key, area, m, t) for key, m, t in pairs if abs(t - m) > CLOSE]
    return {"areas": areas, "biggest_gaps": sorted(gaps, reverse=True)[:10]}


def report(result: dict[str, Any]) -> str:
    if not result["areas"]:
        return "No scores to compare yet: fill in some numbers in calibration.json."
    lines = [f"{'area':<16}{'compared':>9}{'avg gap':>9}{'within 1':>10}{'grader bias':>13}"]
    for area, row in result["areas"].items():
        lines.append(
            f"{area:<16}{row['compared']:>9.0f}{row['average_gap']:>9.1f}"
            f"{row['within_a_point']:>10.0%}{row['grader_bias']:>+13.1f}"
        )
    if result["biggest_gaps"]:
        lines += ["", "Biggest disagreements (you vs the grader):"]
        lines += [
            f"- {key} {area}: you {mine}, grader {theirs}"
            for _, key, area, mine, theirs in result["biggest_gaps"]
        ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", nargs="+", metavar="ROUND", help="write a blank form")
    args = parser.parse_args()
    existing: HumanScores = json.loads(SCORES.read_text()) if SCORES.exists() else {}
    if args.template:
        SCORES.write_text(json.dumps(template(WORK, args.template, existing), indent=2))
        print(f"Fill in your scores: {SCORES}")
        return
    rounds = sorted({key.split("/")[0] for key in existing})
    grader = {k: v for name in rounds for k, v in grader_scores(WORK, name).items()}
    print(report(compare(existing, grader)))


if __name__ == "__main__":
    main()
