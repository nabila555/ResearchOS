"""AI tables: chunk embeddings, background indexing jobs, chat history, app settings."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Enum, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UTCDateTime, utcnow


class IndexStatus(enum.StrEnum):
    """AI (embedding) index state of a document."""

    NONE = "none"  # imported before the AI index existed, or never queued
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class JobStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class ChunkEmbedding(Base):
    """One embedding vector per chunk and model, stored as little-endian float32 bytes."""

    __tablename__ = "chunk_embeddings"

    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    model: Mapped[str] = mapped_column(String(200), primary_key=True, index=True)
    dim: Mapped[int] = mapped_column(Integer)
    vector: Mapped[bytes] = mapped_column(LargeBinary)


class IndexJob(TimestampMixin, Base):
    __tablename__ = "index_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=20), default=JobStatus.PENDING, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    # Default retrieval scope: {"collection_id": int} | {"project_id": int} |
    # {"document_ids": [...]} | {} (whole library).
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChatMessage.id",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    # Assistant messages only ------------------------------------------------
    provider: Mapped[str | None] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(200))
    # "complete" | "error" | "refused" | "insufficient_evidence"
    status: Mapped[str | None] = mapped_column(String(30))
    # True when at least one citation points at a passage that was actually provided.
    grounded: Mapped[bool] = mapped_column(Boolean, default=False)
    # Passages sent to the model: [{n, chunk_id, document_id, title, pages, ...}]
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # Citation numbers used in the answer, split into verified / not verifiable.
    cited: Mapped[list[int]] = mapped_column(JSON, default=list)
    invalid_citations: Mapped[list[int]] = mapped_column(JSON, default=list)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class AppSetting(Base):
    """User-changeable settings persisted in the database (not secrets)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
