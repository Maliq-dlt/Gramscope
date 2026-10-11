"""Offline symbol novelty; run with --help for the authenticated ledger export contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter
from datetime import datetime
from pathlib import Path

from core.src.data import ROOT
from core.src.ngram import events
from core.src.preprocess import BOS, EOS, UNK
from extensions.experiments import registry
from extensions.src.cli import ALGORITHM_VERSION
from extensions.src.event_sequences import SYMBOLS, event_sequences, event_sequences_v2
from extensions.src.models import CountBank, evaluate_counts
from extensions.src.pipeline import candidates, tune

TOKENIZER = "ledger-symbols-v1"
MAX_BYTES = 16 * 1024 * 1024
MAX_EVENTS = 100_000


def session_key(row):
    return row["recording_id"], row["track_id"], row["session_index"]


def prepare(export, workspace_id, seed=42, max_gap_seconds=30):
    """Validate a single authorized workspace export, retaining no identity payloads."""
    if not isinstance(workspace_id, str) or not 1 <= len(workspace_id) <= 120:
        raise ValueError("An explicit workspace ID is required")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("Seed must be an integer in [0, 2**32)")
    if type(max_gap_seconds) not in (int, float) or not 0 < max_gap_seconds <= 86400:
        raise ValueError("Gap must be positive and at most one day")
    if not isinstance(export, dict) or not isinstance(export.get("events"), list):
        raise ValueError("Export must contain an events list")
    if not 1 <= len(export["events"]) <= MAX_EVENTS:
        raise ValueError("Export requires 1..100000 events")
    if export.get("schema_version") == 2:
        return prepare_v2(export, workspace_id, seed, max_gap_seconds)
    rows, identifiers = [], {}
    for row in export["events"]:
        if not isinstance(row, dict) or row.get("workspace_id") != workspace_id:
            raise ValueError("Every event must belong to the explicit workspace")
        if row.get("status") != "verified" or row.get("category") != "observation":
            continue
        if (
            any(
                not isinstance(row.get(key), str) or not 1 <= len(row[key]) <= 120
                for key in ("id", "job_id")
            )
            or type(row.get("track_id")) is not int
            or row["track_id"] < 0
            or not isinstance(row.get("symbol"), str)
            or row.get("symbol") not in SYMBOLS
            or not isinstance(row.get("occurred_at"), str)
        ):
            raise ValueError("Verified event requires a supported symbol, recording and track")
        try:
            when = datetime.fromisoformat(row["occurred_at"].replace("Z", "+00:00"))
            if when.utcoffset() is None:
                raise ValueError
            when.timestamp()
        except (ValueError, OverflowError, OSError) as error:
            raise ValueError("Verified event requires a valid timezone-aware timestamp") from error
        clean = {
            key: row[key]
            for key in (
                "id",
                "workspace_id",
                "job_id",
                "track_id",
                "symbol",
                "occurred_at",
                "status",
                "category",
            )
        }
        if row["id"] in identifiers and identifiers[row["id"]] != clean:
            raise ValueError("Conflicting duplicate event ID")
        identifiers[row["id"]] = clean
        rows.append(clean)
    sessions = event_sequences(rows, max_gap_seconds)
    recordings = sorted({row["recording_id"] for row in sessions})
    if len(recordings) < 3:
        raise ValueError("At least three independent recordings with verified observations needed")
    random.Random(seed).shuffle(recordings)
    train_end = min(int(0.8 * len(recordings)), len(recordings) - 2)
    dev_end = train_end + max(1, int(0.1 * len(recordings)))
    split = {
        "train": recordings[:train_end],
        "dev": recordings[train_end:dev_end],
        "test": recordings[dev_end:],
    }
    labels = {}
    supplied = export.get("labels", [])
    if not isinstance(supplied, list):
        raise ValueError("Labels must be a list")
    provenance = export.get("label_provenance")
    if supplied and (
        not isinstance(provenance, dict)
        or provenance.get("independent") is not True
        or not isinstance(provenance.get("source"), str)
        or not 1 <= len(provenance["source"].strip()) <= 500
    ):
        raise ValueError("Labels require an explicit independent source in label_provenance")
    keys = {session_key(row) for row in sessions}
    for row in supplied:
        if (
            not isinstance(row, dict)
            or set(row) != {"recording_id", "track_id", "session_index", "novel"}
            or not isinstance(row["recording_id"], str)
            or type(row["track_id"]) is not int
            or type(row["session_index"]) is not int
            or type(row["novel"]) is not bool
        ):
            raise ValueError("Invalid session novelty label")
        key = session_key(row)
        if key not in keys or key in labels:
            raise ValueError("Label must identify exactly one existing session")
        labels[key] = row["novel"]
    return sessions, split, labels


def prepare_v2(export, workspace_id, seed, max_gap_seconds):
    if any(
        not isinstance(row, dict) or row.get("workspace_id") != workspace_id
        for row in export["events"]
    ):
        raise ValueError("Every event must belong to the explicit workspace")
    sessions = event_sequences_v2(export["events"], max_gap_seconds)
    # The same original hash OR attributed source group connects all derived recordings.
    parents = {}

    def find(value):
        parents.setdefault(value, value)
        root = value
        while parents[root] != root:
            root = parents[root]
        while parents[value] != value:
            previous = parents[value]
            parents[value] = root
            value = previous
        return root

    for session in sessions:
        for event in session["source_events"]:
            a, b = find(event["original_source_sha256"]), find(event["source_group"])
            parents[max(a, b)] = min(a, b)
    for session in sessions:
        session["source_group"] = find(session["source_group"])
    by_recording = {}
    for session in sessions:
        previous = by_recording.setdefault(
            session["recording_id"], (session["source_group"], session["source_revision"])
        )
        if previous != (session["source_group"], session["source_revision"]):
            raise ValueError("A recording must use one original source and revision per run")
    groups = sorted({row["source_group"] for row in sessions})
    if len(groups) < 3:
        raise ValueError(
            "At least three independent original source hashes required; copies share a split"
        )
    random.Random(seed).shuffle(groups)
    train_end = min(int(0.8 * len(groups)), len(groups) - 2)
    dev_end = train_end + max(1, int(0.1 * len(groups)))
    group_split = {
        "train": groups[:train_end],
        "dev": groups[train_end:dev_end],
        "test": groups[dev_end:],
    }
    split = {
        name: sorted({row["recording_id"] for row in sessions if row["source_group"] in selected})
        for name, selected in group_split.items()
    }
    labels = {}
    supplied = export.get("labels", [])
    provenance = export.get("label_provenance", {})
    if not isinstance(supplied, list) or (
        supplied
        and (
            not isinstance(provenance, dict)
            or provenance.get("independent") is not True
            or any(
                not isinstance(provenance.get(k), str) or not 1 <= len(provenance[k].strip()) <= 500
                for k in ("source", "rubric")
            )
        )
    ):
        raise ValueError("Novelty labels require independent source and frozen rubric provenance")
    keys = {session_key(row) for row in sessions}
    for label in supplied:
        if (
            not isinstance(label, dict)
            or set(label) != {"recording_id", "track_id", "session_index", "novel"}
            or not isinstance(label["recording_id"], str)
            or type(label["track_id"]) is not int
            or label["track_id"] < 0
            or type(label["session_index"]) is not int
            or label["session_index"] < 0
            or type(label["novel"]) is not bool
        ):
            raise ValueError("Invalid novelty label")
        key = session_key(label)
        if key not in keys or key in labels:
            raise ValueError("Label must identify exactly one session")
        labels[key] = label["novel"]
    return sessions, split, labels


def quantile95(values):
    """Linear interpolation at (N-1)*.95, including the single-session case."""
    values = sorted(values)
    if not values or any(not math.isfinite(value) for value in values):
        raise ValueError("Calibration requires finite nonempty dev session losses")
    position = (len(values) - 1) * 0.95
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (position - lower) * (values[upper] - values[lower])


def session_loss(model, session):
    return evaluate_counts(model, model.bank.event_counts([session["symbols"]], model.n))[
        "score_cross_entropy"
    ]


def label_metrics(predictions, labels):
    supported = [row for row in predictions if row.get("supported", True)]
    paired = [
        (row["alert"], labels[session_key(row)]) for row in supported if session_key(row) in labels
    ]
    tp = sum(predicted and actual for predicted, actual in paired)
    fp = sum(predicted and not actual for predicted, actual in paired)
    fn = sum(not predicted and actual for predicted, actual in paired)
    return {
        "labelled_test_sessions": len(paired),
        "available_labelled_test_sessions": sum(session_key(row) in labels for row in predictions),
        "supported_test_sessions": len(supported),
        "test_sessions": len(predictions),
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "true_positives": tp if paired else None,
        "false_positives": fp if paired else None,
        "false_negatives": fn if paired else None,
        "false_alerts_per_hour": None,
        "detection_delay_seconds": None,
    }


def run_novelty(run_id, export, workspace_id, seed=42, max_gap_seconds=30):
    sessions, split, labels = prepare(export, workspace_id, seed, max_gap_seconds)
    partitions = {
        name: [row for row in sessions if row["recording_id"] in ids] for name, ids in split.items()
    }
    train = [row["symbols"] for row in partitions["train"]]
    version2 = export.get("schema_version") == 2
    alphabet = (
        {symbol for row in partitions["train"] for symbol in row["symbols"]}
        if version2
        else SYMBOLS
    )
    methods = (
        ("add_k", "kneser_ney", "witten_bell", "modified_kneser_ney")
        if version2
        else ("kneser_ney", "witten_bell")
    )
    vocabulary = sorted(alphabet | {EOS, UNK})
    bank = CountBank.from_counts(
        vocabulary,
        {n: Counter(gram for sentence in train for gram in events(sentence, n)) for n in (1, 2, 3)},
        min_count=1,
    )
    config = {
        "experiment": "offline-event-novelty-v2" if version2 else "offline-event-novelty-v1",
        "schema_version": 2 if version2 else 1,
        "tokenizer": "ledger-bundles-v2" if version2 else TOKENIZER,
        "algorithm": ALGORITHM_VERSION,
        "workspace_id": workspace_id,
        "source_sha256": registry.fingerprint(export),
        "seed": seed,
        "max_gap_seconds": max_gap_seconds,
        "split": split,
        "split_policy": "seeded original source hash groups; copies share partitions"
        if version2
        else "seeded recording groups; floor 80/10/10 with >=1 dev and test",
        "unit": "observed recording/track session separated by event gaps",
        "alphabet": sorted(alphabet),
        "vocabulary": vocabulary,
        "boundaries": {"context": BOS, "predicted_end": EOS, "reserved_unknown": UNK},
        "loss_units": "natural-log NLL per predicted symbol, including one EOS per session",
        "selection": "minimum token-weighted dev CE; model name breaks ties",
        "threshold": "linear 95th percentile of dev session CE; alert when CE > threshold",
        "frequency_baseline": "alert if any adjacent symbol pair has training count < 2",
        "grid": {f"{n}-{method}": candidates(n, method) for n in (1, 2, 3) for method in methods},
        "label_provenance": export.get("label_provenance") if labels else None,
        "test_policy": (
            "parameters and thresholds fixed on dev before single test scoring; "
            "prior export exposure unknown"
        ),
        "limitations": [
            "Local export status is trusted input, not cryptographic proof of reviewer approval.",
            "Source hashes group copies in v2; v1 recording independence is user-declared.",
            "No duration features; event gaps do not establish camera coverage or exposure hours.",
            "Session scores require the full offline sequence, not causal live detection.",
            "No hazard, attendance or identity inference; independent labels are user-declared.",
            "False alerts/hour and delay unavailable without exposure and onset ground truth.",
        ],
        "code_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "extensions/experiments/event_novelty.py",
                "extensions/experiments/registry.py",
                "extensions/src/event_sequences.py",
                "extensions/src/models.py",
                "extensions/src/pipeline.py",
                "core/src/ngram.py",
            )
        },
    }
    directory = registry.create_run(run_id, config)
    registry.start_stage(run_id, "event_novelty", config)
    registry.atomic_json(directory / "protocol.json", config)
    registry.atomic_json(directory / "sessions.json", sessions)
    registry.atomic_json(directory / "labels.json", export.get("labels", []))
    registry.atomic_json(
        directory / "counts.json",
        {
            "schema": "event-counts-v1",
            "tokenizer": "ledger-bundles-v2" if version2 else TOKENIZER,
            "vocabulary": vocabulary,
            "raw": {
                str(n): [[list(gram), count] for gram, count in sorted(counts.items())]
                for n, counts in bank.raw.items()
            },
        },
    )
    trained, calibration = {}, {}
    for n in (1, 2, 3):
        for method in methods:
            if version2 and method == "add_k" and n != 1:
                continue
            name = f"{n}-{method}"
            model, winner, trials = tune(
                bank,
                n,
                method,
                bank.event_counts([row["symbols"] for row in partitions["dev"]], n),
            )
            dev_losses = [session_loss(model, row) for row in partitions["dev"]]
            calibration[name] = {
                "n": n,
                "method": method,
                "winner": winner,
                "trials": trials,
                "dev_session_ce": dev_losses,
                "threshold": quantile95(dev_losses),
                "parameters": {
                    key: getattr(model, key)
                    for key in ("k", "discount", "weights", "backoff", "epsilon")
                },
            }
            trained[name] = model
    best = min(calibration, key=lambda name: (calibration[name]["winner"]["dev_loss"], name))
    registry.atomic_json(directory / "selection.json", {"best": best, "models": calibration})
    # ponytail: no duration bins; add only with train-fitted bins and coverage/onset evidence.
    pair_counts = Counter(pair for sentence in train for pair in zip(sentence, sentence[1:]))
    predictions = {name: [] for name in (*trained, "pair_frequency_lt2")}
    for row in partitions["test"]:
        identity = {key: row[key] for key in ("recording_id", "track_id", "session_index")}
        for name, model in trained.items():
            loss = session_loss(model, row)
            predictions[name].append(
                {
                    **identity,
                    "session_ce": loss,
                    "alert": loss > calibration[name]["threshold"],
                }
            )
        pairs = list(zip(row["symbols"], row["symbols"][1:]))
        predictions["pair_frequency_lt2"].append(
            {
                **identity,
                "rare_pairs": sum(pair_counts[pair] < 2 for pair in pairs),
                "alert": any(pair_counts[pair] < 2 for pair in pairs),
                "supported": bool(pairs),
            }
        )
    summary = {
        "mode": "labelled offline novelty evaluation"
        if any(session_key(row) in labels for row in partitions["test"])
        else "novelty diagnostics only; no labelled test evidence",
        "selected_model": best,
        "models": {
            name: {**label_metrics(rows, labels), "alerts": sum(row["alert"] for row in rows)}
            for name, rows in predictions.items()
        },
    }
    registry.atomic_json(directory / "predictions.json", predictions)
    if version2:
        import time

        explanations, costs = [], []
        for row in sessions:
            model = trained[best]
            started = time.perf_counter()
            mapped = model.map_sentence(row["symbols"])
            terms = []
            for index, gram in enumerate(events(mapped, model.n)):
                probability = model.score_mapped(gram[-1], gram[:-1])
                terms.append(
                    {
                        "symbol": row["symbols"][index] if index < len(row["symbols"]) else EOS,
                        "mapped_symbol": gram[-1],
                        "context": list(gram[:-1]),
                        "probability": probability,
                        "log_probability": math.log(probability) if probability else None,
                        "nll": -math.log(probability) if probability else None,
                        "event_ids": row["bundles"][index]["event_ids"]
                        if index < len(row["bundles"])
                        else [],
                        "seconds": row["times"][index] if index < len(row["times"]) else None,
                    }
                )
            cached = next(
                (item for item in predictions[best] if session_key(item) == session_key(row)), None
            )
            loss = cached["session_ce"] if cached is not None else session_loss(model, row)
            costs.append((time.perf_counter() - started) * 1000)
            explanations.append(
                {
                    **row,
                    "partition": next(
                        name for name, ids in split.items() if row["recording_id"] in ids
                    ),
                    "model": best,
                    "threshold": calibration[best]["threshold"],
                    "session_ce": loss,
                    "needs_review": loss > calibration[best]["threshold"],
                    "terms": terms,
                }
            )
        ordered = sorted(costs)
        summary["scoring_ms"] = {
            "p50": ordered[int((len(ordered) - 1) * 0.5)],
            "p95": ordered[int((len(ordered) - 1) * 0.95)],
            "samples": len(ordered),
        }
        summary["threshold"] = calibration[best]["threshold"]
        summary["schema_version"] = 2
        summary["source_groups"] = sorted({row["source_group"] for row in sessions})
        summary["limitations"] = [
            "Full-session offline; novelty needs review, not hazard.",
            "Labels absent unless supplied; false alerts/hour requires camera exposure.",
        ]
        registry.atomic_json(directory / "explanations.json", explanations)
    registry.atomic_json(directory / "summary.json", summary)
    registry.complete_stage(run_id, "event_novelty")
    return directory


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Input: {events:[authenticated ledger rows], labels?:"
            "[{recording_id,track_id,session_index,novel}], "
            "label_provenance?:{source,independent:true}}. Labels are optional. "
            "Outputs are private offline diagnostics under extensions/results/runs/<run-id>."
        ),
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-gap-seconds", type=float, default=30)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Ledger export exceeds 16 MiB")
        export = json.loads(raw)
        directory = run_novelty(
            args.run_id, export, args.workspace_id, args.seed, args.max_gap_seconds
        )
    except (ValueError, OSError) as error:
        parser.exit(2, f"event novelty: {error}\n")
    print(directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
