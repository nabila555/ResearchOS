"""Import, organise, edit, list, and delete library documents."""

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import httpx
from sqlalchemy import delete, exists, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.document_processing import storage
from app.document_processing.chunking import chunk_pages
from app.document_processing.extractors import (
    extract,
    extract_html,
    extract_plain_text,
    finalize,
)
from app.document_processing.metadata import find_doi
from app.document_processing.types import ExtractedDocument, ExtractedPage, ExtractionError
from app.document_processing.validation import (
    MIME_TYPES,
    check_size,
    detect_type,
    sanitize_filename,
    verify_content,
)
from app.document_processing.web import Resolver, fetch_url, resolve_host
from app.models.library import (
    Author,
    Chunk,
    Collection,
    Document,
    DocumentAuthor,
    DocumentStatus,
    DocumentType,
    Tag,
    collection_documents,
    document_tags,
)
from app.models.project import Project, project_documents
from app.schemas.library import (
    AttachmentOptions,
    ChunkPage,
    ChunkRead,
    CollectionRef,
    DocumentDetail,
    DocumentPage,
    DocumentSummary,
    DocumentUpdate,
    NoteCreate,
    ProjectRef,
    SortOption,
    TagRef,
    UrlImport,
)
from app.services import indexing_service, search_service
from app.services.activity_service import log_activity
from app.services.errors import ConflictError, InvalidRequestError, NotFoundError

_WS = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    return _WS.sub(" ", name).strip()


# --- Serialisation -------------------------------------------------------------


def _load_options():  # type: ignore[no-untyped-def]
    return (
        selectinload(Document.authors).joinedload(DocumentAuthor.author),
        selectinload(Document.tags),
    )


def to_summary(doc: Document, hit: search_service.SearchHit | None = None) -> DocumentSummary:
    return DocumentSummary(
        id=doc.id,
        title=doc.title,
        doc_type=doc.doc_type,
        status=doc.status,
        authors=[link.author.full_name for link in doc.authors],
        publication_year=doc.publication_year,
        venue=doc.venue,
        page_count=doc.page_count,
        tags=[TagRef(id=t.id, name=t.name) for t in sorted(doc.tags, key=lambda t: t.name.lower())],
        has_file=doc.file_path is not None,
        ai_index_status=doc.ai_index_status,
        source_url=doc.source_url,
        created_at=doc.created_at,
        snippet=hit.snippet if hit else None,
        match_page=hit.page if hit else None,
    )


def to_detail(db: Session, doc: Document) -> DocumentDetail:
    chunk_count = db.scalar(select(func.count()).where(Chunk.document_id == doc.id)) or 0
    extra = doc.extra_metadata or {}
    return DocumentDetail(
        **to_summary(doc).model_dump(),
        abstract=doc.abstract,
        keywords=doc.keywords or [],
        doi=doc.doi,
        volume=doc.volume,
        issue=doc.issue,
        pages=doc.pages,
        publisher=doc.publisher,
        original_filename=doc.original_filename,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        reference_list=doc.reference_list or [],
        note_body=doc.note_body,
        language=doc.language,
        chunk_count=chunk_count,
        collections=[CollectionRef(id=c.id, name=c.name) for c in doc.collections],
        projects=[ProjectRef(id=p.id, name=p.name) for p in doc.projects],
        metadata_sources=extra.get("metadata_sources", {}),
        warnings=extra.get("warnings", []),
        ai_index_error=doc.ai_index_error,
        error_message=doc.error_message,
        updated_at=doc.updated_at,
    )


def get_document(db: Session, document_id: int) -> Document:
    doc = db.scalar(select(Document).where(Document.id == document_id).options(*_load_options()))
    if doc is None:
        raise NotFoundError(f"Document {document_id} not found")
    return doc


# --- Relationship helpers --------------------------------------------------------


def _set_authors(db: Session, doc: Document, names: list[str]) -> None:
    cleaned: list[str] = []
    for name in names:
        name = normalize_name(name)[:300]
        if name and name.lower() not in {c.lower() for c in cleaned}:
            cleaned.append(name)

    existing = {link.author.normalized_name: link for link in doc.authors}
    links: list[DocumentAuthor] = []
    for position, name in enumerate(cleaned):
        key = name.lower()
        link = existing.pop(key, None)
        if link is None:
            author = db.scalar(select(Author).where(Author.normalized_name == key))
            if author is None:
                author = Author(full_name=name, normalized_name=key)
                db.add(author)
            link = DocumentAuthor(author=author)
        link.position = position
        links.append(link)
    doc.authors = links


def _get_or_create_tags(db: Session, names: list[str]) -> list[Tag]:
    tags: list[Tag] = []
    for raw in names:
        name = normalize_name(raw).strip("#")[:100]
        if not name or name.lower() in {t.name.lower() for t in tags}:
            continue
        tag = db.scalar(select(Tag).where(func.lower(Tag.name) == name.lower()))
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
        tags.append(tag)
    return tags


def _fetch_by_ids(db: Session, model: type, ids: list[int], label: str) -> list:  # type: ignore[type-arg]
    unique = list(dict.fromkeys(ids))
    rows = list(db.scalars(select(model).where(model.id.in_(unique)))) if unique else []
    missing = set(unique) - {r.id for r in rows}
    if missing:
        raise NotFoundError(f"{label} {sorted(missing)[0]} not found")
    return rows


def _apply_attachments(db: Session, doc: Document, options: AttachmentOptions) -> None:
    if options.tags:
        doc.tags = _get_or_create_tags(db, options.tags)
    if options.collection_ids:
        doc.collections = _fetch_by_ids(db, Collection, options.collection_ids, "Collection")
    if options.project_ids:
        doc.projects = _fetch_by_ids(db, Project, options.project_ids, "Project")


def _replace_chunks(db: Session, doc: Document, pages: list[ExtractedPage]) -> None:
    db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    db.add_all(
        Chunk(
            document_id=doc.id,
            chunk_index=c.chunk_index,
            page_start=c.page_start,
            page_end=c.page_end,
            section=c.section,
            text=c.text,
            char_count=len(c.text),
        )
        for c in chunk_pages(pages)
    )
    db.expire(doc, ["chunks"])


# --- Import ------------------------------------------------------------------------


@dataclass
class _FileInfo:
    relative_path: str
    original_filename: str
    sha256: str
    size: int
    mime_type: str


def _create_document(
    db: Session,
    extracted: ExtractedDocument,
    *,
    doc_type: DocumentType,
    options: AttachmentOptions,
    file: _FileInfo | None = None,
    source_url: str | None = None,
    note_body: str | None = None,
    mime_type: str | None = None,
) -> Document:
    doc = Document(
        title=(extracted.title or "Untitled")[:500],
        doc_type=doc_type,
        status=DocumentStatus.READY,
        source_url=source_url,
        file_path=file.relative_path if file else None,
        original_filename=file.original_filename if file else None,
        file_hash=file.sha256 if file else None,
        file_size=file.size if file else None,
        mime_type=file.mime_type if file else mime_type,
        abstract=extracted.abstract,
        publication_year=extracted.publication_year,
        venue=extracted.venue,
        doi=extracted.doi,
        keywords=extracted.keywords,
        reference_list=extracted.reference_list,
        page_count=extracted.page_count,
        note_body=note_body,
        extra_metadata={
            "metadata_sources": extracted.metadata_sources,
            "warnings": extracted.warnings,
        },
    )
    db.add(doc)
    db.flush()
    _set_authors(db, doc, extracted.authors)
    _apply_attachments(db, doc, options)
    _replace_chunks(db, doc, extracted.pages)
    db.flush()
    search_service.refresh_document_index(db, doc)
    indexing_service.enqueue(db, [doc.id])
    verb = "Added note" if doc_type is DocumentType.NOTE else "Imported"
    log_activity(
        db,
        action="note.created" if doc_type is DocumentType.NOTE else "document.imported",
        entity_type="document",
        entity_id=doc.id,
        summary=f"{verb} “{doc.title[:200]}”",
    )
    db.commit()
    return get_document(db, doc.id)


def _ensure_not_duplicate_file(db: Session, sha256: str) -> None:
    existing = db.scalar(select(Document).where(Document.file_hash == sha256))
    if existing is not None:
        raise ConflictError(
            f"This file is already in your library as “{existing.title}”.",
            existing_document_id=existing.id,
        )


def import_file(
    db: Session,
    settings: Settings,
    temp_path: Path,
    filename: str | None,
    options: AttachmentOptions,
    *,
    source_url: str | None = None,
) -> Document:
    """Validate, extract, and store an uploaded file. ``temp_path`` is consumed."""
    name = sanitize_filename(filename)
    doc_type = detect_type(name)
    check_size(temp_path.stat().st_size, settings.max_upload_mb * 1024 * 1024)
    verify_content(temp_path, doc_type)
    sha256 = storage.sha256_of(temp_path)
    _ensure_not_duplicate_file(db, sha256)

    extracted = extract(temp_path, doc_type, fallback_title=PurePosixPath(name).stem)
    size = temp_path.stat().st_size
    relative = storage.store_file(
        temp_path, settings.documents_dir, sha256, PurePosixPath(name).suffix.lower()
    )
    try:
        return _create_document(
            db,
            extracted,
            doc_type=doc_type,
            options=options,
            source_url=source_url,
            file=_FileInfo(relative, name, sha256, size, MIME_TYPES[doc_type]),
        )
    except Exception:
        db.rollback()
        storage.delete_stored_file(settings.documents_dir, relative)
        raise


def temp_upload_path(settings: Settings, suffix: str = "") -> Path:
    tmp_dir = settings.data_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(dir=tmp_dir, suffix=suffix, delete=False)
    handle.close()
    return Path(handle.name)


def import_url(
    db: Session,
    settings: Settings,
    data: UrlImport,
    *,
    transport: httpx.BaseTransport | None = None,
    resolver: Resolver = resolve_host,
) -> Document:
    existing = db.scalar(select(Document).where(Document.source_url == data.url))
    if existing is not None:
        raise ConflictError(
            f"This URL is already in your library as “{existing.title}”.",
            existing_document_id=existing.id,
        )
    resource = fetch_url(
        data.url,
        max_bytes=settings.max_upload_mb * 1024 * 1024,
        transport=transport,
        resolver=resolver,
    )

    if resource.is_pdf:
        name = PurePosixPath(urlsplit(resource.url).path).name or "download.pdf"
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        temp_path = temp_upload_path(settings, ".pdf")
        try:
            temp_path.write_bytes(resource.content)
            return import_file(db, settings, temp_path, name, data, source_url=data.url)
        finally:
            temp_path.unlink(missing_ok=True)

    host = urlsplit(resource.url).hostname or "web page"
    if resource.is_html:
        extracted = extract_html(resource.content)
    else:
        extracted = extract_plain_text(resource.text(), markdown=False)
    finalize(extracted, fallback_title=host)
    if not extracted.full_text.strip():
        raise ExtractionError("No readable text was found at this URL.")
    return _create_document(
        db,
        extracted,
        doc_type=DocumentType.WEB,
        options=data,
        source_url=data.url,
        mime_type=resource.content_type or None,
    )


def create_note(db: Session, data: NoteCreate) -> Document:
    extracted = extract_plain_text(data.body, markdown=True)
    extracted.title = data.title
    extracted.metadata_sources = {"title": "manual"}
    return _create_document(
        db, extracted, doc_type=DocumentType.NOTE, options=data, note_body=data.body
    )


# --- Edit & organise ----------------------------------------------------------------


def update_document(db: Session, document_id: int, data: DocumentUpdate) -> Document:
    doc = get_document(db, document_id)
    fields = data.model_fields_set
    sources = dict((doc.extra_metadata or {}).get("metadata_sources", {}))

    if "note_body" in fields and doc.doc_type is not DocumentType.NOTE:
        raise InvalidRequestError("Only notes have an editable body.")
    if "title" in fields and data.title:
        doc.title = data.title
    if "authors" in fields:
        _set_authors(db, doc, data.authors or [])
    if "publication_year" in fields:
        doc.publication_year = data.publication_year
    if "venue" in fields:
        doc.venue = data.venue or None
    if "doi" in fields:
        doi = (data.doi or "").strip()
        doc.doi = (find_doi(doi) or doi.lower()) if doi else None
    if "abstract" in fields:
        doc.abstract = data.abstract or None
    for name in ("volume", "issue", "pages", "publisher"):
        if name in fields:
            setattr(doc, name, getattr(data, name) or None)
    if "keywords" in fields:
        doc.keywords = list(dict.fromkeys(k.strip() for k in data.keywords or [] if k.strip()))
    if "note_body" in fields:
        doc.note_body = data.note_body or ""
        _replace_chunks(db, doc, extract_plain_text(doc.note_body, markdown=True).pages)
        indexing_service.enqueue(db, [doc.id])

    for field in fields - {"note_body"}:
        sources[field] = "manual"
    doc.extra_metadata = {**(doc.extra_metadata or {}), "metadata_sources": sources}
    db.flush()
    search_service.refresh_document_index(db, doc)
    log_activity(
        db,
        action="document.updated",
        entity_type="document",
        entity_id=doc.id,
        summary=f"Edited “{doc.title[:200]}”",
    )
    db.commit()
    return get_document(db, doc.id)


def set_tags(db: Session, document_id: int, names: list[str]) -> Document:
    doc = get_document(db, document_id)
    doc.tags = _get_or_create_tags(db, names)
    db.commit()
    return get_document(db, document_id)


def set_collections(db: Session, document_id: int, ids: list[int]) -> Document:
    doc = get_document(db, document_id)
    doc.collections = _fetch_by_ids(db, Collection, ids, "Collection")
    db.commit()
    return get_document(db, document_id)


def set_projects(db: Session, document_id: int, ids: list[int]) -> Document:
    doc = get_document(db, document_id)
    doc.projects = _fetch_by_ids(db, Project, ids, "Project")
    db.commit()
    return get_document(db, document_id)


def delete_document(db: Session, settings: Settings, document_id: int) -> None:
    doc = get_document(db, document_id)
    title, relative = doc.title, doc.file_path
    db.delete(doc)
    log_activity(
        db,
        action="document.deleted",
        entity_type="document",
        entity_id=None,
        summary=f"Removed “{title[:200]}”",
    )
    db.commit()
    storage.delete_stored_file(settings.documents_dir, relative)


def stored_file_path(settings: Settings, doc: Document) -> Path:
    if not doc.file_path:
        raise NotFoundError("This item has no stored file.")
    path = storage.resolve_stored_path(settings.documents_dir, doc.file_path)
    if not path.is_file():
        raise NotFoundError("The stored file is missing from the data directory.")
    return path


# --- Queries ----------------------------------------------------------------------


@dataclass
class DocumentFilters:
    q: str | None = None
    doc_types: list[DocumentType] | None = None
    tag: str | None = None
    collection_id: int | None = None
    project_id: int | None = None
    author: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    sort: SortOption | None = None
    offset: int = 0
    limit: int = 25


def list_documents(db: Session, filters: DocumentFilters) -> DocumentPage:
    stmt = select(Document.id)
    if filters.doc_types:
        stmt = stmt.where(Document.doc_type.in_(filters.doc_types))
    if filters.tag:
        stmt = stmt.where(
            exists()
            .where(document_tags.c.document_id == Document.id)
            .where(document_tags.c.tag_id == Tag.id)
            .where(func.lower(Tag.name) == filters.tag.strip().lower())
        )
    if filters.collection_id is not None:
        stmt = stmt.where(
            exists()
            .where(collection_documents.c.document_id == Document.id)
            .where(collection_documents.c.collection_id == filters.collection_id)
        )
    if filters.project_id is not None:
        stmt = stmt.where(
            exists()
            .where(project_documents.c.document_id == Document.id)
            .where(project_documents.c.project_id == filters.project_id)
        )
    if filters.author:
        stmt = stmt.where(
            exists()
            .where(DocumentAuthor.document_id == Document.id)
            .where(DocumentAuthor.author_id == Author.id)
            .where(Author.normalized_name.contains(normalize_name(filters.author).lower()))
        )
    if filters.year_from is not None:
        stmt = stmt.where(Document.publication_year >= filters.year_from)
    if filters.year_to is not None:
        stmt = stmt.where(Document.publication_year <= filters.year_to)

    hits: dict[int, search_service.SearchHit] = {}
    query = (filters.q or "").strip()
    if query:
        ranked = search_service.search(db, query)
        hits = {h.document_id: h for h in ranked}
        stmt = stmt.where(Document.id.in_(list(hits)))

    sort = filters.sort or ("relevance" if query else "added")
    if sort == "title":
        stmt = stmt.order_by(func.lower(Document.title), Document.id)
    elif sort == "year":
        stmt = stmt.order_by(
            Document.publication_year.is_(None),
            Document.publication_year.desc(),
            Document.id.desc(),
        )
    else:
        stmt = stmt.order_by(Document.created_at.desc(), Document.id.desc())

    ids = list(db.scalars(stmt))
    if sort == "relevance" and query:
        ids.sort(key=lambda i: hits[i].score)
    page_ids = ids[filters.offset : filters.offset + filters.limit]
    if query:
        search_service.add_snippets(db, query, [hits[i] for i in page_ids if i in hits])
    docs = {
        d.id: d
        for d in db.scalars(
            select(Document).where(Document.id.in_(page_ids)).options(*_load_options())
        )
    }
    return DocumentPage(
        items=[to_summary(docs[i], hits.get(i)) for i in page_ids if i in docs],
        total=len(ids),
        offset=filters.offset,
        limit=filters.limit,
    )


def list_chunks(
    db: Session, document_id: int, offset: int = 0, limit: int = 50, page: int | None = None
) -> ChunkPage:
    get_document(db, document_id)
    stmt = select(Chunk).where(Chunk.document_id == document_id)
    if page is not None:
        stmt = stmt.where(
            Chunk.page_start <= page, func.coalesce(Chunk.page_end, Chunk.page_start) >= page
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Chunk.chunk_index).offset(offset).limit(limit))
    return ChunkPage(items=[ChunkRead.model_validate(c) for c in rows], total=total)
