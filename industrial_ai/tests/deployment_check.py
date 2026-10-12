"""Real HTTP deployment smoke; run with the application's installed Python."""

from __future__ import annotations

import http.cookiejar
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from storage import Store


def main():
    base = ROOT / ".tmp" / ("deployment-" + uuid4().hex)
    base.mkdir(parents=True)
    data = base / "data"
    data.mkdir()
    env = dict(os.environ, INSIGHT_DATA_ROOT=str(data), PYTHONDONTWRITEBYTECODE="1")
    for name in ("TEMP", "TMP", "TMPDIR"):
        env[name] = str(base)
    # Native ephemeral port keeps concurrent local/browser checks independent.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    env.pop("INSIGHT_PUBLIC_URL", None)
    env["INSIGHT_HOSTS"] = "127.0.0.1,localhost"
    resolved = subprocess.run(
        [sys.executable, "-c", "import runtime; print(runtime.JOBS.parent)"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if Path(resolved).resolve() != data.resolve():
        raise RuntimeError("Runtime must honor INSIGHT_DATA_ROOT before deployment checks can run.")
    subprocess.run(
        [sys.executable, "access.py", "init", "--username", "deployment-owner", "--generate"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    credentials = (data / "security" / "first-access.txt").read_text(encoding="utf-8")
    password = next(
        line.removeprefix("Password: ")
        for line in credentials.splitlines()
        if line.startswith("Password: ")
    )
    database = Store(data / "security" / "studio.sqlite3")
    database.create_user(
        "deployment-viewer", "viewer-long-password", "viewer", database.workspace()
    )
    jar = http.cookiejar.CookieJar()
    client = build_opener(HTTPCookieProcessor(jar))
    checks = []

    def request(path, payload=None, csrf=None, origin_header=origin):
        headers = {}
        if payload is not None:
            headers.update({"Content-Type": "application/json", "Origin": origin_header})
        if csrf is not None:
            headers["X-CSRF-Token"] = csrf
        query = Request(
            origin + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers,
        )
        try:
            # Password rotation verifies and hashes scrypt; allow two expensive operations.
            response = client.open(query, timeout=15 if path == "/api/auth/password" else 5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read()), response.headers

    def check(condition, name):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    with (base / "server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                if server.poll() is not None:
                    raise RuntimeError("Server exited; inspect " + str(base / "server.log"))
                try:
                    if request("/healthz")[0] == 200:
                        break
                except (URLError, TimeoutError, ConnectionError):
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "Server failed to start; inspect " + str(base / "server.log")
                    )
                time.sleep(0.2)
            for asset, mime in (("brand.svg", "image/svg+xml"), ("crowd.png", "image/png")):
                with client.open(origin + "/assets/" + asset, timeout=5) as response:
                    check(response.status == 200, "anonymous asset " + asset)
                    check(response.headers.get_content_type() == mime, "asset MIME " + asset)
                    check(
                        response.read() == (ROOT / "assets" / asset).read_bytes(),
                        "asset bytes " + asset,
                    )
                    check(
                        response.headers.get("X-Content-Type-Options") == "nosniff",
                        "asset headers " + asset,
                    )
            for bundle in ("motion.js", "app.js"):
                with client.open(origin + "/assets/" + bundle, timeout=5) as response:
                    check(response.status == 200, "anonymous bundle " + bundle)
                    check(
                        response.headers.get_content_type()
                        in {"text/javascript", "application/javascript"},
                        "bundle MIME " + bundle,
                    )
                    check(response.read() == (ROOT / bundle).read_bytes(), "bundle bytes " + bundle)
                    check(
                        response.headers.get("X-Content-Type-Options") == "nosniff",
                        "bundle headers " + bundle,
                    )
            try:
                client.open(origin + "/assets/studio.sqlite3", timeout=5)
                raise AssertionError("unknown asset must be denied")
            except HTTPError as error:
                check(error.code == 404, "asset allowlist denies unknown file")
            check(request("/api/jobs")[0] == 401, "anonymous jobs denied")
            status, owner, headers = request(
                "/api/auth/login", {"username": "deployment-owner", "password": password}
            )
            check(status == 200 and bool(owner["csrf_token"]), "owner login")
            check(
                "HttpOnly" in headers.get("Set-Cookie", "")
                and "SameSite=strict" in headers.get("Set-Cookie", ""),
                "cookie protection",
            )
            check(request("/api/admin/users")[0] == 200, "owner administration")
            old_cookie = next(cookie.value for cookie in jar if cookie.name == "insight_session")
            assert isinstance(old_cookie, str)
            old_csrf = owner["csrf_token"]
            other_session = database.authenticate("deployment-owner", password)
            status, rotated, cookie_headers = request(
                "/api/auth/password",
                {"current_password": password, "new_password": "new-deployment-password-long"},
                old_csrf,
            )
            check(
                status == 200 and rotated["csrf_token"] != old_csrf,
                "password rotates csrf over HTTP",
            )
            check(
                "HttpOnly" in cookie_headers.get("Set-Cookie", ""), "rotated HTTP cookie protection"
            )
            check(
                database.session(old_cookie) is None
                and database.session(other_session["token"]) is None,
                "password revokes every previous session",
            )
            stale = Request(
                origin + "/api/jobs", headers={"Cookie": "insight_session=" + old_cookie}
            )
            try:
                with build_opener().open(stale, timeout=5) as old_response:
                    check(old_response.status == 401, "old cookie denied over HTTP")
            except HTTPError as error:
                check(error.code == 401, "old cookie denied over HTTP")
            check(request("/api/auth/logout", {}, old_csrf)[0] == 403, "old csrf denied over HTTP")
            owner = rotated
            check(request("/api/jobs")[0] == 200, "rotated HTTP session works")

            check(request("/api/auth/logout", {})[0] == 403, "missing csrf denied")
            check(
                request("/api/auth/logout", {}, owner["csrf_token"], "http://foreign.example")[0]
                == 403,
                "foreign origin denied",
            )
            check(request("/api/auth/logout", {}, owner["csrf_token"])[0] == 200, "owner logout")
            check(request("/api/jobs")[0] == 401, "revoked session denied")
            status, viewer, _ = request(
                "/api/auth/login",
                {"username": "deployment-viewer", "password": "viewer-long-password"},
            )
            check(status == 200, "viewer login")
            check(request("/api/admin/users")[0] == 403, "viewer administration denied")
            check(
                request("/api/jobs", {}, viewer["csrf_token"])[0] == 403,
                "viewer upload denied before model work",
            )
            check(request("/api/auth/session")[1]["user"]["role"] == "viewer", "viewer session")
            check(database.verify_audit(), "HTTP audit verified")
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
    (base / "verification.json").write_text(
        json.dumps({"checks": checks, "count": len(checks)}, indent=2), encoding="utf-8"
    )
    print(f"Deployment HTTP checks passed: {len(checks)}; report {base / 'verification.json'}")


if __name__ == "__main__":
    main()
