"""Tests for indexing, retrieval, and the citation-verified assistant (fake providers)."""

import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.ai.anthropic_provider import AnthropicChatProvider
from app.ai.ollama import OllamaChatProvider, OllamaEmbeddingProvider
from app.ai.providers import (
    ChatTurn,
    ModelNotInstalledError,
    ProviderError,
    ProviderUnavailableError,
    RefusalError,
)
from app.ai.registry import AIServices
from app.ai.vector_index import VectorIndex, to_blob
from app.core.config import Settings
from app.models.ai import ChunkEmbedding, IndexJob
from app.services import indexing_service
from app.services.assistant_service import INSUFFICIENT_PHRASE, parse_citations
from tests.fixtures.fake_ai import FakeChat, make_fake_ai

SLEEP_NOTE = (
    "Sleep spindles predict overnight memory consolidation. In 48 adults, spindle density "
    "during slow-wave sleep correlated with recall of word pairs."
)
CORAL_NOTE = "Coral reefs bleach when ocean water temperatures rise for several weeks."


def note(client: TestClient, title: str, body: str, **extra) -> dict:  # type: ignore[no-untyped-def]
    response = client.post("/api/documents/notes", json={"title": title, "body": body, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def run_indexer(client: TestClient) -> None:
    state = client.app.state  # type: ignore[attr-defined]
    while indexing_service.process_next(state.session_factory, state.ai):
        pass


def ask(client: TestClient, session_id: int, content: str, **extra) -> list[dict]:  # type: ignore[no-untyped-def]
    response = client.post(
        f"/api/assistant/sessions/{session_id}/messages", json={"content": content, **extra}
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def new_session(client: TestClient, **body) -> int:  # type: ignore[no-untyped-def]
    response = client.post("/api/assistant/sessions", json=body)
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def library(client: TestClient) -> dict[str, dict]:
    docs = {
        "sleep": note(client, "Spindles and memory", SLEEP_NOTE),
        "coral": note(client, "Reef notes", CORAL_NOTE),
    }
    run_indexer(client)
    return docs


# --- Indexing ------------------------------------------------------------------------


def test_import_queues_index_job_and_worker_embeds(client: TestClient) -> None:
    doc = note(client, "Spindles", SLEEP_NOTE)
    assert doc["ai_index_status"] == "pending"
    run_indexer(client)
    assert client.get(f"/api/documents/{doc['id']}").json()["ai_index_status"] == "ready"
    index = client.get("/api/assistant/status").json()["index"]
    assert index["ready"] == 1 and index["pending"] == 0
    assert index["chunks_embedded"] == index["chunks_total"] > 0


def test_unavailable_embedder_keeps_jobs_pending(client: TestClient, ai: AIServices) -> None:
    doc = note(client, "Spindles", SLEEP_NOTE)
    ai.embedder.available = False  # type: ignore[attr-defined]
    state = client.app.state  # type: ignore[attr-defined]
    with pytest.raises(ProviderUnavailableError):
        indexing_service.process_next(state.session_factory, state.ai)
    assert client.get(f"/api/documents/{doc['id']}").json()["ai_index_status"] == "pending"
    with state.session_factory() as db:
        job = db.scalar(select(IndexJob))
        assert job.status == "pending" and job.attempts == 0  # waiting is not an attempt
    ai.embedder.available = True  # type: ignore[attr-defined]
    run_indexer(client)
    assert client.get(f"/api/documents/{doc['id']}").json()["ai_index_status"] == "ready"


def test_note_edit_requeues_and_delete_removes_embeddings(client: TestClient) -> None:
    doc = note(client, "Spindles", SLEEP_NOTE)
    run_indexer(client)
    edited = client.patch(f"/api/documents/{doc['id']}", json={"note_body": CORAL_NOTE}).json()
    assert edited["ai_index_status"] == "pending"
    run_indexer(client)
    state = client.app.state  # type: ignore[attr-defined]
    with state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ChunkEmbedding)) == 1
    client.delete(f"/api/documents/{doc['id']}")
    with state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ChunkEmbedding)) == 0


def test_reindex_endpoint(client: TestClient) -> None:
    doc = note(client, "Spindles", SLEEP_NOTE)
    run_indexer(client)
    assert client.post("/api/assistant/reindex", json={}).json()["queued"] == 0
    assert (
        client.post("/api/assistant/reindex", json={"document_ids": [doc["id"], 999]}).json()[
            "queued"
        ]
        == 1
    )
    # A second request while the job is pending doesn't duplicate it.
    assert (
        client.post("/api/assistant/reindex", json={"document_ids": [doc["id"]]}).json()["queued"]
        == 0
    )


# --- Retrieval -------------------------------------------------------------------------


def test_retrieve_hybrid_and_scoped(client: TestClient, library: dict[str, dict]) -> None:
    result = client.post(
        "/api/assistant/retrieve", json={"query": "How do spindles relate to recall?"}
    ).json()
    assert result["semantic"] is True
    assert result["passages"][0]["document_id"] == library["sleep"]["id"]
    assert result["passages"][0]["n"] == 1

    collection = client.post("/api/collections", json={"name": "Reefs"}).json()
    client.put(
        f"/api/documents/{library['coral']['id']}/collections", json={"ids": [collection["id"]]}
    )
    scoped = client.post(
        "/api/assistant/retrieve",
        json={"query": "spindles recall", "scope": {"collection_id": collection["id"]}},
    ).json()
    assert all(p["document_id"] == library["coral"]["id"] for p in scoped["passages"])


def test_retrieve_falls_back_to_keywords_without_embeddings(client: TestClient) -> None:
    note(client, "Spindles", SLEEP_NOTE)  # not indexed
    result = client.post("/api/assistant/retrieve", json={"query": "spindle density"}).json()
    assert result["semantic"] is False
    assert any("keyword" in n for n in result["notes"])
    assert len(result["passages"]) == 1


def test_vector_index_reloads_after_changes(client: TestClient) -> None:
    state = client.app.state  # type: ignore[attr-defined]
    index = VectorIndex()
    with state.session_factory() as db:
        assert index.size(db, "fake-embed") == 0
    note(client, "Spindles", SLEEP_NOTE)
    run_indexer(client)
    with state.session_factory() as db:
        hits = index.search(db, "fake-embed", state.ai.embedder.embed_query("spindles"), 5)
        assert hits and hits[0][1] > 0
        # Wrong dimension (e.g. embedding model changed) returns nothing instead of crashing.
        assert index.search(db, "fake-embed", [1.0, 0.0], 5) == []


def test_to_blob_roundtrip() -> None:
    import numpy as np

    from app.ai.vector_index import from_blob

    assert np.allclose(from_blob(to_blob([0.5, -1.25, 3.0])), [0.5, -1.25, 3.0])


# --- Answers ------------------------------------------------------------------------------


def test_answer_streams_and_verifies_citations(
    client: TestClient, ai: AIServices, library: dict
) -> None:
    chat: FakeChat = ai.chat("ollama")  # type: ignore[assignment]
    chat.reply = lambda _s, _t: "Spindle density predicted recall [1]. Some say otherwise [7]."
    session_id = new_session(client)
    events = ask(client, session_id, "What do spindles predict?")

    assert [e["type"] for e in events[:2]] == ["user_message", "sources"]
    assert events[-1]["type"] == "done"
    deltas = "".join(e["text"] for e in events if e["type"] == "delta")
    assert deltas == "Spindle density predicted recall [1]. Some say otherwise [7]."
    message = events[-1]["message"]
    assert message["status"] == "complete"
    assert message["cited"] == [1] and message["invalid_citations"] == [7]
    assert message["grounded"] is True
    assert any("[7]" in n for n in message["notes"])
    assert message["sources"][0]["document_id"] == library["sleep"]["id"]

    # The model saw the strict rules and numbered sources.
    system, turns = chat.calls[-1]
    assert "ONLY the numbered source passages" in system
    assert INSUFFICIENT_PHRASE in system
    assert "[1] “Spindles and memory”" in turns[-1].content
    assert turns[-1].content.endswith("Question: What do spindles predict?")

    detail = client.get(f"/api/assistant/sessions/{session_id}").json()
    assert detail["title"] == "What do spindles predict?"
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]


def test_unrelated_question_is_declined_without_calling_the_model(
    client: TestClient, ai: AIServices, library: dict
) -> None:
    chat: FakeChat = ai.chat("ollama")  # type: ignore[assignment]
    events = ask(client, new_session(client), "What is the capital of France?")
    message = events[-1]["message"]
    assert message["status"] == "insufficient_evidence"
    assert message["content"].startswith(INSUFFICIENT_PHRASE)
    assert message["sources"] == []
    assert chat.calls == []


def test_uncited_answer_is_flagged(client: TestClient, ai: AIServices, library: dict) -> None:
    ai.chat("ollama").reply = lambda _s, _t: "Spindles are important for memory."  # type: ignore[attr-defined]
    message = ask(client, new_session(client), "spindles memory?")[-1]["message"]
    assert message["grounded"] is False
    assert any("unverified" in n for n in message["notes"])


def test_model_reported_insufficient_evidence(
    client: TestClient, ai: AIServices, library: dict
) -> None:
    ai.chat("ollama").reply = lambda _s, _t: (
        f"{INSUFFICIENT_PHRASE} The sources do not report sample ages."
    )  # type: ignore[attr-defined]
    message = ask(client, new_session(client), "How old were the spindle participants?")[-1][
        "message"
    ]
    assert message["status"] == "insufficient_evidence"


def test_provider_error_mid_stream_is_reported(
    client: TestClient, ai: AIServices, library: dict
) -> None:
    ai.chat("ollama").error = ProviderError("The local model took too long to respond.")  # type: ignore[attr-defined]
    events = ask(client, new_session(client), "spindles?")
    assert events[-1]["type"] == "error"
    assert events[-1]["message"] == "The local model took too long to respond."
    assert events[-1]["chat_message"]["status"] == "error"


def test_history_is_sent_without_old_citation_markers(
    client: TestClient, ai: AIServices, library: dict
) -> None:
    chat: FakeChat = ai.chat("ollama")  # type: ignore[assignment]
    session_id = new_session(client)
    ask(client, session_id, "What do spindles predict?")
    ask(client, session_id, "And in how many adults?")
    _, turns = chat.calls[-1]
    assert [t.role for t in turns] == ["user", "assistant", "user"]
    assert turns[0].content == "What do spindles predict?"
    assert "[1]" not in turns[1].content


def test_scope_override_on_question(client: TestClient, ai: AIServices, library: dict) -> None:
    session_id = new_session(client)
    events = ask(client, session_id, "spindles", scope={"document_ids": [library["coral"]["id"]]})
    assert all(s["document_id"] == library["coral"]["id"] for s in events[1]["sources"])
    assert client.get(f"/api/assistant/sessions/{session_id}").json()["scope"] == {
        "document_ids": [library["coral"]["id"]]
    }


# --- Cloud consent ---------------------------------------------------------------------------


@pytest.fixture
def cloud_client(settings: Settings):  # type: ignore[no-untyped-def]
    from app.main import create_app

    cloud = FakeChat(name="anthropic", model="claude-opus-5-5")
    with TestClient(create_app(settings, ai=make_fake_ai(cloud=cloud))) as test_client:
        yield test_client, cloud


def test_cloud_provider_requires_explicit_consent(cloud_client) -> None:  # type: ignore[no-untyped-def]
    client, cloud = cloud_client
    note(client, "Spindles", SLEEP_NOTE)
    run_indexer(client)
    status = client.put("/api/assistant/settings", json={"chat_provider": "anthropic"}).json()
    assert status["chat_provider"] == "anthropic" and status["cloud_consent"] is False
    assert {p["name"]: p["cloud"] for p in status["providers"]} == {
        "ollama": False,
        "anthropic": True,
    }

    session_id = new_session(client)
    blocked = client.post(
        f"/api/assistant/sessions/{session_id}/messages", json={"content": "spindles?"}
    )
    assert blocked.status_code == 409
    assert cloud.calls == []

    client.put("/api/assistant/settings", json={"cloud_consent": True})
    message = ask(client, session_id, "spindles?")[-1]["message"]
    assert message["provider"] == "anthropic" and message["model"] == "claude-opus-5-5"
    assert any("sent to Claude API" in n for n in message["notes"])
    assert len(cloud.calls) == 1


def test_unconfigured_provider_is_rejected(client: TestClient) -> None:
    client.put(
        "/api/assistant/settings", json={"chat_provider": "anthropic", "cloud_consent": True}
    )
    response = client.post(
        f"/api/assistant/sessions/{new_session(client)}/messages", json={"content": "x"}
    )
    assert response.status_code == 400
    assert "not configured" in response.json()["detail"]


def test_session_crud(client: TestClient) -> None:
    session_id = new_session(client, title="Thesis questions")
    assert (
        client.patch(f"/api/assistant/sessions/{session_id}", json={"title": "Renamed"}).json()[
            "title"
        ]
        == "Renamed"
    )
    assert [s["id"] for s in client.get("/api/assistant/sessions").json()] == [session_id]
    assert client.delete(f"/api/assistant/sessions/{session_id}").status_code == 204
    assert client.get(f"/api/assistant/sessions/{session_id}").status_code == 404


# --- Citation parsing -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("A [1]. B [2, 3]. C [1][4].", [1, 2, 3, 4]),
        ("Range [4–6] and [8-9].", [4, 5, 6, 8, 9]),
        ("No citations here.", []),
        ("Weird [a] [ 2 ] [1;3]", [2, 1, 3]),
    ],
)
def test_parse_citations(answer: str, expected: list[int]) -> None:
    assert parse_citations(answer) == expected


# --- Provider adapters ---------------------------------------------------------------------------


def _ollama_settings(**overrides) -> Settings:  # type: ignore[no-untyped-def]
    return Settings(_env_file=None, ollama_base_url="http://ollama.test", **overrides)


def test_ollama_chat_streams_ndjson() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["messages"][0] == {"role": "system", "content": "SYS"}
        assert body["options"]["temperature"] == 0.1
        lines = [
            {"message": {"content": "Hello "}, "done": False},
            {"message": {"content": "world"}, "done": False},
            {"message": {"content": ""}, "done": True},
        ]
        return httpx.Response(200, content="\n".join(json.dumps(x) for x in lines).encode())

    provider = OllamaChatProvider(_ollama_settings(), transport=httpx.MockTransport(handler))
    assert (
        "".join(provider.stream_chat("SYS", [ChatTurn("user", "hi")], max_tokens=10))
        == "Hello world"
    )


def test_ollama_missing_model_and_offline() -> None:
    missing = httpx.MockTransport(lambda r: httpx.Response(404, json={"error": "model not found"}))
    with pytest.raises(ModelNotInstalledError, match="ollama pull"):
        list(
            OllamaChatProvider(_ollama_settings(), transport=missing).stream_chat(
                "s", [], max_tokens=5
            )
        )

    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(ProviderUnavailableError):
        OllamaEmbeddingProvider(
            _ollama_settings(), transport=httpx.MockTransport(offline)
        ).embed_query("x")


def test_ollama_embedding_uses_nomic_task_prefixes() -> None:
    seen: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        texts = json.loads(request.content)["input"]
        seen.append(texts)
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2]] * len(texts)})

    provider = OllamaEmbeddingProvider(_ollama_settings(), transport=httpx.MockTransport(handler))
    provider.embed_documents(["a", "b"])
    provider.embed_query("q")
    assert seen == [["search_document: a", "search_document: b"], ["search_query: q"]]


class _FakeStream:
    def __init__(self, texts: list[str], stop_reason: str) -> None:
        self.text_stream = iter(texts)
        self._stop_reason = stop_reason

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, *_exc) -> None:  # type: ignore[no-untyped-def]
        return None

    def get_final_message(self):  # type: ignore[no-untyped-def]
        return SimpleNamespace(stop_reason=self._stop_reason)


def _fake_anthropic(texts: list[str], stop_reason: str, captured: dict):  # type: ignore[no-untyped-def]
    def stream(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return _FakeStream(texts, stop_reason)

    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))


def test_anthropic_provider_request_shape_and_refusal() -> None:
    settings = Settings(_env_file=None, anthropic_api_key="test-key")
    captured: dict = {}
    provider = AnthropicChatProvider(
        settings, client=_fake_anthropic(["Hi ", "there"], "end_turn", captured)
    )  # type: ignore[arg-type]
    assert (
        "".join(provider.stream_chat("SYS", [ChatTurn("user", "q")], max_tokens=100)) == "Hi there"
    )
    assert captured["model"] == "claude-opus-5-5"
    assert captured["system"] == "SYS"
    assert captured["fallbacks"] == "default"
    assert captured["betas"] == ["server-side-fallback-2026-07-01"]
    assert "temperature" not in captured

    refusing = AnthropicChatProvider(settings, client=_fake_anthropic(["partial"], "refusal", {}))  # type: ignore[arg-type]
    with pytest.raises(RefusalError):
        list(refusing.stream_chat("SYS", [ChatTurn("user", "q")], max_tokens=100))


def test_anthropic_provider_requires_key() -> None:
    with pytest.raises(ProviderError):
        AnthropicChatProvider(Settings(_env_file=None, anthropic_api_key=None))
