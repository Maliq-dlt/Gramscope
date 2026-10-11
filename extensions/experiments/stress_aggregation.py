"""Reproduce A3 session/token aggregates from hash-verified public CSVs, without model calls."""

import argparse
import csv
import hashlib
import io
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "extensions/results/event_stress_v1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    if path.stat().st_size > 32 * 2**20:
        raise ValueError("Aggregation input exceeds 32 MiB")
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def derive(source=SOURCE):
    result, inputs = [], {}
    for seed in (42, 43, 44):
        directory = Path(source) / f"seed{seed}"
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("phase") != "A3" or manifest.get("status") != "completed":
            raise ValueError("Expected completed public A3 package")
        for filename, target_key, count in (
            ("A3_sessions.csv", "observed_targets_including_eos", 7920),
            ("A3_duration.csv", "targets_including_eos", 360),
        ):
            path = directory / filename
            if digest(path) != manifest["files"][filename]:
                raise ValueError(f"Public source fingerprint mismatch: {path}")
            inputs[f"seed{seed}/{filename}"] = digest(path)
            rows = read_csv(path)
            if len(rows) != count:
                raise ValueError("Frozen A3 row count differs")
            grouped = defaultdict(list)
            for row in rows:
                if int(row["seed"]) != seed or int(row[target_key]) < 1:
                    raise ValueError("Invalid seed or predicted-target denominator")
                for key in (
                    ("score", "clean_score") if filename == "A3_sessions.csv" else ("score",)
                ):
                    if not math.isfinite(float(row[key])):
                        raise ValueError("Aggregation requires finite stored scores")
                grouped[row["condition"], row["model"]].append(row)
            for (condition, model), items in sorted(grouped.items()):
                if len(items) != 180 or len({r["case_id"] for r in items}) != 180:
                    raise ValueError("Expected 180 unique sessions per condition/model")
                lm = model not in ("transition_rules", "pair_frequency_lt2")
                targets = sum(int(r[target_key]) for r in items)
                loss = (
                    math.fsum(float(r["score"]) * int(r[target_key]) for r in items) if lm else None
                )
                result.append(
                    {
                        "seed": seed,
                        "condition": condition,
                        "model": model,
                        "score_kind": "CE_nats" if lm else "rule_count_per_session",
                        "sessions": len(items),
                        "predicted_targets_including_eos": targets,
                        "mean_session_score": math.fsum(float(r["score"]) for r in items)
                        / len(items),
                        "negative_log_likelihood_nats": loss,
                        "token_weighted_ce_nats": loss / targets if loss is not None else None,
                        "clean_mean_session_score": None,
                        "clean_predicted_targets_including_eos": None,
                        "clean_token_weighted_ce_nats": None,
                        "token_weighted_ce_delta_from_clean": None,
                    }
                )
                if filename == "A3_sessions.csv":
                    clean_targets = sum(int(r["clean_targets_including_eos"]) for r in items)
                    if clean_targets < 1:
                        raise ValueError("Invalid clean predicted-target denominator")
                    clean_loss = (
                        math.fsum(
                            float(r["clean_score"]) * int(r["clean_targets_including_eos"])
                            for r in items
                        )
                        if lm
                        else None
                    )
                    result[-1].update(
                        clean_mean_session_score=math.fsum(float(r["clean_score"]) for r in items)
                        / len(items),
                        clean_predicted_targets_including_eos=clean_targets,
                        clean_token_weighted_ce_nats=clean_loss / clean_targets
                        if clean_loss is not None
                        else None,
                        token_weighted_ce_delta_from_clean=loss / targets
                        - clean_loss / clean_targets
                        if loss is not None and clean_loss is not None
                        else None,
                    )
    if len(result) != 138:
        raise ValueError("Expected 138 frozen aggregation grains")
    return result, inputs


def verify(path, rows):
    expected = [
        {key: "" if value is None else str(value) for key, value in row.items()} for row in rows
    ]
    if read_csv(Path(path)) != expected:
        raise ValueError("Stored aggregation differs from public source derivation")
    metadata = Path(path).with_suffix(".json")
    if metadata.exists():
        receipt = json.loads(metadata.read_text(encoding="utf-8"))
        if receipt["aggregation_rows"] != len(rows) or receipt["aggregation_csv_sha256"] != digest(
            Path(path)
        ):
            raise ValueError("Stored aggregation metadata fingerprint mismatch")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--output", type=Path, help="Exclusive new directory inside repository")
    action.add_argument("--check", type=Path, help="Verify an existing aggregation CSV")
    args = parser.parse_args(argv)
    rows, inputs = derive(args.source)
    if args.check:
        verify(args.check, rows)
        print(f"Verified {len(rows)} aggregation grains")
        return 0
    output = (args.output or ROOT / ".tmp/stress-aggregation").resolve()
    if not output.is_relative_to(ROOT) or output == ROOT:
        raise ValueError("Output must be a fresh directory inside repository")
    output.mkdir(parents=True)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    csv_path = output / "aggregation.csv"
    with csv_path.open("x", encoding="utf-8", newline="") as stream:
        stream.write(buffer.getvalue())
    with (output / "derivation_receipt.json").open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "schema": "event-stress-aggregation-generator-v1",
                "generator_sha256": digest(Path(__file__)),
                "aggregation_csv_sha256": digest(csv_path),
                "aggregation_rows": len(rows),
                "source_files": inputs,
                "method": "sum(stored session CE * targets) / sum(targets); no model calls",
            },
            stream,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    verify(csv_path, rows)
    print(csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
