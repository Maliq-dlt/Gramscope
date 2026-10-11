"""One runnable check: class-aware matcher, frozen confidence, AP and cache integrity."""

import json
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runtime  # isort: skip

import detector_benchmark as benchmark

THRESHOLDS = {"person": 0.35, "Hardhat": 0.45, "NO-Hardhat": 0.45}


def box(cls=0, bbox=None, confidence=None):
    row = {"class": cls, "bbox": bbox or [0.1, 0.1, 0.9, 0.9]}
    if confidence is not None:
        row["confidence"] = confidence
    return row


def metric(rows):
    return benchmark.calculate_metrics(rows, THRESHOLDS)


def expect_error(function, *args):
    try:
        function(*args)
    except (TypeError, ValueError, FileExistsError):
        return
    raise AssertionError("Invalid input or existing output must fail")


truth = [box()]
assert benchmark.match_predictions(truth, [box(confidence=0.9)]).all()
assert (
    benchmark.match_predictions(truth, [box(confidence=0.9), box(confidence=0.8)])[:, 0].sum() == 1
)
assert not benchmark.match_predictions(truth, [box(1, confidence=0.9)]).any()
assert benchmark.match_predictions(truth, []).shape == (0, 10)
assert not benchmark.match_predictions([], [box(confidence=0.9)]).any()
assert benchmark.match_predictions([], []).shape == (0, 10)
# Exact IoU=.5 uses >=, not > or epsilon-shrunken IoU at normalized coordinates.
assert benchmark.match_predictions(
    [box(bbox=[0, 0, 1, 1])], [box(bbox=[0, 0, 0.5, 1], confidence=0.35)]
)[0, 0]
assert not benchmark.match_predictions(
    [box(bbox=[0, 0, 1, 1])], [box(bbox=[0, 0, 0.49, 1], confidence=0.35)]
)[0, 0]

rows = [
    {
        "id": "positive",
        "targets": [box(), box(1)],
        "predictions": [box(confidence=0.9), box(confidence=0.8)],
    },
    {"id": "negative", "targets": [], "predictions": [box(confidence=0.95)]},
    {"id": "below_threshold", "targets": [box(2)], "predictions": [box(2, confidence=0.44)]},
    {"id": "empty", "targets": [], "predictions": []},
]
result = metric(rows)
assert result["images"] == 4 and result["image_ids"] == [r["id"] for r in rows]
person, hardhat, no_hat = result["per_class"]
assert (person["tp"], person["fp"], person["fn"]) == (1, 2, 0)
assert person["precision"] == 1 / 3 and person["recall"] == 1
assert (hardhat["tp"], hardhat["fp"], hardhat["fn"]) == (0, 0, 1)
assert hardhat["ap50"] == 0
assert (no_hat["tp"], no_hat["fp"], no_hat["fn"]) == (0, 0, 1)
assert no_hat["ap50"] > 0.99 and no_hat["recall"] == 0  # AP must not replace fixed operating P/R.
assert person["ap50"] < 0.8  # High-confidence false positive on a negative image lowers AP.
perfect = metric([{"id": "one", "targets": truth, "predictions": [box(confidence=0.35)]}])
assert perfect["per_class"][0]["tp"] == 1 and perfect["map50"] > 0.99
# Operating matching must be rerun after filtering: a below-threshold exact box cannot steal TP.
rematched = metric(
    [
        {
            "id": "competing",
            "targets": [box(bbox=[0, 0, 1, 1])],
            "predictions": [
                box(bbox=[0, 0, 0.5, 1], confidence=0.9),
                box(bbox=[0, 0, 1, 1], confidence=0.1),
            ],
        }
    ]
)
assert (rematched["per_class"][0]["tp"], rematched["per_class"][0]["fn"]) == (1, 0)
assert (
    benchmark.match_predictions(
        [box(bbox=[0, 0, 0.45, 1]), box(bbox=[0.55, 0, 1, 1])],
        [box(bbox=[0, 0, 0.45, 1], confidence=0.9), box(bbox=[0.55, 0, 1, 1], confidence=0.8)],
    )[:, 0].sum()
    == 2
)
missed = metric([{"id": "missed", "targets": truth, "predictions": []}])
assert missed["per_class"][0]["fn"] == 1 and missed["map50"] == 0
empty = metric([{"id": "negative", "targets": [], "predictions": []}])
assert empty["map50"] is None and all(r["recall"] is None for r in empty["per_class"])
expect_error(metric, [rows[0], rows[0]])
expect_error(benchmark.match_predictions, truth, [box(confidence=float("nan"))])
expect_error(
    benchmark.match_predictions, truth, [box(bbox=[0, 0, float("nan"), 1], confidence=0.9)]
)
expect_error(benchmark.match_predictions, truth, [box(bbox=[0, 0, 1.01, 1], confidence=0.9)])
expect_error(benchmark.match_predictions, {}, [])
# Native clip_boxes may collapse a border box. Retain it as FP, including on negative images.
collapsed = box(bbox=[0.2, 1, 0.4, 1], confidence=0.9)
assert not benchmark.match_predictions(truth, [collapsed]).any()
assert not benchmark.match_predictions([], [collapsed]).any()
zero = metric([{"id": "zero", "targets": truth, "predictions": [collapsed]}])["per_class"][0]
assert (zero["tp"], zero["fp"], zero["fn"], zero["ap50"]) == (0, 1, 1, 0)
expect_error(benchmark.match_predictions, truth, [box(bbox=[0.9, 0, 0.1, 1], confidence=0.9)])
expect_error(benchmark.match_predictions, [box(bbox=[0, 0, 0, 1])], [])
expect_error(benchmark.output_directory, runtime.MODELS / "benchmark")

root = runtime.ROOT / ".tmp" / f"detector_benchmark_check_{uuid4()}"
root.mkdir()
assert benchmark.output_directory(root) == root
benchmark.atomic_json(root / "atomic.json", {"value": 1})
expect_error(benchmark.atomic_json, root / "atomic.json", {"value": 2})
assert json.loads((root / "atomic.json").read_text())["value"] == 1
assert not list(root.glob("*.pending"))
(root / "occupied.json.pending").write_text("existing writer", encoding="utf-8")
expect_error(benchmark.atomic_json, root / "occupied.json", {"value": 2})
assert (root / "occupied.json.pending").read_text() == "existing writer"
claims = root / "claims"
claim_data = {"split": "val", "files": {"frozen-source": "a"}}
claimed = root / "claimed"
claimed.mkdir()
benchmark.atomic_json(claimed / "snapshot.json", claim_data)
receipt = benchmark.claim_run(claim_data, claimed, claims)
assert receipt.is_file()
second = root / "second"
second.mkdir()
benchmark.atomic_json(second / "snapshot.json", claim_data)
expect_error(benchmark.claim_run, claim_data, second, claims)
assert json.loads(receipt.read_text())["output"] == claimed.relative_to(benchmark.ROOT).as_posix()
benchmark.claim_run({**claim_data, "split": "test"}, second, claims)
changed_environment = {"files": {}, **benchmark.native_environment()}
changed_environment["versions"] = {**changed_environment["versions"], "numpy": "changed"}
expect_error(benchmark.verify_sources, changed_environment)
# Recovery verifies a claimed contiguous prefix and copies bytes without repeating inference.
prior = root / "partial"
prior.mkdir()
fixture_images = [{"id": "first", "targets": truth}, {"id": "second", "targets": truth}]
fixture = {
    "split": "val",
    "files": {},
    **benchmark.native_environment(),
    "images": fixture_images,
    "device": {"selected": "cpu"},
    "protocol": {"benchmark": {"operating_confidence": THRESHOLDS}},
}
benchmark.atomic_json(prior / "snapshot.json", fixture)
benchmark.atomic_json(prior / "failure.json", {"status": "failed", "cached_images": 1})
(prior / "val.claim").write_text(benchmark.sha256(prior / "snapshot.json"))
benchmark.atomic_json(
    prior / "predictions/0000.json", {**fixture_images[0], "predictions": [collapsed]}
)
fixture_claims = root / "fixture-claims"
benchmark.claim_run(fixture, prior, fixture_claims)
original_hashes = {
    p.relative_to(prior).as_posix(): benchmark.sha256(p) for p in prior.rglob("*") if p.is_file()
}
invalid_output = root / "invalid-recovery"
try:
    benchmark.prepare_recovery(prior, invalid_output, fixture_claims, requested_split="test")
except ValueError:
    pass
else:
    raise AssertionError("Split mismatch must fail before output or recovery claim")
assert not invalid_output.exists() and not list(fixture_claims.glob("recovery-*"))
try:
    benchmark.prepare_recovery(
        prior, invalid_output, fixture_claims, requested_device={"selected": "cuda:0"}
    )
except ValueError:
    pass
else:
    raise AssertionError("Device mismatch must fail before output or recovery claim")
assert not invalid_output.exists() and not list(fixture_claims.glob("recovery-*"))
recovered_output = root / "recovered"
recovered, recovered_rows = benchmark.prepare_recovery(prior, recovered_output, fixture_claims)
assert len(recovered_rows) == 1 and recovered_rows[0]["id"] == "first"
assert (
    benchmark.sha256(recovered_output / "predictions/0000.json")
    == original_hashes["predictions/0000.json"]
)
assert recovered["recovery"]["reused_cached_images"] == 1
benchmark.verify_sources(recovered)
expect_error(benchmark.prepare_recovery, prior, root / "second-recovery", fixture_claims)
assert {
    p.relative_to(prior).as_posix(): benchmark.sha256(p) for p in prior.rglob("*") if p.is_file()
} == original_hashes
cache = root / "cache"
cache.mkdir()
benchmark.atomic_json(
    cache / "snapshot.json",
    {
        "files": {},
        **benchmark.native_environment(),
        "images": rows,
        "protocol": {"benchmark": {"operating_confidence": THRESHOLDS}},
    },
)
for index, row in enumerate(rows):
    benchmark.atomic_json(cache / "predictions" / f"{index:04d}.json", row)
benchmark.atomic_json(cache / "metrics.json", result)
benchmark.atomic_json(
    cache / "manifest.json",
    {
        "status": "completed",
        "files": {
            p.relative_to(cache).as_posix(): benchmark.sha256(p)
            for p in cache.rglob("*")
            if p.is_file()
        },
    },
)
assert benchmark.check_cached(cache) == result
(cache / "predictions/0000.json").write_text("{}", encoding="utf-8")
expect_error(benchmark.check_cached, cache)
print(
    "PASS: duplicates/wrong class/misses/negatives/exact IoU, fixed confidence, native AP, exclusive cache/tamper, degenerate FP and recovery checks"
)
