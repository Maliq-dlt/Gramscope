"""Validate merged deployment with Compose, without publishing or starting services."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
base = root / ".tmp" / ("cloudflare_" + uuid4().hex)
base.mkdir(parents=True)
secret = base / "token.txt"
secret.touch()  # Only the mount path is checked; no real token is required.
env = dict(
    os.environ, CF_HOSTNAME="video.example.invalid", CLOUDFLARE_TUNNEL_TOKEN_FILE=str(secret)
)
command = [
    "docker",
    "compose",
    "-f",
    "compose.yaml",
    "-f",
    "compose.cloudflare.yaml",
    "config",
    "--format",
    "json",
]
result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, check=True)
config = json.loads(result.stdout)
services = config["services"]
assert "proxy" not in services, "Caddy must require the direct-https profile"
assert set(services) == {"app", "cloudflared"}
assert not services["app"].get("ports") and not services["cloudflared"].get("ports")
assert services["app"]["environment"]["INSIGHT_PUBLIC_URL"] == "https://video.example.invalid"
assert services["app"]["environment"]["INSIGHT_HOSTS"] == "video.example.invalid"
assert services["app"]["environment"]["INSIGHT_MAX_UPLOAD_MIB"] == "95"
assert services["app"]["read_only"] and services["cloudflared"]["read_only"]
assert services["cloudflared"]["command"][-2:] == ["--token-file", "/run/secrets/tunnel_token"]
assert "**/.secrets" in (root.parent / ".dockerignore").read_text()
assert ".secrets/" in (root / ".gitignore").read_text()
for key in ("CF_HOSTNAME", "CLOUDFLARE_TUNNEL_TOKEN_FILE"):
    incomplete = env.copy()
    incomplete.pop(key)
    assert (
        subprocess.run(
            command, cwd=root, env=incomplete, capture_output=True, check=False
        ).returncode
        != 0
    )
print(
    "PASS: merged app/Tunnel config, no published ports, TLS origin/Host, 95 MiB cap, secret file, required fields."
)
