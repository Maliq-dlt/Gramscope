"""Meaningful leakage/selection checks using tiny real model count banks."""

import math

import pytest

from core.src.preprocess import fit_vocabulary
from extensions.experiments.academic_upgrade import (
    average_seed_losses,
    budget_subset,
    frozen_bank,
    group_se,
    probe_design,
    select_one_se,
    sentence_split_design,
)
from extensions.src.models import ExtensionLM


def test_one_se_simplifies_and_rejects_invalid_uncertainty():
    rows = [
        {
            "model": "3-modified_kneser_ney",
            "n": 3,
            "method": "modified_kneser_ney",
            "dev_ce_nats": 2.0,
        },
        {"model": "2-kneser_ney", "n": 2, "method": "kneser_ney", "dev_ce_nats": 2.02},
        {"model": "1-kneser_ney", "n": 1, "method": "kneser_ney", "dev_ce_nats": 2.2},
    ]
    assert select_one_se(rows, 0.03)["one_se"] == "2-kneser_ney"
    assert select_one_se(rows, 0)["one_se"] == "3-modified_kneser_ney"
    with pytest.raises(ValueError):
        select_one_se(rows, math.nan)
    equal = [{"group_id": str(i), "nll": 20.0, "predicted_tokens": 10} for i in range(4)]
    assert group_se(equal) == 0


def test_probe_exclusion_budget_and_shared_unknown_mapping():
    train = [{"id": "a", "split_group": "a", "sentences": [["train", "only"]] * 600}]
    test = [
        {
            "id": str(i),
            "split_group": str(i),
            "sentences": [["test", "sibling", "token"]] * 20 + [["probe", str(i)]],
        }
        for i in range(10)
    ]
    # Unique probes regardless of random choice: all siblings of one doc have a distinct marker.
    for i, doc in enumerate(test):
        doc["sentences"] = [
            ["test", "word" + chr(97 + i), "sentence" + chr(97 + j)] for j in range(30)
        ]
    probes, arms, audit = probe_design({"train": train, "test": test})
    exact = {tuple(d["sentences"][0]) for d in probes}
    assert len(arms) == 9
    assert all(tuple(s) not in exact for rows in arms.values() for s in rows)
    assert max(r["fill_residual"] for r in audit) < 20
    vocab, _ = fit_vocabulary(train[0]["sentences"], 2)
    bank = frozen_bank(arms[(42, "sibling_exposure")], vocab)
    assert bank.map_sentence(["test", "train"]) == ["<UNK>", "train"]
    model = ExtensionLM(bank, 3, "modified_kneser_ney")
    assert math.isclose(sum(model.score(w, ["test", "train"]) for w in bank.vocabulary), 1)
    chosen, _, residual = budget_subset([["x"] * 10, ["y"]], 12, 4)
    assert sum(len(s) + 1 for s in chosen) + residual == 12


def test_seed_averaging_does_not_make_seeds_independent_samples():
    rows = [
        {
            "seed": seed,
            "arm": "strict",
            "model": "m",
            "id": "d",
            "group_id": "g",
            "nll": value,
            "predicted_tokens": 2,
        }
        for seed, value in [(42, 2), (43, 4), (44, 6)]
    ]
    result = average_seed_losses(rows, "m", "strict")
    assert len(result) == 1 and result[0]["nll"] == 4
    with pytest.raises(ValueError):
        average_seed_losses(rows[:2], "m", "strict")


def test_random_sentence_vocabulary_uses_only_common_train_occurrences():
    split = {
        "train": [
            {
                "id": "train",
                "split_group": "train",
                "sentences": [["safe", "word"] for _ in range(100)],
            }
        ],
        "dev": [{"id": "dev", "split_group": "dev", "sentences": [["devsecret"]] * 20}],
        "test": [{"id": "test", "split_group": "test", "sentences": [["testsecret"]] * 20}],
    }
    designs, audit = sentence_split_design(split)
    assert len(designs) == 3 and len(audit) == 3
    for design in designs.values():
        assert "safe" in design["vocabulary"]
        assert "devsecret" not in design["vocabulary"]
        assert "testsecret" not in design["vocabulary"]
