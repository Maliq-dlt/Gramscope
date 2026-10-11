"""Fresh document holdout: dev-only selection; held-out test scored once after freeze."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from importlib.metadata import version
from pathlib import Path
from typing import Any

from core.src.data import ROOT
from extensions.experiments import registry
from extensions.experiments.prepare_indonesian import LICENSE, POLICY
from extensions.experiments.wiki_expansion import PILOT, eligible_documents
from extensions.src.analytics import aggregate, document_losses, paired_bootstrap
from extensions.src.cli import save_model
from extensions.src.datasets import POLICY as DUPLICATE_POLICY
from extensions.src.datasets import digest, read_documents, sentences, split_documents
from extensions.src.models import CountBank
from extensions.src.pipeline import tune

SPECS = (
    (1, "kneser_ney"),
    (2, "kneser_ney"),
    (3, "kneser_ney"),
    (2, "witten_bell"),
    (3, "witten_bell"),
    (2, "modified_kneser_ney"),
    (3, "modified_kneser_ney"),
    (3, "interpolation_em"),
)


def development_split(documents, seed, train_groups):
    groups = {}
    for doc in documents:
        groups.setdefault(doc["split_group"], []).append(doc)
    keys = sorted(groups)
    random.Random(seed).shuffle(keys)
    cut = train_groups
    if not 1 <= cut < len(keys):
        raise ValueError("Development partition requires nonempty train/dev groups")
    return {
        name: [d for key in subset for d in groups[key]]
        for name, subset in (("train", keys[:cut]), ("dev", keys[cut:]))
    }


def corpus_provenance(corpus, docs):
    """Verify the frozen collector snapshot and independently recheck pilot exclusion."""
    corpus = Path(corpus).resolve()
    if not corpus.is_relative_to(ROOT.resolve()):
        raise ValueError("Corpus must stay inside the repository")
    path = corpus.with_name("manifest.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "format": "indonesian-wikipedia-expansion-v1",
        "policy": POLICY,
        "language": "id",
        "license": LICENSE,
        "jsonl_sha256": hashlib.sha256(Path(corpus).read_bytes()).hexdigest(),
        "documents_sha256": digest(docs),
        "documents": len(docs),
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError("Collector manifest or corpus fingerprint differs")
    pilot = read_documents(PILOT)
    exclusion = manifest.get("pilot_exclusion", {})
    if any(
        exclusion.get(key) != value
        for key, value in {
            "path": str(PILOT.relative_to(ROOT)),
            "jsonl_sha256": hashlib.sha256(PILOT.read_bytes()).hexdigest(),
            "documents_sha256": digest(pilot),
            "ids": sorted(doc["id"] for doc in pilot),
            "duplicate_policy": DUPLICATE_POLICY,
        }.items()
    ):
        raise ValueError("Historical pilot exclusion fingerprint differs")
    eligible, groups, _ = eligible_documents(pilot, docs)
    if len(eligible) != len(docs) or manifest.get("independent_groups") != len(groups):
        raise ValueError("Corpus contains pilot duplicates or incorrect group count")
    articles = manifest.get("articles", [])
    if not isinstance(articles, list) or len(articles) != len(docs):
        raise ValueError("Missing article provenance")
    by_id = {article.get("id"): article for article in articles}
    for doc in docs:
        suffix = doc["id"].removeprefix("idwiki/")
        article = by_id.get(doc["id"], {})
        if (
            not doc["id"].startswith("idwiki/")
            or not suffix.isdecimal()
            or int(suffix) < 1
            or doc["source"] != f"https://id.wikipedia.org/?curid={suffix}"
            or doc["license"] != LICENSE
            or article.get("license") != LICENSE
            or article.get("source_url") != doc["source"]
            or article.get("tokens_sha256") != digest(doc["sentences"])
        ):
            raise ValueError("Article provenance does not match corpus")
    for key, name in (
        ("importer_sha256", "wiki_expansion.py"),
        ("pilot_importer_sha256", "prepare_indonesian.py"),
    ):
        actual = hashlib.sha256((ROOT / "extensions/experiments" / name).read_bytes()).hexdigest()
        if manifest.get(key) != actual:
            raise ValueError("Collector code differs from frozen snapshot")
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        **expected,
    }


def run(run_id, corpus, output, minimum_groups=200):
    if type(minimum_groups) is not int or minimum_groups < 3:
        raise ValueError("minimum_groups must be an integer >=3")
    output = Path(output)
    if output.exists():
        raise FileExistsError("Use a fresh public output directory")
    registry.run_directory(run_id)  # Validate ID before corpus/fitting or any mutation.
    if output.resolve().is_relative_to(registry.RUNS.resolve()):
        raise ValueError("Public output must stay outside immutable registry runs")
    if not output.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Output must stay inside the repository")
    corpus = Path(corpus).resolve()
    if not corpus.is_relative_to(ROOT.resolve()):
        raise ValueError("Corpus must stay inside the repository")
    docs = read_documents(corpus)
    if any(
        not token.isalpha() or token != token.lower()
        for doc in docs
        for sentence in doc["sentences"]
        for token in sentence
    ):
        raise ValueError("Corpus requires the fixed lowercase alphabetic preprocessing")
    provenance = corpus_provenance(corpus, docs)
    split, split_manifest = split_documents(docs, 42)
    train_groups = len({d["split_group"] for d in split["train"]})
    if len(split_manifest["groups"]) < minimum_groups:
        raise ValueError("Insufficient independent document groups")
    config = {
        "experiment": "fresh-idwiki-holdout-v1",
        "corpus_sha256": digest(docs),
        "collector": provenance,
        "split": split_manifest,
        "models": SPECS,
        "min_count": 2,
        "versions": {name: version(name) for name in ("numpy", "nltk")},
        "primary_seed": 42,
        "development_seeds": [43, 44],
        "development_train_groups": train_groups,
        "selection": "minimum token-weighted dev CE, lexical tie",
        "test_policy": "primary winner and same-order KN scored once; no seed selected from test",
        "limitations": (
            "encyclopedic introductions, bounded lexical selection; "
            "not population-general confirmation"
        ),
        "code_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "extensions/experiments/fresh_holdout.py",
                "extensions/src/models.py",
                "extensions/src/pipeline.py",
                "extensions/src/datasets.py",
                "extensions/src/analytics.py",
                "extensions/src/cli.py",
                "extensions/experiments/registry.py",
                "core/src/ngram.py",
                "core/src/preprocess.py",
            )
        },
    }
    directory = registry.create_run(run_id, config)
    registry.start_stage(run_id, "holdout", config)
    registry.atomic_json(directory / "protocol.json", config)
    selections: list[dict[str, Any]] = []
    trained = {}
    for seed in (42, 43, 44):
        partition = (
            split
            if seed == 42
            else development_split(split["train"] + split["dev"], seed, train_groups)
        )
        bank = CountBank(sentences(partition["train"]), max_n=3, min_count=2)
        rows = []
        for n, method in SPECS:
            model, winner, trials = tune(
                bank, n, method, bank.event_counts(sentences(partition["dev"]), n)
            )
            name = f"{n}-{method}"
            if not math.isfinite(winner["dev_loss"]):
                raise ValueError("Nonfinite dev selection; do not inspect test")
            rows.append(
                {
                    "seed": seed,
                    "model": name,
                    "n": n,
                    "method": method,
                    "dev_ce_nats": winner["dev_loss"],
                    "train_documents": len(partition["train"]),
                    "dev_documents": len(partition["dev"]),
                    "vocabulary_size": len(bank.vocabulary),
                }
            )
            registry.atomic_json(
                directory / f"tuning/{seed}-{name}.json", {"winner": winner, "trials": trials}
            )
            if seed == 42:
                trained[name] = model
        best = min(rows, key=lambda r: (r["dev_ce_nats"], r["model"]))
        selections.append(
            {
                "seed": seed,
                "winner": best["model"],
                "dev_ce_nats": best["dev_ce_nats"],
                "partitions": {
                    key: [doc["id"] for doc in value] for key, value in partition.items()
                },
                "models": rows,
                "role": "primary" if seed == 42 else "development robustness; no primary test",
            }
        )
    selected = selections[0]["winner"]
    baseline = selected.split("-")[0] + "-kneser_ney"
    registry.atomic_json(
        directory / "selection.json",
        {"selections": selections, "primary": selected, "baseline": baseline},
    )
    # Claim test before computing: interruption needs a fresh run, never silent retry.
    with (directory / "test.claim").open("x", encoding="utf-8") as claim:
        claim.write(digest(split["test"]))
    losses = {}
    metrics: list[dict[str, Any]] = []
    for name in dict.fromkeys((selected, baseline)):
        model = trained[name]
        save_model(
            directory / "models" / (name + ".json.gz"),
            model,
            {
                "run_id": run_id,
                "selection": "dev-only",
                "corpus_sha256": split_manifest["corpus_sha256"],
                "seed": 42,
                "collector_manifest_sha256": provenance["sha256"],
                "document_split": split_manifest,
                "tuning_source": f"tuning/42-{name}.json",
            },
        )
        losses[name] = document_losses(model, split["test"])
        registry.atomic_json(directory / f"test/{name}.json", losses[name])
        metrics.append(
            {
                "model": name,
                "role": "dev winner + KN baseline"
                if selected == baseline
                else "dev winner"
                if name == selected
                else "same-order KN baseline",
                **aggregate(losses[name]),
                "test_documents": len(split["test"]),
                "test_groups": len({d["split_group"] for d in split["test"]}),
                "mean_document_oov": sum(r["oov_rate"] for r in losses[name]) / len(losses[name]),
            }
        )
    result = {
        "selected": selected,
        "baseline": baseline,
        "metrics": metrics,
        "paired_bootstrap": paired_bootstrap(
            losses[selected], losses[baseline], seed=42, resamples=1000
        ),
        "selection_stability": [s["winner"] for s in selections],
        "interpretation": config["limitations"],
    }
    registry.atomic_json(directory / "summary.json", result)
    registry.complete_stage(run_id, "holdout")
    receipt = registry.read_run(run_id)
    output.mkdir(parents=True)
    for name in ("protocol.json", "selection.json", "summary.json"):
        registry.atomic_json(
            output / name, json.loads((directory / name).read_text(encoding="utf-8"))
        )
    tables: dict[str, list[dict[str, Any]]] = {
        "development.csv": [r for s in selections for r in s["models"]],
        "test_comparison.csv": metrics,
        "test_documents.csv": [
            {"model": name, **row} for name, rows in losses.items() for row in rows
        ],
    }
    for name, rows in tables.items():
        with (output / name).open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    registry.atomic_json(
        output / "manifest.json",
        {
            "status": "completed",
            "run_id": run_id,
            "source_files": receipt["files"],
            "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()},
        },
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.run_id, args.input, args.output)
    except (OSError, ValueError) as error:
        parser.exit(2, f"fresh holdout: {error}\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
