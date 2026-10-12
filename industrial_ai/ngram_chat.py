"""Inspectable word N-gram retrieval over Q&A; no language model or generated answers."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from time import perf_counter
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

STOPWORDS = frozenset(
    [
        "apa",
        "apakah",
        "itu",
        "yang",
        "dan",
        "atau",
        "di",
        "ke",
        "dari",
        "untuk",
        "dengan",
        "saya",
        "kamu",
        "anda",
        "ini",
        "bagaimana",
        "jelaskan",
        "tentang",
        "tolong",
        "sebuah",
        "adalah",
        "bisa",
    ]
)
THRESHOLD = 0.24
MARGIN = 0.035


def tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"\bn[ -]+gram\b", "ngram", text)
    return re.findall(r"[^\W_]+", text, re.UNICODE)


def terms(text: str, n: int) -> Counter[str]:
    words = [word for word in tokens(text) if word not in STOPWORDS]
    return Counter(
        " ".join(words[i : i + order])
        for order in range(1, n + 1)
        for i in range(len(words) - order + 1)
    )


class Pair(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=6000)
    source: str = Field(min_length=1, max_length=160)

    @field_validator("question", "answer", "source")
    @classmethod
    def valid_text(cls, value: str) -> str:
        if any(unicodedata.category(c).startswith("C") and c not in "\n\t" for c in value):
            raise ValueError("Teks memuat karakter kontrol.")
        return value


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)
    pairs: list[Pair] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def valid_pairs(self):
        seen = set()
        for pair in self.pairs:
            question = tuple(tokens(pair.question))
            if not terms(pair.question, 1) or question in seen:
                raise ValueError("Pertanyaan harus berbeda dan memuat kata informatif.")
            seen.add(question)
        if sum(len(p.question) + len(p.answer) + len(p.source) for p in self.pairs) > 200_000:
            raise ValueError("Total teks dataset maksimal 200.000 karakter.")
        return self


# Authored learning corpus, visible and replaceable; not a measured benchmark.
DEFAULT = Dataset(
    name="Panduan N-gram · kurasi proyek",
    pairs=[
        Pair(
            question="Apa itu N-gram?",
            answer="N-gram adalah rangkaian n token yang berurutan. Unigram memakai satu token, bigram dua, dan trigram tiga. Chatbot ini mencocokkan rangkaian kata pada pertanyaan dengan pertanyaan di dataset Q&A.",
            source="Kurasi materi N-gram proyek",
        ),
        Pair(
            question="Apa itu unigram?",
            answer="Unigram memakai satu token. Urutan antarkata belum tercakup sehingga dua kalimat dengan kata yang sama dapat memiliki representasi yang sama.",
            source="Kurasi materi N-gram proyek",
        ),
        Pair(
            question="Apa itu bigram?",
            answer="Bigram memakai dua token berurutan, misalnya ‘model bahasa’. Pada chatbot ini, mode bigram menggabungkan fitur unigram dan bigram untuk mempertahankan kecocokan kata serta frasa.",
            source="Kurasi materi N-gram proyek",
        ),
        Pair(
            question="Apa itu trigram?",
            answer="Trigram memakai tiga token berurutan. Mode trigram di sini memakai fitur unigram, bigram, dan trigram. Frasa yang lebih panjang lebih spesifik, tetapi sensitif terhadap perubahan susunan kata.",
            source="Kurasi materi N-gram proyek",
        ),
        Pair(
            question="Bagaimana tokenisasi bekerja?",
            answer="Teks dinormalisasi dengan Unicode NFKC dan huruf kecil, lalu dipisahkan menjadi token huruf atau angka. Kata umum seperti ‘apa’ dan ‘yang’ dikeluarkan sebelum fitur N-gram dibuat.",
            source="ngram_chat.py · tokens / terms",
        ),
        Pair(
            question="Bagaimana TF IDF dihitung?",
            answer="Bobot TF adalah 1 + ln(frekuensi). IDF adalah 1 + ln((1 + jumlah pertanyaan)/(1 + jumlah pertanyaan yang memuat fitur)). Fitur yang jarang muncul di dataset mendapat bobot lebih besar.",
            source="ngram_chat.py · retrieve",
        ),
        Pair(
            question="Bagaimana skor kemiripan cosine dihitung?",
            answer="Vektor TF-IDF dinormalisasi dengan panjang Euclidean. Cosine adalah jumlah hasil kali bobot fitur yang sama. Nilai tinggi berarti pertanyaan lebih mirip secara leksikal; nilainya bukan probabilitas jawaban benar.",
            source="ngram_chat.py · retrieve",
        ),
        Pair(
            question="Mengapa jawaban tidak ditemukan?",
            answer="Chatbot menolak memilih jawaban jika skor tertinggi di bawah 0,24, cakupan kata dikenal di bawah 50%, atau dua jawaban berbeda terlalu berdekatan (selisih di bawah 0,035). Coba istilah yang ada di dataset atau impor Q&A yang relevan.",
            source="ngram_chat.py · aturan pemilihan",
        ),
        Pair(
            question="Apakah chatbot memakai LLM?",
            answer="Chatbot N-gram ini tidak memanggil LLM, Torch, Qwen, atau layanan AI. Ia menghitung fitur kata dan kemiripan, kemudian mengambil jawaban persis dari pasangan Q&A yang terpilih.",
            source="ngram_chat.py · retrieval",
        ),
        Pair(
            question="Bagaimana mengimpor dataset Q&A?",
            answer="Buka Data Q&A, unduh dataset untuk melihat format JSON, lalu ganti name dan pairs. Setiap pasangan memuat question, answer, dan source. Impor maksimal 200 pasangan dan 200.000 karakter teks. Dataset kustom hanya dipakai dalam sesi halaman ini; unduh agar tidak hilang saat halaman dimuat ulang.",
            source="frontend/NgramChat.tsx · data sesi",
        ),
        Pair(
            question="Apa itu perplexity?",
            answer="Perplexity adalah exp(cross entropy) untuk model bahasa probabilistik. Skor cosine retrieval Q&A bukan perplexity. Perhitungan perplexity tetap tersedia pada bagian Analisis & eksperimen N-gram.",
            source="academic.py · score_sentence",
        ),
        Pair(
            question="Apa isi log pencocokan?",
            answer="Log menampilkan token input, fitur N-gram, kata di luar kosakata, bobot IDF, kontribusi fitur, peringkat kandidat, ambang pemilihan, dan fingerprint dataset. Percakapan dan log berada di sesi halaman dan dapat diunduh sebagai JSON.",
            source="ngram_chat.py / frontend/NgramChat.tsx",
        ),
    ],
)


class Contribution(TypedDict):
    term: str
    contribution: float


class Candidate(TypedDict):
    index: int
    question: str
    score: float
    contributions: list[Contribution]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=2000)
    n: int = Field(default=2, ge=1, le=3, strict=True)
    dataset: Dataset | None = None


def describe(dataset: Dataset):
    encoded = json.dumps(dataset.model_dump(), ensure_ascii=False, sort_keys=True).encode()
    vocabulary = {word for pair in dataset.pairs for word in terms(pair.question, 1)}
    return {
        "name": dataset.name,
        "pairs": len(dataset.pairs),
        "vocabulary_size": len(vocabulary),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def retrieve(request: ChatRequest):
    started = perf_counter()
    dataset = request.dataset or DEFAULT
    documents = [terms(pair.question, request.n) for pair in dataset.pairs]
    df = Counter(word for document in documents for word in document)
    raw = terms(request.question, request.n)
    idf = {
        word: 1 + math.log((1 + len(documents)) / (1 + df.get(word, 0)))
        for word in set(df) | set(raw)
    }

    def vector(counts):
        values = {word: (1 + math.log(count)) * idf[word] for word, count in counts.items()}
        length = math.sqrt(sum(value * value for value in values.values()))
        return {word: value / length for word, value in values.items()} if length else {}

    query = vector(raw)
    ranked: list[Candidate] = []
    for index, document in enumerate(documents):
        candidate = vector(document)
        contributions: list[Contribution] = [
            {"term": word, "contribution": query[word] * candidate[word]}
            for word in query.keys() & candidate.keys()
        ]
        contributions.sort(key=lambda row: (-row["contribution"], row["term"]))
        ranked.append(
            {
                "index": index,
                "question": dataset.pairs[index].question,
                "score": sum(row["contribution"] for row in contributions),
                "contributions": contributions,
            }
        )
    ranked.sort(key=lambda row: (-row["score"], row["index"]))
    top = ranked[0]
    best = dataset.pairs[top["index"]]
    query_words = set(terms(request.question, 1))
    known = {word for word in df if " " not in word}
    coverage = len(query_words & known) / len(query_words) if query_words else 0
    rival = next(
        (row for row in ranked[1:] if dataset.pairs[row["index"]].answer != best.answer), None
    )
    gap = top["score"] - rival["score"] if rival else top["score"]
    matched = top["score"] >= THRESHOLD and coverage >= 0.5 and (rival is None or gap >= MARGIN)
    reason = (
        "matched"
        if matched
        else "low_coverage"
        if coverage < 0.5
        else "low_score"
        if top["score"] < THRESHOLD
        else "ambiguous"
    )
    return {
        "answer": best.answer
        if matched
        else "Belum ada jawaban yang cukup cocok di data Q&A. Coba pertanyaan lebih spesifik atau gunakan dataset yang memuat topik ini.",
        "matched": matched,
        "reason": reason,
        "source": best.source if matched else None,
        "selected_question": best.question if matched else None,
        "dataset": describe(dataset),
        "n": request.n,
        "trace": {
            "tokens": tokens(request.question),
            "features": [
                {"term": word, "count": count, "idf": idf[word], "weight": query[word]}
                for word, count in raw.items()
            ],
            "unknown_words": sorted(query_words - known),
            "coverage": coverage,
            "candidates": ranked[:3],
            "threshold": THRESHOLD,
            "margin": MARGIN,
            "gap": gap,
        },
        "elapsed_ms": (perf_counter() - started) * 1000,
    }


def install(app):
    @app.get("/api/ngram/chat/data")
    def data():
        return {"dataset": DEFAULT.model_dump(), "summary": describe(DEFAULT)}

    @app.post("/api/ngram/chat/data")
    def validate_data(dataset: Dataset):
        return {"dataset": dataset.model_dump(), "summary": describe(dataset)}

    app.post("/api/ngram/chat")(retrieve)
