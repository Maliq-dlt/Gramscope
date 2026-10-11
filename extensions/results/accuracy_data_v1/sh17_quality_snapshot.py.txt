"""Audit every SH17 photograph and create visual-group-disjoint pilot splits."""

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.fft import dctn

from prepare_sh17 import NAMES, parse_label, save, sha


def phash(image):
    gray = np.asarray(image.convert("L").resize((32, 32)), dtype=float)
    block = dctn(gray, norm="ortho")[:8, :8].flatten()[1:]
    return sum(int(value > np.median(block)) << bit for bit, value in enumerate(block))


def components(hashes, distance=6):
    """Transitive visual duplicates; photographer independence remains unverified."""
    parents = list(range(len(hashes)))

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    # Eight disjoint chunks: distance<=6 guarantees at least one identical chunk.
    buckets = [defaultdict(list) for _ in range(8)]
    for i, value in enumerate(hashes):
        candidates = set()
        for part in range(8):
            candidates.update(buckets[part][(value >> (part * 8)) & 255])
        for j in candidates:
            if (value ^ hashes[j]).bit_count() <= distance:
                parents[root(i)] = root(j)
        for part in range(8):
            buckets[part][(value >> (part * 8)) & 255].append(i)
    return [root(i) for i in range(len(hashes))]


def audit(source, name="quality"):
    if name not in {"quality", "quality-parallel"}:
        raise ValueError("Unknown audit output")
    output = source / name
    output.mkdir()
    dataset = source / "dataset"
    images = sorted(p for p in dataset.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    labels = [p for p in dataset.rglob("*.txt") if "labels" in p.parts]
    label_files = {p.stem: p for p in labels}
    if len(label_files) != len(labels) or not images:
        raise ValueError("Nonempty unique images/labels required")
    save(
        output / "protocol.json",
        {
            "source_grouping": "transitive union same photographer_id and phash<=6",
            "seed": 20261011,
            "split": "80/10/10 shuffled groups",
            "source": "SH17 v1 meta-data",
            "head_is_nohelmet": False,
            "audit_code_sha256": sha(Path(__file__)),
        },
    )
    rows, failures, counts = [], [], Counter()

    def inspect_image(path):
        label = label_files.get(path.stem)
        try:
            if label is None:
                raise ValueError("Missing YOLO label")
            boxes = parse_label(label.read_text(encoding="utf-8"))
            metadata = dataset / "meta-data" / (path.stem + ".json")
            meta = json.loads(metadata.read_text(encoding="utf-8"))
            if type(meta.get("photographer_id")) is not int or not meta.get("url", "").startswith(
                "https://www.pexels.com/"
            ):
                raise ValueError("Missing authoritative Pexels photographer/source")
            with Image.open(path) as image:
                image.load()
                width, height = image.size
                fingerprint = phash(image)
                pixel_sha = hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()
            return {
                "id": path.stem,
                "photographer_id": meta["photographer_id"],
                "source_url": meta["url"],
                "metadata_sha256": sha(metadata),
                "image": str(path.relative_to(source).as_posix()),
                "label": str(label.relative_to(source).as_posix()),
                "width": width,
                "height": height,
                "image_sha256": sha(path),
                "label_sha256": sha(label),
                "pixel_sha256": pixel_sha,
                "phash": fingerprint,
                "boxes": boxes,
            }, None
        except (OSError, ValueError) as error:
            return None, {"image": path.name, "error": str(error)}

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=4) as pool:
        for index, (row, failure) in enumerate(pool.map(inspect_image, images)):
            if row is not None:
                rows.append(row)
                counts.update(NAMES[b[0]] for b in row["boxes"])
            if failure is not None:
                failures.append(failure)
            if index % 500 == 0:
                print(
                    json.dumps(
                        {"audited": index + 1, "accepted": len(rows), "failed": len(failures)}
                    ),
                    flush=True,
                )
    if failures:
        save(output / "failures.json", failures)
        raise ValueError("Invalid samples require explicit resolution before splitting")
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate image stems")
    groups = components([r["phash"] for r in rows])
    parents = list(range(len(rows)))

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    seen_visual, seen_photographer = {}, {}
    for i, (row, group) in enumerate(zip(rows, groups)):
        for mapping, key in ((seen_visual, group), (seen_photographer, row["photographer_id"])):
            if key in mapping:
                parents[root(i)] = root(mapping[key])
            mapping[key] = i
    groups = [root(i) for i in range(len(rows))]
    unique = sorted(set(groups))
    random.Random(20261011).shuffle(unique)
    partitions = {
        g: (
            "train"
            if i < int(0.8 * len(unique))
            else "dev"
            if i < int(0.9 * len(unique))
            else "test"
        )
        for i, g in enumerate(unique)
    }
    for row, group in zip(rows, groups):
        row["visual_group"] = group
        row["partition"] = partitions[group]
    # Exact-pixel duplicates are a stricter check than compressed-file identity.
    pixel_partitions = defaultdict(set)
    for row in rows:
        pixel_partitions[row["pixel_sha256"]].add(row["partition"])
    if any(len(p) > 1 for p in pixel_partitions.values()):
        raise ValueError("Exact-pixel leakage across visual groups")
    save(output / "samples.json", rows)
    summary = {
        "images": len(rows),
        "groups": len(unique),
        "labels": dict(counts),
        "partitions": dict(Counter(r["partition"] for r in rows)),
        "phash_distance": 6,
        "seed": 20261011,
        "input_sha256": sha(source / "dataset.zip"),
        "samples_sha256": sha(output / "samples.json"),
        "data_kind": "real public labeled photographs",
        "limitations": [
            "Photographer and visual groups isolated; unknown cross-photographer session links can remain",
            "Head labels do not imply missing helmet",
            "Not a surveillance-site/incident benchmark",
        ],
    }
    save(output / "summary.json", summary)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-name", default="quality")
    args = parser.parse_args()
    audit(args.source, args.output_name)
