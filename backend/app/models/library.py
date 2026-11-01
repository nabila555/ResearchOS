"""Research library tables: documents, authors, tags, collections, and text chunks.

Chunks keep page numbers so every AI answer can cite `document + page`.
Embedding vectors are stored separately (see docs/ARCHITECTURE.md, Phase 3).
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.project import Project


class DocumentType(enum.StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    TEXT = "text"
    MARKDOWN = "markdown"
    WEB = "web"
    NOTE = "note"


class DocumentStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


document_tags = Table(
    "document_tags",
    Base.metadata,
    Column("document_id", ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

collection_documents = Table(
    "collection_documents",
    Base.metadata,
    Column("collection_id", ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    Column("document_id", ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
)


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    doc_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, native_enum=False, length=20), index=True
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False, length=20), default=DocumentStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    # Embedding index for the AI assistant (see app.models.ai.IndexStatus).
    ai_index_status: Mapped[str] = mapped_column(
        String(20), default="none", server_default="none", index=True
    )
    ai_index_error: Mapped[str | None] = mapped_column(Text)

    # Source -------------------------------------------------------------------
    source_url: Mapped[str | None] = mapped_column(String(2000))
    # Path relative to DATA_DIR/documents; never an absolute or user-supplied path.
    file_path: Mapped[str | None] = mapped_column(String(500))
    original_filename: Mapped[str | None] = mapped_column(String(500))
    file_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    file_size: Mapped[int | None] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(100))

    # Bibliographic metadata (only what was actually extracted or entered) -----
    abstract: Mapped[str | None] = mapped_column(Text)
    publication_year: Mapped[int | None] = mapped_column(Integer, index=True)
    venue: Mapped[str | None] = mapped_column(String(500))
    doi: Mapped[str | None] = mapped_column(String(255), index=True)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Raw reference strings as found in the document; parsed later, never invented.
    reference_list: Mapped[list[str]] = mapped_column(JSON, default=list)
    page_count: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str | None] = mapped_column(String(20))
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Free-form content for notes; extracted text lives in chunks.
    note_body: Mapped[str | None] = mapped_column(Text)

    authors: Mapped[list[DocumentAuthor]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentAuthor.position",
    )
    tags: Mapped[list[Tag]] = relationship(secondary=document_tags, back_populates="documents")
    collections: Mapped[list[Collection]] = relationship(
        secondary=collection_documents, back_populates="documents"
    )
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
    projects: Mapped[list[Project]] = relationship(
        secondary="project_documents", back_populates="documents"
    )


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(300), index=True)
    # Lower-cased, whitespace-collapsed name used for de-duplication.
    normalized_name: Mapped[str] = mapped_column(String(300), unique=True)

    documents: Mapped[list[DocumentAuthor]] = relationship(back_populates="author")


class DocumentAuthor(Base):
    __tablename__ = "document_authors"

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)

    document: Mapped[Document] = relationship(back_populates="authors")
    author: Mapped[Author] = relationship(back_populates="documents")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    color: Mapped[str | None] = mapped_column(String(20))

    documents: Mapped[list[Document]] = relationship(secondary=document_tags, back_populates="tags")


class Collection(TimestampMixin, Base):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str | None] = mapped_column(Text)

    documents: Mapped[list[Document]] = relationship(
        secondary=collection_documents, back_populates="collections"
    )


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(500))
    text: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer)

    document: Mapped[Document] = relationship(back_populates="chunks")
