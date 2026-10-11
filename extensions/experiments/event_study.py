"""Frozen A2 symbolic validation; constructed labels are never camera/K3 ground truth."""

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from importlib.metadata import version
from pathlib import Path
from typing import Callable

from core.src.data import ROOT
from core.src.ngram import events
from core.src.preprocess import BOS, EOS, UNK
from extensions.experiments import registry
from extensions.src.models import CountBank, evaluate_counts
from extensions.src.pipeline import tune

PROTOCOL = ROOT / "extensions/reports/validation_protocol.json"
E, X = "PERSON_ENTER_ZONE", "PERSON_EXIT_ZONE"
U, W, N = "HELMET_UNKNOWN", "HELMET_WORN", "HELMET_NOT_WORN"
PATHS = {
    "common": [E, U, W, X],
    "hard_normal": [E, U, U, W, W, U, X],
    "known_nohelmet": [E, U, N, X],
    "rare_valid": [E, W, U, U, X],
    "easy_order": [X, W, U, E],
    "hard_order": [E, U, W, W, U, U, X],
}
NOVEL = {"easy_order", "hard_order"}
ALLOWED = {
    (E, U),
    (E, W),
    (U, U),
    (U, W),
    (W, W),
    (W, U),
    (U, N),
    (N, X),
    (U, X),
    (W, X),
    (BOS, E),
    (X, EOS),
}


def construct(seed, groups):
    """Split fresh RNG source IDs first, then construct frozen synthetic paths."""
    if (
        type(seed) is not int
        or not 0 <= seed < 2**32
        or groups != {"train": 30, "dev": 10, "calibration": 30, "test": 30}
    ):
        raise ValueError("Expected frozen seed and 30/10/30/30 source groups")
    ids = [f"source-{seed}-{i:03}" for i in range(sum(groups.values()))]
    random.Random(seed).shuffle(ids)
    split, cases, offset = {}, [], 0
    for partition in ("train", "dev", "calibration", "test"):
        split[partition] = ids[offset : offset + groups[partition]]
        offset += groups[partition]
        for index, source in enumerate(split[partition]):
            names = list(PATHS) if partition == "test" else list(PATHS)[:4]
            if partition == "train" and index:
                names.remove("rare_valid")
            rng = random.Random(registry.fingerprint([seed, source, "gaps"]))
            for name in names:
                symbols = PATHS[name]
                times = [0.0]
                for _ in symbols[1:]:
                    times.append(times[-1] + rng.uniform(0.5, 3.0))
                cases.append(
                    {
                        "case_id": f"{source}-{name}",
                        "source_group": source,
                        "partition": partition,
                        "scenario": name,
                        "acquisition_index": len(cases),
                        "symbols": list(symbols),
                        "times": times,
                        "latent_novel": name in NOVEL,
                        "known_nohelmet_rule": N in symbols,
                        "duration_outlier": False,
                    }
                )
    test = [r for r in cases if r["partition"] == "test"]
    random.Random(registry.fingerprint([seed, "acquisition-order"])).shuffle(test)
    for index, row in enumerate(test):
        row["acquisition_index"] = index
    return cases, split


def conformal_p(calibration, score):
    if not calibration or any(not math.isfinite(x) for x in (*calibration, score)):
        raise ValueError("Source calibration needs finite nonempty scores")
    return (1 + sum(value >= score for value in calibration)) / (len(calibration) + 1)


def transition_score(symbols):
    return sum(pair not in ALLOWED for pair in zip([BOS, *symbols], [*symbols, EOS]))


def score(model, segments):
    counts = model.bank.event_counts(segments, model.n)
    result = evaluate_counts(model, counts)
    return result["score_cross_entropy"], result["predicted_tokens"]


def fit(cases, protocol):
    train = [r["symbols"] for r in cases if r["partition"] == "train"]
    dev = [r["symbols"] for r in cases if r["partition"] == "dev"]
    bank = CountBank.from_counts(
        sorted({s for row in train for s in row} | {EOS, UNK}),
        {n: Counter(g for row in train for g in events(row, n)) for n in (1, 2, 3)},
        1,
    )
    models, selection = {}, {}
    for n in protocol["models"]["orders"]:
        for method in protocol["models"]["methods"]:
            name = f"{n}-{method}"
            model, winner, trials = tune(bank, n, method, bank.event_counts(dev, n))
            models[name] = model
            selection[name] = {"order": n, "method": method, "winner": winner, "trials": trials}
    best = min(selection, key=lambda name: (selection[name]["winner"]["dev_loss"], name))
    return bank, models, {"best": best, "models": selection}


def rankings(rows, best, seed, budgets):
    output = []
    conditions = sorted({r["condition"] for r in rows})
    for condition in conditions:
        condition_rows = [r for r in rows if r["condition"] == condition]
        for model in sorted({r["model"] for r in condition_rows}):
            items = [r for r in condition_rows if r["model"] == model]
            rng = random.Random(registry.fingerprint([seed, condition, model, "review-ties"]))
            tie = {r["case_id"]: rng.random() for r in sorted(items, key=lambda r: r["case_id"])}
            strategies: dict[str, Callable] = {"score": lambda r: (-r["score"], tie[r["case_id"]])}
            if model == best:
                strategies.update(
                    {
                        "random": lambda r: (tie[r["case_id"]],),
                        "chronological": lambda r: (r["acquisition_index"],),
                        "rule_priority_then_lm": lambda r: (
                            -int(r["observed_nohelmet_rule"] or r["transition_violations"]),
                            -r["score"],
                            tie[r["case_id"]],
                        ),
                    }
                )
            for strategy, key in strategies.items():
                ordered = sorted(items, key=key)
                positives = sum(r["latent_novel"] for r in items)
                helmets = sum(r["known_nohelmet_rule"] for r in items)
                for budget in budgets:
                    selected = ordered[:budget]
                    found = sum(r["latent_novel"] for r in selected)
                    output.append(
                        {
                            "seed": seed,
                            "condition": condition,
                            "model": model,
                            "strategy": strategy,
                            "budget_sessions": budget,
                            "test_cases": len(items),
                            "reviewed": len(selected),
                            "novel_total": positives,
                            "novel_found": found,
                            "precision_at_budget": found / len(selected),
                            "recall_at_budget": found / positives,
                            "rare_valid_reviewed": sum(
                                r["scenario"] == "rare_valid" for r in selected
                            ),
                            "known_nohelmet_recall": sum(r["known_nohelmet_rule"] for r in selected)
                            / helmets,
                        }
                    )
    return output


def evaluate(cases, models, bank, calibration, seed, condition="clean"):
    predictions, sources = [], []
    pairs = bank.raw[2]
    for row in cases:
        if row["partition"] != "test":
            continue
        segments = row.get("segments", [row["symbols"]])
        symbols = [s for segment in segments for s in segment]
        violations = sum(transition_score(s) for s in segments)
        rare = sum(pairs[p] < 2 for segment in segments for p in events(segment, 2))
        for name in (*models, "transition_rules", "pair_frequency_lt2"):
            value, targets = (
                score(models[name], segments)
                if name in models
                else (
                    (violations if name == "transition_rules" else rare),
                    sum(len(s) + 1 for s in segments),
                )
            )
            predictions.append(
                {
                    "seed": seed,
                    "condition": condition,
                    "case_id": row["case_id"],
                    "source_group": row["source_group"],
                    "acquisition_index": row["acquisition_index"],
                    "scenario": row["scenario"],
                    "latent_novel": row["latent_novel"],
                    "model": name,
                    "score": value,
                    "observed_targets_including_eos": targets,
                    "segments": len(segments),
                    "observed_symbols": " | ".join(symbols),
                    "transition_violations": violations,
                    "rare_pairs": rare,
                    "known_nohelmet_rule": row["known_nohelmet_rule"],
                    "observed_nohelmet_rule": N in symbols,
                    "noise_changed": row.get("noise_changed", False),
                    "duration_outlier": row["duration_outlier"],
                }
            )
    for name in models:
        grouped = defaultdict(list)
        for row in predictions:
            if row["model"] == name:
                grouped[row["source_group"]].append(row)
        for group, rows in grouped.items():
            maximum = max(r["score"] for r in rows)
            normal = max(r["score"] for r in rows if not r["latent_novel"])
            sources.append(
                {
                    "seed": seed,
                    "condition": condition,
                    "source_group": group,
                    "model": name,
                    "source_max_ce": maximum,
                    "source_p": conformal_p(calibration[name], maximum),
                    "source_alert": conformal_p(calibration[name], maximum) <= 0.05,
                    "normal_subset_max_ce": normal,
                    "normal_subset_p": conformal_p(calibration[name], normal),
                    "normal_subset_alert": conformal_p(calibration[name], normal) <= 0.05,
                    "hard_with_normal_p": conformal_p(
                        calibration[name],
                        max(normal, max(r["score"] for r in rows if r["scenario"] == "hard_order")),
                    ),
                }
            )
    return predictions, sources


def calibration_scores(cases, models):
    result = {}
    for name, model in models.items():
        grouped = defaultdict(list)
        for row in cases:
            if row["partition"] == "calibration":
                grouped[row["source_group"]].append(score(model, [row["symbols"]])[0])
        result[name] = [max(grouped[group]) for group in sorted(grouped)]
    return result


def summarize(rows, sources, selection):
    output = []
    for condition, name in sorted({(r["condition"], r["model"]) for r in rows}):
        items = [r for r in rows if (r["condition"], r["model"]) == (condition, name)]
        group_rows = [r for r in sources if (r["condition"], r["model"]) == (condition, name)]
        means = {
            scenario: math.fsum(r["score"] for r in items if r["scenario"] == scenario) / 30
            for scenario in PATHS
        }
        output.append(
            {
                "seed": items[0]["seed"],
                "condition": condition,
                "model": name,
                "selected_on_dev": name == selection["best"],
                "dev_ce_nats": selection["models"].get(name, {}).get("winner", {}).get("dev_loss"),
                **{f"{scenario}_mean_score": value for scenario, value in means.items()},
                "hard_minus_normal_mean": means["hard_order"] - means["hard_normal"],
                "normal_source_alerts": sum(r["normal_subset_alert"] for r in group_rows)
                if group_rows
                else None,
                "hard_with_normal_source_alerts": sum(
                    r["hard_with_normal_p"] <= 0.05 for r in group_rows
                )
                if group_rows
                else None,
                "source_alerts": sum(r["source_alert"] for r in group_rows) if group_rows else None,
                "source_groups": len(group_rows) if group_rows else None,
                "changed_cases": sum(r["noise_changed"] for r in items),
            }
        )
    return output


def write_csv(path, rows):
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_a2(seed, protocol, run_id):
    cases, split = construct(seed, protocol["synthetic"]["groups"])
    config = {
        "experiment": "event-validation-v1",
        "seed": seed,
        "protocol": protocol,
        "split": split,
        "input_sha256": registry.fingerprint(cases),
        "versions": {name: version(name) for name in ("ngram-assignment", "nltk", "numpy")},
        "contract": {
            "label_rubric": "easy_order/hard_order novel by construction; other paths valid",
            "label_independence": "frozen labels independent of LM scores; no expert K3 truth",
            "source_assumption": "IDs share grammar; conditional synthetic groups, not cameras",
            "review_budget_unit": "number of original sessions in whole 180-case test queue",
            "calibration": "30 normal source maxima; separate train/dev; ties >=, alpha .05",
            "normal_subset": "test normal paths only; mirrors four-path calibration groups",
            "rare_prevalence": "train1/91, dev10/40, cal30/120, test30/180; designed shift",
            "known_nohelmet": "separate rule tag; not novelty-positive or safety evidence",
        },
        "code_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "extensions/experiments/event_study.py",
                "extensions/src/models.py",
                "extensions/src/pipeline.py",
                "extensions/experiments/registry.py",
                "core/src/ngram.py",
                "core/src/preprocess.py",
            )
        },
    }
    directory = registry.create_run(run_id, config)
    registry.start_stage(run_id, "A2", config)
    bank, models, selection = fit(cases, protocol["synthetic"])
    calibration = calibration_scores(cases, models)
    support = {
        "hard_pair_counts": [[list(p), bank.raw[2][p]] for p in events(PATHS["hard_order"], 2)],
        "hard_unigram_equal": Counter(PATHS["hard_normal"]) == Counter(PATHS["hard_order"]),
        "hard_pair_multiset_equal": Counter(events(PATHS["hard_normal"], 2))
        == Counter(events(PATHS["hard_order"], 2)),
        "train_sessions": sum(r["partition"] == "train" for r in cases),
        "train_rare_valid": 1,
        "test_sessions": 180,
        "test_rare_valid": 30,
    }
    if any(bank.raw[2][pair] < 2 for pair in events(PATHS["hard_order"], 2)):
        raise ValueError("Hard contrast must have known training pairs including BOS/EOS")
    if not support["hard_unigram_equal"] or not support["hard_pair_multiset_equal"]:
        raise ValueError("Hard contrast requires equal unigram and pair multisets")
    for name, value in {
        "input_cases": cases,
        "protocol": config,
        "selection": selection,
        "calibration": calibration,
        "support": support,
        "counts": {
            "vocabulary": list(bank.vocabulary),
            "raw": {
                str(n): [[list(gram), count] for gram, count in sorted(counts.items())]
                for n, counts in bank.raw.items()
            },
        },
    }.items():
        registry.atomic_json(directory / f"{name}.json", value)
    with (directory / "A2_test.claim").open("x", encoding="utf-8") as claim:
        claim.write(registry.fingerprint(config))
    rows, sources = evaluate(cases, models, bank, calibration, seed)
    write_csv(directory / "A2_sessions.csv", rows)
    write_csv(directory / "A2_sources.csv", sources)
    write_csv(
        directory / "A2_review.csv",
        rankings(rows, selection["best"], seed, protocol["synthetic"]["review_budgets"]),
    )
    write_csv(directory / "A2_models.csv", summarize(rows, sources, selection))
    registry.complete_stage(run_id, "A2")
    return directory, cases, bank, models, selection, calibration


def output_path(output):
    output = Path(output)
    resolved = output.resolve()
    if not resolved.is_relative_to(ROOT.resolve()) or resolved.is_relative_to(
        registry.RUNS.resolve()
    ):
        raise ValueError("Public output must stay in repository outside private run receipts")
    if output.exists() or output.is_symlink():
        raise FileExistsError("Public output exists; choose a fresh directory")
    return output


def export_package(run_id, output):
    output = output_path(output)
    source = registry.selected_run(run_id)
    receipt = registry.read_run(run_id)
    if receipt["stages"].get("A2") != "completed":
        raise ValueError("Public export requires completed A2")
    names = [
        "input_cases.json",
        "protocol.json",
        "selection.json",
        "calibration.json",
        "support.json",
        "A2_sessions.csv",
        "A2_sources.csv",
        "A2_models.csv",
        "A2_review.csv",
    ]
    output.mkdir(parents=True)
    for name in names:
        with (output / name).open("xb") as stream:
            stream.write((source / name).read_bytes())
    registry.atomic_json(
        output / "manifest.json",
        {
            "status": "completed",
            "phase": "A2",
            "data_kind": "synthetic-symbolic",
            "source_run": run_id,
            "source_config_sha256": receipt["config_sha256"],
            "source_files": receipt["files"],
            "files": {
                name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in names
            },
            "limitations": [
                "No camera, detector or K3 accuracy evidence.",
                "Source conformal applies to exchangeable constructed normal groups only.",
                "Rare-valid negatives can dominate source maxima and suppress hard novelty.",
                "Session review rankings carry no source-level conformal guarantee.",
            ],
        },
    )
    return check_package(output)


def check_package(output):
    output = Path(output)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("status") != "completed"
        or manifest.get("phase") != "A2"
        or not manifest.get("files")
    ):
        raise ValueError("Not a completed A2 package")
    for name, digest in manifest["files"].items():
        path = output / name
        if not path.resolve().is_relative_to(output.resolve()) or path.is_symlink():
            raise ValueError("Invalid package path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Package fingerprint mismatch: {name}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, choices=(42, 43, 44), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        output_path(args.output)
        protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        directory, *_ = run_a2(args.seed, protocol, args.run_id)
        export_package(args.run_id, args.output)
    except (OSError, ValueError) as error:
        parser.exit(2, f"event study: {error}\n")
    print(directory)


if __name__ == "__main__":
    main()
