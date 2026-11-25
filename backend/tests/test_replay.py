"""The public replay keeps only a ticket's latest run."""

from experiments.replay import latest_run


def test_only_the_latest_run_is_kept_and_renumbered() -> None:
    kinds = ["run_started", "run_failed", "run_started", "node_started", "run_ended"]
    events = [{"id": 40 + n, "kind": kind} for n, kind in enumerate(kinds)]
    assert latest_run(events) == [
        {"id": 1, "kind": "run_started"},
        {"id": 2, "kind": "node_started"},
        {"id": 3, "kind": "run_ended"},
    ]
