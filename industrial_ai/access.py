"""Authenticated workspace boundary and local administration; no default credentials."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import io
import json
import os
import unicodedata
import warnings
from contextvars import ContextVar
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, field_validator

import runtime
from storage import Store

principal: ContextVar[dict | None] = ContextVar("workspace_principal", default=None)
_stores: dict[Path, Store] = {}
COOKIE = "insight_session"
DOCUMENTS = {
    "state.json",
    "summary.json",
    "annotations.json",
    "tracking_corrections.json",
    "overlays.json",
    "source.json",
    "selection.json",
}


def database_path() -> Path:
    if runtime.JOBS.resolve() == (runtime.DATA_ROOT / "jobs").resolve():
        return runtime.JOBS.parent / "security" / "studio.sqlite3"
    return runtime.JOBS / ".security" / "studio.sqlite3"


def store() -> Store:
    path = database_path()
    if path not in _stores:
        _stores[path] = Store(path)
    return _stores[path]


def actor() -> dict:
    value = principal.get()
    if value is None:
        raise HTTPException(401, "Silakan masuk terlebih dahulu.")
    return value


def workspace_id() -> str:
    return actor()["workspace_id"]


def register(kind: str, folder: Path) -> None:
    store().register_resource(kind, folder.name, workspace_id(), str(folder.resolve()))


def owned(kind: str, resource_id: str, folder: Path) -> None:
    record = store().require_resource(kind, resource_id, workspace_id())
    if record is None or Path(record["path"]).resolve() != folder.resolve():
        raise HTTPException(404, "Data tidak ditemukan dalam workspace ini.")


def folders(kind: str) -> list[Path]:
    return [Path(row["path"]) for row in store().list_resources(kind, workspace_id())]


def managed(path: Path) -> bool:
    if path.name not in DOCUMENTS:
        return False
    return any(
        path.resolve().is_relative_to(root.resolve())
        for root in (runtime.JOBS, runtime.JOBS.parent / "trainings")
    )


def has_document(path: Path) -> bool:
    return (
        managed(path) and store().get_document(str(path.resolve())) is not None
    ) or path.is_file()


def read_document(path: Path, default=None):
    if managed(path):
        data = store().get_document(str(path.resolve()))
        if data is not None:
            return data
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    if default is not None:
        return default
    raise FileNotFoundError(path)


def persist_document(path: Path, data: dict) -> None:
    if managed(path):
        store().put_document(str(path.resolve()), data)


def migrate_existing(training_root: Path) -> None:
    database = store()
    default = database.workspace()
    for kind, root in (("job", runtime.JOBS), ("training", training_root)):
        for file in root.glob("*/state.json"):
            folder = file.parent
            # Already owned rows and documents are never reassigned or re-imported.
            with database.connection() as connection:
                exists = connection.execute(
                    "SELECT 1 FROM resources WHERE kind=? AND id=?", (kind, folder.name)
                ).fetchone()
            if not exists:
                database.register_resource(kind, folder.name, default, str(folder.resolve()))
            for path in folder.rglob("*.json"):
                if path.name in DOCUMENTS and database.get_document(str(path.resolve())) is None:
                    database.put_document(
                        str(path.resolve()), json.loads(path.read_text(encoding="utf-8"))
                    )


def headers(response):
    response.headers.update(
        {
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "same-origin",
            "Cache-Control": "no-store",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }
    )
    return response


def public_url() -> str | None:
    value = os.environ.get("INSIGHT_PUBLIC_URL")
    if value:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise RuntimeError("INSIGHT_PUBLIC_URL harus berupa origin HTTP(S).")
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("Deployment di luar localhost wajib HTTPS.")
        return value.rstrip("/")
    return None


def same_origin(request: Request) -> bool:
    expected = public_url() or str(request.base_url).rstrip("/")
    origin = request.headers.get("origin")
    return (
        origin == expected
        if origin is not None
        else request.headers.get("sec-fetch-site") not in {"cross-site", "none"}
    )


def session_response(data: dict) -> dict:
    user = data.get("user", data)
    profile = store().profile(user["id"])
    avatar = profile["avatar"]
    return {
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": profile["display_name"] or user["username"],
            "avatar_url": "/api/auth/avatar?v=" + hashlib.sha256(avatar).hexdigest()
            if avatar
            else None,
            "role": user["role"],
            "tenant_id": user["workspace_id"],
            "tenant_name": user["tenant_name"],
        },
        "csrf_token": data["csrf"],
    }


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class Password(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class Profile(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def valid_name(cls, value):
        if not value.strip() or any(unicodedata.category(c).startswith("C") for c in value):
            raise ValueError("Nama tampilan tidak boleh kosong atau memuat karakter kontrol.")
        return value.strip()


MAX_AVATAR = 2 * 1024 * 1024


def normalize_avatar(data: bytes) -> bytes:
    if not data or len(data) > MAX_AVATAR:
        raise HTTPException(413, "Foto profil maksimal 2 MiB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("format")
                if source.width * source.height > 4_000_000 or getattr(source, "n_frames", 1) != 1:
                    raise ValueError("dimensions")
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGBA")
                image.info.clear()
                image.thumbnail((512, 512))
                output = io.BytesIO()
                image.save(output, format="PNG")
                return output.getvalue()
    except (
        ValueError,
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise HTTPException(
            422, "Gunakan foto JPEG, PNG, atau WebP statis maksimal 4 megapiksel."
        ) from error


class NewUser(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=12, max_length=256)
    role: str = Field(pattern="^(admin|reviewer|viewer)$")


def install(app, max_upload: int):
    public_url()
    hosts = os.environ.get("INSIGHT_HOSTS", "127.0.0.1,localhost,[::1],testserver").split(",")
    if any(not value or "*" in value for value in hosts):
        raise RuntimeError("INSIGHT_HOSTS wajib host eksplisit tanpa wildcard.")

    @app.middleware("http")
    async def secured(request: Request, call_next):
        path = request.url.path
        unsafe = request.method not in {"GET", "HEAD", "OPTIONS"}
        public = path in {
            "/",
            "/healthz",
            "/api/auth/login",
            "/api/auth/session",
        } or path.startswith("/assets/")
        value = None
        token = request.cookies.get(COOKIE, "")
        if token:
            value = store().session(token)
        try:
            if (
                not (public_url() or "").startswith("https://")
                and request.client
                and request.client.host not in {"127.0.0.1", "::1", "testclient"}
            ):
                raise HTTPException(403, "Akses jaringan memerlukan konfigurasi origin HTTPS.")
            if unsafe and not same_origin(request):
                raise HTTPException(403, "Origin tidak sesuai dengan aplikasi.")
            if path == "/api/auth/login":
                if request.method != "POST":
                    raise HTTPException(405, "Gunakan POST.")
                if request.headers.get("origin") is None:
                    raise HTTPException(403, "Origin login wajib diisi.")
                key = "login:" + (request.client.host if request.client else "unknown")
                if not store().rate_limit(key, 10, 300):
                    raise HTTPException(429, "Terlalu banyak percobaan login; tunggu lima menit.")
            elif not public:
                if value is None:
                    raise HTTPException(401, "Silakan masuk terlebih dahulu.")
                if unsafe:
                    if not hmac.compare_digest(
                        request.headers.get("x-csrf-token", "").encode(), value["csrf"].encode()
                    ):
                        raise HTTPException(403, "Token CSRF tidak valid.")
                    if value["role"] == "viewer" and path not in {
                        "/api/chat",
                        "/api/ngram/explore",
                        "/api/ledger/query",
                        "/api/ledger/report",
                        "/api/auth/logout",
                        "/api/auth/password",
                        "/api/auth/profile",
                        "/api/auth/avatar",
                    }:
                        raise HTTPException(403, "Viewer hanya dapat membaca hasil.")
                # Annotation playback has many small requests; expensive work has its own compute lock.
                if not store().rate_limit("api:" + value["id"], 600, 60):
                    raise HTTPException(429, "Terlalu banyak permintaan; coba lagi sebentar.")
            if unsafe:
                length = request.headers.get("content-length", "")
                limit = max_upload + 1024 * 1024 if path == "/api/jobs" else 1024 * 1024
                if path == "/api/auth/avatar":
                    limit = MAX_AVATAR + 64 * 1024
                if not length.isdigit():
                    raise HTTPException(411, "Ukuran permintaan wajib diketahui.")
                if int(length) > limit:
                    raise HTTPException(413, "Ukuran permintaan melebihi batas.")
            context = principal.set(value)
            try:
                response = await call_next(request)
            finally:
                principal.reset(context)
        except HTTPException as error:
            response = JSONResponse({"detail": error.detail}, status_code=error.status_code)
        if unsafe and path.startswith("/api/"):
            store().audit(
                "http:" + request.method + ":" + path.split("?")[0],
                user_id=value["id"] if value else None,
                workspace_id=value["workspace_id"] if value else None,
                outcome=str(response.status_code),
            )
        if response.status_code == 429:
            response.headers["Retry-After"] = "60"
        if (public_url() or "").startswith("https://"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return headers(response)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.post("/api/auth/login")
    def login(data: Login):
        authenticated = store().authenticate(data.username, data.password)
        if authenticated is None:
            raise HTTPException(401, "Username atau password tidak sesuai.")
        response = JSONResponse(session_response(authenticated))
        response.set_cookie(
            COOKIE,
            authenticated["token"],
            httponly=True,
            samesite="strict",
            secure=(public_url() or "").startswith("https://"),
            max_age=8 * 3600,
            path="/",
        )
        return response

    @app.get("/api/auth/session")
    def current_session(request: Request):
        data = store().session(request.cookies.get(COOKIE, ""))
        if data is None:
            raise HTTPException(401, "Silakan masuk terlebih dahulu.")
        return session_response(data)

    @app.post("/api/auth/logout")
    def logout(request: Request):
        store().revoke(request.cookies.get(COOKIE, ""))
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE, path="/")
        return response

    @app.post("/api/auth/password")
    def password(data: Password, request: Request):
        user = actor()
        authenticated = store().change_password(
            user["id"],
            data.new_password,
            current_password=data.current_password,
            token=request.cookies.get(COOKIE, ""),
        )
        if authenticated is None:
            raise HTTPException(403, "Password atau sesi berubah. Masuk kembali dan coba lagi.")
        response = JSONResponse(session_response(authenticated))
        response.set_cookie(
            COOKIE,
            authenticated["token"],
            httponly=True,
            samesite="strict",
            secure=(public_url() or "").startswith("https://"),
            max_age=8 * 3600,
            path="/",
        )
        return response

    @app.patch("/api/auth/profile")
    def update_profile(data: Profile):
        store().update_profile(actor()["id"], display_name=data.display_name)
        return session_response(actor())

    @app.put("/api/auth/avatar")
    async def update_avatar(file: Annotated[UploadFile, File()]):
        try:
            avatar = normalize_avatar(await file.read(MAX_AVATAR + 1))
        finally:
            await file.close()
        store().update_profile(actor()["id"], avatar=avatar, change_avatar=True)
        return session_response(actor())

    @app.delete("/api/auth/avatar")
    def remove_avatar():
        store().update_profile(actor()["id"], change_avatar=True)
        return session_response(actor())

    @app.get("/api/auth/avatar")
    def avatar():
        data = store().profile(actor()["id"])["avatar"]
        if data is None:
            raise HTTPException(404, "Foto profil belum tersedia.")
        return Response(data, media_type="image/png")

    @app.get("/api/admin/users")
    def users():
        if actor()["role"] != "admin":
            raise HTTPException(403, "Akses administrator diperlukan.")
        return store().list_users(workspace_id())

    @app.post("/api/admin/users", status_code=201)
    def new_user(data: NewUser):
        if actor()["role"] != "admin":
            raise HTTPException(403, "Akses administrator diperlukan.")
        try:
            return store().create_user(data.username, data.password, data.role, workspace_id())
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.post("/api/admin/users/{user_id}/revoke")
    def revoke_user(user_id: str):
        if actor()["role"] != "admin":
            raise HTTPException(403, "Akses administrator diperlukan.")
        user = store().get_user(user_id)
        if user is None or user["workspace_id"] != workspace_id():
            raise HTTPException(404, "Akun tidak ditemukan.")
        store().revoke_user(user_id)
        return {"ok": True}


def main():
    parser = argparse.ArgumentParser(description="Administrasi lokal Video Insight")
    sub = parser.add_subparsers(dest="command", required=True)
    owner = sub.add_parser("init", help="Buat owner pertama dan migrasi metadata lama")
    owner.add_argument("--username", required=True)
    owner.add_argument(
        "--generate",
        action="store_true",
        help="Buat password acak ke data/security/first-access.txt",
    )
    user = sub.add_parser("user", help="Tambahkan akun lokal")
    user.add_argument("--username", required=True)
    user.add_argument("--role", choices=["admin", "reviewer", "viewer"], default="reviewer")
    user.add_argument("--workspace", default="Local")
    backup = sub.add_parser(
        "backup", help="Backup SQLite dan manifest artefak, tanpa menghapus sumber"
    )
    backup.add_argument("target", type=Path)
    sub.add_parser("verify", help="Verifikasi integritas rantai audit")
    sub.add_parser("users", help="Daftar akun dan workspace lokal")
    args = parser.parse_args()
    database = store()
    if args.command in {"init", "user"}:
        generated = args.command == "init" and args.generate
        if generated:
            with database.connection() as connection:
                if connection.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                    print("Owner sudah tersedia; gunakan akun yang ada.")
                    return
            import secrets

            password = secrets.token_urlsafe(24)
        else:
            password = getpass.getpass("Password (minimal 12 karakter): ")
            if password != getpass.getpass("Ulangi password: "):
                parser.error("Password tidak sama.")
        if args.command == "init":
            database.bootstrap(args.username, password)
        else:
            database.create_user(
                args.username, password, args.role, database.workspace(args.workspace)
            )
        if generated:
            credential = database.path.parent / "first-access.txt"
            with credential.open("x", encoding="utf-8") as stream:
                stream.write(
                    f"Username: {args.username}\nPassword: {password}\n\nUbah password setelah masuk, lalu hapus file ini. Jangan dibagikan/diunggah.\n"
                )
            print(f"Akses awal tersimpan lokal di {credential}")
        migrate_existing(runtime.JOBS.parent / "trainings")
        print("Akun tersimpan. Masuk melalui dashboard.")
    elif args.command == "users":
        with database.connection() as connection:
            rows = connection.execute(
                "SELECT username,role,workspace_id,id FROM users ORDER BY username"
            ).fetchall()
        for row in rows:
            print(dict(row))
    elif args.command == "verify":
        if not database.verify_audit():
            raise SystemExit("Audit tidak sesuai; periksa database dan checkpoint.")
        print("Audit terverifikasi.")
    elif args.command == "backup":
        target = args.target.resolve()
        if not target.is_relative_to(runtime.ROOT.resolve()) or target.exists():
            parser.error("Target harus direktori baru dalam industrial_ai.")
        target.mkdir(parents=True)
        database.backup(target / "studio.sqlite3")
        import hashlib

        rows = []
        for root in (runtime.JOBS, runtime.JOBS.parent / "trainings"):
            for path in root.rglob("*"):
                if path.is_file():
                    with path.open("rb") as stream:
                        digest = hashlib.file_digest(stream, "sha256").hexdigest()
                    rows.append(
                        {
                            "path": str(path.relative_to(runtime.ROOT)),
                            "size": path.stat().st_size,
                            "sha256": digest,
                        }
                    )
        (target / "artifacts.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(
            "Database dibackup; manifest artefak dibuat. Salin video/model terpisah sebelum memulihkan."
        )


if __name__ == "__main__":
    main()
