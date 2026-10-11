"""Offline checks for SH17 labels and archive trust boundary."""

import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runtime  # local tempfile before acquisition imports
from ppe_accuracy_study import normalized_target, verify_dataset
from prepare_sh17 import extract, parse_label, save, sha
from sh17_quality import components


def main():
    assert runtime.ROOT.is_dir()
    groups = components([0, 1, 3, (1 << 63) - 1])
    assert groups[0] == groups[1] == groups[2] and groups[3] != groups[0]
    assert parse_label("10 0.5 0.5 0.2 0.1")[0][0] == 10
    assert parse_label("") == []
    assert normalized_target(1, 0.5, 0.5, 1.0000001, 1)["bbox"] == [0.0, 0.0, 1.0, 1.0]
    for text in ("17 .5 .5 .2 .2", "12 .5 .5 -1 .2", "nan .5 .5 .2 .2", "10 .99 .5 .5 .2"):
        try:
            parse_label(text)
        except ValueError:
            pass
        else:
            raise AssertionError(text)
    with tempfile.TemporaryDirectory(dir=runtime.ROOT / ".tmp") as folder:
        base = Path(folder)
        prepared = base / "prepared"
        dataset = prepared / "dataset"
        dataset.mkdir(parents=True)
        target = dataset / "sample.txt"
        target.write_text("1 .5 .5 .2 .2", encoding="utf-8")
        save(prepared / "derived_hashes.json", {"sample.txt": sha(target)})
        verify_dataset(prepared)
        (dataset / "train.cache").write_bytes(b"generated training cache")
        verify_dataset(prepared)
        target.write_text("1 .5 .5 .3 .2", encoding="utf-8")
        try:
            verify_dataset(prepared)
        except ValueError:
            pass
        else:
            raise AssertionError("Changed label accepted")
        for index, name in enumerate(("../escape.txt", "C:/escape", "labels/CON.txt", "a./b")):
            archive = base / f"{index}.zip"
            with zipfile.ZipFile(archive, "w") as stream:
                item = zipfile.ZipInfo("safe")
                item.filename = name
                stream.writestr(item, "bad")
            try:
                extract(archive, base / str(index))
            except ValueError:
                assert not (base / str(index)).exists()
            else:
                raise AssertionError(name)
        archive = base / "ok.zip"
        with zipfile.ZipFile(archive, "w") as stream:
            stream.writestr("labels/x.txt", "0 .5 .5 .2 .2")
        assert extract(archive, base / "ok") == 1
        assert (base / "ok/labels/x.txt").read_text() == "0 .5 .5 .2 .2"
    print("SH17 acquisition self-check passed")


if __name__ == "__main__":
    main()
