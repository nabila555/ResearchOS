"""Content-addressed file storage inside DATA_DIR/documents.

Files are stored as ``<sha256[:2]>/<sha256><ext>``. User-supplied names never
become paths, and every resolved path is checked to stay inside the store.
"""

import hashlib
import shutil
from pathlib import Path


class UnsafePathError(ValueError):
    pass


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def store_file(source: Path, documents_dir: Path, sha256: str, extension: str) -> str:
    """Move ``source`` into the store and return its path relative to ``documents_dir``."""
    if len(sha256) != 64 or not all(c in "0123456789abcdef" for c in sha256):
        raise UnsafePathError("invalid content hash")
    if extension not in {".pdf", ".docx", ".txt", ".md", ".markdown"}:
        raise UnsafePathError("invalid extension")
    relative = f"{sha256[:2]}/{sha256}{extension}"
    target = resolve_stored_path(documents_dir, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        source.unlink(missing_ok=True)
    else:
        shutil.move(str(source), target)
    return relative


def resolve_stored_path(documents_dir: Path, relative: str) -> Path:
    root = documents_dir.resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise UnsafePathError("path escapes the document store")
    return candidate


def delete_stored_file(documents_dir: Path, relative: str | None) -> None:
    if not relative:
        return
    try:
        path = resolve_stored_path(documents_dir, relative)
        path.unlink(missing_ok=True)
        if path.parent != documents_dir.resolve() and not any(path.parent.iterdir()):
            path.parent.rmdir()  # remove the now-empty hash-prefix folder
    except (UnsafePathError, OSError):
        pass
