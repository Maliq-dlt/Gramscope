"""Real detector fine-tuning from reviewed frames; separate candidate and source split."""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
from pathlib import Path

from access import has_document, read_document
from runtime import MODELS

GROUP_POLICY = "original-byte-or-attributed-url-transitive-v1"


def source_identity(folder: Path) -> dict:
    """Resolve reanalysis ancestry and preserve original bytes separately from source grouping."""
    with (folder / "upload.bin").open("rb") as stream:
        upload_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    original, seen = folder, set()
    while True:
        if original.resolve() in seen:
            raise ValueError("Relasi sumber rekaman tidak valid.")
        seen.add(original.resolve())
        state = read_document(original / "state.json", {})
        if state is None or not isinstance(state, dict):
            raise ValueError("Metadata sumber analisis ulang tidak valid.")
        parent = state.get("source_job_id")
        if not parent:
            break
        if not isinstance(parent, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", parent):
            raise ValueError("Relasi sumber rekaman tidak valid.")
        original = folder.parent / parent
        if not original.resolve().is_relative_to(folder.parent.resolve()) or not original.is_dir():
            raise ValueError("Sumber asli analisis ulang tidak tersedia.")
    with (original / "upload.bin").open("rb") as stream:
        source_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    if source_hash != upload_hash:
        raise ValueError("Hash upload analisis ulang berbeda dari sumber asli.")
    metadata = read_document(original / "source.json", {})
    if metadata is None or not isinstance(metadata, dict):
        raise ValueError("Metadata sumber segmen tidak valid.")
    offset = metadata.get("start_seconds", 0)
    if metadata:
        if (
            not isinstance(metadata.get("source_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", metadata["source_sha256"])
            or metadata.get("segment_sha256") != upload_hash
            or not isinstance(offset, (int, float))
            or isinstance(offset, bool)
            or not math.isfinite(offset)
            or offset < 0
        ):
            raise ValueError("Metadata sumber segmen tidak valid atau hash upload berubah.")
        source_hash = metadata["source_sha256"]
    attribution = metadata.get("attribution", {})
    url = attribution.get("source") if isinstance(attribution, dict) else None
    if not isinstance(url, str) or not url.startswith("https://") or len(url) > 2000:
        url = None
    group_hash = (
        hashlib.sha256(
            json.dumps(
                {"original_attributed_source": url},
                sort_keys=True,
                allow_nan=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        if url
        else source_hash
    )
    return {
        "source_sha256": source_hash,
        "upload_sha256": upload_hash,
        "source_url": url,
        "source_group_sha256": group_hash,
        "original_job_id": original.name,
        "start_seconds": offset,
    }


def canonical_groups(identities: list[dict]) -> list[dict]:
    """Union byte identities and attribution IDs transitively, including legacy rows."""
    parent = list(range(len(identities)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    owners = {}
    for index, row in enumerate(identities):
        for key in ("source_sha256", "source_group_sha256"):
            value = row.get(key, row["source_sha256"])
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError("Identitas kelompok sumber tidak valid.")
            token = (key, value)
            if token in owners:
                parent[find(index)] = find(owners[token])
            owners[token] = index
        url = row.get("source_url")
        if isinstance(url, str) and url.startswith("https://") and len(url) <= 2000:
            token = ("source_url", url)
            if token in owners:
                parent[find(index)] = find(owners[token])
            owners[token] = index
    members = {}
    for index, row in enumerate(identities):
        members.setdefault(find(index), []).append(row)
    groups = {
        root: min(
            [r["source_group_sha256"] for r in rows if r.get("source_url")]
            or [r.get("source_group_sha256", r["source_sha256"]) for r in rows]
        )
        for root, rows in members.items()
    }
    return [{**row, "source_group_sha256": groups[find(i)]} for i, row in enumerate(identities)]


def collect_reviewed(
    folders: list[Path],
    group: str,
    *,
    approved_only: bool = False,
    source_folders: list[Path] | None = None,
) -> list[dict]:
    flag = "complete" if group == "objects" else "helmets_complete"
    # Unselected or unapproved uploads may bridge byte identities and attributed URLs.
    sources = list({f.resolve(): f for f in [*(source_folders or []), *folders]}.values())
    identities = dict(
        zip(
            (f.resolve() for f in sources),
            canonical_groups([source_identity(f) for f in sources]),
        )
    )
    rows = []
    for folder in folders:
        identity = identities[folder.resolve()]
        annotations = folder / "annotations.json"
        if not has_document(annotations):
            continue
        data = read_document(annotations)
        for frame in data["frames"]:
            if not frame.get(flag, False) or (
                approved_only and group not in frame.get("learn_groups", [])
            ):
                continue
            boxes = [
                b
                for b in frame["boxes"]
                if (b["label"] in {"Hardhat", "NO-Hardhat"}) == (group == "helmets")
            ]
            image = folder / f"annotation_{frame['frame_index']}.jpg"
            if not image.is_file():
                raise ValueError("Foto anotasi hilang; simpan koreksi kembali.")
            seconds = frame.get("seconds", frame["frame_index"] / 10)
            if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
                raise ValueError("Posisi frame sumber tidak valid.")
            rows.append(
                {
                    "job_id": folder.name,
                    **identity,
                    "revision": data["revision"],
                    "updated_at": frame.get("updated_at", ""),
                    "frame_index": frame["frame_index"],
                    "source_position": round(
                        identity["start_seconds"] + seconds,
                        6,
                    ),
                    "image": image,
                    "boxes": boxes,
                }
            )
    rows = list(
        {
            (r["source_group_sha256"], r["source_position"]): r
            for r in sorted(rows, key=lambda r: (r["updated_at"], r["job_id"]))
        }.values()
    )
    if len({r["source_group_sha256"] for r in rows}) < 2:
        raise ValueError(
            "Tambahkan koreksi lengkap dari video sumber berbeda. Minimal dua sumber diperlukan agar latihan dan evaluasi terpisah."
        )
    if not any(r["boxes"] for r in rows):
        raise ValueError("Belum ada kotak pada kelompok yang dipilih.")
    return rows


def build_dataset(folder: Path, rows: list[dict], group: str, base_names: list[str]) -> dict:
    rows = canonical_groups(rows)
    sources = sorted({r["source_group_sha256"] for r in rows})
    if len(sources) < 2:
        raise ValueError("Minimal dua sumber independen diperlukan untuk train/val.")
    assigned = {}
    for row in rows:
        if "split" in row:
            assigned.setdefault(row["source_group_sha256"], set()).add(row["split"])
    if any(len(splits) > 1 for splits in assigned.values()):
        raise ValueError("Kelompok sumber yang sama tidak boleh melintasi train/val.")
    observed = {b["label"] for r in rows for b in r["boxes"]}
    if not observed:
        raise ValueError("Belum ada kotak pada kelompok yang dipilih.")
    names = base_names + sorted(observed - set(base_names))
    val_sources = set(sources[-max(1, len(sources) // 5) :])
    if not any(r["boxes"] for r in rows if r["source_group_sha256"] not in val_sources):
        positive = next(r["source_group_sha256"] for r in rows if r["boxes"])
        val_sources.remove(positive)
        val_sources.add(next(s for s in sources if s != positive))
    counts = {"train": 0, "val": 0}
    manifest = []
    for row in rows:
        split = "val" if row["source_group_sha256"] in val_sources else "train"
        stem = f"{row['job_id']}_{row['frame_index']}"
        image_dir = folder / "dataset/images" / split
        label_dir = folder / "dataset/labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(row["image"], image_dir / (stem + ".jpg"))
        labels = []
        for b in row["boxes"]:
            x1, y1, x2, y2 = b["bbox"]
            if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
                raise ValueError("Koordinat dataset tidak valid.")
            labels.append(
                f"{names.index(b['label'])} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"
            )
        (label_dir / (stem + ".txt")).write_text("\n".join(labels) + "\n", encoding="utf-8")
        counts[split] += 1
        manifest.append(
            {
                **{k: v for k, v in row.items() if k != "image"},
                "split": split,
                "image_sha256": hashlib.sha256(row["image"].read_bytes()).hexdigest(),
            }
        )
    config = {
        "path": (folder / "dataset").resolve().as_posix(),
        "train": "images/train",
        "val": "images/val",
        "names": dict(enumerate(names)),
    }
    # JSON is valid YAML; no extra YAML dependency or generated shell commands.
    (folder / "dataset/data.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    provenance = {
        "group": group,
        "names": names,
        "learned_classes": sorted(observed),
        "frames": manifest,
        "counts": counts,
        "split_unit": GROUP_POLICY,
        "source_groups": sources,
        "notice": "Small local pilot. User-complete labels are not independently validated; no factory accuracy claim.",
    }
    (folder / "dataset/provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return provenance


def train_once(folder: Path, state: dict, device: str, progress, cancel=None) -> dict:
    import time

    import torch
    from ultralytics import YOLO

    from operations import check_cancel

    check_cancel(cancel)
    folder = folder.resolve()
    torch.set_num_threads(8)
    base = MODELS / ("yolo26n.pt" if state["group"] == "objects" else "helmet.pt")
    model = YOLO(str(base))
    attempt = "gpu_attempt" if device.startswith("cuda") else "cpu_attempt"

    def epoch_done(trainer):
        progress(
            5 + int(90 * (trainer.epoch + 1) / state["epochs"]),
            f"Training epoch {trainer.epoch + 1}/{state['epochs']}",
        )

    model.add_callback("on_fit_epoch_end", epoch_done)
    model.add_callback("on_train_batch_end", lambda trainer: check_cancel(cancel))
    started = time.monotonic()
    result = model.train(
        data=str(folder / "dataset/data.yaml"),
        epochs=state["epochs"],
        imgsz=640,
        batch=2,
        nbs=2,  # Update every pilot batch, including datasets smaller than the default nbs=64.
        device=int(device.split(":")[1]) if device.startswith("cuda") else "cpu",
        workers=0,
        project=str(folder),
        name=attempt,
        exist_ok=False,
        plots=False,
        cache=False,
        amp=False,
        freeze=10,
        seed=42,
        deterministic=True,
        optimizer="AdamW",
        lr0=0.001,
        warmup_epochs=0,
        mosaic=0,
        close_mosaic=0,
        patience=state["epochs"],
        verbose=False,
    )
    check_cancel(cancel)
    checkpoint = folder / attempt / "weights/best.pt"
    if not checkpoint.is_file():
        raise RuntimeError("Training tidak menghasilkan checkpoint.")
    (folder / "weights").mkdir(exist_ok=True)
    shutil.copyfile(checkpoint, folder / "weights/best.pt")
    metrics = {k: float(v) for k, v in result.results_dict.items()}
    return {
        "device": device,
        "training_seconds": round(time.monotonic() - started, 2),
        "metrics": metrics,
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "base_sha256": hashlib.sha256(base.read_bytes()).hexdigest(),
    }


def train_candidate(folder: Path, state: dict, progress, cancel=None) -> dict:
    import gc

    import torch
    from ultralytics import YOLO

    import chat
    from runtime import select_device

    chat.release_model()
    base = MODELS / ("yolo26n.pt" if state["group"] == "objects" else "helmet.pt")
    names = [n.replace(" ", "_") for n in YOLO(str(base)).names.values()]
    rows = [{**r, "image": Path(r["image"])} for r in state["review_snapshot"]]
    provenance = build_dataset(folder, rows, state["group"], names)
    device, reason = select_device(state["device_preference"], 2)
    fallback = False
    try:
        result = train_once(folder, state, device, progress, cancel)
    except torch.cuda.OutOfMemoryError:
        if device == "cpu":
            raise
        fallback = True
    if fallback:
        gc.collect()
        torch.cuda.empty_cache()
        device, reason = "cpu", "VRAM habis; training diulang dengan CPU."
        result = train_once(folder, state, device, progress, cancel)
    return {
        **result,
        "device_reason": reason,
        "learned_classes": provenance["learned_classes"],
        "dataset_counts": provenance["counts"],
        "validation_notice": provenance["notice"],
    }
