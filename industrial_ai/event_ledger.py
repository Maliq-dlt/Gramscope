"""Verified local event/attendance records. Track IDs never identify employees."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

import access


def timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, AttributeError) as error:
        raise ValueError("Time must be an ISO8601 timestamp with timezone.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Time must include an explicit timezone.")
    return parsed.astimezone(UTC).isoformat()


def digest(data) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()
    ).hexdigest()


def source(job_id: str):
    try:
        if str(UUID(job_id)) != job_id:
            raise ValueError
    except ValueError as error:
        raise HTTPException(404, "Rekaman tidak ditemukan.") from error
    row = access.store().require_resource("job", job_id, access.workspace_id())
    if row is None:
        raise HTTPException(404, "Rekaman tidak ditemukan dalam workspace ini.")
    from pathlib import Path

    folder = Path(row["path"])
    state = access.read_document(folder / "state.json")
    if state["status"] != "done":
        raise HTTPException(409, "Rekaman harus selesai dianalisis.")
    summary = access.read_document(folder / "summary.json")
    annotations = access.read_document(folder / "annotations.json", {"revision": 0, "frames": []})
    corrections = access.read_document(
        folder / "tracking_corrections.json", {"revision": 0, "frames": []}
    )
    evidence_files = {}
    for track in summary.get("tracks", []):
        for key in ("evidence", "helmet_evidence"):
            name = track.get(key)
            if not name or (isinstance(name, str) and name in evidence_files):
                continue
            if not isinstance(name, str) or not re.fullmatch(r"evidence_\d+\.jpg", name):
                evidence_files[str(name)] = {"status": "invalid"}
                continue
            evidence = folder / name
            if not evidence.resolve().is_relative_to(folder.resolve()):
                evidence_files[name] = {"status": "invalid"}
                continue
            try:
                with evidence.open("rb") as stream:
                    evidence_files[name] = {
                        "status": "present",
                        "sha256": hashlib.file_digest(stream, "sha256").hexdigest(),
                    }
            except FileNotFoundError:
                evidence_files[name] = {"status": "missing"}
            except OSError:
                evidence_files[name] = {"status": "unreadable"}
    metadata = {
        "evidence_files": evidence_files,
        "state": {key: state.get(key) for key in ("id", "status", "model_id", "source_job_id")},
        "summary": summary,
        "annotations": annotations,
        "corrections": corrections,
    }
    return folder, summary, metadata, digest(metadata)


CLASSES = {"person", "car", "bus", "truck", "motorcycle", "bicycle"}


class HelmetReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["worn", "not_worn", "unknown"] = "unknown"
    association: Literal["head_visible", "held_in_hand", "occluded", "ambiguous", "unreviewed"] = (
        "unreviewed"
    )
    head_bbox: tuple[float, float, float, float] | None = None

    @model_validator(mode="after")
    def validate_association(self):
        if self.head_bbox is not None:
            x1, y1, x2, y2 = self.head_bbox
            if not all(math.isfinite(v) for v in self.head_bbox) or not (
                0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1
            ):
                raise ValueError("Head box must have positive area inside the frame.")
        if self.status != "unknown" and (
            self.association != "head_visible" or self.head_bbox is None
        ):
            raise ValueError(
                "Known helmet status requires reviewer-confirmed visible head association."
            )
        return self


class ImportCrossings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1, 2] = 1
    recorded_at: str | None = Field(default=None, max_length=80)
    expected_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    helmet_reviews: dict[int, HelmetReview] = Field(default_factory=dict, max_length=1000)
    crossing_indices: list[int] = Field(min_length=1, max_length=1000)

    @field_validator("recorded_at")
    @classmethod
    def valid_time(cls, value):
        return timestamp(value) if value is not None else None


class Attendance(BaseModel):
    subject_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    source_kind: Literal["badge", "qr", "manual"]
    source_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
    occurred_at: str = Field(max_length=80)
    action: Literal["arrived", "departed"]
    job_id: str | None = None
    track_id: int | None = Field(default=None, ge=0)

    @field_validator("occurred_at")
    @classmethod
    def valid_time(cls, value):
        return timestamp(value)


class Retraction(BaseModel):
    reason: str = Field(min_length=1, max_length=200)


class Ledger:
    def __init__(self, store):
        self.store = store
        with store.connection() as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='ledger_events'").fetchone()
        if exists:
            return

        def initialize(db):
            db.execute("""CREATE TABLE IF NOT EXISTS ledger_events(
                id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                category TEXT NOT NULL CHECK(category IN ('observation','attendance')),
                source_key TEXT NOT NULL, source_fingerprint TEXT NOT NULL,
                job_id TEXT, track_id INTEGER, occurred_at TEXT NOT NULL,
                symbol TEXT NOT NULL, payload TEXT NOT NULL, verifier_id TEXT NOT NULL REFERENCES users(id),
                retracted INTEGER NOT NULL DEFAULT 0 CHECK(retracted IN (0,1)), reason TEXT,
                verified_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f+00:00','now')),
                UNIQUE(workspace_id,category,source_key))""")
            db.execute(
                "CREATE INDEX IF NOT EXISTS ledger_workspace ON ledger_events(workspace_id,occurred_at)"
            )

        store._write(initialize, "ledger.schema")

    def append(self, category, entries):
        user = access.actor()

        def operation(db):
            results = []
            for entry in entries:
                payload = json.dumps(entry["payload"], sort_keys=True, allow_nan=False)
                old = db.execute(
                    "SELECT * FROM ledger_events WHERE workspace_id=? AND category=? AND source_key=?",
                    (user["workspace_id"], category, entry["source_key"]),
                ).fetchone()
                if old:
                    if (
                        old["payload"] != payload
                        or old["source_fingerprint"] != entry["source_fingerprint"]
                    ):
                        raise ValueError(
                            "Source already recorded with different evidence or revision; retract it and use a new source revision."
                        )
                    results.append(dict(old))
                    continue
                event_id = str(uuid4())
                db.execute(
                    "INSERT INTO ledger_events(id,workspace_id,category,source_key,source_fingerprint,job_id,track_id,occurred_at,symbol,payload,verifier_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        event_id,
                        user["workspace_id"],
                        category,
                        entry["source_key"],
                        entry["source_fingerprint"],
                        entry.get("job_id"),
                        entry.get("track_id"),
                        entry["occurred_at"],
                        entry["symbol"],
                        payload,
                        user["id"],
                    ),
                )
                results.append(
                    dict(
                        db.execute("SELECT * FROM ledger_events WHERE id=?", (event_id,)).fetchone()
                    )
                )
            return results

        return self.store._write(
            operation, "ledger.import", user_id=user["id"], workspace_id=user["workspace_id"]
        )

    def rows(self):
        with self.store.connection() as db:
            rows = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM ledger_events WHERE workspace_id=? ORDER BY occurred_at,id",
                    (access.workspace_id(),),
                )
            ]
        fingerprints = {}
        integrity = {}
        video_integrity = {}
        for row in rows:
            row["payload"] = json.loads(row["payload"])
            row["status"] = "retracted" if row["retracted"] else "verified"
            if row["occurred_at"].startswith("video+"):
                row["occurred_at"] = None
            if row["job_id"] and not row["retracted"]:
                if row["job_id"] not in fingerprints:
                    try:
                        fingerprints[row["job_id"]] = source(row["job_id"])[3]
                    except (HTTPException, FileNotFoundError):
                        fingerprints[row["job_id"]] = None
                if fingerprints[row["job_id"]] != row["source_fingerprint"]:
                    row["status"] = "stale"
                if row["payload"].get("schema_version") == 2 and row["status"] == "verified":
                    payload = row["payload"]
                    key = (row["job_id"], payload["evidence_sha256"])
                    if key not in integrity:
                        try:
                            folder = source(row["job_id"])[0]
                            if row["job_id"] not in video_integrity:
                                with (folder / "original.mp4").open("rb") as stream:
                                    video_hash = hashlib.file_digest(stream, "sha256").hexdigest()
                                video_integrity[row["job_id"]] = (
                                    video_hash,
                                    original_source(row["job_id"]),
                                )
                            video_hash, original_hash = video_integrity[row["job_id"]]
                            proof_hash = hashlib.sha256(
                                (
                                    folder / ("ledger_" + payload["evidence_sha256"] + ".jpg")
                                ).read_bytes()
                            ).hexdigest()
                            integrity[key] = (
                                video_hash == payload["video_sha256"]
                                and proof_hash == payload["evidence_sha256"]
                                and original_source(row["job_id"])
                                == payload["original_source_sha256"]
                            )
                        except (OSError, HTTPException):
                            integrity[key] = False
                    if not integrity[key]:
                        row["status"] = "stale"
        return rows

    def retract(self, event_id, reason):
        user = access.actor()

        def operation(db):
            record = db.execute(
                "SELECT category FROM ledger_events WHERE id=? AND workspace_id=?",
                (event_id, user["workspace_id"]),
            ).fetchone()
            if (
                record is not None
                and record["category"] == "attendance"
                and user["role"] != "admin"
            ):
                raise HTTPException(403, "Penarikan absensi membutuhkan administrator.")
            if not db.execute(
                "UPDATE ledger_events SET retracted=1,reason=? WHERE id=? AND workspace_id=?",
                (reason, event_id, user["workspace_id"]),
            ).rowcount:
                raise HTTPException(404, "Catatan tidak ditemukan dalam workspace ini.")

        self.store._write(
            operation,
            "ledger.retract",
            user_id=user["id"],
            workspace_id=user["workspace_id"],
            resource=event_id,
        )


def reviewer():
    if access.actor()["role"] not in {"admin", "reviewer"}:
        raise HTTPException(403, "Reviewer diperlukan.")


def facts(rows, role=None):
    role = access.actor()["role"] if role is None else role
    live = [row for row in rows if row["status"] == "verified"]
    observations = [row for row in live if row["category"] == "observation"]
    attendance = [row for row in live if row["category"] == "attendance"]
    links = {}
    for row in attendance:
        if row["job_id"] is not None and row["track_id"] is not None:
            links.setdefault((row["job_id"], row["track_id"]), set()).add(
                row["payload"]["subject_id"]
            )
    ambiguous = [key for key, subjects in links.items() if len(subjects) > 1]
    return {
        "scope": "authenticated_workspace",
        "crossing_event_count": sum(
            row["symbol"] in {"PERSON_ENTER_ZONE", "PERSON_EXIT_ZONE"} for row in observations
        ),
        "observed_track_count": len({(row["job_id"], row["track_id"]) for row in observations}),
        "unique_person_count": None,
        "identity_status": "unknown",
        "attendance_record_count": len(attendance),
        "ambiguous_track_links": [
            {"job_id": job, "track_id": track, "identity": "unknown"} for job, track in ambiguous
        ],
        "unknown_helmet_observation_count": sum(
            row["symbol"] == "HELMET_UNKNOWN" for row in observations
        ),
        "stale_count": sum(row["status"] == "stale" for row in rows),
        "retracted_count": sum(row["status"] == "retracted" for row in rows),
        "proof": [
            {
                "event_id": row["id"],
                "source": row["payload"],
                **({"verifier_id": row["verifier_id"]} if role != "viewer" else {}),
                "verified_at": row["verified_at"],
                "occurred_at": row["occurred_at"],
            }
            for row in live
            if role == "admin" or row["category"] == "observation"
        ],
        "limitations": [
            "Track ID bukan identitas pegawai atau hitungan orang unik.",
            "Absensi diverifikasi manual; badge/QR tidak didekode dan biometrik tidak diterapkan.",
            "Zona berarti sisi bawah garis analisis; unknown helm bukan pelanggaran.",
        ],
    }


def original_source(job_id):
    """Copies/reanalyses share the original upload hash; never use job ID as a split group."""
    seen = set()
    while job_id not in seen:
        seen.add(job_id)
        folder, _, metadata, _ = source(job_id)
        parent = metadata["state"].get("source_job_id")
        if not parent:
            path = folder / "upload.bin"
            if not path.is_file():
                path = folder / "original.mp4"
            try:
                with path.open("rb") as stream:
                    return hashlib.file_digest(stream, "sha256").hexdigest()
            except OSError as error:
                raise HTTPException(409, "Sumber asli tidak tersedia untuk provenance.") from error
        job_id = parent
    raise HTTPException(409, "Relasi sumber rekaman tidak valid.")


def import_v2(job_id, request, folder, summary, metadata, fingerprint):
    if request.expected_fingerprint != fingerprint:
        raise HTTPException(409, "Revisi berubah; tinjau ulang preview sebelum mengesahkan.")
    if set(request.helmet_reviews) - set(request.crossing_indices):
        raise HTTPException(422, "Review helm harus terkait crossing terpilih.")
    from app import frame_image

    tracks = {t["id"]: t for t in summary.get("tracks", [])}
    entries = []
    source_hash = original_source(job_id)
    with (folder / "original.mp4").open("rb") as stream:
        video_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    for index in dict.fromkeys(request.crossing_indices):
        if not 0 <= index < len(summary.get("crossings", [])):
            raise HTTPException(422, "Crossing tidak tersedia.")
        crossing = summary["crossings"][index]
        kind, seconds = crossing["kind"], crossing["seconds"]
        track = tracks.get(crossing["track_id"])
        if (
            kind not in CLASSES
            or not track
            or track["kind"] != kind
            or crossing["direction"] not in {"up", "down"}
            or type(seconds) not in (int, float)
            or not math.isfinite(seconds)
            or not 0 <= seconds <= summary["duration"]
        ):
            raise HTTPException(422, "Kelas, track, arah atau offset crossing tidak valid.")
        if kind != "person" and index in request.helmet_reviews:
            raise HTTPException(422, "Review helm hanya untuk track orang.")
        review = request.helmet_reviews.get(index, HelmetReview())
        frame_index = min(int(seconds * summary["fps"]), summary["frames"] - 1)
        image = frame_image(folder, frame_index, summary)
        image_hash = hashlib.sha256(image).hexdigest()
        evidence = folder / ("ledger_" + image_hash + ".jpg")
        if not evidence.exists():
            pending = evidence.with_suffix(".pending")
            pending.write_bytes(image)
            pending.replace(evidence)
        payload = {
            "schema_version": 2,
            "recording_id": job_id,
            "track_id": crossing["track_id"],
            "seconds": seconds,
            "interval_seconds": [seconds, seconds],
            "class_name": kind,
            "direction": crossing["direction"],
            "line": summary["line"],
            "source_revision": fingerprint,
            "original_source_sha256": source_hash,
            "video_sha256": video_hash,
            "annotation_revision": metadata["annotations"]["revision"],
            "correction_revision": metadata["corrections"]["revision"],
            "model_id": metadata["state"]["model_id"],
            "result_source": "fine_tuned_candidate"
            if metadata["state"]["model_id"]
            else "original_detector",
            "review_status": "reviewer_approved_crossing",
            "recorded_at": request.recorded_at,
            "frame_index": frame_index,
            "evidence_seconds": frame_index / summary["fps"],
            "evidence_mode": "original_exact_frame",
            "evidence_sha256": image_hash,
            "helmet_status": review.status if kind == "person" else None,
            "head_association": review.model_dump() if kind == "person" else None,
        }
        when = (
            (datetime.fromisoformat(request.recorded_at) + timedelta(seconds=seconds)).isoformat()
            if request.recorded_at
            else f"video+{seconds:.9f}"
        )
        symbol = kind.upper() + ("_ENTER_ZONE" if crossing["direction"] == "down" else "_EXIT_ZONE")
        symbols = [symbol]
        if kind == "person":
            symbols.append(
                {"worn": "HELMET_WORN", "not_worn": "HELMET_NOT_WORN", "unknown": "HELMET_UNKNOWN"}[
                    review.status
                ]
            )
        for symbol in symbols:
            entries.append(
                {
                    "source_key": f"v2:{job_id}:{fingerprint}:{index}:{'helmet' if symbol.startswith('HELMET_') else symbol}",
                    "source_fingerprint": fingerprint,
                    "job_id": job_id,
                    "track_id": crossing["track_id"],
                    "occurred_at": when,
                    "symbol": symbol,
                    "payload": payload,
                }
            )
    # Source can be edited during frame decoding. Fail closed before writing the ledger.
    if source(job_id)[3] != fingerprint:
        raise HTTPException(409, "Revisi berubah selama penyiapan bukti.")
    try:
        return {"events": Ledger(access.store()).append("observation", entries)}
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


class FactFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recording_id: str | None = None
    source_revision: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    class_name: Literal["person", "car", "bus", "truck", "motorcycle", "bicycle"] | None = None
    direction: Literal["up", "down"] | None = None
    start_seconds: float = Field(default=0, ge=0, le=86400, allow_inf_nan=False)
    end_seconds: float | None = Field(default=None, gt=0, le=86400, allow_inf_nan=False)

    @model_validator(mode="after")
    def valid_range(self):
        if self.end_seconds is not None and self.end_seconds <= self.start_seconds:
            raise ValueError("Range must satisfy start < end.")
        if self.source_revision and not self.recording_id:
            raise ValueError("Revision requires a recording.")
        return self


def filtered_facts(rows, filters, role=None):
    selected, excluded = [], []
    for row in rows:
        if row["category"] != "observation":
            continue
        payload = row["payload"]
        if filters.recording_id and row["job_id"] != filters.recording_id:
            continue
        if filters.source_revision and payload.get("source_revision") != filters.source_revision:
            continue
        kind = payload.get(
            "class_name", "person" if row["symbol"].startswith(("PERSON_", "HELMET_")) else None
        )
        if filters.class_name and kind != filters.class_name:
            continue
        if filters.direction and payload.get("direction") != filters.direction:
            continue
        seconds = payload.get("seconds")
        if type(seconds) not in (int, float) or not math.isfinite(seconds):
            continue
        if seconds < filters.start_seconds or (
            filters.end_seconds is not None and seconds >= filters.end_seconds
        ):
            continue
        (selected if row["status"] == "verified" else excluded).append(row)
    crossings = [row for row in selected if row["symbol"].endswith(("_ENTER_ZONE", "_EXIT_ZONE"))]
    helmets = {
        name: sum(row["symbol"] == symbol for row in selected)
        for name, symbol in (
            ("worn", "HELMET_WORN"),
            ("not_worn", "HELMET_NOT_WORN"),
            ("unknown", "HELMET_UNKNOWN"),
        )
    }
    return {
        "schema_version": 2,
        "filter": filters.model_dump(),
        "boundary": "start <= seconds < end",
        "count_unit": "verified crossing events",
        "crossing_event_count": len(crossings),
        "observed_track_count": len({(r["job_id"], r["track_id"]) for r in crossings}),
        "helmet_observations": helmets,
        "unique_object_count": None,
        "coverage": "reviewed events only; not exhaustive video coverage"
        if selected
        else "no verified observations in this filter",
        "has_verified_coverage": bool(selected),
        "excluded_stale_or_retracted": len(excluded),
        "proof": [
            {
                "event_id": row["id"],
                "recording_id": row["job_id"],
                "symbol": row["symbol"],
                "occurred_at": row["occurred_at"],
                "source": row["payload"],
            }
            for row in selected
        ],
        "limitations": [
            "Track bukan identitas atau objek unik.",
            "Nol crossing tidak membuktikan video kosong.",
            "Unknown helm bukan pelanggaran; novelty bukan bahaya.",
        ],
    }


def novelty_detail(run_id):
    from extensions.experiments import registry

    from academic import read_json

    try:
        directory = registry.run_directory(run_id)
        config = read_json(directory / "manifest.json").get("config", {})
        if (
            config.get("workspace_id") != access.workspace_id()
            or config.get("experiment") != "offline-event-novelty-v2"
        ):
            raise HTTPException(404, "Run tidak tersedia dalam workspace ini.")
        registry.read_run(run_id)
        sessions = read_json(directory / "sessions.json", 16 * 2**20)
        current = {row["id"]: row for row in Ledger(access.store()).rows()}
        stale = any(
            current.get(event["id"], {}).get("status") != "verified"
            or current[event["id"]]["payload"].get("source_revision") != event["source_revision"]
            or current[event["id"]]["symbol"] != event["symbol"]
            for session in sessions
            for event in session["source_events"]
        )
        return {
            "run_id": run_id,
            "stale": stale,
            "summary": read_json(directory / "summary.json"),
            "sessions": read_json(directory / "explanations.json", 16 * 2**20),
        }
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(409, "Run belum lengkap atau integritasnya gagal.") from error


def install(app):
    @app.get("/api/ledger/novelty/runs/{run_id}")
    def run_detail(run_id: str):
        return novelty_detail(run_id)

    @app.get("/api/ledger/export")
    def export_events():
        rows = [
            row
            for row in Ledger(access.store()).rows()
            if row["status"] == "verified"
            and row["category"] == "observation"
            and row["payload"].get("schema_version") == 2
        ]
        # Private authenticated export only; identity-bearing attendance never enters event training.
        return {
            "schema_version": 2,
            "workspace_id": access.workspace_id(),
            "events": rows,
            "label_provenance": None,
            "labels": [],
        }

    @app.post("/api/ledger/query")
    def query(request: FactFilter):
        if request.recording_id:
            _, summary, _, fingerprint = source(request.recording_id)
            if request.source_revision and request.source_revision != fingerprint:
                raise HTTPException(409, "Revisi query sudah stale.")
            if request.start_seconds > summary["duration"] or (
                request.end_seconds is not None and request.end_seconds > summary["duration"]
            ):
                raise HTTPException(422, "Rentang query di luar durasi video.")
        return filtered_facts(Ledger(access.store()).rows(), request)

    @app.get("/api/ledger/jobs/{job_id}/preview")
    def preview(job_id: str):
        _, summary, metadata, fingerprint = source(job_id)
        return {
            "schema_version": 2,
            "source_revision": fingerprint,
            "annotation_revision": metadata["annotations"]["revision"],
            "correction_revision": metadata["corrections"]["revision"],
            "model_id": metadata["state"]["model_id"],
            "crossings": summary.get("crossings", []),
            "tracks": summary.get("tracks", []),
            "duration": summary["duration"],
            "fps": summary["fps"],
            "frames": summary["frames"],
        }

    @app.get("/api/ledger/events/{event_id}/proof")
    def proof(event_id: str):
        from fastapi.responses import Response

        row = next(
            (
                r
                for r in Ledger(access.store()).rows()
                if r["id"] == event_id and r["category"] == "observation"
            ),
            None,
        )
        if row is None:
            raise HTTPException(404, "Bukti tidak tersedia dalam workspace ini.")
        if row["status"] != "verified" or row["payload"].get("schema_version") != 2:
            raise HTTPException(409, "Bukti stale/ditarik atau hanya snapshot legacy.")
        folder = source(row["job_id"])[0]
        path = folder / ("ledger_" + row["payload"]["evidence_sha256"] + ".jpg")
        try:
            data = path.read_bytes()
        except OSError as error:
            raise HTTPException(404, "Frame bukti tidak tersedia.") from error
        if hashlib.sha256(data).hexdigest() != row["payload"]["evidence_sha256"]:
            raise HTTPException(409, "Integritas frame bukti gagal.")
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.post("/api/ledger/jobs/{job_id}/import")
    def import_crossings(job_id: str, request: ImportCrossings):
        reviewer()
        folder, summary, metadata, fingerprint = source(job_id)
        if request.schema_version == 2:
            return import_v2(job_id, request, folder, summary, metadata, fingerprint)
        if request.recorded_at is None:
            raise HTTPException(
                422, "Versi 1 memerlukan waktu rekaman; gunakan versi 2 untuk offset."
            )
        entries = []
        start = datetime.fromisoformat(request.recorded_at)
        tracks = {track["id"]: track for track in summary.get("tracks", [])}
        for index in dict.fromkeys(request.crossing_indices):
            crossings = summary.get("crossings", [])
            if not 0 <= index < len(crossings):
                raise HTTPException(422, "Indeks crossing tidak tersedia.")
            crossing = crossings[index]
            track = tracks.get(crossing["track_id"])
            seconds = crossing["seconds"]
            if (
                not track
                or track["kind"] != "person"
                or crossing["kind"] != "person"
                or crossing["direction"] not in {"up", "down"}
                or not isinstance(seconds, (int, float))
                or not math.isfinite(seconds)
                or not 0 <= seconds <= summary["duration"]
            ):
                raise HTTPException(422, "Crossing orang dengan track/waktu valid diperlukan.")
            evidence = track.get("evidence")
            if evidence and (
                not re.fullmatch(r"evidence_\d+\.jpg", evidence)
                or not (folder / evidence).is_file()
            ):
                raise HTTPException(409, "Bukti crossing tidak tersedia.")
            payload = {
                "recording_id": job_id,
                "track_id": crossing["track_id"],
                "seconds": seconds,
                "line": summary["line"],
                "direction": crossing["direction"],
                "model": summary.get("models", {}),
                "model_id": metadata["state"]["model_id"],
                "review_status": "reviewer_approved_crossing",
                "annotation_revision": metadata["annotations"]["revision"],
                "correction_revision": metadata["corrections"]["revision"],
                "evidence": f"/api/jobs/{job_id}/media/{evidence}" if evidence else None,
                "evidence_seconds": track.get("evidence_seconds"),
                "evidence_scope": "track_snapshot_not_crossing_identity",
                "helmet_status": "unknown",
                "recorded_at": request.recorded_at,
            }
            occurred_at = (start + timedelta(seconds=seconds)).isoformat()
            symbol = "PERSON_ENTER_ZONE" if crossing["direction"] == "down" else "PERSON_EXIT_ZONE"
            for event_symbol in (symbol, "HELMET_UNKNOWN"):
                entries.append(
                    {
                        "source_key": f"{job_id}:{fingerprint}:{index}:{event_symbol}",
                        "source_fingerprint": fingerprint,
                        "job_id": job_id,
                        "track_id": crossing["track_id"],
                        "occurred_at": occurred_at,
                        "symbol": event_symbol,
                        "payload": payload,
                    }
                )
        try:
            return {"events": Ledger(access.store()).append("observation", entries)}
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @app.get("/api/ledger/events")
    def events():
        role = access.actor()["role"]
        rows = Ledger(access.store()).rows()
        visible = [row for row in rows if role == "admin" or row["category"] == "observation"]
        if role == "viewer":
            for row in visible:
                row.pop("verifier_id", None)
        return {"events": visible}

    @app.post("/api/ledger/events/{event_id}/retract")
    def retract(event_id: str, request: Retraction):
        reviewer()
        ledger = Ledger(access.store())
        ledger.retract(event_id, request.reason)
        return {"ok": True}

    @app.post("/api/ledger/attendance", status_code=201)
    def attendance(request: Attendance):
        if access.actor()["role"] != "admin":
            raise HTTPException(403, "Verifikasi absensi membutuhkan administrator.")
        if (request.job_id is None) != (request.track_id is None):
            raise HTTPException(422, "Relasi rekaman dan track harus diisi bersama.")
        fingerprint = "manual"
        if request.job_id:
            _, summary, _, fingerprint = source(request.job_id)
            if not any(
                track["id"] == request.track_id and track["kind"] == "person"
                for track in summary.get("tracks", [])
            ):
                raise HTTPException(
                    422, "Track orang tidak tersedia; identitas tidak boleh ditebak."
                )
        payload = request.model_dump()
        payload["verification"] = "manual_admin_verified"
        entry = {
            "source_key": request.source_kind + ":" + request.source_id,
            "source_fingerprint": fingerprint,
            "job_id": request.job_id,
            "track_id": request.track_id,
            "occurred_at": request.occurred_at,
            "symbol": "ATTENDANCE_" + request.action.upper(),
            "payload": payload,
        }
        try:
            return {"records": Ledger(access.store()).append("attendance", [entry])}
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @app.get("/api/ledger/facts")
    def current_facts():
        return facts(Ledger(access.store()).rows())

    @app.get("/api/ledger/novelty/runs")
    def novelty_runs():
        from extensions.experiments import registry

        from academic import read_json

        runs, errors = [], []
        current = {row["id"]: row for row in Ledger(access.store()).rows()}
        folders = sorted(registry.RUNS.iterdir())[:100] if registry.RUNS.is_dir() else []
        for folder in folders:
            config = {}
            try:
                config = read_json(folder / "manifest.json").get("config", {})
                if (
                    config.get("experiment")
                    not in {"offline-event-novelty-v1", "offline-event-novelty-v2"}
                    or config.get("workspace_id") != access.workspace_id()
                ):
                    continue
                registry.read_run(folder.name)
                sessions = read_json(folder / "sessions.json", 16 * 2**20)
                if config.get("schema_version") == 2:
                    stale = any(
                        current.get(row["id"], {}).get("status") != "verified"
                        or current[row["id"]]["symbol"] != row["symbol"]
                        or current[row["id"]]["payload"].get("source_revision")
                        != row["source_revision"]
                        for session in sessions
                        for row in session["source_events"]
                    )
                else:
                    stale = any(
                        current.get(event, {}).get("status") != "verified"
                        or current[event]["symbol"] != symbol
                        or current[event]["occurred_at"] != when
                        for session in sessions
                        for event, symbol, when in zip(
                            session["event_ids"], session["symbols"], session["times"], strict=True
                        )
                    )
                runs.append(
                    {
                        "run_id": folder.name,
                        "summary": {
                            **read_json(folder / "summary.json"),
                            "stale": stale,
                            "scope": "historical offline observation sequences; never live hazard/identity inference",
                        },
                    }
                )
            except (OSError, ValueError, KeyError, TypeError):
                # Do not disclose another workspace's IDs through corrupt/foreign manifests.
                if folder.is_dir() and config.get("workspace_id") == access.workspace_id():
                    errors.append(
                        {
                            "run_id": folder.name,
                            "detail": "Laporan urutan belum selesai atau integritasnya gagal.",
                        }
                    )
        return {"schema_version": 1, "runs": runs, "errors": errors}
