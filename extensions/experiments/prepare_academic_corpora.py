"""Freeze a clustered random sample of full Indonesian Wikipedia articles."""

import argparse
import hashlib
import json
import random
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core.src.data import ROOT
from core.src.preprocess import preprocess, tokenize
from extensions.src.datasets import digest, read_documents, split_documents, validate_documents

DATASET = "wikimedia/wikipedia"
CONFIG = "20231101.id"
REVISION = "b04c8d1ceb2f5cd4588862100d08de323dccfbaa"
ROWS = "https://datasets-server.huggingface.co/rows"
METADATA = "https://huggingface.co/api/datasets/wikimedia/wikipedia"
LICENSE = "CC-BY-SA-3.0"
SEED = 271828
WINDOW_SIZE = 100
HISTORICAL = (
    "wiki-pilot-20261010-final",
    "wiki-expansion-20261011",
)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def fetch(path, url, download):
    """Keep exact UTF-8 response bytes in a verified, resumable repository-local receipt."""
    if path.exists():
        if path.stat().st_size > 16 * 2**20:
            raise ValueError("Cached source receipt exceeds 16 MiB")
        envelope = json.loads(path.read_text(encoding="utf-8"))
    else:
        if not download:
            raise ValueError(f"Missing {path}; pass --download")
        request = Request(
            url,
            headers={
                "User-Agent": "NgramAcademicCorpus/1.0 (educational; https://github.com/Maliq-dlt/N-Gram)",
                "Accept": "application/json",
            },
        )
        for attempt in range(4):
            try:
                with urlopen(request, timeout=45) as response:
                    raw = response.read(8 * 2**20 + 1)
                break
            except (HTTPError, URLError, TimeoutError) as exc:
                if (
                    attempt == 3
                    or isinstance(exc, HTTPError)
                    and exc.code not in (429, 500, 502, 503, 504)
                ):
                    raise
                header = exc.headers.get("Retry-After", "") if isinstance(exc, HTTPError) else ""
                retry_after = int(header) if header.isdecimal() else 0
                time.sleep(min(120, max(retry_after, 15 * 2**attempt)))
        if len(raw) > 8 * 2**20:
            raise ValueError("Source response exceeds 8 MiB")
        data = json.loads(raw)
        if not isinstance(data, dict) or "error" in data:
            raise ValueError("Source API returned an error")
        envelope = {
            "url": url,
            "retrieved_at": timestamp(),
            "response_sha256": sha(raw),
            "raw_json": raw.decode("utf-8"),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            json.dump(envelope, stream, ensure_ascii=False)
        time.sleep(1.2)
    if (
        envelope["url"] != url
        or sha(envelope["raw_json"].encode("utf-8")) != envelope["response_sha256"]
    ):
        raise ValueError("Source response receipt URL/hash mismatch")
    data = json.loads(envelope["raw_json"])
    if not isinstance(data, dict) or "error" in data:
        raise ValueError("Source API returned an error")
    return data, {key: envelope[key] for key in ("url", "retrieved_at", "response_sha256")}


def source_info(metadata):
    if metadata.get("id") != DATASET or metadata.get("sha") != REVISION:
        raise ValueError("Upstream dataset revision changed; review source before collecting")
    licenses = metadata.get("cardData", {}).get("license", [])
    if not {"cc-by-sa-3.0", "gfdl"} <= set(licenses):
        raise ValueError("Unexpected source license")
    configs = metadata["cardData"]["dataset_info"]
    selected = [item for item in configs if item.get("config_name") == CONFIG]
    if len(selected) != 1:
        raise ValueError("Missing Indonesian snapshot configuration")
    split = selected[0]["splits"]
    if len(split) != 1 or split[0].get("name") != "train":
        raise ValueError("Unexpected upstream split")
    return split[0]["num_examples"], licenses


def row_url(offset):
    return (
        ROWS
        + "?"
        + urlencode(
            {
                "dataset": DATASET,
                "config": CONFIG,
                "split": "train",
                "offset": offset,
                "length": 100,
            }
        )
    )


def windows(total, count, seed):
    if type(total) is not int or total < WINDOW_SIZE or type(count) is not int or count < 1:
        raise ValueError("Invalid source size or window count")
    starts = range(0, total, WINDOW_SIZE)
    if count > len(starts):
        raise ValueError("Window count exceeds source")
    return sorted(random.Random(seed).sample(starts, count))


def parse_row(record):
    if not isinstance(record, dict) or not isinstance(record.get("row_idx"), int):
        raise ValueError("Invalid upstream row index")
    row = record.get("row")
    if not isinstance(row, dict) or not {"id", "url", "title", "text"} <= row.keys():
        raise ValueError("Invalid upstream article fields")
    pageid, url, title, article = (row[key] for key in ("id", "url", "title", "text"))
    if (
        not isinstance(pageid, str)
        or not pageid.isdecimal()
        or int(pageid) < 1
        or not isinstance(url, str)
        or not url.startswith("https://id.wikipedia.org/wiki/")
        or len(url) > 1000
        or not isinstance(title, str)
        or not title.strip()
        or len(title) > 400
        or not isinstance(article, str)
    ):
        raise ValueError("Invalid Wikipedia page ID, URL, title, or text")
    article_bytes = article.encode("utf-8")
    if len(article_bytes) > 512 * 2**10:
        return None, "oversize-article"
    chunks = re.split(r"(?<=[.!?])\s+|\n+", article.strip())
    sentences, _ = preprocess([tokenize(chunk) for chunk in chunks if chunk.strip()])
    # ponytail: skip short section headings; restore them only with a section-aware parser.
    sentences = [[word for word in sentence if len(word) <= 256] for sentence in sentences]
    sentences = [sentence for sentence in sentences if len(sentence) >= 5]
    token_count = sum(map(len, sentences))
    if token_count < 100:
        return None, "under-100-tokens"
    doc_id = f"idwiki/{int(pageid)}"
    doc = {
        "id": doc_id,
        "source": url,
        "license": LICENSE,
        "group": doc_id,
        "genre": "encyclopedia",
        "title": title,
        "sentences": sentences,
    }
    return (
        doc,
        {
            "row_index": record["row_idx"],
            "text_sha256": sha(article_bytes),
            "tokens_sha256": digest(sentences),
            "tokens": token_count,
        },
    ), None


def historical_exposure():
    ids, hashes, sources = set(), set(), []
    for name in HISTORICAL:
        path = ROOT / "data" / "indonesian" / name / "documents.jsonl"
        documents = read_documents(path)
        ids.update(doc["id"] for doc in documents)
        hashes.update(digest(doc["sentences"]) for doc in documents)
        sources.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path.read_bytes()),
                "document_count": len(documents),
            }
        )
    return ids, hashes, sources


def prepare(output, *, target=3000, window_count=160, seed=SEED, download=False):
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT / "data").resolve()):
        raise ValueError("Output must remain inside repository data/")
    if (
        type(target) is not int
        or not 2000 <= target <= 3000
        or type(seed) is not int
        or not 0 <= seed < 2**32
    ):
        raise ValueError("Target must be 2000..3000 and seed must be uint32")
    if output.exists() and any(item.name != "raw" for item in output.iterdir()):
        raise FileExistsError(output)
    raw_dir = output / "raw"
    initial, first_receipt = fetch(raw_dir / "metadata-before.json", METADATA, download)
    total, licenses = source_info(initial)
    selected_windows = windows(total, window_count, seed)
    prior_ids, prior_hashes, prior_sources = historical_exposure()
    candidates, eligible, seen_ids, seen_hashes, receipts = [], [], set(), set(), []
    for offset in selected_windows:
        response, receipt = fetch(raw_dir / f"row-{offset:06d}.json", row_url(offset), download)
        receipts.append({"offset": offset, **receipt})
        rows = response.get("rows")
        if (
            response.get("num_rows_total") != total
            or response.get("partial")
            or not isinstance(rows, list)
        ):
            raise ValueError("Upstream rows do not match snapshot metadata")
        if [record.get("row_idx") for record in rows] != list(
            range(offset, min(offset + 100, total))
        ):
            raise ValueError("Upstream row indices missing or out of order")
        for record in rows:
            parsed, reason = parse_row(record)
            candidate = {"row_index": record["row_idx"]}
            if parsed is not None:
                doc, evidence = parsed
                candidate.update({"id": doc["id"], **evidence})
                if doc["id"] in prior_ids:
                    reason = "historical-id"
                elif evidence["tokens_sha256"] in prior_hashes:
                    reason = "historical-tokens"
                elif doc["id"] in seen_ids:
                    reason = "duplicate-id"
                elif evidence["tokens_sha256"] in seen_hashes:
                    reason = "duplicate-tokens"
                else:
                    seen_ids.add(doc["id"])
                    seen_hashes.add(evidence["tokens_sha256"])
                    eligible.append(candidate)
            candidate["status"] = reason or "eligible"
            candidates.append(candidate)
    final, final_receipt = fetch(raw_dir / "metadata-after.json", METADATA, download)
    if final_receipt["retrieved_at"] < max(item["retrieved_at"] for item in receipts):
        raise ValueError(
            "Cached metadata-after predates article responses; move it aside and retry"
        )
    if source_info(final)[0] != total:
        raise ValueError("Dataset row count changed during acquisition")
    ranked = sorted(eligible, key=lambda item: sha(f"{seed}:{item['id']}".encode()))
    if len(ranked) < target:
        raise ValueError(f"Only {len(ranked)} eligible articles for target {target}")
    selected = {item["row_index"]: item for item in ranked[:target]}
    documents = []
    for offset in selected_windows:
        response, _ = fetch(raw_dir / f"row-{offset:06d}.json", row_url(offset), False)
        for record in response["rows"]:
            if record["row_idx"] in selected:
                parsed, reason = parse_row(record)
                if (
                    reason
                    or parsed is None
                    or digest(parsed[0]["sentences"])
                    != selected[record["row_idx"]]["tokens_sha256"]
                ):
                    raise ValueError("Selected article changed during replay")
                documents.append(parsed[0])
    # Existing split policy identifies near duplicates without fitting or exposing test outcomes.
    _, grouping = split_documents(documents, seed=seed)
    rank = {item["id"]: index for index, item in enumerate(ranked)}
    duplicate_of = {}
    for group in grouping["groups"]:
        representative = min(group, key=rank.__getitem__)
        duplicate_of.update(
            {article: representative for article in group if article != representative}
        )
    documents = sorted(
        (doc for doc in documents if doc["id"] not in duplicate_of), key=lambda doc: rank[doc["id"]]
    )
    validate_documents(documents)
    tokens = sum(len(sentence) for doc in documents for sentence in doc["sentences"])
    if len(documents) < 2000 or tokens < 500_000:
        raise ValueError(
            f"Insufficient independent material: {len(documents)} documents, {tokens} tokens"
        )
    output.mkdir(parents=True, exist_ok=True)
    corpus = output / "documents.jsonl"
    with corpus.open("x", encoding="utf-8") as stream:
        for doc in documents:
            stream.write(json.dumps(doc, ensure_ascii=False) + "\n")
    selected_ids = {doc["id"] for doc in documents}
    for candidate in candidates:
        if candidate["status"] == "eligible":
            candidate["status"] = (
                "selected"
                if candidate["id"] in selected_ids
                else "group-overlap"
                if candidate["id"] in duplicate_of
                else "rank-surplus"
            )
            if candidate["id"] in duplicate_of:
                candidate["grouped_with"] = duplicate_of[candidate["id"]]
    manifest = {
        "format": "academic-idwiki-full-v1",
        "created_at": timestamp(),
        "source": {
            "dataset": DATASET,
            "config": CONFIG,
            "split": "train",
            "snapshot_date": "2023-11-01",
            "repository_revision": REVISION,
            "dataset_card_url": f"https://huggingface.co/datasets/{DATASET}",
            "license": licenses,
            "license_url": "https://creativecommons.org/licenses/by-sa/3.0/",
            "total_rows": total,
            "metadata_before": first_receipt,
            "metadata_after": final_receipt,
        },
        "selection": {
            "seed": seed,
            "window_size": WINDOW_SIZE,
            "window_starts": selected_windows,
            "requested_documents": target,
            "candidate_rows": len(candidates),
            "eligible_rows": len(eligible),
            "selected_documents": len(documents),
            "status_counts": dict(Counter(item["status"] for item in candidates)),
            "design": "Random 100-row windows, then seeded SHA-256 rank; clustered sample, not SRS",
            "minimum_processed_tokens_per_article": 100,
            "minimum_total_tokens": 500_000,
        },
        "historical_exposure": {
            "sources": prior_sources,
            "excluded_ids": sorted(prior_ids),
            "rule": "exclude identical page IDs or exact processed-document hashes",
        },
        "preprocessing": (
            "Full article text; punctuation/newline sentence segmentation; "
            "core wordpunct/alpha/lowercase; drop chunks under 5 tokens and "
            "tokens over 256 characters"
        ),
        "grouping_policy": grouping["policy"],
        "snapshot_limit": (
            "Rows API has no documented revision parameter; repository SHA checked "
            "before/after, exact response bytes frozen and SHA-256 verified; "
            "viewer conversion revision cannot be pinned; per-article revision IDs are unavailable"
        ),
        "requests": receipts,
        "candidates": candidates,
        "documents": len(documents),
        "sentences": sum(len(doc["sentences"]) for doc in documents),
        "tokens": tokens,
        "documents_sha256": digest(documents),
        "jsonl_sha256": sha(corpus.read_bytes()),
        "importer_sha256": sha(Path(__file__).read_bytes()),
        "attribution": (
            "Wikipedia contributors; source URLs in documents and page histories "
            "identify authors. Derived corpus is CC-BY-SA-3.0."
        ),
    }
    with (output / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
    return corpus, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/academic_upgrade_v2/idwiki_20231101_full"
    )
    parser.add_argument("--target", type=int, default=3000)
    parser.add_argument("--windows", type=int, default=160)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args(argv)
    corpus, manifest = prepare(
        args.output,
        target=args.target,
        window_count=args.windows,
        seed=args.seed,
        download=args.download,
    )
    print(
        json.dumps(
            {
                "path": str(corpus),
                "documents": manifest["documents"],
                "tokens": manifest["tokens"],
                "manifest": str(corpus.parent / "manifest.json"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
