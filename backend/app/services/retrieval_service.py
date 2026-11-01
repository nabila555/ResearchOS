"""Hybrid passage retrieval for the assistant.

Semantic matches (local embeddings, cosine similarity) and keyword matches
(SQLite FTS5, BM25) are merged with Reciprocal Rank Fusion, limited per document
for diversity, and trimmed to a character budget so they fit the model context.
If embeddings are unavailable, retrieval degrades to keyword search and says so.
"""

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import exists, select, text
from sqlalchemy.orm import Session, selectinload

from app.ai.providers import ProviderError
from app.ai.registry import AIServices
from app.ai.vector_index import VectorIndex
from app.core.config import Settings
from app.models.library import Chunk, Document, DocumentAuthor, collection_documents
from app.models.project import project_documents
from app.services.search_service import to_fts_query

CANDIDATES_PER_METHOD = 40
MAX_PASSAGES_PER_DOCUMENT = 3
RRF_K = 60

# Function words are dropped from keyword queries so that an unrelated question
# ("what is the capital of France?") doesn't match every passage containing "the".
STOP_WORDS = frozenset(
    """a about above after again against all am an and any are as at be because been before
    being below between both but by can could did do does doing down during each few for from
    further had has have having he her here hers him his how i if in into is it its itself just
    me more most my no nor not now of off on once only or other our ours out over own same she
    should so some such than that the their theirs them then there these they this those through
    to too under until up very was we were what when where which while who whom why will with
    would you your yours tell explain describe give list show find papers paper study studies
    research document documents say says said according main""".split()
)


@dataclass
class Scope:
    collection_id: int | None = None
    project_id: int | None = None
    document_ids: list[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Scope":
        data = data or {}
        return cls(
            collection_id=data.get("collection_id"),
            project_id=data.get("project_id"),
            document_ids=list(data.get("document_ids") or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in (None, [])}

    def document_filter(self, db: Session) -> set[int] | None:
        """Allowed document ids, or None for the whole library."""
        if not (self.collection_id or self.project_id or self.document_ids):
            return None
        stmt = select(Document.id)
        if self.collection_id:
            stmt = stmt.where(
                exists()
                .where(collection_documents.c.document_id == Document.id)
                .where(collection_documents.c.collection_id == self.collection_id)
            )
        if self.project_id:
            stmt = stmt.where(
                exists()
                .where(project_documents.c.document_id == Document.id)
                .where(project_documents.c.project_id == self.project_id)
            )
        if self.document_ids:
            stmt = stmt.where(Document.id.in_(self.document_ids))
        return set(db.scalars(stmt))


@dataclass
class Passage:
    n: int
    chunk_id: int
    document_id: int
    title: str
    authors: list[str]
    year: int | None
    page_start: int | None
    page_end: int | None
    section: str | None
    text: str
    score: float
    semantic_similarity: float | None


@dataclass
class RetrievalResult:
    passages: list[Passage]
    semantic: bool
    notes: list[str]


def _keyword_hits(db: Session, query: str, allowed: set[int] | None, limit: int) -> list[int]:
    content_words = [w for w in re.findall(r"[\w'’\-]+", query.lower()) if w not in STOP_WORDS]
    fts_query = to_fts_query(" ".join(content_words))
    if fts_query is None or db.get_bind().dialect.name != "sqlite":
        return []
    # OR the terms: a passage need not contain every word of a natural-language question.
    fts_query = " OR ".join(fts_query.split(" "))
    rows = db.execute(
        text(
            "SELECT c.id, c.document_id FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid "
            "WHERE chunks_fts MATCH :q ORDER BY bm25(chunks_fts) LIMIT :limit"
        ),
        {"q": fts_query, "limit": limit * 5 if allowed is not None else limit},
    ).all()
    hits = [chunk_id for chunk_id, doc_id in rows if allowed is None or doc_id in allowed]
    return hits[:limit]


def retrieve(
    db: Session,
    ai: AIServices,
    index: VectorIndex,
    settings: Settings,
    query: str,
    scope: Scope | None = None,
    top_k: int | None = None,
) -> RetrievalResult:
    scope = scope or Scope()
    top_k = top_k or settings.retrieval_top_k
    allowed = scope.document_filter(db)
    notes: list[str] = []
    if allowed is not None and not allowed:
        return RetrievalResult([], False, ["The selected scope contains no documents."])

    semantic_scores: dict[int, float] = {}
    semantic_rank: list[int] = []
    semantic = False
    model = ai.embedder.model
    if index.size(db, model) == 0:
        notes.append("No documents are indexed for semantic search yet; using keyword search.")
    else:
        try:
            query_vector = ai.embedder.embed_query(query)
            hits = index.search(
                db,
                model,
                query_vector,
                CANDIDATES_PER_METHOD,
                document_ids=allowed,
                min_similarity=settings.retrieval_min_similarity,
            )
            semantic = True
            semantic_rank = [chunk_id for chunk_id, _ in hits]
            semantic_scores = dict(hits)
        except ProviderError as exc:
            notes.append(f"Semantic search unavailable ({exc}); using keyword search only.")

    keyword_rank = _keyword_hits(db, query, allowed, CANDIDATES_PER_METHOD)

    fused: dict[int, float] = {}
    for ranking in (semantic_rank, keyword_rank):
        for rank, chunk_id in enumerate(ranking):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
    if not fused:
        return RetrievalResult([], semantic, notes)

    ordered = sorted(fused, key=lambda cid: fused[cid], reverse=True)
    chunks = {
        c.id: c
        for c in db.scalars(
            select(Chunk)
            .where(Chunk.id.in_(ordered))
            .options(
                selectinload(Chunk.document)
                .selectinload(Document.authors)
                .selectinload(DocumentAuthor.author)
            )
        )
    }

    passages: list[Passage] = []
    per_document: dict[int, int] = {}
    budget = settings.retrieval_max_chars
    for chunk_id in ordered:
        chunk = chunks.get(chunk_id)
        if chunk is None:
            continue
        if per_document.get(chunk.document_id, 0) >= MAX_PASSAGES_PER_DOCUMENT:
            continue
        if len(chunk.text) > budget and passages:
            continue
        doc = chunk.document
        passages.append(
            Passage(
                n=len(passages) + 1,
                chunk_id=chunk.id,
                document_id=doc.id,
                title=doc.title,
                authors=[link.author.full_name for link in doc.authors],
                year=doc.publication_year,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                section=chunk.section,
                text=chunk.text,
                score=round(fused[chunk_id], 5),
                semantic_similarity=(
                    round(semantic_scores[chunk_id], 4) if chunk_id in semantic_scores else None
                ),
            )
        )
        per_document[chunk.document_id] = per_document.get(chunk.document_id, 0) + 1
        budget -= len(chunk.text)
        if len(passages) >= top_k or budget <= 0:
            break
    return RetrievalResult(passages, semantic, notes)
