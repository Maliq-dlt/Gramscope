"""A3 identity/denominator and duration-fitting checks on frozen symbolic cases."""

import copy
import math

from extensions.experiments import event_stress as stress
from extensions.experiments import event_study as study


def test_noise_is_paired_and_duration_bins_only_use_train():
    cases, _ = study.construct(42, {"train": 30, "dev": 10, "calibration": 30, "test": 30})
    original = copy.deepcopy(cases)
    lookup = {r["case_id"]: r for r in cases}
    for condition in stress.CONDITIONS:
        noisy = stress.perturb(cases, 42, condition)
        assert noisy == stress.perturb(cases, 42, condition)
        assert len(noisy) == 180 and any(r["noise_changed"] for r in noisy)
        for row in noisy:
            clean = lookup[row["case_id"]]
            assert row["source_group"] == clean["source_group"]
            assert row["latent_novel"] == clean["latent_novel"]
            assert row["known_nohelmet_rule"] == clean["known_nohelmet_rule"]
            assert len(row["segments"]) == (2 if condition == "track-fragment" else 1)
            assert all(len(a) == len(b) for a, b in zip(row["segments"], row["segment_times"]))
    assert cases == original
    bins = stress.gap_bins(cases)
    mutated = copy.deepcopy(cases)
    for row in mutated:
        if row["partition"] != "train":
            row["times"] = [t * 1000 for t in row["times"]]
    assert stress.gap_bins(mutated) == bins
    base, slow = stress.encode_duration(cases, bins), stress.encode_duration(cases, bins, slow=True)
    assert any(a["symbols"] != b["symbols"] for a, b in zip(base, slow))
    assert all(a["latent_novel"] == b["latent_novel"] for a, b in zip(base, slow))
    assert all(math.isfinite(t) for row in slow for t in row["times"])


def test_a3_checkpoint_and_phase_preserve_a2_bytes(tmp_path, monkeypatch):
    import csv
    import hashlib
    import json

    import pytest

    from extensions.experiments import registry

    protocol = json.loads(study.PROTOCOL.read_text(encoding="utf-8"))
    monkeypatch.setattr(registry, "RUNS", tmp_path / "runs")
    a2, *_ = study.run_a2(42, protocol, "a2-checkpoint")
    before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in a2.iterdir() if p.is_file()
    }
    original_fit = study.fit

    def duration_fit(cases, protocol):
        assert all("@" in symbol for row in cases for symbol in row["symbols"])
        return original_fit(cases, protocol)

    monkeypatch.setattr(study, "fit", duration_fit)
    original_evaluate = study.evaluate
    claimed = []

    def preclaimed_evaluate(*args, **kwargs):
        target = registry.run_directory("a3-checkpoint")
        for name in (
            "protocol",
            "input_variants",
            "duration_cases",
            "duration_slow_cases",
            "duration_selection",
            "duration_calibration",
            "duration_counts",
        ):
            assert (target / f"{name}.json").is_file()
        assert (target / "A3_test.claim").is_file()
        claimed.append(True)
        return original_evaluate(*args, **kwargs)

    monkeypatch.setattr(study, "evaluate", preclaimed_evaluate)
    a3 = stress.run_a3("a2-checkpoint", "a3-checkpoint")
    assert len(claimed) == 4
    assert registry.read_run("a3-checkpoint")["stages"] == {"A3": "completed"}
    assert before == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in a2.iterdir() if p.is_file()
    }
    invariants = stress.read(a3 / "timestamp_invariance.json")
    assert all(r["ce_delta"] == 0 and r["targets_equal"] for r in invariants)
    assert all(r["base_times"] != r["slow_times"] for r in invariants)
    with (a3 / "A3_sessions.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 4 * 180 * 11
    fragments = [r for r in rows if r["condition"] == "track-fragment"]
    assert all(int(r["target_delta_from_clean"]) == 1 for r in fragments)
    assert all(int(r["segments"]) == 2 for r in fragments)
    assert all(math.isfinite(float(r["score"])) for r in rows)
    variants = stress.read(a3 / "input_variants.json")
    source = {r["case_id"]: r for r in stress.read(a2 / "input_cases.json")}
    assert all(
        r["latent_novel"] == source[r["case_id"]]["latent_novel"]
        for cases in variants.values()
        for r in cases
    )
    output = tmp_path / "public"
    assert stress.export_package("a3-checkpoint", output)["phase"] == "A3"
    with pytest.raises(FileExistsError):
        stress.export_package("a3-checkpoint", output)
    (output / "A3_models.csv").write_text("damaged", encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint"):
        stress.check_package(output)
