"""Text and metadata extraction for each supported format."""

import re
from pathlib import Path

import docx
import pymupdf
from bs4 import BeautifulSoup

from app.document_processing import metadata as md
from app.document_processing.types import ExtractedDocument, ExtractedPage, ExtractionError
from app.models.library import DocumentType

# Pages scanned for front-matter metadata (title, authors, abstract...).
FRONT_MATTER_PAGES = 3


def extract(path: Path, doc_type: DocumentType, fallback_title: str) -> ExtractedDocument:
    if doc_type is DocumentType.PDF:
        result = extract_pdf(path)
    elif doc_type is DocumentType.DOCX:
        result = extract_docx(path)
    elif doc_type in (DocumentType.TEXT, DocumentType.MARKDOWN):
        result = extract_plain_text(
            read_text_file(path), markdown=doc_type is DocumentType.MARKDOWN
        )
    else:
        raise ExtractionError(f"No extractor for {doc_type}")
    finalize(result, fallback_title)
    return result


def finalize(result: ExtractedDocument, fallback_title: str) -> None:
    """Apply text heuristics for fields the format-specific extractor didn't find."""
    front = "\n\n".join(p.text for p in result.pages[:FRONT_MATTER_PAGES])
    result.set("doi", md.find_doi(front), "heuristic")
    result.set("publication_year", md.find_year(front), "heuristic")
    result.set("abstract", md.find_abstract(front), "heuristic")
    result.set("keywords", md.find_keywords(front), "heuristic")
    result.set("reference_list", md.find_references(result.full_text), "heuristic")
    if not result.title:
        result.title = fallback_title
        result.metadata_sources["title"] = "filename"
    if not result.full_text.strip():
        result.warnings.append(
            "No text could be extracted. If this is a scanned document it needs OCR, "
            "which is not supported yet."
        )


# --- PDF -----------------------------------------------------------------------


def _pdf_title_from_layout(page: pymupdf.Page) -> str | None:
    """The largest text on the upper part of page 1 is usually the title."""
    data = page.get_text("dict")
    height = page.rect.height or 1
    spans: list[tuple[float, float, str]] = []  # (size, y, text)
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                y = span.get("bbox", [0, 0, 0, 0])[1]
                if len(text) >= 2 and y < height * 0.6:
                    spans.append((round(span.get("size", 0), 1), y, text))
    if not spans:
        return None
    max_size = max(s[0] for s in spans)
    body_sizes = sorted(s[0] for s in spans)
    median = body_sizes[len(body_sizes) // 2]
    if max_size < median * 1.15:  # no clearly emphasised title text
        return None
    title_spans = sorted((s for s in spans if s[0] >= max_size - 0.6), key=lambda s: s[1])
    # Keep only spans close together vertically (a multi-line title, not scattered labels).
    first_y = title_spans[0][1]
    parts = [t for _, y, t in title_spans if y - first_y < max_size * 4]
    title = md.clean_inline(" ".join(parts))
    return title if md.is_plausible_title(title) else None


def _pdf_authors_from_layout(first_page_text: str, title: str | None) -> list[str]:
    """Look for a line of personal names right below the title."""
    lines = [line.strip() for line in first_page_text.splitlines() if line.strip()]
    start = 0
    if title:
        # Start searching after the last of the first 15 lines that belongs to the title.
        title_words = set(title.lower().split())
        for index, line in enumerate(lines[:15]):
            words = set(line.lower().split())
            if words and len(words & title_words) / len(words) >= 0.6:
                start = index + 1
    for line in lines[start : start + 6]:
        if re.match(r"\s*abstract\b", line, re.I):
            break
        names = md.parse_author_line(line)
        if names:
            return names
    return []


def extract_pdf(path: Path) -> ExtractedDocument:
    try:
        document = pymupdf.open(path)
    except Exception as exc:  # PyMuPDF raises several internal error types
        raise ExtractionError("The PDF could not be opened; it may be damaged.") from exc
    with document:
        if document.needs_pass:
            raise ExtractionError("The PDF is password-protected. Remove the password and retry.")
        pages = [
            ExtractedPage(number=i + 1, text=page.get_text("text"))
            for i, page in enumerate(document)
        ]
        result = ExtractedDocument(pages=pages, page_count=document.page_count)
        info = document.metadata or {}

        if md.is_plausible_title(info.get("title")):
            result.set("title", md.clean_inline(info["title"]), "pdf_metadata")
        elif document.page_count:
            result.set("title", _pdf_title_from_layout(document[0]), "heuristic")

        if md.is_plausible_author_field(info.get("author")):
            result.set("authors", md.split_author_field(info["author"]), "pdf_metadata")
        elif pages:
            result.set(
                "authors", _pdf_authors_from_layout(pages[0].text, result.title), "heuristic"
            )

        keywords = info.get("keywords") or ""
        if keywords.strip():
            parts = [k.strip() for k in re.split(r"[;,]", keywords) if 2 <= len(k.strip()) <= 60]
            result.set("keywords", parts[:15], "pdf_metadata")
        result.set("doi", md.find_doi(info.get("subject") or ""), "pdf_metadata")
    return result


# --- DOCX ----------------------------------------------------------------------


def extract_docx(path: Path) -> ExtractedDocument:
    try:
        document = docx.Document(str(path))
    except Exception as exc:
        raise ExtractionError("The Word document could not be read; it may be damaged.") from exc

    lines: list[str] = []
    styled_title: str | None = None
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style = (paragraph.style.name if paragraph.style is not None else "") or ""
        if styled_title is None and style.lower().startswith(("title", "heading 1")):
            styled_title = text
        # Mark headings with "#" so the chunker can track sections.
        lines.append(f"# {text}" if style.lower().startswith("heading") else text)
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                lines.append(" | ".join(dict.fromkeys(cells)))

    result = ExtractedDocument(pages=[ExtractedPage(number=None, text="\n\n".join(lines))])
    props = document.core_properties
    if md.is_plausible_title(props.title):
        result.set("title", props.title.strip(), "document_properties")
    elif md.is_plausible_title(styled_title):
        result.set("title", styled_title, "heuristic")
    if md.is_plausible_author_field(props.author):
        result.set("authors", md.split_author_field(props.author), "document_properties")
    if props.keywords:
        parts = [k.strip() for k in re.split(r"[;,]", props.keywords) if k.strip()]
        result.set("keywords", parts[:15], "document_properties")
    return result


# --- Plain text & Markdown -----------------------------------------------------


def read_text_file(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def _parse_front_matter(block: str) -> dict[str, str | list[str]]:
    """Minimal YAML front-matter reader: `key: value`, `key: [a, b]`, and `- item` lists."""
    data: dict[str, str | list[str]] = {}
    current: str | None = None
    for line in block.splitlines():
        item = re.match(r"^\s+-\s+(.+)$", line)
        if item and current:
            existing = data.get(current)
            values = existing if isinstance(existing, list) else []
            values.append(item.group(1).strip().strip("\"'"))
            data[current] = values
            continue
        pair = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if pair:
            current = pair.group(1).lower()
            value = pair.group(2).strip()
            if value.startswith("[") and value.endswith("]"):
                data[current] = [
                    v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()
                ]
            elif value:
                data[current] = value.strip("\"'")
    return data


def _as_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if v]
    return [v.strip() for v in re.split(r"[;,]", value) if v.strip()]


def extract_plain_text(text: str, *, markdown: bool) -> ExtractedDocument:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    result = ExtractedDocument(pages=[])
    if markdown:
        match = FRONT_MATTER.match(text)
        if match:
            meta = _parse_front_matter(match.group(1))
            text = text[match.end() :]
            title = meta.get("title")
            if isinstance(title, str) and md.is_plausible_title(title):
                result.set("title", title, "front_matter")
            authors = meta.get("authors", meta.get("author"))
            result.set("authors", _as_list(authors), "front_matter")
            for key in ("year", "date", "published"):
                value = meta.get(key)
                if isinstance(value, str) and md.year_from_date_string(value):
                    result.set("publication_year", md.year_from_date_string(value), "front_matter")
                    break
            result.set(
                "keywords", _as_list(meta.get("keywords", meta.get("tags")))[:15], "front_matter"
            )
            doi = meta.get("doi")
            if isinstance(doi, str):
                result.set("doi", md.find_doi(doi), "front_matter")
        heading = re.search(r"^#\s+(.+)$", text, re.M)
        if heading and md.is_plausible_title(heading.group(1).strip()):
            result.set("title", heading.group(1).strip(), "heuristic")
    else:
        first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        if md.is_plausible_title(first_line) and len(first_line) <= 200:
            result.set("title", first_line, "heuristic")
    result.pages = [ExtractedPage(number=None, text=text)]
    return result


# --- HTML (web articles) --------------------------------------------------------

STRIP_TAGS = [
    "script",
    "style",
    "noscript",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "svg",
    "iframe",
    "button",
    "template",
]


def _meta(soup: BeautifulSoup, *names: str) -> list[str]:
    values: list[str] = []
    for name in names:
        for tag in soup.find_all("meta", attrs={"name": name}) + soup.find_all(
            "meta", attrs={"property": name}
        ):
            content = (tag.get("content") or "").strip()
            if content:
                values.append(content)
    return values


def extract_html(html: str | bytes) -> ExtractedDocument:
    # Bytes let BeautifulSoup detect the encoding from <meta charset> / BOM.
    soup = BeautifulSoup(html, "lxml")
    result = ExtractedDocument(pages=[])

    # Highwire Press "citation_*" tags are used by most scholarly publishers and
    # repositories (Google Scholar inclusion guidelines), so prefer them.
    for title in _meta(soup, "citation_title", "dc.title", "DC.title"):
        result.set("title", md.clean_inline(title), "citation_meta")
    result.set(
        "authors", [md.clean_inline(a) for a in _meta(soup, "citation_author")], "citation_meta"
    )
    for date in _meta(
        soup,
        "citation_publication_date",
        "citation_date",
        "citation_online_date",
        "dc.date",
        "DC.date",
        "article:published_time",
    ):
        if md.year_from_date_string(date):
            result.set("publication_year", md.year_from_date_string(date), "citation_meta")
            break
    for doi in _meta(soup, "citation_doi", "dc.identifier", "DC.identifier"):
        result.set("doi", md.find_doi(doi), "citation_meta")
    for abstract in _meta(soup, "citation_abstract"):
        result.set("abstract", md.clean_inline(abstract), "citation_meta")
    keywords = [k for v in _meta(soup, "citation_keywords") for k in re.split(r"[;,]", v)]
    result.set("keywords", [k.strip() for k in keywords if k.strip()][:15], "citation_meta")
    for venue in _meta(soup, "citation_journal_title", "citation_conference_title"):
        result.set("venue", md.clean_inline(venue), "citation_meta")
    result.set(
        "reference_list",
        [md.clean_inline(r) for r in _meta(soup, "citation_reference")],
        "citation_meta",
    )

    if not result.title:
        for candidate in _meta(soup, "og:title") + [soup.title.string if soup.title else ""]:
            if candidate and md.is_plausible_title(candidate.strip()):
                result.set("title", md.clean_inline(candidate), "page_title")
                break
    if not result.authors:
        result.set(
            "authors", md.split_author_field(next(iter(_meta(soup, "author")), None)), "page_meta"
        )

    for tag in soup(STRIP_TAGS):
        tag.decompose()
    root = (
        soup.find("article")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.body
        or soup
    )
    for heading in root.find_all(["h1", "h2", "h3", "h4"]):
        heading.insert_before("\n# ")
    text = root.get_text("\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*(\n\s*)+", "\n\n", text).strip()
    result.pages = [ExtractedPage(number=None, text=text)]
    return result
