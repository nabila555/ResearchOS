"""Citation formatting (APA 7, MLA 9, Chicago author-date, IEEE) and BibTeX / RIS export.

Only metadata the user has (extracted or entered) is used. Missing elements are left
out and reported in ``missing`` so the UI can ask for them; nothing is invented. Style
conventions for unknown values are applied where the style defines them (APA "n.d.").
Titles are used exactly as stored: automatic sentence/title casing would corrupt proper
nouns, so the UI reminds users to check capitalisation.
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

Style = Literal["apa", "mla", "chicago", "ieee"]
STYLES: dict[str, str] = {
    "apa": "APA 7th",
    "mla": "MLA 9th",
    "chicago": "Chicago (author-date, 17th)",
    "ieee": "IEEE",
}
PARTICLES = {
    "van",
    "von",
    "de",
    "der",
    "den",
    "da",
    "di",
    "del",
    "della",
    "la",
    "le",
    "du",
    "dos",
    "das",
    "ter",
    "ten",
    "bin",
    "al",
}
MONTHS_MLA = [
    "Jan.",
    "Feb.",
    "Mar.",
    "Apr.",
    "May",
    "June",
    "July",
    "Aug.",
    "Sept.",
    "Oct.",
    "Nov.",
    "Dec.",
]
MONTHS_IEEE = [
    "Jan.",
    "Feb.",
    "Mar.",
    "Apr.",
    "May",
    "Jun.",
    "Jul.",
    "Aug.",
    "Sep.",
    "Oct.",
    "Nov.",
    "Dec.",
]


@dataclass(frozen=True)
class Name:
    given: str
    family: str

    @property
    def initials(self) -> str:
        """'Alan M.' -> 'A. M.'; 'Jean-Paul' -> 'J.-P.'"""
        parts = []
        for token in self.given.split():
            pieces = [p for p in token.split("-") if p]
            parts.append("-".join(f"{p[0].upper()}." for p in pieces))
        return " ".join(parts)

    @property
    def given_first(self) -> str:
        return f"{self.given} {self.family}".strip()

    @property
    def family_first(self) -> str:
        return f"{self.family}, {self.given}" if self.given else self.family


def parse_name(raw: str) -> Name:
    raw = re.sub(r"\s+", " ", raw).strip().strip(",")
    if "," in raw:
        family, given = (part.strip() for part in raw.split(",", 1))
        return Name(given, family)
    tokens = raw.split(" ")
    if len(tokens) == 1:
        return Name("", tokens[0])
    start = len(tokens) - 1
    while start > 1 and tokens[start - 1].lower() in PARTICLES:
        start -= 1
    return Name(" ".join(tokens[:start]), " ".join(tokens[start:]))


@dataclass
class CitationData:
    id: int
    kind: Literal["article", "web", "document"]
    title: str
    authors: list[Name]
    year: int | None
    venue: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    publisher: str | None = None
    doi: str | None = None
    url: str | None = None
    accessed: datetime | None = None

    @property
    def site(self) -> str | None:
        if self.venue:
            return self.venue
        return urlsplit(self.url).hostname if self.url else None

    @property
    def link(self) -> str | None:
        return f"https://doi.org/{self.doi}" if self.doi else self.url


@dataclass
class Formatted:
    parts: list[tuple[str, bool]] = field(default_factory=list)  # (text, italic)
    missing: list[str] = field(default_factory=list)

    def add(self, text: str, italic: bool = False) -> None:
        if text:
            self.parts.append((text, italic))

    @property
    def text(self) -> str:
        return "".join(t for t, _ in self.parts)

    @property
    def markdown(self) -> str:
        return "".join(f"*{t}*" if italic and t.strip() else t for t, italic in self.parts)


def _end(text: str) -> str:
    """Add a period unless the text already ends with punctuation."""
    return text if text.endswith((".", "?", "!")) else f"{text}."


def _pages(pages: str, dash: str = "–") -> str:
    return re.sub(r"\s*[-–—]+\s*", dash, pages.strip())


def missing_fields(data: CitationData) -> list[str]:
    missing = []
    if not data.authors:
        missing.append("authors")
    if data.year is None:
        missing.append("year")
    if data.kind == "article":
        for name in ("volume", "pages"):
            if not getattr(data, name):
                missing.append(name)
        if not data.doi and not data.url:
            missing.append("doi")
    if data.kind == "web" and not data.url:
        missing.append("url")
    return missing


# --- APA 7 ------------------------------------------------------------------------------


def _apa_authors(authors: list[Name]) -> str:
    names = [f"{a.family}, {a.initials}".rstrip(", ") if a.given else a.family for a in authors]
    if len(names) == 1:
        return names[0]
    if len(names) <= 20:
        return ", ".join(names[:-1]) + ", & " + names[-1]
    return ", ".join(names[:19]) + ", . . . " + names[-1]


def format_apa(d: CitationData) -> Formatted:
    f = Formatted(missing=missing_fields(d))
    year = f"({d.year})." if d.year else "(n.d.)."
    title_italic = d.kind != "article"
    if d.authors:
        f.add(_end(_apa_authors(d.authors)) + " " + year + " ")
        f.add(_end(d.title) if not title_italic else d.title, italic=title_italic)
        if title_italic:
            f.add(". " if not d.title.endswith((".", "?", "!")) else " ")
        else:
            f.add(" ")
    else:  # APA: the title moves to the author position
        f.add(d.title, italic=title_italic)
        f.add(" " if d.title.endswith((".", "?", "!")) else ". ")
        f.add(year + " ")
    if d.kind == "article" and d.venue:
        f.add(d.venue, italic=True)
        if d.volume:
            f.add(", ")
            f.add(d.volume, italic=True)
            if d.issue:
                f.add(f"({d.issue})")
        if d.pages:
            f.add(f", {_pages(d.pages)}")
        f.add(". ")
    elif d.kind == "web" and d.site:
        f.add(f"{d.site}. ")
    elif d.publisher:
        f.add(f"{_end(d.publisher)} ")
    if d.link:
        f.add(d.link)
    f.parts[-1] = (f.parts[-1][0].rstrip(), f.parts[-1][1])
    return f


# --- MLA 9 -------------------------------------------------------------------------------


def _mla_authors(authors: list[Name]) -> str:
    if len(authors) == 1:
        return authors[0].family_first
    if len(authors) == 2:
        return f"{authors[0].family_first}, and {authors[1].given_first}"
    return f"{authors[0].family_first}, et al"


def format_mla(d: CitationData) -> Formatted:
    f = Formatted(missing=missing_fields(d))
    if d.authors:
        f.add(_end(_mla_authors(d.authors)) + " ")
    if d.kind == "document":
        f.add(d.title, italic=True)
        f.add(". " if not d.title.endswith((".", "?", "!")) else " ")
        tail = ", ".join(x for x in (d.publisher, str(d.year) if d.year else None) if x)
        if tail:
            f.add(f"{tail}. ")
    else:
        f.add(f"“{_end(d.title)}” ")
        container = d.venue if d.kind == "article" else d.site
        if container:
            f.add(container, italic=True)
        details = []
        if d.kind == "article":
            if d.volume:
                details.append(f"vol. {d.volume}")
            if d.issue:
                details.append(f"no. {d.issue}")
        if d.year:
            details.append(str(d.year))
        if d.kind == "article" and d.pages:
            pages = _pages(d.pages, "-")
            details.append(f"{'pp.' if '-' in pages else 'p.'} {pages}")
        if details:
            f.add((", " if container else "") + ", ".join(details))
        if container or details:
            f.add(". ")
    if d.link:
        f.add(_end(d.link))
        if d.kind == "web" and d.accessed:
            a = d.accessed
            f.add(f" Accessed {a.day} {MONTHS_MLA[a.month - 1]} {a.year}.")
    f.parts[-1] = (f.parts[-1][0].rstrip(), f.parts[-1][1])
    return f


# --- Chicago author-date -----------------------------------------------------------------


def _chicago_authors(authors: list[Name]) -> str:
    if len(authors) > 10:
        names = [authors[0].family_first] + [a.given_first for a in authors[1:7]]
        return ", ".join(names) + ", et al"
    names = [authors[0].family_first] + [a.given_first for a in authors[1:]]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]}, and {names[1]}"
    return ", ".join(names[:-1]) + ", and " + names[-1]


def format_chicago(d: CitationData) -> Formatted:
    f = Formatted(missing=missing_fields(d))
    year = str(d.year) if d.year else "n.d."
    if d.authors:
        f.add(_end(_chicago_authors(d.authors)) + f" {_end(year)} ")
    if d.kind == "document":
        f.add(d.title, italic=True)
        f.add(". " if not d.title.endswith((".", "?", "!")) else " ")
    else:
        f.add(f"“{_end(d.title)}” ")
    if not d.authors:
        f.add(f"{_end(year)} ")
    if d.kind == "article" and d.venue:
        f.add(d.venue, italic=True)
        if d.volume:
            f.add(f" {d.volume}")
            if d.issue:
                f.add(f" ({d.issue})")
        if d.pages:
            f.add(f": {_pages(d.pages)}")
        f.add(". ")
    elif d.kind == "web" and d.site:
        f.add(f"{d.site}. ")
    elif d.publisher:
        f.add(f"{_end(d.publisher)} ")
    if d.link:
        f.add(_end(d.link))
    f.parts[-1] = (f.parts[-1][0].rstrip(), f.parts[-1][1])
    return f


# --- IEEE --------------------------------------------------------------------------------


def _ieee_authors(authors: list[Name]) -> str:
    names = [f"{a.initials} {a.family}".strip() for a in authors]
    if len(names) > 6:
        return f"{names[0]} et al."
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + ", and " + names[-1]


def format_ieee(d: CitationData) -> Formatted:
    f = Formatted(missing=missing_fields(d))
    if d.authors:
        f.add(_ieee_authors(d.authors) + ", ")
    if d.kind == "document":
        f.add(d.title, italic=True)
        tail = ", ".join(x for x in (d.publisher, str(d.year) if d.year else None) if x)
        f.add(f". {tail}." if tail else ".")
        if d.doi:
            f.add(f" doi: {d.doi}.")
        elif d.url:
            f.add(f" [Online]. Available: {d.url}")
    else:
        f.add(f"“{d.title},” ")
        if d.kind == "article":
            if d.venue:
                f.add(d.venue, italic=True)
            details = []
            if d.volume:
                details.append(f"vol. {d.volume}")
            if d.issue:
                details.append(f"no. {d.issue}")
            if d.pages:
                pages = _pages(d.pages)
                details.append(f"{'pp.' if '–' in pages else 'p.'} {pages}")
            if d.year:
                details.append(str(d.year))
            if details:
                f.add((", " if d.venue else "") + ", ".join(details))
            f.add(".")
            if d.doi:
                f.add(f" doi: {d.doi}.")
            elif d.url:
                f.add(f" [Online]. Available: {d.url}")
        else:
            if d.site:
                f.add(f"{d.site}.")
            if d.year:
                f.add(f" {d.year}.")
            if d.accessed:
                a = d.accessed
                f.add(f" Accessed: {MONTHS_IEEE[a.month - 1]} {a.day}, {a.year}.")
            if d.url:
                f.add(f" [Online]. Available: {d.url}")
    return f


FORMATTERS = {"apa": format_apa, "mla": format_mla, "chicago": format_chicago, "ieee": format_ieee}


def format_citation(d: CitationData, style: Style) -> Formatted:
    return FORMATTERS[style](d)


def sort_key(d: CitationData) -> tuple[str, int, str]:
    first = d.authors[0].family.lower() if d.authors else d.title.lower()
    return (_ascii(first), d.year or 0, _ascii(d.title.lower()))


def bibliography(items: list[CitationData], style: Style) -> list[tuple[CitationData, Formatted]]:
    """IEEE keeps the given (citation) order and is numbered; the others sort alphabetically."""
    ordered = items if style == "ieee" else sorted(items, key=sort_key)
    return [(d, format_citation(d, style)) for d in ordered]


def in_text(d: CitationData, style: Style, number: int | None = None) -> str:
    """Parenthetical in-text citation: (Lovelace et al., 2021) / (Lovelace et al.) / [3]."""
    if style == "ieee":
        return f"[{number or '?'}]"
    if not d.authors:
        short = d.title if len(d.title) <= 40 else d.title[:37].rstrip() + "…"
        who = f"“{short}”"
    elif len(d.authors) == 1:
        who = d.authors[0].family
    elif len(d.authors) == 2:
        joiner = " & " if style == "apa" else " and "
        who = f"{d.authors[0].family}{joiner}{d.authors[1].family}"
    else:
        who = f"{d.authors[0].family} et al."
    if style == "mla":
        return f"({who})"
    return f"({who}, {d.year if d.year else 'n.d.'})"


def narrative(d: CitationData, style: Style, number: int | None = None) -> str:
    """Citation as part of a sentence: "Lovelace et al. (2021)", "Lovelace et al.", "[3]"."""
    if style == "ieee":
        return f"[{number or '?'}]"
    if not d.authors:
        who = f"“{d.title if len(d.title) <= 40 else d.title[:37].rstrip() + '…'}”"
    elif len(d.authors) == 1:
        who = d.authors[0].family
    elif len(d.authors) == 2:
        who = f"{d.authors[0].family} and {d.authors[1].family}"
    else:
        who = f"{d.authors[0].family} et al."
    if style == "mla":
        return who
    return f"{who} ({d.year if d.year else 'n.d.'})"


# --- BibTeX & RIS ------------------------------------------------------------------------

_BIBTEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def _tex(text: str) -> str:
    return "".join(_BIBTEX_ESCAPES.get(ch, ch) for ch in text)


def bibtex_key(d: CitationData, used: set[str]) -> str:
    who = re.sub(r"[^a-z]", "", _ascii(d.authors[0].family.lower())) if d.authors else "anon"
    word = next((w for w in re.findall(r"[a-z]+", _ascii(d.title.lower())) if len(w) > 3), "item")
    base = f"{who or 'anon'}{d.year or 'nd'}{word}"
    key, suffix = base, ord("a")
    while key in used:
        key = f"{base}{chr(suffix)}"
        suffix += 1
    used.add(key)
    return key


def to_bibtex(items: list[CitationData]) -> str:
    used: set[str] = set()
    entries = []
    for d in items:
        entry_type = "article" if d.kind == "article" else ("online" if d.kind == "web" else "misc")
        fields: list[tuple[str, str]] = [("title", "{" + _tex(d.title) + "}")]
        if d.authors:
            fields.insert(0, ("author", " and ".join(_tex(a.family_first) for a in d.authors)))
        if d.kind == "article" and d.venue:
            fields.append(("journal", _tex(d.venue)))
        if d.year:
            fields.append(("year", str(d.year)))
        for name, value in (("volume", d.volume), ("number", d.issue)):
            if value:
                fields.append((name, _tex(value)))
        if d.pages:
            fields.append(("pages", _pages(d.pages, "--")))
        if d.publisher:
            fields.append(("publisher", _tex(d.publisher)))
        if d.doi:
            fields.append(("doi", d.doi))
        if d.url:
            fields.append(("url", d.url))
        if d.kind == "web" and d.accessed:
            fields.append(("urldate", d.accessed.strftime("%Y-%m-%d")))
        body = ",\n".join(f"  {name} = {{{value}}}" for name, value in fields)
        entries.append(f"@{entry_type}{{{bibtex_key(d, used)},\n{body}\n}}")
    return "\n\n".join(entries) + ("\n" if entries else "")


def to_ris(items: list[CitationData]) -> str:
    records = []
    for d in items:
        lines = [f"TY  - {'JOUR' if d.kind == 'article' else 'ELEC' if d.kind == 'web' else 'GEN'}"]
        lines += [f"AU  - {a.family_first}" for a in d.authors]
        lines.append(f"TI  - {d.title}")
        if d.kind == "article" and d.venue:
            lines.append(f"T2  - {d.venue}")
        if d.year:
            lines.append(f"PY  - {d.year}")
        if d.volume:
            lines.append(f"VL  - {d.volume}")
        if d.issue:
            lines.append(f"IS  - {d.issue}")
        if d.pages:
            start, _, end = _pages(d.pages, "-").partition("-")
            lines.append(f"SP  - {start}")
            if end:
                lines.append(f"EP  - {end}")
        if d.publisher:
            lines.append(f"PB  - {d.publisher}")
        if d.doi:
            lines.append(f"DO  - {d.doi}")
        if d.url:
            lines.append(f"UR  - {d.url}")
        lines.append("ER  - ")
        records.append("\n".join(lines))
    return "\n\n".join(records) + ("\n" if records else "")


_LABEL_GROUP = re.compile(r"[(\[]\s*P\d+(?:\s*(?:[,;]|and|&)\s*P\d+)*\s*[)\]]")
_LABEL = re.compile(r"\bP\d+\b")


def replace_paper_labels(
    text: str,
    resolve: Callable[[str], tuple[CitationData, int] | None],
    style: Style,
) -> tuple[str, set[str]]:
    """Turn model-written paper labels into citations.

    "(P1)" / "(P1, P2)" / "[P1]" become parenthetical citations; a bare "P1" in a sentence
    becomes a narrative citation ("Lovelace et al. (2021)"). ``resolve`` maps a label to its
    citation data and number (IEEE). Returns the new text and the labels that were cited.
    """
    named: set[str] = set()

    def group(match: re.Match[str]) -> str:
        cited = []
        for label in _LABEL.findall(match.group(0)):
            found = resolve(label)
            if found is not None:
                named.add(label)
                cited.append(in_text(found[0], style, found[1]))
        if not cited:
            return match.group(0)
        if style == "ieee":
            return ", ".join(cited)
        return "(" + "; ".join(c.strip("()") for c in cited) + ")"

    def single(match: re.Match[str]) -> str:
        found = resolve(match.group(0))
        if found is None:
            return match.group(0)
        named.add(match.group(0))
        return narrative(found[0], style, found[1])

    return _LABEL.sub(single, _LABEL_GROUP.sub(group, text)), named
