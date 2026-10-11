"""Frozen, continuous SDD person detection/tracking study; no model training."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path
from typing import cast

# isort: off
import runtime  # Sets workspace-local caches before importing ML packages.
import tracking_benchmark as base
import numpy as np
from scipy.optimize import linear_sum_assignment
from trackeval.metrics import HOTA
# isort: on


ROOT = runtime.ROOT
CANDIDATES = ("standard+byte", "standard+bot", "sliced+byte", "sliced+bot")
BASELINE = "standard+byte"
SETTINGS = {
    "stride": 1,
    "person_class": 0,
    "confidence": 0.1,
    "imgsz": 640,
    "iou": 0.5,
    "max_det": 300,
    "slice_size": 640,
    "slice_overlap": 0.2,
    "slice_full_image": True,
    "small_area_max_px": 1024,
    "match_iou": 0.5,
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def inside(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Path outside allowed workspace directory: {path}")
    return path


def clip_file(dataset, clip, filename):
    path = inside(dataset / clip / filename, dataset)
    if path.parent != (dataset / clip).resolve():
        raise ValueError("Invalid clip path")
    return path


def native_snapshot():
    import inspect
    from importlib.metadata import version

    from sahi.models.ultralytics import UltralyticsDetectionModel
    from sahi.predict import get_sliced_prediction
    from ultralytics.trackers.bot_sort import BOTSORT

    return {
        "versions": {"sahi": version("sahi"), **base.native_receipt()["versions"]},
        "sources": {
            "runner": base.sha256(__file__),
            "benchmark": base.sha256(base.__file__),
            "hota": base.sha256(inspect.getfile(HOTA)),
            "sahi_predict": base.sha256(inspect.getfile(get_sliced_prediction)),
            "sahi_ultralytics": base.sha256(inspect.getfile(UltralyticsDetectionModel)),
            "bot_sort": base.sha256(inspect.getfile(BOTSORT)),
            "byte_yaml": base.sha256(
                Path(inspect.getfile(BOTSORT)).parents[1] / "cfg/trackers/bytetrack.yaml"
            ),
            "bot_yaml": base.sha256(
                Path(inspect.getfile(BOTSORT)).parents[1] / "cfg/trackers/botsort.yaml"
            ),
            **base.native_receipt()["sources"],
        },
    }


def inputs(dataset, clips, frames):
    old = read(base.PROTOCOL)
    historical = read(ROOT / old["dataset"] / "manifest.json")
    old_hashes = {
        digest
        for relative, digest in historical["files"].items()
        if relative.endswith(("/video.mp4", "/annotations.txt"))
    }
    old_scenes = {name.split("/", 1)[0] for name in old["clips"]}
    manifest = read(dataset / "manifest.json")
    if manifest.get("status") != "completed":
        raise ValueError("Dataset manifest must be completed before freeze")
    available = {row["clip"]: row for row in manifest["clips"]}
    if len(available) != len(manifest["clips"]):
        raise ValueError("Duplicate manifest clip")
    checked = []
    for chosen in clips:
        row = available[chosen["clip"]]
        if row != chosen["metadata"] or row["source_group"] in old_scenes:
            raise ValueError("Clip metadata changed or historical scene reused")
        if row["max_annotation_frame"] + 1 < frames or frames < 1:
            raise ValueError("Requested contiguous clip interval exceeds annotations")
        files = {}
        for filename in ("video.mp4", "annotations.txt", "reference.jpg"):
            relative = f"{row['clip']}/{filename}"
            digest = base.sha256(clip_file(dataset, row["clip"], filename))
            if digest != manifest["files"].get(relative) or digest in old_hashes:
                raise ValueError(f"Missing, changed, or historically reused input: {relative}")
            files[filename] = digest
        targets, _ = base.ground_truth(dataset / row["clip"] / "annotations.txt", row, 1)
        if len(targets) < frames:
            raise ValueError("Ground truth does not cover every requested frame")
        checked.append({**chosen, "files": files})
    return manifest, checked


def prepare(dataset, output, frames, dev_scenes, test_scenes):
    import cv2

    dataset = inside(dataset, ROOT / "data/public")
    output = base.local_output(output)
    if output.exists() or frames < 1 or not dev_scenes or not test_scenes:
        raise ValueError("Fresh protocol, positive frame count and both roles required")
    if set(dev_scenes) & set(test_scenes):
        raise ValueError("A source scene cannot be both dev and test")
    manifest = read(dataset / "manifest.json")
    scenes = set(dev_scenes) | set(test_scenes)
    if {row["source_group"] for row in manifest["clips"]} != scenes:
        raise ValueError("Every manifest source group must have a declared role")
    clips = [
        {
            "clip": row["clip"],
            "role": "dev" if row["source_group"] in dev_scenes else "test",
            "metadata": row,
        }
        for row in manifest["clips"]
    ]
    if (
        len({cast(dict, row["metadata"])["source_group"] for row in clips if row["role"] == "dev"})
        < 2
    ):
        raise ValueError("At least two independent dev scenes required")
    if (
        len({cast(dict, row["metadata"])["source_group"] for row in clips if row["role"] == "test"})
        < 2
    ):
        raise ValueError("At least two independent test scenes required")
    _, clips = inputs(dataset, clips, frames)
    historical = read(base.PROTOCOL)
    if (
        base.sha256(ROOT / "models/yolo26n.pt") != historical["source_hashes"]["models/yolo26n.pt"]
        or base.native_receipt() != historical["native"]
    ):
        raise ValueError("Original detector or tracker snapshot differs from historical freeze")
    for clip in clips:
        metadata = clip["metadata"]
        capture = cv2.VideoCapture(str(dataset / clip["clip"] / "video.mp4"))
        try:
            if not capture.isOpened() or not math.isclose(
                capture.get(cv2.CAP_PROP_FPS), metadata["fps"], abs_tol=1e-3
            ):
                raise ValueError(f"Frozen clip cannot be decoded at manifest FPS: {clip['clip']}")
            for frame_index in range(frames):
                ok, image = capture.read()
                if not ok or list(image.shape[1::-1]) != metadata["video_dimensions"]:
                    raise ValueError(
                        f"Missing contiguous frame or canvas: {clip['clip']}:{frame_index}"
                    )
        finally:
            capture.release()
    protocol = {
        "version": 1,
        "dataset": dataset.relative_to(ROOT).as_posix(),
        "manifest_sha256": base.sha256(dataset / "manifest.json"),
        "frames_per_clip": frames,
        "settings": SETTINGS,
        "candidates": CANDIDATES,
        "selection": "max dev combined mean HOTA, then IDF1, then lexical candidate name",
        "clips": clips,
        "weights": "models/yolo26n.pt",
        "weights_sha256": base.sha256(ROOT / "models/yolo26n.pt"),
        "native": native_snapshot(),
        "source_snapshot": {
            "continuous_tracking_study.py": Path(__file__).read_text(encoding="utf-8"),
            "tracking_benchmark.py": Path(base.__file__).read_text(encoding="utf-8"),
        },
    }
    base.save(output, protocol)
    return protocol


def preflight(path):
    path = inside(path, ROOT)
    protocol = read(path)
    if (
        protocol["version"] != 1
        or protocol["settings"] != SETTINGS
        or tuple(protocol["candidates"]) != CANDIDATES
        or protocol["weights"] != "models/yolo26n.pt"
        or protocol["weights_sha256"] != base.sha256(ROOT / protocol["weights"])
        or protocol["native"] != native_snapshot()
        or protocol["source_snapshot"]["continuous_tracking_study.py"]
        != Path(__file__).read_text(encoding="utf-8")
        or protocol["source_snapshot"]["tracking_benchmark.py"]
        != Path(base.__file__).read_text(encoding="utf-8")
        or base.native_receipt() != read(base.PROTOCOL)["native"]
    ):
        raise ValueError("Frozen code, model, dependency, or settings changed")
    dataset = inside(ROOT / protocol["dataset"], ROOT / "data/public")
    if protocol["manifest_sha256"] != base.sha256(dataset / "manifest.json"):
        raise ValueError("Manifest changed since protocol freeze")
    _, checked = inputs(dataset, protocol["clips"], protocol["frames_per_clip"])
    if checked != protocol["clips"]:
        raise ValueError("Input hashes changed since protocol freeze")
    roles = {"dev": set(), "test": set()}
    for clip in checked:
        roles[clip["role"]].add(clip["metadata"]["source_group"])
    if len(roles["dev"]) < 2 or len(roles["test"]) < 2 or roles["dev"] & roles["test"]:
        raise ValueError("Source groups must be independent and split by role")
    return protocol, dataset


def normalize(objects, dimensions):
    rows = []
    for obj in objects:
        if obj.category.id != SETTINGS["person_class"]:
            continue
        raw = [float(x) for x in obj.bbox.to_xyxy()]
        bbox, _ = base.clamp_box(raw, dimensions, allow_empty=True)
        rows.append({"track_id": None, "bbox": bbox, "confidence": float(obj.score.value)})
    base.validate_rows(rows, dimensions, predictions=True)
    return rows


def tracked_rows(output, raw, dimensions):
    rows = []
    for values in np.asarray(output).reshape(-1, 8).tolist():
        box, identity, score, category, source = values[:4], *values[4:]
        if (
            category != SETTINGS["person_class"]
            or source != int(source)
            or not 0 <= source < len(raw)
        ):
            raise ValueError("Native tracker output does not correspond to person detection")
        if identity != int(identity) or identity < 0:
            raise ValueError("Native tracker emitted invalid ID")
        bbox, _ = base.clamp_box(box, dimensions, allow_empty=True)
        rows.append({"track_id": int(identity), "bbox": bbox, "confidence": float(score)})
    base.validate_rows(rows, dimensions, predictions=True)
    return rows


def match_counts(gt, detections):
    similarity = base.pairwise_iou(gt, detections)
    small = [
        (r["bbox"][2] - r["bbox"][0]) * (r["bbox"][3] - r["bbox"][1])
        <= SETTINGS["small_area_max_px"]
        for r in gt
    ]
    matches = set()
    if similarity.size:
        valid = similarity >= SETTINGS["match_iou"]
        # Prioritize the number of valid matches, then their IoU.
        score = valid * (min(similarity.shape) + 1 + similarity)
        rows, cols = linear_sum_assignment(-score)
        matches = {int(i) for i, j in zip(rows, cols) if similarity[i, j] >= SETTINGS["match_iou"]}
    return {
        "tp": len(matches),
        "fp": len(detections) - len(matches),
        "fn": len(gt) - len(matches),
        "small_gt": sum(small),
        "small_tp": sum(small[i] for i in matches),
    }


def hota_json(metric, result):
    converted = {"thresholds": metric.array_labels.tolist()}
    for key, value in result.items():
        if isinstance(value, np.ndarray):
            converted[key] = [
                int(x) if key in metric.integer_array_fields else float(x) for x in value
            ]
        else:
            converted[key] = float(value)
    converted["mean_HOTA"] = float(np.mean(result["HOTA"]))
    return converted


def score(protocol_path, run_dir):
    protocol, dataset = preflight(protocol_path)
    run_dir = base.local_output(run_dir)
    receipt, complete = read(run_dir / "receipt.json"), read(run_dir / "complete.json")
    if (
        receipt["protocol_sha256"] != base.sha256(protocol_path)
        or receipt["native"] != protocol["native"]
        or (run_dir / "failure.json").exists()
    ):
        raise ValueError("Run receipt mismatch or failed run")
    for name in ("detections", "tracks"):
        if complete[f"{name}_sha256"] != base.sha256(run_dir / f"{name}.jsonl"):
            raise ValueError("Prediction receipt hash mismatch")
    phase = receipt["phase"]
    if phase not in ("dev", "test"):
        raise ValueError("Invalid run phase")
    if phase == "test":
        selection = base.local_output(receipt["selection_path"])
        selected = read(selection)
        if (
            receipt["selection_sha256"] != base.sha256(selection)
            or receipt["selected"] != selected["selected"]
            or selected["protocol_sha256"] != base.sha256(protocol_path)
            or selected["dev_complete_sha256"]
            != base.sha256(base.local_output(selected["dev_run"]) / "complete.json")
        ):
            raise ValueError("Test selection receipt mismatch")
    if phase == "dev" and receipt.get("selected") is not None:
        raise ValueError("Dev cannot have a test candidate")
    clips = [c for c in protocol["clips"] if c["role"] == phase]
    if not clips or (phase == "test" and receipt["selected"] not in CANDIDATES):
        raise ValueError("Missing phase clips or unknown candidate")
    if phase == "test":
        for clip in clips:
            claim = read(
                ROOT / ".tmp/continuous_tracking_claims" / (clip["files"]["video.mp4"] + ".json")
            )
            if (
                claim["output"] != str(run_dir)
                or claim["gt_sha256"] != clip["files"]["annotations.txt"]
                or claim["selection_sha256"] != receipt["selection_sha256"]
            ):
                raise ValueError("Test claim and receipt mismatch")
    candidates = (
        CANDIDATES if phase == "dev" else tuple(dict.fromkeys((BASELINE, receipt["selected"])))
    )
    expected_detection_rows = len(clips) * protocol["frames_per_clip"] * 2
    expected_track_rows = len(clips) * protocol["frames_per_clip"] * len(candidates)
    detections = (run_dir / "detections.jsonl").open(encoding="utf-8")
    tracks = (run_dir / "tracks.jsonl").open(encoding="utf-8")
    detection_totals: dict[str, dict[str, int | float]] = {
        mode: {key: 0 for key in ("tp", "fp", "fn", "small_gt", "small_tp")}
        for mode in ("standard", "sliced")
    }
    per_candidate = {name: {} for name in candidates}
    native_hota = {name: {} for name in candidates}
    try:
        for clip in clips:
            name, metadata = clip["clip"], clip["metadata"]
            gt, _ = base.ground_truth(dataset / name / "annotations.txt", metadata, 1)
            frames_by_candidate = {candidate: [] for candidate in candidates}
            for frame in range(protocol["frames_per_clip"]):
                for mode in ("standard", "sliced"):
                    line = detections.readline()
                    if not line:
                        raise ValueError("Missing detection row")
                    row = json.loads(line)
                    if (row["clip"], row["frame"], row["mode"], row["gt"]) != (
                        name,
                        frame,
                        mode,
                        gt[frame],
                    ):
                        raise ValueError("Detection/GT frame mismatch")
                    base.validate_rows(row["detections"], metadata["video_dimensions"], True)
                    for key, value in match_counts(gt[frame], row["detections"]).items():
                        detection_totals[mode][key] += value
                for candidate in candidates:
                    line = tracks.readline()
                    if not line:
                        raise ValueError("Missing tracking row")
                    row = json.loads(line)
                    if (row["clip"], row["frame"], row["candidate"], row["gt"]) != (
                        name,
                        frame,
                        candidate,
                        gt[frame],
                    ):
                        raise ValueError("Tracking/GT frame mismatch")
                    base.validate_rows(row["predictions"], metadata["video_dimensions"], True)
                    frames_by_candidate[candidate].append(row)
            for candidate, frames in frames_by_candidate.items():
                native_hota[candidate][name] = HOTA().eval_sequence(
                    base.sequence_data(frames, metadata["video_dimensions"])
                )
                per_candidate[candidate][name] = base.metrics(frames, metadata["video_dimensions"])
        if detections.read() or tracks.read():
            raise ValueError("Unexpected extra prediction rows")
    finally:
        detections.close()
        tracks.close()
    if (
        complete["detection_rows"] != expected_detection_rows
        or complete["track_rows"] != expected_track_rows
    ):
        raise ValueError("Incomplete or extra frame count")
    summary = {}
    for candidate in candidates:
        metric = HOTA()
        combined = metric.combine_sequences(native_hota[candidate])
        summary[candidate] = {
            "per_clip": {
                name: {**per_candidate[candidate][name], "HOTA": hota_json(metric, result)}
                for name, result in native_hota[candidate].items()
            },
            "combined": {
                **base.aggregate(per_candidate[candidate]),
                "HOTA": hota_json(metric, combined),
            },
        }
    for counts in detection_totals.values():
        counts["precision"] = counts["tp"] / max(1, counts["tp"] + counts["fp"])
        counts["recall"] = counts["tp"] / max(1, counts["tp"] + counts["fn"])
        counts["small_recall"] = counts["small_tp"] / max(1, counts["small_gt"])
    return {
        "phase": phase,
        "protocol_sha256": base.sha256(protocol_path),
        "frames": protocol["frames_per_clip"] * len(clips),
        "clips": [c["clip"] for c in clips],
        "selected_on_dev": receipt.get("selected"),
        "pedestrian_detector": detection_totals,
        "candidates": summary,
        "limitations": [
            "SDD aerial Pedestrian labels, not factory/helmet or live CCTV validation.",
            "Generated and occluded Pedestrian ground truth is retained.",
            "Biker, Skater and other SDD classes are excluded from GT; person detections on them count as false positives, so precision is Pedestrian-target precision only.",
            "First contiguous frames per independent scene; no delay or false-alert exposure claim.",
        ],
    }


def select(protocol_path, dev_run, output):
    protocol, _ = preflight(protocol_path)
    output = base.local_output(output)
    if output.exists():
        raise ValueError("Use a fresh selection output")
    scored = score(protocol_path, dev_run)
    if scored["phase"] != "dev" or set(scored["candidates"]) != set(CANDIDATES):
        raise ValueError("Candidate selection requires complete dev comparison")
    ranking = sorted(
        CANDIDATES,
        key=lambda name: (
            -scored["candidates"][name]["combined"]["HOTA"]["mean_HOTA"],
            -scored["candidates"][name]["combined"]["Identity"]["IDF1"],
            name,
        ),
    )
    result = {
        "protocol_sha256": base.sha256(protocol_path),
        "dev_run": str(base.local_output(dev_run)),
        "dev_complete_sha256": base.sha256(Path(dev_run) / "complete.json"),
        "dev_metrics": {
            name: {
                "mean_HOTA": scored["candidates"][name]["combined"]["HOTA"]["mean_HOTA"],
                "IDF1": scored["candidates"][name]["combined"]["Identity"]["IDF1"],
            }
            for name in CANDIDATES
        },
        "rule": protocol["selection"],
        "ranking": ranking,
        "selected": ranking[0],
        "baseline": BASELINE,
    }
    base.save(output, result)
    return result


def claim_test(protocol_path, protocol, selection, output):
    selected = read(selection)
    if (
        selected["protocol_sha256"] != base.sha256(protocol_path)
        or selected["rule"] != protocol["selection"]
    ):
        raise ValueError("Selection belongs to another protocol")
    dev_run = base.local_output(selected["dev_run"])
    if selected["dev_complete_sha256"] != base.sha256(dev_run / "complete.json"):
        raise ValueError("Dev run changed since candidate selection")
    verified = score(protocol_path, dev_run)
    ranking = sorted(
        CANDIDATES,
        key=lambda name: (
            -verified["candidates"][name]["combined"]["HOTA"]["mean_HOTA"],
            -verified["candidates"][name]["combined"]["Identity"]["IDF1"],
            name,
        ),
    )
    if ranking != selected["ranking"] or ranking[0] != selected["selected"]:
        raise ValueError("Selection does not match locked dev metrics")
    claim_dir = ROOT / ".tmp/continuous_tracking_claims"
    for clip in protocol["clips"]:
        if clip["role"] == "test":
            claim = claim_dir / (clip["files"]["video.mp4"] + ".json")
            if claim.exists():
                raise FileExistsError(f"Test video already claimed: {clip['clip']}")
    for clip in protocol["clips"]:
        if clip["role"] == "test":
            claim = claim_dir / (clip["files"]["video.mp4"] + ".json")
            base.save(
                claim,
                {
                    "video_sha256": clip["files"]["video.mp4"],
                    "gt_sha256": clip["files"]["annotations.txt"],
                    "protocol_sha256": base.sha256(protocol_path),
                    "selection_sha256": base.sha256(selection),
                    "output": str(output),
                    "claimed_unix_seconds": time.time(),
                },
            )
    return selected["selected"]


def run(protocol_path, phase, output, device_preference="auto", selection=None):
    import cv2
    import torch
    from sahi import AutoDetectionModel
    from sahi.predict import get_prediction, get_sliced_prediction
    from ultralytics.engine.results import Boxes
    from ultralytics.trackers.bot_sort import BOTSORT
    from ultralytics.trackers.byte_tracker import BYTETracker
    from ultralytics.utils import YAML, IterableSimpleNamespace
    from ultralytics.utils.torch_utils import init_seeds

    if phase not in ("dev", "test"):
        raise ValueError("Choose dev or test")
    protocol, dataset = preflight(protocol_path)
    output = base.local_output(output)
    if output.exists():
        raise FileExistsError("Run output already exists")
    if phase == "test" and selection is None:
        raise ValueError("Test requires locked dev selection")
    selected = (
        claim_test(protocol_path, protocol, selection, output) if phase == "test" else BASELINE
    )
    candidates = CANDIDATES if phase == "dev" else tuple(dict.fromkeys((BASELINE, selected)))
    output.mkdir(parents=True)
    base.save(
        output / "receipt.json",
        {
            "phase": phase,
            "selected": selected if phase == "test" else None,
            "selection_sha256": base.sha256(selection) if selection else None,
            "selection_path": str(Path(selection).resolve()) if selection else None,
            "protocol_sha256": base.sha256(protocol_path),
            "native": protocol["native"],
            "claimed_unix_seconds": time.time(),
        },
    )
    started = time.perf_counter()
    try:
        init_seeds(seed=0, deterministic=True)
        device, reason = runtime.select_device(device_preference)
        cuda = device.startswith("cuda")
        if cuda:
            torch.cuda.reset_peak_memory_stats(device)

        def sync():
            if cuda:
                torch.cuda.synchronize(device)

        def timing(values):
            return {
                "calls": len(values),
                "total_ms": sum(values),
                "p50_ms": float(np.percentile(values, 50)) if values else 0.0,
                "p95_ms": float(np.percentile(values, 95)) if values else 0.0,
            }

        model = AutoDetectionModel.from_pretrained(
            model_type="ultralytics",
            model_path=str(ROOT / protocol["weights"]),
            confidence_threshold=SETTINGS["confidence"],
            image_size=cast(int, SETTINGS["imgsz"]),
            device=device,
        )
        if model.model.names.get(SETTINGS["person_class"]) != "person":
            raise ValueError("Model person class changed")
        model.model.overrides.update(
            {"iou": SETTINGS["iou"], "max_det": SETTINGS["max_det"], "classes": [0]}
        )
        import inspect

        tracker_dir = Path(inspect.getfile(BOTSORT)).parents[1] / "cfg/trackers"
        detection_count = track_count = 0
        detector_ms = {mode: [] for mode in ("standard", "sliced")}
        tracker_ms = {candidate: [] for candidate in candidates}
        with (
            (output / "detections.jsonl").open("x", encoding="utf-8") as detection_file,
            (output / "tracks.jsonl").open("x", encoding="utf-8") as track_file,
        ):
            for clip in protocol["clips"]:
                if clip["role"] != phase:
                    continue
                name, metadata = clip["clip"], clip["metadata"]
                gt, _ = base.ground_truth(dataset / name / "annotations.txt", metadata, 1)
                trackers = {}
                for candidate in candidates:
                    tracker_name = candidate.split("+")[1]
                    config = YAML.load(
                        tracker_dir
                        / ("bytetrack.yaml" if tracker_name == "byte" else "botsort.yaml")
                    )
                    if tracker_name == "bot" and config["with_reid"] is not False:
                        raise ValueError("BoT-SORT ReID must remain disabled")
                    config["device"] = device
                    tracker = BYTETracker if tracker_name == "byte" else BOTSORT
                    trackers[candidate] = tracker(IterableSimpleNamespace(**config))
                capture = cv2.VideoCapture(str(dataset / name / "video.mp4"))
                try:
                    if not capture.isOpened() or not math.isclose(
                        capture.get(cv2.CAP_PROP_FPS), metadata["fps"], abs_tol=1e-3
                    ):
                        raise ValueError(f"Cannot decode frozen FPS: {name}")
                    for frame_index in range(protocol["frames_per_clip"]):
                        ok, frame = capture.read()
                        if not ok or list(frame.shape[1::-1]) != metadata["video_dimensions"]:
                            raise ValueError(
                                f"Missing frame or canvas mismatch: {name}:{frame_index}"
                            )
                        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        raw_by_mode = {}
                        for mode in ("standard", "sliced"):
                            sync()
                            mode_started = time.perf_counter()
                            result = (
                                get_prediction(rgb, model)
                                if mode == "standard"
                                else get_sliced_prediction(
                                    rgb,
                                    model,
                                    slice_height=cast(int, SETTINGS["slice_size"]),
                                    slice_width=cast(int, SETTINGS["slice_size"]),
                                    overlap_height_ratio=SETTINGS["slice_overlap"],
                                    overlap_width_ratio=SETTINGS["slice_overlap"],
                                    perform_standard_pred=cast(bool, SETTINGS["slice_full_image"]),
                                    postprocess_type="NMS",
                                    postprocess_match_metric="IOU",
                                    postprocess_match_threshold=SETTINGS["iou"],
                                    verbose=0,
                                )
                            )
                            raw = normalize(
                                result.object_prediction_list, metadata["video_dimensions"]
                            )
                            sync()
                            detector_ms[mode].append((time.perf_counter() - mode_started) * 1000)
                            raw_by_mode[mode] = raw
                            detection_file.write(
                                json.dumps(
                                    {
                                        "clip": name,
                                        "frame": frame_index,
                                        "mode": mode,
                                        "gt": gt[frame_index],
                                        "detections": raw,
                                    },
                                    sort_keys=True,
                                    allow_nan=False,
                                )
                                + "\n"
                            )
                            detection_count += 1
                        for candidate in candidates:
                            raw = raw_by_mode[candidate.split("+")[0]]
                            values = np.asarray(
                                [r["bbox"] + [r["confidence"], 0] for r in raw], dtype=np.float32
                            ).reshape(-1, 6)
                            boxes = Boxes(values, frame.shape[:2])
                            sync()
                            tracker_started = time.perf_counter()
                            predicted = tracked_rows(
                                trackers[candidate].update(boxes, frame),
                                raw,
                                metadata["video_dimensions"],
                            )
                            sync()
                            tracker_ms[candidate].append(
                                (time.perf_counter() - tracker_started) * 1000
                            )
                            track_file.write(
                                json.dumps(
                                    {
                                        "clip": name,
                                        "frame": frame_index,
                                        "candidate": candidate,
                                        "gt": gt[frame_index],
                                        "predictions": predicted,
                                    },
                                    sort_keys=True,
                                    allow_nan=False,
                                )
                                + "\n"
                            )
                            track_count += 1
                    print(
                        f"{phase} {name}: {protocol['frames_per_clip']} contiguous frames",
                        flush=True,
                    )
                finally:
                    capture.release()
            for stream in (detection_file, track_file):
                stream.flush()
                os.fsync(stream.fileno())
        base.save(
            output / "complete.json",
            {
                "detection_rows": detection_count,
                "track_rows": track_count,
                "detections_sha256": base.sha256(output / "detections.jsonl"),
                "tracks_sha256": base.sha256(output / "tracks.jsonl"),
                "device": device,
                "device_reason": reason,
                "elapsed_seconds": time.perf_counter() - started,
                "detector_timing": {name: timing(values) for name, values in detector_ms.items()},
                "tracker_timing": {name: timing(values) for name, values in tracker_ms.items()},
                "peak_cuda_allocated_bytes": (
                    torch.cuda.max_memory_allocated(device) if cuda else None
                ),
            },
        )
        base.save(output / "metrics.json", score(protocol_path, output))
    except Exception as error:
        base.save(
            output / "failure.json",
            {
                "type": type(error).__name__,
                "error": str(error),
                "test_claim_is_final": phase == "test",
            },
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("prepare")
    freeze.add_argument("--dataset", type=Path, required=True)
    freeze.add_argument("--output", type=Path, required=True)
    freeze.add_argument("--frames", type=int, default=300)
    freeze.add_argument("--dev-scenes", required=True, help="Comma-separated SDD source groups")
    freeze.add_argument("--test-scenes", required=True, help="Comma-separated SDD source groups")
    infer = commands.add_parser("run")
    infer.add_argument("--protocol", type=Path, required=True)
    infer.add_argument("--phase", choices=("dev", "test"), required=True)
    infer.add_argument("--output", type=Path, required=True)
    infer.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    infer.add_argument("--selection", type=Path)
    select_cmd = commands.add_parser("select")
    select_cmd.add_argument("--protocol", type=Path, required=True)
    select_cmd.add_argument("--dev-run", type=Path, required=True)
    select_cmd.add_argument("--output", type=Path, required=True)
    recompute = commands.add_parser("score")
    recompute.add_argument("--protocol", type=Path, required=True)
    recompute.add_argument("--run", type=Path, required=True)
    recompute.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(
            args.dataset,
            args.output,
            args.frames,
            [s for s in args.dev_scenes.split(",") if s],
            [s for s in args.test_scenes.split(",") if s],
        )
        print(json.dumps({"protocol": str(args.output), "clips": len(result["clips"])}))
    elif args.command == "run":
        run(args.protocol, args.phase, args.output, args.device, args.selection)
    elif args.command == "select":
        print(json.dumps(select(args.protocol, args.dev_run, args.output), sort_keys=True))
    else:
        base.save(base.local_output(args.output), score(args.protocol, args.run))


if __name__ == "__main__":
    main()
