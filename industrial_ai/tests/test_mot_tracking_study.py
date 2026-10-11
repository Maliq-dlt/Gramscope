"""Runnable MOT17 evaluator and locked-candidate check."""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from trackeval.datasets import MotChallenge2DBox
from trackeval.metrics import Identity

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import mot_tracking_study as mot
import tracking_benchmark as base


def main():
    entry = {
        "path": "train/MOT17-05-FRCNN/img1/000001.jpg",
        "type": "file",
        "size": 40_000,
        "oid": "a" * 40,
        "lfs": {"oid": "b" * 64, "size": 40_000},
    }
    assert mot.validate_entry(entry) is entry
    for bad in (
        {**entry, "path": "../outside.jpg"},
        {**entry, "type": "symlink"},
        {**entry, "size": 9 * 2**20},
        {**entry, "lfs": {"oid": "b" * 64, "size": 40_001}},
    ):
        try:
            mot.validate_entry(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("Untrusted remote metadata accepted")
    assert len(mot.expected_paths()) == 604
    assert mot.phase_names("dev") == mot.CANDIDATES
    assert mot.phase_names("test", {"selected": mot.BASELINE}) == (mot.BASELINE,)
    assert mot.phase_names("test", {"selected": "sliced+bot"}) == (
        mot.BASELINE,
        "sliced+bot",
    )
    runtime = Path(__file__).resolve().parent / "runtime"
    runtime.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=runtime) as folder:
        root = Path(folder)
        name = "MOT17-check"
        gt = root / "gt" / name / "gt" / "gt.txt"
        pred = root / "trackers" / "candidate" / "data" / (name + ".txt")
        gt.parent.mkdir(parents=True)
        pred.parent.mkdir(parents=True)
        gt.write_text(
            "1,1,0,0,10,10,1,1,1.0\n1,2,100,100,10,10,0,8,1.0\n",
            encoding="utf-8",
        )
        pred.write_text(
            "1,1,0,0,10,10,0.9\n1,2,100,100,10,10,0.9\n",
            encoding="utf-8",
        )
        evaluator = MotChallenge2DBox(
            {
                "GT_FOLDER": str(root / "gt"),
                "TRACKERS_FOLDER": str(root / "trackers"),
                "TRACKERS_TO_EVAL": ["candidate"],
                "SEQ_INFO": {name: 1},
                "SKIP_SPLIT_FOL": True,
                "PRINT_CONFIG": False,
                "DO_PREPROC": True,
            }
        )
        data = evaluator.get_preprocessed_seq_data(
            evaluator.get_raw_seq_data("candidate", name), "pedestrian"
        )
        assert (data["num_gt_dets"], data["num_tracker_dets"]) == (1, 1)
        assert Identity(base.CONFIG).eval_sequence(data)["IDF1"] == 1.0
    print("MOT17 native distractor preprocessing and locked candidate: OK")


if __name__ == "__main__":
    main()
