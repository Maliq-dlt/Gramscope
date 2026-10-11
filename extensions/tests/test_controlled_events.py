"""Paired controlled study: dev selection, order sensitivity and tamper rejection."""

import csv
import json
import math
from collections import Counter

import pytest

from extensions.experiments import controlled_events as study
from extensions.experiments import registry


def test_controlled_data_package(tmp_path, monkeypatch):
    # Validate the public package and historical CSV without rescoring its held-out data.
    public = study.ROOT / "extensions/results/cctv_symbol_order_v1"
    study.check_package(public)
    original = json.loads(
        (study.ROOT / "extensions/reports/pilot_metrics.json").read_text(encoding="utf-8")
    )
    with (study.ROOT / "extensions/results/academic_pilot_metrics.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        stored = list(csv.DictReader(stream))
    expected = [(r["run_id"], m) for r in original["runs"] for m in r["metrics"]]
    assert len(stored) == len(expected) == 72
    for row, (run_id, metric) in zip(stored, expected):
        assert row["run_id"] == run_id
        assert row["source_json_fingerprint"] == registry.fingerprint(original)
        assert row["method"] == metric["method"] and int(row["n"]) == metric["n"]
        for key in ("dev_cross_entropy", "test_cross_entropy", "test_perplexity"):
            assert (float(row[key]) if row[key] else None) == metric[key]
    monkeypatch.setattr(registry, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(study, "ROOT", tmp_path)
    output = tmp_path / "data"
    manifest = study.build("controlled-test", output)
    registry.read_run("controlled-test")
    assert manifest["table_rows"] == {
        "model_comparison.csv": 11,
        "sessions.csv": 176,
        "token_probabilities.csv": 638,
        "order_contrasts.csv": 176,
    }
    protocol = json.loads((output / "protocol.json").read_text())
    assert [len(protocol["split"][k]) for k in ("train", "dev", "test")] == [16, 2, 2]
    selection = json.loads((output / "selection.json").read_text())
    assert selection["best"] == min(
        selection["models"],
        key=lambda name: (selection["models"][name]["winner"]["dev_loss"], name),
    )
    with (output / "sessions.csv").open(newline="") as stream:
        sessions = list(csv.DictReader(stream))
    pairs = {}
    for row in sessions:
        assert int(row["oov_targets"]) == 0
        assert math.isclose(
            float(row["nll"]) / int(row["targets_including_eos"]), float(row["ce_nats"])
        )
        assert (row["needs_review"] == "True") == (float(row["ce_nats"]) > float(row["threshold"]))
        if row["variant"] == "reversed":
            assert row["partition"] == "test"
        if row["partition"] == "test":
            pairs.setdefault(row["pair_id"], {})[row["variant"]] = row["symbols"].split(" -> ")
    assert len(pairs) == 16
    assert all(Counter(p["canonical"]) == Counter(p["reversed"]) for p in pairs.values())
    with (output / "order_contrasts.csv").open(newline="") as stream:
        contrasts = list(csv.DictReader(stream))
    assert all(
        abs(float(r["delta_ce_nats"])) < 1e-12 for r in contrasts if r["model"].startswith("1-")
    )
    assert all(float(r["delta_ce_nats"]) > 0 for r in contrasts if r["model"] == "2-kneser_ney")
    summary = json.loads((output / "summary.json").read_text())
    assert summary["mode"] == "novelty diagnostics only; no labelled test evidence"
    assert all(m["precision"] is None and m["recall"] is None for m in summary["models"].values())
    with pytest.raises(FileExistsError):
        study.build("other", output)
    with pytest.raises(FileExistsError):
        study.build("controlled-test", tmp_path / "new-data")
    (output / "sessions.csv").write_text("damaged", encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint"):
        study.check_package(output)
