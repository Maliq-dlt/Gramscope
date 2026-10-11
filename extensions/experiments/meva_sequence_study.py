"""Bounded predictive study of MEVA public example activity annotations.

Clip timelines join simultaneous labels; they do not establish actor or causal order.
Run ``select`` before ``test`` so the held-out dates cannot select a model.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

from core.src.data import ROOT
from extensions.experiments import registry
from extensions.src.models import CountBank, ExtensionLM, evaluate_counts

SOURCE = ROOT / "industrial_ai/data/public/meva-examples-20261011-q1/normalized"
OUTPUT = ROOT / "extensions/results/meva_sequence_v1"
SPLIT_DATES = {
    "train": ("2018-03-07", "2018-03-09", "2018-03-11"),
    "dev": ("2018-03-12",),
    "test": ("2018-03-13", "2018-03-15"),
}
CANDIDATES = (
    ("unigram_wb", 1, "witten_bell"),
    ("bigram_wb", 2, "witten_bell"),
    ("bigram_kn", 2, "kneser_ney"),
    ("bigram_mkn", 2, "modified_kneser_ney"),
    ("trigram_wb", 3, "witten_bell"),
    ("trigram_kn", 3, "kneser_ney"),
    ("trigram_mkn", 3, "modified_kneser_ney"),
)
SELECTION_FILES = ("source_files.json", "counts.json", "selection.json", "dev_sequences.csv")
CODE_FILES = (
    Path(__file__),
    ROOT / "extensions/src/models.py",
    ROOT / "core/src/ngram.py",
    ROOT / "core/src/preprocess.py",
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files_and_hashes(source):
    source = Path(source).resolve()
    if not source.is_dir() or not source.is_relative_to(ROOT.resolve()):
        raise ValueError("Source must be a repository directory")
    files = sorted(source.glob("*.json"))
    dates = {path.stem[:10] for path in files}
    if len(files) != 64 or dates != set().union(*SPLIT_DATES.values()):
        raise ValueError("Expected the frozen 64-clip, six-date MEVA example set")
    if any(path.is_symlink() or not path.resolve().is_relative_to(source) for path in files):
        raise ValueError("Source JSON must be regular files inside source directory")
    return files, {path.relative_to(ROOT).as_posix(): sha256(path) for path in files}


def clip_tokens(record):
    """One token per change in active labels on disjoint inclusive frame segments."""
    # ponytail: clip order only; reviewed multi-event actor tracks are needed for actor transitions.
    activities = record["activities"]
    if not isinstance(activities, list) or not activities:
        raise ValueError("Clip needs annotated activities")
    spans: list[tuple[int, int, set[str]]] = []
    by_id = {}
    for activity in activities:
        identity, labels = activity["activity_id"], activity["labels"]
        if (
            type(identity) is not int
            or identity in by_id
            or not isinstance(labels, dict)
            or not labels
        ):
            raise ValueError("Invalid activity ID or labels")
        if any(
            not isinstance(label, str)
            or not label
            or type(weight) not in (int, float)
            or not math.isfinite(weight)
            or weight <= 0
            for label, weight in labels.items()
        ):
            raise ValueError("Activity labels need positive finite weights")
        by_id[identity] = labels
        for pair in activity["intervals"]:
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or any(type(frame) is not int or frame < 0 for frame in pair)
                or pair[1] < pair[0]
            ):
                raise ValueError("Invalid activity frame interval")
            spans.append((pair[0], pair[1], set(labels)))
    if not spans:
        raise ValueError("Clip needs activity intervals")
    actor_lengths = []
    for sequence in record["actor_sequences"]:
        events = sequence["events"]
        actor_lengths.append(len(events))
        for event in events:
            start, end = event["start_frame"], event["end_frame"]
            if (
                event["activity_id"] not in by_id
                or event["labels"] != by_id[event["activity_id"]]
                or type(start) is not int
                or type(end) is not int
                or not 0 <= start <= end
            ):
                raise ValueError("Actor event does not match clip activity")
    changes: defaultdict[int, Counter[str]] = defaultdict(Counter)
    for start, end, labels in spans:
        for label in labels:
            changes[start][label] += 1
            changes[end + 1][label] -= 1
    active: Counter[str] = Counter()
    tokens, cooccurrence_tokens = [], 0
    previous_token = None
    for frame in sorted(changes)[:-1]:
        for label, delta in changes[frame].items():
            count = active[label] + delta
            if count < 0:
                raise ValueError("Activity interval balance is invalid")
            if count:
                active[label] = count
            else:
                active.pop(label, None)
        if active:
            token = json.dumps(sorted(active), ensure_ascii=False, separators=(",", ":"))
            if previous_token != token:
                tokens.append(token)
                cooccurrence_tokens += len(active) > 1
            previous_token = token
        else:
            previous_token = None  # unlabeled gap separates episodes; not a negative event
    return tokens, {
        "activities": len(activities),
        "cooccurrence_tokens": cooccurrence_tokens,
        "actor_sequences": len(actor_lengths),
        "singleton_actor_sequences": sum(length == 1 for length in actor_lengths),
    }


def load_cases(files, dates):
    cases = []
    for path in files:
        if path.stem[:10] not in dates:
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["clip"] != path.stem:
            raise ValueError(f"Clip/file mismatch: {path.name}")
        tokens, quality = clip_tokens(record)
        cases.append({"clip": record["clip"], "date": path.stem[:10], "tokens": tokens, **quality})
    if not cases:
        raise ValueError("Split has no annotated clips")
    return cases


def models(bank):
    return {name: ExtensionLM(bank, order, method) for name, order, method in CANDIDATES}


def score_cases(cases, fitted):
    rows = []
    for name, model in fitted.items():
        for case in cases:
            tokens = case["tokens"]
            result = evaluate_counts(model, model.bank.event_counts([tokens], model.n))
            rows.append(
                {
                    "model": name,
                    "date": case["date"],
                    "clip": case["clip"],
                    "activities": case["activities"],
                    "state_tokens": len(tokens),
                    "cooccurrence_tokens": case["cooccurrence_tokens"],
                    "predicted_tokens": result["predicted_tokens"],
                    "oov_tokens": sum(token not in model.bank.vocab_set for token in tokens),
                    "cross_entropy": result["score_cross_entropy"],
                }
            )
    return rows


def aggregate(rows):
    count = sum(row["predicted_tokens"] for row in rows)
    return math.fsum(row["cross_entropy"] * row["predicted_tokens"] for row in rows) / count


def write_csv(path, rows):
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def select(source=SOURCE, output=OUTPUT):
    files, source_hashes = files_and_hashes(source)
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT.resolve()) or output.is_relative_to(Path(source).resolve()):
        raise ValueError("Output must be inside repository and outside source")
    train = load_cases(files, SPLIT_DATES["train"])
    dev = load_cases(files, SPLIT_DATES["dev"])
    bank = CountBank([case["tokens"] for case in train], max_n=3, min_count=1)
    fitted = models(bank)
    dev_rows = score_cases(dev, fitted)
    trials = [
        {
            "model": name,
            "dev_cross_entropy": aggregate([row for row in dev_rows if row["model"] == name]),
        }
        for name in fitted
    ]
    winner = min(trials, key=lambda row: (row["dev_cross_entropy"], row["model"]))["model"]
    output.mkdir(parents=True)  # exclusive; never overwrite a selection or test receipt
    registry.atomic_json(output / "source_files.json", source_hashes)
    registry.atomic_json(
        output / "counts.json",
        {
            "min_count": 1,
            "vocabulary": bank.vocabulary,
            "orders": {
                str(n): [[list(gram), count] for gram, count in sorted(bank.raw[n].items())]
                for n in (1, 2, 3)
            },
        },
    )
    registry.atomic_json(
        output / "selection.json",
        {
            "split_dates": SPLIT_DATES,
            "criterion": "minimum token-weighted development cross-entropy; name breaks ties",
            "winner": winner,
            "trials": trials,
            "train_clips": len(train),
            "train_state_tokens": sum(len(case["tokens"]) for case in train),
            "dev_clips": len(dev),
            "dev_state_tokens": sum(len(case["tokens"]) for case in dev),
            "train_singleton_actor_sequences": sum(
                case["singleton_actor_sequences"] for case in train
            ),
            "train_actor_sequences": sum(case["actor_sequences"] for case in train),
        },
    )
    write_csv(output / "dev_sequences.csv", dev_rows)
    registry.atomic_json(
        output / "manifest.json",
        {
            "schema": 1,
            "status": "selected",
            "dataset": "MEVA public example activity annotations; CC BY 4.0",
            "license_url": "https://mevadata.org/resources/MEVA-data-license.txt",
            "unit": (
                "clip-level disjoint frame states; labels co-occur only while intervals "
                "intersect, and adjacent equal states collapse"
            ),
            "winner": winner,
            "code": {path.relative_to(ROOT).as_posix(): sha256(path) for path in CODE_FILES},
            "files": {name: sha256(output / name) for name in SELECTION_FILES},
        },
    )
    return winner


def test(source=SOURCE, output=OUTPUT):
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT.resolve()) or output.is_symlink():
        raise ValueError("Output must be a repository directory")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "selected" or set(manifest["files"]) != set(SELECTION_FILES):
        raise ValueError("Test requires a frozen development selection")
    if manifest["code"] != {path.relative_to(ROOT).as_posix(): sha256(path) for path in CODE_FILES}:
        raise ValueError("Study/model implementation changed after selection")
    if any(
        (output / name).is_symlink()
        or not (output / name).resolve().is_relative_to(output)
        or sha256(output / name) != digest
        for name, digest in manifest["files"].items()
    ):
        raise ValueError("Frozen selection artifact changed")
    if (output / "test_sequences.csv").exists() or (output / "test_dates.json").exists():
        raise FileExistsError("Held-out results already exist")
    files, source_hashes = files_and_hashes(source)
    if source_hashes != json.loads((output / "source_files.json").read_text(encoding="utf-8")):
        raise ValueError("Source annotations changed after selection")
    selection = json.loads((output / "selection.json").read_text(encoding="utf-8"))
    if selection["winner"] != manifest["winner"] or selection["split_dates"] != {
        key: list(value) for key, value in SPLIT_DATES.items()
    }:
        raise ValueError("Selection protocol changed")
    saved = json.loads((output / "counts.json").read_text(encoding="utf-8"))
    bank = CountBank.from_counts(
        saved["vocabulary"],
        {
            int(n): Counter({tuple(gram): count for gram, count in rows})
            for n, rows in saved["orders"].items()
        },
        saved["min_count"],
    )
    heldout = {
        name: digest
        for name, digest in source_hashes.items()
        if Path(name).stem[:10] in SPLIT_DATES["test"]
    }
    fingerprint = registry.fingerprint(heldout)
    claims = ROOT / ".tmp/meva-sequence-test-claims"
    claims.mkdir(parents=True, exist_ok=True)
    with (claims / (fingerprint + ".json")).open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "source_sha256": fingerprint,
                "selection_sha256": sha256(output / "selection.json"),
                "policy": "one test claim per annotation corpus, including interruptions",
            },
            stream,
        )
    with (output / "test.claim").open("x", encoding="utf-8") as stream:
        stream.write(fingerprint)
    test_rows = score_cases(load_cases(files, SPLIT_DATES["test"]), models(bank))
    dates = []
    for name, _, _ in CANDIDATES:
        for date in SPLIT_DATES["test"]:
            group = [row for row in test_rows if row["model"] == name and row["date"] == date]
            rng = random.Random(int(hashlib.sha256(f"{name}/{date}".encode()).hexdigest()[:16], 16))
            boot = sorted(
                aggregate([group[rng.randrange(len(group))] for _ in group]) for _ in range(1000)
            )
            dates.append(
                {
                    "model": name,
                    "date": date,
                    "clips": len(group),
                    "state_tokens": sum(row["state_tokens"] for row in group),
                    "predicted_tokens": sum(row["predicted_tokens"] for row in group),
                    "oov_tokens": sum(row["oov_tokens"] for row in group),
                    "cross_entropy": aggregate(group),
                    "within_date_clip_bootstrap_p05_p95_descriptive": [boot[50], boot[949]],
                }
            )
    write_csv(output / "test_sequences.csv", test_rows)
    registry.atomic_json(
        output / "test_dates.json",
        {
            "winner": selection["winner"],
            "dates": dates,
            "interpretation": (
                "Two held-out dates and sparse activity labels; bootstrap describes clips "
                "within each date, not a population confidence interval. No incident/novelty "
                "truth, recall, precision, actor continuity, or camera generalization claim."
            ),
        },
    )
    manifest["status"] = "evaluated"
    manifest["files"].update(
        {
            name: sha256(output / name)
            for name in ("test_sequences.csv", "test_dates.json", "test.claim")
        }
    )
    registry.atomic_json(output / "manifest.json", manifest)
    return selection["winner"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("select", "test"))
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        winner = (
            select(args.source, args.output)
            if args.stage == "select"
            else test(args.source, args.output)
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"MEVA sequence study: {error}\n")
    print(f"{args.stage}: {winner} -> {args.output}")


if __name__ == "__main__":
    main()
