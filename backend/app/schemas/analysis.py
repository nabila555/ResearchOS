from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.analysis import AnalysisKind, AnalysisStatus


class AnalysisCreate(BaseModel):
    kind: AnalysisKind
    document_ids: list[int] = Field(default_factory=list, max_length=50)
    # Alternatively analyse every document in a collection or project.
    collection_id: int | None = None
    project_id: int | None = None
    # Gap analysis only: optional theme to focus on.
    focus: str | None = Field(default=None, max_length=300)
    # Research proposal only: topic and an optional earlier gap analysis to build on.
    topic: str | None = Field(default=None, max_length=300)
    gap_analysis_id: int | None = None
    # Reports: citation style for references.
    style: Literal["apa", "mla", "chicago", "ieee"] = "apa"


class AnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: AnalysisKind
    status: AnalysisStatus
    title: str
    document_ids: list[int]
    params: dict[str, Any]
    progress: float
    progress_message: str | None
    error: str | None
    provider: str
    model: str
    report_id: int | None
    created_at: datetime
    updated_at: datetime


class AnalysisRead(AnalysisSummary):
    result: dict[str, Any] | None


class ProfileField(BaseModel):
    key: str
    label: str
    status: str
    statements: list[dict[str, Any]]


class PaperProfileRead(BaseModel):
    document_id: int
    provider: str
    model: str
    stale: bool
    passages_used: int
    fields: list[ProfileField]
    updated_at: datetime


class ReportSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    report_type: str
    source_document_ids: list[int]
    model_used: str | None
    created_at: datetime


class ReportRead(ReportSummary):
    content_markdown: str
