"""Check a live temporary HTTPS origin without reading workspace data."""

import json
import re
import sys
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

url = sys.argv[1].rstrip("/")
parsed = urlsplit(url)
assert parsed.scheme == "https" and re.fullmatch(r"[a-z0-9-]+\.trycloudflare\.com", parsed.netloc)
assert not parsed.path and not parsed.query and not parsed.fragment


def request(path, *, origin=None):
    body = None
    headers = {}
    if origin:
        body = json.dumps(
            {"username": "cf-probe-" + uuid4().hex[:12], "password": uuid4().hex}
        ).encode()
        headers = {"Origin": origin, "Content-Type": "application/json"}
    try:
        with urlopen(Request(url + path, data=body, headers=headers), timeout=30) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


checks = {}
for path in ("/", "/healthz", "/assets/app.js", "/assets/dashboard.css"):
    status, content = request(path)
    assert status == 200 and content, (path, status)
    checks[path] = status
for path in ("/api/jobs", "/api/ngram/chat/data", "/api/auth/session"):
    status, _ = request(path)
    assert status == 401, (path, status)
    checks[path] = status
assert request("/api/auth/login", origin=url)[0] == 401, (
    "Correct public origin must reach credential validation"
)
assert request("/api/auth/login", origin="https://invalid.example")[0] == 403, (
    "Cross-site login must be rejected"
)
checks["same_origin_login"] = 401
checks["cross_origin_login"] = 403
print(json.dumps({"url": url, "checks": checks, "result": "PASS"}, indent=2))
