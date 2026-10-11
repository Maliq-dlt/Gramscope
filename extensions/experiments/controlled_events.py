"""Reproducible synthetic event-order experiment; never camera accuracy evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter
from importlib.metadata import version
from pathlib import Path

from core.src.data import ROOT
from extensions.experiments import event_novelty, registry
from extensions.src.models import CountBank, ExtensionLM

WORKSPACE = "academic-controlled-v1"
TEMPLATES = {
    "person_worn": [["PERSON_ENTER_ZONE", "HELMET_WORN"], ["HELMET_WORN"], ["PERSON_EXIT_ZONE"]],
    "person_unknown": [
        ["PERSON_ENTER_ZONE", "HELMET_UNKNOWN"],
        ["HELMET_UNKNOWN"],
        ["PERSON_EXIT_ZONE"],
    ],
    "person_not_worn": [
        ["PERSON_ENTER_ZONE", "HELMET_NOT_WORN"],
        ["HELMET_NOT_WORN"],
        ["PERSON_EXIT_ZONE"],
    ],
    "person_resolved": [
        ["PERSON_ENTER_ZONE", "HELMET_UNKNOWN"],
        ["HELMET_WORN"],
        ["PERSON_EXIT_ZONE"],
    ],
    "person_obscured": [
        ["PERSON_ENTER_ZONE", "HELMET_WORN"],
        ["HELMET_UNKNOWN"],
        ["PERSON_EXIT_ZONE"],
    ],
    **{
        kind.lower(): [[f"{kind}_ENTER_ZONE"], [f"{kind}_EXIT_ZONE"]]
        for kind in ("CAR", "BUS", "TRUCK")
    },
}


def controlled_export():
    """Freeze groups/seed first; reverse only held-out sequences, preserving symbol counts."""
    groups = [
        (f"synthetic-{i:02}", registry.fingerprint({"synthetic_group": i})) for i in range(20)
    ]
    shuffled = sorted(digest for _, digest in groups)
    random.Random(42).shuffle(shuffled)
    heldout = set(shuffled[18:])  # same fixed 80/10/10 source-group policy as the runner
    rows, cases = [], []
    for job, digest in groups:
        canonical = {"job": job, "templates": TEMPLATES, "reversed_test": digest in heldout}
        for index, (scenario, bundles) in enumerate(TEMPLATES.items(), 1):
            variants = {"canonical": bundles}
            if digest in heldout:
                variants["reversed"] = list(reversed(bundles))
            for variant, sequence in variants.items():
                track = index if variant == "canonical" else index + len(TEMPLATES)
                cases.append(
                    {
                        "recording_id": job,
                        "track_id": track,
                        "session_index": 0,
                        "scenario": scenario,
                        "variant": variant,
                        "pair_id": f"{job}-{scenario}",
                    }
                )
                for seconds, symbols in enumerate(sequence, 1):
                    for symbol in symbols:
                        rows.append(
                            {
                                "id": f"{job}-{track}-{seconds}-{symbol}",
                                "workspace_id": WORKSPACE,
                                "job_id": job,
                                "track_id": track,
                                "symbol": symbol,
                                "status": "verified",
                                "category": "observation",
                                "occurred_at": None,
                                "payload": {
                                    "schema_version": 2,
                                    "seconds": seconds,
                                    "source_revision": registry.fingerprint(canonical),
                                    "original_source_sha256": digest,
                                },
                            }
                        )
    return {
        "schema_version": 2,
        "events": rows,
        "controlled_cases": cases,
        "provenance": {
            "kind": "synthetic-controlled",
            "generator": __name__,
            "seed": 42,
            "source_groups": 20,
            "approval": "test-only verified fixture; no real reviewer or footage",
            "independence": "synthetic replicas share templates; not independent cameras",
            "labels": "none; canonical/reversed are construction tags, not hazard truth",
        },
    }


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def paper_tables(directory, export):
    config = read_json(directory / "protocol.json")
    selection = read_json(directory / "selection.json")
    predictions = read_json(directory / "predictions.json")
    explanations = read_json(directory / "explanations.json")
    counts = read_json(directory / "counts.json")
    bank = CountBank.from_counts(
        counts["vocabulary"],
        {
            int(n): Counter({tuple(gram): count for gram, count in grams})
            for n, grams in counts["raw"].items()
        },
        min_count=1,
    )
    cases = {event_novelty.session_key(row): row for row in export["controlled_cases"]}
    sessions, terms, comparisons, contrasts = [], [], [], []
    for row in explanations:
        case = cases[event_novelty.session_key(row)]
        base = {
            k: row[k] for k in ("recording_id", "track_id", "session_index", "partition", "model")
        }
        base.update({k: case[k] for k in ("scenario", "variant", "pair_id")})
        nll = math.fsum(term["nll"] for term in row["terms"])
        if not math.isclose(nll / len(row["terms"]), row["session_ce"], abs_tol=1e-10):
            raise ValueError("Per-symbol NLL does not match the frozen session CE")
        sessions.append(
            {
                **base,
                "symbols": " -> ".join(row["symbols"]),
                "targets_including_eos": len(row["terms"]),
                "nll": nll,
                "ce_nats": row["session_ce"],
                "perplexity": math.exp(row["session_ce"]),
                "oov_targets": sum(t["symbol"] != t["mapped_symbol"] for t in row["terms"]),
                "threshold": row["threshold"],
                "needs_review": row["needs_review"],
            }
        )
        for index, term in enumerate(row["terms"]):
            terms.append(
                {
                    **base,
                    "position": index,
                    **{
                        k: term[k]
                        for k in (
                            "symbol",
                            "mapped_symbol",
                            "probability",
                            "log_probability",
                            "nll",
                            "seconds",
                        )
                    },
                    "context": " | ".join(term["context"]),
                    "event_ids": " | ".join(term["event_ids"]),
                }
            )
    targets = {event_novelty.session_key(row): len(row["terms"]) for row in explanations}
    for name, rows in predictions.items():
        calibrated = selection["models"].get(name)
        losses = [r["session_ce"] for r in rows] if calibrated else []
        total = sum(targets[event_novelty.session_key(r)] for r in rows)
        ce = (
            sum(targets[event_novelty.session_key(r)] * r["session_ce"] for r in rows) / total
            if losses
            else None
        )
        discounts = (
            ExtensionLM(
                bank, calibrated["n"], calibrated["method"], **calibrated["parameters"]
            ).mkn_discounts
            if calibrated
            else {}
        )
        comparisons.append(
            {
                "model": name,
                "selected_on_dev": name == selection["best"],
                "dev_ce_nats": calibrated["winner"]["dev_loss"] if calibrated else None,
                "threshold": calibrated["threshold"] if calibrated else None,
                "test_ce_nats": ce,
                "test_perplexity": math.exp(ce) if ce is not None else None,
                "test_sessions": len(rows),
                "test_targets_including_eos": total,
                "canonical_alerts": sum(
                    r["alert"]
                    for r in rows
                    if cases[event_novelty.session_key(r)]["variant"] == "canonical"
                ),
                "reversed_alerts": sum(
                    r["alert"]
                    for r in rows
                    if cases[event_novelty.session_key(r)]["variant"] == "reversed"
                ),
                "parameters": json.dumps(
                    calibrated["parameters"] if calibrated else {"pair_count_lt": 2}, sort_keys=True
                ),
                "mkn_discount_details": json.dumps(discounts, sort_keys=True),
            }
        )
        by_pair = {}
        for row in rows:
            case = cases[event_novelty.session_key(row)]
            by_pair.setdefault(case["pair_id"], {})[case["variant"]] = row
        for pair, variants in sorted(by_pair.items()):
            a, b = variants["canonical"], variants["reversed"]
            contrasts.append(
                {
                    "model": name,
                    "pair_id": pair,
                    "canonical_ce_nats": a.get("session_ce"),
                    "reversed_ce_nats": b.get("session_ce"),
                    "delta_ce_nats": b["session_ce"] - a["session_ce"] if calibrated else None,
                    "canonical_alert": a["alert"],
                    "reversed_alert": b["alert"],
                }
            )
    return config, {
        "model_comparison.csv": comparisons,
        "sessions.csv": sessions,
        "token_probabilities.csv": terms,
        "order_contrasts.csv": contrasts,
    }


def check_package(output):
    manifest = read_json(output / "manifest.json")
    if manifest.get("status") != "completed" or manifest.get("data_kind") != "synthetic-controlled":
        raise ValueError("Not a completed controlled data package")
    if not isinstance(manifest.get("files"), dict) or not manifest["files"]:
        raise ValueError("Data package requires file fingerprints")
    for name, digest in manifest["files"].items():
        if not isinstance(name, str) or not isinstance(digest, str):
            raise ValueError("Invalid package fingerprint")
        path = output / name
        if not path.resolve().is_relative_to(output.resolve()) or path.is_symlink():
            raise ValueError("Invalid package path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Package fingerprint mismatch: {name}")
    return manifest


def build(run_id, output):
    output = Path(output)
    if not output.resolve().is_relative_to(ROOT.resolve()) or output.is_symlink():
        raise ValueError("Output must stay inside the repository")
    if output.exists():
        raise FileExistsError("Data package exists; use a new output and run ID")
    export = controlled_export()
    directory = event_novelty.run_novelty(run_id, export, WORKSPACE)
    receipt = registry.read_run(run_id)
    config, tables = paper_tables(directory, export)
    if config["source_sha256"] != registry.fingerprint(export):
        raise ValueError("Run input fingerprint mismatch")
    output.mkdir(parents=True)
    for name in ("protocol.json", "selection.json", "predictions.json", "summary.json"):
        registry.atomic_json(output / name, read_json(directory / name))
    registry.atomic_json(output / "input_events.json", export)
    for name, rows in tables.items():
        with (output / name).open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    registry.atomic_json(
        output / "manifest.json",
        {
            "schema_version": 1,
            "status": "completed",
            "data_kind": "synthetic-controlled",
            "run_id": run_id,
            "source_config_sha256": receipt["config_sha256"],
            "source_files": receipt["files"],
            "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "versions": {name: version(name) for name in ("ngram-assignment", "nltk", "numpy")},
            "table_rows": {name: len(rows) for name, rows in tables.items()},
            "unavailable_metrics": [
                "camera precision",
                "camera recall",
                "IDF1",
                "false alerts/hour",
                "detection delay",
            ],
            "files": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(output.iterdir())
                if p.is_file()
            },
        },
    )
    return check_package(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if args.check:
            manifest = check_package(args.output)
        elif args.run_id:
            manifest = build(args.run_id, args.output)
        else:
            parser.error("--run-id is required for a new experiment")
    except (ValueError, OSError) as error:
        parser.exit(2, f"controlled study: {error}\n")
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "run_id": manifest["run_id"],
                "table_rows": manifest["table_rows"],
            }
        )
    )


if __name__ == "__main__":
    main()
