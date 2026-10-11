"""Larger grouped language study and matched-probe sibling-exposure diagnostic."""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from importlib.metadata import version
from pathlib import Path

import numpy as np

from core.src.data import ROOT
from core.src.ngram import events
from core.src.preprocess import BOS, fit_vocabulary
from extensions.experiments import registry
from extensions.src.analytics import aggregate, document_losses, paired_bootstrap
from extensions.src.datasets import (
    digest,
    nltk_documents,
    read_documents,
    sentences,
    split_documents,
)
from extensions.src.models import CountBank, ExtensionLM
from extensions.src.pipeline import tune

SPECS = (
    (1, "kneser_ney"),
    (2, "kneser_ney"),
    (3, "kneser_ney"),
    (2, "modified_kneser_ney"),
    (3, "modified_kneser_ney"),
)
SEEDS = (42, 43, 44)
METHOD_PRIORITY = {"kneser_ney": 0, "modified_kneser_ney": 1}


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_csv(path, rows):
    if not rows:
        raise ValueError("Cannot export an empty table")
    with Path(path).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def group_se(rows, seed=42, resamples=1000):
    """Bootstrap SE of token-weighted dev CE, clustered by duplicate/source group."""
    grouped = defaultdict(lambda: [0.0, 0])
    for row in rows:
        grouped[row["group_id"]][0] += row["nll"]
        grouped[row["group_id"]][1] += row["predicted_tokens"]
    if len(grouped) < 2:
        raise ValueError("One-SE requires at least two development groups")
    values = np.array(list(grouped.values()), dtype=float)
    if not np.isfinite(values).all() or (values[:, 1] <= 0).any():
        raise ValueError("Finite positive development losses required")
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(resamples):
        selected = values[rng.integers(0, len(values), len(values))]
        samples.append(float(selected[:, 0].sum() / selected[:, 1].sum()))
    return float(np.std(samples, ddof=1))


def select_one_se(rows, best_se):
    if not rows or not math.isfinite(best_se) or best_se < 0:
        raise ValueError("Finite nonnegative SE required")
    if any(not math.isfinite(row["dev_ce_nats"]) for row in rows):
        raise ValueError("Nonfinite development selection")
    best = min(rows, key=lambda r: (r["dev_ce_nats"], r["model"]))
    ceiling = best["dev_ce_nats"] + best_se
    eligible = [r for r in rows if r["dev_ce_nats"] <= ceiling]
    chosen = min(
        eligible, key=lambda r: (r["n"], METHOD_PRIORITY[r["method"]], r["dev_ce_nats"], r["model"])
    )
    return {
        "minimum_dev": best["model"],
        "one_se": chosen["model"],
        "best_se_nats": best_se,
        "ceiling_nats": ceiling,
        "eligible": [r["model"] for r in eligible],
    }


def development_partition(split, seed):
    if seed == 42:
        return {k: split[k] for k in ("train", "dev")}
    groups = defaultdict(list)
    for doc in split["train"] + split["dev"]:
        groups[doc["split_group"]].append(doc)
    keys = sorted(groups)
    random.Random(seed).shuffle(keys)
    cut = len({d["split_group"] for d in split["train"]})
    return {
        name: [d for key in subset for d in groups[key]]
        for name, subset in (("train", keys[:cut]), ("dev", keys[cut:]))
    }


def split_audit(split):
    result = {}
    for name, docs in split.items():
        counts = Counter()
        for doc in docs:
            counts[doc["split_group"]] += sum(len(s) + 1 for s in doc["sentences"])
        total = sum(counts.values())
        result[name] = {
            "documents": len(docs),
            "groups": len(counts),
            "sentences": sum(len(d["sentences"]) for d in docs),
            "predicted_tokens": total,
            "largest_group_token_fraction": max(counts.values()) / total,
            "effective_groups_by_token_weight": total**2 / sum(x * x for x in counts.values()),
        }
    return result


def budget_subset(pool, budget, seed):
    """Select whole sentences without scores, keeping EOS events in the budget."""
    if type(budget) is not int or budget < 1:
        raise ValueError("Positive integer event budget required")
    indices = list(range(len(pool)))
    random.Random(seed).shuffle(indices)
    chosen, remaining = [], budget
    for i in indices:
        size = len(pool[i]) + 1
        if size <= remaining:
            chosen.append(i)
            remaining -= size
        if not remaining:
            break
    return [pool[i] for i in chosen], set(chosen), remaining


def probe_design(split):
    rng = random.Random(314159)
    probes, siblings = [], []
    for doc in sorted(split["test"], key=lambda d: d["id"]):
        if len(doc["sentences"]) < 2:
            continue
        index = rng.randrange(len(doc["sentences"]))
        probes.append({**doc, "sentences": [doc["sentences"][index]]})
        siblings.extend(s for i, s in enumerate(doc["sentences"]) if i != index)
    if len(probes) < 2:
        raise ValueError("Need at least two eligible probe documents")
    exact = {tuple(d["sentences"][0]) for d in probes}
    siblings = [s for s in siblings if tuple(s) not in exact]
    strict = [s for s in sentences(split["train"]) if tuple(s) not in exact]
    # ponytail: fixed whole-sentence budgets; add exact knapsack only if residual is material.
    fill_budget = int(
        min(sum(len(s) + 1 for s in strict) / 5, sum(len(s) + 1 for s in siblings) * 0.8)
    )
    if fill_budget < 100:
        raise ValueError("Insufficient sibling/control event budget")
    base, used, base_residual = budget_subset(strict, 2 * fill_budget, 161803)
    control_pool = [s for i, s in enumerate(strict) if i not in used]
    arms, audit = {}, []
    for seed in SEEDS:
        for arm, pool, offset in (
            ("strict", control_pool, 0),
            ("strict_resample", control_pool, 1000),
            ("sibling_exposure", siblings, 2000),
        ):
            fill, _, residual = budget_subset(pool, fill_budget, seed + offset)
            if residual > max(20, fill_budget // 1000):
                raise ValueError("Whole-sentence budget residual exceeds prespecified tolerance")
            train = base + fill
            if any(tuple(s) in exact for s in train):
                raise AssertionError("Exact probe leaked into training")
            arms[(seed, arm)] = train
            audit.append(
                {
                    "seed": seed,
                    "arm": arm,
                    "base_event_budget": 2 * fill_budget,
                    "base_residual": base_residual,
                    "fill_event_budget": fill_budget,
                    "fill_residual": residual,
                    "sentences": len(train),
                    "predicted_tokens": sum(len(s) + 1 for s in train),
                    "train_sha256": digest(train),
                    "exact_probe_matches": 0,
                }
            )
    return probes, arms, audit


def frozen_bank(train, vocabulary):
    mapped = [[w if w in vocabulary else "<UNK>" for w in s] for s in train]
    raw = {n: Counter(g for s in mapped for g in events(s, n)) for n in range(1, 4)}
    return CountBank.from_counts(sorted(vocabulary), raw, min_count=2)


def average_seed_losses(rows, model, arm):
    grouped = defaultdict(list)
    for row in rows:
        if row["model"] == model and row["arm"] == arm:
            grouped[row["id"]].append(row)
    result = []
    for items in grouped.values():
        if len(items) != len(SEEDS) or len({i["predicted_tokens"] for i in items}) != 1:
            raise ValueError("All training seeds must score the same target once")
        result.append(
            {k: v for k, v in items[0].items() if k not in ("seed", "arm", "model")}
            | {"nll": math.fsum(i["nll"] for i in items) / len(items)}
        )
    return result


def sentence_split_design(split):
    """Freeze descriptive split comparison with vocab fit on shared train occurrences only."""
    records = [
        dict(d, id=d["id"] + ":sentence:" + str(i), parent_id=d["id"], sentences=[sentence])
        for docs in split.values()
        for d in sorted(docs, key=lambda x: x["id"])
        for i, sentence in enumerate(d["sentences"])
    ]
    strict_ids = {d["id"] for d in split["train"]}
    designs, audits = {}, []
    for seed in SEEDS:
        indices = list(range(len(records)))
        random.Random(seed).shuffle(indices)
        cut1, cut2 = int(len(indices) * 0.8), int(len(indices) * 0.9)
        random_train = [records[i] for i in indices[:cut1]]
        random_test = [records[i] for i in indices[cut2:]]
        common = [d["sentences"][0] for d in random_train if d["parent_id"] in strict_ids]
        vocabulary, _ = fit_vocabulary(common, 2)
        vocabulary.discard(BOS)
        train_parents = {d["parent_id"] for d in random_train}
        overlap = sum(d["parent_id"] in train_parents for d in random_test)
        designs[seed] = {
            "vocabulary": vocabulary,
            "arms": {
                "document": (sentences(split["train"]), split["test"]),
                "random_sentence": (sentences(random_train), random_test),
            },
        }
        audits.append(
            {
                "seed": seed,
                "random_train_sha256": digest(random_train),
                "random_test_sha256": digest(random_test),
                "common_train_sha256": digest(common),
                "vocabulary_size": len(vocabulary),
                "vocabulary_sha256": digest(sorted(vocabulary)),
                "random_test_sentences": len(random_test),
                "random_test_with_train_siblings": overlap,
                "vocabulary_policy": "min_count2 fitted on intersection of train occurrences",
                "dev_usage": "unused; fixed KN3 D=.75 and MKN3",
                "comparison": "descriptive; targets differ, no paired causal delta",
            }
        )
    return designs, audits


def load_corpus(name, input_path=None):
    if name in ("brown", "reuters"):
        docs = nltk_documents(name)
        archive = ROOT / "data/nltk_data/corpora" / (name + ".zip")
        provenance = {
            "archive": str(archive.relative_to(ROOT)),
            "archive_sha256": sha(archive),
            "exposure": "previous project corpus; expanded exploratory study",
            "split": "grouped rerandomization; not official Reuters train/test",
        }
    elif name == "idwiki" and input_path is not None:
        path = Path(input_path).resolve()
        if not path.is_relative_to(ROOT.resolve()):
            raise ValueError("Input must stay inside repository")
        docs = read_documents(path)
        manifest_path = path.with_name("manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["jsonl_sha256"] != sha(path) or manifest["documents_sha256"] != digest(docs):
            raise ValueError("Corpus snapshot fingerprint mismatch")
        from extensions.experiments.prepare_academic_corpora import CONFIG, DATASET, REVISION

        source = manifest.get("source", {})
        if (
            manifest.get("format") != "academic-idwiki-full-v1"
            or source.get("dataset") != DATASET
            or source.get("config") != CONFIG
            or source.get("repository_revision") != REVISION
            or len(docs) != manifest.get("documents")
            or {d["id"] for d in docs} & set(manifest["historical_exposure"]["excluded_ids"])
        ):
            raise ValueError("Requires the full-article snapshot with historical exclusion")
        provenance = {
            "path": str(path.relative_to(ROOT)),
            "sha256": sha(path),
            "manifest_sha256": sha(manifest_path),
            "source": source,
            "selection": manifest["selection"],
            "snapshot_limit": manifest["snapshot_limit"],
            "preprocessing": manifest["preprocessing"],
            "tokens": manifest["tokens"],
        }
    else:
        raise ValueError("Choose brown, reuters or idwiki with input")
    if any(not w.isalpha() or w != w.lower() for d in docs for s in d["sentences"] for w in s):
        raise ValueError("Fixed lowercase alphabetic preprocessing required")
    return docs, provenance


def run(run_id, name, output, input_path=None):
    output = Path(output).resolve()
    if (
        output.exists()
        or not output.is_relative_to(ROOT.resolve())
        or output.is_relative_to(registry.RUNS.resolve())
    ):
        raise ValueError("Use a fresh repository output outside registry")
    registry.run_directory(run_id)
    docs, provenance = load_corpus(name, input_path)
    split, split_manifest = split_documents(docs)
    audit = split_audit(split)
    if any(audit[k]["groups"] < 20 for k in ("dev", "test")):
        raise ValueError("Need >=20 independent dev/test groups")
    probes, arms, budget_audit = probe_design(split)
    sentence_designs, sentence_audit = sentence_split_design(split)
    code = (
        "extensions/experiments/academic_upgrade.py",
        "extensions/src/models.py",
        "extensions/src/pipeline.py",
        "extensions/src/datasets.py",
        "extensions/src/analytics.py",
        "extensions/experiments/registry.py",
        "core/src/ngram.py",
        "core/src/preprocess.py",
    )
    config = {
        "experiment": "academic-evidence-upgrade-v2",
        "corpus": name,
        "corpus_sha256": digest(docs),
        "provenance": provenance,
        "split": split_manifest,
        "split_audit": audit,
        "models": SPECS,
        "min_count": 2,
        "seeds": SEEDS,
        "selection": "minimum dev CE + bootstrap one-SE simplest order then ordinary KN",
        "one_se_bootstrap": {"resamples": 1000, "seed": 42, "unit": "split_group"},
        "test_contrasts": "one-SE/minimum-dev/same-order KN + prespecified KN3/MKN3, deduplicated",
        "probe": {
            "seed": 314159,
            "documents": len(probes),
            "sha256": digest(probes),
            "budget": budget_audit,
            "base_seed": 161803,
            "vocabulary": "primary strict full train only, identical across all arms",
            "models": ["3-kneser_ney D=.75", "3-modified_kneser_ney"],
            "estimand": "token-weighted probe CE with seed-averaged losses; group bootstrap",
            "design": "same base + matched whole-sentence fills, sibling vs strict/control",
            "limitations": "exposure diagnostic, not causal random-split bias estimate",
        },
        "sentence_split_diagnostic": sentence_audit,
        "versions": {n: version(n) for n in ("nltk", "numpy")},
        "code_sha256": {n: sha(ROOT / n) for n in code},
        "interpretation": (
            "established methods; no journal-rank guarantee; conditional corpus evidence"
        ),
    }
    directory = registry.create_run(run_id, config)
    registry.start_stage(run_id, "language", config)
    registry.atomic_json(directory / "protocol.json", config)
    registry.atomic_json(directory / "probe_targets.json", probes)
    selections, all_dev, parameters = [], [], {}
    for seed in SEEDS:
        partition = development_partition(split, seed)
        bank = CountBank(sentences(partition["train"]), max_n=3, min_count=2)
        dev_counts = {n: bank.event_counts(sentences(partition["dev"]), n) for n in range(1, 4)}
        rows, dev_losses = [], {}
        for n, method in SPECS:
            model, winner, trials = tune(bank, n, method, dev_counts[n])
            key = f"{n}-{method}"
            losses = document_losses(model, partition["dev"])
            row = {
                "seed": seed,
                "model": key,
                "n": n,
                "method": method,
                "dev_ce_nats": aggregate(losses)["cross_entropy"],
                "vocabulary_size": len(bank.vocabulary),
            }
            rows.append(row)
            dev_losses[key] = losses
            registry.atomic_json(
                directory / f"tuning/{seed}-{key}.json",
                {"winner": winner, "trials": trials, "discounts": model.mkn_discounts},
            )
            if seed == 42:
                parameters[key] = winner["parameters"]
            del model
        best = min(rows, key=lambda r: (r["dev_ce_nats"], r["model"]))
        selection = select_one_se(rows, group_se(dev_losses[best["model"]]))
        selections.append(
            {
                "seed": seed,
                **selection,
                "partition_ids": {k: [d["id"] for d in v] for k, v in partition.items()},
            }
        )
        all_dev.extend(rows)
        del bank, dev_counts, dev_losses
        gc.collect()
        print(
            json.dumps(
                {
                    "phase": "dev",
                    "corpus": name,
                    **{k: selection[k] for k in ("one_se", "minimum_dev")},
                    "seed": seed,
                }
            ),
            flush=True,
        )
    primary = selections[0]
    same_order = primary["one_se"].split("-")[0] + "-kneser_ney"
    selected = list(
        dict.fromkeys(
            [
                primary["one_se"],
                primary["minimum_dev"],
                same_order,
                "3-kneser_ney",
                "3-modified_kneser_ney",
            ]
        )
    )
    registry.atomic_json(
        directory / "selection.json",
        {"selections": selections, "test_models": selected, "parameters": parameters},
    )
    with (directory / "test.claim").open("x", encoding="utf-8") as stream:
        stream.write(digest(split["test"]))
    bank = CountBank(sentences(split["train"]), max_n=3, min_count=2)
    losses, metrics = {}, []
    for key in selected:
        n, method = key.split("-", 1)
        model = ExtensionLM(bank, int(n), method, **parameters[key])
        losses[key] = document_losses(model, split["test"])
        metrics.append(
            {
                "model": key,
                **aggregate(losses[key]),
                "test_documents": len(split["test"]),
                "test_groups": audit["test"]["groups"],
            }
        )
        registry.atomic_json(directory / f"test/{key}.json", losses[key])
        del model
    comparisons = {
        "MKN3_minus_KN3": paired_bootstrap(losses["3-modified_kneser_ney"], losses["3-kneser_ney"]),
        "oneSE_minus_minDev": paired_bootstrap(
            losses[primary["one_se"]], losses[primary["minimum_dev"]]
        ),
        "oneSE_minus_sameOrderKN": paired_bootstrap(losses[primary["one_se"]], losses[same_order]),
    }
    summary = {
        "corpus": name,
        "split_audit": audit,
        "selections": selections,
        "test_metrics": metrics,
        "paired_bootstrap": comparisons,
    }
    registry.atomic_json(directory / "language_summary.json", summary)
    del bank, losses
    gc.collect()
    registry.complete_stage(run_id, "language")
    registry.start_stage(run_id, "probe", config)
    vocabulary, _ = fit_vocabulary(sentences(split["train"]), 2)
    vocabulary.discard(BOS)
    all_probe, probe_metrics = [], []
    for (seed, arm), train in arms.items():
        bank = frozen_bank(train, vocabulary)
        for method in ("kneser_ney", "modified_kneser_ney"):
            model = ExtensionLM(bank, 3, method, discount=0.75)
            rows = document_losses(model, probes)
            key = "3-" + method
            all_probe.extend({"seed": seed, "arm": arm, "model": key, **r} for r in rows)
            probe_metrics.append({"seed": seed, "arm": arm, "model": key, **aggregate(rows)})
            del model
        del bank
        gc.collect()
    probe_comparisons = {}
    for method in ("kneser_ney", "modified_kneser_ney"):
        key = "3-" + method
        strict = average_seed_losses(all_probe, key, "strict")
        for arm in ("sibling_exposure", "strict_resample"):
            other = average_seed_losses(all_probe, key, arm)
            probe_comparisons[key + ":" + arm + "_minus_strict"] = paired_bootstrap(other, strict)
    registry.atomic_json(
        directory / "probe_summary.json",
        {
            "metrics": probe_metrics,
            "paired_bootstrap": probe_comparisons,
            "budget_audit": budget_audit,
            "probe_documents": len(probes),
            "probe_groups": len({d["split_group"] for d in probes}),
            "vocabulary_size": len(vocabulary),
            "vocabulary_sha256": digest(sorted(vocabulary)),
        },
    )
    write_csv(directory / "development.csv", all_dev)
    write_csv(directory / "test_comparison.csv", metrics)
    write_csv(directory / "probe_metrics.csv", probe_metrics)
    write_csv(directory / "probe_documents.csv", all_probe)
    write_csv(directory / "probe_budget.csv", budget_audit)
    registry.complete_stage(run_id, "probe")
    registry.start_stage(run_id, "sentence_split", config)
    split_metrics, split_rows = [], []
    for seed, design in sentence_designs.items():
        for arm, (train, test) in design["arms"].items():
            bank = frozen_bank(train, design["vocabulary"])
            for method in ("kneser_ney", "modified_kneser_ney"):
                model = ExtensionLM(bank, 3, method, discount=0.75)
                rows = document_losses(model, test)
                key = "3-" + method
                split_rows.extend({"seed": seed, "arm": arm, "model": key, **r} for r in rows)
                split_metrics.append(
                    {
                        "seed": seed,
                        "arm": arm,
                        "model": key,
                        **aggregate(rows),
                        "evaluation_units": len(rows),
                        "groups": len({r["group_id"] for r in rows}),
                        "mean_unit_oov_rate": math.fsum(r["oov_rate"] for r in rows) / len(rows),
                    }
                )
                del model
            del bank
            gc.collect()
    write_csv(directory / "sentence_split_metrics.csv", split_metrics)
    write_csv(directory / "sentence_split_losses.csv", split_rows)
    registry.atomic_json(
        directory / "sentence_split_summary.json",
        {
            "metrics": split_metrics,
            "design": sentence_audit,
            "limitations": (
                "Different targets/training distributions; descriptive, no causal paired CI"
            ),
        },
    )
    registry.complete_stage(run_id, "sentence_split")
    receipt = registry.read_run(run_id)
    output.mkdir(parents=True)
    names = (
        "protocol.json",
        "selection.json",
        "language_summary.json",
        "probe_summary.json",
        "development.csv",
        "test_comparison.csv",
        "probe_metrics.csv",
        "probe_documents.csv",
        "probe_budget.csv",
        "sentence_split_metrics.csv",
        "sentence_split_losses.csv",
        "sentence_split_summary.json",
    )
    for filename in names:
        with (output / filename).open("xb") as stream:
            stream.write((directory / filename).read_bytes())
    registry.atomic_json(
        output / "manifest.json",
        {
            "status": "completed",
            "run_id": run_id,
            "source_files": receipt["files"],
            "files": {n: sha(output / n) for n in names},
        },
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", choices=("brown", "reuters", "idwiki"), required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.run_id, args.corpus, args.output, args.input)
    except (OSError, ValueError) as error:
        parser.exit(2, f"academic study: {error}\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
