from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ScopeIn(BaseModel):
    collection_id: int | None = None
    project_id: int | None = None
    document_ids: list[int] = Field(default_factory=list, max_length=200)


class ChatSessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    scope: ScopeIn | None = None


class ChatSessionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    scope: ScopeIn | None = None


class ChatSessionRead(BaseModel):
    id: int
    title: str
    scope: dict[str, Any]
    message_count: int
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    role: str
    content: str
    provider: str | None = None
    model: str | None = None
    status: str | None = None
    grounded: bool = False
    sources: list[dict[str, Any]] = Field(default_factory=list)
    cited: list[int] = Field(default_factory=list)
    invalid_citations: list[int] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    created_at: datetime


class ChatSessionDetail(ChatSessionRead):
    messages: list[ChatMessageRead]


class AskRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    # When given, replaces the chat's scope for this and later questions.
    scope: ScopeIn | None = None


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    scope: ScopeIn | None = None
    top_k: int | None = Field(default=None, ge=1, le=30)


class RetrieveResponse(BaseModel):
    passages: list[dict[str, Any]]
    semantic: bool
    notes: list[str]


class ProviderInfo(BaseModel):
    name: str
    label: str
    model: str
    cloud: bool


class IndexStats(BaseModel):
    documents_total: int
    ready: int
    pending: int
    failed: int
    not_indexed: int
    chunks_total: int
    chunks_embedded: int
    waiting_for_provider: bool


class AssistantStatus(BaseModel):
    chat_provider: str
    providers: list[ProviderInfo]
    cloud_consent: bool
    embed_model: str
    index: IndexStats


class AISettingsUpdate(BaseModel):
    chat_provider: Literal["ollama", "anthropic"] | None = None
    cloud_consent: bool | None = None


class ReindexRequest(BaseModel):
    document_ids: list[int] = Field(default_factory=list, max_length=10_000)
    # With no document_ids: queue every document that is not indexed (and failed ones).
    include_failed: bool = True


class ReindexResponse(BaseModel):
    queued: int
