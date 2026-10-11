"""Offline checks for source boundaries and deterministic article conversion."""

import hashlib
import json

import pytest

from extensions.experiments import prepare_academic_corpora as corpus


def article(text=None):
    return {
        "row_idx": 17,
        "row": {
            "id": "123",
            "url": "https://id.wikipedia.org/wiki/Artikel",
            "title": "Artikel",
            "text": text
            or (
                "Judul\n"
                + "Kalimat berbahasa Indonesia berisi banyak kata yang dapat diproses. " * 12
            ),
        },
    }


def test_full_article_conversion_retains_provenance_and_core_tokens():
    parsed, reason = corpus.parse_row(article())
    assert reason is None
    document, evidence = parsed
    assert document["id"] == document["group"] == "idwiki/123"
    assert document["license"] == "CC-BY-SA-3.0"
    assert evidence["row_index"] == 17
    assert evidence["text_sha256"] == hashlib.sha256(article()["row"]["text"].encode()).hexdigest()
    assert evidence["tokens"] >= 100
    assert all(len(sentence) >= 5 for sentence in document["sentences"])
    assert all(
        word.isalpha() and word == word.lower()
        for sentence in document["sentences"]
        for word in sentence
    )


def test_short_oversize_and_invalid_source_rejected():
    assert corpus.parse_row(article("Kalimat singkat."))[1] == "under-100-tokens"
    assert corpus.parse_row(article("kata " * 120_000))[1] == "oversize-article"
    with pytest.raises(ValueError, match="Wikipedia page ID"):
        corpus.parse_row({**article(), "row": {**article()["row"], "id": "../../../1"}})


def test_window_sampling_and_receipt_integrity(tmp_path):
    assert corpus.windows(1_001, 5, 7) == corpus.windows(1_001, 5, 7)
    assert len(set(corpus.windows(1_001, 5, 7))) == 5
    assert all(offset % 100 == 0 for offset in corpus.windows(1_001, 5, 7))
    url = "https://example.invalid/rows"
    path = tmp_path / "row.json"
    raw = json.dumps({"rows": []})
    receipt = {
        "url": url,
        "retrieved_at": "2026-10-11T00:00:00Z",
        "response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "raw_json": raw,
    }
    path.write_text(json.dumps(receipt), encoding="utf-8")
    assert corpus.fetch(path, url, False)[0] == {"rows": []}
    receipt["raw_json"] += " "
    path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        corpus.fetch(path, url, False)


def test_metadata_revision_and_license_must_match():
    data = {
        "id": corpus.DATASET,
        "sha": corpus.REVISION,
        "cardData": {
            "license": ["cc-by-sa-3.0", "gfdl"],
            "dataset_info": [
                {
                    "config_name": corpus.CONFIG,
                    "splits": [{"name": "train", "num_examples": 665622}],
                }
            ],
        },
    }
    assert corpus.source_info(data)[0] == 665622
    with pytest.raises(ValueError, match="revision changed"):
        corpus.source_info({**data, "sha": "different"})
