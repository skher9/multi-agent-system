"""Comparing a person's rubric scores with the grader's. No model calls."""

import json
from pathlib import Path

from agents.rubric import AREAS
from experiments.calibrate import compare, grader_scores, report, template


def grades(tmp_path: Path, **tickets: int) -> None:
    """A round "r1" whose tickets each got one score in every area."""
    rows = {
        name: {"grade": {"scores": [{"area": a, "score": score} for a in AREAS]}}
        for name, score in tickets.items()
    }
    rows["crashed"] = {"error": "boom"}  # type: ignore[dict-item]
    folder = tmp_path / "rounds" / "r1"
    folder.mkdir(parents=True)
    (folder / "grades.json").write_text(json.dumps(rows))


def test_template_lists_graded_tickets_and_keeps_scores_already_given(tmp_path: Path) -> None:
    grades(tmp_path, footer=8, todo=6)
    mine = {"r1/footer": {"tests": 7}, "old/ticket": {"tests": 5}}
    form = template(tmp_path, ["r1"], mine)  # type: ignore[arg-type]
    assert set(form) == {"r1/footer", "r1/todo", "old/ticket"}  # the crashed one isn't there
    assert form["r1/footer"] == {**dict.fromkeys(AREAS), "tests": 7}
    assert form["r1/todo"] == dict.fromkeys(AREAS)


def test_compare_measures_the_gap_per_area_and_skips_blanks(tmp_path: Path) -> None:
    grades(tmp_path, footer=8, todo=6)
    mine = {
        "r1/footer": {"correctness": 8, "tests": 5, "readability": None},
        "r1/todo": {"correctness": 7, "tests": 6},
        "r1/never-graded": {"correctness": 2},
    }
    result = compare(mine, grader_scores(tmp_path, "r1"))  # type: ignore[arg-type]
    assert set(result["areas"]) == {"correctness", "tests"}
    correctness = result["areas"]["correctness"]
    assert correctness == {
        "compared": 2,
        "average_gap": 0.5,
        "within_a_point": 1.0,
        "grader_bias": -0.5,  # the grader gave todo 6 where the person gave 7
    }
    assert result["areas"]["tests"]["within_a_point"] == 0.5
    assert result["biggest_gaps"] == [(3, "r1/footer", "tests", 5, 8)]
    text = report(result)
    assert "- r1/footer tests: you 5, grader 8" in text
    assert report(compare({}, {})).startswith("No scores to compare yet")
