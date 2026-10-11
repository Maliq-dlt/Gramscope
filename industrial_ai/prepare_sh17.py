"""Acquire official SH17 v1 and audit labels/images; head is never nohelmet."""

import argparse
import hashlib
import json
import math
import re
import shutil
import stat
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
URL = "https://www.kaggle.com/api/v1/datasets/download/mugheesahmad/sh17-dataset-for-ppe-detection?datasetVersionNumber=1"
MAX_ARCHIVE = 15_000_000_000
MAX_EXPANDED = 20_000_000_000
NAMES = [
    "person",
    "ear",
    "ear-mufs",
    "face",
    "face-guard",
    "face-mask",
    "foot",
    "tool",
    "glasses",
    "gloves",
    "helmet",
    "hands",
    "head",
    "medical-suit",
    "shoes",
    "safety-suit",
    "safety-vest",
]


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)


def extract(archive, output):
    """Validate the complete archive before writing any untrusted member."""
    with zipfile.ZipFile(archive) as source:
        files = source.infolist()
        seen, total = set(), 0
        for item in files:
            name = PurePosixPath(item.filename)
            total += item.file_size
            if (
                not name.parts
                or any(
                    part in {".", ".."}
                    or part.rstrip(" .") != part
                    or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?", part)
                    for part in name.parts
                )
                or name.is_absolute()
                or ".." in name.parts
                or "\\" in item.filename
                or ":" in item.filename
                or item.flag_bits & 1
                or stat.S_ISLNK(item.external_attr >> 16)
                or item.filename.casefold() in seen
                or item.file_size > 100_000_000
                or total > MAX_EXPANDED
                or item.file_size > max(1, item.compress_size) * 1000
            ):
                raise ValueError("Unsafe/oversized/duplicate archive member")
            seen.add(item.filename.casefold())
        output.mkdir()
        for item in files:
            target = output.joinpath(*PurePosixPath(item.filename).parts)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(item) as incoming, target.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing, 1 << 20)
                if target.stat().st_size != item.file_size:
                    raise ValueError("Incomplete extracted member")
    return len(files)


def parse_label(text):
    labels = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 5:
            raise ValueError("Expected class and normalized xywh")
        cls, x, y, w, h = map(float, fields)
        if (
            not all(math.isfinite(v) for v in (cls, x, y, w, h))
            or cls != int(cls)
            or not 0 <= cls < 17
            or w <= 0
            or h <= 0
            or min(x - w / 2, y - h / 2) < -1e-6
            or max(x + w / 2, y + h / 2) > 1 + 1e-6
        ):
            raise ValueError("Invalid SH17 normalized box")
        labels.append([int(cls), x, y, w, h])
    return labels


def acquire(output):
    if output.exists() or not output.resolve().is_relative_to((ROOT / "data/public").resolve()):
        raise ValueError("Choose a fresh directory inside data/public")
    output.mkdir(parents=True)
    save(
        output / "protocol.json",
        {
            "dataset": "mugheesahmad/sh17-dataset-for-ppe-detection",
            "version": 1,
            "official": "https://github.com/ahmadmughees/SH17dataset",
            "url": URL,
            "license": "CC-BY-NC-SA-4.0 + Pexels source restrictions",
            "class_names": NAMES,
            "head_is_nohelmet": False,
            "selection": "complete v1 archive, no model-based selection",
            "collector_sha256": sha(Path(__file__)),
            "limitations": [
                "Photographer metadata requires grouping audit; cross-photographer session links remain unknown",
                "Pexels photographs are not CCTV or worn-PPE association truth",
            ],
        },
    )
    raw = output / "dataset.zip.partial"
    request = urllib.request.Request(URL)
    with urllib.request.urlopen(request, timeout=90) as response, raw.open("xb") as stream:
        expected = int(response.headers.get("Content-Length", 0))
        if not 0 < expected <= MAX_ARCHIVE or response.status != 200:
            raise ValueError("Expected bounded full public dataset archive")
        count, last = 0, 0
        while chunk := response.read(4 << 20):
            count += len(chunk)
            if count > expected:
                raise ValueError("Download exceeds declared size")
            stream.write(chunk)
            if count - last >= 500_000_000:
                print(json.dumps({"download_bytes": count, "expected": expected}), flush=True)
                last = count
    if count != expected:
        raise ValueError("Incomplete download; partial preserved")
    archive = output / "dataset.zip"
    raw.rename(archive)
    save(output / "download.json", {"bytes": count, "sha256": sha(archive), "url": URL})
    print(
        json.dumps({"archive_complete": count, "members": extract(archive, output / "dataset")}),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    acquire(args.output)


if __name__ == "__main__":
    main()
