from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectStatus, project_documents
from app.models.report import Report
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.activity_service import log_activity


class ProjectNotFoundError(LookupError):
    pass


def _counts(db: Session, project_ids: list[int]) -> tuple[dict[int, int], dict[int, int]]:
    if not project_ids:
        return {}, {}
    doc_rows = db.execute(
        select(project_documents.c.project_id, func.count())
        .where(project_documents.c.project_id.in_(project_ids))
        .group_by(project_documents.c.project_id)
    )
    report_rows = db.execute(
        select(Report.project_id, func.count())
        .where(Report.project_id.in_(project_ids))
        .group_by(Report.project_id)
    )
    return dict(doc_rows.all()), dict(report_rows.all())


def to_read_models(db: Session, projects: list[Project]) -> list[ProjectRead]:
    doc_counts, report_counts = _counts(db, [p.id for p in projects])
    return [
        ProjectRead.model_validate(p).model_copy(
            update={
                "document_count": doc_counts.get(p.id, 0),
                "report_count": report_counts.get(p.id, 0),
            }
        )
        for p in projects
    ]


def list_projects(
    db: Session, status: ProjectStatus | None = None, limit: int | None = None
) -> list[Project]:
    stmt = select(Project).order_by(Project.updated_at.desc(), Project.id.desc())
    if status is not None:
        stmt = stmt.where(Project.status == status)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


def get_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(project_id)
    return project


def create_project(db: Session, data: ProjectCreate) -> Project:
    project = Project(**data.model_dump())
    db.add(project)
    db.flush()
    log_activity(
        db,
        action="project.created",
        entity_type="project",
        entity_id=project.id,
        summary=f"Created project “{project.name}”",
    )
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project_id: int, data: ProjectUpdate) -> Project:
    project = get_project(db, project_id)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        del changes["name"]  # name is required; ignore explicit nulls
    previous_status = project.status
    for field, value in changes.items():
        setattr(project, field, value)
    if "status" in changes and changes["status"] != previous_status:
        summary = f"Marked project “{project.name}” as {project.status.value}"
    else:
        summary = f"Updated project “{project.name}”"
    log_activity(
        db, action="project.updated", entity_type="project", entity_id=project.id, summary=summary
    )
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project_id: int) -> None:
    project = get_project(db, project_id)
    name = project.name
    db.delete(project)
    log_activity(
        db,
        action="project.deleted",
        entity_type="project",
        entity_id=None,
        summary=f"Deleted project “{name}”",
    )
    db.commit()
