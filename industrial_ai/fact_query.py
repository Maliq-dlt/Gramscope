"""Deterministic ledger questions. Predictions never supply identities or counts."""

from __future__ import annotations

import re

from event_ledger import FactFilter, facts, filtered_facts


def answer_filtered(message, rows, job_id):
    """Bounded grammar: explicit class/direction/offset; never infer missing filters."""
    q = " ".join(message.lower().strip().rstrip("?!.").split())
    if not q.startswith("ledger crossing"):
        return None
    match = re.fullmatch(
        r"ledger crossing (person|car|bus|truck|motorcycle|bicycle)(?: (up|down))?(?: dari (\d+(?:\.\d+)?) sampai (\d+(?:\.\d+)?) detik)?",
        q,
    )
    if not match or not job_id:
        return {
            "answer": "Filter belum didukung. Pilih rekaman, lalu gunakan 'ledger crossing person down dari 0 sampai 10 detik'.",
            "mode": "facts",
            "evidence": [],
            "ledger_proof": [],
        }
    kind, direction, start, end = match.groups()
    try:
        filters = FactFilter.model_validate(
            {
                "recording_id": job_id,
                "class_name": kind,
                "direction": direction,
                "start_seconds": float(start or 0),
                "end_seconds": float(end) if end else None,
            }
        )
    except ValueError:
        return {
            "answer": "Rentang belum didukung: awal harus lebih kecil dari akhir.",
            "mode": "facts",
            "evidence": [],
            "ledger_proof": [],
        }
    result = filtered_facts(rows, filters)
    text = f"Ada {result['crossing_event_count']} kejadian crossing {kind} terverifikasi pada filter ini."
    if not result["has_verified_coverage"]:
        text += " Belum ada coverage terverifikasi; angka nol tidak berarti video kosong."
    proof = [r for r in result["proof"] if r["symbol"].endswith(("_ENTER_ZONE", "_EXIT_ZONE"))]
    return {"answer": text, "mode": "facts", "evidence": [], "ledger_proof": proof, "facts": result}


def answer_ledger(message, rows, role, job_id=None):
    filtered = answer_filtered(message, rows, job_id)
    if filtered is not None:
        return filtered
    q = " ".join(message.lower().strip().rstrip("?!.").split())
    attendance = bool(
        re.search(
            r"absen|kehadiran|catatan hadir|(?:siapa|karyawan|pegawai|orang)\b.*\b(?:datang|hadir|pulang)",
            q,
        )
    )
    observation = bool(
        re.search(r"(?:kejadian|crossing|lintasan|track|helm) terverifikasi|ledger", q)
    )
    if not attendance and not observation:
        return None
    selected = [r for r in rows if job_id is None or r.get("job_id") == job_id]
    current = facts(selected, role)
    proof = []
    if attendance and role != "admin":
        text = "Identitas dan catatan absensi hanya dapat dibaca administrator. Track ID bukan identitas pegawai."
    elif re.search(
        r"\b(?:kemarin|besok|pukul|jam|tanggal|shift|sekarang|saat ini|sedang|hari ini|tadi|sejak|sebelum|setelah|selama|pagi|siang|sore|malam|minggu|bulan|tahun)\b|\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}",
        q,
    ):
        text = "Filter waktu dan status hadir seluruh shift belum didukung oleh query chat ini. Tinjau timestamp berzona pada catatan terverifikasi; kehadiran saat ini belum dapat disimpulkan."
    elif attendance and re.search(r"mobil|kendaraan|helm|wajah|topeng|foto palsu", q):
        text = "Ledger absensi berisi catatan identitas yang diverifikasi administrator; pertanyaan deteksi atau biometrik tidak dapat dijawab dari catatan ini."
    elif not re.fullmatch(
        (
            r"(?:(?:berapa|jumlah) (?:catatan )?(?:absensi|kehadiran)(?: terverifikasi)?"
            r"|siapa (?:yang )?(?:datang|hadir|pulang))(?: di ledger)?"
            if attendance
            else r"(?:(?:berapa |jumlah )?(?:kejadian|crossing|lintasan|track|helm) terverifikasi"
            r"|(?:berapa |jumlah )?(?:kejadian|crossing|lintasan|track|helm)(?: terverifikasi)? di ledger"
            r"|(?:berapa )?(?:orang unik|identitas(?: orang| pegawai)?) di ledger|ledger)"
        ),
        q,
    ):
        text = "Bentuk atau filter pertanyaan ini belum didukung. Gunakan 'berapa catatan absensi?', 'siapa datang?', atau 'berapa crossing terverifikasi?'. Filter pegawai, negasi, gabungan kondisi, arah crossing, dan hitungan orang unik tidak diterapkan otomatis."
    elif attendance:
        records = [
            r for r in selected if r["status"] == "verified" and r["category"] == "attendance"
        ]
        action = (
            "ATTENDANCE_DEPARTED"
            if "pulang" in q
            else "ATTENDANCE_ARRIVED"
            if re.search(r"datang|hadir", q)
            else None
        )
        if action:
            records = [r for r in records if r["symbol"] == action]
        ambiguous = {(r["job_id"], r["track_id"]) for r in current["ambiguous_track_links"]}
        if "siapa" in q:
            identified = [
                r for r in records if (r.get("job_id"), r.get("track_id")) not in ambiguous
            ]
            subjects = sorted({r["payload"]["subject_id"] for r in identified})
            text = (
                "ID pada catatan absensi terverifikasi: "
                + (", ".join(subjects[:20]) if subjects else "belum diketahui")
                + "."
            )
            if ambiguous:
                text += " Relasi track yang ambigu tidak dipakai untuk menyimpulkan identitas."
            proof = identified[:20]
        else:
            text = f"Ada {len(records)} catatan absensi terverifikasi dalam scope ini. Ini jumlah catatan, bukan jumlah orang unik atau bukti hadir sepanjang shift."
            proof = records[:20]
        text += " Sumber identitas diverifikasi manual oleh administrator; pengenalan wajah dan scanner badge/QR belum diterapkan."
    else:
        proof = [
            r for r in selected if r["status"] == "verified" and r["category"] == "observation"
        ]
        if "helm" in q:
            proof = [r for r in proof if r["symbol"].startswith("HELMET_")]
        elif "track" not in q and "orang unik" not in q and "identitas" not in q:
            proof = [r for r in proof if r["symbol"] in {"PERSON_ENTER_ZONE", "PERSON_EXIT_ZONE"}]
        else:
            proof = []
        proof = proof[:20]
        if "helm" in q:
            known = [
                r for r in selected if r["status"] == "verified" and r["category"] == "observation"
            ]
            worn = sum(r["symbol"] == "HELMET_WORN" for r in known)
            not_worn = sum(r["symbol"] == "HELMET_NOT_WORN" for r in known)
            text = (
                f"Observasi helm terverifikasi: dipakai {worn}, tidak dipakai {not_worn}, "
                f"unknown {current['unknown_helmet_observation_count']}. Track bukan identitas; unknown bukan pelanggaran."
            )
        elif "orang unik" in q or "identitas" in q:
            text = "Jumlah orang unik dan identitas dari track belum diketahui; track lintas rekaman tidak digabung sebagai satu orang."
        elif "track" in q:
            text = f"Ada {current['observed_track_count']} track teramati pada kejadian terverifikasi; track bukan identitas orang."
        else:
            text = f"Ada {current['crossing_event_count']} kejadian crossing orang terverifikasi. Enter/exit berarti sisi bawah garis analisis, bukan masuk atau keluar pabrik."
    if current["stale_count"] or current["retracted_count"]:
        text += f" {current['stale_count']} catatan stale dan {current['retracted_count']} catatan ditarik dikeluarkan dari hitungan."
    references = [
        {
            "event_id": r["id"],
            "occurred_at": r["occurred_at"],
            "verified_at": r["verified_at"],
            "source": r["payload"],
        }
        for r in proof
    ]
    if references:
        text += "\nBukti: " + "; ".join(
            r["event_id"] + " @ " + (r["occurred_at"] or str(r["source"].get("seconds", "?")) + "s")
            for r in references
        )
    return {
        "answer": text,
        "mode": "facts",
        "evidence": [],
        "ledger_proof": references,
        "source": "ledger terverifikasi; " + ("rekaman " + job_id if job_id else "workspace aktif"),
    }
