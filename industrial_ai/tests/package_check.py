"""Check built package content against source; never include local runtime artifacts."""

import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
output = Path(sys.argv[1]) if len(sys.argv) > 1 else root / ".tmp/packages"
modules = tomllib.loads((root / "pyproject.toml").read_text())["tool"]["setuptools"]["py-modules"]
wheel = next(output.glob("industrial_video_workspace*.whl"))
with zipfile.ZipFile(wheel) as archive:
    metadata = archive.read(
        next(p for p in archive.namelist() if p.endswith(".dist-info/METADATA"))
    ).decode()
    assert "Requires-Dist: ngram-assignment==0.1.0" in metadata
    for name in modules:
        assert archive.read(name + ".py") == (root / (name + ".py")).read_bytes(), name
    for name in [
        "index.html",
        "dashboard.js",
        "auth.js",
        "theme.js",
        "app.js",
        "frontend/auth.ts",
        "frontend/tsconfig.auth.json",
        "frontend/tsconfig.json",
        "frontend/tsconfig.studio.json",
        "frontend/App.tsx",
        "frontend/main.tsx",
        "frontend/studio.ts",
        "frontend/Account.tsx",
        "frontend/Annotation.tsx",
        "frontend/ChatPanel.tsx",
        "frontend/VideoPanel.tsx",
        "frontend/Workspace.tsx",
        "frontend/LiveViews.tsx",
        "frontend/NgramLab.tsx",
        "frontend/EventLedger.tsx",
        "motion.js",
        "frontend/motion.ts",
        "frontend/tsconfig.motion.json",
        "assets/dashboard.css",
        "assets/THIRD_PARTY_LICENSES.txt",
        "docs/README.md",
        "docs/EVENT_CONTRACT.md",
        "docs/DATA_POLICY.md",
        "assets/brand.svg",
        "assets/crowd.png",
    ]:
        entry = next(
            p for p in archive.namelist() if p.endswith("/share/industrial-video-workspace/" + name)
        )
        assert archive.read(entry) == (root / name).read_bytes(), name
    assert not any(
        "/models/" in p or p.startswith("data/") or "/.tmp/" in p or "/.cache/" in p
        for p in archive.namelist()
    )
with tarfile.open(next(output.glob("industrial_video_workspace*.tar.gz"))) as archive:
    for name in (
        "docs/README.md",
        "docs/EVENT_CONTRACT.md",
        "docs/DATA_POLICY.md",
        "assets/brand.svg",
        "assets/crowd.png",
        "app.js",
        "motion.js",
        "frontend/motion.ts",
        "frontend/tsconfig.motion.json",
        "frontend/auth.ts",
        "frontend/tsconfig.auth.json",
        "frontend/tsconfig.json",
        "frontend/tsconfig.studio.json",
        "frontend/App.tsx",
        "frontend/main.tsx",
        "frontend/studio.ts",
        "frontend/Account.tsx",
        "frontend/Annotation.tsx",
        "frontend/ChatPanel.tsx",
        "frontend/VideoPanel.tsx",
        "frontend/Workspace.tsx",
        "frontend/LiveViews.tsx",
        "frontend/NgramLab.tsx",
        "frontend/EventLedger.tsx",
    ):
        member = next(p for p in archive.getmembers() if p.name.endswith("/" + name))
        extracted = archive.extractfile(member)
        assert extracted is not None and extracted.read() == (root / name).read_bytes(), name
    assert not any(
        any(
            part in {"models", "data", ".tmp", ".cache", ".venv", "node_modules"}
            for part in Path(p.name).parts
        )
        for p in archive.getmembers()
    )
print("PASS: package source equality and runtime-data exclusion.")
