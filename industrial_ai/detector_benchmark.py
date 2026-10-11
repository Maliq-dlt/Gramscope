"""Frozen public-image detection benchmark; interrupted runs are never inferred again."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import time
from collections import Counter, defaultdict
from importlib.metadata import version
from pathlib import Path

import runtime  # Workspace cache paths precede ML imports.

ROOT = runtime.ROOT.parent
PROTOCOL = runtime.ROOT / "reports/validation_protocol_20261011.json"
PROTOCOL_SHA256 = "84b2768453ebaa8ef21c642dfabded907dbf9ca2ff956a2c80ca45feaaa36753"
NAMES = {0: "person", 1: "Hardhat", 2: "NO-Hardhat"}
LABEL_MAP = {6: 0, 0: 1, 7: 2}
LEGACY_SHA256 = "7f25d0d9ad08391823345964877e0add9f1bbe015e425d08d823390334c841a0"
LEGACY_SOURCE = ROOT / ".tmp/academic-validation/detector_benchmark_v1.py"


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    stream = pending.open("x", encoding="utf-8")
    try:
        with stream:
            json.dump(data, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(pending, path)  # Exclusive commit; never replace a previous result.
    finally:
        pending.unlink(missing_ok=True)


def output_directory(path):
    path = Path(path).resolve()
    allowed = (runtime.ROOT / ".tmp", runtime.ROOT / "reports/runtime")
    if not any(
        path != parent.resolve() and path.is_relative_to(parent.resolve()) for parent in allowed
    ):
        raise ValueError(
            "Output must be a new directory under industrial_ai/.tmp or reports/runtime"
        )
    return path


def validate_boxes(boxes, predictions=False):
    if not isinstance(boxes, list):
        raise TypeError("Boxes must be a list")
    for row in boxes:
        if (
            not isinstance(row, dict)
            or type(row.get("class")) is not int
            or row["class"] not in NAMES
        ):
            raise ValueError("Unknown benchmark class")
        box = row.get("bbox")
        if (
            not isinstance(box, list)
            or len(box) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
            or not (0 <= box[0] <= box[2] <= 1 and 0 <= box[1] <= box[3] <= 1)
            or (not predictions and (box[0] == box[2] or box[1] == box[3]))
        ):
            raise ValueError("Finite ordered normalized xyxy required; targets need positive area")
        if predictions and (
            type(row.get("confidence")) not in (int, float)
            or not math.isfinite(row["confidence"])
            or not 0 <= row["confidence"] <= 1
        ):
            raise ValueError("Finite confidence in 0..1 required")


def match_predictions(targets, predictions):
    """Native class-aware IoU matching without constructing a file-writing validator."""
    import torch
    from ultralytics.engine.validator import BaseValidator
    from ultralytics.utils.metrics import box_iou

    validate_boxes(targets)
    validate_boxes(predictions, True)
    truth = torch.tensor([r["bbox"] for r in targets], dtype=torch.float64).reshape(-1, 4)
    predicted = torch.tensor([r["bbox"] for r in predictions], dtype=torch.float64).reshape(-1, 4)
    thresholds = torch.tensor([0.5 + i * 0.05 for i in range(10)], dtype=torch.float64)
    # Positive-area targets keep union > 0; degenerate predictions have IoU 0.
    validator = object.__new__(BaseValidator)
    validator.iouv = thresholds
    return validator.match_predictions(
        torch.tensor([r["class"] for r in predictions]),
        torch.tensor([r["class"] for r in targets]),
        box_iou(truth, predicted, eps=0),
        use_scipy=False,
    ).numpy()


def calculate_metrics(rows, operating_confidence):
    """All images, including negatives; AP and fixed operating-point counts stay separate."""
    import numpy as np
    from ultralytics.utils.metrics import ap_per_class

    if not rows or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Nonempty unique image IDs required")
    if set(operating_confidence) != set(NAMES.values()) or any(
        type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
        for v in operating_confidence.values()
    ):
        raise ValueError("One finite operating confidence per class required")
    targets, classes, confidences, matches = [], [], [], []
    counts = {c: Counter() for c in NAMES}
    for row in rows:
        truth, predictions = row["targets"], row["predictions"]
        matches.append(match_predictions(truth, predictions))
        targets.extend(r["class"] for r in truth)
        classes.extend(r["class"] for r in predictions)
        confidences.extend(r["confidence"] for r in predictions)
        selected = [
            r for r in predictions if r["confidence"] >= operating_confidence[NAMES[r["class"]]]
        ]
        operating = match_predictions(truth, selected)[:, 0]
        for cls in NAMES:
            support = sum(r["class"] == cls for r in truth)
            predicted = sum(r["class"] == cls for r in selected)
            tp = sum(bool(hit) and r["class"] == cls for hit, r in zip(operating, selected))
            counts[cls].update(support=support, tp=tp, fp=predicted - tp, fn=support - tp)
    average_precision = {}
    if targets:
        # Ignore native max-F1 P/R/TP/FP; they select a confidence from the evaluated split.
        result = ap_per_class(
            np.concatenate(matches),
            np.asarray(confidences),
            np.asarray(classes),
            np.asarray(targets),
            plot=False,
            names=NAMES,
        )
        average_precision = dict(zip(result[6].tolist(), result[5]))
    per_class = []
    for cls, name in NAMES.items():
        c = counts[cls]
        ap = average_precision.get(cls)
        per_class.append(
            {
                "class": name,
                "confidence": operating_confidence[name],
                **dict(c),
                "precision": c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else None,
                "recall": c["tp"] / c["support"] if c["support"] else None,
                "ap50": float(ap[0]) if ap is not None else None,
                "ap50_95": float(ap.mean()) if ap is not None else None,
            }
        )
    labeled = [r for r in per_class if r["support"]]
    return {
        "images": len(rows),
        "image_ids": [r["id"] for r in rows],
        "per_class": per_class,
        "map50": float(np.mean([r["ap50"] for r in labeled])) if labeled else None,
        "map50_95": float(np.mean([r["ap50_95"] for r in labeled])) if labeled else None,
        "operating_iou": 0.5,
        "native_max_f1_ignored": True,
    }


def native_environment():
    import ultralytics.engine.validator as native_validator
    import ultralytics.utils.metrics as native_metrics

    return {
        "native_code": {
            "metrics.py": sha256(native_metrics.__file__),
            "validator.py": sha256(native_validator.__file__),
        },
        "versions": {
            n: version(n) for n in ("ultralytics", "torch", "torchvision", "numpy", "Pillow")
        },
    }


def snapshot(split, protocol_path=PROTOCOL):
    """Decode no test predictions; freeze all source bytes and supplied labels before claim."""
    from PIL import Image

    protocol_path = Path(protocol_path).resolve()
    if sha256(protocol_path) != PROTOCOL_SHA256:
        raise ValueError("Frozen benchmark protocol differs")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    benchmark = protocol["benchmark"]
    if split not in benchmark["split"]:
        raise ValueError("Split must be val or test")
    dataset = (ROOT / benchmark["dataset"]).resolve()
    if not dataset.is_relative_to((runtime.ROOT / "data/public").resolve()):
        raise ValueError("Dataset must stay in public workspace data")
    files = [
        protocol_path,
        Path(__file__).resolve(),
        dataset / "data.yaml",
        dataset / "LICENSE",
        dataset / "source.json",
    ]
    images_by_split, hashes = {}, defaultdict(list)
    orphan_labels = {}
    for partition in ("train", "val", "test"):
        images = sorted((dataset / "images" / partition).iterdir())
        if any(
            p.suffix.lower() not in {".jpg", ".jpeg", ".png"} or not p.is_file() or p.is_symlink()
            for p in images
        ):
            raise ValueError("Only regular public image files are accepted")
        if len({p.stem for p in images}) != len(images):
            raise ValueError("Ambiguous image stem")
        labels = sorted((dataset / "labels" / partition).glob("*.txt"))
        if any(p.is_symlink() for p in labels):
            raise ValueError("Symlink labels are not accepted")
        stems = {p.stem for p in images}
        orphan_labels[partition] = [p.name for p in labels if p.stem not in stems]
        files.extend(images + labels)
        images_by_split[partition] = images
        for image in images:
            hashes[sha256(image)].append(f"{partition}/{image.name}")
    duplicate_groups = [
        names for names in hashes.values() if len({n.split("/")[0] for n in names}) > 1
    ]
    if duplicate_groups:
        raise ValueError("Exact cross-split image duplicates; do not infer holdout")
    if len(images_by_split[split]) != {"val": 143, "test": 141}[split]:
        raise ValueError("Frozen benchmark image count differs")
    for name, expected in benchmark["weights"].items():
        path = runtime.MODELS / name
        if sha256(path) != expected:
            raise ValueError("Base weight hash differs")
        files.append(path)
    inventory = {str(p.relative_to(ROOT).as_posix()): sha256(p) for p in files}
    rows = []
    for image in images_by_split[split]:
        label = dataset / "labels" / split / (image.stem + ".txt")
        targets, ignored = [], Counter()
        for line in label.read_text(encoding="utf-8").splitlines():
            fields = line.split()
            if len(fields) != 5:
                raise ValueError("Malformed YOLO label")
            cls = int(fields[0])
            x, y, width, height = map(float, fields[1:])
            if (
                cls not in range(11)
                or not all(math.isfinite(v) and 0 <= v <= 1 for v in (x, y, width, height))
                or not width * height
            ):
                raise ValueError("Invalid supplied YOLO label")
            box = [x - width / 2, y - height / 2, x + width / 2, y + height / 2]
            if min(box) < -1e-5 or max(box) > 1 + 1e-5:
                raise ValueError("Supplied box outside image")
            if cls in LABEL_MAP:
                targets.append({"class": LABEL_MAP[cls], "bbox": [min(1, max(0, v)) for v in box]})
            else:
                ignored[str(cls)] += 1
        validate_boxes(targets)
        with Image.open(image) as decoded:
            width, height = decoded.size
            if width < 1 or height < 1 or width * height > 40_000_000:
                raise ValueError("Unbounded image dimensions")
            decoded.verify()
        rows.append(
            {
                "id": f"{split}/{image.name}",
                "path": str(image.relative_to(ROOT).as_posix()),
                "sha256": inventory[str(image.relative_to(ROOT).as_posix())],
                "width": width,
                "height": height,
                "targets": targets,
                "ignored_labels": dict(ignored),
            }
        )
    return {
        "schema": 1,
        "split": split,
        "protocol": protocol,
        "files": inventory,
        **native_environment(),
        "exact_cross_split_duplicates": 0,
        "orphan_labels": orphan_labels,
        "images": rows,
        "label_rounding": "edges within 1e-5 clipped to 0..1; original labels preserved",
        "unconditional_heads": True,
        "deterministic": True,
        "rect": True,
        "agnostic_nms": False,
    }


def verify_sources(data, compatible=False):
    if any(data.get(key) != value for key, value in native_environment().items()):
        raise ValueError("Native metrics code or dependency versions changed")
    for relative, expected in data["files"].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT.resolve()):
            raise ValueError("Source outside workspace")
        if sha256(path) != expected and not (
            compatible
            and path == Path(__file__).resolve()
            and expected == LEGACY_SHA256
            and sha256(LEGACY_SOURCE) == expected
        ):
            raise ValueError("Source changed after frozen snapshot")
    for relative, expected in data.get("recovery", {}).get("files", {}).items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT.resolve()) or sha256(path) != expected:
            raise ValueError("Recovery input changed")


def source_fingerprint(data):
    evaluator = Path(__file__).resolve().relative_to(ROOT).as_posix()
    sources = {p: digest for p, digest in data["files"].items() if p != evaluator}
    return hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()


def claim_run(data, output, claims=None):
    """One inference claim per frozen protocol/data/weights and split, including failures."""
    claims = output_directory(claims or runtime.ROOT / ".tmp/detector-benchmark-claims")
    fingerprint = source_fingerprint(data)
    path = claims / f"{fingerprint}-{data['split']}.json"
    atomic_json(
        path,
        {
            "split": data["split"],
            "sources_sha256": fingerprint,
            "snapshot_sha256": sha256(output / "snapshot.json"),
            "output": output.relative_to(ROOT).as_posix(),
            "policy": "claimed before model loading; interrupted/failed inference is not repeated",
        },
    )
    return path


def raw_predictions(raw, head):
    if not (len(raw["cls"]) == len(raw["conf"]) == len(raw["xyxyn"])):
        raise ValueError("Native output lengths differ")
    predictions = []
    for cls, confidence, bbox in zip(raw["cls"], raw["conf"], raw["xyxyn"]):
        if type(cls) not in (int, float) or not math.isfinite(cls) or cls != int(cls):
            raise ValueError("Native class must be a finite integer")
        predictions.append(
            {
                "class": int(cls) if head == 0 else int(cls) + 1,
                "confidence": confidence,
                "bbox": bbox,
            }
        )
    validate_boxes(predictions, True)
    return predictions


def prepare_recovery(
    prior, output, claims=None, diagnosis=None, requested_split=None, requested_device=None
):
    """Preserve the interrupted run and copy its contiguous cache to a fresh recovery."""
    prior, output = output_directory(prior), output_directory(output)
    claims = output_directory(claims or runtime.ROOT / ".tmp/detector-benchmark-claims")
    if output.exists() or (prior / "manifest.json").exists():
        raise FileExistsError("Recovery needs fresh output and an interrupted source run")
    data = json.loads((prior / "snapshot.json").read_text())
    failure = json.loads((prior / "failure.json").read_text())
    if requested_split is not None and requested_split != data["split"]:
        raise ValueError("Recovery split differs")
    if requested_device is not None and requested_device != data["device"]:
        raise ValueError("Recovery must use original device")
    verify_sources(data, compatible=True)
    prior_hash = sha256(prior / "snapshot.json")
    claim = json.loads((claims / f"{source_fingerprint(data)}-{data['split']}.json").read_text())
    if (
        claim["snapshot_sha256"] != prior_hash
        or claim["output"] != prior.relative_to(ROOT).as_posix()
        or (prior / f"{data['split']}.claim").read_text() != prior_hash
        or failure.get("status") != "failed"
    ):
        raise ValueError("Interrupted claim or failure differs")
    count = failure["cached_images"]
    paths = sorted((prior / "predictions").glob("*.json"))
    if (
        type(count) is not int
        or not 0 <= count < len(data["images"])
        or [p.name for p in paths] != [f"{i:04d}.json" for i in range(count)]
    ):
        raise ValueError("Recovery cache must be contiguous and incomplete")
    rows = [json.loads(path.read_text()) for path in paths]
    for row, image in zip(rows, data["images"]):
        if any(row.get(key) != value for key, value in image.items()):
            raise ValueError("Cached reference differs from snapshot")
        validate_boxes(row["predictions"], True)
    sources = {p.relative_to(ROOT).as_posix(): sha256(p) for p in prior.rglob("*") if p.is_file()}
    sources[
        (claims / f"{source_fingerprint(data)}-{data['split']}.json").relative_to(ROOT).as_posix()
    ] = sha256(claims / f"{source_fingerprint(data)}-{data['split']}.json")
    recovery = {
        "prior": prior.relative_to(ROOT).as_posix(),
        "prior_snapshot_sha256": prior_hash,
        "reused_cached_images": count,
        "files": sources,
        "correction": "native zero-area predictions retained as false positives; targets positive",
        "policy": "same frozen models/confidence/inference; cached observations are not repeated",
    }
    diagnostic_row = None
    if diagnosis is not None:
        diagnosis = output_directory(diagnosis)
        manifest = json.loads((diagnosis / "manifest.json").read_text())
        diagnostic_files = {
            p.relative_to(diagnosis).as_posix(): sha256(p)
            for p in diagnosis.rglob("*")
            if p.is_file() and p.name != "manifest.json"
        }
        if manifest.get("status") != "diagnosed" or manifest["files"] != diagnostic_files:
            raise ValueError("Diagnostic raw cache changed")
        info = json.loads((diagnosis / "diagnosis.json").read_text())
        image = data["images"][count]
        if (
            info["prior_snapshot_sha256"] != prior_hash
            or info["image_id"] != image["id"]
            or info["image_sha256"] != image["sha256"]
            or info["inference"] != data["protocol"]["benchmark"]["inference"]
            or info["native"] != native_environment()
            or info.get("prior") != prior.relative_to(ROOT).as_posix()
        ):
            raise ValueError("Diagnostic sources or frozen parameters differ")
        predictions, timings = [], {}
        for head, name in enumerate(("yolo26n.pt", "helmet.pt")):
            raw = json.loads((diagnosis / f"head-{head}.json").read_text())
            if (
                raw["head"] != head
                or raw["model"] != name
                or raw["model_sha256"] != data["protocol"]["benchmark"]["weights"][name]
            ):
                raise ValueError("Diagnostic model differs")
            predictions.extend(raw_predictions(raw, head))
            timings["person" if head == 0 else "helmets"] = {
                "wall_ms": raw["wall_ms"],
                "native_stage_ms": raw["native_stage_ms"],
                "diagnostic": True,
            }
        diagnostic_row = {
            **image,
            "predictions": predictions,
            "timings": timings,
            "image_wall_ms": sum(t["wall_ms"] for t in timings.values()),
        }
        recovery.update(
            diagnostic_image=image["id"],
            diagnostic_repeat=True,
            deviation="original failed image output was lost before cache; one isolated diagnostic repeat reused",
            diagnostic_device_evidence="diagnostic command explicitly selected cuda:0; device/name was not independently stored in raw metadata",
            timing_notice="diagnostic image wall is sum of head walls; interrupted sessions are not continuous throughput",
        )
        recovery["files"].update(
            {p.relative_to(ROOT).as_posix(): sha256(p) for p in diagnosis.rglob("*") if p.is_file()}
        )
    evaluator = Path(__file__).resolve().relative_to(ROOT).as_posix()
    if data["files"].get(evaluator) == LEGACY_SHA256:
        data["files"][LEGACY_SOURCE.relative_to(ROOT).as_posix()] = LEGACY_SHA256
    data["files"][evaluator] = sha256(__file__)
    data["recovery"] = recovery
    output.mkdir(parents=True)
    atomic_json(output / "snapshot.json", data)
    atomic_json(
        claims / f"recovery-{prior_hash}.json",
        {
            "prior_snapshot_sha256": prior_hash,
            "snapshot_sha256": sha256(output / "snapshot.json"),
            "output": output.relative_to(ROOT).as_posix(),
        },
    )
    for path in paths:
        destination = output / "predictions" / path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    if diagnostic_row is not None and diagnosis is not None:
        atomic_json(output / "predictions" / f"{count:04d}.json", diagnostic_row)
        rows.append(diagnostic_row)
        for head in range(2):
            shutil.copyfile(
                diagnosis / f"head-{head}.json", output / f"diagnostic-head-{head}.json"
            )
    return data, rows


def run(split, output, device="auto", protocol_path=PROTOCOL, resume=None, diagnosis=None):
    output = output_directory(output)
    if output.exists():
        raise FileExistsError(
            "Use a new output directory; cached or interrupted runs cannot be reinferred"
        )
    if resume is None:
        data, rows = snapshot(split, protocol_path), []
    else:
        prior = output_directory(resume)
        data = json.loads((prior / "snapshot.json").read_text())
        if split is not None and split != data["split"]:
            raise ValueError("Resume split differs")
        split = data["split"]
        rows = []
    import cv2
    import torch
    from ultralytics import YOLO
    from ultralytics.engine.results import Results
    from ultralytics.utils.torch_utils import init_seeds

    if device not in {"auto", "cpu", "cuda"}:
        raise ValueError("Device must be auto, cpu or cuda")
    available = torch.cuda.is_available()
    if device == "cuda" and not available:
        raise ValueError("CUDA requested but unavailable")
    chosen = "cuda:0" if device != "cpu" and available else "cpu"
    init_seeds(42, deterministic=True)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.set_num_threads(8)
    selected_device = {
        "requested": device,
        "selected": chosen,
        "cuda_available": available,
        "name": torch.cuda.get_device_name(0) if chosen != "cpu" else "CPU",
        "compiled_cuda": torch.version.cuda,
        "fallback": False,
    }
    if resume is not None:
        data, rows = prepare_recovery(
            resume,
            output,
            diagnosis=diagnosis,
            requested_split=split,
            requested_device=selected_device,
        )
    else:
        data["device"] = selected_device
        output.mkdir(parents=True)
        atomic_json(output / "snapshot.json", data)
        claim_run(data, output)
    with (output / f"{split}.claim").open("x", encoding="utf-8") as claim:
        claim.write(sha256(output / "snapshot.json"))
    models = []
    started = time.perf_counter()
    try:
        for name, expected_names in (
            ("yolo26n.pt", {0: "person"}),
            ("helmet.pt", {0: "Hardhat", 1: "NO-Hardhat"}),
        ):
            model = YOLO(str(runtime.MODELS / name))
            if any(model.names.get(k) != v for k, v in expected_names.items()):
                raise ValueError("Model class mapping differs")
            models.append(model)
        load_seconds = time.perf_counter() - started
        for index, image in enumerate(data["images"]):
            if index < len(rows):
                continue
            began = time.perf_counter()
            raw = (ROOT / image["path"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != image["sha256"]:
                raise ValueError("Image changed after snapshot")
            import numpy as np

            frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None or frame.shape[:2] != (image["height"], image["width"]):
                raise ValueError("Image decode differs from snapshot")
            predictions, timings, raw_heads = [], {}, []
            inference = data["protocol"]["benchmark"]["inference"]
            for head, model in enumerate(models):
                if chosen != "cpu":
                    torch.cuda.synchronize(0)
                head_started = time.perf_counter()
                results = model.predict(
                    frame,
                    classes=[0] if head == 0 else None,
                    conf=inference["confidence_min"],
                    imgsz=inference["imgsz"],
                    iou=inference["iou_nms"],
                    max_det=inference["max_det"],
                    batch=1,
                    augment=False,
                    half=False,
                    rect=True,
                    agnostic_nms=False,
                    device=chosen,
                    save=False,
                    verbose=False,
                    stream=False,
                    project=str(output),
                    name="inference",
                    exist_ok=True,
                )
                result = next(iter(results))
                if not isinstance(result, Results):
                    raise TypeError("Detector must return native Results")
                if chosen != "cpu":
                    torch.cuda.synchronize(0)
                timings["person" if head == 0 else "helmets"] = {
                    "wall_ms": (time.perf_counter() - head_started) * 1000,
                    "native_stage_ms": dict(result.speed),
                    "end2end_head": bool(getattr(model.model, "end2end", False)),
                }
                if result.boxes is None:
                    raise ValueError("Model returned no boxes object")
                raw_head = {
                    "cls": result.boxes.cls.tolist(),
                    "conf": result.boxes.conf.tolist(),
                    "xyxyn": result.boxes.xyxyn.tolist(),
                    "native_data": result.boxes.data.tolist(),
                    "timing": timings["person" if head == 0 else "helmets"],
                }
                # Preserve NaN/Infinity as explicit strings if the native trust boundary fails.
                saved_raw = json.loads(json.dumps(raw_head), parse_constant=lambda token: token)
                atomic_json(output / "raw" / f"{index:04d}-head-{head}.json", saved_raw)
                raw_heads.append(raw_head)
            # Both heads are persisted before validation or metric derivation.
            for head, raw_head in enumerate(raw_heads):
                predictions.extend(raw_predictions(raw_head, head))
            validate_boxes(predictions, True)
            row = {
                **image,
                "predictions": predictions,
                "timings": timings,
                "image_wall_ms": (time.perf_counter() - began) * 1000,
            }
            atomic_json(output / "predictions" / f"{index:04d}.json", row)
            rows.append(row)
        verify_sources(data)
        metrics = calculate_metrics(rows, data["protocol"]["benchmark"]["operating_confidence"])
        atomic_json(output / "metrics.json", metrics)
        with (output / "metrics.csv").open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(metrics["per_class"][0]))
            writer.writeheader()
            writer.writerows(metrics["per_class"])
        import numpy as np

        summary = {
            "split": split,
            "images": len(rows),
            "device": data["device"],
            "model_load_seconds": load_seconds,
            "total_seconds": time.perf_counter() - started,
            "image_wall_ms_p50": float(np.quantile([r["image_wall_ms"] for r in rows], 0.5)),
            "image_wall_ms_p95": float(np.quantile([r["image_wall_ms"] for r in rows], 0.95)),
            "timing_notice": "cold first inference/warmup included; per-image wall includes both heads and decode",
            "limits": data["protocol"]["benchmark"]["limits"],
            "metrics": metrics,
        }
        summary["degenerate_predictions"] = {
            name: {
                "all_confidences": sum(
                    r["class"] == cls
                    and (r["bbox"][0] == r["bbox"][2] or r["bbox"][1] == r["bbox"][3])
                    for row in rows
                    for r in row["predictions"]
                ),
                "operating_confidence": sum(
                    r["class"] == cls
                    and r["confidence"]
                    >= data["protocol"]["benchmark"]["operating_confidence"][name]
                    and (r["bbox"][0] == r["bbox"][2] or r["bbox"][1] == r["bbox"][3])
                    for row in rows
                    for r in row["predictions"]
                ),
            }
            for cls, name in NAMES.items()
        }
        if "recovery" in data:
            summary["recovery"] = data["recovery"]
            summary["timing_notice"] += (
                "; interrupted sessions/diagnostic/cache reuse, not continuous throughput"
            )
        atomic_json(output / "summary.json", summary)
        atomic_json(
            output / "manifest.json",
            {
                "status": "completed",
                "split": split,
                "files": {
                    p.relative_to(output).as_posix(): sha256(p)
                    for p in sorted(output.rglob("*"))
                    if p.is_file()
                },
            },
        )
        return summary
    except BaseException as error:
        atomic_json(
            output / "failure.json",
            {
                "status": "failed",
                "error_type": type(error).__name__,
                "detail": str(error),
                "cached_images": len(rows),
                "fallback": False,
            },
        )
        raise


def check_cached(output):
    """Verify and recompute cached metrics without inference or overwriting artifacts."""
    output = output_directory(output)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    files = {
        p.relative_to(output).as_posix(): sha256(p)
        for p in sorted(output.rglob("*"))
        if p.is_file() and p.name != "manifest.json"
    }
    if manifest.get("status") != "completed" or manifest.get("files") != files:
        raise ValueError("Incomplete or changed cached benchmark")
    data = json.loads((output / "snapshot.json").read_text(encoding="utf-8"))
    verify_sources(data, compatible=True)
    rows = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((output / "predictions").glob("*.json"))
    ]
    if [r["id"] for r in rows] != [r["id"] for r in data["images"]]:
        raise ValueError("Cached image coverage differs")
    actual = calculate_metrics(rows, data["protocol"]["benchmark"]["operating_confidence"])
    if actual != json.loads((output / "metrics.json").read_text(encoding="utf-8")):
        raise ValueError("Cached metric parity differs")
    return actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("val", "test"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--resume", type=Path, help="Interrupted source run; reuse its contiguous cached prefix"
    )
    parser.add_argument(
        "--diagnosis", type=Path, help="Verified raw diagnostic cache for first failed image"
    )
    args = parser.parse_args()
    try:
        if args.diagnosis is not None and args.resume is None:
            parser.error("--diagnosis requires --resume")
        if not args.check and args.split is None and args.resume is None:
            parser.error("--split is required for inference")
        result = (
            check_cached(args.output)
            if args.check
            else run(
                args.split, args.output, args.device, resume=args.resume, diagnosis=args.diagnosis
            )
        )
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f"detector benchmark: {error}\n")
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
