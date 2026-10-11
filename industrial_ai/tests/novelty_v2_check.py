"""V2 runner via authenticated ledger, real frames and isolated source revisions."""

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
from extensions.experiments import event_novelty, registry
from fastapi import FastAPI
from fastapi.testclient import TestClient

import access
import event_ledger
import runtime


def main():
    fixture = AccessFixture(ROOT / ".tmp" / ("novelty-v2-" + uuid4().hex))
    api = FastAPI()
    access.install(api, 250 * 1024 * 1024)
    event_ledger.install(api)
    with (
        patch.object(access, "store", return_value=fixture.store),
        patch.object(runtime, "JOBS", fixture.jobs),
        patch.object(registry, "RUNS", fixture.root / "runs"),
        TestClient(api) as client,
        TestClient(api) as other,
    ):
        fixture.login(client, "owner")
        fixture.login(other, "other")
        for index in range(3):
            folder = fixture.resource("job", fixture.owner)
            writer = cv2.VideoWriter(
                str(folder / "original.mp4"), cv2.VideoWriter.fourcc(*"mp4v"), 10, (80, 60)
            )
            for frame in range(20):
                writer.write(np.full((60, 80, 3), index * 30 + frame, np.uint8))
            writer.release()
            state = fixture.store.get_document(folder / "state.json")
            fixture.store.put_document(folder / "state.json", {**state, "status": "done"})
            summary = {
                "frames": 20,
                "fps": 10,
                "duration": 2,
                "line": 0.5,
                "tracks": [{"id": 1, "kind": "person"}],
                "crossings": [
                    {"track_id": 1, "kind": "person", "direction": "down", "seconds": 0.5},
                    {"track_id": 1, "kind": "person", "direction": "up", "seconds": 1.5},
                ],
            }
            fixture.store.put_document(folder / "summary.json", summary)
            prefix = f"/api/ledger/jobs/{folder.name}"
            preview = client.get(prefix + "/preview").json()
            response = client.post(
                prefix + "/import",
                json={
                    "schema_version": 2,
                    "expected_fingerprint": preview["source_revision"],
                    "crossing_indices": [0, 1],
                },
            )
            assert response.status_code == 200, response.text
        export = client.get("/api/ledger/export").json()
        directory = event_novelty.run_novelty("v2-demo", export, fixture.owner["workspace_id"])
        detail = client.get("/api/ledger/novelty/runs/v2-demo")
        assert detail.status_code == 200, detail.text
        data = detail.json()
        assert not data["stale"] and len(data["sessions"]) == 3
        assert client.get("/api/ledger/novelty/runs").json()["runs"][0]["summary"]["stale"] is False
        assert other.get("/api/ledger/novelty/runs/v2-demo").status_code == 404
        event = data["sessions"][0]["terms"][0]["event_ids"][0]
        assert client.get(f"/api/ledger/events/{event}/proof").status_code == 200
        client.post(f"/api/ledger/events/{event}/retract", json={"reason": "review withdrawn"})
        assert client.get("/api/ledger/novelty/runs/v2-demo").json()["stale"]
        (directory / "explanations.json").write_text("{}")
        assert client.get("/api/ledger/novelty/runs/v2-demo").status_code == 409
    print(
        "PASS: real v2 frame->ledger->grouped runner->NLL/proof HTTP; foreign/stale/corrupt guards"
    )


if __name__ == "__main__":
    main()
