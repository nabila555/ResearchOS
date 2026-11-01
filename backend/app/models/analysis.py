"""Research-intelligence tables: cached paper profiles and long-running analyses."""

import enum
from typing import Any

from sqlalchemy import JSON, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class AnalysisKind(enum.StrEnum):
    PROFILE = "profile"  # structured extraction for one paper
    COMPARISON = "comparison"
    GAP_ANALYSIS = "gap_analysis"
    DETECTIVE = "detective"
    THEME_SUMMARY = "theme_summary"  # literature review theme synthesis
    SUMMARY = "summary"  # research summary report (no extra model call)
    METHODOLOGY = "methodology"  # methodology analysis report (no extra model call)
    PROPOSAL = "proposal"  # model-drafted research proposal


class AnalysisStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaperProfile(TimestampMixin, Base):
    """Structured, evidence-linked summary of one paper, reused by every analysis.

    ``fields`` maps a field key (e.g. "sample_size") to
    ``{"status": ..., "statements": [{"text", "evidence": {...}, "verified"}]}``.
    """

    __tablename__ = "paper_profiles"

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(200))
    fields: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Fingerprint of the chunks the profile was built from; differs once the text changes.
    chunk_signature: Mapped[str] = mapped_column(String(100))
    passages_used: Mapped[int] = mapped_column(Integer, default=0)


class Analysis(TimestampMixin, Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[AnalysisKind] = mapped_column(
        Enum(AnalysisKind, native_enum=False, length=30), index=True
    )
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, native_enum=False, length=20),
        default=AnalysisStatus.PENDING,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(300))
    document_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    progress_message: Mapped[str | None] = mapped_column(String(300))
    error: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(200))
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id", ondelete="SET NULL"))
