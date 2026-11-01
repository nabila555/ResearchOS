"""Generated research reports (summaries, literature reviews, gap analyses...)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.project import Project


class Report(TimestampMixin, Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    # e.g. summary, literature_review, comparison, methodology, gap_analysis, proposal
    report_type: Mapped[str] = mapped_column(String(50), index=True)
    content_markdown: Mapped[str] = mapped_column(Text)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    source_document_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    # Which provider/model produced the content, for transparency.
    model_used: Mapped[str | None] = mapped_column(String(200))

    project: Mapped[Project | None] = relationship(back_populates="reports")
