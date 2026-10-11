"""Frozen sampled SDD benchmark using native TrackEval Identity and CLEAR metrics."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import os
import time
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from typing import cast

# isort: off
import runtime  # Workspace cache paths precede ML imports.
import numpy as np
from trackeval.metrics import CLEAR, Identity
# isort: on

ROOT = runtime.ROOT
PROTOCOL = ROOT / "reports/tracking_protocol_20261011.json"
CONFIG = {"THRESHOLD": 0.5, "PRINT_CONFIG": False}


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    stream = pending.open("x", encoding="utf-8")
    try:
        with stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(pending, path)  # Exclusive publication; never overwrite a result.
    finally:
        pending.unlink(missing_ok=True)


def local_output(path):
    path = Path(path).resolve()
    if not any(
        path != base.resolve() and path.is_relative_to(base.resolve())
        for base in (ROOT / ".tmp", ROOT / "reports/runtime")
    ):
        raise ValueError("Use a fresh output below industrial_ai/.tmp or reports/runtime")
    return path


def native_receipt():
    import ultralytics

    native = Path(inspect.getfile(Identity)).parent
    tracker = Path(ultralytics.__file__).parent / "cfg/trackers/bytetrack.yaml"
    return {
        "versions": {
            name: version(name)
            for name in ("trackeval", "scipy", "numpy", "ultralytics", "torch", "opencv-python")
        },
        "sources": {
            "identity.py": sha256(native / "identity.py"),
            "clear.py": sha256(native / "clear.py"),
            "bytetrack.yaml": sha256(tracker),
            "byte_tracker.py": sha256(tracker.parents[2] / "trackers/byte_tracker.py"),
            "track.py": sha256(tracker.parents[2] / "trackers/track.py"),
            "default.yaml": sha256(tracker.parent.parent / "default.yaml"),
            "model.py": sha256(tracker.parents[2] / "engine/model.py"),
            "predictor.py": sha256(tracker.parents[2] / "engine/predictor.py"),
        },
    }


def preflight():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if protocol["native"] != native_receipt():
        raise ValueError("Native dependency/version/source changed after protocol freeze")
    for relative, digest in protocol["source_hashes"].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or sha256(path) != digest:
            raise ValueError(f"Frozen source hash mismatch: {relative}")
    dataset = (ROOT / protocol["dataset"]).resolve()
    if not dataset.is_relative_to(ROOT):
        raise ValueError("Dataset must stay inside workspace")
    if sha256(dataset / "manifest.json") != protocol["manifest_sha256"]:
        raise ValueError("Dataset manifest hash mismatch")
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    for relative, digest in manifest["files"].items():
        path = (dataset / relative).resolve()
        if not path.is_relative_to(dataset) or sha256(path) != digest:
            raise ValueError(f"Dataset file hash mismatch: {relative}")
    if [row["clip"] for row in manifest["clips"]] != protocol["clips"]:
        raise ValueError("Frozen clip order changed")
    frames = sum(
        (row["max_annotation_frame"] + protocol["stride"]) // protocol["stride"]
        for row in manifest["clips"]
    )
    if frames != protocol["sampled_frames"]:
        raise ValueError("Frozen sampled frame count mismatch")
    for clip in manifest["clips"]:
        ground_truth(dataset / clip["clip"] / "annotations.txt", clip, protocol["stride"])
    return protocol, manifest, dataset


def clamp_box(box, dimensions, scale=(1.0, 1.0), allow_empty=False):
    if (
        not isinstance(box, list)
        or len(box) != 4
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
    ):
        raise ValueError("Finite xyxy boxes required")
    if (
        box[0] > box[2]
        or box[1] > box[3]
        or (not allow_empty and (box[0] == box[2] or box[1] == box[3]))
    ):
        raise ValueError("Ordered xyxy boxes required; ground truth must have positive area")
    scaled = [float(v * scale[i % 2]) for i, v in enumerate(box)]
    clamped = [min(max(v, 0.0), float(dimensions[i % 2])) for i, v in enumerate(scaled)]
    if not allow_empty and not (clamped[0] < clamped[2] and clamped[1] < clamped[3]):
        raise ValueError("Box has no area after clamping")
    return clamped, clamped != scaled


def validate_rows(rows, dimensions, predictions=False):
    if not isinstance(rows, list):
        raise TypeError("Detection rows must be a list")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or "track_id" not in row:
            raise ValueError("Detection objects require explicit track_id")
        track_id = row["track_id"]
        if not (predictions and track_id is None):
            if type(track_id) is not int or track_id < 0 or track_id in seen:
                raise ValueError("Nonnegative unique per-frame track IDs required")
            seen.add(track_id)
        box, changed = clamp_box(row.get("bbox"), dimensions, allow_empty=predictions)
        if changed or box != row["bbox"]:
            raise ValueError("Receipt boxes must already be clamped to canvas")
        if predictions:
            confidence = row.get("confidence")
            if (
                type(confidence) not in (int, float)
                or not math.isfinite(confidence)
                or not 0 <= confidence <= 1
            ):
                raise ValueError("Finite confidence in 0..1 required")


def ground_truth(path, clip, stride):
    targets = {frame: [] for frame in range(0, clip["max_annotation_frame"] + 1, stride)}
    counts = Counter()
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            fields = line.split()
            if len(fields) != 10:
                raise ValueError("SDD requires ten annotation columns")
            track_id, x1, y1, x2, y2, frame, lost, occluded, generated = map(int, fields[:9])
            if (
                track_id < 0
                or not 0 <= frame <= clip["max_annotation_frame"]
                or any(v not in (0, 1) for v in (lost, occluded, generated))
            ):
                raise ValueError("Invalid SDD annotation metadata")
            sampled = frame in targets
            if lost:
                counts["lost_rows_excluded"] += sampled
                continue
            if fields[9].strip('"') != "Pedestrian":
                counts["other_class_rows_excluded"] += sampled
                continue
            box, clamped = clamp_box(
                [x1, y1, x2, y2],
                clip["video_dimensions"],
                clip["coordinate_scale"],
                allow_empty=True,
            )
            if x1 >= x2 or y1 >= y2:
                raise ValueError("Ground truth must have positive source area")
            if box[0] == box[2] or box[1] == box[3]:
                counts["gt_fully_outside_excluded"] += sampled
                continue
            if not sampled:
                continue
            targets[frame].append(
                {
                    "track_id": track_id,
                    "bbox": box,
                    "occluded": bool(occluded),
                    "generated": bool(generated),
                }
            )
            counts["gt_detections"] += 1
            counts["gt_clamped"] += clamped
            counts["gt_occluded"] += occluded
            counts["gt_generated"] += generated
    for rows in targets.values():
        validate_rows(rows, clip["video_dimensions"])
    return targets, dict(counts)


def pairwise_iou(targets, predictions):
    """All raw pairwise IoU values; TrackEval performs its own matching."""
    left = np.asarray([r["bbox"] for r in targets], dtype=float).reshape(-1, 4)
    right = np.asarray([r["bbox"] for r in predictions], dtype=float).reshape(-1, 4)
    intersection = np.maximum(
        0,
        np.minimum(left[:, None, 2:], right[None, :, 2:])
        - np.maximum(left[:, None, :2], right[None, :, :2]),
    ).prod(axis=2)
    union = (
        (left[:, 2:] - left[:, :2]).prod(axis=1)[:, None]
        + (right[:, 2:] - right[:, :2]).prod(axis=1)[None, :]
        - intersection
    )
    return np.divide(intersection, union, out=np.zeros_like(intersection), where=union > 0)


def sequence_data(frames, dimensions):
    gt_ids, tracker_ids, similarities = [], [], []
    gt_map, tracker_map = {}, {}
    temporary_id = -1
    for frame in frames:
        gt, predictions = frame["gt"], frame["predictions"]
        validate_rows(gt, dimensions)
        validate_rows(predictions, dimensions, True)
        ids = []
        for row in predictions:
            track_id = row["track_id"]
            if track_id is None:  # Preserve detections with no persistent ID as one-frame tracks.
                track_id = temporary_id
                temporary_id -= 1
            ids.append(tracker_map.setdefault(track_id, len(tracker_map)))
        gt_ids.append(
            np.asarray([gt_map.setdefault(r["track_id"], len(gt_map)) for r in gt], dtype=int)
        )
        tracker_ids.append(np.asarray(ids, dtype=int))
        similarities.append(pairwise_iou(gt, predictions))
    return {
        "gt_ids": gt_ids,
        "tracker_ids": tracker_ids,
        "similarity_scores": similarities,
        "num_gt_dets": sum(map(len, gt_ids)),
        "num_tracker_dets": sum(map(len, tracker_ids)),
        "num_gt_ids": len(gt_map),
        "num_tracker_ids": len(tracker_map),
        "num_timesteps": len(frames),
    }


def metrics(frames, dimensions):
    data = sequence_data(frames, dimensions)
    identity, clear = Identity(CONFIG).eval_sequence(data), CLEAR(CONFIG).eval_sequence(data)
    return {
        "Identity": {
            k: float(v) if k in ("IDF1", "IDP", "IDR") else int(v) for k, v in identity.items()
        },
        "CLEAR": {
            k: int(v) if k in CLEAR(CONFIG).integer_fields else float(v) for k, v in clear.items()
        },
    }


def aggregate(per_clip):
    result = {}
    for name, metric in (("Identity", Identity(CONFIG)), ("CLEAR", CLEAR(CONFIG))):
        values = metric.combine_sequences({k: v[name] for k, v in per_clip.items()})
        result[name] = {
            k: int(v) if k in metric.integer_fields else float(v) for k, v in values.items()
        }
    return result


def run(output, preference="auto"):
    import cv2
    from ultralytics import YOLO
    from ultralytics.engine.results import Results

    protocol, manifest, dataset = preflight()
    output = local_output(output)
    output.mkdir(parents=True, exist_ok=False)
    receipt = {
        "protocol_sha256": sha256(PROTOCOL),
        "protocol": protocol,
        "output": str(output),
        "device_preference": preference,
        "claimed_unix_seconds": time.time(),
    }
    save(ROOT / ".tmp/tracking_runs" / (protocol["run_id"] + ".json"), receipt)
    save(output / "receipt.json", receipt)
    started = time.perf_counter()
    counts, summaries = Counter(), {}
    try:
        import torch
        from ultralytics.utils.torch_utils import init_seeds

        init_seeds(
            seed=protocol["inference_kwargs"]["seed"],
            deterministic=protocol["inference_kwargs"]["deterministic"],
        )
        device, reason = runtime.select_device(preference)
        if device.startswith("cuda"):
            torch.cuda.reset_peak_memory_stats(device)
        save(output / "device.json", {"device": device, "reason": reason})
        with (
            (output / "predictions.jsonl").open("x", encoding="utf-8") as stream,
            (output / "raw_predictions.jsonl").open("x", encoding="utf-8") as raw_stream,
        ):
            for clip in manifest["clips"]:
                clip_started = time.perf_counter()
                native_stage_ms: dict[str, float] = {}
                name = clip["clip"]
                targets, gt_counts = ground_truth(
                    dataset / name / "annotations.txt", clip, protocol["stride"]
                )
                detector = YOLO(str(ROOT / protocol["weights"]))  # Fresh tracker for each clip.
                person = [i for i, label in detector.names.items() if label == "person"]
                if person != [protocol["person_class"]]:
                    raise ValueError("Frozen person class does not match model")
                capture = cv2.VideoCapture(str(dataset / name / "video.mp4"))
                if not capture.isOpened():
                    raise ValueError(f"Video cannot be opened: {name}")
                if not math.isclose(capture.get(cv2.CAP_PROP_FPS), clip["fps"], abs_tol=1e-3):
                    capture.release()
                    raise ValueError("Decoded FPS differs from frozen manifest")
                frame_index, sampled, clip_counts = 0, 0, Counter()
                try:
                    while True:
                        ok, frame = capture.read()
                        if not ok:
                            break
                        if list(frame.shape[1::-1]) != clip["video_dimensions"]:
                            raise ValueError("Decoded canvas differs from frozen manifest")
                        if frame_index in targets:
                            result = cast(
                                list[Results],
                                detector.track(
                                    frame,
                                    device=device,
                                    **protocol["inference_kwargs"],
                                ),
                            )[0]
                            for stage, milliseconds in result.speed.items():
                                if milliseconds is not None:
                                    native_stage_ms[stage] = (
                                        native_stage_ms.get(stage, 0.0) + milliseconds
                                    )
                            boxes = result.boxes
                            if boxes is None:
                                raise ValueError("Detector returned no boxes object")
                            raw_stream.write(
                                json.dumps(
                                    {
                                        "clip": name,
                                        "raw_frame": frame_index,
                                        "seconds": frame_index / clip["fps"],
                                        "is_track": boxes.is_track,
                                        "data": [
                                            [v if math.isfinite(v) else str(v) for v in values]
                                            for values in boxes.data.tolist()
                                        ],
                                    },
                                    sort_keys=True,
                                    allow_nan=False,
                                )
                                + "\n"
                            )
                            raw_stream.flush()  # Native result persists before adapter validation.
                            ids = boxes.id.tolist() if boxes.id is not None else [None] * len(boxes)
                            predictions = []
                            for box, track_id, confidence, cls in zip(
                                boxes.xyxy.tolist(), ids, boxes.conf.tolist(), boxes.cls.tolist()
                            ):
                                if int(cls) != protocol["person_class"]:
                                    raise ValueError("Unexpected prediction class")
                                if track_id is not None and (
                                    not math.isfinite(track_id) or track_id != int(track_id)
                                ):
                                    raise ValueError("Nonintegral detector track ID")
                                bbox, clamped = clamp_box(
                                    box, clip["video_dimensions"], allow_empty=True
                                )
                                predictions.append(
                                    {
                                        "track_id": None if track_id is None else int(track_id),
                                        "bbox": bbox,
                                        "raw_bbox": box,
                                        "confidence": float(confidence),
                                    }
                                )
                                clip_counts["prediction_clamped"] += clamped
                                clip_counts["prediction_degenerate"] += (
                                    bbox[0] == bbox[2] or bbox[1] == bbox[3]
                                )
                                clip_counts["untracked_detections"] += track_id is None
                            validate_rows(predictions, clip["video_dimensions"], True)
                            row = {
                                "clip": name,
                                "raw_frame": frame_index,
                                "seconds": frame_index / clip["fps"],
                                "gt": targets[frame_index],
                                "predictions": predictions,
                            }
                            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
                            stream.flush()
                            sampled += 1
                            clip_counts["prediction_detections"] += len(predictions)
                        frame_index += 1
                    if frame_index != clip["max_annotation_frame"] + 1 or sampled != len(targets):
                        raise ValueError(
                            f"Incomplete sequential decode: {name}, {frame_index} frames"
                        )
                finally:
                    capture.release()
                summaries[name] = {
                    "raw_frames": frame_index,
                    "sampled_frames": sampled,
                    "timeline_seconds": frame_index / clip["fps"],
                    "effective_fps": clip["fps"] / protocol["stride"],
                    "elapsed_seconds": time.perf_counter() - clip_started,
                    "native_stage_ms": dict(native_stage_ms),
                    **gt_counts,
                    **dict(clip_counts),
                }
                counts.update({"sampled_frames": sampled, **gt_counts, **dict(clip_counts)})
                print(f"{name}: {sampled} sampled frames", flush=True)
                del detector
            raw_stream.flush()
            os.fsync(raw_stream.fileno())
            stream.flush()
            os.fsync(stream.fileno())
        if counts["sampled_frames"] != protocol["sampled_frames"]:
            raise ValueError("Sampled frame total differs from protocol")
        save(
            output / "inference_complete.json",
            {
                "counts": dict(counts),
                "clips": summaries,
                "predictions_sha256": sha256(output / "predictions.jsonl"),
                "raw_predictions_sha256": sha256(output / "raw_predictions.jsonl"),
                "elapsed_seconds": time.perf_counter() - started,
                "peak_cuda_allocated_bytes": (
                    torch.cuda.max_memory_allocated(device) if device.startswith("cuda") else None
                ),
            },
        )
        save(output / "metrics.json", score(output))
    except Exception as error:
        save(
            output / "failure.json",
            {
                "error": str(error),
                "type": type(error).__name__,
                "elapsed_seconds": time.perf_counter() - started,
                "inference_must_not_be_retried": True,
            },
        )
        raise


def score(output):
    """Recompute metrics from complete receipts without loading or executing a detector."""
    protocol, manifest, dataset = preflight()
    output = local_output(output)
    receipt = json.loads((output / "receipt.json").read_text(encoding="utf-8"))
    complete = json.loads((output / "inference_complete.json").read_text(encoding="utf-8"))
    predictions = output / "predictions.jsonl"
    if (
        receipt["protocol_sha256"] != sha256(PROTOCOL)
        or receipt["protocol"] != protocol
        or complete["predictions_sha256"] != sha256(predictions)
        or complete["raw_predictions_sha256"] != sha256(output / "raw_predictions.jsonl")
    ):
        raise ValueError("Inference receipt integrity mismatch")
    per_clip = {}
    with predictions.open(encoding="utf-8") as stream:
        for clip in manifest["clips"]:
            targets, _ = ground_truth(
                dataset / clip["clip"] / "annotations.txt", clip, protocol["stride"]
            )
            frames = []
            for raw_frame, gt in targets.items():
                line = stream.readline()
                if not line:
                    raise ValueError("Incomplete predictions receipt")
                row = json.loads(line)
                if (
                    row["clip"] != clip["clip"]
                    or row["raw_frame"] != raw_frame
                    or row["gt"] != gt
                    or not math.isclose(row["seconds"], raw_frame / clip["fps"], abs_tol=1e-9)
                ):
                    raise ValueError("Prediction/GT frame alignment mismatch")
                frames.append(row)
            per_clip[clip["clip"]] = metrics(frames, clip["video_dimensions"])
        if stream.read():
            raise ValueError("Unexpected extra prediction rows")
    return {
        "run_id": protocol["run_id"],
        "protocol_sha256": sha256(PROTOCOL),
        "predictions_sha256": complete["predictions_sha256"],
        "per_clip": per_clip,
        "combined": aggregate(per_clip),
        "sampled_frames": protocol["sampled_frames"],
        "sampled_timeline_seconds": manifest["raw_exposure_seconds"],
        "limitations": protocol["limitations"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight")
    infer = commands.add_parser("infer")
    infer.add_argument("--output", required=True)
    infer.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    recompute = commands.add_parser("score")
    recompute.add_argument("--run", required=True)
    recompute.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "infer":
        run(args.output, args.device)
    elif args.command == "score":
        save(local_output(args.output), score(args.run))
    else:
        protocol, _, _ = preflight()
        print(f"Preflight passed: {protocol['sampled_frames']} frames; no inference")


if __name__ == "__main__":
    main()
