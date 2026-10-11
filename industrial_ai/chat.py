"""Verified queries first; a real local LoRA model handles ordinary conversation."""

from __future__ import annotations

import re
import time
from typing import cast

from runtime import CHAT_ADAPTER, CHAT_BASE, select_device
from vision import OBJECT_NAMES, reviewed_summary

SYSTEM = (
    "Kamu asisten Video Insight Lokal. Jawab singkat dalam Bahasa Indonesia. "
    "Jelaskan hanya kemampuan yang tersedia: unggah video, tracking orang dan kendaraan, "
    "deteksi helm, perbandingan video, koreksi manual, training detector dari review lengkap, analisis ulang dan ringkasan. Track ID bukan identitas orang. "
    "Hasil model helm adalah kandidat, bukan keputusan keselamatan. "
    "Lab N-gram dan ledger crossing/absensi yang diverifikasi manual tersedia. "
    "N-gram memodelkan kata/simbol kejadian, tidak membaca piksel atau wajah. "
    "Scanner badge/QR, pembacaan plat, identifikasi wajah dan CCTV live belum tersedia. "
    "Jangan mengarang angka, nama orang, kejadian, atau sumber. "
    "Untuk angka analisis, arahkan pengguna ke pertanyaan jumlah/ringkasan yang memakai data terverifikasi."
)
_model = None
_tokenizer = None
_loaded_device = None


def release_model():
    """Free chat weights before detector training, without changing adapter files."""
    global _model, _tokenizer, _loaded_device
    import gc

    import torch

    _model = _tokenizer = _loaded_device = None
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def answer_facts(message: str, summary: dict | None) -> dict | None:
    q = message.lower()
    ai_only = bool(re.search(r"\b(ai|otomatis|model)\b", q))
    if summary is not None:
        summary = reviewed_summary(summary)
    names: dict[str, str] = {**OBJECT_NAMES, **(summary or {}).get("object_names", {})}
    manual_labels = {
        b["label"]
        for f in (summary or {}).get("manual_frames", [])
        for b in f["boxes"]
        if b["label"] not in {"Hardhat", "NO-Hardhat"}
    }
    for label in manual_labels:
        names.setdefault(label, label)
    terms = (
        "orang",
        "pekerja",
        "karyawan",
        "mobil",
        "bus",
        "bis",
        "truk",
        "motor",
        "sepeda",
        "kendaraan",
        "helm",
        "apd",
        "bukti",
        "lewat",
        "lintas",
        "ringkas",
        "video",
        "rekaman",
        "track",
        "hasilnya",
        "jumlahnya",
        "totalnya",
        "plat",
        "wajah",
        "absen",
        "cctv",
    )
    guide_terms = (
        "proyek",
        "aplikasi",
        "sistem",
        "tracking",
        "track id",
        "kotak",
        "warna",
        "fine-tuning",
        "fine tuning",
        "model",
    )
    if any(term in q for term in guide_terms) and not any(
        term in q
        for term in (
            "berapa",
            "jumlah",
            "siapa",
            "bukti",
            "detik",
            "lewat",
            "lintas",
            "plat",
            "absen",
            "wajah",
            "cctv",
        )
    ):
        return {
            "answer": "Unggah video pendek, pilih garis counting, lalu mulai analisis. Setelah selesai, putar video asli dan hasil tracking bersama. Kotak mengikuti orang, mobil, bus, truk, motor dan sepeda dengan ID sementara; hijau berarti helm terdeteksi, merah tanpa helm terdeteksi, dan kuning belum jelas. Chat jumlah membaca analisis tersimpan, sedangkan percakapan memakai Qwen3-1.7B dan adapter LoRA lokal bila tersedia. Upload menjalankan inferensi. Jeda video, koreksi kotak AI atau gambar kotak baru, lalu klik Simpan koreksi setelah semua objek pada posisi itu benar. Hitungan dashboard dan chat langsung memakai posisi yang disahkan; draft belum dihitung. Putar & ikuti kotak mengikuti gerakan tanpa training ulang. Latih untuk video lain adalah tindakan opsional terpisah dari minimal dua sumber berbeda; bobot model tidak berubah saat menyimpan koreksi. Kelas baru memerlukan contoh berlabel; training tidak menjamin akurasi. Kandidat helm perlu ditinjau dan belum divalidasi untuk pabrik.",
            "mode": "guide",
            "evidence": [],
            "source": "Kemampuan aplikasi versi awal",
        }
    terms = (*terms, *(name.lower() for name in names))
    if not any(
        re.search(
            r"\b"
            + re.escape(term)
            + (r"\b" if term in {"bus", "bis", "truk", "motor", "sepeda"} else r"\w*\b"),
            q,
        )
        for term in terms
    ):
        return None
    if any(term in q for term in ("plat", "wajah", "absen", "cctv")):
        return {
            "answer": "Versi ini menyediakan unggah video, tracking orang dan kendaraan dan deteksi helm. Pembacaan plat, identifikasi wajah, absensi, dan CCTV belum tersedia.",
            "mode": "guide",
            "evidence": [],
        }
    if (
        "helm" in q
        and any(term in q for term in ("pakai", "menggunakan"))
        and not any(term in q for term in ("tanpa", "tidak", "nggak", "gak", "belum", "kandidat"))
    ):
        return {
            "answer": "Hitungan pemakai helm per frame belum disimpan dalam versi ini. Video menampilkan prediksi warna, dan ringkasan menyimpan track kandidat tanpa helm. Jangan menganggap track lain otomatis memakai helm.",
            "mode": "guide",
            "evidence": [],
        }
    if summary is None:
        return {
            "answer": "Unggah dan selesaikan analisis video dahulu. Saya belum mempunyai data video untuk menjawab jumlah atau kejadian.",
            "mode": "facts",
            "evidence": [],
        }
    if any(
        term in q
        for term in (
            "hari ini",
            "kemarin",
            "besok",
            "tanggal",
            "minggu",
            "bulan",
            "antara",
            "rentang",
            "sampai",
        )
    ):
        return {
            "answer": "Versi ini menjawab keseluruhan video atau satu posisi detik, belum mendukung filter rentang/tanggal. Waktu perekaman tidak diketahui; waktu upload bukan waktu kejadian. Contoh: berapa orang pada detik 3, atau berapa orang melintas di video ini.",
            "mode": "facts",
            "evidence": [],
        }
    tracks = summary["tracks"]
    crossings = (
        summary.get("original_crossings", summary["crossings"]) if ai_only else summary["crossings"]
    )
    occupancy = summary["occupancy" if ai_only else "reviewed_occupancy"]
    candidates = [t for t in tracks if t["kind"] == "person" and t["helmet_candidate"]]
    requested = set()
    if re.search(r"\b(orang|pekerja|karyawan|manusia|person)\b", q):
        requested.add("person")
    for kind, pattern in {
        "car": r"\b(mobil|car)\b",
        "bus": r"\b(bus|bis)\b",
        "truck": r"\b(truk|truck)\b",
        "motorcycle": r"\b(motor|motorcycle)\b",
        "bicycle": r"\b(sepeda(?!\s+motor)|bicycle)\b",
    }.items():
        if re.search(pattern, q):
            requested.add(kind)
    for kind in names:
        if kind not in OBJECT_NAMES and re.search(r"\b" + re.escape(kind.lower()) + r"\b", q):
            requested.add(kind)
    if "kendaraan" in q:
        requested.update(k for k in OBJECT_NAMES if k != "person")
    available = (
        summary.get("object_classes", ["person", "car"]) if ai_only else summary["reviewed_classes"]
    )
    unsupported = requested - set(available)
    moment = re.search(r"detik\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*detik", q)
    manual_available = False
    if moment and not ai_only:
        seconds = float((moment[1] or moment[2]).replace(",", "."))
        if 0 <= seconds < summary["duration"]:
            frame = min(occupancy, key=lambda f: abs(f["seconds"] - seconds))
            manual_available = any(
                f["complete"] and abs(f["seconds"] - frame["seconds"]) < 0.01
                for f in summary.get("manual_frames", [])
            )
    if unsupported and not manual_available:
        return {
            "answer": "Analisis ini belum mencakup "
            + ", ".join(names[k] for k in names if k in unsupported)
            + ". Unggah ulang video untuk memakai kelas detector terbaru; hasil lama tetap tersimpan.",
            "mode": "guide",
            "evidence": [],
        }
    helmet_query = "helm" in q or "apd" in q
    if helmet_query or "siapa" in q:
        requested = {"person"}
    selected_tracks = [t for t in tracks if not requested or t["kind"] in requested]
    if helmet_query:
        selected_tracks = candidates
    used_review = False
    evidence = []
    for track in selected_tracks:
        key = "helmet_evidence" if helmet_query and "helmet_evidence" in track else "evidence"
        if key in track:
            evidence.append(
                {
                    "file": track[key],
                    "track_id": track["id"],
                    "kind": track["kind"],
                    "seconds": track["helmet_seconds"]
                    if key == "helmet_evidence"
                    else track["evidence_seconds"],
                    "status": track.get("evidence_status", track.get("status", "unknown")),
                }
            )
    if "bukti" in q:
        label = "/".join(names[k] for k in names if k in (requested or set(available)))
        text = f"Tersimpan {len(evidence)} foto bukti {label}. Setiap foto menandai ID track dan mencatat posisi detik di video. ID sementara bukan nama/identitas."
        if not evidence:
            text += " Analisis lama mungkin belum menyimpan foto track orang biasa; analisis ulang membuat bukti baru."
    elif "siapa" in q and "helm" not in q and "apd" not in q:
        people = [t["id"] for t in tracks if t["kind"] == "person"]
        text = (
            "Nama orang belum tersedia. ID track orang dalam video ini: "
            + ", ".join(f"#{i}" for i in people)
            + ". ID sementara bukan identitas karyawan."
        )
    elif "helm" in q or "apd" in q:
        descriptions = [
            f"ID #{t['id']} pada detik {t.get('helmet_seconds', t['evidence_seconds']):g}"
            for t in candidates
        ]
        text = (
            f"Ada {len(candidates)} track kandidat tanpa helm (deteksi konsisten minimal 2 detik). "
        )
        text += (
            "; ".join(descriptions) + "."
            if descriptions
            else "Tidak ada kandidat yang memenuhi aturan ini; hasil tersebut tidak membuktikan semua orang memakai helm."
        )
        text += " Hijau = helm terdeteksi; merah = tanpa helm terdeteksi; kuning = belum jelas. ID sementara tidak memberikan nama karyawan."
        evidence = [e for e in evidence if e["kind"] == "person"]
    else:
        kinds = [k for k in [*available, *sorted(unsupported)] if not requested or k in requested]
        label = " dan ".join(names[k] for k in kinds)
        offset = None
        match = re.search(r"detik\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*detik", q)
        stamp = re.search(r"\b(\d{1,2}):(\d{2})\b", q)
        if match:
            offset = float((match[1] or match[2]).replace(",", "."))
        elif stamp:
            offset = int(stamp[1]) * 60 + int(stamp[2])
        if offset is not None:
            if not 0 <= offset < summary["duration"]:
                text = (
                    f"Posisi waktu di luar video. Durasi video ini {summary['duration']:g} detik."
                )
            else:
                frame = min(occupancy, key=lambda f: abs(f["seconds"] - offset))
                manual = next(
                    (
                        f
                        for f in summary.get("manual_frames", [])
                        if f["complete"] and abs(f["seconds"] - frame["seconds"]) < 0.01
                    ),
                    None,
                )
                if manual and not ai_only:
                    counts = " dan ".join(
                        f"{sum(b['label'] == k for b in manual['boxes'])} {names[k]}" for k in kinds
                    )
                    return {
                        "answer": f"Pada detik {manual['seconds']:g}, koreksi manual mencatat {counts}. Ini anotasi pengguna pada satu frame; hasil AI asli tetap tersimpan.",
                        "mode": "manual",
                        "evidence": [],
                        "source": "annotations.json: frame selesai ditinjau",
                    }
                counts = " dan ".join(f"{frame.get(k, 0)} {names[k]}" for k in kinds)
                text = f"Pada detik {frame['seconds']:g}, terdeteksi {counts} yang terlihat. Ini jumlah pada frame tersebut."
        elif "lewat" in q or "lintas" in q:
            selected = [c for c in crossings if c["kind"] in kinds]
            up = sum(c["direction"] == "up" for c in selected)
            down = len(selected) - up
            text = f"Tercatat {len(selected)} lintasan {label} melewati garis horizontal: {up} ke atas, {down} ke bawah. Satu track dapat melintas lebih dari sekali; ini bukan jumlah individu unik."
        else:
            maxima = {k: max((f.get(k, 0) for f in occupancy), default=0) for k in kinds}
            if not requested:
                kinds = [k for k in kinds if maxima[k] > 0]
            peaks = " dan ".join(f"{maxima[k]} {names[k]}" for k in kinds)
            if requested:
                text = f"Maksimum {peaks} terlihat bersamaan dalam video {summary['duration']:g} detik."
            else:
                minutes, seconds = divmod(round(summary["duration"]), 60)
                duration = f"{minutes} menit {seconds} detik" if minutes else f"{seconds} detik"
                text = f"Rekaman ini berdurasi {duration}. "
                if len(kinds) == 1:
                    kind = kinds[0]
                    peak_at = next(
                        f["seconds"] for f in occupancy if f.get(kind, 0) == maxima[kind]
                    )
                    text += f"Maksimum {peaks} terlihat bersamaan, sekitar detik {peak_at:g}."
                elif kinds:
                    text += f"Jumlah tertinggi per kategori: {peaks}. Puncak tiap kategori bisa berada pada waktu berbeda."
                else:
                    text += "Belum ada objek yang tercatat pada frame analisis."
                if crossings:
                    text += f" Ada {len(crossings)} kejadian melintasi garis hitung."
                if candidates:
                    text += f" {len(candidates)} track kandidat tanpa helm perlu ditinjau."
            total_tracks = sum(t["kind"] in kinds for t in tracks)
            if total_tracks:
                text += (
                    f"\n\nTracker AI awal menghasilkan {total_tracks} ID sementara. Satu objek bisa berganti ID, sehingga angka ini bukan jumlah individu unik."
                    if requested
                    else " Jumlah individu unik belum dapat dipastikan karena ID dapat berganti."
                )
            status = summary["review_status"]
            used_review = not ai_only and status["saved_positions"] > 0
            if not ai_only and (status["saved_positions"] or status["draft_positions"]):
                if status["latest"]:
                    latest = status["latest"]
                    latest_kinds = (
                        kinds if requested else [k for k, n in latest["counts"].items() if n]
                    )
                    counts = (
                        " dan ".join(
                            f"{latest['counts'].get(k, 0)} {names.get(k, k)}" for k in latest_kinds
                        )
                        or "0 objek"
                    )
                    text += f"\n\nKoreksi terbaru: {counts} pada detik {latest['seconds']:g}."
                text += f" {status['saved_positions']} posisi disahkan; {status['draft_positions']} draft belum masuk hitungan. ID bukan identitas; lintasan mengikuti sumber hasil yang dipilih."
    evidence_limit = 3 if "ringkas" in q else 8
    if len(evidence) > evidence_limit:
        text += f"\n\n{evidence_limit} foto bukti ditampilkan; foto lainnya ada di Bukti & hasil."

    return {
        "answer": text,
        "mode": "reviewed" if used_review else "facts",
        "evidence": evidence[:evidence_limit],
        "source": "summary.json + annotations.json: koreksi objek lengkap pada posisi yang disahkan"
        if used_review
        else "summary.json: hasil AI asli",
    }


def _generate_once(message: str, history: list[dict], summary: dict | None, device: str) -> dict:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    global _model, _tokenizer, _loaded_device
    start = time.monotonic()
    adapter = CHAT_ADAPTER
    if _model is not None and _loaded_device != device:
        _model = None
        import gc

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    if _model is None:
        torch.set_num_threads(8)
        _tokenizer = AutoTokenizer.from_pretrained(CHAT_BASE, local_files_only=True)
        base = AutoModelForCausalLM.from_pretrained(
            CHAT_BASE,
            local_files_only=True,
            dtype=torch.bfloat16 if device.startswith("cuda") else torch.float32,
            attn_implementation="sdpa",
        )
        _model = (
            PeftModel.from_pretrained(base, adapter, local_files_only=True)
            if (adapter / "adapter_config.json").is_file()
            else base
        )
        cast(torch.nn.Module, _model).to(device)
        _loaded_device = device
        _model.eval()
    assert _model is not None and _tokenizer is not None
    context = "Kamu asisten percakapan berbahasa Indonesia. Jawab singkat, langsung, dan sesuai permintaan pengguna. Jangan mengubah topik ke analisis video bila tidak diminta."
    if summary and any(word in message.lower() for word in ("itu", "tadi", "rekaman", "hasil")):
        facts = answer_facts("ringkasan", summary)
        assert facts is not None
        context += "\nRingkasan data terverifikasi: " + facts["answer"]
    messages = [
        {"role": "system", "content": context},
        *history[-6:],
        {"role": "user", "content": message},
    ]
    inputs = _tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
        return_dict=True,
        return_tensors="pt",
    )
    from transformers.tokenization_utils_base import BatchEncoding

    if not isinstance(inputs, BatchEncoding):
        raise RuntimeError("Tokenizer did not return the requested tensor mapping.")  # noqa: TRY004
    if inputs["input_ids"].shape[1] > 1800:
        messages = [messages[0], messages[-1]]
        inputs = _tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=False,
            return_dict=True,
            return_tensors="pt",
        )
    if not isinstance(inputs, BatchEncoding):
        raise RuntimeError("Tokenizer did not return the requested tensor mapping.")  # noqa: TRY004
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.inference_mode():
        output = cast(
            torch.Tensor,
            _model.generate(  # ty: ignore[invalid-argument-type]  # Upstream AutoModel self protocol.
                **inputs,
                max_new_tokens=140,
                do_sample=True,
                temperature=0.7,
                top_p=0.8,
                top_k=20,
                pad_token_id=_tokenizer.eos_token_id,
                return_dict_in_generate=False,
            ),
        )
    decoded = _tokenizer.decode(output[0, inputs["input_ids"].shape[1] :], skip_special_tokens=True)
    if not isinstance(decoded, str):
        raise RuntimeError("Tokenizer did not return one decoded response.")  # noqa: TRY004
    text = decoded.strip()
    if not text:
        raise RuntimeError("Model menghasilkan respons kosong.")
    return {
        "answer": text,
        "mode": "lora" if (adapter / "adapter_config.json").is_file() else "base",
        "evidence": [],
        "seconds": round(time.monotonic() - start, 2),
        "source": "Qwen3-1.7B lokal",
        "truncated": output.shape[1] - inputs["input_ids"].shape[1] == 140,
    }


def generate_reply(
    message: str, history: list[dict], summary: dict | None, preference: str = "auto"
) -> dict:
    import gc

    import torch

    global _model, _loaded_device

    budget = 0.8 if _model is not None and str(_loaded_device).startswith("cuda") else 4.5
    device, reason = select_device(preference, budget)
    fallback = False
    try:
        reply = _generate_once(message, history, summary, device)
    except torch.cuda.OutOfMemoryError:
        if device == "cpu":
            raise
        _model = None
        _loaded_device = None
        fallback = True
    if fallback:
        gc.collect()
        torch.cuda.empty_cache()
        device, reason = "cpu", "VRAM habis saat chat; menggunakan CPU"
        reply = _generate_once(message, history, summary, device)
    reply.update(device=device, device_reason=reason)
    return reply
