"""Run directly: canonical native TrackEval checks; no model or video inference."""

import importlib.util
import math
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("tracking_benchmark", ROOT / "tracking_benchmark.py")
assert spec is not None and spec.loader is not None
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)
CANVAS = [100, 100]
A, B = [0, 0, 10, 10], [30, 0, 40, 10]


def row(track_id, bbox, prediction=False):
    result = {"track_id": track_id, "bbox": bbox}
    if prediction:
        result["confidence"] = 0.9
    return result


def frame(gt, predictions):
    return {
        "gt": [row(i, box) for i, box in gt],
        "predictions": [row(i, box, True) for i, box in predictions],
    }


def check():
    perfect = [frame([(7, A), (9, B)], [(101, A), (105, B)]) for _ in range(3)]
    result = benchmark.metrics(perfect, CANVAS)
    assert result["Identity"] == {"IDF1": 1, "IDP": 1, "IDR": 1, "IDTP": 6, "IDFP": 0, "IDFN": 0}
    assert result["CLEAR"]["IDSW"] == 0 and result["CLEAR"]["MOTA"] == 1
    swapped = perfect[:1] + [frame([(7, A), (9, B)], [(101, B), (105, A)])] + perfect[2:]
    result = benchmark.metrics(swapped, CANVAS)
    assert result["Identity"]["IDTP"] == 4
    assert result["Identity"]["IDFP"] == result["Identity"]["IDFN"] == 2
    assert math.isclose(result["Identity"]["IDF1"], 2 / 3)
    assert result["CLEAR"]["IDSW"] == 4 and result["CLEAR"]["CLR_TP"] == 6
    assert math.isclose(result["CLEAR"]["MOTA"], 1 / 3)
    ambiguous = [frame([(7, A), (9, A)], [(101, A), (105, A)])]
    data = benchmark.sequence_data(ambiguous, CANVAS)
    assert data["similarity_scores"][0].tolist() == [[1, 1], [1, 1]]
    assert benchmark.metrics(ambiguous, CANVAS)["Identity"]["IDTP"] == 2
    missed = [
        frame([(7, A)], [(101, A)]),
        frame([(7, A)], []),
        frame([(7, A)], [(101, A), (105, B)]),
    ]
    result = benchmark.metrics(missed, CANVAS)
    assert result["Identity"]["IDTP"] == 2
    assert result["Identity"]["IDFP"] == result["Identity"]["IDFN"] == 1
    assert result["CLEAR"]["CLR_TP"] == 2 and result["CLEAR"]["CLR_FP"] == 1
    assert result["CLEAR"]["CLR_FN"] == 1 and result["CLEAR"]["IDSW"] == 0
    for gt, predictions, field, count in (
        ([(7, A)], [], "IDFN", 1),
        ([], [(101, A)], "IDFP", 1),
        ([], [], "IDTP", 0),
    ):
        result = benchmark.metrics([frame(gt, predictions)], CANVAS)
        assert result["Identity"][field] == count and result["Identity"]["IDF1"] == 0
    degenerate = benchmark.metrics([frame([(7, A)], [(101, [0, 0, 10, 0])])], CANVAS)
    assert degenerate["Identity"]["IDTP"] == 0 and degenerate["Identity"]["IDFP"] == 1
    assert degenerate["CLEAR"]["CLR_FP"] == degenerate["CLEAR"]["CLR_FN"] == 1
    untracked = [frame([(7, A)], [(None, A)]) for _ in range(2)]
    result = benchmark.metrics(untracked, CANVAS)
    assert result["Identity"]["IDTP"] == 1 and result["CLEAR"]["IDSW"] == 1
    combined = benchmark.aggregate(
        {
            "perfect": benchmark.metrics(perfect, CANVAS),
            "missing": benchmark.metrics(missed, CANVAS),
        }
    )
    assert math.isclose(combined["Identity"]["IDF1"], 8 / 9)
    assert combined["Identity"]["IDTP"] == 8
    for invalid in (
        frame([(7, A), (7, B)], []),
        frame([], [(101, A), (101, B)]),
        frame([(7, [0, 0, float("nan"), 10])], []),
        frame([(7, [-1, 0, 10, 10])], []),
    ):
        try:
            benchmark.metrics([invalid], CANVAS)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid receipt accepted")
    assert benchmark.clamp_box([-2, 2, 20, 22], [10, 10], [0.5, 0.5]) == ([0, 1, 10, 10], True)
    (ROOT / ".tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / ".tmp", prefix="tracking-check-") as temporary:
        annotations = Path(temporary) / "annotations.txt"
        annotations.write_text(
            '7 -2 2 20 22 0 0 1 1 "Pedestrian"\n'
            '8 0 0 10 10 0 1 0 0 "Pedestrian"\n'
            '9 0 0 10 10 0 0 0 0 "Biker"\n'
            '7 0 0 10 10 1 0 0 1 "Pedestrian"\n'
            '10 -20 0 -10 10 0 0 0 0 "Pedestrian"\n',
            encoding="utf-8",
        )
        targets, counts = benchmark.ground_truth(
            annotations,
            {
                "max_annotation_frame": 1,
                "video_dimensions": [10, 10],
                "coordinate_scale": [0.5, 0.5],
            },
            6,
        )
        assert targets == {
            0: [{"track_id": 7, "bbox": [0, 1, 10, 10], "occluded": True, "generated": True}]
        }
        assert counts == {
            "gt_detections": 1,
            "gt_clamped": 1,
            "gt_occluded": 1,
            "gt_generated": 1,
            "lost_rows_excluded": 1,
            "other_class_rows_excluded": 1,
            "gt_fully_outside_excluded": 1,
        }
        saved = Path(temporary) / "exclusive.json"
        benchmark.save(saved, {"original": True})
        try:
            benchmark.save(saved, {"overwrite": True})
        except FileExistsError:
            pass
        else:
            raise AssertionError("Existing result overwritten")
        assert saved.read_text(encoding="utf-8").find('"original"') >= 0
        pending = saved.with_name(saved.name + ".pending")
        pending.write_text("other writer", encoding="utf-8")
        try:
            benchmark.save(saved, {"collision": True})
        except FileExistsError:
            pass
        else:
            raise AssertionError("Existing pending writer accepted")
        assert pending.read_text(encoding="utf-8") == "other writer"
    print("Tracking benchmark checks passed (native Identity/CLEAR; no inference)")


if __name__ == "__main__":
    check()
