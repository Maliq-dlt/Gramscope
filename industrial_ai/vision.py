"""Video tracking and conservative helmet association."""

from dataclasses import dataclass, field

OBJECT_NAMES = {
    "person": "orang",
    "car": "mobil",
    "bus": "bus",
    "truck": "truk",
    "motorcycle": "motor",
    "bicycle": "sepeda",
}


def reviewed_summary(summary: dict) -> dict:
    """Apply complete object reviews at their exact timestamps; keep AI data intact."""
    frames = summary.get("manual_frames", [])
    completed = [f for f in frames if f.get("complete", False)]
    classes = list(
        dict.fromkeys(
            [
                *summary.get("object_classes", ["person", "car"]),
                *sorted(
                    {
                        b["label"]
                        for f in completed
                        for b in f["boxes"]
                        if b["label"] not in {"Hardhat", "NO-Hardhat"}
                    }
                ),
            ]
        )
    )
    by_time = {round(f["seconds"], 2): f for f in completed}
    occupancy = []
    for original in summary["occupancy"]:
        row = dict(original)
        review = by_time.get(round(row["seconds"], 2))
        if review is not None:
            for kind in classes:
                row[kind] = sum(b["label"] == kind for b in review["boxes"])
        occupancy.append(row)
    latest = max(completed, key=lambda f: (f.get("updated_at", ""), f["seconds"]), default=None)
    status = {
        "saved_positions": len(completed),
        "draft_positions": sum(not f.get("complete", False) for f in frames),
        "latest": None
        if latest is None
        else {
            "seconds": latest["seconds"],
            "counts": {k: sum(b["label"] == k for b in latest["boxes"]) for k in classes},
        },
    }
    return {
        **summary,
        "reviewed_occupancy": occupancy,
        "reviewed_classes": classes,
        "review_status": status,
    }


def reviewed_box_rows(overlays, annotations, corrections):
    """Apply approved replacements, retaining only unambiguous existing track associations."""
    rows = {row["frame_index"]: row for row in overlays["frames"]}
    rows.update({row["frame_index"]: row for row in corrections["frames"]})
    for frame in annotations["frames"]:
        if not frame.get("complete"):
            continue
        candidates = rows.get(frame["frame_index"], {}).get("boxes", [])
        boxes = []
        claimed = set()
        for box in frame["boxes"]:
            from prompt_tracking import PromptTracker

            matches = [
                b
                for b in candidates
                if b.get("track_id") is not None
                and b["track_id"] not in claimed
                and b["label"] == box["label"]
                and PromptTracker.overlap(b["bbox"], box["bbox"]) >= 0.3
            ]
            if len(matches) == 1:
                claimed.add(matches[0]["track_id"])
                boxes.append({**box, "track_id": matches[0]["track_id"]})
        rows[frame["frame_index"]] = {"boxes": boxes}
    return rows


def crossing_review(summary, overlays, annotations, corrections):
    """Recount candidate crossings from saved boxes; approval still happens in the ledger."""
    rows = reviewed_box_rows(overlays, annotations, corrections)
    corrected = bool(corrections["frames"] or any(f.get("complete") for f in annotations["frames"]))
    if not rows or "line" not in summary:
        return {**summary, "crossing_source": "original_detector"}
    counter = Counter(summary["line"])
    tracks = {t["id"]: dict(t) for t in summary.get("tracks", [])}
    previous, boxes_by_frame = {}, {}
    for index, row in sorted(rows.items()):
        for box in row["boxes"]:
            track = box.get("track_id")
            if type(track) is not int or box["label"] not in OBJECT_NAMES:
                continue
            if track in previous and index - previous[track] > 1:
                counter.sides.pop(track, None)
            previous[track] = index
            tracks[track] = {**tracks.get(track, {}), "id": track, "kind": box["label"]}
            boxes_by_frame[index, track] = box["bbox"]
            before = len(counter.crossings)
            counter.update(
                track, box["label"], (box["bbox"][1] + box["bbox"][3]) / 2, index / summary["fps"]
            )
            if len(counter.crossings) > before:
                counter.crossings[-1]["bbox"] = box["bbox"]
    if not corrected:
        crossings = [
            {
                **c,
                "bbox": boxes_by_frame.get(
                    (min(int(c["seconds"] * summary["fps"]), summary["frames"] - 1), c["track_id"]),
                    c.get("bbox"),
                ),
            }
            for c in summary.get("crossings", [])
        ]
    else:
        crossings = counter.crossings
    return {
        **summary,
        "tracks": list(tracks.values()),
        "crossings": crossings,
        "crossing_source": "reviewer_corrected" if corrected else "original_detector",
    }


@dataclass
class Counter:
    line: float
    sides: dict = field(default_factory=dict)
    crossings: list = field(default_factory=list)
    last_crossing: dict = field(default_factory=dict)

    def update(self, track_id: int, kind: str, position: float, seconds: float):
        # Hysteresis and cooldown stop boxes jittering on the counting line.
        side = -1 if position < self.line - 0.025 else 1 if position > self.line + 0.025 else 0
        if not side:
            return
        previous = self.sides.get(track_id)
        if (
            previous is not None
            and previous != side
            and seconds - self.last_crossing.get(track_id, -10) >= 1
        ):
            self.crossings.append(
                {
                    "track_id": track_id,
                    "kind": kind,
                    "direction": "down" if side > 0 else "up",
                    "seconds": round(seconds, 2),
                }
            )
            self.last_crossing[track_id] = seconds
        self.sides[track_id] = side


def helmet_status(person, hats):
    x1, y1, x2, y2 = person
    candidates = set()
    for box, label in hats:
        hx1, hy1, hx2, hy2 = box
        cx, cy = (hx1 + hx2) / 2, (hy1 + hy2) / 2
        if x1 <= cx <= x2 and y1 <= cy <= y1 + (y2 - y1) * 0.35:
            candidates.add(label)
    if candidates == {"Hardhat"}:
        return "helmet"
    if candidates == {"NO-Hardhat"}:
        return "no_helmet"
    return "unknown"


def process_video(
    folder,
    line,
    report_progress,
    device="cpu",
    object_model=None,
    helmet_model=None,
    object_classes=None,
    cancel=None,
):
    import json
    import shutil
    import time
    from typing import cast

    import cv2
    import torch
    from ultralytics import YOLO
    from ultralytics.engine.results import Results

    from operations import check_cancel, run_command
    from runtime import MODELS

    def command(args, timeout=180):
        result = run_command(args, text=True, timeout=timeout, cancel=cancel)
        if result.returncode:
            raise ValueError("Pemrosesan video gagal: " + result.stderr[-800:])
        return result.stdout

    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ValueError("FFmpeg/ffprobe belum tersedia di PATH.")
    metadata = json.loads(
        command(
            [
                ffprobe,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-format_whitelist",
                "mov,matroska,avi,m4v",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(folder / "upload.bin"),
            ]
        )
    )
    streams = [s for s in metadata["streams"] if s["codec_type"] == "video"]
    duration = float(metadata["format"].get("duration", 0))
    if not streams or not 0 < duration <= 120:
        raise ValueError("Pilih video yang dapat dibaca dengan durasi maksimal 2 menit.")
    stream = streams[0]
    if int(stream["width"]) * int(stream["height"]) > 3840 * 2160:
        raise ValueError("Resolusi input maksimal 4K.")
    report_progress(2, "Menyiapkan salinan video untuk pemutar")
    # ponytail: local demo uses 720p/10 FPS; retain the upload for a future full-resolution worker.
    command(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-protocol_whitelist",
            "file,pipe",
            "-format_whitelist",
            "mov,matroska,avi,m4v",
            "-i",
            str(folder / "upload.bin"),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2,fps=10",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(folder / "original.mp4"),
        ]
    )
    torch.set_num_threads(8)
    detector = YOLO(str(object_model or MODELS / "yolo26n.pt"))
    helmet = YOLO(str(helmet_model or MODELS / "helmet.pt"))
    names = {name: OBJECT_NAMES.get(name, name) for name in (object_classes or OBJECT_NAMES)}
    classes = [key for key, name in detector.names.items() if name in names]
    capture = cv2.VideoCapture(str(folder / "original.mp4"))
    fps = capture.get(cv2.CAP_PROP_FPS)
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width, height = int(capture.get(3)), int(capture.get(4))
    if not capture.isOpened() or fps <= 0 or total <= 0:
        raise ValueError("Video gagal dibuka setelah normalisasi.")
    writer = cv2.VideoWriter(
        str(folder / "annotated.avi"), cv2.VideoWriter.fourcc(*"MJPG"), fps, (width, height)
    )
    if not writer.isOpened():
        capture.release()
        raise ValueError("Encoder video hasil tidak tersedia.")
    counter, tracks, occupancy = Counter(line), {}, []
    overlays = []
    palette = {
        "helmet": (65, 165, 55),
        "no_helmet": (50, 55, 220),
        "unknown": (0, 175, 235),
        "car": (225, 150, 65),
        "bus": (185, 105, 110),
        "truck": (120, 125, 170),
        "motorcycle": (165, 125, 45),
        "bicycle": (140, 145, 75),
    }
    for kind in names:
        palette.setdefault(kind, (180, 120, 70))
    started = time.monotonic()
    index = 0
    try:
        while True:
            check_cancel(cancel)
            ok, frame = capture.read()
            if not ok:
                break
            seconds = index / fps
            evidence_frame = frame.copy()
            result = cast(
                list[Results],
                detector.track(
                    frame,
                    persist=True,
                    tracker="bytetrack.yaml",
                    classes=classes,
                    conf=0.35,
                    imgsz=640,
                    verbose=False,
                    device=device,
                    stream=False,
                ),
            )[0]
            boxes = result.boxes
            if boxes is None:
                raise RuntimeError("Detector did not return detection boxes.")
            ids = (
                [int(i) for i in boxes.id.tolist()] if boxes.id is not None else [None] * len(boxes)
            )
            rows = list(
                zip(
                    boxes.xyxy.tolist(),
                    [int(i) for i in boxes.cls.tolist()],
                    ids,
                    boxes.conf.tolist(),
                )
            )
            people = [box for box, cls, _, _ in rows if detector.names[cls] == "person"]
            hats = []
            if people:
                prediction = cast(
                    list[Results],
                    helmet.predict(
                        frame, conf=0.45, imgsz=640, verbose=False, device=device, stream=False
                    ),
                )[0].boxes
                if prediction is None:
                    raise RuntimeError("Helmet detector did not return boxes.")
                for box, cls in zip(
                    prediction.xyxy.tolist(), [int(i) for i in prediction.cls.tolist()]
                ):
                    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                    owners = sum(
                        p[0] <= cx <= p[2] and p[1] <= cy <= p[1] + (p[3] - p[1]) * 0.35
                        for p in people
                    )
                    if owners == 1:
                        hats.append((box, helmet.names[cls]))
            frame_boxes = []
            for box, cls, track_id, _ in rows:
                kind = detector.names[cls]
                status = helmet_status(box, hats) if kind == "person" else kind
                b, g, r = palette[status]
                frame_boxes.append(
                    {
                        "label": kind,
                        "name": None,
                        "color": f"#{r:02x}{g:02x}{b:02x}",
                        "bbox": [
                            max(0, box[0] / width),
                            max(0, box[1] / height),
                            min(1, box[2] / width),
                            min(1, box[3] / height),
                        ],
                        "track_id": track_id,
                        "source": "detector",
                    }
                )
            for box, label in hats:
                frame_boxes.append(
                    {
                        "label": label,
                        "name": None,
                        "color": None,
                        "bbox": [
                            max(0, box[0] / width),
                            max(0, box[1] / height),
                            min(1, box[2] / width),
                            min(1, box[3] / height),
                        ],
                        "source": "detector",
                    }
                )
            overlays.append({"frame_index": index, "boxes": frame_boxes})
            visible = dict.fromkeys(names, 0)
            for box, cls, track_id, confidence in rows:
                kind = detector.names[cls]
                visible[kind] += 1
                status = helmet_status(box, hats) if kind == "person" else kind
                x1, y1, x2, y2 = [int(x) for x in box]
                cv2.rectangle(frame, (x1, y1), (x2, y2), palette[status], 2)
                label = f"{kind} #{track_id if track_id is not None else '?'} / {status} {confidence:.2f}"
                cv2.rectangle(
                    frame,
                    (x1, max(0, y1 - 24)),
                    (min(width, x1 + len(label) * 8), y1),
                    palette[status],
                    -1,
                )
                cv2.putText(
                    frame,
                    label,
                    (x1 + 3, max(16, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (0, 0, 0),
                    1,
                    cv2.LINE_AA,
                )
                if track_id is None:
                    continue
                counter.update(track_id, kind, (y1 + y2) / 2 / height, seconds)
                track = tracks.setdefault(
                    track_id,
                    {
                        "id": track_id,
                        "kind": kind,
                        "first_seconds": round(seconds, 2),
                        "helmet_candidate": False,
                        "without_helmet_since": None,
                    },
                )
                if seconds - track.get("last_seconds", seconds) > 1.5 / fps:
                    track["without_helmet_since"] = None
                track["last_seconds"] = round(seconds, 2)
                track["status"] = status
                track["detection_confidence"] = round(confidence, 3)
                area = max(0, x2 - x1) * max(0, y2 - y1)
                if "evidence" not in track or area > track.get("evidence_area", 0) * 1.25:
                    track["evidence"] = f"evidence_{track_id}.jpg"
                    track["evidence_seconds"] = round(seconds, 2)
                    track["evidence_status"] = status
                    track["evidence_bbox"] = [x1, y1, x2, y2]
                    track["evidence_area"] = area
                    proof = evidence_frame.copy()
                    cv2.rectangle(proof, (x1, y1), (x2, y2), palette[status], 2)
                    cv2.putText(
                        proof,
                        f"{kind} ID #{track_id} / {status}",
                        (max(0, x1), max(20, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        palette[status],
                        2,
                        cv2.LINE_AA,
                    )
                    if not cv2.imwrite(str(folder / track["evidence"]), proof):
                        raise OSError("Failed to save track evidence.")
                if status == "no_helmet":
                    if track["without_helmet_since"] is None:
                        track["without_helmet_since"] = seconds
                    if (
                        seconds - track["without_helmet_since"] >= 2
                        and not track["helmet_candidate"]
                    ):
                        track["helmet_candidate"] = True
                        track["helmet_seconds"] = round(seconds, 2)
                        track["helmet_evidence"] = f"helmet_{track_id}.jpg"
                        proof = evidence_frame.copy()
                        cv2.rectangle(proof, (x1, y1), (x2, y2), palette[status], 2)
                        cv2.putText(
                            proof,
                            f"person ID #{track_id} / no_helmet candidate",
                            (max(0, x1), max(20, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            palette[status],
                            2,
                            cv2.LINE_AA,
                        )
                        if not cv2.imwrite(str(folder / track["helmet_evidence"]), proof):
                            raise OSError("Failed to save helmet evidence.")
                else:
                    track["without_helmet_since"] = None
            occupancy.append({"seconds": round(seconds, 2), **visible})
            for x in range(0, width, 32):
                cv2.line(
                    frame,
                    (x, int(height * line)),
                    (min(x + 16, width), int(height * line)),
                    (240, 240, 240),
                    1,
                )
            cv2.putText(
                frame,
                "COUNTING LINE",
                (12, max(18, int(height * line) - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (240, 240, 240),
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                f"VISIBLE: person {visible.get('person', 0)} | other objects {sum(v for k, v in visible.items() if k != 'person')}",
                (12, height - 14),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )
            writer.write(frame)
            index += 1
            if index % 10 == 0:
                report_progress(
                    min(90, 5 + int(index / total * 85)), f"Tracking {index}/{total} frame"
                )
        if index == 0 or index < total - 2:
            raise ValueError("Video berhenti sebelum seluruh frame terbaca.")
    finally:
        capture.release()
        writer.release()
    pending = folder / "overlays.pending"
    pending.write_text(json.dumps({"frames": overlays}), encoding="utf-8")
    pending.replace(folder / "overlays.json")
    report_progress(94, "Menyimpan video hasil dan ringkasan")
    command(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(folder / "annotated.avi"),
            "-i",
            str(folder / "original.mp4"),
            "-map",
            "0:v:0",
            "-map",
            "1:a?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            "-shortest",
            str(folder / "tracked.mp4"),
        ]
    )
    elapsed = time.monotonic() - started
    return {
        "object_classes": list(names),
        "object_names": names,
        "device": device,
        "duration": round(index / fps, 2),
        "frames": index,
        "fps": fps,
        "line": line,
        "processing_seconds": round(elapsed, 2),
        "tracks": list(tracks.values()),
        "crossings": counter.crossings,
        "occupancy": occupancy,
        "models": {
            "tracking": "YOLO26n + ByteTrack",
            "helmet": "keremberke YOLOv8n hard-hat (pretrained)",
        },
        "notes": [
            "Track ID bukan identitas orang unik.",
            "Warna menilai helm saja; kandidat tanpa helm perlu ditinjau.",
            "Salinan pemutar: maksimal 720p dan 10 FPS; upload asli dipertahankan.",
        ],
    }
