"""Fresh holdout selection excludes primary test from development robustness."""

import hashlib
import json

import pytest

from extensions.experiments import fresh_holdout, registry
from extensions.src.datasets import digest


def test_holdout_frozen_once(tmp_path, monkeypatch):
    docs = [
        {
            "id": f"idwiki/{i + 1}",
            "group": f"idwiki/{i + 1}",
            "source": f"https://id.wikipedia.org/?curid={i + 1}",
            "license": fresh_holdout.LICENSE,
            "sentences": [[f"unique{chr(97 + i)}", "worker", "wears", "helmet"]],
        }
        for i in range(20)
    ]
    # Trust-boundary input uses lowercase alphabetic tokens; IDs are independent.
    source = tmp_path / "docs.jsonl"
    source.write_text("\n".join(json.dumps(d) for d in docs), encoding="utf-8")
    monkeypatch.setattr(fresh_holdout, "ROOT", tmp_path)
    for name in (
        "extensions/experiments/fresh_holdout.py",
        "extensions/src/models.py",
        "extensions/src/pipeline.py",
        "extensions/src/datasets.py",
        "extensions/src/analytics.py",
        "extensions/src/cli.py",
        "extensions/experiments/registry.py",
        "extensions/experiments/wiki_expansion.py",
        "extensions/experiments/prepare_indonesian.py",
        "core/src/ngram.py",
        "core/src/preprocess.py",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    monkeypatch.setattr(registry, "RUNS", tmp_path / "runs")
    pilot_path = tmp_path / "pilot.jsonl"
    pilot = [
        dict(
            d,
            id=f"pilot/{i}",
            group=f"pilot/{i}",
            sentences=[[f"old{chr(97 + i)}", "historical", "text"]],
        )
        for i, d in enumerate(docs[:3])
    ]
    pilot_path.write_text("\n".join(json.dumps(d) for d in pilot), encoding="utf-8")
    monkeypatch.setattr(fresh_holdout, "PILOT", pilot_path)
    manifest = {
        "format": "indonesian-wikipedia-expansion-v1",
        "policy": fresh_holdout.POLICY,
        "language": "id",
        "license": fresh_holdout.LICENSE,
        "jsonl_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "documents_sha256": digest(docs),
        "documents": len(docs),
        "independent_groups": 20,
        "pilot_exclusion": {
            "path": "pilot.jsonl",
            "duplicate_policy": fresh_holdout.DUPLICATE_POLICY,
            "jsonl_sha256": hashlib.sha256(pilot_path.read_bytes()).hexdigest(),
            "documents_sha256": digest(pilot),
            "ids": sorted(d["id"] for d in pilot),
        },
        "articles": [
            {
                "id": d["id"],
                "source_url": d["source"],
                "license": d["license"],
                "tokens_sha256": digest(d["sentences"]),
            }
            for d in docs
        ],
        "importer_sha256": hashlib.sha256(
            (tmp_path / "extensions/experiments/wiki_expansion.py").read_bytes()
        ).hexdigest(),
        "pilot_importer_sha256": hashlib.sha256(
            (tmp_path / "extensions/experiments/prepare_indonesian.py").read_bytes()
        ).hexdigest(),
    }
    manifest_path = source.with_name("manifest.json")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="outside immutable"):
        fresh_holdout.run("invalid", source, tmp_path / "runs/invalid/public", minimum_groups=10)
    assert not (tmp_path / "runs/invalid").exists()
    original_manifest = manifest_path.read_bytes()
    manifest["documents_sha256"] = "tampered"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint"):
        fresh_holdout.run("tampered", source, tmp_path / "bad", minimum_groups=10)
    assert not (tmp_path / "runs/tampered").exists()
    manifest_path.write_bytes(original_manifest)
    score = fresh_holdout.document_losses
    scored = []

    def score_once(model, documents):
        directory = tmp_path / "runs/holdout"
        selection = json.loads((directory / "selection.json").read_text())
        assert (directory / "test.claim").read_text() == digest(documents)
        assert {d["id"] for d in documents} == set(selection["selections"][0]["partitions"]["test"])
        assert model not in scored
        scored.append(model)
        return score(model, documents)

    monkeypatch.setattr(fresh_holdout, "document_losses", score_once)
    # Exact shared sentences would merge documents; each sentence includes its unique word.
    result = fresh_holdout.run("holdout", source, tmp_path / "public", minimum_groups=10)
    registry.read_run("holdout")
    assert 1 <= len(scored) <= 2
    selection = json.loads((tmp_path / "public/selection.json").read_text())
    primary = selection["selections"][0]
    test_ids = set(primary["partitions"]["test"])
    assert test_ids and len(primary["partitions"]["train"]) == 16
    for row in selection["selections"][1:]:
        assert not test_ids.intersection(row["partitions"]["train"] + row["partitions"]["dev"])
        assert "test" not in row["partitions"]
        assert len(row["partitions"]["train"]) == 16
        assert len(row["partitions"]["dev"]) == 2
    assert (
        result["selected"]
        == min(primary["models"], key=lambda r: (r["dev_ce_nats"], r["model"]))["model"]
    )
    assert result["paired_bootstrap"]["independent_groups"] == 2
    with pytest.raises(FileExistsError):
        fresh_holdout.run("holdout", source, tmp_path / "new", minimum_groups=10)
    with pytest.raises(FileExistsError):
        fresh_holdout.run("new", source, tmp_path / "public", minimum_groups=10)
