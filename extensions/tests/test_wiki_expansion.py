"""Offline acquisition verifies pilot exclusion, transitive groups and hard request budgets."""

import hashlib
import json
from email.message import Message
from urllib.error import HTTPError

import pytest

from extensions.experiments import wiki_expansion as importer


def article(pageid, text=None):
    return {
        "ns": 0,
        "pageid": pageid,
        "title": f"Artikel {pageid}",
        "pagelanguage": "id",
        "extract": text or " ".join(["kata" + chr(97 + pageid)] * 25) + ".",
        "revisions": [{"revid": 100 + pageid, "timestamp": "2026-10-11T00:00:00Z"}],
    }


def setup_pilot(tmp_path, monkeypatch):
    monkeypatch.setattr(importer, "ROOT", tmp_path)
    path = tmp_path / "data/pilot/documents.jsonl"
    path.parent.mkdir(parents=True)
    pilot = [importer.parse_page(article(pageid))[0] for pageid in (1, 2, 3)]
    path.write_text("".join(json.dumps(doc) + "\n" for doc in pilot), encoding="utf-8")
    monkeypatch.setattr(importer, "PILOT", path)
    monkeypatch.setattr(importer, "LIST_BATCH", 2)
    return path


def offline_api(monkeypatch, listing_batches, articles, *, continuation=True):
    calls = []
    listing_index = 0

    def request(parameters, download=False):
        nonlocal listing_index
        calls.append(parameters)
        assert not download
        if parameters.get("meta") == "siteinfo":
            data = {"query": {"rightsinfo": {"url": importer.LICENSE_URL}}}
        elif parameters.get("list") == "allpages":
            assert parameters["apnamespace"] == 0
            assert parameters["apfilterredir"] == "nonredirects"
            assert parameters["apdir"] == "ascending"
            assert parameters["aplimit"] == 2
            if listing_index == 0:
                assert parameters["apfrom"] == "A"
            else:
                assert parameters["apcontinue"] == f"A{listing_index}"
            batch = listing_batches[listing_index]
            listing_index += 1
            data = {
                "query": {
                    "allpages": [
                        {"ns": 0, "pageid": pageid, "title": f"Artikel {pageid}"}
                        for pageid in batch
                    ]
                }
            }
            if continuation:
                data["continue"] = {"apcontinue": f"A{listing_index}", "continue": "-||"}
        else:
            assert parameters["explaintext"] == parameters["exintro"] == 1
            assert parameters["exlimit"] == 10
            pageids = [int(value) for value in parameters["pageids"].split("|")]
            # Property query order differs; collector must restore allpages selection order.
            data = {"query": {"pages": [articles[pageid] for pageid in reversed(pageids)]}}
        return data, {
            "url": "https://id.wikipedia.org/w/api.php?" + str(len(calls)),
            "retrieved_at": "2026-10-11T00:00:00Z",
            "response_sha256": importer.digest(data),
        }

    monkeypatch.setattr(importer, "api_request", request)
    return calls


def test_snapshot_excludes_pilot_ids_and_transitive_duplicate_groups(tmp_path, monkeypatch):
    pilot = setup_pilot(tmp_path, monkeypatch)
    before = pilot.read_bytes()
    bridge = " ".join(["penghubung"] * 25) + "."
    pages = {pageid: article(pageid) for pageid in range(4, 10)}
    pages[4] = article(4, article(1)["extract"] + " " + bridge)
    pages[5] = article(5, bridge + " " + article(5)["extract"])
    pages[6] = article(6, "Terlalu singkat.")
    calls = offline_api(monkeypatch, [[1, 4], [5, 6], [7, 8], [9]], pages)
    output = tmp_path / "data/expansion"
    corpus, manifest = importer.prepare(output, limit=3, max_candidates=20, minimum_groups=3)
    documents = importer.read_documents(corpus)
    assert [doc["id"] for doc in documents] == ["idwiki/7", "idwiki/8", "idwiki/9"]
    assert all("split_group" not in doc for doc in documents)
    assert manifest["independent_groups"] == 3
    assert manifest["model_split"].startswith("not performed")
    assert not {"ids", "split", "split_sizes", "scores"}.intersection(manifest)
    assert manifest["pilot_exclusion"]["blocked_groups"] == [
        ["idwiki/1", "idwiki/4", "idwiki/5"],
        ["idwiki/2"],
        ["idwiki/3"],
    ]
    assert manifest["selection"]["candidates"][0]["status"] == "pilot-id"
    assert manifest["selection"]["candidates"][1]["status"] == "pilot-duplicate-group"
    assert all("1" not in call["pageids"].split("|") for call in calls if "pageids" in call)
    assert manifest["jsonl_sha256"] == hashlib.sha256(corpus.read_bytes()).hexdigest()
    assert manifest["documents_sha256"] == importer.digest(documents)
    assert len(manifest["articles"]) == 3
    assert all(article["license"] == "CC-BY-SA-4.0" for article in manifest["articles"])
    assert pilot.read_bytes() == before
    with pytest.raises(FileExistsError):
        importer.prepare(output, limit=3, minimum_groups=3)


def test_empty_allpages_batches_cannot_escape_request_budget(tmp_path, monkeypatch):
    setup_pilot(tmp_path, monkeypatch)
    calls = offline_api(monkeypatch, [[], []], {})
    output = tmp_path / "data/empty"
    with pytest.raises(ValueError, match="Only 0 eligible"):
        importer.prepare(output, limit=3, max_candidates=4, minimum_groups=3)
    assert len(calls) == 3  # License request plus exactly ceil(4/2) listing requests.
    assert not output.exists()


def test_insufficient_independent_groups_do_not_write_snapshot(tmp_path, monkeypatch):
    setup_pilot(tmp_path, monkeypatch)
    pages = {pageid: article(pageid) for pageid in (4, 5, 6, 7)}
    pages[5] = article(5, pages[4]["extract"])
    pages[6] = article(6, pages[4]["extract"])
    offline_api(monkeypatch, [[4, 5], [6, 7]], pages)
    output = tmp_path / "data/collapsed"
    with pytest.raises(ValueError, match="Only 2 independent groups"):
        importer.prepare(output, limit=4, max_candidates=4, minimum_groups=3)
    assert not output.exists()


def test_output_and_budget_validation_precedes_api_calls(tmp_path, monkeypatch):
    setup_pilot(tmp_path, monkeypatch)

    def unexpected(*args, **kwargs):
        pytest.fail("Invalid parameters must not reach the network")

    monkeypatch.setattr(importer, "api_request", unexpected)
    with pytest.raises(ValueError, match="inside"):
        importer.prepare(tmp_path / "outside")
    with pytest.raises(ValueError, match="new directory"):
        importer.prepare(tmp_path / "data")
    with pytest.raises(ValueError, match="3..300"):
        importer.prepare(tmp_path / "data/new", limit=301)
    with pytest.raises(ValueError, match="5000"):
        importer.prepare(tmp_path / "data/new", max_candidates=5001)
    with pytest.raises(ValueError, match="Minimum"):
        importer.prepare(tmp_path / "data/new", minimum_groups=301)


def test_rate_limit_retries_are_bounded_and_preserve_failure_evidence(tmp_path, monkeypatch):
    setup_pilot(tmp_path, monkeypatch)
    calls, waits = [], []

    def unavailable(parameters, download=False):
        assert download
        calls.append(parameters)
        raise HTTPError(importer.API, 429, "Too Many Requests", Message(), None)

    monkeypatch.setattr(importer, "api_request", unavailable)
    monkeypatch.setattr(importer.time, "sleep", waits.append)
    output = tmp_path / "data/throttled"
    with pytest.raises(HTTPError):
        importer.prepare(output, limit=3, max_candidates=3, minimum_groups=3, download=True)
    assert len(calls) == 3
    assert waits == [3, 30, 3, 30, 30, 3]
    failures = [
        json.loads(line)
        for line in (tmp_path / ".cache/idwiki/wiki-expansion-failures.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [failure["attempt"] for failure in failures] == [1, 2, 3]
    assert all(failure["http_status"] == 429 for failure in failures)
    assert not output.exists()
