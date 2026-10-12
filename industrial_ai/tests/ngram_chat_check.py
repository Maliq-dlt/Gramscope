"""Real N-gram retrieval and authenticated HTTP checks, without model loading."""

from __future__ import annotations

import math
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from access_fixture import AccessFixture
from fastapi.testclient import TestClient
from pydantic import ValidationError

import access
import app
import ngram_chat as chat
import runtime

for n in (1, 2, 3):
    for pair in chat.DEFAULT.pairs:
        reply = chat.retrieve(chat.ChatRequest(question=pair.question, n=n))
        assert reply["matched"] and reply["answer"] == pair.answer
        assert math.isclose(reply["trace"]["candidates"][0]["score"], 1, abs_tol=1e-12)
        candidate = reply["trace"]["candidates"][0]
        assert math.isclose(
            candidate["score"], sum(term["contribution"] for term in candidate["contributions"])
        )
        assert reply["dataset"]["sha256"] == chat.describe(chat.DEFAULT)["sha256"]
assert chat.retrieve(chat.ChatRequest(question="APA ITU N-GRAM?"))["matched"]
for text in ("ramalan cuaca mars besok", "apa yang itu", "123!!!", "bigram ramalan mars astronomi"):
    assert not chat.retrieve(chat.ChatRequest(question=text))["matched"]
custom = chat.Dataset(
    name="Manual toko",
    pairs=[
        chat.Pair(
            question="kapan toko buka", answer="Toko buka pukul 09.00.", source="Jadwal pemilik"
        ),
        chat.Pair(
            question="kapan toko tutup", answer="Toko tutup pukul 18.00.", source="Jadwal pemilik"
        ),
    ],
)
assert (
    chat.retrieve(chat.ChatRequest(question="toko buka", dataset=custom))["answer"]
    == custom.pairs[0].answer
)
ambiguous = chat.retrieve(chat.ChatRequest(question="kapan toko", dataset=custom))
assert not ambiguous["matched"] and ambiguous["reason"] == "ambiguous"
assert not chat.retrieve(chat.ChatRequest(question="toko buka"))["matched"]
for body in (
    {"name": "Empty", "pairs": []},
    {"name": "Duplicate", "pairs": [custom.pairs[0].model_dump()] * 2},
    {"name": "Control", "pairs": [{**custom.pairs[0].model_dump(), "answer": "bad\x00"}]},
    {"name": "Invalid", "pairs": [{"question": "!!!", "answer": "bad", "source": "test"}]},
):
    try:
        chat.Dataset.model_validate(body)
        raise AssertionError("Invalid corpus accepted")
    except ValidationError:
        pass
fixture = AccessFixture(runtime.ROOT / ".tmp" / ("ngram_chat_" + uuid4().hex))
runtime.JOBS = fixture.jobs
app.training_root = fixture.trainings
access._stores[access.database_path()] = fixture.store
with TestClient(app.app) as client:
    assert client.get("/api/ngram/chat/data").status_code == 401
    assert client.post("/api/ngram/chat", json={"question": "Apa itu bigram?"}).status_code == 401
    fixture.login(client, "viewer")
    data = client.get("/api/ngram/chat/data").json()
    assert data["summary"]["pairs"] == len(chat.DEFAULT.pairs)
    assert client.post("/api/ngram/chat/data", json=custom.model_dump()).status_code == 200
    assert client.get("/api/ngram/chat/data").json() == data, (
        "Custom corpus must not mutate shared data"
    )
    response = client.post(
        "/api/ngram/chat", json={"question": "toko buka", "dataset": custom.model_dump()}
    )
    assert response.status_code == 200 and response.json()["answer"] == custom.pairs[0].answer
    assert client.post("/api/ngram/chat", json={"question": " ", "n": 2}).status_code == 422
    for invalid in (0, 4, True, "2"):
        assert (
            client.post("/api/ngram/chat", json={"question": "bigram", "n": invalid}).status_code
            == 422
        )
    assert client.post("/api/ngram/chat/data", json={"name": "bad", "pairs": []}).status_code == 422
    assert (
        client.post("/api/ngram/chat", json={"question": "bigram", "model": "Qwen"}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/ngram/chat", json={"question": "bigram"}, headers={"X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )
assert "torch" not in sys.modules and "transformers" not in sys.modules
print(
    "PASS: 36 exact Q&A matches, trace math, no-match/ambiguity, custom data isolation, validation, viewer auth/CSRF, no LLM loads."
)
