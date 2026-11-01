"""Collections, tags, and library facets (filter options with counts)."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.library import (
    Author,
    Collection,
    Document,
    DocumentAuthor,
    Tag,
    collection_documents,
    document_tags,
)
from app.schemas.library import (
    CollectionCreate,
    CollectionRead,
    CollectionUpdate,
    FacetCount,
    LibraryFacets,
    TagRead,
)
from app.services.activity_service import log_activity
from app.services.errors import ConflictError, NotFoundError

# --- Collections ---------------------------------------------------------------------


def _collection_read(collection: Collection, count: int) -> CollectionRead:
    return CollectionRead(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        document_count=count,
        created_at=collection.created_at,
    )


def list_collections(db: Session) -> list[CollectionRead]:
    rows = db.execute(
        select(Collection, func.count(collection_documents.c.document_id))
        .outerjoin(collection_documents, collection_documents.c.collection_id == Collection.id)
        .group_by(Collection.id)
        .order_by(func.lower(Collection.name))
    )
    return [_collection_read(c, n) for c, n in rows]


def _get_collection(db: Session, collection_id: int) -> Collection:
    collection = db.get(Collection, collection_id)
    if collection is None:
        raise NotFoundError(f"Collection {collection_id} not found")
    return collection


def _count(db: Session, collection_id: int) -> int:
    return (
        db.scalar(select(func.count()).where(collection_documents.c.collection_id == collection_id))
        or 0
    )


def _ensure_unique_name(db: Session, name: str, exclude_id: int | None = None) -> None:
    stmt = select(Collection.id).where(func.lower(Collection.name) == name.lower())
    if exclude_id is not None:
        stmt = stmt.where(Collection.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise ConflictError(f"A collection named “{name}” already exists.")


def create_collection(db: Session, data: CollectionCreate) -> CollectionRead:
    _ensure_unique_name(db, data.name)
    collection = Collection(name=data.name, description=data.description or None)
    db.add(collection)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ConflictError(f"A collection named “{data.name}” already exists.") from None
    log_activity(
        db,
        action="collection.created",
        entity_type="collection",
        entity_id=collection.id,
        summary=f"Created collection “{collection.name}”",
    )
    db.commit()
    return _collection_read(collection, 0)


def update_collection(db: Session, collection_id: int, data: CollectionUpdate) -> CollectionRead:
    collection = _get_collection(db, collection_id)
    if "name" in data.model_fields_set and data.name:
        _ensure_unique_name(db, data.name, exclude_id=collection_id)
        collection.name = data.name
    if "description" in data.model_fields_set:
        collection.description = data.description or None
    db.commit()
    return _collection_read(collection, _count(db, collection_id))


def delete_collection(db: Session, collection_id: int) -> None:
    collection = _get_collection(db, collection_id)
    name = collection.name
    db.delete(collection)  # documents are kept; only the membership rows cascade
    log_activity(
        db,
        action="collection.deleted",
        entity_type="collection",
        entity_id=None,
        summary=f"Deleted collection “{name}”",
    )
    db.commit()


# --- Tags -----------------------------------------------------------------------------


def list_tags(db: Session) -> list[TagRead]:
    rows = db.execute(
        select(Tag, func.count(document_tags.c.document_id))
        .outerjoin(document_tags, document_tags.c.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(func.lower(Tag.name))
    )
    return [TagRead(id=t.id, name=t.name, document_count=n) for t, n in rows]


def delete_tag(db: Session, tag_id: int) -> None:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise NotFoundError(f"Tag {tag_id} not found")
    db.delete(tag)
    db.commit()


# --- Facets -----------------------------------------------------------------------------


def facets(db: Session) -> LibraryFacets:
    types = db.execute(
        select(Document.doc_type, func.count())
        .group_by(Document.doc_type)
        .order_by(func.count().desc())
    )
    years = db.execute(
        select(Document.publication_year, func.count())
        .where(Document.publication_year.is_not(None))
        .group_by(Document.publication_year)
        .order_by(Document.publication_year.desc())
    )
    authors = db.execute(
        select(Author.full_name, func.count(DocumentAuthor.document_id).label("n"))
        .join(DocumentAuthor, DocumentAuthor.author_id == Author.id)
        .group_by(Author.id)
        .order_by(func.count(DocumentAuthor.document_id).desc(), func.lower(Author.full_name))
        .limit(100)
    )
    return LibraryFacets(
        total=db.scalar(select(func.count()).select_from(Document)) or 0,
        types=[FacetCount(value=t.value, count=n) for t, n in types],
        years=[FacetCount(value=str(y), count=n) for y, n in years],
        authors=[FacetCount(value=a, count=n) for a, n in authors],
        tags=[t for t in list_tags(db) if t.document_count > 0],
        collections=list_collections(db),
    )
