"""Original-source grouping, approvals and legacy split checks; no detector training."""

import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runtime  # isort: skip

from access_fixture import AccessFixture
from fastapi.testclient import TestClient

import access
import app
from detector_training import build_dataset, canonical_groups, collect_reviewed
from event_ledger import digest

root = runtime.ROOT / ".tmp" / f"source_group_check_{uuid4()}"
root.mkdir()


def fixture(name, content, url=None, *, complete=True, approved=True, offset=0):
    folder = root / name
    folder.mkdir()
    (folder / "upload.bin").write_bytes(content)
    sha = hashlib.sha256(content).hexdigest()
    if url:
        (folder / "source.json").write_text(
            json.dumps(
                {
                    "source_sha256": sha,
                    "segment_sha256": sha,
                    "start_seconds": offset,
                    "attribution": {"source": url},
                }
            ),
            encoding="utf-8",
        )
    frame = {
        "frame_index": 0,
        "seconds": 0,
        "updated_at": name,
        "complete": complete,
        "helmets_complete": complete,
        "learn_groups": ["objects", "helmets"] if approved else [],
        "boxes": [
            {"label": "person", "bbox": [0.1, 0.1, 0.4, 0.6]},
            {"label": "Hardhat", "bbox": [0.2, 0.1, 0.3, 0.2]},
        ],
    }
    (folder / "annotations.json").write_text(json.dumps({"revision": 1, "frames": [frame]}))
    (folder / "annotation_0.jpg").write_bytes(b"controlled image copy fixture")
    return folder


def rejected(call, text):
    try:
        call()
    except ValueError as error:
        assert text in str(error), str(error)
    else:
        raise AssertionError(f"Expected rejection: {text}")


url = "https://example.org/original-one"
a = fixture("a", b"encoding-one", url)
b = fixture("b", b"encoding-two", url)
c = fixture("c", b"independent-original", "https://example.org/original-two")
rejected(lambda: collect_reviewed([a, b], "objects", approved_only=True), "dua sumber")
rows = collect_reviewed([a, b, c], "objects", approved_only=True)
assert len(rows) == 2
assert len(collect_reviewed([a, b, c], "objects")) == 2
same = next(row for row in rows if row["source_url"] == url)
assert same["source_group_sha256"] == digest({"original_attributed_source": url})
assert same["source_sha256"] == hashlib.sha256(b"encoding-two").hexdigest()
assert same["upload_sha256"] == same["source_sha256"]
assert len(collect_reviewed([a, b, c], "helmets", approved_only=True)) == 2
bridge = fixture("bridge", b"encoding-one", "https://example.org/another-url", approved=False)
d = fixture("d", b"encoding-three", "https://example.org/another-url")
rejected(lambda: collect_reviewed([a, bridge, d], "objects", approved_only=True), "dua sumber")
assert len(collect_reviewed([a, bridge, d, c], "objects", approved_only=True)) == 2
assert (
    canonical_groups(
        [
            {"source_sha256": "a" * 64, "source_group_sha256": "b" * 64},
            {"source_sha256": "a" * 64, "source_group_sha256": "c" * 64},
            {"source_sha256": "d" * 64, "source_group_sha256": "c" * 64},
        ]
    )[0]["source_group_sha256"]
    == "b" * 64
)
incomplete = fixture("incomplete", b"draft", complete=False)
unapproved = fixture("unapproved", b"not-approved", approved=False)
rejected(lambda: collect_reviewed([a, incomplete], "objects"), "dua sumber")
rejected(lambda: collect_reviewed([a, unapproved], "objects", approved_only=True), "dua sumber")
assert len(collect_reviewed([a, unapproved], "objects")) == 2
later = fixture("later", b"another-segment", url, offset=5)
assert {row["source_position"] for row in collect_reviewed([a, later, c], "objects")} == {0, 5}
reanalysis = fixture("reanalysis", b"encoding-one")
(reanalysis / "state.json").write_text(json.dumps({"source_job_id": "a"}))
rejected(lambda: collect_reviewed([a, reanalysis], "objects", approved_only=True), "dua sumber")
assert any(row["original_job_id"] == "a" for row in collect_reviewed([reanalysis, c], "objects"))
legacy_a = fixture("legacy_a", b"legacy-a")
legacy_b = fixture("legacy_b", b"legacy-b")
legacy = collect_reviewed([legacy_a, legacy_b], "objects", approved_only=True)
assert all(row["source_group_sha256"] == row["source_sha256"] for row in legacy)
for row in legacy:
    for field in (
        "source_group_sha256",
        "source_url",
        "upload_sha256",
        "original_job_id",
        "start_seconds",
    ):
        row.pop(field)
dataset = root / "dataset-check"
dataset.mkdir()
provenance = build_dataset(dataset, legacy, "objects", ["person"])
assert provenance["counts"] == {"train": 1, "val": 1}
assert len(provenance["source_groups"]) == 2
assert all(frame["source_group_sha256"] == frame["source_sha256"] for frame in provenance["frames"])
rejected(
    lambda: build_dataset(root / "one-source", legacy[:1], "objects", ["person"]), "dua sumber"
)
same_source = [{**legacy[0], "split": "train"}, {**legacy[0], "split": "val"}, legacy[1]]
rejected(lambda: build_dataset(root / "leak", same_source, "objects", ["person"]), "melintasi")
assert not (root / "leak").exists()
rejected(
    lambda: build_dataset(
        root / "same-url", [same, {**same, "source_sha256": "f" * 64}], "objects", ["person"]
    ),
    "dua sumber",
)

url_rows = [
    {**legacy[0], "source_url": url, "source_group_sha256": "e" * 64, "split": "train"},
    {**legacy[1], "source_url": url, "source_group_sha256": "f" * 64, "split": "val"},
    {**same, "source_url": "https://example.org/independent", "source_group_sha256": "a" * 64},
]
rejected(lambda: build_dataset(root / "url-leak", url_rows, "objects", ["person"]), "melintasi")
assert not (root / "url-leak").exists()
(root / "invalid-meta").mkdir()
(root / "invalid-meta/upload.bin").write_bytes(b"broken metadata")
(root / "invalid-meta/source.json").write_text("[]")
rejected(lambda: collect_reviewed([root / "invalid-meta", c], "objects"), "Metadata")

# Identity evidence is wider than the label selection, including incomplete bridges.
incomplete_bridge = fixture(
    "incomplete_bridge", b"encoding-one", "https://example.org/another-url", complete=False
)
for identity_only in (bridge, incomplete_bridge):
    rejected(
        lambda identity_only=identity_only: collect_reviewed(
            [a, d], "objects", approved_only=True, source_folders=[a, identity_only, d]
        ),
        "dua sumber",
    )
    selected = collect_reviewed(
        [a, d, c], "objects", approved_only=True, source_folders=[a, identity_only, d, c]
    )
    assert len({row["source_group_sha256"] for row in selected}) == 2
    assert all(row["job_id"] != identity_only.name for row in selected)

security = AccessFixture(root / "api")


def api_fixture(content, url, *, owner=None, status="done", complete=True, pending=False):
    folder = security.resource("job", owner or security.owner)
    (folder / "upload.bin").write_bytes(content)
    sha = hashlib.sha256(content).hexdigest()
    state = {
        "id": folder.name,
        "status": status,
        "filename": "controlled-source.bin",
        "created_at": "2026-10-11",
        "bytes": len(content),
    }
    documents = {
        "state.json": state,
        "source.json": {
            "source_sha256": sha,
            "segment_sha256": sha,
            "start_seconds": 0,
            "attribution": {"source": url},
        },
        "summary.json": {"frames": 2, "fps": 10},
        "annotations.json": {
            "revision": 1,
            "frames": [
                {
                    "frame_index": 0,
                    "seconds": 0,
                    "updated_at": folder.name,
                    "complete": complete,
                    "learn_groups": ["objects"] if complete else [],
                    "boxes": [{"label": "person", "bbox": [0.1, 0.1, 0.4, 0.6]}],
                }
            ],
        },
    }
    if pending:
        documents["selection.json"] = {"groups": ["objects"], "frames": [{"frame_index": 1}]}
    for name, document in documents.items():
        path = folder / name
        path.write_text(json.dumps(document), encoding="utf-8")
        security.store.put_document(path, document)
    (folder / "annotation_0.jpg").write_bytes(b"controlled image copy fixture")
    return folder


api_a = api_fixture(b"encoding-one", url)
api_bridge = api_fixture(
    b"encoding-one", "https://example.org/another-url", status="error", complete=False
)
api_d = api_fixture(b"encoding-three", "https://example.org/another-url")
api_other = api_fixture(b"other-workspace", url, owner=security.other)
api_uploading = api_fixture(b"unfinished", "https://example.org/unfinished", status="uploading")
security.store.put_document(
    api_uploading / "state.json",
    {
        k: v
        for k, v in security.store.get_document(api_uploading / "state.json").items()
        if k != "bytes"
    },
)
api_partial = api_fixture(b"partial", "https://example.org/partial", status="error")
partial_state = security.store.get_document(api_partial / "state.json")
security.store.put_document(api_partial / "state.json", {**partial_state, "bytes": 1000})

with (
    patch.object(runtime, "JOBS", security.jobs),
    patch.object(app, "training_root", security.trainings),
    patch.dict(access._stores, {security.jobs / ".security/studio.sqlite3": security.store}),
    TestClient(app.app) as client,
):
    security.login(client, "owner")
    token = access.principal.set({**security.owner, "tenant_name": "Workspace A"})
    try:
        universe = app.training_source_folders()
        assert api_bridge in universe
        assert all(folder not in universe for folder in (api_other, api_uploading, api_partial)), {
            folder.name: access.read_document(folder / "state.json")
            for folder in (api_other, api_uploading, api_partial)
            if folder in universe
        }
        request = {"job_ids": [api_a.name, api_d.name], "group": "objects"}
        # Holding the compute lock proves source leakage is rejected before compute allocation.
        app.compute_lock.acquire()
        try:
            response = client.post("/api/training", json=request)
            assert response.status_code == 422 and "dua sumber" in response.text, response.text
            response = client.post(f"/api/jobs/{api_a.name}/learn", json={"group": "objects"})
            assert response.status_code == 200 and response.json()["status"] == "waiting"
            assert "dua sumber" in response.json()["message"]
            assert not list(security.trainings.iterdir())
        finally:
            app.compute_lock.release()
        # A done bridge with draft labels must also remain usable as identity evidence.
        security.store.put_document(
            api_bridge / "state.json",
            {**security.store.get_document(api_bridge / "state.json"), "status": "done"},
        )
        response = client.post("/api/training", json=request)
        assert response.status_code == 422 and "dua sumber" in response.text, response.text
        assert not app.compute_lock.locked() and not list(security.trainings.iterdir())
        api_c = api_fixture(b"independent", "https://example.org/independent")
        api_pending = api_fixture(b"pending", "https://example.org/pending", pending=True)
        with patch.object(
            app, "start_detector_training", return_value={"status": "queued"}
        ) as start:
            response = client.post(f"/api/jobs/{api_a.name}/learn", json={"group": "objects"})
            assert response.status_code == 200 and response.json()["status"] == "queued", (
                response.text
            )
            snapshot = start.call_args.kwargs["review_snapshot"]
            assert {row["job_id"] for row in snapshot} <= {api_a.name, api_d.name, api_c.name}
            assert len({row["source_group_sha256"] for row in snapshot}) == 2
            assert all(row["job_id"] != api_pending.name for row in snapshot)
    finally:
        access.principal.reset(token)

(root / "report.json").write_text(
    json.dumps({"status": "passed", "source_groups": provenance["source_groups"]}, indent=2)
)
print(
    "PASS: transitive identities including omitted/draft/failed bridges, owned API filtering, precompute split rejection, approvals, offsets, reanalysis and legacy."
)
