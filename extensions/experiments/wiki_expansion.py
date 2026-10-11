"""Bounded Wikipedia Indonesia expansion, excluding the historical pilot before scoring."""

import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.error import HTTPError

from core.src.data import ROOT
from extensions.experiments.prepare_indonesian import (
    API,
    LICENSE,
    LICENSE_URL,
    POLICY,
    TERMS,
    api_request,
    parse_page,
    timestamp,
)
from extensions.src.datasets import POLICY as DUPLICATE_POLICY
from extensions.src.datasets import digest, read_documents, split_documents, validate_documents

PILOT = ROOT / "data/indonesian/wiki-pilot-20261010-final/documents.jsonl"
START_TITLE = "A"
LIST_BATCH = 50
EXTRACT_BATCH = 10


def eligible_documents(pilot, candidates):
    """Reuse duplicate groups only; discard the grouping API's unused split assignments."""
    if not candidates:
        return [], [], []
    _, grouping = split_documents(pilot + candidates, seed=42)
    pilot_ids = {doc["id"] for doc in pilot}
    blocked_groups = [group for group in grouping["groups"] if pilot_ids.intersection(group)]
    blocked = {docid for group in blocked_groups for docid in group}
    eligible = [doc for doc in candidates if doc["id"] not in blocked]
    groups = [group for group in grouping["groups"] if not pilot_ids.intersection(group)]
    return eligible, groups, blocked_groups


def prepare(output, limit=300, max_candidates=5000, minimum_groups=200, download=False):
    output = Path(output).resolve()
    data_root = (ROOT / "data").resolve()
    if output == data_root or not output.is_relative_to(data_root):
        raise ValueError("Corpus output must be a new directory inside repository data/")
    if type(limit) is not int or not 3 <= limit <= 300:
        raise ValueError("Document limit must be 3..300")
    if type(max_candidates) is not int or not limit <= max_candidates <= 5000:
        raise ValueError("Candidate budget must be document limit..5000")
    if type(minimum_groups) is not int or not 3 <= minimum_groups <= limit:
        raise ValueError("Minimum independent groups must be 3..document limit")
    if output.exists():
        raise FileExistsError(output)
    pilot = read_documents(PILOT)
    pilot_ids = {doc["id"] for doc in pilot}
    requests, failed_attempts = [], []

    def request(parameters, kind):
        for attempt in range(3):
            if download:
                time.sleep(3)
            try:
                data, evidence = api_request(parameters, download)
                requests.append({"kind": kind, "parameters": parameters, **evidence})
                return data
            except HTTPError as error:
                failure = {
                    "kind": kind,
                    "parameters": parameters,
                    "url": error.url,
                    "observed_at": timestamp(),
                    "http_status": error.code,
                    "attempt": attempt + 1,
                    "retry_after": error.headers.get("Retry-After") if error.headers else None,
                }
                failed_attempts.append(failure)
                cache = ROOT / ".cache/idwiki"
                cache.mkdir(parents=True, exist_ok=True)
                with (cache / "wiki-expansion-failures.jsonl").open(
                    "a", encoding="utf-8"
                ) as stream:
                    stream.write(json.dumps(failure, ensure_ascii=False) + "\n")
                if not download or error.code not in (429, 503) or attempt == 2:
                    raise
                print(
                    f"HTTP {error.code}; bounded retry {attempt + 1}/2 after {(attempt + 1) * 30}s"
                )
                for _ in range(attempt + 1):
                    time.sleep(30)
        raise AssertionError("Unreachable request retry state")

    rightsinfo = request({"meta": "siteinfo", "siprop": "rightsinfo"}, "license")["query"][
        "rightsinfo"
    ]
    if rightsinfo.get("url", "").rstrip("/") not in (
        LICENSE_URL.rstrip("/"),
        LICENSE_URL + "deed.id",
    ):
        raise ValueError("Wikipedia site license differs from configured CC-BY-SA-4.0")
    candidates, articles, listing, seen, continuations = [], {}, [], set(), set()
    eligible, groups, blocked_groups = [], [], []
    continuation = {"apfrom": START_TITLE}
    max_batches = (max_candidates + LIST_BATCH - 1) // LIST_BATCH
    for _ in range(max_batches):
        remaining = max_candidates - len(listing)
        if remaining <= 0:
            break
        batch_limit = min(LIST_BATCH, remaining)
        data = request(
            {
                "list": "allpages",
                "apnamespace": 0,
                "apfilterredir": "nonredirects",
                "apdir": "ascending",
                "aplimit": batch_limit,
                **continuation,
            },
            "listing",
        )
        next_continuation = data.get("continue")
        pages = data["query"]["allpages"]
        if not isinstance(pages, list) or len(pages) > batch_limit:
            raise ValueError("Allpages response exceeds listing budget")
        pending = []
        for page in pages:
            pageid, title = page.get("pageid"), page.get("title")
            if (
                page.get("ns") != 0
                or type(pageid) is not int
                or pageid < 1
                or not isinstance(title, str)
                or not title.strip()
                or len(title) > 1000
            ):
                raise ValueError("Invalid namespace0 allpages entry")
            docid = f"idwiki/{pageid}"
            record = {"id": docid, "pageid": pageid, "title": title}
            listing.append(record)
            if docid in pilot_ids or pageid in seen:
                record["status"] = "pilot-id" if docid in pilot_ids else "repeated-id"
                continue
            seen.add(pageid)
            pending.append(record)
        for offset in range(0, len(pending), EXTRACT_BATCH):
            batch = pending[offset : offset + EXTRACT_BATCH]
            data = request(
                {
                    "prop": "extracts|info|revisions",
                    "pageids": "|".join(str(item["pageid"]) for item in batch),
                    "explaintext": 1,
                    "exintro": 1,
                    "exlimit": EXTRACT_BATCH,
                    "rvprop": "ids|timestamp",
                    "inprop": "url",
                },
                "extracts",
            )
            if "continue" in data:
                raise ValueError(
                    "Unexpected extract continuation; cached batch requires inspection"
                )
            requested = {item["pageid"] for item in batch}
            returned = {}
            for page in data["query"]["pages"]:
                pageid = page.get("pageid")
                if "missing" in page:
                    continue
                if pageid not in requested or pageid in returned:
                    raise ValueError("Unexpected or repeated extract page identifier")
                returned[pageid] = page
            for record in batch:
                page = returned.get(record["pageid"])
                parsed = parse_page(page) if page and "redirect" not in page else None
                if parsed is None:
                    record["status"] = "unusable-introduction"
                    continue
                document, article = parsed
                document["genre"] = "encyclopedia-title-ordered"
                candidates.append(document)
                articles[document["id"]] = article
                record["status"] = "usable"
        eligible, groups, blocked_groups = eligible_documents(pilot, candidates)
        if len(eligible) >= limit:
            break
        if next_continuation is None:
            break
        if (
            not isinstance(next_continuation, dict)
            or not {"apcontinue", "continue"} == next_continuation.keys()
            or any(not isinstance(value, str) for value in next_continuation.values())
            or not next_continuation["apcontinue"]
        ):
            raise ValueError("Invalid allpages continuation")
        marker = digest(next_continuation)
        if marker in continuations:
            raise ValueError("Repeated allpages continuation")
        continuations.add(marker)
        continuation = next_continuation
    if len(eligible) < limit:
        raise ValueError(
            f"Only {len(eligible)} eligible introductions from {len(listing)} candidates; "
            f"requested {limit}. API cache preserved; corpus snapshot not written"
        )
    documents = validate_documents(eligible[:limit])
    selected = {doc["id"] for doc in documents}
    independent_groups = sum(bool(selected.intersection(group)) for group in groups)
    if independent_groups < minimum_groups:
        raise ValueError(
            f"Only {independent_groups} independent groups; required {minimum_groups}. "
            "API cache preserved; corpus snapshot not written"
        )
    blocked = {docid for group in blocked_groups for docid in group} - pilot_ids
    for record in listing:
        if record.get("status") == "usable":
            record["status"] = (
                "pilot-duplicate-group"
                if record["id"] in blocked
                else "selected"
                if record["id"] in selected
                else "budget-surplus"
            )
    output.mkdir(parents=True)
    corpus = output / "documents.jsonl"
    with corpus.open("x", encoding="utf-8") as stream:
        for document in documents:
            stream.write(json.dumps(document, ensure_ascii=False) + "\n")
    manifest = {
        "format": "indonesian-wikipedia-expansion-v1",
        "created_at": timestamp(),
        "policy": POLICY,
        "language": "id",
        "license": LICENSE,
        "license_url": LICENSE_URL,
        "license_evidence": rightsinfo,
        "terms_url": TERMS,
        "api": API,
        "requests": requests,
        "failed_attempts": failed_attempts,
        "selection": {
            "start_title": START_TITLE,
            "namespace": 0,
            "nonredirect": True,
            "order": "MediaWiki allpages ascending title; preserve API order across batches",
            "limit": limit,
            "max_candidates": max_candidates,
            "maximum_listing_batches": max_batches,
            "maximum_success_requests": 1
            + max_batches * (1 + (LIST_BATCH + EXTRACT_BATCH - 1) // EXTRACT_BATCH),
            "maximum_attempts_per_request": 3,
            "request_delay_seconds": 3 if download else 0,
            "retry_backoff_seconds": [30, 60],
            "listing_batch": LIST_BATCH,
            "extract_batch": EXTRACT_BATCH,
            "minimum_groups": minimum_groups,
            "pageids": [int(doc["id"].split("/")[1]) for doc in documents],
            "candidates": listing,
        },
        "pilot_exclusion": {
            "path": str(PILOT.relative_to(ROOT)),
            "jsonl_sha256": hashlib.sha256(PILOT.read_bytes()).hexdigest(),
            "documents_sha256": digest(pilot),
            "ids": sorted(pilot_ids),
            "duplicate_policy": DUPLICATE_POLICY,
            "blocked_groups": sorted(sorted(group) for group in blocked_groups),
            "grouping": "split_documents groups only; unused assignment discarded; no model split",
        },
        "source_kind": "title-ordered encyclopedic introductions; not representative Indonesian",
        "preprocessing": "Pilot parse_page: punctuation/newline; core wordpunct alpha lowercase",
        "snapshot": "Exact cached API hashes; observed revision IDs, not revision-pinned extracts",
        "model_split": "not performed; corpus frozen before model splitting or scoring",
        "documents": len(documents),
        "sentences": sum(len(doc["sentences"]) for doc in documents),
        "tokens": sum(len(sentence) for doc in documents for sentence in doc["sentences"]),
        "independent_groups": independent_groups,
        "documents_sha256": digest(documents),
        "jsonl_sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
        "importer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "pilot_importer_sha256": hashlib.sha256(
            Path(__file__).with_name("prepare_indonesian.py").read_bytes()
        ).hexdigest(),
        "articles": [articles[doc["id"]] for doc in documents],
        "attribution": "Wikipedia contributors; article source/history URLs; derived CC-BY-SA-4.0",
    }
    with (output / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
    return corpus, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--max-candidates", type=int, default=5000)
    parser.add_argument("--minimum-groups", type=int, default=200)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args(argv)
    corpus, manifest = prepare(
        args.output, args.limit, args.max_candidates, args.minimum_groups, args.download
    )
    print(
        json.dumps(
            {
                "path": str(corpus),
                "documents": manifest["documents"],
                "independent_groups": manifest["independent_groups"],
                "jsonl_sha256": manifest["jsonl_sha256"],
                "requests": len(manifest["requests"]),
                "license": manifest["license"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
