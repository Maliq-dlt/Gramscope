"""Bounded public SDD reference acquisition; no training, inference or identity claims."""

import argparse
import hashlib
import json
import math
import stat
import subprocess
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from PIL import Image

ROOT = Path(__file__).resolve().parent
REF = "aryashah2k/stanford-drone-dataset"
API = "https://www.kaggle.com/api/v1/datasets"
ORIGINAL = "https://cvgl.stanford.edu/projects/uav_data/"
LICENSE = "CC-BY-NC-SA-3.0"
VIDEO_BUDGET, AUX_BUDGET = 200_000_000, 100_000_000
CANDIDATES = [(scene, index) for scene in ("coupa", "hyang") for index in range(4)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)


def metadata(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        if "json" not in response.headers.get("Content-Type", ""):
            raise ValueError("Public metadata returned an unexpected content type")
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("Metadata exceeds bound")
    return json.loads(data)


def select(files):
    lookup = {row["name"]: row["totalBytes"] for row in files}
    selected, excluded, video_bytes, auxiliary_bytes = [], [], 0, 0
    for scene, index in CANDIDATES:
        clip = f"{scene}/video{index}"
        paths = [
            f"video/{clip}/video.mp4",
            f"annotations/{clip}/annotations.txt",
            f"annotations/{clip}/reference.jpg",
        ]
        if any(path not in lookup for path in paths):
            raise ValueError(f"Missing fixed candidate files: {clip}")
        sizes = [lookup[path] for path in paths]
        if any(type(size) is not int or size <= 0 for size in sizes):
            raise ValueError("Files require positive declared sizes")
        if (
            excluded
            or video_bytes + sizes[0] > VIDEO_BUDGET
            or auxiliary_bytes + sum(sizes[1:]) > AUX_BUDGET
        ):
            excluded.append({"clip": clip, "reason": "fixed priority prefix exceeds byte budget"})
            continue
        selected.append({"clip": clip, "source_group": scene, "files": dict(zip(paths, sizes))})
        video_bytes += sizes[0]
        auxiliary_bytes += sum(sizes[1:])
    return selected, excluded


def unpack(raw, output, expected_name, max_bytes):
    """A single expected ZIP member only; never extractall or trust member paths."""
    if zipfile.is_zipfile(raw):
        with zipfile.ZipFile(raw) as archive:
            entries = archive.infolist()
            if len(entries) != 1:
                raise ValueError("Expected exactly one archive member")
            entry = entries[0]
            path = PurePosixPath(entry.filename)
            if (
                entry.filename != expected_name
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in entry.filename
                or entry.is_dir()
                or entry.flag_bits & 1
                or stat.S_ISLNK(entry.external_attr >> 16)
                or entry.file_size > max_bytes
                or entry.file_size > max(1, entry.compress_size) * 1000
            ):
                raise ValueError("Unsafe or oversized archive member")
            source = archive.open(entry)
            with source, output.open("xb") as target:
                total = 0
                while chunk := source.read(1 << 20):
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("Archive output exceeds bound")
                    target.write(chunk)
    else:
        if raw.stat().st_size > max_bytes:
            raise ValueError("Raw output exceeds bound")
        with raw.open("rb") as source, output.open("xb") as target:
            while chunk := source.read(1 << 20):
                target.write(chunk)


def download(path, output, declared_size):
    url = f"{API}/download/{REF}/" + urllib.parse.quote(path, safe="")
    raw = output.with_name(output.name + ".download")
    limit = declared_size + 1_000_000
    with urllib.request.urlopen(url, timeout=60) as response, raw.open("xb") as target:
        headers = {
            key: response.headers.get(key)
            for key in ("Content-Type", "Content-Length", "Content-Range")
        }
        total = 0
        while chunk := response.read(1 << 20):
            total += len(chunk)
            if total > limit:
                raise ValueError("Download exceeds declared byte bound")
            target.write(chunk)
    content_range = headers["Content-Range"]
    if content_range:
        positions, expected = content_range.removeprefix("bytes ").split("/")
        first, last = map(int, positions.split("-"))
        if first != 0 or last + 1 != int(expected) or total != int(expected):
            raise ValueError("Incomplete ranged response; preserve partial download")
    unpack(raw, output, PurePosixPath(path).name, declared_size)
    if output.stat().st_size != declared_size:
        raise ValueError("Extracted file differs from frozen declared size")
    return {
        "download_url": url,
        "headers": headers,
        "declared_bytes": declared_size,
        "download_bytes": total,
        "raw_sha256": sha(raw),
        "sha256": sha(output),
        "extracted_bytes": output.stat().st_size,
    }


def inspect(clip):
    info = json.loads(
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
                str(clip / "video.mp4"),
            ],
            text=True,
            timeout=30,
        )
    )
    stream = info["streams"][0]
    duration = float(info["format"]["duration"])
    numerator, denominator = map(float, stream["r_frame_rate"].split("/"))
    fps = numerator / denominator
    if not math.isfinite(duration) or duration <= 0 or not math.isfinite(fps) or fps <= 0:
        raise ValueError("Video requires positive duration and FPS")
    with Image.open(clip / "reference.jpg") as image:
        reference = image.size
    video = stream["width"], stream["height"]
    rows, max_frame, classes, outside = 0, -1, set(), 0
    with (clip / "annotations.txt").open(encoding="utf-8") as source:
        for line in source:
            fields = line.split()
            if len(fields) != 10:
                raise ValueError("Expected ten-column SDD annotation")
            numbers = list(map(int, fields[:9]))
            identity, left, top, right, bottom, frame, lost, occluded, generated = numbers
            if (
                identity < 0
                or frame < 0
                or left > right
                or top > bottom
                or any(flag not in (0, 1) for flag in (lost, occluded, generated))
            ):
                raise ValueError("Invalid SDD tracking annotation")
            outside += int(left < 0 or top < 0 or right > reference[0] or bottom > reference[1])
            rows += 1
            max_frame = max(max_frame, frame)
            classes.add(fields[9].strip('"'))
    return {
        "duration_seconds": duration,
        "fps": fps,
        "video_dimensions": video,
        "reference_dimensions": reference,
        "annotation_rows": rows,
        "max_annotation_frame": max_frame,
        "classes": sorted(classes),
        "boxes_outside_reference": outside,
        "coordinate_scale": [video[0] / reference[0], video[1] / reference[1]],
        "coordinate_transform_required": video != reference,
        "annotation_time_seconds": (max_frame + 1) / fps,
        "time_alignment_delta_seconds": duration - (max_frame + 1) / fps,
        "evaluated_exposure_seconds": 0,
        "inference_status": "not started",
    }


def collect(output):
    output = Path(output)
    if not output.resolve().is_relative_to((ROOT / "data/public").resolve()) or output.exists():
        raise ValueError("Choose a fresh output inside industrial_ai/data/public")
    dataset = metadata(f"{API}/view/{REF}")
    listing = metadata(f"{API}/list/{REF}?pageSize=200")
    if dataset.get("isPrivate") or listing.get("nextPageToken"):
        raise ValueError("Expected complete public fixed-size dataset listing")
    selected, excluded = select(listing["datasetFiles"])
    output.mkdir(parents=True)
    protocol = {
        "dataset_ref": REF,
        "kaggle_url": f"https://www.kaggle.com/datasets/{REF}",
        "original_url": ORIGINAL,
        "original_license": LICENSE,
        "license_url": "https://creativecommons.org/licenses/by-nc-sa/3.0/",
        "mirror_license": dataset["licenseName"],
        "license_discrepancy": "Original NC-SA overrides mirror CC0",
        "original_license_evidence": (
            "Stanford original page accessed 2026-10-11 states datasets published under "
            "Creative Commons Attribution-NonCommercial-ShareAlike 3.0 License"
        ),
        "collector_sha256": sha(Path(__file__)),
        "version": dataset["currentVersionNumber"],
        "video_budget_bytes": VIDEO_BUDGET,
        "auxiliary_budget_bytes": AUX_BUDGET,
        "selection": "fixed coupa0..3,hyang0..3 priority prefix within budget; no model results",
        "selected": selected,
        "excluded": excluded,
        "use": "unscored tracking reference; no training on evaluation videos",
        "source_group_policy": "scene group; re-encodes and annotations stay with original video",
    }
    save(output / "protocol.json", protocol)
    save(output / "dataset_metadata.json", dataset)
    save(output / "file_listing.json", listing)
    downloads, clips = {}, []
    for entry in selected:
        clip = output / entry["clip"]
        clip.mkdir(parents=True)
        for path, declared in entry["files"].items():
            downloads[path] = download(path, clip / PurePosixPath(path).name, declared)
        details = {"clip": entry["clip"], "source_group": entry["source_group"], **inspect(clip)}
        clips.append(details)
        save(clip / "provenance.json", details)
        print(
            json.dumps(
                {"downloaded": entry["clip"], "duration_seconds": details["duration_seconds"]}
            ),
            flush=True,
        )
    duration = math.fsum(row["duration_seconds"] for row in clips)
    manifest = {
        "status": "completed",
        "phase": "C3-acquisition",
        "protocol": protocol,
        "downloads": downloads,
        "clips": clips,
        "raw_exposure_seconds": duration,
        "raw_exposure_30min": duration >= 1800,
        "evaluated_exposure_seconds": 0,
        "files": {
            str(p.relative_to(output).as_posix()): sha(p) for p in output.rglob("*") if p.is_file()
        },
        "limitations": [
            "No tracking inference, IDF1 or helmet labels.",
            "Raw exposure is not evaluated exposure.",
            "Original annotations include interpolated, lost and occluded boxes.",
        ],
    }
    save(output / "manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = collect(args.output)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(2, f"SDD collector: {error}\n")
    print(
        json.dumps(
            {
                "clips": len(manifest["clips"]),
                "raw_seconds": manifest["raw_exposure_seconds"],
                "evaluated_seconds": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
