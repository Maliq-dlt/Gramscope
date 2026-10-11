"""Scientific invariants for the new synthetic study, without historical rescoring."""

import math
from collections import Counter

import pytest

from core.src.ngram import events
from extensions.experiments import event_study as study


def test_splits_pair_matched_contrast_and_rules():
    cases, split = study.construct(42, {"train": 30, "dev": 10, "calibration": 30, "test": 30})
    assert list(map(len, split.values())) == [30, 10, 30, 30]
    assert len(set(group for groups in split.values() for group in groups)) == 100
    assert (cases, split) == study.construct(
        42, {"train": 30, "dev": 10, "calibration": 30, "test": 30}
    )
    train = [r["symbols"] for r in cases if r["partition"] == "train"]
    pairs = Counter(p for row in train for p in events(row, 2))
    a, b = study.PATHS["hard_normal"], study.PATHS["hard_order"]
    assert Counter(a) == Counter(b) and Counter(events(a, 2)) == Counter(events(b, 2))
    assert Counter(events(a, 3)) != Counter(events(b, 3))
    assert all(pairs[p] >= 2 for p in events(b, 2))
    assert study.transition_score(b) == 0
    assert study.transition_score(study.PATHS["easy_order"]) > 0
    rare = [r for r in cases if r["scenario"] == "rare_valid"]
    assert sum(r["partition"] == "train" for r in rare) == 1
    assert all(not r["latent_novel"] for r in rare)
    assert any(pairs[p] == 1 for p in events(study.PATHS["rare_valid"], 2))
    assert len([r for r in cases if r["partition"] == "test"]) == 180
    assert all(0 < b - a < 30 for r in cases for a, b in zip(r["times"], r["times"][1:]))


def test_source_conformal_is_conservative_with_ties_and_small_m():
    assert study.conformal_p([1.0] * 30, 1.0) == 1
    assert study.conformal_p([1.0] * 30, 2.0) == 1 / 31
    assert study.conformal_p([1.0] * 18, 2.0) > 0.05
    for calibration, score in (([], 1), ([math.inf], 1), ([1], math.nan)):
        with pytest.raises(ValueError):
            study.conformal_p(calibration, score)


def test_a2_receipt_and_claim_precede_test_scores(tmp_path, monkeypatch):
    import csv
    import json

    from extensions.experiments import registry

    protocol = json.loads(study.PROTOCOL.read_text(encoding="utf-8"))
    monkeypatch.setattr(registry, "RUNS", tmp_path / "runs")
    evaluate = study.evaluate
    checked = []

    def claimed_evaluation(*args, **kwargs):
        run = registry.run_directory("event-study-test")
        for name in ("input_cases", "protocol", "selection", "calibration", "support", "counts"):
            assert (run / f"{name}.json").is_file()
        assert (run / "A2_test.claim").is_file()
        checked.append(True)
        return evaluate(*args, **kwargs)

    monkeypatch.setattr(study, "evaluate", claimed_evaluation)
    directory, _, _, _, selection, calibration = study.run_a2(42, protocol, "event-study-test")
    receipt = registry.read_run("event-study-test")
    assert receipt["stages"] == {"A2": "completed"}
    assert checked == [True] and all(len(v) == 30 for v in calibration.values())
    assert selection["best"] == min(
        selection["models"],
        key=lambda name: (selection["models"][name]["winner"]["dev_loss"], name),
    )
    with (directory / "A2_review.csv").open(newline="") as stream:
        reviews = list(csv.DictReader(stream))
    assert {int(r["reviewed"]) for r in reviews} == {10, 20, 40}
    with pytest.raises(FileExistsError):
        study.run_a2(42, protocol, "event-study-test")


def test_public_package_is_exclusive_and_tamper_checked(tmp_path, monkeypatch):
    import json

    from extensions.experiments import registry

    protocol = json.loads(study.PROTOCOL.read_text(encoding="utf-8"))
    monkeypatch.setattr(registry, "RUNS", tmp_path / "runs")
    study.run_a2(42, protocol, "export-test")
    monkeypatch.setattr(study, "ROOT", tmp_path)
    # The test relocates ROOT only after the run, so hashes use actual source files.
    monkeypatch.setattr(registry, "selected_run", lambda run_id: registry.run_directory(run_id))
    output = tmp_path / "public"
    assert study.export_package("export-test", output)["phase"] == "A2"
    with pytest.raises(FileExistsError):
        study.export_package("export-test", output)
    with pytest.raises(ValueError, match="outside"):
        study.export_package("export-test", registry.RUNS / "bad-output")
    (output / "support.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint"):
        study.check_package(output)
