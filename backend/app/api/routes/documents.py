import json
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import AppSettings, DbSession
from app.document_processing.types import FileTooLargeError, InvalidFileError
from app.models.library import DocumentType
from app.schemas.library import (
    AttachmentOptions,
    ChunkPage,
    DocumentDetail,
    DocumentPage,
    DocumentUpdate,
    IdList,
    NameList,
    NoteCreate,
    SortOption,
    UrlImport,
)
from app.services import document_service
from app.services.document_service import DocumentFilters

router = APIRouter(prefix="/documents", tags=["documents"])

COPY_BLOCK = 1024 * 1024


def _parse_options(raw: str | None) -> AttachmentOptions:
    if not raw:
        return AttachmentOptions()
    try:
        return AttachmentOptions.model_validate(json.loads(raw))
    except (ValueError, TypeError) as exc:
        raise InvalidFileError("Invalid import options.") from exc


@router.get("", response_model=DocumentPage)
def list_documents(
    db: DbSession,
    q: Annotated[str | None, Query(max_length=500)] = None,
    doc_type: Annotated[list[DocumentType] | None, Query()] = None,
    tag: str | None = None,
    collection_id: int | None = None,
    project_id: int | None = None,
    author: Annotated[str | None, Query(max_length=200)] = None,
    year_from: Annotated[int | None, Query(ge=1000, le=2100)] = None,
    year_to: Annotated[int | None, Query(ge=1000, le=2100)] = None,
    sort: SortOption | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> DocumentPage:
    return document_service.list_documents(
        db,
        DocumentFilters(
            q=q,
            doc_types=doc_type,
            tag=tag,
            collection_id=collection_id,
            project_id=project_id,
            author=author,
            year_from=year_from,
            year_to=year_to,
            sort=sort,
            offset=offset,
            limit=limit,
        ),
    )


@router.post("/upload", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
def upload_document(
    request: Request,
    db: DbSession,
    settings: AppSettings,
    file: Annotated[UploadFile, File()],
    options: Annotated[str | None, Form(description="JSON AttachmentOptions")] = None,
) -> DocumentDetail:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    declared = int(request.headers.get("content-length") or 0)
    if declared > max_bytes + 64 * 1024:  # allow for multipart overhead
        raise FileTooLargeError(f"The upload exceeds the {settings.max_upload_mb} MB limit.")
    attach = _parse_options(options)

    temp_path = document_service.temp_upload_path(settings)
    try:
        written = 0
        with temp_path.open("wb") as out:
            while block := file.file.read(COPY_BLOCK):
                written += len(block)
                if written > max_bytes:
                    raise FileTooLargeError(
                        f"The upload exceeds the {settings.max_upload_mb} MB limit."
                    )
                out.write(block)
        doc = document_service.import_file(db, settings, temp_path, file.filename, attach)
    finally:
        temp_path.unlink(missing_ok=True)
    return document_service.to_detail(db, doc)


@router.post("/url", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
def import_url(data: UrlImport, db: DbSession, settings: AppSettings) -> DocumentDetail:
    doc = document_service.import_url(db, settings, data)
    return document_service.to_detail(db, doc)


@router.post("/notes", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
def create_note(data: NoteCreate, db: DbSession) -> DocumentDetail:
    return document_service.to_detail(db, document_service.create_note(db, data))


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: int, db: DbSession) -> DocumentDetail:
    return document_service.to_detail(db, document_service.get_document(db, document_id))


@router.patch("/{document_id}", response_model=DocumentDetail)
def update_document(document_id: int, data: DocumentUpdate, db: DbSession) -> DocumentDetail:
    doc = document_service.update_document(db, document_id, data)
    return document_service.to_detail(db, doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: DbSession, settings: AppSettings) -> Response:
    document_service.delete_document(db, settings, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{document_id}/tags", response_model=DocumentDetail)
def set_tags(document_id: int, data: NameList, db: DbSession) -> DocumentDetail:
    return document_service.to_detail(db, document_service.set_tags(db, document_id, data.names))


@router.put("/{document_id}/collections", response_model=DocumentDetail)
def set_collections(document_id: int, data: IdList, db: DbSession) -> DocumentDetail:
    doc = document_service.set_collections(db, document_id, data.ids)
    return document_service.to_detail(db, doc)


@router.put("/{document_id}/projects", response_model=DocumentDetail)
def set_projects(document_id: int, data: IdList, db: DbSession) -> DocumentDetail:
    doc = document_service.set_projects(db, document_id, data.ids)
    return document_service.to_detail(db, doc)


@router.get("/{document_id}/chunks", response_model=ChunkPage)
def list_chunks(
    document_id: int,
    db: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    page: Annotated[int | None, Query(ge=1)] = None,
) -> ChunkPage:
    return document_service.list_chunks(db, document_id, offset, limit, page)


@router.get("/{document_id}/file")
def get_file(document_id: int, db: DbSession, settings: AppSettings) -> FileResponse:
    doc = document_service.get_document(db, document_id)
    path = document_service.stored_file_path(settings, doc)
    return FileResponse(
        path,
        media_type=doc.mime_type or "application/octet-stream",
        filename=doc.original_filename or path.name,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff"},
    )
