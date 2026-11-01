"""Performance benchmark on a synthetic library (no Ollama needed).

    python scripts/benchmark.py --papers 500 --chunks 20

Builds a throw-away data directory with N papers (authors, tags, keywords, references,
page-aware chunks, FTS index and 768-dimension embeddings like nomic-embed-text), then
times the main API endpoints. Nothing touches your real library.
"""

import argparse
import hashlib
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.registry import AIServices  # noqa: E402
from app.ai.vector_index import to_blob  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import (  # noqa: E402
    Author,
    Chunk,
    ChunkEmbedding,
    Collection,
    Document,
    DocumentAuthor,
    DocumentStatus,
    DocumentType,
    Tag,
)
from app.services import search_service  # noqa: E402

DIM = 768
VOCAB = (
    "sleep memory spindle cortex hippocampus learning attention adolescents students survey "
    "randomised trial cohort regression bias sample participants consolidation recall emotion "
    "stress anxiety cognition screen light circadian melatonin insomnia apnea reaction accuracy "
    "performance measure scale validity reliability model network neural signal frequency band "
    "oscillation replay plasticity synapse dopamine reward motivation decision context design"
).split()


def embed(text: str) -> list[float]:
    vector = np.zeros(DIM, dtype=np.float32)
    for word in text.lower().split():
        bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM
        vector[bucket] += 1.0
    norm = float(np.linalg.norm(vector)) or 1.0
    return (vector / norm).tolist()


class BenchEmbedder:
    model = "bench-embed"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return embed(text)


def populate(session_factory, papers: int, chunks_per_paper: int, seed: int = 7) -> None:  # type: ignore[no-untyped-def]
    rng = random.Random(seed)
    with session_factory() as db:
        authors = [
            Author(full_name=f"Author {i}", normalized_name=f"author {i}")
            for i in range(papers // 2)
        ]
        tags = [Tag(name=f"topic {i}") for i in range(30)]
        collections = [Collection(name=f"Collection {i}") for i in range(10)]
        db.add_all(authors + tags + collections)
        db.flush()
        shared_refs = [f"Shared Reference {i}. Journal of Things. {2000 + i}." for i in range(200)]
        for p in range(papers):
            doc = Document(
                title=f"Study {p}: " + " ".join(rng.sample(VOCAB, 6)),
                doc_type=DocumentType.PDF,
                status=DocumentStatus.READY,
                ai_index_status="ready",
                publication_year=rng.randint(1995, 2025),
                abstract=" ".join(rng.choices(VOCAB, k=120)),
                keywords=rng.sample(VOCAB, 4),
                reference_list=rng.sample(shared_refs, 15),
                page_count=chunks_per_paper // 2,
                venue=f"Journal {rng.randint(1, 40)}",
            )
            doc.tags = rng.sample(tags, 3)
            doc.collections = rng.sample(collections, 1)
            db.add(doc)
            db.flush()
            for position, author in enumerate(rng.sample(authors, 3)):
                db.add(DocumentAuthor(document_id=doc.id, author_id=author.id, position=position))
            for c in range(chunks_per_paper):
                text = " ".join(rng.choices(VOCAB, k=160))
                chunk = Chunk(
                    document_id=doc.id,
                    chunk_index=c,
                    page_start=c // 2 + 1,
                    page_end=c // 2 + 1,
                    section="Results",
                    text=text,
                    char_count=len(text),
                )
                db.add(chunk)
                db.flush()
                db.add(
                    ChunkEmbedding(
                        chunk_id=chunk.id,
                        model=BenchEmbedder.model,
                        dim=DIM,
                        vector=to_blob(embed(text)),
                    )
                )
            db.flush()
            db.refresh(doc)
            search_service.refresh_document_index(db, doc)
            if p % 100 == 99:
                db.commit()
                print(f"  {p + 1} papers…", flush=True)
        db.commit()


def timed(client: TestClient, method: str, url: str, runs: int, **kwargs) -> tuple[float, float]:  # type: ignore[no-untyped-def]
    durations = []
    for _ in range(runs):
        start = time.perf_counter()
        response = client.request(method, url, **kwargs)
        durations.append((time.perf_counter() - start) * 1000)
        assert response.status_code < 400, (url, response.status_code, response.text[:200])
    return statistics.median(durations), max(durations)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers", type=int, default=500)
    parser.add_argument("--chunks", type=int, default=20)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(
            _env_file=None,
            data_dir=Path(tmp),
            run_background_worker=False,
            ollama_base_url="http://127.0.0.1:9",
            ollama_timeout_seconds=0.2,
        )
        ai = AIServices(embedder=BenchEmbedder(), chat_factories={})
        with TestClient(create_app(settings, ai=ai)) as client:
            print(f"Building {args.papers} papers × {args.chunks} chunks…")
            start = time.perf_counter()
            populate(client.app.state.session_factory, args.papers, args.chunks)  # type: ignore[attr-defined]
            print(f"Built in {time.perf_counter() - start:.1f}s\n")

            checks = [
                ("Dashboard", "GET", "/api/dashboard", {}),
                ("Library list (page 1)", "GET", "/api/documents", {}),
                (
                    "Library list, filtered by tag + year",
                    "GET",
                    "/api/documents",
                    {"params": {"tag": "topic 3", "year_from": 2010}},
                ),
                (
                    "Full-text search",
                    "GET",
                    "/api/documents",
                    {"params": {"q": "hippocampus replay"}},
                ),
                ("Library facets", "GET", "/api/library/facets", {}),
                (
                    "Hybrid retrieval (assistant)",
                    "POST",
                    "/api/assistant/retrieve",
                    {"json": {"query": "does sleep spindle density predict memory consolidation"}},
                ),
                ("Knowledge graph (all layers)", "GET", "/api/graph", {}),
                ("Citations (APA, whole library)", "GET", "/api/citations", {}),
                (
                    "BibTeX export (whole library)",
                    "GET",
                    "/api/citations/export",
                    {"params": {"format": "bibtex"}},
                ),
            ]
            print(f"{'Endpoint':<40} {'median':>9} {'max':>9}")
            for label, method, url, kwargs in checks:
                median, worst = timed(client, method, url, args.runs, **kwargs)
                print(f"{label:<40} {median:>7.0f}ms {worst:>7.0f}ms")


if __name__ == "__main__":
    main()
