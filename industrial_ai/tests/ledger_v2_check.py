"""Versioned real-frame ledger regression; run with studio Python."""

import sys
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
import cv2
import numpy as np
from access_fixture import AccessFixture
from fastapi import FastAPI
from fastapi.testclient import TestClient

import access
import event_ledger
import runtime


def main():
    fixture = AccessFixture(ROOT / ".tmp" / ("ledger-v2-" + uuid4().hex))
    folder = fixture.resource("job", fixture.owner)
    video = cv2.VideoWriter(
        str(folder / "original.mp4"), cv2.VideoWriter.fourcc(*"mp4v"), 10, (80, 60)
    )
    for i in range(20):
        video.write(np.full((60, 80, 3), i * 10, np.uint8))
    video.release()
    state = fixture.store.get_document(folder / "state.json")
    fixture.store.put_document(folder / "state.json", {**state, "status": "done"})
    summary = {
        "frames": 20,
        "fps": 10,
        "duration": 2,
        "line": 0.5,
        "tracks": [{"id": i, "kind": k} for i, k in enumerate(["person", "car", "bus"])],
        "crossings": [
            {"track_id": i, "kind": k, "direction": "down", "seconds": 0.55 + i * 0.4}
            for i, k in enumerate(["person", "car", "bus"])
        ],
    }
    fixture.store.put_document(folder / "summary.json", summary)
    api = FastAPI()
    access.install(api, 250 * 1024 * 1024)
    event_ledger.install(api)
    with (
        patch.object(access, "store", return_value=fixture.store),
        patch.object(runtime, "JOBS", fixture.jobs),
        TestClient(api) as reviewer,
        TestClient(api) as other,
    ):
        fixture.login(reviewer, "reviewer")
        fixture.login(other, "other")
        prefix = f"/api/ledger/jobs/{folder.name}"
        response = reviewer.get(prefix + "/preview")
        assert response.status_code == 200, response.text
        preview = response.json()
        payload = {
            "schema_version": 2,
            "expected_fingerprint": preview["source_revision"],
            "crossing_indices": [0, 1, 2],
            "helmet_reviews": {
                "0": {
                    "status": "not_worn",
                    "association": "head_visible",
                    "head_bbox": [0.1, 0.1, 0.3, 0.3],
                }
            },
        }
        invalid = {
            **payload,
            "helmet_reviews": {"0": {"status": "not_worn", "association": "occluded"}},
        }
        assert reviewer.post(prefix + "/import", json=invalid).status_code == 422
        result = reviewer.post(prefix + "/import", json=payload)
        assert result.status_code == 200, result.text
        rows = reviewer.get("/api/ledger/events").json()["events"]
        assert len(rows) == 4 and {r["symbol"] for r in rows} == {
            "PERSON_ENTER_ZONE",
            "HELMET_NOT_WORN",
            "CAR_ENTER_ZONE",
            "BUS_ENTER_ZONE",
        }
        assert all(
            r["occurred_at"] is None
            and r["payload"]["source_revision"] == preview["source_revision"]
            for r in rows
        )
        assert reviewer.post(prefix + "/import", json=payload).status_code == 200
        row = next(r for r in rows if r["symbol"] == "PERSON_ENTER_ZONE")
        proof = f"/api/ledger/events/{row['id']}/proof"
        response = reviewer.get(proof)
        assert response.status_code == 200 and response.headers["content-type"] == "image/jpeg"
        frame = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
        assert 40 < frame.mean() < 60 and row["payload"]["frame_index"] == 5
        assert other.get(proof).status_code == 404
        assert other.get(prefix + "/preview").status_code == 404
        query = {
            "recording_id": folder.name,
            "source_revision": preview["source_revision"],
            "class_name": "person",
            "start_seconds": 0.55,
            "end_seconds": 0.95,
        }
        result = reviewer.post("/api/ledger/query", json=query)
        assert result.status_code == 200, result.text
        facts = result.json()
        assert facts["crossing_event_count"] == 1 and facts["helmet_observations"]["not_worn"] == 1
        assert all(item["source"]["class_name"] == "person" for item in facts["proof"])
        assert (
            reviewer.post("/api/ledger/query", json={**query, "start_seconds": 0.56}).json()[
                "has_verified_coverage"
            ]
            is False
        )
        assert (
            reviewer.post("/api/ledger/query", json={**query, "end_seconds": 0.55}).status_code
            == 422
        )
        assert (
            reviewer.post("/api/ledger/query", json={**query, "end_seconds": 3}).status_code == 422
        )
        assert other.post("/api/ledger/query", json=query).status_code == 404
        from fact_query import answer_ledger

        answered = answer_ledger(
            "ledger crossing person down dari 0 sampai 1 detik", rows, "reviewer", folder.name
        )
        assert "Ada 1 kejadian" in answered["answer"] and len(answered["ledger_proof"]) == 1
        for bad in [
            "ledger crossing person selain bus",
            "ledger crossing person -1",
            "ledger crossing person down dan car",
        ]:
            assert answer_ledger(bad, rows, "reviewer", folder.name)["ledger_proof"] == []
        changed = {
            **payload,
            "helmet_reviews": {
                "0": {
                    "status": "worn",
                    "association": "head_visible",
                    "head_bbox": [0.1, 0.1, 0.3, 0.3],
                }
            },
        }
        assert reviewer.post(prefix + "/import", json=changed).status_code == 409
        fixture.store.put_document(folder / "annotations.json", {"revision": 1, "frames": []})
        assert reviewer.post(prefix + "/import", json=payload).status_code == 409
        assert reviewer.get(proof).status_code == 409
        assert all(
            r["status"] == "stale" for r in reviewer.get("/api/ledger/events").json()["events"]
        )
        assert fixture.store.verify_audit()
    print(
        "PASS: v2 people/car/bus, real crossing frame, offset, head review, duplicate, isolation and stale guards"
    )


if __name__ == "__main__":
    main()
