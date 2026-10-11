"""Loopback-only upload, durable results, and grounded video chat."""

from __future__ import annotations

import runtime  # isort: skip  # Set local cache paths before upload/ML imports.

import asyncio
import json
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from contextvars import copy_context
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal, cast
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

import access
from corrections import merge_overlay, read_corrections, render_video
from operations import WorkCancelled, check_cancel
from review import review_queue
from vision import OBJECT_NAMES, process_video, reviewed_summary

MAX_UPLOAD = 250 * 1024 * 1024
state_lock = threading.RLock()
compute_lock = threading.Lock()
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="local-ai")
logger = logging.getLogger("industrial_ai")
export_lock = threading.Lock()
export_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="video-export")
active_work: dict[Path, threading.Event] = {}


def submit_work(pool, worker, folder, *args):
    with state_lock:
        active_work[folder] = threading.Event()
        try:
            pool.submit(copy_context().run, worker, folder, *args)
        except BaseException:
            active_work.pop(folder, None)
            raise


def cancel_work(folder: Path):
    with state_lock:
        event = active_work.get(folder)
        if event is not None and read_state(folder)["status"] in {
            "queued",
            "processing",
            "cancelling",
        }:
            event.set()
            update_state(
                folder,
                status="cancelling",
                message="Membatalkan pada batas kerja berikutnya...",
            )
        return read_state(folder)


def finish_work(folder):
    with state_lock:
        active_work.pop(folder, None)


def job_folder(job_id: str) -> Path:
    try:
        if str(UUID(job_id)) != job_id:
            raise ValueError
    except ValueError as exc:
        raise HTTPException(404, "Video tidak ditemukan.") from exc
    folder = runtime.JOBS / job_id
    access.owned("job", job_id, folder)
    if not access.has_document(folder / "state.json"):
        raise HTTPException(404, "Video tidak ditemukan.")
    return folder


def read_state(folder: Path) -> dict:
    with state_lock:
        return access.read_document(folder / "state.json")


def write_json(path: Path, data: dict) -> None:
    with state_lock:
        access.persist_document(path, data)
        temporary = path.with_suffix(".pending")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)


def update_state(folder: Path, **changes) -> None:
    with state_lock:
        state = read_state(folder)
        state.update(changes)
        write_json(folder / "state.json", state)


def run_video(folder: Path, line: float) -> None:
    cancel = active_work[folder]
    try:
        check_cancel(cancel)
        update_state(folder, status="processing", progress=1, message="Memuat detektor lokal")
        import gc

        import torch

        device, reason = runtime.select_device(read_state(folder).get("device_preference", "auto"))
        update_state(folder, device=device, device_reason=reason)
        callback = lambda p, m: update_state(folder, progress=p, message=m)
        fallback = False
        try:
            summary = process_video(
                folder,
                line,
                callback,
                device=device,
                cancel=cancel,
                **candidate_models(read_state(folder).get("model_id", "")),
            )
        except torch.cuda.OutOfMemoryError:
            if device == "cpu":
                raise
            fallback = True
        if fallback:
            gc.collect()
            torch.cuda.empty_cache()
            device, reason = "cpu", "VRAM habis saat analisis; proses diulang dengan CPU"
            update_state(folder, device=device, device_reason=reason, message=reason)
            summary = process_video(
                folder,
                line,
                callback,
                device=device,
                cancel=cancel,
                **candidate_models(read_state(folder).get("model_id", "")),
            )
        check_cancel(cancel)
        summary["device_reason"] = reason
        model_id = read_state(folder).get("model_id", "")
        if model_id:
            trained = read_state(training_folder(model_id))
            summary["learning_evidence"] = {
                k: trained.get(k)
                for k in (
                    "checkpoint_sha256",
                    "base_sha256",
                    "training_seconds",
                    "group",
                    "metrics",
                )
            }
        summary["model_id"] = read_state(folder).get("model_id", "")
        for name in ("overlays.json", "selection.json", "source.json"):
            path = folder / name
            if path.is_file():
                access.persist_document(path, json.loads(path.read_text(encoding="utf-8")))
        write_json(folder / "summary.json", summary)
        update_state(folder, status="done", progress=100, message="Analisis selesai")
    except WorkCancelled as exc:
        update_state(folder, status="cancelled", message=str(exc))
    except Exception:
        logger.exception("Video analysis failed: %s", folder.name)
        update_state(
            folder,
            status="error",
            message="Video gagal dianalisis. Periksa format/durasi, model lokal, dan log server. Upload asli tetap tersimpan.",
        )
    finally:
        finish_work(folder)
        compute_lock.release()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    access.migrate_existing(training_root)
    # Results survive restart; interrupted work is explicit, never fabricated as complete.
    for path in runtime.JOBS.glob("*/state.json"):
        if read_state(path.parent)["status"] in {"queued", "processing", "uploading", "cancelling"}:
            update_state(
                path.parent,
                status="error",
                message="Proses terhenti ketika server ditutup. Gunakan Coba lagi jika upload lengkap; file lama tetap tersimpan.",
            )
    for path in training_root.glob("*/state.json"):
        data = access.read_document(path)
        if data["status"] in {"queued", "processing", "cancelling"}:
            write_json(
                path,
                {
                    **data,
                    "status": "error",
                    "message": "Training terhenti saat server ditutup. Kandidat belum siap.",
                },
            )
    for path in runtime.JOBS.glob("*/exports/*/state.json"):
        if read_state(path.parent)["status"] in {"queued", "processing", "cancelling"}:
            update_state(path.parent, status="error", message="Ekspor terhenti; coba ekspor lagi.")
    yield
    with state_lock:
        for event in active_work.values():
            event.set()
    executor.shutdown(wait=True)
    export_executor.shutdown(wait=True)
    with tracking_lock:
        for _, tracker, _ in tracking_sessions.values():
            tracker.close()
        tracking_sessions.clear()


app = FastAPI(
    title="Video Insight", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=os.environ.get("INSIGHT_HOSTS", "127.0.0.1,localhost,[::1],testserver").split(
        ","
    ),
)
access.install(app, MAX_UPLOAD)

import academic
import event_ledger
import fact_query

academic.install(app)
event_ledger.install(app)


@app.get("/")
def home():
    return FileResponse(runtime.INDEX, media_type="text/html")


@app.get("/assets/{name}")
def ui_asset(name: str):
    if name not in {
        "dashboard.css",
        "dashboard.js",
        "auth.js",
        "theme.js",
        "motion.js",
        "app.js",
        "brand.svg",
        "crowd.png",
    }:
        raise HTTPException(404, "File UI tidak ditemukan.")
    path = runtime.INDEX.parent / (name if name.endswith(".js") else "assets/" + name)
    if not path.is_file():
        raise HTTPException(503, "Asset UI belum dibangun. Jalankan npm ci dan npm run build.")
    return FileResponse(path)


@app.get("/api/health")
def health():
    return {
        "vision_ready": all((runtime.MODELS / n).is_file() for n in ("yolo26n.pt", "helmet.pt")),
        "chat_ready": (runtime.CHAT_BASE / "config.json").is_file(),
        "adapter_ready": (runtime.CHAT_ADAPTER / "adapter_model.safetensors").is_file(),
        "device": runtime.select_device()[0],
        "device_reason": runtime.select_device()[1],
        "busy": compute_lock.locked(),
    }


@app.get("/api/jobs")
def list_jobs():
    states = [
        read_state(folder)
        for folder in access.folders("job")
        if access.has_document(folder / "state.json")
    ]
    return sorted(states, key=lambda s: s["created_at"], reverse=True)


@app.post("/api/jobs", status_code=202)
async def upload_video(
    file: Annotated[UploadFile, File()],
    line: Annotated[float, Form(ge=0.1, le=0.9)] = 0.5,
    device: Annotated[Literal["auto", "cpu", "cuda"], Form()] = "auto",
    model_id: Annotated[str, Form()] = "",
):
    candidate_models(model_id)
    name = (file.filename or "video").replace(chr(92), "/").rsplit("/", 1)[-1][:120]
    if Path(name).suffix.lower() not in {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}:
        raise HTTPException(415, "Pilih MP4, MOV, AVI, MKV, WEBM, atau M4V.")
    if file.size is not None and file.size > MAX_UPLOAD:
        raise HTTPException(413, "Ukuran video maksimal 250 MB.")
    if not all((runtime.MODELS / n).is_file() for n in ("yolo26n.pt", "helmet.pt")):
        raise HTTPException(503, "Jalankan setup_models.py terlebih dahulu.")
    if not compute_lock.acquire(blocking=False):
        raise HTTPException(409, "AI masih bekerja. Tunggu proses sebelumnya selesai.")
    folder = runtime.JOBS / str(uuid4())
    try:
        folder.mkdir()
        access.register("job", folder)
        state = {
            "id": folder.name,
            "filename": name,
            "created_at": datetime.now(UTC).isoformat(),
            "status": "uploading",
            "progress": 0,
            "message": "Menyimpan upload",
            "line": line,
            "device_preference": device,
            "model_id": model_id,
        }
        write_json(folder / "state.json", state)
        size = 0
        with (folder / "upload.bin").open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, "Ukuran video maksimal 250 MB.")
                target.write(chunk)
        if not size:
            raise HTTPException(422, "File video kosong.")
        update_state(folder, status="queued", bytes=size, message="Menunggu analisis")
        submit_work(executor, run_video, folder, line)
    except BaseException:
        try:
            if access.has_document(folder / "state.json"):
                update_state(
                    folder, status="error", message="Upload tidak selesai. Silakan unggah ulang."
                )
        finally:
            compute_lock.release()
        raise
    finally:
        await file.close()
    return read_state(folder)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    folder = job_folder(job_id)
    state = read_state(folder)
    if state["status"] == "done":
        state["summary"] = result_summary(folder)
    return state


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    return cancel_work(job_folder(job_id))


class ManualBox(BaseModel):
    label: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")
    name: str | None = Field(default=None, max_length=60)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    bbox: tuple[float, float, float, float]

    @model_validator(mode="after")
    def valid_rectangle(self):
        if self.name is not None:
            self.name = self.name.strip()
            if not self.name or any(ord(c) < 32 or ord(c) == 127 for c in self.name):
                raise ValueError("Nama kotak harus berupa teks yang dapat dibaca.")
        x1, y1, x2, y2 = self.bbox
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError("Kotak harus berada dalam frame dan mempunyai luas positif.")
        return self


class ManualFrame(BaseModel):
    frame_index: int = Field(ge=0)
    revision: int = Field(ge=0)
    complete: bool = False
    helmets_complete: bool = False
    learn_group: Literal["objects", "helmets"] | None = None
    boxes: list[ManualBox] = Field(max_length=100)


def completed_folder(job_id: str) -> tuple[Path, dict]:
    folder = job_folder(job_id)
    if read_state(folder)["status"] != "done":
        raise HTTPException(409, "Analisis video belum selesai.")
    return folder, access.read_document(folder / "summary.json")


def read_annotations(folder: Path) -> dict:
    with state_lock:
        return access.read_document(folder / "annotations.json", {"revision": 0, "frames": []})


def result_summary(folder: Path) -> dict:
    summary = access.read_document(folder / "summary.json")
    annotations = read_annotations(folder)
    summary["manual_frames"] = annotations["frames"]
    summary = reviewed_summary(summary)
    state = read_state(folder)
    corrections = access.read_document(folder / "tracking_corrections.json", {"revision": 0})
    summary["result_provenance"] = {
        "detector_source": "fine_tuned_candidate" if state.get("model_id") else "original_detector",
        "model_id": state.get("model_id"),
        "source_job_id": state.get("source_job_id"),
        "annotation_revision": annotations["revision"],
        "correction_revision": corrections["revision"],
        "has_review_corrections": bool(annotations["frames"] or corrections["revision"]),
        "weight_update_on_save": False,
    }
    return summary


@app.get("/api/jobs/{job_id}/summary")
def download_reviewed_summary(job_id: str):
    folder, _ = completed_folder(job_id)
    return JSONResponse(
        result_summary(folder),
        headers={
            "Content-Disposition": 'attachment; filename="summary_reviewed.json"',
        },
    )


def frame_image(folder: Path, frame_index: int, summary: dict) -> bytes:
    import cv2

    if not 0 <= frame_index < summary["frames"]:
        raise HTTPException(422, "Frame di luar video.")
    capture = cv2.VideoCapture(str(folder / "original.mp4"))
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok:
            raise HTTPException(422, "Frame tidak dapat dibaca.")
        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            raise HTTPException(500, "Frame tidak dapat disimpan.")
        return encoded.tobytes()
    finally:
        capture.release()


@app.get("/api/jobs/{job_id}/frame/{frame_index}")
def get_frame(job_id: str, frame_index: int):
    folder, summary = completed_folder(job_id)
    return Response(frame_image(folder, frame_index, summary), media_type="image/jpeg")


@app.get("/api/jobs/{job_id}/suggestions/{frame_index}")
def suggest_boxes(job_id: str, frame_index: int, group: Literal["objects", "helmets"] = "objects"):
    import cv2
    import numpy as np
    from ultralytics import YOLO
    from ultralytics.engine.results import Results

    folder, summary = completed_folder(job_id)
    image = frame_image(folder, frame_index, summary)
    if not compute_lock.acquire(blocking=False):
        raise HTTPException(
            409, "AI sedang bekerja. Gambar kotak baru atau coba kotak AI setelah selesai."
        )
    try:
        frame = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(422, "Frame anotasi gagal dibaca.")
        models = candidate_models(read_state(folder).get("model_id", ""))
        key = "object_model" if group == "objects" else "helmet_model"
        base = "yolo26n.pt" if group == "objects" else "helmet.pt"
        model = YOLO(str(models.get(key, runtime.MODELS / base)))
        classes = (
            None
            if group == "helmets"
            else [
                i
                for i, name in model.names.items()
                if name in models.get("object_classes", OBJECT_NAMES)
            ]
        )
        # ponytail: isolated frame suggestions use CPU; batch GPU inference belongs to video analysis.
        result = cast(
            list[Results],
            model.predict(
                frame,
                classes=classes,
                conf=0.35,
                imgsz=640,
                device="cpu",
                verbose=False,
                stream=False,
            ),
        )[0]
        height, width = frame.shape[:2]
        boxes = []
        if result.boxes is not None:
            for coords, cls in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist()):
                x1, y1, x2, y2 = coords
                boxes.append(
                    {
                        "label": model.names[int(cls)].replace(" ", "_"),
                        "name": None,
                        "color": None,
                        "bbox": [
                            max(0, x1 / width),
                            max(0, y1 / height),
                            min(1, x2 / width),
                            min(1, y2 / height),
                        ],
                    }
                )
        return {"boxes": boxes[:100], "source": "AI suggestion; review before learning"}
    finally:
        compute_lock.release()


class TrackingPrompt(BaseModel):
    frame_index: int = Field(ge=0)
    boxes: list[ManualBox] = Field(max_length=100)
    revision: int | None = Field(default=None, ge=0)
    suppressed_ids: list[Annotated[int, Field(ge=0)]] = Field(default_factory=list, max_length=100)


class TrackingStep(BaseModel):
    after_frame: int = Field(ge=0)
    count: int = Field(default=10, ge=1, le=10)


tracking_lock = threading.RLock()
tracking_sessions: dict = {}


@app.get("/api/jobs/{job_id}/corrections")
def get_corrections(job_id: str):
    folder, _ = completed_folder(job_id)
    with state_lock:
        return read_corrections(folder)


def persist_tracking(folder: Path, tracker, metadata: dict, frames: list) -> dict:
    data = read_corrections(folder)
    if data["revision"] != metadata["revision"]:
        raise HTTPException(
            409, "Tracking koreksi berubah di tab lain. Muat ulang sebelum memutar."
        )
    if frames:
        rows = [
            merge_overlay(f, tracker.overlays.get(f["frame_index"], []), metadata["suppressed"])
            for f in frames
        ]
        by_frame = {f["frame_index"]: f for f in data["frames"]}
        by_frame.update({f["frame_index"]: f for f in rows})
        data = {
            "revision": data["revision"] + 1,
            "frames": sorted(by_frame.values(), key=lambda f: f["frame_index"]),
        }
        write_json(folder / "tracking_corrections.json", data)
        metadata["revision"] = data["revision"]
        return {"frames": rows, "revision": data["revision"]}
    return {"frames": [], "revision": data["revision"]}


@app.get("/api/jobs/{job_id}/overlays")
def analyzed_overlays(job_id: str):
    folder, _ = completed_folder(job_id)
    path = folder / "overlays.json"
    return access.read_document(path, {"frames": []})


@app.post("/api/jobs/{job_id}/tracking")
def start_tracking(job_id: str, request: TrackingPrompt):
    import time

    from prompt_tracking import PromptTracker

    folder, summary = completed_folder(job_id)
    if request.frame_index >= summary["frames"]:
        raise HTTPException(422, "Frame di luar video.")
    with tracking_lock, state_lock:
        for key, (owner, tracker, _) in list(tracking_sessions.items()):
            if time.monotonic() - tracker.touched > 120:
                tracker.close()
                del tracking_sessions[key]
        if len(tracking_sessions) >= 4:
            raise HTTPException(409, "Empat sesi tracker aktif. Tutup anotasi pada tab lain.")
        revision = read_corrections(folder)["revision"]
        if request.revision is not None and request.revision != revision:
            raise HTTPException(
                409, "Tracking koreksi berubah di tab lain. Muat ulang sebelum memutar."
            )
        try:
            tracker = PromptTracker(
                folder / "original.mp4",
                request.frame_index,
                [b.model_dump() for b in request.boxes],
                analyzed_overlays(job_id)["frames"],
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        metadata = {
            "revision": revision,
            "suppressed": set(request.suppressed_ids),
            "user_id": access.actor()["id"],
            "workspace_id": access.workspace_id(),
        }
        try:
            saved = persist_tracking(folder, tracker, metadata, [tracker.snapshot()])
        except BaseException:
            tracker.close()
            raise
        key = str(uuid4())
        tracking_sessions[key] = (job_id, tracker, metadata)
        return {
            "id": key,
            "frame": saved["frames"][0],
            "revision": saved["revision"],
            "method": "cached_detector_and_optical_flow",
            "message": "Mengikuti kotak pada video ini; bobot YOLO tidak berubah.",
        }


@app.post("/api/jobs/{job_id}/tracking/{session_id}/step")
def advance_tracking(job_id: str, session_id: str, request: TrackingStep):
    with tracking_lock, state_lock:
        owner, tracker, metadata = tracking_sessions.get(session_id, (None, None, None))
        if (
            owner != job_id
            or tracker is None
            or metadata["user_id"] != access.actor()["id"]
            or metadata["workspace_id"] != access.workspace_id()
        ):
            raise HTTPException(404, "Sesi tracker berakhir. Jeda dan putar lagi.")
        if request.after_frame != tracker.index:
            raise HTTPException(409, "Posisi tracker berubah. Jeda dan putar lagi.")
        folder = job_folder(job_id)
        persist_tracking(folder, tracker, metadata, [])  # Check revision before advancing pixels.
        result = tracker.advance(request.count)
        return {**result, **persist_tracking(folder, tracker, metadata, result["frames"])}


@app.post("/api/jobs/{job_id}/tracking/{session_id}/stop")
def stop_tracking(job_id: str, session_id: str):
    job_folder(job_id)
    with tracking_lock:
        owner, tracker, metadata = tracking_sessions.get(session_id, (None, None, None))
        if (
            owner == job_id
            and tracker is not None
            and metadata["user_id"] == access.actor()["id"]
            and metadata["workspace_id"] == access.workspace_id()
        ):
            tracker.close()
            del tracking_sessions[session_id]
    return {"stopped": True}


@app.post("/api/jobs/{job_id}/corrected-video")
def export_corrected_video(job_id: str):
    folder, summary = completed_folder(job_id)
    with state_lock:
        corrections, annotations = read_corrections(folder), read_annotations(folder)
    if not corrections["frames"] and not annotations["frames"]:
        raise HTTPException(409, "Belum ada tracking/kotak koreksi yang tersimpan.")
    target = folder / f"corrected_c{corrections['revision']}_a{annotations['revision']}.mp4"
    if not target.is_file():
        if not export_lock.acquire(blocking=False):
            raise HTTPException(409, "Ekspor lain sedang berjalan. Tunggu proses selesai.")
        try:
            if not target.is_file():
                render_video(folder, target, summary, corrections, annotations)
        except Exception as exc:
            logger.exception("Corrected video export failed: %s", job_id)
            raise HTTPException(
                500,
                "Ekspor video koreksi gagal. Hasil awal tetap tersimpan; periksa FFmpeg/log server.",
            ) from exc
        finally:
            export_lock.release()
    return FileResponse(target, media_type="video/mp4", filename=target.name)


def export_folder(job_id: str, revision: str) -> Path:
    if not re.fullmatch(r"c\d+_a\d+", revision):
        raise HTTPException(404, "Ekspor tidak ditemukan.")
    folder = job_folder(job_id) / "exports" / revision
    if not access.has_document(folder / "state.json"):
        raise HTTPException(404, "Ekspor tidak ditemukan.")
    return folder


def run_export(folder, source, target, summary, corrections, annotations):
    cancel = active_work[folder]
    try:
        check_cancel(cancel)
        update_state(folder, status="processing", message="Merender video koreksi", progress=1)
        if not target.is_file():
            render_video(
                source,
                target,
                summary,
                corrections,
                annotations,
                progress=lambda p, m: update_state(folder, progress=p, message=m),
                cancel=cancel,
            )
        check_cancel(cancel)
        update_state(folder, status="done", progress=100, message="Video koreksi siap.")
    except WorkCancelled as exc:
        update_state(folder, status="cancelled", message=str(exc))
    except Exception:
        logger.exception("Export failed: %s", folder)
        update_state(
            folder, status="error", message="Ekspor gagal; hasil awal tetap tersimpan. Coba lagi."
        )
    finally:
        finish_work(folder)
        export_lock.release()


@app.post("/api/jobs/{job_id}/exports", status_code=202)
def start_export(job_id: str):
    source, summary = completed_folder(job_id)
    with state_lock:
        corrections, annotations = read_corrections(source), read_annotations(source)
        if not corrections["frames"] and not annotations["frames"]:
            raise HTTPException(409, "Belum ada koreksi tersimpan.")
        revision = f"c{corrections['revision']}_a{annotations['revision']}"
        folder = source / "exports" / revision
        if access.has_document(folder / "state.json") and read_state(folder)["status"] in {
            "queued",
            "processing",
            "cancelling",
            "done",
        }:
            return read_state(folder)
        if not export_lock.acquire(blocking=False):
            raise HTTPException(409, "Ekspor lain masih berjalan.")
        try:
            folder.mkdir(parents=True, exist_ok=True)
            target = source / f"corrected_{revision}.mp4"
            write_json(
                folder / "state.json",
                {
                    "id": revision,
                    "status": "queued",
                    "progress": 0,
                    "message": "Menunggu ekspor",
                    "filename": target.name,
                    "media_url": f"/api/jobs/{job_id}/media/{target.name}",
                },
            )
            submit_work(
                export_executor,
                run_export,
                folder,
                source,
                target,
                summary,
                corrections,
                annotations,
            )
        except BaseException:
            export_lock.release()
            raise
        return read_state(folder)


@app.get("/api/jobs/{job_id}/exports/{revision}")
def get_export(job_id: str, revision: str):
    return read_state(export_folder(job_id, revision))


@app.post("/api/jobs/{job_id}/exports/{revision}/cancel")
def cancel_export(job_id: str, revision: str):
    return cancel_work(export_folder(job_id, revision))


@app.get("/api/jobs/{job_id}/review-queue")
def get_review_queue(job_id: str, group: Literal["objects", "helmets"] = "objects"):
    folder, summary = completed_folder(job_id)
    with state_lock:
        return review_queue(
            folder, read_annotations(folder), read_corrections(folder), summary, group
        )


@app.get("/api/jobs/{job_id}/annotations")
def get_annotations(job_id: str):
    folder, _ = completed_folder(job_id)
    return read_annotations(folder)


@app.post("/api/jobs/{job_id}/annotations")
def save_annotations(job_id: str, request: ManualFrame):
    folder, summary = completed_folder(job_id)
    with state_lock:
        data = read_annotations(folder)
        if request.revision != data["revision"]:
            raise HTTPException(
                409, "Koreksi berubah di tab lain. Muat ulang koreksi sebelum menyimpan."
            )
        image = frame_image(folder, request.frame_index, summary)
        snapshot = folder / f"annotation_{request.frame_index}.jpg"
        if not snapshot.is_file():
            pending_image = snapshot.with_suffix(".pending")
            pending_image.write_bytes(image)
            pending_image.replace(snapshot)
        previous = next((f for f in data["frames"] if f["frame_index"] == request.frame_index), {})
        boxes = [box.model_dump() for box in request.boxes]
        approved = []
        flags = {}
        for group, flag in [("objects", "complete"), ("helmets", "helmets_complete")]:

            def labels(items, group=group):
                return sorted(
                    (b["label"], tuple(b["bbox"]))
                    for b in items
                    if (b["label"] in {"Hardhat", "NO-Hardhat"}) == (group == "helmets")
                )

            unchanged = labels(boxes) == labels(previous.get("boxes", []))
            flags[flag] = bool(
                getattr(request, flag)
                if request.learn_group in {None, group}
                else unchanged and previous.get(flag)
            )
            if unchanged and previous.get(flag):
                flags[flag] = True
            if request.learn_group == group:
                if not getattr(request, flag):
                    raise HTTPException(422, "Kelompok yang disahkan harus ditandai lengkap.")
                approved.append(group)
            elif unchanged and group in previous.get("learn_groups", []) and flags[flag]:
                approved.append(group)
        row = {
            "frame_index": request.frame_index,
            "seconds": round(request.frame_index / summary["fps"], 2),
            **flags,
            "boxes": boxes,
            "updated_at": datetime.now(UTC).isoformat(),
            "source": "manual",
            "learn_groups": approved,
        }
        data["frames"] = [f for f in data["frames"] if f["frame_index"] != request.frame_index] + [
            row
        ]
        data["frames"].sort(key=lambda f: f["frame_index"])
        data["revision"] += 1
        write_json(folder / "annotations.json", data)
    return data


@app.get("/api/jobs/{job_id}/dataset")
def export_annotations(job_id: str):
    import hashlib
    import zipfile

    folder, _ = completed_folder(job_id)
    with state_lock:
        data = read_annotations(folder)
        frames = [f for f in data["frames"] if f["complete"] or f.get("helmets_complete", False)]
        if not frames:
            raise HTTPException(409, "Belum ada frame yang ditandai selesai ditinjau.")
        target = folder / f"annotations_v2_r{data['revision']}.zip"
        if not target.is_file():
            pending = target.with_suffix(".pending")
            with zipfile.ZipFile(pending, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                custom = sorted(
                    {
                        b["label"]
                        for f in frames
                        if f["complete"]
                        for b in f["boxes"]
                        if b["label"] not in {*OBJECT_NAMES, "Hardhat", "NO-Hardhat"}
                    }
                )
                groups = [
                    ("objects", (*OBJECT_NAMES, *custom), "complete"),
                    ("helmets", ("Hardhat", "NO-Hardhat"), "helmets_complete"),
                ]
                for group, labels, flag in groups:
                    selected = [f for f in frames if f.get(flag, False)]
                    if not selected:
                        continue
                    archive.writestr(f"{group}/classes.txt", "\n".join(labels) + "\n")
                    for frame in selected:
                        stem = f"{job_id}_{frame['frame_index']:04}"
                        archive.write(
                            folder / f"annotation_{frame['frame_index']}.jpg",
                            f"{group}/images/{stem}.jpg",
                        )
                        rows = []
                        for box in frame["boxes"]:
                            if box["label"] not in labels:
                                continue
                            x1, y1, x2, y2 = box["bbox"]
                            rows.append(
                                f"{labels.index(box['label'])} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"
                            )
                        archive.writestr(
                            f"{group}/labels/{stem}.txt", "\n".join(rows) + ("\n" if rows else "")
                        )
                archive.writestr(
                    "annotations.json",
                    json.dumps(
                        {
                            "schema_version": 2,
                            "job_id": job_id,
                            "revision": data["revision"],
                            "frames": frames,
                            "source_upload_sha256": hashlib.sha256(
                                (folder / "upload.bin").read_bytes()
                            ).hexdigest(),
                            "split": "unassigned",
                            "label_source": "manual review",
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
                archive.writestr(
                    "README.md",
                    "# Koreksi manual - format YOLO\n\n"
                    "objects/ dan helmets/ diekspor terpisah sesuai kelompok koreksi yang diselesaikan. images/ dan labels/ berpasangan; kelas mengikuti classes.txt masing-masing kelompok. Koordinat center-x, center-y, width, height ternormalisasi.\n"
                    "person/kendaraan/kelas khusus: kotak seluruh objek; Hardhat/NO-Hardhat: kotak helm/kepala.\n"
                    "Frame selesai ditinjau dipilih oleh pengguna; bukan label yang divalidasi independen.\n"
                    "Pisahkan train/val/test berdasarkan video/situs agar frame berdekatan tidak bocor antar split.\n"
                    "Warna/nama adalah tampilan; target training memakai label. Saat menggabungkan ZIP, petakan class ID berdasarkan nama classes.txt.\n"
                    "Data belum melatih model. Gunakan data beragam dan evaluasi model kandidat sebelum mengganti model aktif.\n",
                )
            pending.replace(target)
    return FileResponse(
        target, media_type="application/zip", filename=f"koreksi_{job_id}_r{data['revision']}.zip"
    )


@app.get("/api/jobs/{job_id}/media/{name}")
def media(job_id: str, name: str):
    folder = job_folder(job_id)
    if not re.fullmatch(
        r"original\.mp4|tracked\.mp4|corrected_c\d+_a\d+\.mp4|evidence_\d+\.jpg|helmet_\d+\.jpg|annotation_\d+\.jpg|summary\.json|upload\.bin",
        name,
    ):
        raise HTTPException(404, "Media tidak ditemukan.")
    path = folder / name
    if name == "summary.json":
        return JSONResponse(access.read_document(path))
    if not path.is_file():
        raise HTTPException(404, "Media belum tersedia.")
    if name == "upload.bin":
        return FileResponse(
            path, media_type="application/octet-stream", filename=read_state(folder)["filename"]
        )
    return FileResponse(path)


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=600)
    job_id: str | None = None
    device: Literal["auto", "cpu", "cuda"] = "auto"
    history: list[Turn] = Field(default_factory=list, max_length=6)


@app.post("/api/chat")
async def chat(request: ChatRequest):
    from chat import answer_facts, generate_reply

    if not request.message.strip():
        raise HTTPException(422, "Tulis pertanyaan terlebih dahulu.")
    summary = None
    if request.job_id:
        folder = job_folder(request.job_id)
        if read_state(folder)["status"] != "done":
            raise HTTPException(409, "Analisis video ini belum selesai.")
        summary = result_summary(folder)
    ledger_answer = fact_query.answer_ledger(
        request.message,
        event_ledger.Ledger(access.store()).rows(),
        access.actor()["role"],
        request.job_id,
    )
    if ledger_answer is not None:
        return ledger_answer
    facts = answer_facts(request.message, summary)
    if facts:
        return facts
    if not compute_lock.acquire(blocking=False):
        raise HTTPException(429, "Model sedang bekerja. Coba lagi setelah proses selesai.")
    try:
        history = [turn.model_dump() for turn in request.history]
        return await asyncio.get_running_loop().run_in_executor(
            executor, generate_reply, request.message, history, summary, request.device
        )
    except Exception as exc:
        logger.exception("Local chatbot failed")
        raise HTTPException(
            503, "Model chat gagal dimuat/dijalankan. Periksa model dan log server."
        ) from exc
    finally:
        compute_lock.release()


training_root = runtime.DATA_ROOT / "trainings"
training_root.mkdir(parents=True, exist_ok=True)


def training_folder(training_id: str) -> Path:
    try:
        if str(UUID(training_id)) != training_id:
            raise ValueError
    except ValueError as exc:
        raise HTTPException(404, "Training tidak ditemukan.") from exc
    folder = training_root / training_id
    access.owned("training", training_id, folder)
    if not access.has_document(folder / "state.json"):
        raise HTTPException(404, "Training tidak ditemukan.")
    return folder


def candidate_models(model_id: str) -> dict:
    if not model_id:
        return {}
    folder = training_folder(model_id)
    data = read_state(folder)
    checkpoint = folder / "weights/best.pt"
    if data["status"] != "done" or not checkpoint.is_file():
        raise HTTPException(409, "Model kandidat belum siap. Pilih model dasar.")
    key = "object_model" if data["group"] == "objects" else "helmet_model"
    return (
        {
            key: checkpoint,
            "object_classes": list(dict.fromkeys([*OBJECT_NAMES, *data["learned_classes"]])),
        }
        if key == "object_model"
        else {key: checkpoint}
    )


@app.get("/api/training")
def training_list():
    return sorted(
        [
            read_state(folder)
            for folder in access.folders("training")
            if access.has_document(folder / "state.json")
        ],
        key=lambda d: d["created_at"],
        reverse=True,
    )


@app.get("/api/training/eligible")
def training_eligible():
    items = []
    for folder in access.folders("job"):
        if not access.has_document(folder / "state.json") or read_state(folder)["status"] != "done":
            continue
        data = read_annotations(folder)
        items.append(
            {
                "id": folder.name,
                "filename": read_state(folder)["filename"],
                "objects": sum(f["complete"] for f in data["frames"]),
                "helmets": sum(f.get("helmets_complete", False) for f in data["frames"]),
            }
        )
    return items


class DetectorTrainingRequest(BaseModel):
    job_ids: list[str] = Field(min_length=2, max_length=50)
    group: Literal["objects", "helmets"] = "objects"
    epochs: int = Field(default=10, ge=1, le=50)
    device: Literal["auto", "cpu", "cuda"] = "auto"


def run_training(folder: Path):
    handed_off = False
    cancel = active_work[folder]
    try:
        check_cancel(cancel)
        from detector_training import train_candidate

        update_state(
            folder,
            status="processing",
            progress=1,
            message="Menyiapkan dataset dan melepas memori chat",
        )
        result = train_candidate(
            folder,
            read_state(folder),
            lambda p, m: update_state(folder, progress=p, message=m),
            cancel,
        )
        check_cancel(cancel)
        with state_lock:
            check_cancel(cancel)
            update_state(
                folder,
                **result,
                status="done",
                progress=100,
                message="Model hasil koreksi tersimpan.",
            )
            state = read_state(folder)
            if state.get("followup_job_id"):
                analysis = create_reanalysis(
                    state["followup_job_id"],
                    ReanalysisRequest(model_id=folder.name, device=state["device_preference"]),
                )
                handed_off = True
                update_state(
                    folder,
                    result_job_id=analysis["id"],
                    message="Belajar selesai; menganalisis ulang video.",
                )
    except WorkCancelled as exc:
        update_state(folder, status="cancelled", message=str(exc))
    except Exception:
        logger.exception("Detector training failed: %s", folder.name)
        update_state(
            folder,
            status="error",
            message="Training gagal. Dataset dan hasil sebelumnya tetap tersimpan; periksa log server.",
        )
    finally:
        finish_work(folder)
        if not handed_off:
            compute_lock.release()


def start_detector_training(
    request: DetectorTrainingRequest,
    *,
    approved_only=False,
    followup_job_id=None,
    fingerprint=None,
    review_snapshot=None,
):
    from detector_training import collect_reviewed

    folders = [completed_folder(i)[0] for i in dict.fromkeys(request.job_ids)]
    try:
        with state_lock:
            rows = (
                review_snapshot
                if review_snapshot is not None
                else collect_reviewed(folders, request.group, approved_only=approved_only)
            )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not compute_lock.acquire(blocking=False):
        raise HTTPException(409, "AI sedang bekerja; tunggu proses sebelumnya selesai.")
    folder = training_root / str(uuid4())
    try:
        folder.mkdir()
        access.register("training", folder)
        write_json(
            folder / "state.json",
            {
                "id": folder.name,
                "created_at": datetime.now(UTC).isoformat(),
                "status": "queued",
                "progress": 0,
                "message": "Training masuk antrean",
                "group": request.group,
                "epochs": request.epochs,
                "device_preference": request.device,
                "source_folders": [str(f) for f in folders],
                "review_snapshot": [{**r, "image": str(r["image"])} for r in rows],
                "followup_job_id": followup_job_id,
                "fingerprint": fingerprint,
            },
        )
        submit_work(executor, run_training, folder)
    except BaseException:
        compute_lock.release()
        raise
    return read_state(folder)


@app.post("/api/training", status_code=202)
def submit_training(request: DetectorTrainingRequest):
    return start_detector_training(request)


class LearningRequest(BaseModel):
    group: Literal["objects", "helmets"] = "objects"
    device: Literal["auto", "cpu", "cuda"] = "auto"


@app.post("/api/jobs/{job_id}/learn")
def learn_corrections(job_id: str, request: LearningRequest):
    import hashlib

    from detector_training import collect_reviewed

    current, _ = completed_folder(job_id)
    queue = get_review_queue(job_id, request.group)
    if queue["pending"] or not queue["total"]:
        return {
            "status": "waiting",
            "message": f"Koreksi tersimpan. Selesaikan antrean {request.group}: {queue['pending']} posisi belum disahkan.",
        }
    flag = "complete" if request.group == "objects" else "helmets_complete"
    if not any(
        f.get(flag) and request.group in f.get("learn_groups", [])
        for f in read_annotations(current)["frames"]
    ):
        raise HTTPException(409, "Simpan koreksi lengkap pada video ini terlebih dahulu.")
    folders = []
    for item in training_eligible():
        folder = job_folder(item["id"])
        if (
            any(
                f.get(flag) and request.group in f.get("learn_groups", [])
                for f in read_annotations(folder)["frames"]
            )
            and not get_review_queue(item["id"], request.group)["pending"]
        ):
            folders.append(folder)
    # Keep the latest correction of each source frame, including copied reanalyses.
    try:
        rows = collect_reviewed(folders, request.group, approved_only=True)
    except ValueError as exc:
        return {"status": "waiting", "message": "Koreksi tersimpan dan bisa ditanya. " + str(exc)}
    signature = sorted(
        (
            r["source_sha256"],
            r["source_position"],
            [{"label": b["label"], "bbox": b["bbox"]} for b in r["boxes"]],
        )
        for r in rows
    )
    fingerprint = hashlib.sha256(
        json.dumps([request.group, signature], sort_keys=True).encode()
    ).hexdigest()
    previous = next(
        (
            t
            for t in training_list()
            if t.get("fingerprint") == fingerprint
            and t["status"] in {"queued", "processing", "done"}
        ),
        None,
    )
    if previous:
        if previous["status"] == "done":
            existing = next(
                (
                    j
                    for j in list_jobs()
                    if j.get("source_job_id") == job_id
                    and j.get("model_id") == previous["id"]
                    and j["status"] in {"queued", "processing", "done"}
                ),
                None,
            )
            outcome = existing or reanalyze(
                job_id, ReanalysisRequest(model_id=previous["id"], device=request.device)
            )
            return {**previous, "result_job_id": outcome["id"]}
        return previous
    ids = list(dict.fromkeys(r["job_id"] for r in rows))
    if len(ids) > 50:
        raise HTTPException(422, "Maksimal 50 video untuk pembelajaran lokal.")
    return start_detector_training(
        DetectorTrainingRequest(job_ids=ids, group=request.group, device=request.device),
        approved_only=True,
        followup_job_id=job_id,
        fingerprint=fingerprint,
        review_snapshot=rows,
    )


@app.get("/api/training/{training_id}")
def get_training(training_id: str):
    return read_state(training_folder(training_id))


@app.post("/api/training/{training_id}/cancel")
def cancel_training(training_id: str):
    return cancel_work(training_folder(training_id))


class ReanalysisRequest(BaseModel):
    model_id: str = ""
    device: Literal["auto", "cpu", "cuda"] = "auto"


@app.post("/api/jobs/{job_id}/reanalyze", status_code=202)
def reanalyze(job_id: str, request: ReanalysisRequest):
    completed_folder(job_id)
    candidate_models(request.model_id)
    if not compute_lock.acquire(blocking=False):
        raise HTTPException(409, "AI sedang bekerja. Tunggu proses sebelumnya selesai.")
    try:
        return create_reanalysis(job_id, request)
    except BaseException:
        compute_lock.release()
        raise


def create_reanalysis(job_id: str, request: ReanalysisRequest):
    """Create a new result while the caller owns compute_lock; worker releases it."""
    import shutil

    source = job_folder(job_id)
    previous = read_state(source)
    upload = source / "upload.bin"
    expected = previous.get("bytes")
    if not expected and previous["status"] == "done" and (source / "original.mp4").is_file():
        expected = upload.stat().st_size if upload.is_file() else 0
    if not upload.is_file() or not expected or upload.stat().st_size != expected:
        raise HTTPException(
            409, "Upload tidak lengkap. Unggah ulang video; data lama tetap tersimpan."
        )
    target = runtime.JOBS / str(uuid4())
    target.mkdir()
    access.register("job", target)
    previous = read_state(source)
    shutil.copyfile(source / "upload.bin", target / "upload.bin")
    for correction in [
        source / "annotations.json",
        source / "source.json",
        source / "selection.json",
        *source.glob("annotation_*.jpg"),
    ]:
        if correction.is_file():
            shutil.copyfile(correction, target / correction.name)
            if correction.suffix == ".json":
                write_json(target / correction.name, access.read_document(correction))
    state = {
        "id": target.name,
        "filename": previous["filename"],
        "created_at": datetime.now(UTC).isoformat(),
        "status": "queued",
        "progress": 0,
        "message": "Analisis ulang dengan model pilihan",
        "line": previous["line"],
        "device_preference": request.device,
        "model_id": request.model_id,
        "source_job_id": job_id,
        "bytes": expected,
    }
    write_json(target / "state.json", state)
    submit_work(executor, run_video, target, state["line"])
    return read_state(target)


@app.post("/api/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str, request: ReanalysisRequest):
    if read_state(job_folder(job_id))["status"] not in {"error", "cancelled"}:
        raise HTTPException(409, "Coba lagi tersedia untuk proses gagal atau dibatalkan.")
    candidate_models(request.model_id)
    if not compute_lock.acquire(blocking=False):
        raise HTTPException(409, "AI masih bekerja. Tunggu proses selesai.")
    try:
        return create_reanalysis(job_id, request)
    except BaseException:
        compute_lock.release()
        raise
