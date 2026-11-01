from dataclasses import dataclass, field


class ProcessingError(Exception):
    """Base class for errors shown to the user (messages must be safe to display)."""


class UnsupportedFileTypeError(ProcessingError):
    pass


class FileTooLargeError(ProcessingError):
    pass


class InvalidFileError(ProcessingError):
    pass


class ExtractionError(ProcessingError):
    pass


@dataclass
class ExtractedPage:
    # 1-based page number; None for formats without pages (DOCX, Markdown, web).
    number: int | None
    text: str


@dataclass
class ExtractedDocument:
    """Text and metadata found in a document.

    Metadata fields stay ``None``/empty when they could not be found. They are
    never guessed. ``metadata_sources`` records where each populated field came
    from (e.g. ``pdf_metadata``, ``heuristic``, ``citation_meta``) so the UI can
    ask the user to verify heuristic values.
    """

    pages: list[ExtractedPage]
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    publication_year: int | None = None
    abstract: str | None = None
    keywords: list[str] = field(default_factory=list)
    doi: str | None = None
    venue: str | None = None
    reference_list: list[str] = field(default_factory=list)
    page_count: int | None = None
    metadata_sources: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)

    def set(self, name: str, value: object, source: str) -> None:
        """Set a metadata field only if it is still empty and the value is non-empty."""
        if value in (None, "", []) or getattr(self, name) not in (None, "", []):
            return
        setattr(self, name, value)
        self.metadata_sources[name] = source


@dataclass
class ChunkData:
    chunk_index: int
    text: str
    page_start: int | None
    page_end: int | None
    section: str | None
