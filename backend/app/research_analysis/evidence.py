"""Excerpt selection from a paper and verification of model-provided evidence."""

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from app.models.library import Chunk

_NON_WORD = re.compile(r"[^0-9a-z]+")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
REFERENCE_SECTIONS = {"references", "bibliography", "works cited", "literature cited"}
QUOTE_WORD_OVERLAP = 0.85


@dataclass
class Excerpt:
    n: int
    chunk_id: int
    page_start: int | None
    page_end: int | None
    section: str | None
    text: str


@dataclass(frozen=True)
class Focus:
    """Which parts of a paper an extraction step needs."""

    sections: tuple[str, ...]
    keywords: tuple[str, ...]
    prefer_start: bool = False


def normalize(text: str) -> str:
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text.lower())  # join hyphenated line breaks
    return _NON_WORD.sub(" ", text).strip()


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(text)}


def quote_supported(quote: str, passage: str) -> bool:
    """True if ``quote`` appears in ``passage`` (verbatim, or near-verbatim for small models)."""
    q, p = normalize(quote), normalize(passage)
    words = q.split()
    if len(words) < 3:
        return False
    if q in p:
        return True
    passage_words = set(p.split())
    found = sum(1 for w in words if w in passage_words)
    return found / len(words) >= QUOTE_WORD_OVERLAP


def check_statement(text: str, quote: str, excerpt: Excerpt | None) -> tuple[bool, str | None]:
    """Verify one model statement against the excerpt it cites. Returns (verified, reason)."""
    if excerpt is None:
        return False, "cites an excerpt that was not provided"
    if not quote_supported(quote, excerpt.text):
        return False, "quote not found in the cited excerpt"
    missing = _numbers(text) - _numbers(excerpt.text)
    if missing:
        return False, f"number {sorted(missing)[0]} does not appear in the cited excerpt"
    return True, None


def is_reference_chunk(chunk: Chunk) -> bool:
    return (chunk.section or "").strip().lower() in REFERENCE_SECTIONS


def select_excerpts(chunks: list[Chunk], focus: Focus, budget_chars: int) -> list[Excerpt]:
    """Pick the chunks most relevant to ``focus`` within a character budget, in reading order."""
    usable = [c for c in chunks if not is_reference_chunk(c)]
    if sum(len(c.text) for c in usable) <= budget_chars:
        chosen = usable
    else:

        def score(chunk: Chunk) -> float:
            section = (chunk.section or "").lower()
            text = chunk.text.lower()
            value = 5.0 if any(s in section for s in focus.sections) else 0.0
            value += sum(1 for k in focus.keywords if k in text)
            if focus.prefer_start and chunk.chunk_index < 2:
                value += 3
            return value

        chosen = []
        remaining = budget_chars
        for chunk in sorted(usable, key=lambda c: (-score(c), c.chunk_index)):
            if len(chunk.text) <= remaining:
                chosen.append(chunk)
                remaining -= len(chunk.text)
            if remaining < 200:
                break
    chosen.sort(key=lambda c: c.chunk_index)
    return [
        Excerpt(i + 1, c.id, c.page_start, c.page_end, c.section, c.text)
        for i, c in enumerate(chosen)
    ]


def format_excerpts(excerpts: list[Excerpt]) -> str:
    blocks = []
    for e in excerpts:
        where = []
        if e.page_start is not None:
            where.append(
                f"p. {e.page_start}"
                if e.page_end in (None, e.page_start)
                else f"pp. {e.page_start}-{e.page_end}"
            )
        if e.section:
            where.append(e.section)
        label = f" ({', '.join(where)})" if where else ""
        blocks.append(f"[{e.n}]{label}\n{e.text}")
    return "\n\n".join(blocks)


def evidence_record(
    excerpt: Excerpt | None, quote: str, verified: bool, reason: str | None
) -> dict[str, Any]:
    return {
        "chunk_id": excerpt.chunk_id if excerpt else None,
        "page_start": excerpt.page_start if excerpt else None,
        "page_end": excerpt.page_end if excerpt else None,
        "section": excerpt.section if excerpt else None,
        "quote": quote.strip()[:400],
        "verified": verified,
        "reason": reason,
    }


def chunk_signature(chunks: list[Chunk]) -> str:
    """Fingerprint of a document's text. Hashes content, not ids: SQLite reuses row ids."""
    digest = hashlib.sha1()
    for chunk in sorted(chunks, key=lambda c: c.chunk_index):
        digest.update(chunk.text.encode("utf-8"))
        digest.update(b"")
    return digest.hexdigest()
