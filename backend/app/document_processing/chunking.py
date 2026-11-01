"""Split extracted pages into overlapping, page-aware chunks for search and RAG.

Chunks follow paragraph and sentence boundaries, never lose page numbers, and
carry the section heading they belong to (e.g. "Methods", "References").
"""

import re
from dataclasses import dataclass

from app.document_processing.metadata import clean_inline
from app.document_processing.types import ChunkData, ExtractedPage

TARGET_CHARS = 1000
OVERLAP_CHARS = 150
MIN_CHUNK_CHARS = 40

KNOWN_SECTIONS = (
    "abstract|introduction|background|related work|literature review|theoretical framework|"
    "method|methods|methodology|materials and methods|data|dataset|datasets|experimental setup|"
    "experiments|results|findings|analysis|discussion|limitations|future work|conclusion|"
    "conclusions|acknowledgements|acknowledgments|references|bibliography|appendix"
)
SECTION_LINE = re.compile(
    rf"^\s*(?:(?:\d+(?:\.\d+)*|[IVX]+)\.?\s+)?({KNOWN_SECTIONS})\s*:?\s*$", re.I
)
MARKDOWN_HEADING = re.compile(r"^\s*#{1,6}\s+(.{1,120})$")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9“\"(\[])")


@dataclass
class _Unit:
    text: str
    page: int | None
    section: str | None


def _heading(line: str) -> str | None:
    if m := MARKDOWN_HEADING.match(line):
        return m.group(1).strip().strip("#").strip()
    if len(line) <= 60 and (m := SECTION_LINE.match(line)):
        return m.group(1).strip().title()
    return None


def _paragraph_units(pages: list[ExtractedPage]) -> list[_Unit]:
    """Group lines into paragraphs (blank-line separated), tracking page and section."""
    units: list[_Unit] = []
    section: str | None = None
    for page in pages:
        buffer: list[str] = []
        # A trailing empty line flushes the last paragraph of the page.
        for line in [*page.text.splitlines(), ""]:
            stripped = line.strip()
            heading = _heading(stripped) if stripped else None
            if stripped and heading is None:
                buffer.append(line)
                continue
            if buffer:
                text = clean_inline("\n".join(buffer))
                if text:
                    units.append(_Unit(text, page.number, section))
                buffer = []
            if heading:
                section = heading
    return units


def _split_long(unit: _Unit, limit: int) -> list[_Unit]:
    if len(unit.text) <= limit:
        return [unit]
    pieces: list[str] = []
    for sentence in SENTENCE_SPLIT.split(unit.text):
        while len(sentence) > limit:  # pathological sentence: hard-split on a space
            cut = sentence.rfind(" ", 0, limit)
            cut = cut if cut > limit // 2 else limit
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            pieces.append(sentence)
    return [_Unit(p, unit.page, unit.section) for p in pieces]


def chunk_pages(
    pages: list[ExtractedPage], target: int = TARGET_CHARS, overlap: int = OVERLAP_CHARS
) -> list[ChunkData]:
    units = [u for unit in _paragraph_units(pages) for u in _split_long(unit, target)]
    chunks: list[ChunkData] = []
    current: list[_Unit] = []

    def emit() -> None:
        text = " ".join(u.text for u in current).strip()
        if len(text) < MIN_CHUNK_CHARS and chunks and chunks[-1].section == current[0].section:
            # Too small to stand alone: merge into the previous chunk of the same section.
            previous = chunks[-1]
            previous.text = f"{previous.text} {text}".strip()
            previous.page_end = (
                current[-1].page if current[-1].page is not None else previous.page_end
            )
            return
        if text:
            chunks.append(
                ChunkData(
                    chunk_index=len(chunks),
                    text=text,
                    page_start=current[0].page,
                    page_end=current[-1].page,
                    section=current[0].section,
                )
            )

    for unit in units:
        size = sum(len(u.text) + 1 for u in current)
        section_changed = bool(current) and unit.section != current[-1].section
        if current and (size + len(unit.text) > target or section_changed):
            emit()
            # Carry trailing units forward as overlap, unless we crossed into a new section.
            carried: list[_Unit] = []
            if not section_changed:
                for previous in reversed(current):
                    if sum(len(u.text) for u in carried) + len(previous.text) > overlap:
                        break
                    carried.insert(0, previous)
            current = carried
        current.append(unit)
    if current:
        emit()
    return chunks
