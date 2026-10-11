"""Import explicitly reviewed CVAT video boxes into a separate reference receipt.

Review JSON: reviewer, video_sha256, cvat_xml_sha256, excluded_labels,
canvas [width,height], fps (exact rational), frame_count, coverage [[start,end), ...],
frame_policy="dense_explicit".
Only covered frames become reference rows; empty covered frames are declared negatives.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import xml.etree.ElementTree as ET
from bisect import bisect_left
from collections import defaultdict
from fractions import Fraction
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAX_XML_BYTES = 32_000_000
MAX_REVIEW_BYTES = 1_000_000
MAX_COVERED_FRAMES = 250_000
LABELS = {"person": "gt", "head": "heads", "helmet": "helmets"}
STATUSES = {"worn", "not_worn", "unknown"}
VISIBILITY = {"visible", "occluded", "unknown"}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def bounded(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"Input exceeds {limit} bytes: {path.name}")
    return data


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate review JSON key: {key}")
        result[key] = value
    return result


def positive_int(value: object, name: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def review_data(path: Path) -> tuple[dict, Fraction, str]:
    raw = bounded(path, MAX_REVIEW_BYTES)
    data = json.loads(
        raw,
        object_pairs_hook=unique_object,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"Invalid JSON number: {value}")
        ),
    )
    if not isinstance(data, dict) or set(data) != {
        "reviewer",
        "video_sha256",
        "cvat_xml_sha256",
        "excluded_labels",
        "canvas",
        "fps",
        "frame_count",
        "coverage",
        "frame_policy",
    }:
        raise ValueError(
            "Review JSON requires reviewer, video/XML SHA256, excluded_labels, canvas, fps, frame_count, coverage and frame_policy"
        )
    if not isinstance(data["reviewer"], str) or not 0 < len(data["reviewer"].strip()) <= 256:
        raise ValueError("Nonempty reviewer identity declaration required")
    for name in ("video_sha256", "cvat_xml_sha256"):
        if not isinstance(data[name], str) or not re.fullmatch(r"[0-9a-f]{64}", data[name]):
            raise ValueError(f"Lowercase {name} required")
    exclusions = data["excluded_labels"]
    if (
        not isinstance(exclusions, list)
        or any(
            not isinstance(label, str)
            or not label
            or label != label.strip().lower()
            or label in LABELS
            for label in exclusions
        )
        or len(exclusions) != len(set(exclusions))
    ):
        raise ValueError("Excluded labels must be distinct lowercase non-target labels")
    canvas = data["canvas"]
    if not isinstance(canvas, list) or len(canvas) != 2:
        raise ValueError("Canvas must contain width and height")
    for dimension in canvas:
        positive_int(dimension, "Canvas dimension")
    positive_int(data["frame_count"], "Frame count")
    if isinstance(data["fps"], bool) or not isinstance(data["fps"], (str, int, float)):
        raise TypeError("Invalid FPS type")
    try:
        fps = Fraction(str(data["fps"]))
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError("FPS must be an exact positive rational") from error
    if fps <= 0:
        raise ValueError("FPS must be positive")
    if data["frame_policy"] != "dense_explicit":
        raise ValueError("Only dense_explicit frame policy is supported")
    coverage = data["coverage"]
    if not isinstance(coverage, list) or not coverage:
        raise ValueError("Explicit reviewed coverage required")
    previous_end = -1
    total = 0
    for pair in coverage:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or any(type(value) is not int for value in pair)
            or pair[0] < 0
            or pair[0] >= pair[1]
            or pair[1] > data["frame_count"]
            or pair[0] < previous_end
        ):
            raise ValueError(
                "Coverage must contain sorted, non-overlapping [start,end) frame intervals"
            )
        previous_end = pair[1]
        total += pair[1] - pair[0]
    # ponytail: cap review receipts at 250k frames; stream/partition after larger footage is needed.
    if total > MAX_COVERED_FRAMES:
        raise ValueError("Reviewed coverage exceeds frame ceiling")
    return data, fps, hashlib.sha256(raw).hexdigest()


def probe_video(video: Path, review: dict, fps: Fraction) -> None:
    if sha256(video) != review["video_sha256"]:
        raise ValueError("Source video SHA256 differs from review declaration")
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=width,height,avg_frame_rate,nb_read_frames",
            "-of",
            "json",
            str(video),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=600,
    )
    streams = json.loads(result.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("Source video must contain one readable first video stream")
    stream = streams[0]
    if sha256(video) != review["video_sha256"]:
        raise ValueError("Source video changed during metadata probe")
    if (
        [stream.get("width"), stream.get("height")] != review["canvas"]
        or stream.get("nb_read_frames") != str(review["frame_count"])
        or Fraction(stream.get("avg_frame_rate", "0")) != fps
    ):
        raise ValueError(
            "Source video canvas, FPS or decoded frame count differs from review declaration"
        )


def attributes(box: ET.Element) -> dict[str, str]:
    result = {}
    for child in box:
        name = child.get("name")
        if child.tag != "attribute" or not name or name in result:
            raise ValueError("Invalid or duplicate CVAT box attribute")
        result[name] = (child.text or "").strip()
    return result


def cvat_data(raw: bytes, review: dict) -> tuple[dict[str, dict[int, list]], list[str]]:
    if b"\x00" in raw or re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b", raw, re.IGNORECASE):
        raise ValueError("Only UTF-8 CVAT XML without DTD or entities is supported")
    root = ET.fromstring(raw)
    if root.tag != "annotations" or any(
        child.tag not in {"version", "meta", "track"} for child in root
    ):
        raise ValueError("Expected CVAT video track XML")
    task = root.find("meta/task")
    if task is None or task.findtext("mode") != "interpolation":
        raise ValueError("Expected CVAT video interpolation task metadata")
    try:
        size = int(task.findtext("size", ""))
        width = int(task.findtext("original_size/width", ""))
        height = int(task.findtext("original_size/height", ""))
    except ValueError as error:
        raise ValueError("CVAT video size and canvas metadata required") from error
    if size != review["frame_count"] or [width, height] != review["canvas"]:
        raise ValueError("CVAT task metadata differs from reviewed source video")
    covered = review["coverage"]
    merged = []
    for start, end in covered:
        if merged and start == merged[-1][1]:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    rows: dict[str, dict[int, list]] = {label: defaultdict(list) for label in LABELS}
    ignored = set()
    track_ids = set()
    for track in root.findall("track"):
        try:
            identity = int(track.attrib["id"])
            label = track.attrib["label"].strip().lower()
        except (KeyError, ValueError) as error:
            raise ValueError("CVAT track requires numeric ID and label") from error
        if identity < 0 or identity in track_ids or not label:
            raise ValueError("Duplicate or invalid CVAT track ID/label")
        track_ids.add(identity)
        if label not in LABELS:
            if label not in review["excluded_labels"]:
                raise ValueError(f"Undeclared CVAT track label: {label}")
            ignored.add(label)
        states = {}
        previous = -1
        active = False
        for box in track:
            if box.tag == "attribute":
                if box.get("name") in {"helmet_status", "head_visibility"}:
                    raise ValueError(
                        "Helmet status and head visibility must be per-frame box attributes"
                    )
                continue
            if box.tag != "box":
                raise ValueError("Only CVAT box tracks are supported")
            try:
                frame = int(box.attrib["frame"])
                outside = int(box.attrib["outside"])
                keyframe = int(box.attrib["keyframe"])
                occluded = int(box.attrib["occluded"])
                bbox = [float(box.attrib[name]) for name in ("xtl", "ytl", "xbr", "ybr")]
            except (KeyError, ValueError) as error:
                raise ValueError("Invalid CVAT box metadata") from error
            if (
                not previous < frame < review["frame_count"]
                or frame < 0
                or outside not in (0, 1)
                or keyframe not in (0, 1)
                or occluded not in (0, 1)
                or not all(math.isfinite(value) for value in bbox)
                or not (0 <= bbox[0] < bbox[2] <= width and 0 <= bbox[1] < bbox[3] <= height)
            ):
                raise ValueError("Invalid frame, state or on-canvas positive-area CVAT box")
            if outside and not active:
                raise ValueError("Outside marker without preceding visible box")
            active = not outside
            previous = frame
            attrs = attributes(box)
            status = attrs.get("helmet_status", "unknown")
            visibility = attrs.get("head_visibility")
            if status not in STATUSES or (visibility is not None and visibility not in VISIBILITY):
                raise ValueError("Invalid helmet status or head visibility")
            if status != "unknown" and visibility != "visible":
                raise ValueError("Known helmet status requires visible head declaration")
            states[frame] = (outside, keyframe, occluded, bbox, status, visibility)
        if not states:
            raise ValueError("CVAT track contains no boxes")
        if label not in LABELS:
            continue
        frames = list(states)
        for start, end in merged:
            lo, hi = bisect_left(frames, start), bisect_left(frames, end)
            selected = frames[lo:hi]
            if lo and not states[frames[lo - 1]][0] and (not selected or selected[0] != start):
                raise ValueError(
                    "Visible track crosses review boundary without explicit first-frame state"
                )
            if selected and states[selected[0]][0] and selected[0] != start:
                raise ValueError("Outside marker follows unlabelled reviewed frames")
            for left, right in pairwise(selected):
                if not states[left][0] and right != left + 1:
                    raise ValueError(
                        "Sparse visible CVAT track would create unlabelled reviewed frames"
                    )
            if selected and not states[selected[-1]][0] and selected[-1] != end - 1:
                raise ValueError(
                    "Visible CVAT track ends before reviewed coverage without outside marker"
                )
            for frame in selected:
                outside, keyframe, occluded, bbox, status, visibility = states[frame]
                if keyframe != 1:
                    raise ValueError("Interpolated CVAT boxes cannot be used as reviewed reference")
                if outside or label not in LABELS:
                    continue
                row = {"track_id": identity, "bbox": bbox, "occluded": bool(occluded)}
                if label == "person":
                    row["helmet_status"] = status
                    if visibility is not None:
                        row["head_visibility"] = visibility
                rows[label][frame].append(row)
    if set(review["excluded_labels"]) != ignored:
        raise ValueError("Declared excluded labels differ from CVAT labels")
    return rows, sorted(ignored)


def import_reference(xml_path: Path, review_path: Path, video_path: Path, output: Path) -> dict:
    xml_path = Path(xml_path).resolve()
    review_path = Path(review_path).resolve()
    video_path = Path(video_path).resolve()
    output = Path(output).resolve()
    if not any(
        output != base.resolve() and output.is_relative_to(base.resolve())
        for base in (ROOT / ".tmp", ROOT / "reports/runtime")
    ):
        raise ValueError("Use a fresh output directory below industrial_ai/.tmp or reports/runtime")
    if output.exists():
        raise FileExistsError(output)
    review, fps, review_hash = review_data(review_path)
    raw = bounded(xml_path, MAX_XML_BYTES)
    xml_hash = hashlib.sha256(raw).hexdigest()
    if xml_hash != review["cvat_xml_sha256"]:
        raise ValueError("CVAT XML SHA256 differs from review declaration")
    probe_video(video_path, review, fps)
    rows, ignored = cvat_data(raw, review)
    output.mkdir(parents=True, exist_ok=False)
    destination = output / "annotations.jsonl"
    counts = {label: 0 for label in LABELS}
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        for start, end in review["coverage"]:
            for frame in range(start, end):
                item = {"frame": frame, "seconds": float(Fraction(frame, 1) / fps)}
                for label, key in LABELS.items():
                    selected_rows = sorted(
                        rows[label].get(frame, []), key=lambda row: row["track_id"]
                    )
                    item[key] = selected_rows
                    counts[label] += len(selected_rows)
                stream.write(json.dumps(item, sort_keys=True, allow_nan=False) + "\n")
    manifest = {
        "schema_version": 1,
        "provenance": "human_review_declared_identity_not_verified",
        "reviewer": review["reviewer"],
        "source_video_sha256": review["video_sha256"],
        "cvat_xml_sha256": xml_hash,
        "review_json_sha256": review_hash,
        "annotations_jsonl_sha256": sha256(destination),
        "canvas": review["canvas"],
        "fps": str(fps),
        "frame_count": review["frame_count"],
        "coverage": review["coverage"],
        "covered_frames": sum(end - start for start, end in review["coverage"]),
        "frame_policy": "dense_explicit_no_interpolation",
        "empty_covered_frames": "reviewer_declared_negative",
        "outside_coverage": "unknown_no_output_row",
        "counts": counts,
        "excluded_labels": ignored,
        "ignored_labels": ignored,
    }
    with (output / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("xml", "review", "video", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    manifest = import_reference(args.xml, args.review, args.video, args.output)
    print(json.dumps({"output": str(args.output), "covered_frames": manifest["covered_frames"]}))


if __name__ == "__main__":
    main()
