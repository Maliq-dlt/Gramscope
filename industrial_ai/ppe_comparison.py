"""Post-hoc, source-grouped uncertainty from sealed SH17 PPE predictions only."""

import argparse
import csv
import json
import math
import random
import tempfile
from collections import defaultdict
from pathlib import Path

import runtime  # Workspace cache paths precede ML imports.
from detector_benchmark import match_predictions, native_environment, sha256, validate_boxes

ROOT = runtime.ROOT.parent
SEED = 20261011
DRAWS = 2000
MODELS = ("baseline_helmet", "candidate")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sealed_inputs(source, samples):
    completed = read_json(source / "completed.json")
    files = completed["files"]
    required = {
        "protocol.json",
        "derived_hashes.json",
        "selection.json",
        "evaluation_protocol.json",
        "operating_selection.json",
        "test.claim",
        "test_metrics.csv",
        "test-baseline_helmet.jsonl",
        "test-candidate.jsonl",
    }
    if completed["status"] != "completed" or not required <= files.keys():
        raise ValueError("Incomplete PPE evaluation")
    if set(files) != {
        p.name for p in source.iterdir() if p.is_file() and p.name != "completed.json"
    }:
        raise ValueError("Completed file inventory changed")
    for name, digest in files.items():
        path = source / name
        if Path(name).name != name or path.is_symlink() or sha256(path) != digest:
            raise ValueError(f"Sealed file changed: {name}")
    protocol, selection = read_json(source / "protocol.json"), read_json(source / "selection.json")
    operating, evaluation = (
        read_json(source / name)
        for name in ("operating_selection.json", "evaluation_protocol.json")
    )
    checkpoint = source / "training/weights/best.pt"
    if (
        selection["winner"] != "training/weights/best.pt"
        or checkpoint.is_symlink()
        or sha256(checkpoint) != selection["sha256"]
        or selection["sha256"] != completed["checkpoint_sha256"]
        or selection["sha256"] != operating["checkpoint_sha256"]
        or selection["protocol_sha256"] != sha256(source / "protocol.json")
        or (source / "test.claim").read_text() != sha256(source / "operating_selection.json")
        or evaluation["derived_sha256"] != sha256(source / "derived_hashes.json")
        or evaluation["matching_code_sha256"] != sha256(runtime.ROOT / "detector_benchmark.py")
        or evaluation["baseline_helmet_sha256"] != sha256(runtime.MODELS / "helmet.pt")
        or evaluation["code_sha256"] != sha256(runtime.ROOT / "ppe_accuracy_study.py")
        or any(evaluation[key] != value for key, value in native_environment().items())
    ):
        raise ValueError("Checkpoint, selection, or evaluation metadata changed")
    thresholds = operating["thresholds"]
    if set(thresholds) != set(MODELS) or any(
        type(value) not in (int, float)
        or not math.isfinite(value)
        or value not in evaluation["confidence_grid"]
        for value in thresholds.values()
    ):
        raise ValueError("Invalid dev-selected thresholds")
    if (
        samples.name != "samples.json"
        or samples.parent.name != "quality-parallel"
        or not samples.resolve().is_relative_to((runtime.ROOT / "data/public").resolve())
    ):
        raise ValueError("Expected audited SH17 quality-parallel/samples.json")
    audit = read_json(samples.parent / "summary.json")
    if (
        sha256(samples) != audit["samples_sha256"]
        or audit["samples_sha256"] != protocol["samples_sha256"]
        or audit["input_sha256"] != protocol["dataset_sha256"]
        or audit != protocol["split_summary"]
        or not audit_protocol_matches(protocol, source, samples.parent)
    ):
        raise ValueError("Audited SH17 source changed")
    return thresholds, sha256(source / "completed.json")


def audit_protocol_matches(protocol, source, quality):
    digest = sha256(quality / "protocol.json")
    if "input_protocol_sha256" in protocol:
        return digest == protocol["input_protocol_sha256"]
    # ponytail: sole sealed legacy preparation; new runs must record the audit hash.
    return sha256(
        source / "protocol.json"
    ) == "9d18d01d514ed2db4734e7e9127282a27538be15c6a3f676da278a06d4fd15c9" and read_json(
        quality / "protocol.json"
    ) == {
        "audit_code_sha256": sha256(runtime.ROOT / "sh17_quality.py"),
        "head_is_nohelmet": False,
        "seed": 20261011,
        "source": "SH17 v1 meta-data",
        "source_grouping": "transitive union same photographer_id and phash<=6",
        "split": "80/10/10 shuffled groups",
    }


def check_ids(ids, expected):
    if len(ids) != len(expected) or len(set(ids)) != len(ids) or set(ids) != expected:
        raise ValueError("Held-out prediction IDs differ")


def prediction_rows(path, expected):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    ids = [row["id"] for row in rows]
    check_ids(ids, expected)
    for row in rows:
        validate_boxes(row["targets"])
        validate_boxes(row["predictions"], predictions=True)
    return {row["id"]: row for row in rows}


def helmet_counts(row, threshold):
    targets = [box for box in row["targets"] if box["class"] == 1]
    predictions = [
        box for box in row["predictions"] if box["class"] == 1 and box["confidence"] >= threshold
    ]
    tp = int(match_predictions(targets, predictions)[:, 0].sum())
    return tp, len(predictions) - tp, len(targets) - tp


def measures(counts):
    tp, fp, fn = counts
    return {
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
    }


def percentile(values, fraction):
    position = (len(values) - 1) * fraction
    lower = int(position)
    return values[lower] + (values[math.ceil(position)] - values[lower]) * (position - lower)


def uncertainty(groups, draws=DRAWS):
    keys = sorted(groups)
    if not keys:
        raise ValueError("No held-out source groups")
    observed = {
        model: tuple(sum(groups[k][model][i] for k in keys) for i in range(3)) for model in MODELS
    }
    point = {model: measures(counts) for model, counts in observed.items()}
    values = {metric: [] for metric in ("precision", "recall", "f1")}
    rng = random.Random(SEED)
    for _ in range(draws):
        chosen = rng.choices(keys, k=len(keys))
        sample = {
            model: measures(tuple(sum(groups[k][model][i] for k in chosen) for i in range(3)))
            for model in MODELS
        }
        for metric, series in values.items():
            baseline, candidate = (sample[model][metric] for model in MODELS)
            if baseline is not None and candidate is not None:
                series.append(candidate - baseline)
    difference = {
        metric: {
            "candidate_minus_baseline": (
                point["candidate"][metric] - point["baseline_helmet"][metric]
                if all(point[model][metric] is not None for model in MODELS)
                else None
            ),
            "percentile_95": (
                [percentile(sorted(series), 0.025), percentile(sorted(series), 0.975)]
                if series
                else None
            ),
            "defined_draws": len(series),
        }
        for metric, series in values.items()
    }
    return {
        "observed": {
            model: {
                "counts": dict(zip(("tp", "fp", "fn"), observed[model])),
                "metrics": point[model],
            }
            for model in MODELS
        },
        "difference": difference,
    }


def compare(source, samples, output):
    source, samples, output = source.resolve(), samples.resolve(), output.resolve()
    if (
        not source.is_relative_to((runtime.ROOT / ".tmp").resolve())
        or output.exists()
        or not output.is_relative_to((ROOT / ".tmp").resolve())
    ):
        raise ValueError("Use existing industrial_ai/.tmp input and fresh repository .tmp output")
    thresholds, receipt = sealed_inputs(source, samples)
    audited = read_json(samples)
    if len({row["id"] for row in audited}) != len(audited):
        raise ValueError("Duplicate audited image ID")
    test = {row["id"]: row["visual_group"] for row in audited if row["partition"] == "test"}
    rows = {model: prediction_rows(source / f"test-{model}.jsonl", set(test)) for model in MODELS}
    groups = defaultdict(lambda: {model: [0, 0, 0] for model in MODELS})
    sizes = defaultdict(int)
    for image_id, group in test.items():
        baseline, candidate = (rows[model][image_id] for model in MODELS)
        if (
            any(box["class"] != 1 for box in baseline["targets"] + baseline["predictions"])
            or [box for box in candidate["targets"] if box["class"] == 1] != baseline["targets"]
        ):
            raise ValueError(f"Helmet targets or baseline classes differ: {image_id}")
        sizes[group] += 1
        for model in MODELS:
            count = helmet_counts(rows[model][image_id], thresholds[model])
            groups[group][model] = [a + b for a, b in zip(groups[group][model], count)]
    result = uncertainty(groups)
    output.mkdir(parents=True)
    with (output / "per_group_counts.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "visual_group",
                "images",
                *[f"{model}_{name}" for model in MODELS for name in ("tp", "fp", "fn")],
            ]
        )
        for group in sorted(groups):
            row = groups[group]
            writer.writerow([group, sizes[group], *row["baseline_helmet"], *row["candidate"]])
    with (output / "uncertainty.json").open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "label": "descriptive post-hoc small public photograph benchmark; not pre-registered confirmatory or factory evidence",
                "resampling_unit": "audited photographer + pHash visual_group, not independent frames",
                "completed_sha256": receipt,
                "samples_sha256": sha256(samples),
                "thresholds_selected_on_dev": thresholds,
                "images": len(test),
                "groups": len(groups),
                "bootstrap_draws": DRAWS,
                "seed": SEED,
                "iou": 0.5,
                "undefined_metrics": "null when denominator is zero; paired draws require both models defined",
                "comparison": result,
            },
            stream,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )


def self_check():
    with tempfile.TemporaryDirectory(dir=runtime.ROOT / ".tmp") as folder:
        source = Path(folder)
        (source / "protocol.json").write_text("{}", encoding="utf-8")
        assert audit_protocol_matches(
            {"input_protocol_sha256": sha256(source / "protocol.json")}, source, source
        )
        assert not audit_protocol_matches({"input_protocol_sha256": "changed"}, source, source)
        assert not audit_protocol_matches({}, source, source)
    box = {"class": 1, "bbox": [0.1, 0.1, 0.3, 0.3]}
    row = {"targets": [box], "predictions": [{**box, "confidence": 0.8}]}
    assert helmet_counts(row, 0.5) == (1, 0, 0)
    assert helmet_counts({"targets": [box], "predictions": []}, 0.5) == (0, 0, 1)
    same = {7: {model: [1, 0, 0] for model in MODELS}, 9: {model: [0, 1, 1] for model in MODELS}}
    result = uncertainty(same, 200)
    assert all(value["percentile_95"] == [0, 0] for value in result["difference"].values())
    try:
        check_ids(["one", "one"], {"one", "two"})
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid prediction input accepted")
    print("PPE offline self-check passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--samples", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
    elif args.input and args.samples and args.output:
        compare(args.input, args.samples, args.output)
    else:
        parser.error("--input, --samples, and --output are required")
