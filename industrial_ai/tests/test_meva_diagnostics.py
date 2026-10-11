"""Offline correspondence checks; unmatched partial annotations stay unknown."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from meva_diagnostics import matches


def main():
    assert matches([], []) == []
    truth = [{"bbox": [0, 0, 10, 10]}, {"bbox": [20, 20, 30, 30]}]
    pred = [{"bbox": [20, 20, 30, 30]}, {"bbox": [0, 0, 10, 10]}, {"bbox": [50, 50, 60, 60]}]
    assert matches(truth, pred) == [(0, 1), (1, 0)]
    assert matches(truth, []) == []
    print("MEVA diagnostic correspondence passed")


if __name__ == "__main__":
    main()
