"""SQLAlchemy ORM models. Importing this package registers every table."""

from app.models.activity import Activity
from app.models.ai import (
    AppSetting,
    ChatMessage,
    ChatSession,
    ChunkEmbedding,
    IndexJob,
    IndexStatus,
    JobStatus,
)
from app.models.library import (
    Author,
    Chunk,
    Collection,
    Document,
    DocumentAuthor,
    DocumentStatus,
    DocumentType,
    Tag,
    collection_documents,
    document_tags,
)
from app.models.project import Project, ProjectStatus, project_documents
from app.models.report import Report

__all__ = [
    "Activity",
    "AppSetting",
    "ChatMessage",
    "ChatSession",
    "ChunkEmbedding",
    "IndexJob",
    "IndexStatus",
    "JobStatus",
    "Author",
    "Chunk",
    "Collection",
    "Document",
    "DocumentAuthor",
    "DocumentStatus",
    "DocumentType",
    "Project",
    "ProjectStatus",
    "Report",
    "Tag",
    "collection_documents",
    "document_tags",
    "project_documents",
]
