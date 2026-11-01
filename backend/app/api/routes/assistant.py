from dataclasses import asdict

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.ai.registry import CHAT_PROVIDER_LABELS
from app.api.deps import AppSettings, DbSession
from app.models.ai import ChunkEmbedding, IndexStatus
from app.models.library import Chunk, Document
from app.schemas.assistant import (
    AISettingsUpdate,
    AskRequest,
    AssistantStatus,
    ChatSessionCreate,
    ChatSessionDetail,
    ChatSessionRead,
    ChatSessionUpdate,
    IndexStats,
    ProviderInfo,
    ReindexRequest,
    ReindexResponse,
    RetrieveRequest,
    RetrieveResponse,
)
from app.services import assistant_service, indexing_service, settings_service
from app.services.retrieval_service import Scope, retrieve

router = APIRouter(prefix="/assistant", tags=["assistant"])


def notify_indexer(request: Request) -> None:
    worker = getattr(request.app.state, "index_worker", None)
    if worker is not None:
        worker.notify()


@router.get("/status", response_model=AssistantStatus)
def assistant_status(request: Request, db: DbSession, settings: AppSettings) -> AssistantStatus:
    ai = request.app.state.ai
    ai_settings = settings_service.get_ai_settings(db, settings)
    providers = []
    for name in ai.available_chat_providers():
        providers.append(
            ProviderInfo(
                name=name,
                label=CHAT_PROVIDER_LABELS.get(name, name),
                model=ai.chat(name).model,
                cloud=name != "ollama",
            )
        )
    counts = dict(
        db.execute(
            select(Document.ai_index_status, func.count()).group_by(Document.ai_index_status)
        ).all()
    )
    worker = getattr(request.app.state, "index_worker", None)
    return AssistantStatus(
        chat_provider=ai_settings.chat_provider,
        providers=providers,
        cloud_consent=ai_settings.cloud_consent,
        embed_model=ai.embedder.model,
        index=IndexStats(
            documents_total=sum(counts.values()),
            ready=counts.get(IndexStatus.READY.value, 0),
            pending=counts.get(IndexStatus.PENDING.value, 0),
            failed=counts.get(IndexStatus.FAILED.value, 0),
            not_indexed=counts.get(IndexStatus.NONE.value, 0),
            chunks_total=db.scalar(select(func.count()).select_from(Chunk)) or 0,
            chunks_embedded=db.scalar(
                select(func.count()).where(ChunkEmbedding.model == ai.embedder.model)
            )
            or 0,
            waiting_for_provider=bool(worker and worker.waiting_for_provider),
        ),
    )


@router.put("/settings", response_model=AssistantStatus)
def update_settings(
    data: AISettingsUpdate, request: Request, db: DbSession, settings: AppSettings
) -> AssistantStatus:
    settings_service.update_ai_settings(
        db, chat_provider=data.chat_provider, cloud_consent=data.cloud_consent
    )
    return assistant_status(request, db, settings)


@router.post("/reindex", response_model=ReindexResponse)
def reindex(data: ReindexRequest, request: Request, db: DbSession) -> ReindexResponse:
    if data.document_ids:
        existing = list(db.scalars(select(Document.id).where(Document.id.in_(data.document_ids))))
        queued = indexing_service.enqueue(db, existing)
    else:
        queued = indexing_service.enqueue_unindexed(db, include_failed=data.include_failed)
    db.commit()
    notify_indexer(request)
    return ReindexResponse(queued=queued)


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve_passages(
    data: RetrieveRequest, request: Request, db: DbSession, settings: AppSettings
) -> RetrieveResponse:
    scope = Scope.from_dict(data.scope.model_dump() if data.scope else None)
    result = retrieve(
        db,
        request.app.state.ai,
        request.app.state.vector_index,
        settings,
        data.query,
        scope,
        data.top_k,
    )
    return RetrieveResponse(
        passages=[asdict(p) for p in result.passages], semantic=result.semantic, notes=result.notes
    )


@router.get("/sessions", response_model=list[ChatSessionRead])
def list_sessions(db: DbSession) -> list[ChatSessionRead]:
    return assistant_service.list_sessions(db)


@router.post("/sessions", response_model=ChatSessionRead, status_code=status.HTTP_201_CREATED)
def create_session(data: ChatSessionCreate, db: DbSession) -> ChatSessionRead:
    return assistant_service.create_session(
        db, data.title, data.scope.model_dump() if data.scope else None
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionDetail)
def get_session(session_id: int, db: DbSession) -> ChatSessionDetail:
    session = assistant_service.get_session(db, session_id)
    summary = assistant_service._session_read(db, session)
    return ChatSessionDetail(
        **summary.model_dump(), messages=assistant_service.session_messages(db, session_id)
    )


@router.patch("/sessions/{session_id}", response_model=ChatSessionRead)
def update_session(session_id: int, data: ChatSessionUpdate, db: DbSession) -> ChatSessionRead:
    return assistant_service.update_session(
        db, session_id, data.title, data.scope.model_dump() if data.scope else None
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, db: DbSession) -> Response:
    assistant_service.delete_session(db, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/{session_id}/messages")
def ask(
    session_id: int, data: AskRequest, request: Request, db: DbSession, settings: AppSettings
) -> StreamingResponse:
    """Stream an answer as newline-delimited JSON events."""
    ai = request.app.state.ai
    _, provider_name = assistant_service.prepare_question(
        db, settings, ai, session_id, data.content
    )
    stream = assistant_service.answer_stream(
        request.app.state.session_factory,
        settings,
        ai,
        request.app.state.vector_index,
        session_id,
        data.content.strip(),
        provider_name,
        data.scope.model_dump() if data.scope else None,
    )
    return StreamingResponse(
        stream,
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
