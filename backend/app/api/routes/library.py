from fastapi import APIRouter, Response, status

from app.api.deps import DbSession
from app.schemas.library import (
    CollectionCreate,
    CollectionRead,
    CollectionUpdate,
    LibraryFacets,
    TagRead,
)
from app.services import library_service

router = APIRouter(tags=["library"])


@router.get("/library/facets", response_model=LibraryFacets)
def facets(db: DbSession) -> LibraryFacets:
    return library_service.facets(db)


@router.get("/collections", response_model=list[CollectionRead])
def list_collections(db: DbSession) -> list[CollectionRead]:
    return library_service.list_collections(db)


@router.post("/collections", response_model=CollectionRead, status_code=status.HTTP_201_CREATED)
def create_collection(data: CollectionCreate, db: DbSession) -> CollectionRead:
    return library_service.create_collection(db, data)


@router.patch("/collections/{collection_id}", response_model=CollectionRead)
def update_collection(collection_id: int, data: CollectionUpdate, db: DbSession) -> CollectionRead:
    return library_service.update_collection(db, collection_id, data)


@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(collection_id: int, db: DbSession) -> Response:
    library_service.delete_collection(db, collection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tags", response_model=list[TagRead])
def list_tags(db: DbSession) -> list[TagRead]:
    return library_service.list_tags(db)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: int, db: DbSession) -> Response:
    library_service.delete_tag(db, tag_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
