"""Run .venv/Scripts/python tests/review_counts_check.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat import answer_facts


def facts(question: str, data: dict) -> dict:
    result = answer_facts(question, data)
    assert result is not None, question
    return result


sample: dict = {
    "duration": 2,
    "frames": 20,
    "fps": 10,
    "object_classes": ["person", "car"],
    "tracks": [],
    "crossings": [],
    "occupancy": [{"seconds": 0, "person": 2, "car": 1}, {"seconds": 1, "person": 1, "car": 0}],
    "manual_frames": [
        {"frame_index": 10, "seconds": 1, "complete": True, "boxes": [{"label": "person"}] * 4}
    ],
}
answer = facts("Berapa orang di video?", sample)
assert answer and "Maksimum 4 orang" in answer["answer"], answer
print("PASS: completed corrections update global chatbot peak.")

import copy
import json
from unittest.mock import patch
from uuid import uuid4

from access_fixture import authorize
from fastapi.testclient import TestClient

import app
import runtime
from operations import working_directory
from vision import reviewed_summary

original = copy.deepcopy(sample)
derived = reviewed_summary(sample)
assert sample == original
assert derived["occupancy"] == sample["occupancy"]
assert derived["reviewed_occupancy"][1] == {"seconds": 1, "person": 4, "car": 0}
assert derived["review_status"]["saved_positions"] == 1
assert derived["tracks"] == sample["tracks"] and derived["crossings"] == sample["crossings"]
assert "Maksimum 2 orang" in facts("Berapa orang AI?", derived)["answer"]
assert "4 orang" in facts("Berapa orang pada detik 1?", derived)["answer"]
assert "1 orang" in facts("Berapa orang AI pada detik 1?", derived)["answer"]
assert "4 orang" in facts("Ringkasan", derived)["answer"]
assert facts("Ringkasan", derived)["mode"] == "reviewed"
ordered = copy.deepcopy(sample)
ordered["manual_frames"][0]["updated_at"] = "2026-10-08T10:00:00Z"
ordered["manual_frames"].append(
    {"seconds": 0, "complete": True, "boxes": [], "updated_at": "2026-10-08T11:00:00Z"}
)
assert reviewed_summary(ordered)["review_status"]["latest"]["seconds"] == 0
draft = copy.deepcopy(sample)
draft["manual_frames"][0]["complete"] = False
assert reviewed_summary(draft)["reviewed_occupancy"] == draft["occupancy"]
assert reviewed_summary(draft)["review_status"]["draft_positions"] == 1
assert "Maksimum 2 orang" in facts("Berapa orang?", draft)["answer"]
empty = copy.deepcopy(sample)
empty["manual_frames"][0]["boxes"] = []
assert reviewed_summary(empty)["reviewed_occupancy"][1]["person"] == 0
custom = copy.deepcopy(sample)
custom["manual_frames"][0]["boxes"] = [{"label": "karung"}] * 3 + [{"label": "Hardhat"}]
assert "Maksimum 3 karung" in facts("Berapa karung?", custom)["answer"]
assert "belum" in facts("Berapa karung AI?", custom)["answer"]
assert "Hardhat" not in reviewed_summary(custom)["reviewed_classes"]
assert "Hardhat" not in reviewed_summary(custom)["reviewed_occupancy"][1]
helmet = copy.deepcopy(custom)
helmet["manual_frames"][0].update(complete=False, helmets_complete=True)
assert reviewed_summary(helmet)["reviewed_occupancy"] == helmet["occupancy"]

# API reads the same view for dashboard, JSON export and chatbot; old disk result stays intact.
with working_directory(dir=runtime.ROOT / ".tmp") as directory:
    root = Path(directory)
    job_id = str(uuid4())
    folder = root / job_id
    folder.mkdir()
    raw = {k: v for k, v in sample.items() if k != "manual_frames"}
    path = folder / "summary.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    before = path.read_bytes()
    (folder / "state.json").write_text(json.dumps({"id": job_id, "status": "done"}))
    (folder / "annotations.json").write_text(
        json.dumps({"revision": 1, "frames": sample["manual_frames"]})
    )
    client = TestClient(app.app)
    with (
        patch.object(runtime, "JOBS", root),
        patch.object(app, "training_root", root / "trainings"),
    ):
        authorize(client)
        base = f"/api/jobs/{job_id}"
        state = client.get(base).json()["summary"]
        export = client.get(base + "/summary")
        assert export.status_code == 200 and export.json() == state
        assert "summary_reviewed.json" in export.headers["content-disposition"]
        reply = client.post("/api/chat", json={"job_id": job_id, "message": "Berapa orang?"}).json()
        assert "Maksimum 4 orang" in reply["answer"]
        assert state["reviewed_occupancy"][1]["person"] == 4
        assert path.read_bytes() == before

# Regression from the user's actual supermarket job, read only.
folder = runtime.JOBS / "be896883-b8aa-497d-8c00-16d923c18a51"
if folder.exists():
    result = app.result_summary(folder)
    assert result["review_status"]["saved_positions"] == 1
    assert result["review_status"]["draft_positions"] == 7
    assert result["review_status"]["latest"] == {
        "seconds": 100.9,
        "counts": {"person": 5, "car": 0, "bus": 0, "truck": 0, "motorcycle": 0, "bicycle": 0},
    }
    assert max(r["person"] for r in result["reviewed_occupancy"]) == 11
    assert "5 orang" in facts("Berapa orang pada detik 100,9?", result)["answer"]
    assert "4 orang" in facts("Berapa orang AI pada detik 100,9?", result)["answer"]
print(
    "PASS: reviewed/draft/AI peaks, zero counts, custom objects, helmets, API/export/chat consistency and real saved 4-to-5 correction."
)

# Summary adapts to actual content and does not list irrelevant zero-count classes.
reply = facts("Ringkasan", sample)
assert "0 mobil" not in reply["answer"]  # One car exists in this sample.
assert "1 mobil" in reply["answer"]
assert "0 bus" not in reply["answer"]
assert "0 track" not in reply["answer"]
assert "0 track kandidat" not in reply["answer"]
none = {
    **sample,
    "manual_frames": [],
    "tracks": [],
    "crossings": [],
    "occupancy": [{"seconds": 0, "person": 0, "car": 0}],
}
assert "Belum ada objek" in facts("Ringkasan", none)["answer"]
assert "Maksimum 0 orang" in facts("Berapa orang?", none)["answer"]
if folder.exists():
    reply = facts("Ringkasan", result)
    assert "Maksimum 11 orang" in reply["answer"]
    assert not any(
        term in reply["answer"]
        for term in ["0 mobil", "0 bus", "0 truk", "0 motor", "0 sepeda", "0 track kandidat"]
    )
    assert len(reply["evidence"]) == 3
    assert "113 ID sementara" not in reply["answer"]
    assert "individu unik belum" in reply["answer"]
    assert len(result["original_crossings"]) == 20
    assert result["crossing_source"] == "reviewer_corrected"
    assert f"{len(result['crossings'])} kejadian" in reply["answer"] or not result["crossings"]
    original_reply = facts("Ringkasan AI", result)
    assert "20 kejadian" in original_reply["answer"]
print(
    "PASS: contextual summary, observed classes only, explicit zero queries, short evidence and distinct track units."
)
