"""Run directly: .venv/Scripts/python.exe tests/cvat_reference_check.py."""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cvat_reference as cvat

META = (
    "<annotations><version>1.1</version><meta><task><mode>interpolation</mode>"
    "<size>5</size><original_size><width>64</width><height>48</height>"
    "</original_size></task></meta>"
)


def box(frame, *, outside=0, status=None, visibility=None, keyframe=1):
    attrs = ""
    if status:
        attrs += f'<attribute name="helmet_status">{status}</attribute>'
    if visibility:
        attrs += f'<attribute name="head_visibility">{visibility}</attribute>'
    return (
        f'<box frame="{frame}" outside="{outside}" occluded="0" keyframe="{keyframe}" '
        f'xtl="1" ytl="2" xbr="20" ybr="30">{attrs}</box>'
    )


MID = box(1, status="worn", visibility="visible")
PERSON = box(0) + MID + box(2, outside=1) + box(4)
XML = (
    META
    + f'<track id="0" label="person">{PERSON}</track>'
    + f'<track id="1" label="head">{box(1)}{box(2, outside=1)}</track>'
    + f'<track id="2" label="helmet">{box(1)}{box(2, outside=1)}</track>'
    + f'<track id="3" label="car">{box(0)}{box(2, outside=1)}</track>'
    + "</annotations>"
)


def rejects(call):
    try:
        call()
    except ValueError:
        return
    raise AssertionError("Invalid reviewed reference accepted")


def check():
    (ROOT / ".tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / ".tmp", prefix="cvat-check-") as folder:
        folder = Path(folder)
        video = folder / "source.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=64x48:r=5:d=1",
                "-frames:v",
                "5",
                "-c:v",
                "mpeg4",
                str(video),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        review = {
            "reviewer": "reviewer-fixture",
            "video_sha256": cvat.sha256(video),
            "cvat_xml_sha256": hashlib.sha256(XML.encode()).hexdigest(),
            "excluded_labels": ["car"],
            "canvas": [64, 48],
            "fps": "5/1",
            "frame_count": 5,
            "coverage": [[0, 3], [4, 5]],
            "frame_policy": "dense_explicit",
        }
        review_path = folder / "review.json"
        review_path.write_text(json.dumps(review), encoding="utf-8")
        xml_path = folder / "cvat.xml"
        xml_path.write_text(XML, encoding="utf-8")
        output = folder / "import"
        manifest = cvat.import_reference(xml_path, review_path, video, output)
        rows = [
            json.loads(line) for line in (output / "annotations.jsonl").read_text().splitlines()
        ]
        assert [row["frame"] for row in rows] == [0, 1, 2, 4]
        assert rows[1]["gt"] == [
            {
                "track_id": 0,
                "bbox": [1.0, 2.0, 20.0, 30.0],
                "occluded": False,
                "helmet_status": "worn",
                "head_visibility": "visible",
            }
        ]
        assert rows[2]["gt"] == [] and rows[2]["heads"] == []
        assert rows[3]["gt"][0]["helmet_status"] == "unknown"
        assert len(rows[1]["heads"]) == len(rows[1]["helmets"]) == 1
        assert manifest["counts"] == {"person": 3, "head": 1, "helmet": 1}
        assert manifest["ignored_labels"] == ["car"]
        assert manifest["cvat_xml_sha256"] == review["cvat_xml_sha256"]
        assert manifest["review_json_sha256"] == cvat.sha256(review_path)
        assert manifest["provenance"] == "human_review_declared_identity_not_verified"
        assert manifest["annotations_jsonl_sha256"] == cvat.sha256(output / "annotations.jsonl")
        assert json.loads((output / "manifest.json").read_text()) == manifest
        cli_output = folder / "cli-import"
        cli = subprocess.run(
            [
                sys.executable,
                str(ROOT / "cvat_reference.py"),
                "--xml",
                str(xml_path),
                "--review",
                str(review_path),
                "--video",
                str(video),
                "--output",
                str(cli_output),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert json.loads(cli.stdout)["covered_frames"] == 4
        assert (cli_output / "manifest.json").is_file()
        xml_path.write_text(XML.replace('label="person"', 'label="persn"', 1), encoding="utf-8")
        rejects(lambda: cvat.import_reference(xml_path, review_path, video, folder / "wrong-xml"))
        assert not (folder / "wrong-xml").exists()
        xml_path.write_text(XML, encoding="utf-8")
        try:
            cvat.import_reference(xml_path, review_path, video, output)
        except FileExistsError:
            pass
        else:
            raise AssertionError("Existing output overwritten")

        for mutation in (
            XML.replace(MID, "", 1),  # A missing reviewed frame cannot become a negative.
            XML.replace('label="person"', 'label="persn"', 1),
            XML.replace('label="car"', 'label="bus"', 1),
            XML.replace(
                MID, MID.replace('<attribute name="head_visibility">visible</attribute>', ""), 1
            ),
            XML.replace(MID, MID.replace("visible", "unknown"), 1),
            XML.replace('keyframe="1"', 'keyframe="0"', 1),
            XML.replace('xtl="1"', 'xtl="-1"', 1),
            XML.replace('xtl="1"', 'xtl="NaN"', 1),
            XML.replace('xbr="20"', 'xbr="0"', 1),
            XML.replace('xbr="20"', 'xbr="65"', 1),
            XML.replace("<size>5</size>", "<size>4</size>", 1),
            XML.replace('<track id="2"', '<track id="1"', 1),
            XML.replace(MID, MID.replace('frame="1"', 'frame="0"'), 1),
            '<!DOCTYPE annotations [<!ENTITY x "bad">]>' + XML,
        ):
            rejects(lambda source=mutation: cvat.cvat_data(source.encode(), review))
        for changed in (
            {**review, "coverage": [[0, 3], [2, 5]]},
            {**review, "coverage": []},
            {**review, "reviewer": " "},
            {**review, "fps": "5/0"},
            {**review, "frame_policy": "interpolate"},
        ):
            review_path.write_text(json.dumps(changed), encoding="utf-8")
            rejects(lambda: cvat.review_data(review_path))
        rejects(lambda: cvat.cvat_data(XML.encode(), {**review, "excluded_labels": []}))
        review_path.write_text(json.dumps({**review, "video_sha256": "0" * 64}), encoding="utf-8")
        rejects(
            lambda: cvat.import_reference(xml_path, review_path, video, folder / "never-created")
        )
        assert not (folder / "never-created").exists()
    print("CVAT reviewed reference checks passed")


if __name__ == "__main__":
    check()
