from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from app.api.deps import DbSession
from app.citations import STYLES, Style
from app.services import citation_service

router = APIRouter(prefix="/citations", tags=["citations"])


@router.get("/styles")
def styles() -> dict[str, str]:
    return STYLES


@router.get("")
def citations(
    db: DbSession,
    style: Style = "apa",
    document_id: Annotated[list[int] | None, Query()] = None,
) -> list[dict]:
    """Formatted references. Without document_id, every citable item in the library."""
    return citation_service.formatted(db, style, document_id)


@router.get("/export")
def export(
    db: DbSession,
    format: Literal["bibtex", "ris", "markdown", "text"] = "bibtex",  # noqa: A002
    style: Style = "apa",
    document_id: Annotated[list[int] | None, Query()] = None,
) -> Response:
    content, media_type, extension = citation_service.export(db, format, style, document_id)
    return Response(
        content=content,
        media_type=f"{media_type}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="references.{extension}"'},
    )
