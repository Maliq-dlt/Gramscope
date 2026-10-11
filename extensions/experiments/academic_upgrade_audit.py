"""Reproduce sealed academic run development losses without touching test scores."""

from __future__ import annotations

import argparse
import csv
import json
import math
from importlib.metadata import version
from pathlib import Path

from core.src.data import ROOT
from extensions.experiments import registry
from extensions.experiments.academic_upgrade import (
    SEEDS,
    SPECS,
    development_partition,
    group_se,
    load_corpus,
    select_one_se,
    sha,
)
from extensions.src.analytics import aggregate, document_losses
from extensions.src.datasets import digest, sentences, split_documents
from extensions.src.models import CountBank, ExtensionLM

DESTINATION = ROOT / "extensions/results/academic_upgrade_v2/dev_reproduction"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def checked_number(actual, recorded):
    if not math.isfinite(actual) or not math.isclose(
        actual, float(recorded), rel_tol=0, abs_tol=1e-12
    ):
        raise ValueError(f"Development statistic differs: {actual} != {recorded}")
    return abs(actual - float(recorded))


def check_selection(rows, losses, recorded):
    best = min(rows, key=lambda row: (row["dev_ce_nats"], row["model"]))
    se = group_se(losses[best["model"]])
    actual = select_one_se(rows, se)
    for key in ("minimum_dev", "one_se", "eligible"):
        if actual[key] != recorded[key]:
            raise ValueError(f"Recorded development selection differs: {key}")
    errors = {
        "best_se_nats": checked_number(actual["best_se_nats"], recorded["best_se_nats"]),
        "ceiling_nats": checked_number(actual["ceiling_nats"], recorded["ceiling_nats"]),
    }
    return actual, errors


def reproduce(corpus):
    if corpus not in ("brown", "reuters", "idwiki"):
        raise ValueError("Choose brown, reuters or idwiki")
    run_id = f"academic-v2-{corpus}-20261011"
    directory = registry.run_directory(run_id)
    receipt = registry.read_run(run_id)
    protocol = read_json(directory / "protocol.json")
    selection = read_json(directory / "selection.json")
    if receipt["config"] != protocol or protocol["corpus"] != corpus:
        raise ValueError("Completed run protocol differs")
    if (
        protocol["min_count"] != 2
        or protocol["seeds"] != list(SEEDS)
        or protocol["models"] != [list(spec) for spec in SPECS]
    ):
        raise ValueError("Unsupported sealed development protocol")
    for name, expected in protocol["code_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Sealed source changed: {name}")
    for name, expected in protocol["versions"].items():
        if version(name) != expected:
            raise ValueError(f"Sealed dependency changed: {name}")
    input_path = ROOT / protocol["provenance"]["path"] if corpus == "idwiki" else None
    documents, provenance = load_corpus(corpus, input_path)
    if provenance != protocol["provenance"] or digest(documents) != protocol["corpus_sha256"]:
        raise ValueError("Corpus source or contents differ from sealed protocol")
    split, manifest = split_documents(documents, seed=42)
    if manifest != protocol["split"]:
        raise ValueError("Rebuilt duplicate/source split differs")

    with (directory / "development.csv").open(encoding="utf-8", newline="") as stream:
        recorded_rows = {(int(r["seed"]), r["model"]): r for r in csv.DictReader(stream)}
    if len(recorded_rows) != len(SEEDS) * len(SPECS):
        raise ValueError("Incomplete recorded development table")
    if [s["seed"] for s in selection["selections"]] != list(SEEDS):
        raise ValueError("Recorded selection seeds differ")
    output_rows, summaries, tuning_hashes = [], [], {}
    max_error = 0.0
    for seed, saved in zip(SEEDS, selection["selections"]):
        partition = development_partition(split, seed)
        partition_ids = {key: [doc["id"] for doc in value] for key, value in partition.items()}
        if partition_ids != saved["partition_ids"]:
            raise ValueError("Rebuilt train/dev partitions differ")
        bank = CountBank(sentences(partition["train"]), max_n=3, min_count=2)
        rows, losses_by_model = [], {}
        for n, method in SPECS:
            model_name = f"{n}-{method}"
            tuning_path = directory / f"tuning/{seed}-{model_name}.json"
            tuning = read_json(tuning_path)
            tuning_hashes[str(tuning_path.relative_to(directory)).replace("\\", "/")] = sha(
                tuning_path
            )
            model = ExtensionLM(bank, n, method, **tuning["winner"]["parameters"])
            if digest(model.mkn_discounts) != digest(tuning["discounts"]):
                raise ValueError(f"Recorded MKN discounts differ: {seed}-{model_name}")
            losses = document_losses(model, partition["dev"])
            ce = aggregate(losses)["cross_entropy"]
            recorded = recorded_rows[(seed, model_name)]
            max_error = max(
                max_error,
                checked_number(ce, tuning["winner"]["dev_loss"]),
                checked_number(ce, recorded["dev_ce_nats"]),
            )
            if int(recorded["vocabulary_size"]) != len(bank.vocabulary):
                raise ValueError("Recorded development vocabulary size differs")
            rows.append({"model": model_name, "n": n, "method": method, "dev_ce_nats": ce})
            losses_by_model[model_name] = losses
            output_rows.extend({"seed": seed, "model": model_name, **row} for row in losses)
        actual, errors = check_selection(rows, losses_by_model, saved)
        max_error = max(max_error, *errors.values())
        summaries.append(
            {
                "seed": seed,
                "train_documents": len(partition["train"]),
                "dev_documents": len(partition["dev"]),
                "dev_groups": len({doc["split_group"] for doc in partition["dev"]}),
                "vocabulary_size": len(bank.vocabulary),
                **actual,
                "models": rows,
            }
        )
    summary = {
        "status": "dev-only reproduced; no test model loaded or scored",
        "source_run": run_id,
        "corpus": corpus,
        "source_run_manifest_sha256": sha(directory / "manifest.json"),
        "source_protocol_sha256": sha(directory / "protocol.json"),
        "source_selection_sha256": sha(directory / "selection.json"),
        "source_corpus_sha256": protocol["corpus_sha256"],
        "source_provenance": provenance,
        "source_tuning_sha256": tuning_hashes,
        "audit_code_sha256": sha(Path(__file__)),
        "max_abs_statistic_difference": max_error,
        "development": summaries,
        "loss_rows": len(output_rows),
    }
    output = DESTINATION / corpus
    output.mkdir(parents=True)  # exclusive: never alter a prior reproduction
    with (output / "dev_documents.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    with (output / "summary.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    with (output / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "status": "completed",
                "files": {
                    name: sha(output / name) for name in ("dev_documents.csv", "summary.json")
                },
                "source_run": run_id,
            },
            stream,
            indent=2,
        )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", choices=("brown", "reuters", "idwiki"), required=True)
    args = parser.parse_args()
    try:
        result = reproduce(args.corpus)
    except (OSError, ValueError) as error:
        parser.exit(2, f"development reproduction: {error}\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("corpus", "status", "loss_rows", "max_abs_statistic_difference")
            }
        )
    )


if __name__ == "__main__":
    main()
