"""Run with Python directly: bounded SDD acquisition contract checks, no network."""

import importlib.util
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "sdd", ROOT / "industrial_ai/prepare_tracking_reference.py"
)
assert spec is not None and spec.loader is not None
sdd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sdd)


def check():
    files = []
    for scene, index in sdd.CANDIDATES:
        for kind, size in (("video", 40_000_000), ("annotations", 1_000_000)):
            path = f"{kind}/{scene}/video{index}/" + (
                "video.mp4" if kind == "video" else "annotations.txt"
            )
            files.append({"name": path, "totalBytes": size})
        files.append(
            {"name": f"annotations/{scene}/video{index}/reference.jpg", "totalBytes": 1000}
        )
    selected, excluded = sdd.select(files)
    assert len(selected) == 5 and len(excluded) == 3
    assert [r["clip"] for r in selected] == [
        "coupa/video0",
        "coupa/video1",
        "coupa/video2",
        "coupa/video3",
        "hyang/video0",
    ]
    (ROOT / ".tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / ".tmp", prefix="sdd-check-") as temporary:
        directory = Path(temporary)
        raw = directory / "single.zip"
        with zipfile.ZipFile(raw, "w") as archive:
            archive.writestr("annotations.txt", "0 0 0 1 1 0 0 0 0 Pedestrian")
        sdd.unpack(raw, directory / "annotations.txt", "annotations.txt", 100)
        assert (directory / "annotations.txt").is_file()
        for name, content, limit in (("../escape", "x", 100), ("annotations.txt", "x" * 101, 100)):
            malicious = directory / (str(limit) + ".zip")
            malicious.unlink(missing_ok=True)
            with zipfile.ZipFile(malicious, "w") as archive:
                archive.writestr(name, content)
            try:
                sdd.unpack(malicious, directory / "bad.txt", "annotations.txt", limit)
            except ValueError:
                pass
            else:
                raise AssertionError("Unsafe ZIP accepted")
    print("SDD collector checks passed")


if __name__ == "__main__":
    check()
