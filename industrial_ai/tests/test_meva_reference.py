"""Assertion checks for MEVA acquisition rules; run with Python directly."""

import importlib.util
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "prepare_meva_reference.py"
spec = importlib.util.spec_from_file_location("meva", SOURCE)
assert spec is not None and spec.loader is not None
meva = importlib.util.module_from_spec(spec)
spec.loader.exec_module(meva)

STEM = "2018-03-07.16-50-00.16-55-00.admin.G329"


def fixture():
    activities = [
        {
            "act": {
                "id2": 2,
                "act3": {"Enter_Facility": 1.0},
                "timespan": [{"tsr0": [12, 20]}],
                "actors": [{"id1": 4, "timespan": [{"tsr0": [12, 20]}]}],
            }
        },
        {
            "act": {
                "id2": 1,
                "act3": {"Walk": 1.0},
                "timespan": [{"tsr0": [10, 15]}],
                "actors": [{"id1": 4, "timespan": [{"tsr0": [10, 15]}]}],
            }
        },
    ]
    geometry = [{"geom": {"id1": 4, "ts0": 10, "ts1": 1 / 3, "g0": "1 2 11 12"}}]
    types = [{"types": {"id1": 4, "cset3": {"Person": 1.0}}}]
    return activities, geometry, types


def rejects(activity_rows, geometry_rows, type_rows):
    try:
        meva.normalize(STEM, activity_rows, geometry_rows, type_rows)
    except ValueError:
        return
    raise AssertionError("Invalid annotation accepted")


def check():
    activity_rows, geometry_rows, type_rows = fixture()
    clip = meva.normalize(STEM, activity_rows, geometry_rows, type_rows)
    events = clip["actor_sequences"][0]["events"]
    assert [event["activity_id"] for event in events] == [1, 2]
    assert clip["qa"]["overlapping_activity_segments"] == 1
    assert clip["overlapping_activity_segments"][0]["left_activity_id"] == 1
    assert clip["qa"]["max_box_xy"] == [11.0, 12.0]
    assert clip["sequence_semantics"].find("not strict causal") >= 0

    bad_types = [{"types": {"id1": 4, "cset3": {}}}]
    rejects(activity_rows, geometry_rows, bad_types)
    rejects(activity_rows, geometry_rows, [])
    bad_geometry = [{"geom": {**geometry_rows[0]["geom"], "g0": "11 2 1 12"}}]
    rejects(activity_rows, bad_geometry, type_rows)
    bad_activities = [{"act": {**activity_rows[0]["act"], "timespan": [{"tsr0": [20, 12]}]}}]
    rejects(bad_activities, geometry_rows, type_rows)
    duplicate_geometry = geometry_rows + geometry_rows
    rejects(activity_rows, duplicate_geometry, type_rows)

    other_time = "2018-03-07.16-55-00.17-00-00.admin.G329"
    other_camera = "2018-03-07.16-50-00.16-55-00.bus.G331"
    selected = meva.video_candidates({STEM: {}, other_time: {}, other_camera: {}}, 2)
    assert selected == [STEM, other_camera]
    later = "2018-03-11.11-30-01.11-35-01.school.G421"
    by_date = meva.video_candidates(
        {STEM: {}, other_camera: {}, later: {}}, 2, ["2018-03-11", "2018-03-07"]
    )
    assert by_date == [STEM, later]
    try:
        meva.video_candidates({STEM: {}}, 2, ["2018-03-07", "2018-03-07"])
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate requested dates accepted")
    try:
        meva.video_candidates({STEM: {}}, 13)
    except ValueError:
        pass
    else:
        raise AssertionError("Video count bound not enforced")

    key = f"examples/annotations/2018-03-07/16/{STEM}.activities.yml"
    xml = (
        "<ListBucketResult><IsTruncated>false</IsTruncated>"
        + "".join(f"<Contents><Key>{key}</Key><Size>100</Size></Contents>" for _ in range(2))
        + "</ListBucketResult>"
    ).encode()
    try:
        meva.listing(xml)
    except ValueError as error:
        assert "duplicate" in str(error).lower()
    else:
        raise AssertionError("Duplicate listing key accepted")
    print("MEVA reference checks passed")


if __name__ == "__main__":
    check()
