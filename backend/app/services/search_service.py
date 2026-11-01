"""Full-text search over the library.

SQLite uses the FTS5 indexes created in migration 0002 (BM25 ranking, porter
stemming, snippets). Other databases fall back to a simple LIKE search.
"""

import re
from dataclasses import dataclass

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.models.library import Author, Chunk, Document, DocumentAuthor

# Control characters delimit highlighted terms in snippets. The frontend splits on
# them and renders plain text, so snippets can never inject markup.
HIGHLIGHT_START = "\x02"
HIGHLIGHT_END = "\x03"

# documents_fts column weights: title, authors, abstract, keywords.
DOCUMENT_WEIGHTS = (10.0, 6.0, 3.0, 5.0)
# Document-level matches count for more than a single passage match.
DOCUMENT_SCORE_BOOST = 1.5


@dataclass
class SearchHit:
    document_id: int
    score: float  # lower is better (BM25 convention)
    snippet: str | None = None
    page: int | None = None


def _is_sqlite(db: Session) -> bool:
    return db.get_bind().dialect.name == "sqlite"


def to_fts_query(query: str) -> str | None:
    """Turn free text into a safe FTS5 query: every term quoted, last term prefix-matched."""
    terms = re.findall(r"[\w][\w'’\-]*", query, flags=re.UNICODE)[:20]
    if not terms:
        return None
    quoted = ['"' + t.replace('"', '""') + '"' for t in terms]
    if len(terms[-1]) >= 2:
        quoted[-1] += "*"
    return " ".join(quoted)


def refresh_document_index(db: Session, document: Document) -> None:
    """(Re)write the document-level FTS row. Call after metadata changes."""
    if not _is_sqlite(db):
        return
    authors = " ".join(link.author.full_name for link in document.authors)
    db.execute(text("DELETE FROM documents_fts WHERE rowid = :id"), {"id": document.id})
    db.execute(
        text(
            "INSERT INTO documents_fts(rowid, title, authors, abstract, keywords) "
            "VALUES (:id, :title, :authors, :abstract, :keywords)"
        ),
        {
            "id": document.id,
            "title": document.title,
            "authors": authors,
            "abstract": document.abstract or "",
            "keywords": " ".join(document.keywords or []),
        },
    )


def search(db: Session, query: str, limit: int = 1000) -> list[SearchHit]:
    if not _is_sqlite(db):
        return _search_like(db, query, limit)
    fts_query = to_fts_query(query)
    if fts_query is None:
        return []

    hits: dict[int, SearchHit] = {}
    weights = ", ".join(str(w) for w in DOCUMENT_WEIGHTS)
    for doc_id, score in db.execute(
        text(
            f"SELECT rowid, bm25(documents_fts, {weights}) AS score FROM documents_fts "
            "WHERE documents_fts MATCH :q ORDER BY score LIMIT :limit"
        ),
        {"q": fts_query, "limit": limit},
    ):
        hits[doc_id] = SearchHit(doc_id, score * DOCUMENT_SCORE_BOOST)

    chunk_rows = db.execute(
        text(
            "SELECT c.document_id, c.page_start, "
            "snippet(chunks_fts, 0, :hs, :he, ' … ', 28) AS snip, bm25(chunks_fts) AS score "
            "FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid "
            "WHERE chunks_fts MATCH :q ORDER BY score LIMIT :limit"
        ),
        {"q": fts_query, "limit": limit * 4, "hs": HIGHLIGHT_START, "he": HIGHLIGHT_END},
    )
    for doc_id, page, snip, score in chunk_rows:
        hit = hits.get(doc_id)
        if hit is None:
            hits[doc_id] = SearchHit(doc_id, score, snip, page)
        else:
            if hit.snippet is None:  # best passage for a document matched on metadata
                hit.snippet, hit.page = snip, page
            hit.score = min(hit.score, score)
    return sorted(hits.values(), key=lambda h: h.score)[:limit]


def _search_like(db: Session, query: str, limit: int) -> list[SearchHit]:
    terms = [t for t in query.split() if t][:10]
    if not terms:
        return []
    doc_conditions = []
    for term in terms:
        like = f"%{term}%"
        doc_conditions.append(
            or_(
                Document.title.ilike(like),
                Document.abstract.ilike(like),
                Document.id.in_(select(Chunk.document_id).where(Chunk.text.ilike(like))),
                Document.id.in_(
                    select(DocumentAuthor.document_id)
                    .join(Author)
                    .where(Author.full_name.ilike(like))
                ),
            )
        )
    ids = db.scalars(select(Document.id).where(*doc_conditions).limit(limit))
    return [SearchHit(doc_id, float(rank)) for rank, doc_id in enumerate(ids)]
