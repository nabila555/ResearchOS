from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.library import Collection, Document, DocumentType, Tag, document_tags
from app.models.project import Project, ProjectStatus
from app.models.report import Report
from app.schemas.dashboard import (
    ActivityRead,
    DashboardStats,
    DashboardSummary,
    RecentDocument,
    RecentReport,
    TopicCount,
)
from app.services import activity_service, project_service


def _count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def build_dashboard(db: Session) -> DashboardSummary:
    by_type_rows = db.execute(select(Document.doc_type, func.count()).group_by(Document.doc_type))
    by_type = {t: 0 for t in DocumentType} | {t: n for t, n in by_type_rows}

    projects_active = (
        db.scalar(
            select(func.count()).select_from(Project).where(Project.status == ProjectStatus.ACTIVE)
        )
        or 0
    )

    stats = DashboardStats(
        documents_total=sum(by_type.values()),
        documents_by_type=by_type,
        collections_total=_count(db, Collection),
        tags_total=_count(db, Tag),
        projects_total=_count(db, Project),
        projects_active=projects_active,
        reports_total=_count(db, Report),
    )

    recent_documents = db.scalars(
        select(Document).order_by(Document.created_at.desc(), Document.id.desc()).limit(6)
    )

    # Topics are the most-used tags across the library.
    topic_rows = db.execute(
        select(Tag.name, func.count(document_tags.c.document_id).label("n"))
        .join(document_tags, document_tags.c.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(func.count(document_tags.c.document_id).desc(), Tag.name)
        .limit(10)
    )

    recent_reports = db.scalars(
        select(Report).order_by(Report.created_at.desc(), Report.id.desc()).limit(5)
    )

    active_projects = project_service.list_projects(db, status=ProjectStatus.ACTIVE, limit=5)

    return DashboardSummary(
        stats=stats,
        recent_documents=[RecentDocument.model_validate(d) for d in recent_documents],
        topics=[TopicCount(name=name, document_count=n) for name, n in topic_rows],
        active_projects=project_service.to_read_models(db, active_projects),
        recent_activity=[
            ActivityRead.model_validate(a) for a in activity_service.recent_activity(db, limit=10)
        ],
        recent_reports=[RecentReport.model_validate(r) for r in recent_reports],
    )
