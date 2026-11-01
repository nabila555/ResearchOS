"""Turn library documents into citation data and formatted bibliographies."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.citations import CitationData, Style, bibliography, parse_name, to_bibtex, to_ris
from app.models.library import Document, DocumentAuthor, DocumentType
from app.services.errors import InvalidRequestError


def citation_data(doc: Document) -> CitationData:
    if doc.venue:
        kind = "article"
    elif doc.doc_type is DocumentType.WEB:
        kind = "web"
    else:
        kind = "document"
    return CitationData(
        id=doc.id,
        kind=kind,
        title=doc.title,
        authors=[parse_name(link.author.full_name) for link in doc.authors],
        year=doc.publication_year,
        venue=doc.venue,
        volume=doc.volume,
        issue=doc.issue,
        pages=doc.pages,
        publisher=doc.publisher,
        doi=doc.doi,
        url=doc.source_url,
        # For web sources the import date is the date the page was accessed.
        accessed=doc.created_at if doc.doc_type is DocumentType.WEB else None,
    )


def load(db: Session, document_ids: list[int] | None = None) -> list[CitationData]:
    """Citable documents (notes are excluded) in the requested order."""
    stmt = (
        select(Document)
        .where(Document.doc_type != DocumentType.NOTE)
        .options(selectinload(Document.authors).selectinload(DocumentAuthor.author))
    )
    if document_ids is not None:
        stmt = stmt.where(Document.id.in_(document_ids))
    docs = {d.id: d for d in db.scalars(stmt)}
    order = document_ids if document_ids is not None else sorted(docs)
    return [citation_data(docs[i]) for i in order if i in docs]


def formatted(db: Session, style: Style, document_ids: list[int] | None) -> list[dict]:
    items = bibliography(load(db, document_ids), style)
    return [
        {
            "document_id": data.id,
            "number": index + 1 if style == "ieee" else None,
            "text": f.text,
            "markdown": f.markdown,
            "parts": [{"text": t, "italic": i} for t, i in f.parts],
            "missing": f.missing,
            "kind": data.kind,
        }
        for index, (data, f) in enumerate(items)
    ]


def export(
    db: Session, fmt: str, style: Style, document_ids: list[int] | None
) -> tuple[str, str, str]:
    """Return (content, media type, file extension)."""
    items = load(db, document_ids)
    if fmt == "bibtex":
        return to_bibtex(items), "application/x-bibtex", "bib"
    if fmt == "ris":
        return to_ris(items), "application/x-research-info-systems", "ris"
    if fmt in ("markdown", "text"):
        entries = bibliography(items, style)
        lines = [
            (f"[{i + 1}] " if style == "ieee" else "")
            + (f.markdown if fmt == "markdown" else f.text)
            for i, (_, f) in enumerate(entries)
        ]
        joiner = "\n\n" if fmt == "markdown" else "\n"
        header = "# References\n\n" if fmt == "markdown" else ""
        return (
            header + joiner.join(lines) + "\n",
            "text/markdown" if fmt == "markdown" else "text/plain",
            "md" if fmt == "markdown" else "txt",
        )
    raise InvalidRequestError(f"Unknown export format “{fmt}”.")
