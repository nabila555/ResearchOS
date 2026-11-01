from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.library import DocumentStatus, DocumentType


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


class TagRef(BaseModel):
    id: int
    name: str


class CollectionRef(BaseModel):
    id: int
    name: str


class ProjectRef(BaseModel):
    id: int
    name: str


class DocumentSummary(BaseModel):
    id: int
    title: str
    doc_type: DocumentType
    status: DocumentStatus
    authors: list[str]
    publication_year: int | None
    venue: str | None
    page_count: int | None
    tags: list[TagRef]
    has_file: bool
    source_url: str | None
    created_at: datetime
    # Present only for search results.
    snippet: str | None = None
    match_page: int | None = None


class DocumentDetail(DocumentSummary):
    abstract: str | None
    keywords: list[str]
    doi: str | None
    original_filename: str | None
    file_size: int | None
    mime_type: str | None
    reference_list: list[str]
    note_body: str | None
    language: str | None
    chunk_count: int
    collections: list[CollectionRef]
    projects: list[ProjectRef]
    metadata_sources: dict[str, str]
    warnings: list[str]
    error_message: str | None
    updated_at: datetime


class DocumentPage(BaseModel):
    items: list[DocumentSummary]
    total: int
    offset: int
    limit: int


SortOption = Literal["relevance", "added", "title", "year"]


class AttachmentOptions(BaseModel):
    """Optional organisation applied while importing."""

    collection_ids: list[int] = Field(default_factory=list, max_length=50)
    project_ids: list[int] = Field(default_factory=list, max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=50)


class UrlImport(AttachmentOptions):
    url: str = Field(min_length=4, max_length=2000)

    _strip_url = field_validator("url", mode="before")(_strip)


class NoteCreate(AttachmentOptions):
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(default="", max_length=500_000)

    _strip_title = field_validator("title", mode="before")(_strip)


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    authors: list[str] | None = Field(default=None, max_length=200)
    publication_year: int | None = Field(default=None, ge=1000, le=2100)
    venue: str | None = Field(default=None, max_length=500)
    doi: str | None = Field(default=None, max_length=255)
    abstract: str | None = Field(default=None, max_length=20_000)
    keywords: list[str] | None = Field(default=None, max_length=50)
    note_body: str | None = Field(default=None, max_length=500_000)

    _strip_fields = field_validator("title", "venue", "doi", "abstract", mode="before")(_strip)


class NameList(BaseModel):
    names: list[str] = Field(max_length=50)


class IdList(BaseModel):
    ids: list[int] = Field(max_length=200)


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chunk_index: int
    page_start: int | None
    page_end: int | None
    section: str | None
    text: str


class ChunkPage(BaseModel):
    items: list[ChunkRead]
    total: int


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)

    _strip_fields = field_validator("name", "description", mode="before")(_strip)


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)

    _strip_fields = field_validator("name", "description", mode="before")(_strip)


class CollectionRead(BaseModel):
    id: int
    name: str
    description: str | None
    document_count: int
    created_at: datetime


class TagRead(BaseModel):
    id: int
    name: str
    document_count: int


class FacetCount(BaseModel):
    value: str
    count: int


class LibraryFacets(BaseModel):
    total: int
    types: list[FacetCount]
    years: list[FacetCount]
    authors: list[FacetCount]
    tags: list[TagRead]
    collections: list[CollectionRead]
