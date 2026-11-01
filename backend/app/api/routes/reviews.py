import re
from typing import Any

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import AppSettings, DbSession
from app.citations import Style
from app.models.analysis import AnalysisKind
from app.models.review import LiteratureReview, ReviewTheme
from app.services import analysis_service, review_service
from app.services.assistant_service import resolve_chat_provider
from app.services.errors import InvalidRequestError

router = APIRouter(prefix="/reviews", tags=["literature review"])


def _detail(db: DbSession, review_id: int) -> dict[str, Any]:
    # Sessions keep objects after commit; reload so theme order and membership are current.
    db.expire_all()
    return review_service.review_detail(db, review_service.get_review(db, review_id))


class ReviewCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    research_question: str | None = Field(default=None, max_length=2000)
    project_id: int | None = None


class ReviewUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    research_question: str | None = Field(default=None, max_length=2000)
    introduction: str | None = Field(default=None, max_length=50_000)
    citation_style: Style | None = None


class ThemeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    document_ids: list[int] = Field(default_factory=list, max_length=100)


class ThemeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    position: int | None = Field(default=None, ge=0)


class ThemeItemIn(BaseModel):
    document_id: int
    note: str | None = Field(default=None, max_length=5000)


class ThemeItems(BaseModel):
    items: list[ThemeItemIn] = Field(max_length=100)


class SuggestRequest(BaseModel):
    document_ids: list[int] = Field(min_length=2, max_length=100)


@router.get("")
def list_reviews(db: DbSession) -> list[dict[str, Any]]:
    reviews = db.scalars(select(LiteratureReview).order_by(LiteratureReview.updated_at.desc()))
    counts = dict(
        db.execute(
            select(ReviewTheme.review_id, func.count()).group_by(ReviewTheme.review_id)
        ).all()
    )
    return [
        {
            "id": r.id,
            "title": r.title,
            "research_question": r.research_question,
            "theme_count": counts.get(r.id, 0),
            "updated_at": r.updated_at,
        }
        for r in reviews
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_review(data: ReviewCreate, db: DbSession) -> dict[str, Any]:
    review = LiteratureReview(
        title=data.title.strip(),
        research_question=(data.research_question or "").strip() or None,
        project_id=data.project_id,
    )
    db.add(review)
    db.commit()
    return _detail(db, review.id)


@router.get("/{review_id}")
def get_review(review_id: int, db: DbSession) -> dict[str, Any]:
    return _detail(db, review_id)


@router.patch("/{review_id}")
def update_review(review_id: int, data: ReviewUpdate, db: DbSession) -> dict[str, Any]:
    review = review_service.get_review(db, review_id)
    for name in data.model_fields_set:
        value = getattr(data, name)
        if name == "title" and not value:
            continue
        setattr(review, name, value.strip() if isinstance(value, str) else value)
    db.commit()
    return _detail(db, review_id)


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(review_id: int, db: DbSession) -> Response:
    db.delete(review_service.get_review(db, review_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{review_id}/themes", status_code=status.HTTP_201_CREATED)
def create_theme(review_id: int, data: ThemeCreate, db: DbSession) -> dict[str, Any]:
    review = review_service.get_review(db, review_id)
    theme = ReviewTheme(
        review_id=review.id,
        name=data.name.strip(),
        description=(data.description or "").strip() or None,
        position=len(review.themes),
    )
    db.add(theme)
    db.flush()
    review_service.set_theme_items(db, theme, [{"document_id": i} for i in data.document_ids])
    db.commit()
    return _detail(db, review_id)


@router.patch("/themes/{theme_id}")
def update_theme(theme_id: int, data: ThemeUpdate, db: DbSession) -> dict[str, Any]:
    theme = review_service.get_theme(db, theme_id)
    if data.name:
        theme.name = data.name.strip()
    if "description" in data.model_fields_set:
        theme.description = (data.description or "").strip() or None
    if data.position is not None:
        siblings = [
            t for t in review_service.get_review(db, theme.review_id).themes if t.id != theme.id
        ]
        siblings.insert(min(data.position, len(siblings)), theme)
        for index, sibling in enumerate(siblings):
            sibling.position = index
    db.commit()
    return _detail(db, theme.review_id)


@router.delete("/themes/{theme_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_theme(theme_id: int, db: DbSession) -> Response:
    db.delete(review_service.get_theme(db, theme_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/themes/{theme_id}/items")
def set_items(theme_id: int, data: ThemeItems, db: DbSession) -> dict[str, Any]:
    theme = review_service.get_theme(db, theme_id)
    review_service.set_theme_items(db, theme, [i.model_dump() for i in data.items])
    db.commit()
    return _detail(db, theme.review_id)


@router.post("/{review_id}/suggest-themes")
def suggest_themes(
    review_id: int, data: SuggestRequest, request: Request, db: DbSession
) -> dict[str, Any]:
    review_service.get_review(db, review_id)
    return review_service.suggest_groups(db, data.document_ids, request.app.state.ai.embedder.model)


@router.post("/themes/{theme_id}/summary", status_code=status.HTTP_202_ACCEPTED)
def summarise_theme(
    theme_id: int, request: Request, db: DbSession, settings: AppSettings
) -> dict[str, Any]:
    theme = review_service.get_theme(db, theme_id)
    review = review_service.get_review(db, theme.review_id)
    document_ids = [item.document_id for item in theme.items]
    if not document_ids:
        raise InvalidRequestError("Add papers to this theme first.")
    ai = request.app.state.ai
    provider = ai.chat(resolve_chat_provider(db, settings, ai))
    analysis_service.create_analysis(
        db,
        kind=AnalysisKind.THEME_SUMMARY,
        document_ids=document_ids,
        provider=provider,
        params={
            "theme_id": theme.id,
            "theme_name": theme.name,
            "research_question": review.research_question,
        },
    )
    worker = getattr(request.app.state, "analysis_worker", None)
    if worker is not None:
        worker.notify()
    return _detail(db, review.id)


@router.get("/{review_id}/export")
def export_review(review_id: int, db: DbSession, style: Style | None = None) -> Response:
    review = review_service.get_review(db, review_id)
    content = review_service.export_markdown(db, review, style or review.citation_style)  # type: ignore[arg-type]
    filename = re.sub(r"[^A-Za-z0-9._-]+", "-", review.title).strip("-")[:80] or "literature-review"
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}.md"'},
    )
