"""Upload validation: extension allow-list, content sniffing, and size limits."""

import re
import unicodedata
import zipfile
from pathlib import Path, PurePath

from app.document_processing.types import (
    FileTooLargeError,
    InvalidFileError,
    UnsupportedFileTypeError,
)
from app.models.library import DocumentType

ALLOWED_EXTENSIONS: dict[str, DocumentType] = {
    ".pdf": DocumentType.PDF,
    ".docx": DocumentType.DOCX,
    ".txt": DocumentType.TEXT,
    ".md": DocumentType.MARKDOWN,
    ".markdown": DocumentType.MARKDOWN,
}

MIME_TYPES: dict[DocumentType, str] = {
    DocumentType.PDF: "application/pdf",
    DocumentType.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    DocumentType.TEXT: "text/plain",
    DocumentType.MARKDOWN: "text/markdown",
}

# Guard against zip bombs disguised as .docx.
MAX_DOCX_UNCOMPRESSED_BYTES = 300 * 1024 * 1024


def sanitize_filename(name: str | None) -> str:
    """Display-safe base filename. Never used to build a filesystem path."""
    base = PurePath((name or "").replace("\\", "/")).name
    base = "".join(ch for ch in base if unicodedata.category(ch)[0] != "C")
    base = re.sub(r"\s+", " ", base).strip()
    return base[:255] or "untitled"


def detect_type(filename: str) -> DocumentType:
    suffix = PurePath(filename).suffix.lower()
    try:
        return ALLOWED_EXTENSIONS[suffix]
    except KeyError:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise UnsupportedFileTypeError(
            f"Unsupported file type “{suffix or 'none'}”. Allowed: {allowed}."
        ) from None


def check_size(size: int, max_bytes: int) -> None:
    if size > max_bytes:
        raise FileTooLargeError(
            f"File is {size / 1_048_576:.1f} MB; the limit is {max_bytes / 1_048_576:.0f} MB."
        )
    if size == 0:
        raise InvalidFileError("The file is empty.")


def verify_content(path: Path, doc_type: DocumentType) -> None:
    """Check that the bytes match the claimed type (don't trust the extension)."""
    with path.open("rb") as fh:
        head = fh.read(65536)

    if doc_type is DocumentType.PDF:
        if b"%PDF-" not in head[:1024]:
            raise InvalidFileError("This file does not look like a valid PDF.")
    elif doc_type is DocumentType.DOCX:
        if not zipfile.is_zipfile(path):
            raise InvalidFileError("This file does not look like a valid Word (.docx) document.")
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if "word/document.xml" not in {i.filename for i in infos}:
                raise InvalidFileError("This archive is not a Word (.docx) document.")
            if sum(i.file_size for i in infos) > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise InvalidFileError("This Word document expands to an unsafe size.")
    elif b"\x00" in head:
        raise InvalidFileError("This file appears to be binary, not plain text.")
