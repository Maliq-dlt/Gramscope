"""Public stored-loss aggregation reproduces all grains without private registry or scoring."""

import csv
import json
import math

import pytest

from extensions.experiments import stress_aggregation as aggregation


def test_public_aggregation_native_sums_and_exclusive_export(tmp_path, monkeypatch):
    rows, inputs = aggregation.derive()
    assert len(rows) == len({(r["seed"], r["condition"], r["model"]) for r in rows}) == 138
    assert len(inputs) == 6
    aggregation.verify(aggregation.SOURCE / "aggregation.csv", rows)
    for row in rows:
        assert row["sessions"] == 180
        if row["score_kind"] == "CE_nats":
            assert math.isclose(
                row["token_weighted_ce_nats"],
                row["negative_log_likelihood_nats"] / row["predicted_targets_including_eos"],
                abs_tol=1e-14,
            )
        else:
            assert row["negative_log_likelihood_nats"] is row["token_weighted_ce_nats"] is None
    chosen = next(r for r in rows if r["seed"] == 42 and r["condition"] == "duration_base")
    with (aggregation.SOURCE / "seed42/A3_duration.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        sessions = [r for r in csv.DictReader(stream) if r["condition"] == "duration_base"]
    assert chosen["token_weighted_ce_nats"] == math.fsum(
        float(r["score"]) * int(r["targets_including_eos"]) for r in sessions
    ) / sum(int(r["targets_including_eos"]) for r in sessions)
    monkeypatch.setattr(aggregation, "ROOT", tmp_path)
    output = tmp_path / "fresh"
    assert aggregation.main(["--output", str(output)]) == 0
    aggregation.verify(output / "aggregation.csv", rows)
    receipt = json.loads((output / "derivation_receipt.json").read_text(encoding="utf-8"))
    assert receipt["aggregation_rows"] == 138 and receipt["source_files"] == inputs
    with pytest.raises(FileExistsError):
        aggregation.main(["--output", str(output)])
    with pytest.raises(ValueError, match="inside"):
        aggregation.main(["--output", str(tmp_path.parent / "outside")])
    (output / "aggregation.csv").write_text("altered", encoding="utf-8")
    with pytest.raises(ValueError, match="differs"):
        aggregation.verify(output / "aggregation.csv", rows)
