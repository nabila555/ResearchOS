"""Literature review workspace: themes, grouping suggestions, and Markdown export."""

import re
from collections import Counter
from typing import Any

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.citations import CitationData, Style, bibliography, in_text, narrative
from app.models.analysis import Analysis, AnalysisKind, AnalysisStatus
from app.models.library import Document, DocumentAuthor
from app.models.review import LiteratureReview, ReviewTheme, ReviewThemeItem
from app.services import citation_service
from app.services.errors import InvalidRequestError, NotFoundError
from app.services.graph_service import _paper_vectors

STOP = frozenset(
    "a an and are as at by for from in into is of on or the to with using study studies "
    "effect effects evidence analysis role among between based new".split()
)


# --- CRUD -----------------------------------------------------------------------------------


def get_review(db: Session, review_id: int) -> LiteratureReview:
    review = db.scalar(
        select(LiteratureReview)
        .where(LiteratureReview.id == review_id)
        .options(selectinload(LiteratureReview.themes).selectinload(ReviewTheme.items))
    )
    if review is None:
        raise NotFoundError(f"Review {review_id} not found")
    return review


def get_theme(db: Session, theme_id: int) -> ReviewTheme:
    theme = db.get(ReviewTheme, theme_id)
    if theme is None:
        raise NotFoundError(f"Theme {theme_id} not found")
    return theme


def latest_summaries(db: Session, theme_ids: list[int]) -> dict[int, Analysis]:
    found: dict[int, Analysis] = {}
    rows = db.scalars(
        select(Analysis)
        .where(Analysis.kind == AnalysisKind.THEME_SUMMARY)
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
    )
    for analysis in rows:
        theme_id = analysis.params.get("theme_id")
        if theme_id in theme_ids and theme_id not in found:
            found[theme_id] = analysis
    return found


def review_detail(db: Session, review: LiteratureReview) -> dict[str, Any]:
    doc_ids = {item.document_id for theme in review.themes for item in theme.items}
    docs = {
        d.id: d
        for d in db.scalars(
            select(Document)
            .where(Document.id.in_(doc_ids))
            .options(selectinload(Document.authors).selectinload(DocumentAuthor.author))
        )
    }
    summaries = latest_summaries(db, [t.id for t in review.themes])
    themes = []
    for theme in review.themes:
        summary = summaries.get(theme.id)
        themes.append(
            {
                "id": theme.id,
                "name": theme.name,
                "description": theme.description,
                "position": theme.position,
                "items": [
                    {
                        "document_id": item.document_id,
                        "note": item.note,
                        "title": docs[item.document_id].title,
                        "authors": [
                            link.author.full_name for link in docs[item.document_id].authors
                        ],
                        "year": docs[item.document_id].publication_year,
                    }
                    for item in theme.items
                    if item.document_id in docs
                ],
                "summary": None
                if summary is None
                else {
                    "analysis_id": summary.id,
                    "status": summary.status.value,
                    "progress": summary.progress,
                    "progress_message": summary.progress_message,
                    "error": summary.error,
                    "model": summary.model,
                    "result": summary.result,
                    "stale": summary.document_ids != [i.document_id for i in theme.items],
                    "updated_at": summary.updated_at,
                },
            }
        )
    return {
        "id": review.id,
        "title": review.title,
        "research_question": review.research_question,
        "introduction": review.introduction,
        "project_id": review.project_id,
        "citation_style": review.citation_style,
        "themes": themes,
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }


def set_theme_items(db: Session, theme: ReviewTheme, items: list[dict[str, Any]]) -> None:
    ids = [i["document_id"] for i in items]
    if len(set(ids)) != len(ids):
        raise InvalidRequestError("A paper can only appear once in a theme.")
    existing = set(db.scalars(select(Document.id).where(Document.id.in_(ids))))
    missing = [i for i in ids if i not in existing]
    if missing:
        raise NotFoundError(f"Document {missing[0]} not found")
    db.execute(delete(ReviewThemeItem).where(ReviewThemeItem.theme_id == theme.id))
    db.add_all(
        ReviewThemeItem(
            theme_id=theme.id,
            document_id=i["document_id"],
            position=pos,
            note=(i.get("note") or None),
        )
        for pos, i in enumerate(items)
    )


# --- Grouping suggestions ----------------------------------------------------------------------


def _label(docs: list[Document]) -> str:
    counts: Counter[str] = Counter()
    for doc in docs:
        words = {k.strip().lower() for k in doc.keywords or []} | {t.name.lower() for t in doc.tags}
        if not words:
            words = {w for w in re.findall(r"[a-z]{4,}", doc.title.lower()) if w not in STOP}
        counts.update(words)
    common = [w for w, n in counts.most_common(3) if n >= (2 if len(docs) > 1 else 1)]
    return ", ".join(common).capitalize() if common else "Related papers"


def suggest_groups(
    db: Session, document_ids: list[int], embed_model: str, threshold: float = 0.72
) -> dict[str, Any]:
    """Greedy similarity clustering on the papers' mean embeddings (no model call)."""
    docs = {
        d.id: d
        for d in db.scalars(
            select(Document)
            .where(Document.id.in_(document_ids))
            .options(selectinload(Document.tags))
        )
    }
    vectors = _paper_vectors(db, embed_model, list(docs))
    unindexed = [i for i in document_ids if i in docs and i not in vectors]
    ids = [i for i in document_ids if i in vectors]
    groups: list[list[int]] = []
    if ids:
        matrix = np.vstack([vectors[i] for i in ids])
        sims = matrix @ matrix.T
        unassigned = list(range(len(ids)))
        while unassigned:
            seed = unassigned.pop(0)
            members = [seed] + [j for j in unassigned if sims[seed, j] >= threshold]
            unassigned = [j for j in unassigned if j not in members]
            groups.append([ids[m] for m in members])
    return {
        "groups": [
            {"name": _label([docs[i] for i in group]), "document_ids": group} for group in groups
        ],
        "unindexed_document_ids": unindexed,
        "method": f"Grouped by semantic similarity of the papers' text (threshold {threshold}).",
    }


# --- Export ----------------------------------------------------------------------------------


def export_markdown(db: Session, review: LiteratureReview, style: Style) -> str:
    detail = review_detail(db, review)
    doc_ids = list(dict.fromkeys(i["document_id"] for t in detail["themes"] for i in t["items"]))
    cite: dict[int, CitationData] = {c.id: c for c in citation_service.load(db, doc_ids)}
    numbers: dict[int, int] = {}  # IEEE numbering by first appearance

    def ref(document_ids: list[int]) -> str:
        parts = []
        for doc_id in document_ids:
            data = cite.get(doc_id)
            if data is None:
                continue  # notes are not citable
            numbers.setdefault(doc_id, len(numbers) + 1)
            parts.append(in_text(data, style, numbers[doc_id]))
        if not parts:
            return ""
        if style == "ieee":
            return " " + ", ".join(parts)
        return " (" + "; ".join(p.strip("()") for p in parts) + ")"

    def cited_sentence(claim: dict[str, Any], papers: list[dict[str, Any]]) -> str:
        """Sentence text with stray "P1"-style labels turned into narrative citations, followed
        by a parenthetical citation for the supporting papers not already named in the text."""
        by_label = {p["label"]: p["document_id"] for p in papers}
        named: set[int] = set()

        def replace(match: re.Match[str]) -> str:
            doc_id = by_label.get(match.group(0))
            data = cite.get(doc_id) if doc_id is not None else None
            if data is None:
                return match.group(0)
            numbers.setdefault(doc_id, len(numbers) + 1)
            named.add(doc_id)
            return narrative(data, style, numbers[doc_id])

        text = re.sub(r"\bP\d+\b", replace, claim["text"].rstrip("."))
        remaining = [p["document_id"] for p in claim["papers"] if p["document_id"] not in named]
        return f"{text}{ref(remaining)}"

    lines = [f"# {review.title}", ""]
    if review.research_question:
        lines += [f"**Research question:** {review.research_question}", ""]
    if review.introduction:
        lines += ["## Introduction", "", review.introduction.strip(), ""]
    for theme in detail["themes"]:
        lines += [f"## {theme['name']}", ""]
        if theme["description"]:
            lines += [f"_{theme['description']}_", ""]
        summary = theme["summary"]
        result = summary["result"] if summary and summary["status"] == "done" else None
        if result:
            sentences = []
            for claim in result["synthesis"]:
                flag = "" if claim["supported"] else " [⚠ unsupported]"
                sentences.append(f"{cited_sentence(claim, result['papers'])}.{flag}")
            lines += [" ".join(sentences), ""]
            for key, heading in (
                ("agreements", "Points of agreement"),
                ("disagreements", "Points of disagreement"),
            ):
                claims = [c for c in result[key] if c["supported"]]
                if claims:
                    lines += [f"**{heading}**", ""]
                    lines += [f"- {cited_sentence(c, result['papers'])}." for c in claims]
                    lines.append("")
            if summary["stale"]:
                lines += [
                    "_Note: papers in this theme changed after the summary was generated._",
                    "",
                ]
        lines += ["**Sources in this theme**", ""]
        for item in theme["items"]:
            note = f": {item['note']}" if item["note"] else ""
            lines.append(f"- {item['title']}{ref([item['document_id']])}{note}")
        lines.append("")
    entries = bibliography(
        [cite[i] for i in sorted(numbers, key=numbers.get)]
        if style == "ieee"
        else [cite[i] for i in doc_ids if i in cite],
        style,
    )
    if entries:
        lines += ["## References", ""]
        for index, (_, formatted) in enumerate(entries):
            prefix = f"[{index + 1}] " if style == "ieee" else ""
            lines += [prefix + formatted.markdown, ""]
    lines.append("---")
    lines.append(
        "_Drafted in ResearchOS. AI-generated synthesis sentences cite the papers they are "
        "based on; verify them against the sources before submitting._"
    )
    return "\n".join(lines) + "\n"


def summary_in_progress(db: Session, theme_id: int) -> bool:
    return any(
        a.params.get("theme_id") == theme_id
        for a in db.scalars(
            select(Analysis).where(
                Analysis.kind == AnalysisKind.THEME_SUMMARY,
                Analysis.status.in_([AnalysisStatus.PENDING, AnalysisStatus.RUNNING]),
            )
        )
    )
