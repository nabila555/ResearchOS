"""Unit tests for the document processing pipeline (no database)."""

from pathlib import Path

import httpx
import pytest

from app.document_processing import metadata as md
from app.document_processing import storage
from app.document_processing.chunking import chunk_pages
from app.document_processing.extractors import extract, extract_html, extract_plain_text
from app.document_processing.types import (
    ExtractedPage,
    ExtractionError,
    InvalidFileError,
    UnsupportedFileTypeError,
)
from app.document_processing.validation import detect_type, sanitize_filename, verify_content
from app.document_processing.web import (
    FetchError,
    UnsafeUrlError,
    fetch_url,
    validate_public_url,
)
from app.models.library import DocumentType
from tests.fixtures.samples import ABSTRACT, PAPER_AUTHORS, PAPER_TITLE, write_docx, write_paper_pdf

PUBLIC = lambda _host: ["93.184.216.34"]  # noqa: E731


# --- Metadata heuristics -------------------------------------------------------------


def test_find_doi_strips_trailing_punctuation() -> None:
    assert md.find_doi("see https://doi.org/10.1038/NATURE12345.") == "10.1038/nature12345"
    assert md.find_doi("no identifier here") is None


@pytest.mark.parametrize(
    ("text", "year"),
    [
        ("Published online: 3 May 2019", 2019),
        ("© 2015 Elsevier Ltd. All rights reserved.", 2015),
        ("arXiv:2103.00020v1 [cs.CV]", 2021),
        ("Received 2017; accepted 2018", 2018),
        ("We sampled 2000 participants", None),  # a bare number is not a year
        ("© 2999 Future Press", None),
    ],
)
def test_find_year(text: str, year: int | None) -> None:
    assert md.find_year(text) == year


def test_parse_author_line_accepts_names_with_affiliation_marks() -> None:
    assert md.parse_author_line("Ada Lovelace1, Alan M. Turing2 and Grace Hopper*") == PAPER_AUTHORS


@pytest.mark.parametrize(
    "line",
    [
        "Department of Psychology, Example University",
        "Results suggest that sleep matters",
        "ada@example.org",
    ],
)
def test_parse_author_line_rejects_non_names(line: str) -> None:
    assert md.parse_author_line(line) == []


def test_split_author_field() -> None:
    assert md.split_author_field("Smith, J.; Doe, A.") == ["Smith, J.", "Doe, A."]
    assert md.split_author_field("Ada Lovelace and Alan Turing") == ["Ada Lovelace", "Alan Turing"]


def test_references_numbered_and_author_year() -> None:
    numbered = (
        "Body text.\n" * 50
        + "References\n[1] A. Author. A title. 2020.\n[2] B. Author. Another title. 2021.\n"
    )
    assert len(md.find_references(numbered)) == 2
    author_year = (
        "Body.\n" * 50
        + "References\nSmith, J. (2020). A long title about sleep. Journal.\n"
        + "Doe, A. (2019). Another paper on memory. Journal.\n"
    )
    assert [r[:5] for r in md.find_references(author_year)] == ["Smith", "Doe, "]


def test_no_references_without_heading() -> None:
    assert md.find_references("Just text with [1] a citation.") == []


def test_plausible_title_rejects_junk() -> None:
    assert not md.is_plausible_title("Microsoft Word - draft3.docx")
    assert not md.is_plausible_title("untitled")
    assert md.is_plausible_title(PAPER_TITLE)


# --- Extraction ------------------------------------------------------------------------


def test_pdf_extraction_from_layout(tmp_path: Path) -> None:
    result = extract(write_paper_pdf(tmp_path / "p.pdf"), DocumentType.PDF, "fallback")
    assert result.title == PAPER_TITLE
    assert result.authors == PAPER_AUTHORS
    assert result.publication_year == 2021
    assert result.doi == "10.1234/jsr.2021.0042"
    assert result.abstract and result.abstract.startswith(ABSTRACT[:40])
    assert result.keywords == ["sleep spindles", "memory consolidation", "EEG"]
    assert len(result.reference_list) == 3
    assert result.page_count == 4
    assert result.metadata_sources["title"] == "heuristic"


def test_pdf_metadata_preferred_when_plausible(tmp_path: Path) -> None:
    result = extract(write_paper_pdf(tmp_path / "p.pdf", with_metadata=True), DocumentType.PDF, "x")
    assert result.metadata_sources["title"] == "pdf_metadata"
    assert result.authors == PAPER_AUTHORS


def test_damaged_pdf_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"%PDF-1.7\nthis is not really a pdf")
    with pytest.raises(ExtractionError):
        extract(path, DocumentType.PDF, "x")


def test_docx_extraction(tmp_path: Path) -> None:
    result = extract(write_docx(tmp_path / "d.docx"), DocumentType.DOCX, "x")
    assert result.title == "Field Notes on Coral Bleaching"
    assert result.authors == ["Rachel Carson"]
    assert "Reef | Bleached %" in result.full_text
    assert result.pages[0].number is None


def test_markdown_front_matter() -> None:
    text = (
        "---\ntitle: Notes on Attention\nauthors:\n  - Ada Lovelace\n  - Alan Turing\n"
        "year: 2017\ntags: [transformers, nlp]\n---\n# Heading\nBody text.\n"
    )
    result = extract_plain_text(text, markdown=True)
    assert result.title == "Notes on Attention"
    assert result.authors == ["Ada Lovelace", "Alan Turing"]
    assert result.publication_year == 2017
    assert result.keywords == ["transformers", "nlp"]
    assert "title:" not in result.full_text


def test_html_citation_meta_and_boilerplate_removed() -> None:
    html = """<html><head><title>Site | Paper</title>
    <meta name="citation_title" content="Deep Sleep and Memory">
    <meta name="citation_author" content="Lovelace, Ada">
    <meta name="citation_author" content="Turing, Alan">
    <meta name="citation_publication_date" content="2020/05/01">
    <meta name="citation_doi" content="10.5555/abc.123">
    <meta name="citation_journal_title" content="Journal of Sleep">
    </head><body><nav>Home | About</nav><article><h1>Deep Sleep and Memory</h1>
    <p>Slow waves support consolidation.</p></article><footer>Cookie policy</footer>
    <script>alert(1)</script></body></html>"""
    result = extract_html(html)
    assert result.title == "Deep Sleep and Memory"
    assert result.authors == ["Lovelace, Ada", "Turing, Alan"]
    assert result.publication_year == 2020
    assert result.doi == "10.5555/abc.123"
    assert result.venue == "Journal of Sleep"
    assert "Slow waves support consolidation." in result.full_text
    for junk in ("Home | About", "Cookie policy", "alert(1)"):
        assert junk not in result.full_text


# --- Chunking ----------------------------------------------------------------------------


def test_chunks_keep_pages_and_sections() -> None:
    sentence = "Spindles were counted in every night of recording for each participant. "
    pages = [
        ExtractedPage(1, "1 Introduction\n" + sentence * 5),
        ExtractedPage(2, "2 Methods\n" + sentence * 30),
        ExtractedPage(3, "References\n[1] Someone. A paper. 2020."),
    ]
    chunks = chunk_pages(pages, target=600, overlap=100)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert chunks[0].section == "Introduction" and chunks[0].page_start == 1
    methods = [c for c in chunks if c.section == "Methods"]
    assert len(methods) >= 3 and all(c.page_start == 2 for c in methods)
    assert all(len(c.text) <= 600 + 100 for c in chunks)
    assert chunks[-1].section == "References" and chunks[-1].page_start == 3
    # Consecutive chunks within a section overlap.
    assert methods[1].text[:40] in methods[0].text


def test_chunking_empty_input() -> None:
    assert chunk_pages([ExtractedPage(1, "   \n\n ")]) == []


# --- Validation & storage ---------------------------------------------------------------


def test_detect_type_and_sanitize() -> None:
    assert detect_type("Paper.PDF") is DocumentType.PDF
    with pytest.raises(UnsupportedFileTypeError):
        detect_type("malware.exe")
    assert sanitize_filename("..\\..\\etc/passwd") == "passwd"
    assert sanitize_filename("a\x00b.pdf") == "ab.pdf"


def test_verify_content_rejects_mismatched_bytes(tmp_path: Path) -> None:
    fake_pdf = tmp_path / "x.pdf"
    fake_pdf.write_bytes(b"MZ\x90\x00 not a pdf")
    with pytest.raises(InvalidFileError):
        verify_content(fake_pdf, DocumentType.PDF)
    fake_docx = tmp_path / "x.docx"
    fake_docx.write_text("plain text")
    with pytest.raises(InvalidFileError):
        verify_content(fake_docx, DocumentType.DOCX)
    binary_txt = tmp_path / "x.txt"
    binary_txt.write_bytes(b"abc\x00def")
    with pytest.raises(InvalidFileError):
        verify_content(binary_txt, DocumentType.TEXT)


def test_storage_rejects_path_escape(tmp_path: Path) -> None:
    with pytest.raises(storage.UnsafePathError):
        storage.resolve_stored_path(tmp_path, "../outside.pdf")
    with pytest.raises(storage.UnsafePathError):
        storage.store_file(tmp_path / "a", tmp_path, "../" + "a" * 61, ".pdf")


# --- URL safety ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost:8000/api",
        "http://10.0.0.5/",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/",
        "file:///etc/passwd",
        "ftp://example.org/x",
        "http://user:pass@example.org/",
    ],
)
def test_validate_public_url_rejects_unsafe(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        validate_public_url(url)


def test_fetch_blocks_redirect_to_private_address() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://internal.example/"})

    def resolver(host: str) -> list[str]:
        return ["10.1.2.3"] if host == "internal.example" else ["93.184.216.34"]

    with pytest.raises(UnsafeUrlError):
        fetch_url(
            "https://example.org/",
            max_bytes=10_000,
            transport=httpx.MockTransport(handler),
            resolver=resolver,
        )


def test_fetch_enforces_size_and_type() -> None:
    big = httpx.MockTransport(
        lambda r: httpx.Response(200, headers={"content-type": "text/html"}, content=b"x" * 5000)
    )
    with pytest.raises(FetchError, match="larger"):
        fetch_url("https://example.org/", max_bytes=1000, transport=big, resolver=PUBLIC)
    image = httpx.MockTransport(
        lambda r: httpx.Response(200, headers={"content-type": "image/png"}, content=b"\x89PNG")
    )
    with pytest.raises(FetchError, match="Unsupported content type"):
        fetch_url("https://example.org/a.png", max_bytes=1000, transport=image, resolver=PUBLIC)
