"""Conservative heuristics for scholarly metadata in extracted text.

Each function returns ``None``/``[]`` when it is not confident. A wrong value is
worse than a missing one, because missing values are visible and editable while
wrong ones silently propagate into citations.
"""

import re
from datetime import UTC, datetime

_WS = re.compile(r"\s+")
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>{}|\\^`]+)", re.IGNORECASE)

_YEAR = r"((?:19|20)\d{2})"
# Ordered by how reliably they indicate the publication year.
YEAR_PATTERNS = [
    re.compile(
        rf"\b(?:published|publication date|first published)\b[^\n]{{0,60}}?\b{_YEAR}\b", re.I
    ),
    re.compile(rf"\b(?:accepted|available online)\b[^\n]{{0,60}}?\b{_YEAR}\b", re.I),
    re.compile(rf"(?:©|\(c\)|copyright)\s*(?:by\s+)?{_YEAR}\b", re.I),
]
ARXIV_RE = re.compile(r"\barXiv:(\d{2})(\d{2})\.\d{4,5}", re.I)

ABSTRACT_START = re.compile(r"(?:^|\n)\s*abstract\b[\s.:—–-]*", re.I)
ABSTRACT_END = re.compile(
    r"\n\s*(?:keywords?|key\s+words|index\s+terms|(?:1|I)\.?\s+introduction|introduction)\b",
    re.I,
)
KEYWORDS_RE = re.compile(
    r"(?:^|\n)\s*(?:keywords?|key\s+words|index\s+terms)\s*[:—–.-]?\s*(.{3,600}?)"
    r"(?=\n\s*\n|\n\s*(?:\d|I)\.?\s+[A-Z]|\n\s*introduction\b|$)",
    re.I | re.S,
)
REFERENCES_HEADING = re.compile(
    r"^\s*(?:\d+\.?\s*)?"
    r"(?:references|bibliography|works cited|literature cited|reference list)\s*$",
    re.I | re.M,
)

_NAME_NOISE = re.compile(r"[\d*†‡§¶∗⁎✉#]+|\(\s*\)|\[\s*\]")
_NAME_TOKEN = re.compile(
    r"^(?:[A-ZÀ-Ý][a-zà-ÿ'’\-]+|[A-Z]\.(?:-?[A-Z]\.)*|[A-Z]|van|von|de|der|den|da|di|del|la|le)$"
)
_AFFILIATION_WORDS = re.compile(
    r"\b(university|universit|department|dept|institute|school|college|laboratory|lab|center|centre|"
    r"hospital|faculty|inc|ltd|corporation|abstract|email|e-mail|journal|vol|issn|doi|http)\b",
    re.I,
)


def clean_inline(text: str) -> str:
    """Join hyphenated line breaks and collapse whitespace."""
    return _WS.sub(" ", _HYPHEN_BREAK.sub(r"\1\2", text)).strip()


def find_doi(text: str) -> str | None:
    match = DOI_RE.search(text)
    if not match:
        return None
    return match.group(1).rstrip(".,;:)]}'\"").lower()


def _plausible_year(year: int) -> bool:
    return 1900 <= year <= datetime.now(UTC).year + 1


def find_year(text: str) -> int | None:
    for pattern in YEAR_PATTERNS:
        for match in pattern.finditer(text):
            year = int(match.group(1))
            if _plausible_year(year):
                return year
    arxiv = ARXIV_RE.search(text)
    if arxiv and 1 <= int(arxiv.group(2)) <= 12:
        year = 2000 + int(arxiv.group(1))
        if _plausible_year(year):
            return year
    return None


def year_from_date_string(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(_YEAR, value)
    if match and _plausible_year(int(match.group(1))):
        return int(match.group(1))
    return None


def find_abstract(text: str) -> str | None:
    start = ABSTRACT_START.search(text)
    if not start:
        return None
    rest = text[start.end() : start.end() + 6000]
    end = ABSTRACT_END.search(rest)
    abstract = clean_inline(rest[: end.start()] if end else rest[:2500])
    if len(abstract) < 80:
        return None
    return abstract[:4000]


def find_keywords(text: str) -> list[str]:
    match = KEYWORDS_RE.search(text)
    if not match:
        return []
    raw = clean_inline(match.group(1))
    parts = re.split(r"\s*[;,·•|]\s*|\s+—\s+", raw)
    keywords: list[str] = []
    for part in parts:
        part = part.strip(" .")
        if 2 <= len(part) <= 60 and part.lower() not in {k.lower() for k in keywords}:
            keywords.append(part)
    return keywords[:15] if len(keywords) >= 1 else []


def split_reference_section(text: str) -> tuple[str, str | None]:
    """Return (body, references_text) split at the last references heading."""
    matches = list(REFERENCES_HEADING.finditer(text))
    if not matches:
        return text, None
    last = matches[-1]
    # Ignore a "References" heading in the first 20% (e.g. a table of contents).
    if last.start() < len(text) * 0.2:
        return text, None
    return text[: last.start()], text[last.end() :]


def find_references(text: str) -> list[str]:
    _, section = split_reference_section(text)
    if not section:
        return []
    section = section[:300_000]
    if re.search(r"^\s*\[\d+\]", section, re.M):
        parts = re.split(r"\n\s*(?=\[\d+\])", section)
    elif len(re.findall(r"^\s*\d{1,3}\.\s+\S", section, re.M)) >= 3:
        parts = re.split(r"\n\s*(?=\d{1,3}\.\s+\S)", section)
    else:
        # Author-year style: an entry starts with "Surname, X." at the start of a line.
        parts = re.split(r"\n(?=[A-ZÀ-Ý][A-Za-zÀ-ÿ'’\-]+,\s+(?:[A-Z]\.|[A-Z][a-z]+))", section)
    references = []
    for part in parts:
        entry = clean_inline(part)
        if 20 <= len(entry) <= 1500:
            references.append(entry)
    return references[:1000] if len(references) >= 2 else []


def _parse_name(fragment: str) -> str | None:
    fragment = clean_inline(_NAME_NOISE.sub(" ", fragment)).strip(" ,;")
    tokens = fragment.split()
    if not 2 <= len(tokens) <= 5:
        return None
    if not all(_NAME_TOKEN.match(t) for t in tokens):
        return None
    if not any(len(t) > 2 and not t.endswith(".") for t in tokens):
        return None
    return fragment


def parse_author_line(line: str) -> list[str]:
    """Parse "Ada Lovelace¹, Alan M. Turing² and Grace Hopper*" into names.

    Returns [] unless *every* fragment looks like a personal name.
    """
    if len(line) > 300 or "@" in line or _AFFILIATION_WORDS.search(line):
        return []
    fragments = re.split(r"\s*(?:,|;|\band\b|&|·)\s*", line)
    fragments = [f for f in fragments if f.strip(" *†‡§¶0123456789")]
    if not fragments:
        return []
    names = [_parse_name(f) for f in fragments]
    if any(n is None for n in names):
        return []
    return [n for n in names if n]


def split_author_field(value: str | None) -> list[str]:
    """Split an author metadata field ("A; B", "A, B and C", "Surname, Given")."""
    if not value:
        return []
    value = clean_inline(value)
    if ";" in value:
        parts = value.split(";")
    elif " and " in value or value.count(",") >= 2:
        parts = re.split(r"\s*,\s*|\s+and\s+", value)
    else:
        parts = [value]
    names = [p.strip(" ,") for p in parts]
    return [n for n in names if 2 <= len(n) <= 120 and any(c.isalpha() for c in n)]


JUNK_TITLES = re.compile(
    r"^(untitled|title|document\d*|microsoft word\b.*|.*\.(pdf|docx?|tex|dvi|ps|indd)|slide \d+|"
    r"powerpoint presentation)$",
    re.I,
)


def is_plausible_title(value: str | None) -> bool:
    if not value:
        return False
    value = value.strip()
    return (
        4 <= len(value) <= 400 and not JUNK_TITLES.match(value) and any(c.isalpha() for c in value)
    )


def is_plausible_author_field(value: str | None) -> bool:
    # PDF "Author" is often a login name ("jsmith") or software; require a space.
    return bool(
        value and " " in value.strip() and not re.search(r"\b(admin|user|owner)\b", value, re.I)
    )
