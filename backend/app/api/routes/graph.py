from typing import Annotated, Any

from fastapi import APIRouter, Query, Request

from app.api.deps import DbSession
from app.services import graph_service
from app.services.retrieval_service import Scope

router = APIRouter(prefix="/graph", tags=["graph"])

ALL_LAYERS = {"author", "topic", "keyword", "collection", "similar", "shared_references"}


@router.get("")
def graph(
    request: Request,
    db: DbSession,
    include: Annotated[list[str] | None, Query()] = None,
    collection_id: int | None = None,
    project_id: int | None = None,
    similarity: Annotated[float, Query(ge=0.0, le=1.0)] = 0.75,
    min_keyword_papers: Annotated[int, Query(ge=1, le=20)] = 2,
) -> dict[str, Any]:
    layers = ALL_LAYERS if include is None else set(include) & ALL_LAYERS
    return graph_service.build_graph(
        db,
        scope=Scope(collection_id=collection_id, project_id=project_id),
        embed_model=request.app.state.ai.embedder.model,
        include=layers,
        similarity_threshold=similarity,
        min_keyword_papers=min_keyword_papers,
    )


@router.get("/papers/{document_id}")
def paper_details(document_id: int, db: DbSession) -> dict[str, Any]:
    return graph_service.paper_details(db, document_id)
