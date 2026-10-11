"""Bounded N-gram CLI, versioned checkpoints and artifact-bound evaluation receipts."""

import argparse
import gzip
import hashlib
import io
import json
import math
import os
import sys
import uuid
from collections import Counter
from pathlib import Path

import yaml

from core.src.data import ROOT, load_corpus, set_seed
from core.src.preprocess import preprocess, tokenize
from extensions.src.models import ALL_METHODS, METHODS, CountBank, ExtensionLM, evaluate_counts
from extensions.src.pipeline import split_three, tune
from extensions.src.quality import Sampler

ALGORITHM_VERSION = "extensions-smoothing-v2"
PREPROCESS_VERSION = "alphabetic-lower-wordpunct-v1"
MAX_CHECKPOINT = 512 * 2**20
MAX_METADATA = 2 * 2**20
MAX_LINE = 64 * 2**10
MAX_INPUT = 64 * 2**20
PARAMETERS = {"k", "discount", "weights", "backoff", "epsilon"}
BASE_SCHEMA = {
    "format_version",
    "metadata",
    "n",
    "method",
    "parameters",
    "min_count",
    "vocabulary",
    "counts",
}
PROVENANCE_SCHEMA = {"corpus_sha256", "split_sha256", "vocabulary_sha256", "tuning_sha256"}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _json(content):
    return json.loads(
        content.decode("utf-8") if isinstance(content, bytes) else content,
        object_pairs_hook=_object,
        parse_constant=lambda value: _invalid(value),
    )


def _invalid(value):
    raise ValueError(f"Nilai JSON tidak finite: {value}")


def _encoded(value):
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_encoded(value)).hexdigest()


def _hash_file(path):
    digest, size = hashlib.sha256(), 0
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(2**20), b""):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def _output(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Output/cache harus berada di repository")
    return path


def _sidecar(path):
    return Path(path).with_name(Path(path).name + ".meta.json")


def _bounded_json(path, limit=MAX_METADATA):
    with Path(path).open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Metadata melebihi batas ukuran")
    return _json(data)


def _hex(value):
    return (
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    )


def _metadata(metadata, *, legacy=False):
    if not isinstance(metadata, dict) or len(_encoded(metadata)) > MAX_METADATA - 4096:
        raise ValueError("Metadata harus object dan dibatasi 2 MiB")
    if legacy:
        return metadata
    if "split" in metadata and "document_split" in metadata:
        raise ValueError("Metadata hanya boleh memiliki satu kebijakan split")
    if "document_split" in metadata:
        split = metadata["document_split"]
        if (
            not isinstance(split, dict)
            or set(split) != {"policy", "seed", "corpus_sha256", "groups", "ids"}
            or split["policy"] != "document-exact-sentence-and-5gram-jaccard-0.9-v1"
            or type(split["seed"]) is not int
            or not 0 <= split["seed"] < 2**32
            or not _hex(split["corpus_sha256"])
            or not isinstance(split["ids"], dict)
            or set(split["ids"]) != {"train", "dev", "test"}
            or not isinstance(split["groups"], list)
        ):
            raise ValueError("Schema document split tidak valid")
        owner = {}
        for name, values in split["ids"].items():
            if (
                not isinstance(values, list)
                or not values
                or any(not isinstance(value, str) or not value for value in values)
                or len(set(values)) != len(values)
                or any(value in owner for value in values)
            ):
                raise ValueError("Document split IDs invalid/overlap")
            owner.update(dict.fromkeys(values, name))
        grouped = set()
        for group in split["groups"]:
            if (
                not isinstance(group, list)
                or not group
                or any(not isinstance(value, str) or value not in owner for value in group)
                or len(set(group)) != len(group)
                or grouped.intersection(group)
                or len({owner[value] for value in group}) != 1
            ):
                raise ValueError("Document groups invalid/overlap/leakage")
            grouped.update(group)
        if grouped != set(owner):
            raise ValueError("Document groups tidak mencakup split")
        if (
            metadata.get("corpus_sha256") != split["corpus_sha256"]
            or metadata.get("seed") != split["seed"]
        ):
            raise ValueError("Document split corpus/seed tidak cocok")
    for key in ("corpus_sha256",):
        if key in metadata and not _hex(metadata[key]):
            raise ValueError(f"Fingerprint {key} tidak valid")
    if "corpus" in metadata and metadata["corpus"] not in ("brown", "reuters"):
        raise ValueError("Corpus metadata tidak valid")
    if "seed" in metadata and (
        type(metadata["seed"]) is not int or not 0 <= metadata["seed"] < 2**32
    ):
        raise ValueError("Seed metadata tidak valid")
    if "split" in metadata:
        split = metadata["split"]
        if (
            not isinstance(split, dict)
            or set(split) != {"strategy", "ids", "fingerprints"}
            or split["strategy"] != "sentence-80-10-10-v1"
        ):
            raise ValueError("Schema split tidak valid")
        ids, fingerprints = split["ids"], split["fingerprints"]
        keys = {"train", "dev", "test"}
        if (
            not isinstance(ids, dict)
            or set(ids) != keys
            or not isinstance(fingerprints, dict)
            or set(fingerprints) != keys
            or any(not _hex(value) for value in fingerprints.values())
        ):
            raise ValueError("Fingerprint/ID split tidak valid")
        seen = set()
        for values in ids.values():
            if (
                not isinstance(values, list)
                or not values
                or any(type(value) is not int or value < 0 for value in values)
                or len(set(values)) != len(values)
                or seen.intersection(values)
            ):
                raise ValueError("ID split invalid/overlap")
            seen.update(values)
        if seen != set(range(len(seen))):
            raise ValueError("Split tidak mencakup corpus")
    if "tuning_trace" in metadata:
        trace = metadata["tuning_trace"]
        if not isinstance(trace, list) or len(trace) > 10_000:
            raise ValueError("Jejak tuning tidak valid")
        for trial in trace:
            if (
                not isinstance(trial, dict)
                or not {"parameters", "dev_loss"} <= set(trial)
                or set(trial) - {"parameters", "dev_loss", "em_trace"}
                or not isinstance(trial["parameters"], dict)
                or set(trial["parameters"]) - PARAMETERS
                or type(trial["dev_loss"]) not in (int, float)
                or not math.isfinite(trial["dev_loss"])
            ):
                raise ValueError("Schema trial tuning tidak valid")
    return metadata


def read_config(path):
    with Path(path).open("rb") as stream:
        content = stream.read(MAX_LINE + 1)
    if len(content) > MAX_LINE:
        raise ValueError("Config melebihi 64 KiB")
    config = yaml.safe_load(content.decode("utf-8"))
    allowed = {"corpus", "seed", "n", "method", "min_count"}
    if not isinstance(config, dict) or set(config) != allowed:
        raise ValueError(f"Config wajib tepat key {sorted(allowed)}")
    if config["corpus"] not in ("brown", "reuters") or config["method"] not in ALL_METHODS:
        raise ValueError("Corpus/metode config tidak valid")
    for key in ("n", "min_count", "seed"):
        if type(config[key]) is not int:
            raise ValueError(f"{key} harus integer")
    if not 1 <= config["n"] <= 4 or config["min_count"] < 1 or not 0 <= config["seed"] < 2**32:
        raise ValueError("n 1..4; min_count>=1; seed uint32")
    return config


def _split_digest(metadata):
    for key in ("split", "document_split"):
        if key in metadata:
            return _digest(metadata[key])
    return None


def _summary(payload):
    return {
        "format_version": payload["format_version"],
        "algorithm_version": payload.get("algorithm_version", "extensions-smoothing-v1"),
        "preprocess_version": payload.get("preprocess_version", PREPROCESS_VERSION),
        "n": payload["n"],
        "method": payload["method"],
        "min_count": payload["min_count"],
        "vocabulary_size": len(payload["vocabulary"]),
        "metadata": payload["metadata"],
        "provenance": payload.get("provenance"),
    }


def _commit_json(path, value):
    path = _output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(_encoded(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def save_model(path, model, metadata, format_version=2):
    path = _output(path)
    sidecar = _sidecar(path)
    if type(format_version) is not int or format_version not in (1, 2):
        raise ValueError("Format checkpoint harus 1 atau 2")
    if model.method not in (METHODS if format_version == 1 else ALL_METHODS):
        raise ValueError("Metode baru membutuhkan checkpoint v2")
    _metadata(metadata, legacy=format_version == 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    with lock.open("xb"):
        pass
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    committed = False
    try:
        if path.exists() or sidecar.exists():
            raise FileExistsError(f"Checkpoint/metadata sudah ada: {path}")
        payload = {
            "format_version": format_version,
            "metadata": metadata,
            "n": model.n,
            "method": model.method,
            "parameters": {key: getattr(model, key) for key in sorted(PARAMETERS)},
            "min_count": model.bank.min_count,
            "vocabulary": sorted(model.vocabulary),
            "counts": {
                str(n): [[gram, count] for gram, count in sorted(counts.items())]
                for n, counts in sorted(model.bank.raw.items())
            },
        }
        if format_version == 2:
            payload.update(
                algorithm_version=ALGORITHM_VERSION,
                preprocess_version=PREPROCESS_VERSION,
                provenance={
                    "corpus_sha256": metadata.get("corpus_sha256"),
                    "split_sha256": _split_digest(metadata),
                    "vocabulary_sha256": _digest(payload["vocabulary"]),
                    "tuning_sha256": _digest(metadata.get("tuning_trace", [])),
                },
            )
        with temporary.open("xb") as raw:
            with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
                with io.TextIOWrapper(compressed, encoding="utf-8") as stream:
                    json.dump(
                        payload,
                        stream,
                        ensure_ascii=False,
                        allow_nan=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
            raw.flush()
            os.fsync(raw.fileno())
        digest, size = _hash_file(temporary)
        # The sidecar is the commit marker: interrupted pairs cannot be consumed as v2.
        os.link(temporary, path)
        committed = True
        _commit_json(
            sidecar,
            {
                "schema_version": 1,
                "artifact_sha256": digest,
                "artifact_size": size,
                "checkpoint": _summary(payload),
                "checkpoint_sha256": _digest(_summary(payload)),
            },
        )
    except BaseException:
        if committed and path.exists() and os.path.samefile(path, temporary):
            path.unlink()
        raise
    finally:
        temporary.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)


def model_info(path):
    path = Path(path)
    info = _bounded_json(_sidecar(path))
    required = {
        "schema_version",
        "artifact_sha256",
        "artifact_size",
        "checkpoint",
        "checkpoint_sha256",
    }
    if (
        not isinstance(info, dict)
        or set(info) != required
        or type(info["schema_version"]) is not int
        or info["schema_version"] != 1
    ):
        raise ValueError("Schema sidecar tidak valid")
    if (
        not _hex(info["artifact_sha256"])
        or type(info["artifact_size"]) is not int
        or info["artifact_size"] < 1
    ):
        raise ValueError("Identitas artifact tidak valid")
    checkpoint = info["checkpoint"]
    if not _hex(info["checkpoint_sha256"]) or _digest(checkpoint) != info["checkpoint_sha256"]:
        raise ValueError("Fingerprint metadata sidecar tidak cocok")
    keys = {
        "format_version",
        "algorithm_version",
        "preprocess_version",
        "n",
        "method",
        "min_count",
        "vocabulary_size",
        "metadata",
        "provenance",
    }
    if not isinstance(checkpoint, dict) or set(checkpoint) != keys:
        raise ValueError("Schema metadata checkpoint tidak valid")
    version = checkpoint["format_version"]
    if (
        type(version) is not int
        or version not in (1, 2)
        or checkpoint["method"] not in (METHODS if version == 1 else ALL_METHODS)
    ):
        raise ValueError("Versi/metode sidecar tidak valid")
    for key in ("n", "min_count", "vocabulary_size"):
        if type(checkpoint[key]) is not int or checkpoint[key] < 1:
            raise ValueError(f"Sidecar {key} tidak valid")
    if checkpoint["n"] > 4 or checkpoint["preprocess_version"] != PREPROCESS_VERSION:
        raise ValueError("Orde/preprocessing sidecar tidak didukung")
    if checkpoint["algorithm_version"] != (
        ALGORITHM_VERSION if version == 2 else "extensions-smoothing-v1"
    ):
        raise ValueError("Versi algoritme tidak didukung")
    _metadata(checkpoint["metadata"], legacy=version == 1)
    _provenance(checkpoint["provenance"], version)
    if version == 2 and (
        checkpoint["provenance"]["corpus_sha256"] != checkpoint["metadata"].get("corpus_sha256")
        or checkpoint["provenance"]["tuning_sha256"]
        != _digest(checkpoint["metadata"].get("tuning_trace", []))
        or checkpoint["provenance"]["split_sha256"] != _split_digest(checkpoint["metadata"])
    ):
        raise ValueError("Provenance metadata tidak cocok")
    if _hash_file(path) != (info["artifact_sha256"], info["artifact_size"]):
        raise ValueError("Hash/ukuran artifact tidak cocok sidecar")
    return info


def _provenance(value, version):
    if version == 1:
        if value is not None:
            raise ValueError("Provenance v1 tidak valid")
    elif not isinstance(value, dict) or set(value) != PROVENANCE_SCHEMA:
        raise ValueError("Provenance v2 tidak valid")
    elif any(
        not _hex(v)
        for key, v in value.items()
        if v is not None or key in ("vocabulary_sha256", "tuning_sha256")
    ):
        raise ValueError("Fingerprint provenance tidak valid")


def load_model(path):
    # ponytail: bounded in-memory counts up to 512 MiB; stream counts when larger models are needed.
    path = Path(path)
    info = model_info(path) if _sidecar(path).exists() else None
    with gzip.open(path, "rb") as stream:
        content = stream.read(MAX_CHECKPOINT + 1)
    if len(content) > MAX_CHECKPOINT:
        raise ValueError("Checkpoint melebihi 512 MiB setelah dekompresi")
    payload = _json(content)
    if (
        not isinstance(payload, dict)
        or type(payload.get("format_version")) is not int
        or payload["format_version"] not in (1, 2)
    ):
        raise ValueError("Format checkpoint tidak didukung")
    version = payload["format_version"]
    required = BASE_SCHEMA | (
        {"algorithm_version", "preprocess_version", "provenance"} if version == 2 else set()
    )
    if set(payload) != required or not isinstance(payload["counts"], dict):
        raise ValueError("Schema checkpoint tidak valid")
    if not isinstance(payload["parameters"], dict) or set(payload["parameters"]) != PARAMETERS:
        raise ValueError("Schema parameters tidak valid")
    if type(payload["n"]) is not int or payload["method"] not in (
        METHODS if version == 1 else ALL_METHODS
    ):
        raise ValueError("Orde/metode tidak valid")
    _metadata(payload["metadata"], legacy=version == 1)
    if version == 2:
        if (
            info is None
            or payload["algorithm_version"] != ALGORITHM_VERSION
            or payload["preprocess_version"] != PREPROCESS_VERSION
        ):
            raise ValueError("Checkpoint v2 belum committed/versi tidak didukung")
        _provenance(payload["provenance"], version)
        expected = {
            "corpus_sha256": payload["metadata"].get("corpus_sha256"),
            "split_sha256": _split_digest(payload["metadata"]),
            "vocabulary_sha256": _digest(payload["vocabulary"]),
            "tuning_sha256": _digest(payload["metadata"].get("tuning_trace", [])),
        }
        if payload["provenance"] != expected:
            raise ValueError("Fingerprint checkpoint tidak cocok")
    raw = {}
    for order, entries in payload["counts"].items():
        if order not in ("1", "2", "3", "4") or not isinstance(entries, list):
            raise ValueError("Count order/entries tidak valid")
        counts = Counter()
        for entry in entries:
            if not isinstance(entry, list) or len(entry) != 2 or not isinstance(entry[0], list):
                raise ValueError("Count entry tidak valid")
            gram, count = entry
            if any(not isinstance(word, str) for word in gram) or tuple(gram) in counts:
                raise ValueError("Count key tidak valid/duplicate")
            counts[tuple(gram)] = count
        raw[int(order)] = counts
    parameters = payload["parameters"]
    for key in PARAMETERS - {"weights"}:
        if type(parameters[key]) not in (int, float) or not math.isfinite(parameters[key]):
            raise ValueError("Parameter harus numeric finite")
    if not isinstance(parameters["weights"], list) or any(
        type(weight) not in (int, float) or not math.isfinite(weight)
        for weight in parameters["weights"]
    ):
        raise ValueError("Weights harus list numeric finite")
    bank = CountBank.from_counts(payload["vocabulary"], raw, payload["min_count"])
    model = ExtensionLM(bank, payload["n"], payload["method"], **payload["parameters"])
    if info is not None and info["checkpoint"] != _summary(payload):
        raise ValueError("Metadata sidecar berbeda dari checkpoint")
    return model, payload["metadata"]


def corpus_digest(sentences):
    # Preserve the v1 corpus fingerprint contract.
    return hashlib.sha256(
        json.dumps(sentences, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def score_sentence(model, text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_LINE or "\x00" in text:
        raise ValueError("Teks harus UTF-8 tanpa NUL dan maksimal 64 KiB")
    tokens = preprocess([tokenize(text)])[0]
    if not tokens or len(tokens[0]) > 4096:
        raise ValueError("Kalimat harus memiliki 1..4096 token alfabetik")
    tokens = tokens[0]
    mapped = model.map_sentence(tokens)
    from core.src.ngram import events

    rows, losses = [], []
    for gram in events(mapped, model.n):
        probability = model.score_mapped(gram[-1], gram[:-1])
        if not math.isfinite(probability) or probability < 0:
            raise ValueError("Skor model tidak finite/nonnegative")
        loss = -math.log(probability) if probability else math.inf
        losses.append(loss)
        rows.append(
            {
                "word": gram[-1],
                "context": list(gram[:-1]),
                "probability": probability,
                "nll": loss if math.isfinite(loss) else None,
            }
        )
    nll = math.fsum(losses)
    ce = nll / len(losses)
    pp = math.exp(ce) if ce < 709 else math.inf
    probabilistic = model.method != "stupid_backoff"
    return {
        "schema_version": 1,
        "preprocess_version": PREPROCESS_VERSION,
        "tokens": tokens,
        "mapped_tokens": mapped,
        "events": rows,
        "predicted_tokens": len(rows),
        "nll": nll if math.isfinite(nll) else None,
        "cross_entropy": ce if math.isfinite(ce) else None,
        "perplexity": pp if probabilistic and math.isfinite(pp) else None,
        "probabilistic": probabilistic,
        "zero_probability": any(row["probability"] == 0 for row in rows),
    }


def _score_file(model, path):
    total = 0
    with Path(path).open("rb") as stream:
        for line_number in range(1, 1_000_001):
            line = stream.readline(MAX_LINE + 1)
            if not line:
                return
            total += len(line)
            if len(line) > MAX_LINE or total > MAX_INPUT:
                raise ValueError("Input melebihi batas baris 64 KiB/file 64 MiB")
            result = score_sentence(model, line.decode("utf-8").rstrip("\r\n"))
            print(json.dumps({"line": line_number, **result}, ensure_ascii=False, allow_nan=False))
        if stream.read(1):
            raise ValueError("Input melebihi satu juta baris")


def _evaluate_locked(path, model, metadata):
    if not {"corpus", "seed", "corpus_sha256"} <= set(metadata):
        raise ValueError("Checkpoint tidak punya metadata split/corpus")
    sentences, _ = preprocess(load_corpus(metadata["corpus"]))
    if corpus_digest(sentences) != metadata["corpus_sha256"]:
        raise ValueError("Corpus berbeda dari training checkpoint")
    train_set, dev, test, ids = split_three(sentences, metadata["seed"])
    if "split" in metadata and (
        metadata["split"]["ids"] != ids
        or metadata["split"]["fingerprints"]
        != {
            "train": corpus_digest(train_set),
            "dev": corpus_digest(dev),
            "test": corpus_digest(test),
        }
    ):
        raise ValueError("Split berbeda dari checkpoint")
    identity = {
        "artifact_sha256": _hash_file(path)[0],
        "split_sha256": _digest(ids),
        "test_sha256": corpus_digest(test),
        "algorithm_version": model_info(path)["checkpoint"]["algorithm_version"]
        if _sidecar(path).exists()
        else "extensions-smoothing-v1",
        "preprocess_version": PREPROCESS_VERSION,
    }
    receipt = _output(Path(path).with_name(Path(path).name + ".evaluation.json"))
    if receipt.exists():
        saved = _bounded_json(receipt)
        if (
            not isinstance(saved, dict)
            or set(saved) != {"schema_version", "identity", "result", "sha256"}
            or type(saved["schema_version"]) is not int
            or saved["schema_version"] != 1
            or saved["identity"] != identity
            or saved["sha256"] != _digest({"identity": identity, "result": saved["result"]})
        ):
            raise ValueError("Receipt evaluasi tidak cocok/corrupt; tidak mengevaluasi ulang")
        result = saved["result"]
        if (
            not isinstance(result, dict)
            or set(result) != {"perplexity", "score_cross_entropy", "predicted_tokens"}
            or type(result["predicted_tokens"]) is not int
            or result["predicted_tokens"] <= 0
            or (
                result["score_cross_entropy"] is not None
                and (
                    type(result["score_cross_entropy"]) not in (int, float)
                    or not math.isfinite(result["score_cross_entropy"])
                )
            )
            or (model.method == "stupid_backoff" and result["perplexity"] is not None)
            or (
                model.method != "stupid_backoff"
                and (
                    (
                        result["perplexity"] is not None
                        and (
                            type(result["perplexity"]) not in (int, float)
                            or not math.isfinite(result["perplexity"])
                            or result["perplexity"] < 1
                            or result["score_cross_entropy"] is None
                        )
                    )
                    or (
                        result["score_cross_entropy"] is not None
                        and result["score_cross_entropy"] < 0
                    )
                )
            )
        ):
            raise ValueError("Receipt hasil evaluasi tidak valid; tidak mengevaluasi ulang")
        return result, True
    result = {
        key: None if isinstance(value, float) and not math.isfinite(value) else value
        for key, value in evaluate_counts(model, model.bank.event_counts(test, model.n)).items()
    }
    payload = {
        "schema_version": 1,
        "identity": identity,
        "result": result,
        "sha256": _digest({"identity": identity, "result": result}),
    }
    _commit_json(receipt, payload)
    return result, False


def _evaluate(path, model, metadata):
    receipt = _output(Path(path).with_name(Path(path).name + ".evaluation.json"))
    lock = receipt.with_name(receipt.name + ".lock")
    with lock.open("xb"):
        pass
    try:
        return _evaluate_locked(path, model, metadata)
    finally:
        lock.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    train = commands.add_parser("train", help="Fit train, tune dev, save model; test not evaluated")
    train.add_argument("--config", type=Path, default=ROOT / "extensions/config.yaml")
    train.add_argument("--model", type=Path, required=True)
    evaluate = commands.add_parser(
        "evaluate", help="Evaluate held-out split once; reuse artifact-bound receipt"
    )
    evaluate.add_argument("--model", type=Path, required=True)
    generate = commands.add_parser("generate", help="Sample sentences")
    generate.add_argument("--model", type=Path, required=True)
    generate.add_argument("--seed", type=int, default=42)
    generate.add_argument("--count", type=int, default=5)
    generate.add_argument("--max-length", type=int, default=40)
    score = commands.add_parser("score", help="Stream one UTF-8 sentence per input line as JSONL")
    score.add_argument("--model", type=Path, required=True)
    score.add_argument("--input", type=Path, required=True)
    info = commands.add_parser(
        "info", help="Validate bounded sidecar and artifact hash without loading counts"
    )
    info.add_argument("--model", type=Path, required=True)
    listing = commands.add_parser("list", help="List validated checkpoint metadata as JSONL")
    listing.add_argument("--dir", type=Path, required=True)
    interactive = commands.add_parser(
        "repl", help="Read-only interactive score/top-k/checkpoint demo"
    )
    interactive.add_argument("--model", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "repl":
            from extensions.src.repl import repl

            return repl(args.model)
        if args.command == "train":
            config = read_config(args.config)
            set_seed(config["seed"])
            sentences, _ = preprocess(load_corpus(config["corpus"]))
            train_set, dev, test, ids = split_three(sentences, config["seed"])
            bank = CountBank(train_set, max_n=config["n"], min_count=config["min_count"])
            model, winner, trace = tune(
                bank, config["n"], config["method"], bank.event_counts(dev, config["n"])
            )
            metadata = {
                **config,
                "corpus_sha256": corpus_digest(sentences),
                "dev_loss": winner["dev_loss"],
                "selection": "dev-only; no test evaluation during train",
                "split": {
                    "strategy": "sentence-80-10-10-v1",
                    "ids": ids,
                    "fingerprints": {
                        "train": corpus_digest(train_set),
                        "dev": corpus_digest(dev),
                        "test": corpus_digest(test),
                    },
                },
                "tuning_trace": trace,
            }
            save_model(args.model, model, metadata)
            print(
                json.dumps(
                    {"model": str(args.model), "V": len(bank.vocabulary), **metadata},
                    ensure_ascii=False,
                    allow_nan=False,
                )
            )
        elif args.command in ("info", "list"):
            paths = [args.model] if args.command == "info" else sorted(args.dir.glob("*.json.gz"))
            if args.command == "list" and not args.dir.is_dir():
                raise ValueError("Direktori model tidak ditemukan")
            for path in paths:
                print(
                    json.dumps(
                        {"model": str(path), **model_info(path)},
                        ensure_ascii=False,
                        allow_nan=False,
                    )
                )
        else:
            model, metadata = load_model(args.model)
            if args.command == "evaluate":
                result, cached = _evaluate(args.model, model, metadata)
                print(json.dumps({**result, "cached": cached}, ensure_ascii=False, allow_nan=False))
            elif args.command == "score":
                _score_file(model, args.input)
            else:
                if (
                    not 1 <= args.count <= 1000
                    or not 1 <= args.max_length <= 4096
                    or not 0 <= args.seed < 2**32
                ):
                    raise ValueError("count 1..1000; max-length 1..4096; seed uint32")
                sampler = Sampler(model, args.seed)
                for _ in range(args.count):
                    print(" ".join(sampler.generate(args.max_length)))
    except (ValueError, TypeError, KeyError, OSError, EOFError, yaml.YAMLError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
