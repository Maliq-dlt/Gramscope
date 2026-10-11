"""Run directly: continuous tracking metrics and receipt gates, without model inference."""

import inspect
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import continuous_tracking_study as study
import prepare_continuous_reference as acquisition


def line(path, rows):
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )


def check():
    from ultralytics.engine.results import Boxes
    from ultralytics.trackers.bot_sort import BOTSORT
    from ultralytics.trackers.byte_tracker import BYTETracker
    from ultralytics.utils import YAML, IterableSimpleNamespace

    assert len(acquisition.CLIPS) == len(set(acquisition.CLIPS)) == 4
    assert not {c.split("/")[0] for c in acquisition.CLIPS} & {"coupa", "hyang"}
    try:
        acquisition.collect(ROOT / ".tmp" / "outside-source")
    except ValueError:
        pass
    else:
        raise AssertionError("Acquisition output outside public data accepted")
    paths = [
        path
        for name in acquisition.CLIPS
        for path in (
            f"video/{name}/video.mp4",
            f"annotations/{name}/annotations.txt",
            f"annotations/{name}/reference.jpg",
        )
    ]
    ROOT.joinpath(".tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / ".tmp") as temporary:
        for prefix, budget, count in (
            ("video/", acquisition.source.VIDEO_BUDGET, 4),
            ("annotations/", acquisition.source.AUX_BUDGET, 8),
        ):
            listing = {
                "datasetFiles": [
                    {
                        "name": path,
                        "totalBytes": budget // count + 1 if path.startswith(prefix) else 1,
                    }
                    for path in paths
                ]
            }
            destination = Path(temporary) / "data/public" / prefix.rstrip("/")
            with (
                patch.object(acquisition.runtime, "ROOT", Path(temporary)),
                patch.object(acquisition.source, "metadata", return_value=listing),
                patch.object(
                    acquisition.source, "download", side_effect=AssertionError("download started")
                ),
            ):
                try:
                    acquisition.collect(destination)
                except ValueError as error:
                    assert "byte budget" in str(error)
                else:
                    raise AssertionError("Oversized listing accepted")
            assert not destination.exists()
    box = [0, 0, 10, 10]
    person = {"track_id": 7, "bbox": box, "occluded": False, "generated": False}
    det = {"track_id": None, "bbox": box, "confidence": 0.9}
    track = {"track_id": 101, "bbox": box, "confidence": 0.9}
    assert study.match_counts([person], [det]) == {
        "tp": 1,
        "fp": 0,
        "fn": 0,
        "small_gt": 1,
        "small_tp": 1,
    }
    assert study.match_counts([], [det])["fp"] == 1
    assert study.match_counts([person], [])["fn"] == 1
    with patch.object(study.base, "pairwise_iou", return_value=np.array([[0.9, 0.6], [0.6, 0.49]])):
        assert study.match_counts([person, person], [det, det])["tp"] == 2
    tracker_dir = Path(inspect.getfile(BOTSORT)).resolve().parents[1] / "cfg/trackers"
    canvas = np.zeros((100, 100, 3), dtype=np.uint8)
    for cls, config_name in ((BYTETracker, "bytetrack.yaml"), (BOTSORT, "botsort.yaml")):
        config = YAML.load(tracker_dir / config_name)
        assert not config.get("with_reid", False)
        tracker = cls(IterableSimpleNamespace(**config))
        boxes = Boxes(np.array([[0, 0, 10, 10, 0.9, 0]], dtype=np.float32), canvas.shape[:2])
        output = tracker.update(boxes, canvas)
        assert len(study.tracked_rows(output, [det], [100, 100])) == 1
    with tempfile.TemporaryDirectory(dir=ROOT / ".tmp", prefix="continuous-check-") as temporary:
        folder = Path(temporary)
        dataset = folder / "dataset"
        clip = dataset / "scene/video0"
        clip.mkdir(parents=True)
        (clip / "annotations.txt").write_text(
            '7 0 0 10 10 0 0 0 0 "Pedestrian"\n', encoding="utf-8"
        )
        metadata = {
            "max_annotation_frame": 1,
            "video_dimensions": [20, 20],
            "coordinate_scale": [1, 1],
            "source_group": "scene",
        }
        protocol = {
            "frames_per_clip": 2,
            "clips": [{"clip": "scene/video0", "role": "dev", "metadata": metadata}],
        }
        protocol_path = folder / "protocol.json"
        protocol_path.write_text("{}", encoding="utf-8")
        output = folder / "run"
        output.mkdir()
        study.base.save(
            output / "receipt.json",
            {
                "phase": "dev",
                "selected": None,
                "protocol_sha256": study.base.sha256(protocol_path),
                "native": {},
            },
        )
        detections, tracks = [], []
        for frame, gt in enumerate(([person], [])):
            for mode in ("standard", "sliced"):
                detections.append(
                    {
                        "clip": "scene/video0",
                        "frame": frame,
                        "mode": mode,
                        "gt": gt,
                        "detections": [det] if frame == 0 or mode == "standard" else [],
                    }
                )
            for candidate in study.CANDIDATES:
                tracks.append(
                    {
                        "clip": "scene/video0",
                        "frame": frame,
                        "candidate": candidate,
                        "gt": gt,
                        "predictions": [track] if frame == 0 else [],
                    }
                )
        line(output / "detections.jsonl", detections)
        line(output / "tracks.jsonl", tracks)
        study.base.save(
            output / "complete.json",
            {
                "detection_rows": 4,
                "track_rows": 8,
                "detections_sha256": study.base.sha256(output / "detections.jsonl"),
                "tracks_sha256": study.base.sha256(output / "tracks.jsonl"),
            },
        )
        with patch.object(study, "preflight", return_value=({**protocol, "native": {}}, dataset)):
            scored = study.score(protocol_path, output)
            assert scored["frames"] == 2
            assert scored["pedestrian_detector"]["standard"]["precision"] == 0.5
            assert scored["pedestrian_detector"]["sliced"]["small_recall"] == 1
            assert scored["candidates"]["standard+byte"]["combined"]["HOTA"]["mean_HOTA"] == 1
            assert scored["candidates"]["standard+byte"]["combined"]["Identity"]["IDF1"] == 1
            line(output / "tracks.jsonl", tracks[:-1])
            try:
                study.score(protocol_path, output)
            except ValueError as error:
                assert "hash mismatch" in str(error)
            else:
                raise AssertionError("Missing frame accepted")
            line(output / "tracks.jsonl", tracks + [tracks[-1]])
            try:
                study.score(protocol_path, output)
            except ValueError as error:
                assert "hash mismatch" in str(error)
            else:
                raise AssertionError("Extra row accepted")
        claim_protocol = {
            "selection": "max dev combined mean HOTA, then IDF1, then lexical candidate name",
            "clips": [
                {
                    "clip": "new/video0",
                    "role": "test",
                    "files": {"video.mp4": "f" * 64, "annotations.txt": "e" * 64},
                }
            ],
        }
        fake_scores = {
            name: {"combined": {"HOTA": {"mean_HOTA": 1}, "Identity": {"IDF1": 1}}}
            for name in study.CANDIDATES
        }
        dev_run = folder / "dev"
        dev_run.mkdir()
        (dev_run / "complete.json").write_text("{}", encoding="utf-8")
        selection = folder / "selection.json"
        selection.write_text(
            json.dumps(
                {
                    "protocol_sha256": study.base.sha256(protocol_path),
                    "rule": claim_protocol["selection"],
                    "dev_run": str(dev_run),
                    "dev_complete_sha256": study.base.sha256(dev_run / "complete.json"),
                    "ranking": sorted(study.CANDIDATES),
                    "selected": min(study.CANDIDATES),
                }
            ),
            encoding="utf-8",
        )
        with (
            patch.object(study, "ROOT", folder),
            patch.object(study, "score", return_value={"candidates": fake_scores}),
        ):
            first = study.claim_test(protocol_path, claim_protocol, selection, folder / "test")
            assert first == min(study.CANDIDATES)
            try:
                study.claim_test(protocol_path, claim_protocol, selection, folder / "test-again")
            except FileExistsError:
                pass
            else:
                raise AssertionError("Held-out input could be claimed twice")
    print("Continuous tracking receipt and native HOTA checks passed (no inference)")


if __name__ == "__main__":
    check()
