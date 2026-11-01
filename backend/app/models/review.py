"""Literature review workspace: reviews, themes, and the sources grouped under them."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class LiteratureReview(TimestampMixin, Base):
    __tablename__ = "literature_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    research_question: Mapped[str | None] = mapped_column(Text)
    introduction: Mapped[str | None] = mapped_column(Text)  # user-written
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    citation_style: Mapped[str] = mapped_column(String(20), default="apa")

    themes: Mapped[list[ReviewTheme]] = relationship(
        back_populates="review",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ReviewTheme.position",
    )


class ReviewTheme(TimestampMixin, Base):
    __tablename__ = "review_themes"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("literature_reviews.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)

    review: Mapped[LiteratureReview] = relationship(back_populates="themes")
    items: Mapped[list[ReviewThemeItem]] = relationship(
        back_populates="theme",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ReviewThemeItem.position",
    )


class ReviewThemeItem(Base):
    __tablename__ = "review_theme_items"

    theme_id: Mapped[int] = mapped_column(
        ForeignKey("review_themes.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text)

    theme: Mapped[ReviewTheme] = relationship(back_populates="items")
