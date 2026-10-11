"""V2 event semantics and real run; controlled symbols are not camera-quality evidence."""

import copy
import json
import math

import pytest

from extensions.experiments import event_novelty, registry
from extensions.src.event_sequences import event_sequences_v2


def exported():
    rows = []
    for job, group in [("a", "1"), ("copy-a", "1"), ("b", "2"), ("c", "3"), ("d", "4")]:
        for index, (seconds, symbol) in enumerate(
            [(1, "PERSON_ENTER_ZONE"), (1, "HELMET_UNKNOWN"), (2, "PERSON_EXIT_ZONE")]
        ):
            rows.append(
                {
                    "id": f"{job}-{index}",
                    "workspace_id": "w",
                    "job_id": job,
                    "track_id": 1,
                    "symbol": symbol,
                    "status": "verified",
                    "category": "observation",
                    "occurred_at": None,
                    "payload": {
                        "schema_version": 2,
                        "seconds": seconds,
                        "source_revision": "a" * 64,
                        "original_source_sha256": group * 64,
                    },
                }
            )
    return {"schema_version": 2, "events": rows}


def test_bundle_grouping_and_holdout(tmp_path, monkeypatch):
    export = exported()
    sessions, split, labels = event_novelty.prepare(export, "w")
    assert all(len(row["symbols"]) == 2 for row in sessions)
    assert all(row["symbols"][0] == "BUNDLE:HELMET_UNKNOWN|PERSON_ENTER_ZONE" for row in sessions)
    assert next(k for k, v in split.items() if "a" in v) == next(
        k for k, v in split.items() if "copy-a" in v
    )
    assert event_sequences_v2(list(reversed(export["events"]))) == sessions
    few = copy.deepcopy(export)
    few["events"] = [r for r in few["events"] if r["job_id"] in {"a", "copy-a", "b"}]
    with pytest.raises(ValueError, match="independent"):
        event_novelty.prepare(few, "w")
    monkeypatch.setattr(registry, "RUNS", tmp_path / "runs")
    directory = event_novelty.run_novelty("v2", export, "w")
    registry.read_run("v2")
    summary = json.loads((directory / "summary.json").read_text())
    assert len(summary["models"]) == 11 and summary["schema_version"] == 2
    explanations = json.loads((directory / "explanations.json").read_text())
    assert len(explanations) == len(sessions)
    for row in explanations:
        assert math.fsum(term["nll"] for term in row["terms"]) / len(row["terms"]) == pytest.approx(
            row["session_ce"]
        )
        assert row["needs_review"] == (row["session_ce"] > row["threshold"])
        assert row["terms"][-1]["symbol"] == "</s>"
    with pytest.raises(FileExistsError):
        event_novelty.run_novelty("v2", export, "w")


def test_revisions_unknown_and_invalid():
    export = exported()
    export["events"][0]["payload"]["seconds"] = float("nan")
    with pytest.raises(ValueError):
        event_sequences_v2(export["events"])
    export = exported()
    export["events"][0]["symbol"] = "EMPLOYEE_ALICE"
    with pytest.raises(ValueError):
        event_sequences_v2(export["events"])
    export = exported()
    export["events"][0]["status"] = "retracted"
    assert "PERSON_ENTER_ZONE" not in event_sequences_v2(export["events"])[0]["symbols"][0]
