from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import DbSession
from app.models.project import ProjectStatus
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services import project_service
from app.services.project_service import ProjectNotFoundError

router = APIRouter(prefix="/projects", tags=["projects"])


def _not_found(project_id: int) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"Project {project_id} not found")


@router.get("", response_model=list[ProjectRead])
def list_projects(db: DbSession, status: ProjectStatus | None = None) -> list[ProjectRead]:
    return project_service.to_read_models(db, project_service.list_projects(db, status=status))


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(data: ProjectCreate, db: DbSession) -> ProjectRead:
    project = project_service.create_project(db, data)
    return project_service.to_read_models(db, [project])[0]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, db: DbSession) -> ProjectRead:
    try:
        project = project_service.get_project(db, project_id)
    except ProjectNotFoundError:
        raise _not_found(project_id) from None
    return project_service.to_read_models(db, [project])[0]


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: int, data: ProjectUpdate, db: DbSession) -> ProjectRead:
    try:
        project = project_service.update_project(db, project_id, data)
    except ProjectNotFoundError:
        raise _not_found(project_id) from None
    return project_service.to_read_models(db, [project])[0]


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: DbSession) -> Response:
    try:
        project_service.delete_project(db, project_id)
    except ProjectNotFoundError:
        raise _not_found(project_id) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
