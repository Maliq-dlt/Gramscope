"""Group verified observations by recording/track; camera gaps end a sequence."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

SYMBOLS = {"PERSON_ENTER_ZONE", "PERSON_EXIT_ZONE", "HELMET_UNKNOWN"}


def event_sequences(rows, max_gap_seconds=30):
    if type(max_gap_seconds) not in (int, float) or not 0 < max_gap_seconds <= 86400:
        raise ValueError("Gap must be positive and at most one day.")
    grouped = defaultdict(list)
    seen = set()
    for row in rows:
        if row.get("status") != "verified" or row.get("category") != "observation":
            continue
        if row["symbol"] not in SYMBOLS or row.get("track_id") is None or not row.get("job_id"):
            raise ValueError("Verified observation lacks a supported symbol/recording/track.")
        when = datetime.fromisoformat(row["occurred_at"].replace("Z", "+00:00"))
        if when.tzinfo is None:
            raise ValueError("Observation time must include a timezone.")
        unique = (
            row["workspace_id"],
            row["job_id"],
            row["track_id"],
            when.timestamp(),
            row["symbol"],
        )
        if unique in seen:
            continue
        seen.add(unique)
        grouped[unique[:3]].append((when.timestamp(), row))
    result = []
    for key, observations in sorted(grouped.items()):
        chunk = []
        previous = None
        session_index = 0
        start_reason = "track_start"

        def finish():
            nonlocal session_index
            if chunk:
                result.append(
                    {
                        "workspace_id": key[0],
                        "recording_id": key[1],
                        "track_id": key[2],
                        "session_index": session_index,
                        "start_reason": start_reason,
                        "symbols": [item["symbol"] for item in chunk],
                        "event_ids": [item["id"] for item in chunk],
                        "times": [item["occurred_at"] for item in chunk],
                    }
                )
                session_index += 1

        for when, row in sorted(
            observations,
            key=lambda item: (
                item[0],
                item[1]["symbol"] == "HELMET_UNKNOWN",
                item[1]["symbol"],
                item[1]["id"],
            ),
        ):
            if previous is not None and when - previous > max_gap_seconds:
                finish()
                chunk = []
                start_reason = "camera_gap"
            chunk.append(row)
            previous = when
        finish()
    return result


EVENT_SYMBOLS_V2 = {
    kind + suffix
    for kind in ("PERSON", "CAR", "BUS", "TRUCK", "MOTORCYCLE", "BICYCLE")
    for suffix in ("_ENTER_ZONE", "_EXIT_ZONE")
} | {"HELMET_WORN", "HELMET_NOT_WORN", "HELMET_UNKNOWN"}


def event_sequences_v2(rows, max_gap_seconds=30):
    """Explicit offsets, revision groups and simultaneous bundles; no identity tokens."""
    import math
    import re

    if (
        type(max_gap_seconds) not in (int, float)
        or not math.isfinite(max_gap_seconds)
        or not 0 < max_gap_seconds <= 86400
    ):
        raise ValueError("Gap must be finite and positive, at most one day.")
    grouped, identifiers = defaultdict(list), {}
    for row in rows:
        if row.get("status") != "verified" or row.get("category") != "observation":
            continue
        payload = row.get("payload", {})
        if (
            payload.get("schema_version") != 2
            or row.get("symbol") not in EVENT_SYMBOLS_V2
            or type(row.get("track_id")) is not int
            or row["track_id"] < 0
            or any(
                not isinstance(row.get(k), str) or not 1 <= len(row[k]) <= 120
                for k in ("id", "workspace_id", "job_id")
            )
            or any(
                not isinstance(payload.get(k), str) or not re.fullmatch(r"[a-f0-9]{64}", payload[k])
                for k in ("original_source_sha256", "source_revision")
            )
            or type(payload.get("seconds")) not in (int, float)
            or not math.isfinite(payload["seconds"])
            or not 0 <= payload["seconds"] <= 86400
        ):
            raise ValueError(
                "Version 2 requires supported symbols, explicit offset/source/revision provenance."
            )
        clean = {
            "id": row["id"],
            "symbol": row["symbol"],
            "seconds": payload["seconds"],
            "recording_id": row["job_id"],
            "track_id": row["track_id"],
            "source_revision": payload["source_revision"],
            "source_group": payload["original_source_sha256"],
        }
        if row["id"] in identifiers:
            if identifiers[row["id"]] != clean:
                raise ValueError("Conflicting duplicate event ID.")
            continue
        identifiers[row["id"]] = clean
        key = (
            row["workspace_id"],
            row["job_id"],
            row["track_id"],
            payload["source_revision"],
            payload["original_source_sha256"],
        )
        grouped[key].append(clean)
    result = []
    for key, rows in sorted(grouped.items()):
        by_offset = defaultdict(list)
        for row in rows:
            by_offset[row["seconds"]].append(row)
        chunks, chunk, previous = [], [], None
        for seconds, bundle in sorted(by_offset.items()):
            if previous is not None and seconds - previous > max_gap_seconds:
                chunks.append(chunk)
                chunk = []
            symbols = sorted({r["symbol"] for r in bundle})
            # ponytail: crossing-time helmet samples; add intervals with reviewed coverage.
            chunk.append(
                {
                    "symbol": "BUNDLE:" + "|".join(symbols),
                    "seconds": seconds,
                    "event_ids": sorted(r["id"] for r in bundle),
                }
            )
            previous = seconds
        if chunk:
            chunks.append(chunk)
        for index, chunk in enumerate(chunks):
            result.append(
                {
                    "schema_version": 2,
                    "workspace_id": key[0],
                    "recording_id": key[1],
                    "track_id": key[2],
                    "source_revision": key[3],
                    "source_group": key[4],
                    "session_index": index,
                    "start_reason": "track_start" if index == 0 else "event_gap",
                    "end_reason": "event_gap" if index + 1 < len(chunks) else "last_reviewed_event",
                    "symbols": [b["symbol"] for b in chunk],
                    "bundles": chunk,
                    "event_ids": [event for b in chunk for event in b["event_ids"]],
                    "times": [b["seconds"] for b in chunk],
                    "source_events": sorted(
                        (r for r in rows if r["id"] in {e for b in chunk for e in b["event_ids"]}),
                        key=lambda r: (r["seconds"], r["id"]),
                    ),
                }
            )
    return result
