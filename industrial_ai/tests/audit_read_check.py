"""Sensitive read attempts, ranges and privacy. Run directly with studio Python."""

import hashlib
import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runtime  # isort: skip

from access_fixture import AccessFixture
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient
from PIL import Image

import access

root = runtime.ROOT / ".tmp" / ("audit_read_" + uuid4().hex)
fixture = AccessFixture(root)
runtime.JOBS = fixture.jobs
access._stores[access.database_path()] = fixture.store
own = fixture.resource("job", fixture.owner)
other = fixture.resource("job", fixture.other)
training = fixture.resource("training", fixture.owner)
media = own / "annotation_0.jpg"
Image.new("RGB", (16, 16), (45, 120, 180)).save(media, "JPEG")
media_bytes = media.read_bytes()
app = FastAPI()
access.install(app, 1024 * 1024)


@app.get("/api/jobs/{job_id}/media/{name}")
def get_media(job_id: str, name: str):
    access.owned("job", job_id, fixture.jobs / job_id)
    if name != "annotation_0.jpg":
        raise HTTPException(404)
    return FileResponse(media)


@app.get("/api/jobs/{job_id}/summary")
def summary(job_id: str):
    if job_id == "failure":
        raise RuntimeError("controlled read failure")
    access.owned("job", job_id, fixture.jobs / job_id)
    return {"count": 2}


@app.get("/api/jobs/{job_id}/overlays")
@app.get("/api/jobs/{job_id}/review-queue")
def annotation_details(job_id: str):
    access.owned("job", job_id, fixture.jobs / job_id)
    return {"frames": [{"frame_index": 0, "boxes": []}]}


@app.get("/api/jobs/{job_id}/dataset")
def dataset(job_id: str):
    access.owned("job", job_id, fixture.jobs / job_id)
    return {"revision": 3}


@app.get("/api/jobs/{job_id}")
def poll(job_id: str):
    access.owned("job", job_id, fixture.jobs / job_id)
    return {"status": "done", "summary": {"manual_frames": [{"boxes": []}]}}


@app.get("/api/jobs")
@app.get("/api/training")
@app.get("/api/training/eligible")
def inventory():
    return [{"review_snapshot": [{"image": "DO_NOT_LOG", "boxes": []}]}]


@app.get("/api/training/{training_id}")
def training_details(training_id: str):
    access.owned("training", training_id, training)
    return {"review_snapshot": [{"image": "DO_NOT_LOG", "boxes": []}]}


@app.get("/api/jobs/{job_id}/exports/{revision}")
def export_status(job_id: str, revision: str):
    return {"status": "running"}


@app.get("/assets/{name}")
def asset(name: str):
    return {"static": True}


@app.get("/api/jobs/{job_id}/suggestions/{frame_index}")
def suggestions(job_id: str, frame_index: int):
    return {"suggestions": []}


@app.get("/api/ledger/export")
def export():
    return {"events": []}


def reads():
    with fixture.store.connection() as db:
        return [
            json.loads(row["event"])
            for row in db.execute("SELECT event FROM audit_events")
            if json.loads(row["event"])["action"].startswith("http:GET:")
        ]


with TestClient(app, raise_server_exceptions=False) as client:
    base = "/api/jobs/" + own.name
    assert client.get(base + "/summary").status_code == 401
    assert len(reads()) == 1 and reads()[-1]["user_id"] is None
    fixture.login(client, "owner")
    start = len(reads())
    assert (
        client.get(
            base + "/summary?secret=DO_NOT_LOG", headers={"X-Canary": "DO_NOT_LOG"}
        ).status_code
        == 200
    )
    response = client.get(base + "/media/annotation_0.jpg", headers={"Range": "bytes=10-19"})
    assert response.status_code == 206 and response.content == media_bytes[10:20]
    assert (
        client.get(base + "/media/annotation_0.jpg", headers={"Range": "bytes=30-39"}).status_code
        == 206
    )
    assert client.get(base + "/media/DO_NOT_LOG.bin").status_code == 404
    assert client.get("/api/jobs/" + other.name + "/summary").status_code == 404
    assert client.get("/api/jobs/failure/summary").status_code == 500
    assert client.get(base + "/dataset?revision=DO_NOT_LOG").status_code == 200
    assert client.get("/api/ledger/export").status_code == 200
    events = reads()[start:]
    assert [e["outcome"] for e in events] == [
        "200",
        "206",
        "206",
        "404",
        "404",
        "500",
        "200",
        "200",
    ]
    assert all(e["user_id"] == fixture.owner["id"] for e in events)
    assert json.loads(events[1]["resource"]) == {"job_id": own.name, "name": "annotation_0.jpg"}
    assert json.loads(events[3]["resource"]) == {"job_id": own.name}
    assert json.loads(events[6]["resource"]) == {"job_id": own.name}  # No invented revision.
    assert events[-1]["resource"] is None
    for suffix in ("overlays", "review-queue"):
        start = len(reads())
        assert client.get(base + "/" + suffix + "?group=DO_NOT_LOG").status_code == 200
        assert client.get("/api/jobs/" + other.name + "/" + suffix).status_code == 404
        events = reads()[start:]
        assert [e["outcome"] for e in events] == ["200", "404"]
        assert all(e["action"] == "http:GET:/api/jobs/{job_id}/" + suffix for e in events)
        assert [json.loads(e["resource"])["job_id"] for e in events] == [own.name, other.name]
    for path, template, resource in (
        (base, "/api/jobs/{job_id}", {"job_id": own.name}),
        (
            base + "/suggestions/0",
            "/api/jobs/{job_id}/suggestions/{frame_index}",
            {"job_id": own.name, "frame_index": "0"},
        ),
        ("/api/jobs", "/api/jobs", {}),
        ("/api/training", "/api/training", {}),
        ("/api/training/eligible", "/api/training/eligible", {}),
        (
            "/api/training/" + training.name,
            "/api/training/{training_id}",
            {"training_id": training.name},
        ),
    ):
        start = len(reads())
        assert client.get(path).status_code == 200
        event = reads()[-1]
        assert len(reads()) == start + 1 and event["action"] == "http:GET:" + template
        assert (json.loads(event["resource"]) if event["resource"] else {}) == resource
    count = len(reads())
    for path in ("/api/auth/session", "/assets/brand.svg", base + "/exports/1"):
        assert client.get(path).status_code == 200
    assert len(reads()) == count
    encoded = json.dumps(reads())
    assert "DO_NOT_LOG" not in encoded and fixture.password not in encoded
    assert client.cookies.get(access.COOKIE) not in encoded
    assert fixture.store.verify_audit()

backup = root / "backup"
backup.mkdir()
fixture.store.backup(backup / "studio.sqlite3")
shutil.copyfile(media, backup / media.name)
assert (
    hashlib.sha256(media.read_bytes()).digest()
    == hashlib.sha256((backup / media.name).read_bytes()).digest()
)
from storage import Store

restored = Store(backup / "studio.sqlite3")
assert restored.verify_audit()
assert restored.profile(fixture.owner["id"]) == fixture.store.profile(fixture.owner["id"])
with Image.open(backup / media.name) as image:
    image.load()
    assert image.size == (16, 16)


print(
    "PASS: sensitive GET/range/denial/500 audit, owned resources, no query/token/body leakage, HMAC integrity"
)
