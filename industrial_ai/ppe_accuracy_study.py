"""Source-grouped SH17 PPE training; reviewed worn/nohelmet status is outside this study."""

import argparse
import hashlib
import json
from pathlib import Path

# isort: off
import runtime  # workspace cache before scientific imports
from PIL import Image
from ultralytics import YOLO

# isort: on
from prepare_sh17 import save, sha

ROOT = runtime.ROOT
CLASSES = {0: 0, 10: 1, 12: 2}


def normalized_target(cls, x, y, w, h):
    box = [max(0.0, min(1.0, v)) for v in (x - w / 2, y - h / 2, x + w / 2, y + h / 2)]
    if box[0] >= box[2] or box[1] >= box[3]:
        raise ValueError("Degenerate normalized target")
    return {"class": int(cls), "bbox": box}


def prepare(source, output):
    source = source.resolve()
    if output.exists() or not output.resolve().is_relative_to((ROOT / ".tmp").resolve()):
        raise ValueError("Fresh output in .tmp required")
    if not source.is_relative_to((ROOT / "data/public").resolve()):
        raise ValueError("Dataset must stay inside data/public")
    quality = source / "quality-parallel"
    summary = json.loads((quality / "summary.json").read_text())
    if (
        sha(quality / "samples.json") != summary["samples_sha256"]
        or sha(source / "dataset.zip") != summary["input_sha256"]
    ):
        raise ValueError("Audited dataset fingerprint mismatch")
    rows = json.loads((quality / "samples.json").read_text())
    output.mkdir(parents=True)
    protocol = {
        "source": str(source.relative_to(ROOT)),
        "dataset_sha256": sha(source / "dataset.zip"),
        "samples_sha256": sha(quality / "samples.json"),
        "split_summary": summary,
        "classes": ["person", "helmet", "head"],
        "source_label_map": CLASSES,
        "head_is_nohelmet": False,
        "epochs": 20,
        "imgsz": 640,
        "batch": 8,
        "seed": 20261011,
        "freeze": 10,
        "base_sha256": sha(ROOT / "models/yolo26n.pt"),
        "code_sha256": sha(Path(__file__)),
        "input_protocol_sha256": sha(quality / "protocol.json"),
        "resize": "aspect-ratio preserved thumbnail960 JPEGquality93; normalizedboxes unchanged",
        "selection": "best checkpoint by validation only; test untouched until checkpoint seal",
        "derived_sha256": "derived_hashes.json contains all resized image/label/YAML fingerprints",
        "class_semantics": "head is generic anatomical head; baseline nohelmet excluded",
        "limits": [
            "Pexels photos not factory CCTV",
            "Head cannot establish helmet absence or worn association",
            "Pretraining corpus overlap is not fully auditable",
        ],
    }
    save(output / "protocol.json", protocol)
    dataset = output / "dataset"
    for partition in ("train", "dev", "test"):
        (dataset / "images" / partition).mkdir(parents=True)
        (dataset / "labels" / partition).mkdir(parents=True)

    def prepare_image(row):
        image_source = source / row["image"]
        if (
            not image_source.resolve().is_relative_to(source)
            or sha(image_source) != row["image_sha256"]
        ):
            raise ValueError("Audited source image changed")
        destination = dataset / "images" / row["partition"] / (row["id"] + ".jpg")
        with Image.open(image_source) as image:
            image = image.convert("RGB")
            image.thumbnail((960, 960))
            image.save(destination, "JPEG", quality=93)
        lines = [
            " ".join(map(str, [CLASSES[b[0]], *b[1:]])) for b in row["boxes"] if b[0] in CLASSES
        ]
        (dataset / "labels" / row["partition"] / (row["id"] + ".txt")).write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
        )

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=4) as pool:
        for index, _ in enumerate(pool.map(prepare_image, rows)):
            if index % 1000 == 0:
                print(json.dumps({"prepared": index + 1}), flush=True)
    # Test omitted from train YAML; validation cannot silently evaluate it.
    (dataset / "data.yaml").write_text(
        f"path: {dataset.resolve().as_posix()}\ntrain: images/train\nval: images/dev\nnames: [person, helmet, head]\n",
        encoding="utf-8",
    )
    save(
        output / "prepared.json",
        {"images": len(rows), "dataset_yaml_sha256": sha(dataset / "data.yaml")},
    )
    save(
        output / "derived_hashes.json",
        {
            p.relative_to(dataset).as_posix(): sha(p)
            for p in sorted(dataset.rglob("*"))
            if p.is_file()
        },
    )


def verify_dataset(output):
    dataset = (output / "dataset").resolve()
    derived = json.loads((output / "derived_hashes.json").read_text())
    if not derived or set(derived) != {
        p.relative_to(dataset).as_posix()
        for p in dataset.rglob("*")
        if p.is_file() and p.suffix != ".cache"
    }:
        raise ValueError("Prepared dataset inventory changed")
    for name, expected in derived.items():
        path = dataset / name
        if not path.resolve().is_relative_to(dataset) or sha(path) != expected:
            raise ValueError("Prepared dataset changed")


def train(output):
    output = output.resolve()
    if not output.is_relative_to((ROOT / ".tmp").resolve()) or output.is_symlink():
        raise ValueError("Training output must stay in workspace .tmp")
    verify_dataset(output)
    protocol = json.loads((output / "protocol.json").read_text())
    if sha(ROOT / "models/yolo26n.pt") != protocol["base_sha256"]:
        raise ValueError("Base weights changed")
    device, reason = runtime.select_device("auto", 1)
    save(
        output / "training_claim.json",
        {"device": device, "reason": reason, "protocol_sha256": sha(output / "protocol.json")},
    )
    model = YOLO(ROOT / "models/yolo26n.pt")
    model.train(
        data=str(output / "dataset/data.yaml"),
        epochs=protocol["epochs"],
        imgsz=640,
        batch=8,
        device=device,
        workers=0,
        project=str(output),
        name="training",
        exist_ok=False,
        plots=False,
        cache=False,
        amp=True,
        freeze=10,
        seed=protocol["seed"],
        deterministic=True,
        optimizer="AdamW",
        lr0=0.001,
        patience=20,
        mosaic=0.5,
        close_mosaic=5,
        verbose=False,
    )
    best = output / "training/weights/best.pt"
    save(
        output / "selection.json",
        {
            "winner": "training/weights/best.pt",
            "sha256": sha(best),
            "criterion": "Ultralytics best validation fitness across 20 frozen epochs",
            "protocol_sha256": sha(output / "protocol.json"),
        },
    )
    assert sha(ROOT / "models/yolo26n.pt") == protocol["base_sha256"]


def evaluate(output):
    output = output.resolve()
    if not output.is_relative_to((ROOT / ".tmp").resolve()) or output.is_symlink():
        raise ValueError("Evaluation output must stay in workspace .tmp")
    import csv

    import numpy as np
    from ultralytics.utils.metrics import ap_per_class

    from detector_benchmark import match_predictions, native_environment

    verify_dataset(output)
    save(
        output / "evaluation_protocol.json",
        {
            "derived_sha256": sha(output / "derived_hashes.json"),
            "code_sha256": sha(Path(__file__)),
            "baseline_helmet_sha256": sha(ROOT / "models/helmet.pt"),
            "confidence_grid": [0.1, 0.25, 0.5],
            "matching_code_sha256": sha(Path(__file__).with_name("detector_benchmark.py")),
            **native_environment(),
            "test_receipt": "exclusive global corpus claim before predict, no repeated evaluation",
            "inference": {"imgsz": 640, "conf": 0.001, "iou": 0.7, "max_det": 300},
            "metrics": "class-aware native IoU0.50:0.95; operating counts at IoU0.50, AP uses all conf>=0.001",
            "limits": [
                "head is not nohelmet",
                "Pexels photos not factory CCTV",
                "pretraining overlap unknown",
            ],
        },
    )
    selection = json.loads((output / "selection.json").read_text())
    best = output / selection["winner"]
    if (
        sha(best) != selection["sha256"]
        or sha(output / "protocol.json") != selection["protocol_sha256"]
    ):
        raise ValueError("Sealed checkpoint or protocol changed")
    device, _ = runtime.select_device("auto")
    models = {"candidate": YOLO(best), "baseline_helmet": YOLO(ROOT / "models/helmet.pt")}
    if models["candidate"].names != {0: "person", 1: "helmet", 2: "head"} or models[
        "baseline_helmet"
    ].names != {0: "Hardhat", 1: "NO-Hardhat"}:
        raise ValueError("Checkpoint class semantics differ from frozen study")

    def infer(partition, name, model):
        image_dir = output / "dataset/images" / partition
        if not any(image_dir.glob("*.jpg")):
            raise ValueError("Empty evaluation image directory")
        rows = []
        with (output / f"{partition}-{name}.jsonl").open("x", encoding="utf-8") as stream:
            for result in model.predict(
                str(image_dir),
                imgsz=640,
                conf=0.001,
                iou=0.7,
                max_det=300,
                device=device,
                stream=True,
                verbose=False,
            ):
                image = Path(result.path)
                targets = []
                for line in (
                    (output / "dataset/labels" / partition / (image.stem + ".txt"))
                    .read_text()
                    .splitlines()
                ):
                    c, x, y, w, h = map(float, line.split())
                    targets.append(normalized_target(c, x, y, w, h))
                if name == "baseline_helmet":
                    targets = [r for r in targets if r["class"] == 1]
                height, width = result.orig_shape
                predictions = []
                for box, confidence, cls in zip(
                    result.boxes.xyxy.cpu().tolist(),
                    result.boxes.conf.cpu().tolist(),
                    result.boxes.cls.cpu().tolist(),
                ):
                    if name == "baseline_helmet" and int(cls) != 0:
                        continue
                    c = 1 if name == "baseline_helmet" else int(cls)
                    predictions.append(
                        {
                            "class": c,
                            "bbox": [
                                max(0, min(1, v / (width if i % 2 == 0 else height)))
                                for i, v in enumerate(box)
                            ],
                            "confidence": confidence,
                        }
                    )
                row = {"id": image.stem, "targets": targets, "predictions": predictions}
                stream.write(json.dumps(row) + "\n")
                rows.append(row)
        return rows

    def statistics(rows, confidence):
        correct = np.concatenate([match_predictions(r["targets"], r["predictions"]) for r in rows])
        predicted = np.array([r["class"] for row in rows for r in row["predictions"]])
        conf = np.array([r["confidence"] for row in rows for r in row["predictions"]])
        truth = np.array([r["class"] for row in rows for r in row["targets"]])
        values = ap_per_class(correct, conf, predicted, truth, plot=False)
        ap = {int(c): a for c, a in zip(values[6], values[5])}
        result = []
        for cls, name in enumerate(["person", "helmet", "head"]):
            gt = int((truth == cls).sum())
            selected = (predicted == cls) & (conf >= confidence)
            # Rematch at the operating confidence so low-confidence boxes cannot consume GT.
            tp = sum(
                int(
                    match_predictions(
                        [r for r in row["targets"] if r["class"] == cls],
                        [
                            r
                            for r in row["predictions"]
                            if r["class"] == cls and r["confidence"] >= confidence
                        ],
                    )[:, 0].sum()
                )
                for row in rows
            )
            fp = int(selected.sum()) - tp
            result.append(
                {
                    "class": name,
                    "gt": gt,
                    "tp": tp,
                    "fp": fp,
                    "fn": gt - tp,
                    "precision": tp / (tp + fp) if tp + fp else 0.0,
                    "recall": tp / gt if gt else 0.0,
                    "ap50": float(ap[cls][0]) if cls in ap else None,
                    "ap50_95": float(ap[cls].mean()) if cls in ap else None,
                    "confidence": confidence,
                }
            )
        return result

    dev = {name: infer("dev", name, model) for name, model in models.items()}
    thresholds = {}
    for name, rows in dev.items():
        scores = {c: statistics(rows, c) for c in (0.1, 0.25, 0.5)}

        def objective(c, table=scores):
            r = table[c][1]
            return (
                2 * r["precision"] * r["recall"] / (r["precision"] + r["recall"])
                if r["precision"] + r["recall"]
                else 0.0
            )

        thresholds[name] = max(scores, key=lambda c: (objective(c), c))
    save(
        output / "operating_selection.json",
        {
            "thresholds": thresholds,
            "objective": "helmet F1 on dev; one common threshold per model",
            "checkpoint_sha256": sha(best),
        },
    )
    from detector_benchmark import atomic_json

    fingerprint = hashlib.sha256(
        json.dumps(
            {
                k: v
                for k, v in json.loads((output / "derived_hashes.json").read_text()).items()
                if k.startswith(("images/test/", "labels/test/"))
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    atomic_json(
        ROOT / ".tmp/ppe-accuracy-test-claims" / (fingerprint + ".json"),
        {
            "test_data_sha256": fingerprint,
            "operating_selection_sha256": sha(output / "operating_selection.json"),
            "output": output.relative_to(ROOT).as_posix(),
            "policy": "one test claim per held-out image/label corpus, even if interrupted",
        },
    )
    with (output / "test.claim").open("x") as claim:
        claim.write(sha(output / "operating_selection.json"))
    metrics = []
    for name, model in models.items():
        rows = infer("test", name, model)
        metrics.extend(
            {"model": name, **r}
            for r in statistics(rows, thresholds[name])
            if name != "baseline_helmet" or r["class"] == "helmet"
        )
    with (output / "test_metrics.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(metrics[0]))
        writer.writeheader()
        writer.writerows(metrics)
    save(
        output / "completed.json",
        {
            "status": "completed",
            "checkpoint_sha256": sha(best),
            "files": {p.name: sha(p) for p in output.iterdir() if p.is_file()},
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "train", "evaluate"])
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.stage == "prepare":
        prepare(args.source, args.output)
    elif args.stage == "train":
        train(args.output)
    else:
        evaluate(args.output)
