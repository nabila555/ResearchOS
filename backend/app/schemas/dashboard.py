from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.library import DocumentStatus, DocumentType
from app.schemas.project import ProjectRead


class DashboardStats(BaseModel):
    documents_total: int
    documents_by_type: dict[DocumentType, int]
    collections_total: int
    tags_total: int
    projects_total: int
    projects_active: int
    reports_total: int


class RecentDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    doc_type: DocumentType
    status: DocumentStatus
    publication_year: int | None
    created_at: datetime


class TopicCount(BaseModel):
    name: str
    document_count: int


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    entity_type: str
    entity_id: int | None
    summary: str
    created_at: datetime


class RecentReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    report_type: str
    created_at: datetime


class DashboardSummary(BaseModel):
    stats: DashboardStats
    recent_documents: list[RecentDocument]
    topics: list[TopicCount]
    active_projects: list[ProjectRead]
    recent_activity: list[ActivityRead]
    recent_reports: list[RecentReport]
