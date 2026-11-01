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
from app.models.analysis import Analysis, AnalysisKind, AnalysisStatus, PaperProfile
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
from app.models.review import LiteratureReview, ReviewTheme, ReviewThemeItem

__all__ = [
    "Activity",
    "Analysis",
    "AnalysisKind",
    "AnalysisStatus",
    "PaperProfile",
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
    "LiteratureReview",
    "Report",
    "ReviewTheme",
    "ReviewThemeItem",
    "Tag",
    "collection_documents",
    "document_tags",
    "project_documents",
]
