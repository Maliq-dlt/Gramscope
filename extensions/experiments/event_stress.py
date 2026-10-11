"""A3 noise/duration stress from immutable A2 checkpoints; no camera accuracy claim."""

import argparse
import copy
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

from extensions.experiments import event_study as study
from extensions.experiments import registry
from extensions.src.models import CountBank, ExtensionLM

CONDITIONS = ("drop10pct", "duplicate10pct", "helmet-flip10pct", "track-fragment")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def restore(source_run):
    source = registry.selected_run(source_run)
    receipt = registry.read_run(source_run)
    if receipt["stages"] != {"A2": "completed"}:
        raise ValueError("A3 requires an immutable completed A2 source")
    counts, selection = read(source / "counts.json"), read(source / "selection.json")
    bank = CountBank.from_counts(
        counts["vocabulary"],
        {
            int(n): Counter({tuple(gram): count for gram, count in rows})
            for n, rows in counts["raw"].items()
        },
        1,
    )
    models = {
        name: ExtensionLM(bank, row["order"], row["method"], **row["winner"]["parameters"])
        for name, row in selection["models"].items()
    }
    return source, receipt, bank, models, selection


def perturb(cases, seed, condition):
    if condition not in CONDITIONS:
        raise ValueError("Unsupported frozen noise condition")
    output = []
    for original in cases:
        if original["partition"] != "test":
            continue
        row = copy.deepcopy(original)
        rng = random.Random(registry.fingerprint([seed, row["case_id"], condition]))
        symbols, times = [], []
        for symbol, when in zip(row["symbols"], row["times"]):
            changed = rng.random() < 0.1
            if condition == "drop10pct" and changed:
                continue
            if (
                condition == "helmet-flip10pct"
                and changed
                and symbol in (study.U, study.W, study.N)
            ):
                symbol = rng.choice([s for s in (study.U, study.W, study.N) if s != symbol])
            symbols.append(symbol)
            times.append(when)
            if condition == "duplicate10pct" and changed:
                symbols.append(symbol)
                times.append(when)
        segments, segment_times = [symbols], [times]
        if condition == "track-fragment":
            midpoint = len(symbols) // 2
            segments, segment_times = (
                [symbols[:midpoint], symbols[midpoint:]],
                [times[:midpoint], times[midpoint:]],
            )
        row.update(
            {
                "symbols": symbols,
                "times": times,
                "segments": segments,
                "segment_times": segment_times,
                "noise_changed": segments != [original["symbols"]],
            }
        )
        output.append(row)
    return output


def gap_bins(cases):
    gaps = sorted(
        b - a
        for r in cases
        if r["partition"] == "train"
        for a, b in zip(r["times"], r["times"][1:])
    )
    if not gaps or any(not math.isfinite(gap) or gap <= 0 for gap in gaps):
        raise ValueError("Duration fitting requires finite positive training gaps")
    return [gaps[int((len(gaps) - 1) * fraction)] for fraction in (1 / 3, 2 / 3)]


def delay_only(row):
    slower = copy.deepcopy(row)
    slower["times"] = [value * 2 for value in row["times"]]
    slower["duration_outlier"] = True
    return slower


def encode_duration(cases, bins, slow=False):
    output = copy.deepcopy(cases)
    for row in output:
        original = row["symbols"]
        if slow and row["partition"] == "test":
            row.update(delay_only(row))
        gaps = [b - a for a, b in zip(row["times"], row["times"][1:])]
        if any(not math.isfinite(gap) or not 0 < gap < 30 for gap in gaps):
            raise ValueError("Duration-only offsets must preserve positive sub-30s gaps")
        row["symbols"] = [original[0] + "@START"] + [
            symbol + f"@GAP{sum(gap > edge for edge in bins)}"
            for symbol, gap in zip(original[1:], gaps)
        ]
    return output


def run_a3(source_run, run_id):
    source, receipt, bank, models, selection = restore(source_run)
    config_a2 = receipt["config"]
    seed = config_a2["seed"]
    cases = read(source / "input_cases.json")
    if registry.fingerprint(cases) != config_a2["input_sha256"]:
        raise ValueError("A2 input fingerprint differs")
    variants = {condition: perturb(cases, seed, condition) for condition in CONDITIONS}
    bins = gap_bins(cases)
    duration_cases = encode_duration(cases, bins)
    duration_bank, duration_models, duration_selection = study.fit(
        duration_cases, config_a2["protocol"]["synthetic"]
    )
    duration_calibration = study.calibration_scores(duration_cases, duration_models)
    slow_cases = encode_duration(cases, bins, slow=True)
    config = {
        "experiment": "event-stress-v1",
        "source_run": source_run,
        "source_config_sha256": receipt["config_sha256"],
        "source_files": receipt["files"],
        "seed": seed,
        "gap_bin_edges_train_only": bins,
        "noise": list(CONDITIONS),
        "input_sha256": registry.fingerprint(variants),
        "duration_input_sha256": registry.fingerprint([duration_cases, slow_cases]),
        "contract": {
            "labels": "latent novelty/nohelmet tags preserved under observation noise",
            "calibration": "A2 clean source maxima frozen; shifted noise has no guarantee",
            "score": "token-weighted CE, EOS per observed segment; empty segment predicts EOS",
            "duration": "new train-fit bins/dev-selected model/clean calibration; slow x2",
            "duration_label": "slow construction tag separate from symbolic novelty",
            "review": "10/20/40 original cases; random/ties same seed as clean A2",
        },
        "code_sha256": {
            "extensions/experiments/event_stress.py": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
            **config_a2["code_sha256"],
        },
        "versions": config_a2["versions"],
    }
    directory = registry.create_run(run_id, config)
    registry.start_stage(run_id, "A3", config)
    for name, value in {
        "protocol": config,
        "input_variants": variants,
        "duration_cases": duration_cases,
        "duration_slow_cases": slow_cases,
        "duration_selection": duration_selection,
        "duration_calibration": duration_calibration,
        "duration_counts": {
            "vocabulary": list(duration_bank.vocabulary),
            "raw": {
                str(n): [[list(gram), count] for gram, count in sorted(counts.items())]
                for n, counts in duration_bank.raw.items()
            },
        },
    }.items():
        registry.atomic_json(directory / f"{name}.json", value)
    with (directory / "A3_test.claim").open("x", encoding="utf-8") as claim:
        claim.write(registry.fingerprint(config))
    calibration = read(source / "calibration.json")
    rows, sources, reviews = [], [], []
    with (source / "A2_sessions.csv").open(newline="", encoding="utf-8") as stream:
        cached = {(r["case_id"], r["model"]): r for r in csv.DictReader(stream)}
    for condition, observed in variants.items():
        predictions, source_rows = study.evaluate(
            observed, models, bank, calibration, seed, condition
        )
        for row in predictions:
            clean = cached[row["case_id"], row["model"]]
            row["clean_score"] = float(clean["score"])
            row["score_delta_from_clean"] = row["score"] - row["clean_score"]
            row["clean_targets_including_eos"] = int(clean["observed_targets_including_eos"])
            row["target_delta_from_clean"] = (
                row["observed_targets_including_eos"] - row["clean_targets_including_eos"]
            )
        # Use A2 tie/random ordering for all paired conditions to isolate observation changes.
        ranked = study.rankings(
            [{**r, "condition": "clean"} for r in predictions],
            selection["best"],
            seed,
            config_a2["protocol"]["synthetic"]["review_budgets"],
        )
        reviews.extend({**r, "condition": condition} for r in ranked)
        rows.extend(predictions)
        sources.extend(source_rows)
    study.write_csv(directory / "A3_sessions.csv", rows)
    study.write_csv(directory / "A3_sources.csv", sources)
    summary = study.summarize(rows, sources, selection)
    for item in summary:
        paired = [
            r for r in rows if (r["condition"], r["model"]) == (item["condition"], item["model"])
        ]
        item["mean_score_delta_from_clean"] = math.fsum(
            r["score_delta_from_clean"] for r in paired
        ) / len(paired)
        item["mean_target_delta_from_clean"] = math.fsum(
            r["target_delta_from_clean"] for r in paired
        ) / len(paired)
    study.write_csv(directory / "A3_models.csv", summary)
    study.write_csv(directory / "A3_review.csv", reviews)
    duration_rows, duration_sources, invariants = [], [], []
    best = duration_selection["best"]
    model = duration_models[best]
    for condition, encoded in (("duration_base", duration_cases), ("duration_slow", slow_cases)):
        maxima = defaultdict(list)
        for row in encoded:
            if row["partition"] != "test":
                continue
            value, targets = study.score(model, [row["symbols"]])
            duration_rows.append(
                {
                    "seed": seed,
                    "condition": condition,
                    "case_id": row["case_id"],
                    "model": best,
                    "score": value,
                    "targets_including_eos": targets,
                    "oov_targets": sum(symbol not in model.vocab_set for symbol in row["symbols"]),
                    "symbol_targets_without_eos": len(row["symbols"]),
                    "latent_novel": row["latent_novel"],
                    "duration_outlier": row["duration_outlier"],
                }
            )
            if not row["latent_novel"]:
                maxima[row["source_group"]].append(value)
        duration_sources.extend(
            {
                "seed": seed,
                "condition": condition,
                "model": best,
                "source_group": group,
                "normal_max_ce": max(values),
                "source_p": study.conformal_p(duration_calibration[best], max(values)),
                "source_alert": study.conformal_p(duration_calibration[best], max(values)) <= 0.05,
            }
            for group, values in maxima.items()
        )
    # Actual paired timestamp-only check evaluates a fresh invariant contrast, not the cached test.
    contrast = {
        "symbols": list(study.PATHS["hard_normal"]),
        "times": [float(i) for i in range(len(study.PATHS["hard_normal"]))],
    }
    slower_case = delay_only(contrast)
    if contrast["times"] == slower_case["times"]:
        raise ArithmeticError("Timestamp check requires an actual offset change")
    for name, model in models.items():
        base, targets = study.score(model, [contrast["symbols"]])
        slower, slower_targets = study.score(model, [slower_case["symbols"]])
        if base != slower or targets != slower_targets:
            raise ArithmeticError("Timestamp-only change altered symbolic score")
        invariants.append(
            {
                "model": name,
                "ce_delta": slower - base,
                "targets_equal": True,
                "base_times": contrast["times"],
                "slow_times": slower_case["times"],
                "scope": "fresh path with actual times x2; scorer consumes symbols only",
            }
        )
    study.write_csv(directory / "A3_duration.csv", duration_rows)
    study.write_csv(directory / "A3_duration_sources.csv", duration_sources)
    duration_summary = []
    for condition in ("duration_base", "duration_slow"):
        items = [r for r in duration_rows if r["condition"] == condition]
        group_rows = [r for r in duration_sources if r["condition"] == condition]
        duration_summary.append(
            {
                "seed": seed,
                "condition": condition,
                "model": best,
                "dev_ce_nats": duration_selection["models"][best]["winner"]["dev_loss"],
                "mean_ce_nats": math.fsum(r["score"] for r in items) / len(items),
                "oov_targets": sum(r["oov_targets"] for r in items),
                "symbol_targets": sum(r["symbol_targets_without_eos"] for r in items),
                "normal_source_alerts": sum(r["source_alert"] for r in group_rows),
                "normal_source_groups": len(group_rows),
            }
        )
    study.write_csv(directory / "A3_duration_summary.csv", duration_summary)
    registry.atomic_json(directory / "timestamp_invariance.json", invariants)
    if registry.read_run(source_run)["files"] != receipt["files"]:
        raise ValueError("A2 source changed during A3")
    registry.complete_stage(run_id, "A3")
    return directory


def export_package(run_id, output):
    output = study.output_path(output)
    source = registry.selected_run(run_id)
    receipt = registry.read_run(run_id)
    if receipt["stages"] != {"A3": "completed"}:
        raise ValueError("Public A3 export requires completed A3")
    output.mkdir(parents=True)
    files = {}
    for name in receipt["files"]:
        if name.endswith((".csv", ".json")) and name != "duration_counts.json":
            with (output / name).open("xb") as stream:
                stream.write((source / name).read_bytes())
            files[name] = receipt["files"][name]
    registry.atomic_json(
        output / "manifest.json",
        {
            "status": "completed",
            "phase": "A3",
            "source_run": run_id,
            "source_config_sha256": receipt["config_sha256"],
            "source_files": receipt["files"],
            "files": files,
            "limitations": [
                "Synthetic noise is not detector accuracy evidence.",
                "Shifted noise/duration loses clean exchangeability guarantee.",
                "Primary A2 clean observations/checkpoints are immutable.",
            ],
        },
    )
    return check_package(output)


def check_package(output):
    output = Path(output)
    manifest = read(output / "manifest.json")
    if (
        manifest.get("status") != "completed"
        or manifest.get("phase") != "A3"
        or not manifest.get("files")
    ):
        raise ValueError("Not a completed A3 package")
    for name, digest in manifest["files"].items():
        path = output / name
        if not path.resolve().is_relative_to(output.resolve()) or path.is_symlink():
            raise ValueError("Invalid A3 package path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"A3 package fingerprint mismatch: {name}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        study.output_path(args.output)
        directory = run_a3(args.source_run, args.run_id)
        export_package(args.run_id, args.output)
    except (OSError, ValueError) as error:
        parser.exit(2, f"event stress: {error}\n")
    print(directory)


if __name__ == "__main__":
    main()
