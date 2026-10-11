"""Bounded acquisition and quality audit of public MEVA example annotations."""

import argparse
import hashlib
import json
import math
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
BUCKET = "https://mevadata-public-01.s3.amazonaws.com"
PREFIX = "examples/annotations/"
LICENSE_URL = "https://mevadata.org/resources/MEVA-data-license.txt"
README_URL = "https://mevadata.org/resources/README-meva-kf1-data.html"
FAQ_URL = "https://mevadata.org/transcoding-faq.html"
FILE_LIMIT = 2_000_000
VIDEO_LIMIT = 250_000_000
VIDEO_COUNT_LIMIT = 12
STEM = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})\.(?P<start>\d{2}-\d{2}-\d{2})"
    r"\.(?P<end>\d{2}-\d{2}-\d{2})\.(?P<place>[a-z]+)\.(?P<camera>G\d+)"
)
KEY = re.compile(
    r"examples/annotations/(?P<date>\d{4}-\d{2}-\d{2})/(?P<hour>\d{2})/"
    r"(?P<stem>[^/]+)\.(?P<kind>activities|geom|types)\.yml"
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def save_json(path, data):
    save(path, (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n").encode())


def get(url, limit, expected_size=None):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=45) as response:
                data = response.read(limit + 1)
                headers = {
                    key: response.headers.get(key)
                    for key in ("Content-Length", "ETag", "Last-Modified", "Content-Type")
                }
            if len(data) > limit or (expected_size is not None and len(data) != expected_size):
                raise ValueError(f"Unexpected response size: {url}")
            return data, headers
        except (OSError, urllib.error.URLError) as error:
            if attempt == 2:
                raise OSError(f"Download failed after three attempts: {url}") from error
            time.sleep(attempt + 1)
    raise AssertionError("unreachable")


def clip_info(stem):
    match = STEM.fullmatch(stem)
    if not match:
        raise ValueError(f"Unrecognized MEVA clip name: {stem}")
    fields = match.groupdict()
    # ponytail: MEVA supplies wall-clock filenames without a zone; compare only within one date.
    start = datetime.strptime(fields["date"] + "." + fields["start"], "%Y-%m-%d.%H-%M-%S")  # noqa: DTZ007
    end = datetime.strptime(fields["date"] + "." + fields["end"], "%Y-%m-%d.%H-%M-%S")  # noqa: DTZ007
    if start >= end:
        raise ValueError(f"Invalid clip time window: {stem}")
    return {
        **fields,
        "source_group": f"{fields['date']}/{fields['camera']}",
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
    }


def listing(xml):
    root = ET.fromstring(xml)
    if root.findtext("{*}IsTruncated") != "false":
        raise ValueError("MEVA listing is truncated")
    result: dict[str, dict] = {}
    groups = defaultdict(dict)
    for node in root.findall("{*}Contents"):
        key = node.findtext("{*}Key")
        match = KEY.fullmatch(key or "")
        if key is None or match is None or key in result:
            raise ValueError(f"Invalid or duplicate annotation key: {key}")
        fields = match.groupdict()
        info = clip_info(fields["stem"])
        if fields["date"] != info["date"] or fields["hour"] != info["end"][:2]:
            raise ValueError(f"Inconsistent annotation directory: {key}")
        size_text = node.findtext("{*}Size")
        if size_text is None:
            raise ValueError(f"Missing annotation size: {key}")
        size = int(size_text)
        if not 0 < size <= FILE_LIMIT:
            raise ValueError(f"Annotation exceeds byte bound: {key}")
        result[key] = {"bytes": size, "etag": node.findtext("{*}ETag")}
        kinds = groups[fields["stem"]]
        if fields["kind"] in kinds:
            raise ValueError(f"Duplicate annotation kind: {key}")
        kinds[fields["kind"]] = key
    if len(groups) != 64 or any(
        set(kinds) != {"activities", "geom", "types"} for kinds in groups.values()
    ):
        raise ValueError("Expected 64 complete public MEVA example triplets")
    return result, dict(sorted(groups.items()))


def spans(items):
    if not isinstance(items, list) or not items:
        raise ValueError("Missing MEVA timespan")
    result = []
    for item in items:
        pair = item.get("tsr0") if isinstance(item, dict) else None
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or any(type(value) is not int for value in pair)
            or pair[0] < 0
            or pair[1] < pair[0]
        ):
            raise ValueError(f"Invalid MEVA frame range: {pair}")
        result.append(pair)
    return result


def records(rows, key):
    if not isinstance(rows, list):
        raise TypeError("MEVA YAML must contain a list")
    result = []
    for row in rows:
        if not isinstance(row, dict) or len(row) != 1:
            raise ValueError("Invalid MEVA annotation row")
        if key in row:
            if not isinstance(row[key], dict):
                raise ValueError(f"Invalid MEVA {key} record")
            result.append(row[key])
        elif "meta" not in row:
            raise ValueError(f"Unexpected MEVA annotation row: {row}")
    return result


def class_map(value):
    if (
        not isinstance(value, dict)
        or not value
        or any(
            not isinstance(label, str)
            or not label
            or type(score) not in (int, float)
            or not math.isfinite(score)
            or score <= 0
            for label, score in value.items()
        )
    ):
        raise ValueError("Missing or invalid class mapping")
    return value


def actor_id(value):
    if type(value) is not int or value < 0:
        raise ValueError("Invalid clip-local actor ID")
    return value


def normalize(stem, activity_rows, geom_rows, type_rows):
    info = clip_info(stem)
    types = {}
    for row in records(type_rows, "types"):
        identity = actor_id(row.get("id1"))
        if identity in types:
            raise ValueError("Duplicate MEVA type ID")
        types[identity] = class_map(row.get("cset3"))
    geometry, seen, max_frame, extent = [], set(), -1, [0, 0]
    for row in records(geom_rows, "geom"):
        identity = actor_id(row.get("id1"))
        frame = row.get("ts0")
        if identity not in types:
            raise ValueError("Geometry references actor without type")
        if type(frame) is not int or frame < 0 or (identity, frame) in seen:
            raise ValueError("Invalid or duplicate geometry frame")
        seen.add((identity, frame))
        try:
            box = [float(value) for value in row["g0"].split()]
        except (KeyError, AttributeError, ValueError) as error:
            raise ValueError("Invalid MEVA bounding box") from error
        if (
            len(box) != 4
            or not all(math.isfinite(value) for value in box)
            or box[0] < 0
            or box[1] < 0
            or box[2] <= box[0]
            or box[3] <= box[1]
        ):
            raise ValueError("Invalid MEVA bounding box")
        timestamp = row.get("ts1")
        if type(timestamp) not in (int, float) or not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError("Invalid geometry timestamp")
        geometry.append(
            {"actor_id": identity, "frame": frame, "time_seconds": timestamp, "xyxy": box}
        )
        max_frame = max(max_frame, frame)
        extent = [max(extent[0], box[2]), max(extent[1], box[3])]
    activities, sequences, ids = [], defaultdict(list), set()
    for row in records(activity_rows, "act"):
        event_id = row.get("id2")
        if type(event_id) is not int or event_id < 0 or event_id in ids:
            raise ValueError("Invalid or duplicate activity ID")
        ids.add(event_id)
        labels = class_map(row.get("act3"))
        intervals = spans(row.get("timespan"))
        actors = row.get("actors")
        if not isinstance(actors, list) or not actors:
            raise ValueError("Activity requires actors")
        participants = []
        for actor in actors:
            identity = actor_id(actor.get("id1"))
            if identity not in types:
                raise ValueError("Activity references actor without type")
            actor_intervals = spans(actor.get("timespan"))
            participants.append({"actor_id": identity, "intervals": actor_intervals})
            for segment, (start, end) in enumerate(actor_intervals):
                sequences[identity].append(
                    {
                        "activity_id": event_id,
                        "segment": segment,
                        "labels": labels,
                        "start_frame": start,
                        "end_frame": end,
                    }
                )
        activities.append(
            {
                "activity_id": event_id,
                "labels": labels,
                "intervals": intervals,
                "actors": participants,
            }
        )
    sequence_rows, overlaps = [], []
    for identity, events in sorted(sequences.items()):
        events.sort(
            key=lambda event: (
                event["start_frame"],
                event["end_frame"],
                event["activity_id"],
                event["segment"],
            )
        )
        for left_index, left in enumerate(events):
            for right in events[left_index + 1 :]:
                if right["start_frame"] > left["end_frame"]:
                    break
                overlaps.append(
                    {
                        "actor_id": identity,
                        "left_activity_id": left["activity_id"],
                        "right_activity_id": right["activity_id"],
                        "left_segment": left["segment"],
                        "right_segment": right["segment"],
                    }
                )
        sequence_rows.append({"actor_id": identity, "events": events})
    summary = {
        "activities": len(activities),
        "geometry_rows": len(geometry),
        "typed_actors": len(types),
        "sequence_actors": len(sequence_rows),
        "overlapping_activity_segments": len(overlaps),
        "max_annotation_frame": max(
            max_frame, *(span[1] for activity in activities for span in activity["intervals"])
        ),
        "max_box_xy": extent,
        "activity_labels": dict(
            sorted(
                Counter(label for activity in activities for label in activity["labels"]).items()
            )
        ),
        "object_labels": dict(
            sorted(Counter(label for labels in types.values() for label in labels).items())
        ),
    }
    return {
        "clip": stem,
        "source": info,
        "types": [
            {"actor_id": identity, "classes": labels} for identity, labels in sorted(types.items())
        ],
        "geometry": geometry,
        "activities": activities,
        "actor_sequences": sequence_rows,
        "overlapping_activity_segments": overlaps,
        "sequence_semantics": "clip-local actor order by start/end/ID; overlap is co-occurrence, not strict causal order",
        "qa": summary,
    }


def video_candidates(groups, count, dates=None):
    if type(count) is not int or not 0 <= count <= VIDEO_COUNT_LIMIT:
        raise ValueError(f"--videos must be 0..{VIDEO_COUNT_LIMIT}")
    if dates is not None:
        if len(dates) != count or count > 4 or len(set(dates)) != count:
            raise ValueError("--video-dates needs 1..4 unique dates and the same --videos count")
        by_date = {}
        for stem in sorted(groups):
            date = clip_info(stem)["date"]
            if date in dates:
                by_date.setdefault(date, stem)
        if set(by_date) != set(dates):
            raise ValueError("Requested date lacks a public example clip")
        return [by_date[date] for date in sorted(dates)]
    by_group = {}
    for stem in sorted(groups):
        group = clip_info(stem)["source_group"]
        by_group.setdefault(group, stem)
    return [by_group[group] for group in sorted(by_group)[:count]]


def video_info(path, annotation):
    result = json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,r_frame_rate,nb_frames:format=duration",
                "-of",
                "json",
                str(path),
            ],
            text=True,
            timeout=45,
        )
    )
    stream = result["streams"][0]
    width, height = int(stream["width"]), int(stream["height"])
    num, den = map(int, stream["r_frame_rate"].split("/"))
    fps = num / den
    duration = float(result["format"]["duration"])
    frame_count = int(stream["nb_frames"]) if stream.get("nb_frames", "N/A").isdigit() else None
    if (
        width <= 0
        or height <= 0
        or not math.isfinite(fps)
        or fps <= 0
        or not math.isfinite(duration)
        or duration <= 0
    ):
        raise ValueError("Invalid video stream metadata")
    if frame_count is not None and annotation["qa"]["max_annotation_frame"] >= frame_count:
        raise ValueError("Annotation frame exceeds video frame count")
    max_x, max_y = annotation["qa"]["max_box_xy"]
    delta = max(
        (abs(row["time_seconds"] - row["frame"] / fps) for row in annotation["geometry"]),
        default=0.0,
    )
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "duration_seconds": duration,
        "frame_count": frame_count,
        "max_annotation_frame": annotation["qa"]["max_annotation_frame"],
        "max_annotation_time_seconds_at_video_fps": annotation["qa"]["max_annotation_frame"] / fps,
        "annotation_boxes_fit_video_dimensions": max_x <= width and max_y <= height,
        "max_geometry_timestamp_delta_seconds": delta,
        "geometry_timestamps_within_one_video_frame": delta <= 1 / fps,
        "coordinate_transform": {
            "status": "unverified source coordinate dimensions",
            "annotation_max_xy": [max_x, max_y],
            "video_dimensions": [width, height],
            "scale_xy": None,
            "reason": "Observed box extent does not establish original canvas dimensions",
        },
        "time_mapping": "MEVA ts0/tsr0 frame indices checked against r13 frame count; ts1 and clip duration retained",
        "decode_status": "ffprobe metadata only; full-frame decode not audited",
    }


def download_video(output, stem, info):
    key = f"drops-123-r13/{info['date']}/{info['end'][:2]}/{stem}.r13.avi"
    url = BUCKET + "/" + urllib.parse.quote(key, safe="/")
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as response:
        expected = int(response.headers["Content-Length"])
        etag = response.headers.get("ETag")
    if not 0 < expected <= VIDEO_LIMIT:
        raise ValueError(f"Video exceeds {VIDEO_LIMIT} byte bound: {stem}")
    path = output / "videos" / f"{stem}.r13.avi"
    path.parent.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(url, timeout=90) as response, path.open("xb") as target:
        while chunk := response.read(1 << 20):
            total += len(chunk)
            if total > expected:
                raise ValueError("Video exceeds declared size")
            sha.update(chunk)
            target.write(chunk)
    if total != expected:
        raise ValueError("Incomplete MEVA video download")
    return path, {
        "source_key": key,
        "url": url,
        "bytes": total,
        "sha256": sha.hexdigest(),
        "etag": etag,
    }


def collect(output, videos=0, reuse_annotations=None, video_dates=None):
    output = Path(output)
    if output.exists() or not output.resolve().is_relative_to((ROOT / "data/public").resolve()):
        raise ValueError("Choose a fresh --output inside industrial_ai/data/public")
    if type(videos) is not int or not 0 <= videos <= VIDEO_COUNT_LIMIT:
        raise ValueError(f"--videos must be 0..{VIDEO_COUNT_LIMIT}")
    reuse = Path(reuse_annotations) if reuse_annotations is not None else None
    if reuse is not None:
        if not reuse.resolve().is_relative_to((ROOT / "data/public").resolve()):
            raise ValueError("--reuse-annotations must reference a dataset in data/public")
        old = json.loads((reuse / "manifest.json").read_text(encoding="utf-8"))
        if old.get("status") != "completed" or len(old.get("annotations", {})) != 192:
            raise ValueError("Reuse source lacks a completed 192-file annotation manifest")
        xml = (reuse / "source-listing.xml").read_bytes()
        license_text = (reuse / "MEVA-data-license.txt").read_bytes()
        if (
            digest(xml) != old["protocol"]["listing_sha256"]
            or digest(license_text) != old["protocol"]["license_sha256"]
        ):
            raise ValueError("Reuse source listing/license hash mismatch")
    else:
        query = BUCKET + "/?list-type=2&prefix=" + urllib.parse.quote(PREFIX, safe="")
        xml, _ = get(query, 100_000)
        license_text, _ = get(LICENSE_URL, 100_000)
    files, groups = listing(xml)
    if b"Attribution 4.0 International" not in license_text:
        raise ValueError("MEVA source license changed or could not be verified")
    selected_videos = video_candidates(groups, videos, video_dates)
    output.mkdir(parents=True)
    save(output / "source-listing.xml", xml)
    save(output / "MEVA-data-license.txt", license_text)
    protocol = {
        "source": BUCKET,
        "annotation_prefix": PREFIX,
        "license_url": LICENSE_URL,
        "license": "CC BY 4.0",
        "readme_url": README_URL,
        "transcoding_faq_url": FAQ_URL,
        "listing_sha256": digest(xml),
        "license_sha256": digest(license_text),
        "collector_sha256": digest(Path(__file__).read_bytes()),
        "annotation_triplets": len(groups),
        "selection": (
            "all public example triplets; first lexicographic clip per requested date"
            if video_dates is not None
            else "all public example triplets; video earliest lexicographic clip per distinct date/camera group"
        ),
        "requested_video_dates": video_dates,
        "video_count_limit": VIDEO_COUNT_LIMIT,
        "video_byte_limit_each": VIDEO_LIMIT,
        "selected_videos": selected_videos,
        "reused_annotations_from": str(reuse.resolve()) if reuse is not None else None,
        "split_policy": "Do not split same date/camera or overlapping date/time windows across train/dev/test; date-level holdout is simplest safe assignment. No split is assigned here.",
        "annotation_scope": "Sparse, activity-targeted MEVA examples; unlabeled frames/objects are unknown, never negatives.",
        "identity_scope": "id1 is clip-local annotation linkage only; no person re-identification or biometric identity.",
        "use": "acquisition and QA only; no model training, inference, IDF1, or whole-video score",
    }
    save_json(output / "protocol.json", protocol)
    provenance, clips, hashes = {}, [], {}
    for stem, kinds in groups.items():
        loaded = {}
        for kind, key in sorted(kinds.items()):
            path = output / key
            if reuse is None:
                data, headers = get(
                    BUCKET + "/" + urllib.parse.quote(key, safe="/"),
                    FILE_LIMIT,
                    files[key]["bytes"],
                )
            else:
                data = (reuse / key).read_bytes()
                previous = old["annotations"][key]
                if len(data) != files[key]["bytes"] or digest(data) != previous["sha256"]:
                    raise ValueError(f"Reuse annotation hash mismatch: {key}")
                headers = previous["headers"]
            save(path, data)
            hashes[key] = digest(data)
            provenance[key] = {
                "url": BUCKET + "/" + key,
                "bytes": len(data),
                "sha256": digest(data),
                "listing_etag": files[key]["etag"],
                "headers": headers,
            }
            loaded[kind] = yaml.safe_load(data)
        clip = normalize(stem, loaded["activities"], loaded["geom"], loaded["types"])
        save_json(output / "normalized" / f"{stem}.json", clip)
        clips.append(
            {
                "clip": stem,
                "source_group": clip["source"]["source_group"],
                "window_start": clip["source"]["window_start"],
                "window_end": clip["source"]["window_end"],
                **clip["qa"],
            }
        )
        print(
            json.dumps({"annotation_clip": stem, "activities": clip["qa"]["activities"]}),
            flush=True,
        )
    video_receipts = {}
    for stem in selected_videos:
        clip_path = output / "normalized" / f"{stem}.json"
        clip = json.loads(clip_path.read_text(encoding="utf-8"))
        path, receipt = download_video(output, stem, clip["source"])
        receipt["probe"] = video_info(path, clip)
        video_receipts[stem] = receipt
        print(json.dumps({"video_clip": stem, "bytes": receipt["bytes"]}), flush=True)
    summary = {
        "status": "completed",
        "protocol": protocol,
        "annotations": provenance,
        "videos": video_receipts,
        "clips": clips,
        "sha256_annotations": hashes,
        "qa_totals": {
            "activities": sum(c["activities"] for c in clips),
            "geometry_rows": sum(c["geometry_rows"] for c in clips),
            "typed_actors": sum(c["typed_actors"] for c in clips),
            "overlapping_activity_segments": sum(c["overlapping_activity_segments"] for c in clips),
            "labels": dict(
                sorted(
                    Counter(
                        label
                        for c in clips
                        for label, count in c["activity_labels"].items()
                        for _ in range(count)
                    ).items()
                )
            ),
        },
        "evaluated_exposure_seconds": 0,
        "limitations": [
            "Example annotations are sparse and activity-targeted; unlabeled intervals are not negatives.",
            "Clip-local actor IDs and overlapping activities do not establish global identities or strict causal chains.",
            "No model was trained or evaluated; no whole-video IDF1 or accuracy claims.",
        ],
    }
    save_json(output / "manifest.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--videos", type=int, default=0, help="0..12 fixed candidates; default annotations only"
    )
    parser.add_argument(
        "--reuse-annotations", type=Path, help="Reuse a completed local annotation snapshot"
    )
    parser.add_argument(
        "--video-dates", nargs="+", help="1..4 source dates; first lexicographic clip per date"
    )
    args = parser.parse_args()
    try:
        report = collect(args.output, args.videos, args.reuse_annotations, args.video_dates)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        yaml.YAMLError,
        subprocess.SubprocessError,
    ) as error:
        parser.exit(2, f"MEVA collector: {error}\n")
    print(
        json.dumps(
            {
                "clips": len(report["clips"]),
                "annotations": len(report["annotations"]),
                "videos": len(report["videos"]),
                "evaluated_seconds": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
