"""Thematic synthesis for the literature review workspace.

The model writes a short synthesis of one theme from the papers' *verified* profile
statements. Every sentence must cite papers (P1, P2 ...) from the theme; sentences
without a valid citation are kept but flagged as unsupported, and disagreements must
name at least two papers.
"""

from typing import Any

from app.ai.providers import ChatProvider
from app.research_analysis.gaps import PaperDigest, digest_text

SYSTEM_PROMPT = """You help write a literature review. You receive verified summaries of the \
papers in one theme, labelled P1, P2, ...

Write a concise synthesis (3 to 7 sentences) that compares and connects the papers rather than \
summarising them one by one. Then list points where papers agree and points where they disagree.

Rules:
- Every sentence and point must list the papers that support it in "papers" (numbers only).
- Use only the information in the summaries. Do not invent findings, numbers or papers.
- A disagreement means papers report incompatible results on the same question; name at least two.
- Write in a neutral academic register. Do not include citation markers in the text itself."""

_CLAIM = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "papers": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["text", "papers"],
    "additionalProperties": False,
}
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "synthesis": {"type": "array", "items": _CLAIM},
        "agreements": {"type": "array", "items": _CLAIM},
        "disagreements": {"type": "array", "items": _CLAIM},
    },
    "required": ["synthesis", "agreements", "disagreements"],
    "additionalProperties": False,
}


def _verify_claims(
    raw: list[Any], papers: dict[int, PaperDigest], min_papers: int, limit: int
) -> list[dict[str, Any]]:
    claims = []
    for item in raw[:limit]:
        text = str(item.get("text", "")).strip()[:800]
        if not text:
            continue
        refs = [n for n in dict.fromkeys(item.get("papers") or []) if isinstance(n, int)]
        valid = [n for n in refs if n in papers]
        notes = []
        if len(valid) < len(refs):
            notes.append(
                "Referred to papers outside this theme: "
                + ", ".join(f"P{n}" for n in refs if n not in papers)
            )
        supported = len(valid) >= min_papers
        if not supported:
            notes.append(
                "Not linked to any paper in this theme."
                if min_papers == 1
                else f"Needs at least {min_papers} papers."
            )
        claims.append(
            {
                "text": text,
                "supported": supported,
                "papers": [{"label": f"P{n}", "document_id": papers[n].document_id} for n in valid],
                "notes": notes,
            }
        )
    return claims


def summarise_theme(
    theme_name: str,
    research_question: str | None,
    digests: list[PaperDigest],
    provider: ChatProvider,
) -> dict[str, Any]:
    context = f"Theme: {theme_name}\n"
    if research_question:
        context += f"Review question: {research_question}\n"
    prompt = context + "\nPapers:\n\n" + "\n\n".join(digest_text(d) for d in digests)
    data = provider.generate_json(SYSTEM_PROMPT, prompt, SCHEMA, max_tokens=1500)
    by_number = {i + 1: d for i, d in enumerate(digests)}
    return {
        "theme": theme_name,
        "papers": [
            {"label": d.label, "document_id": d.document_id, "title": d.title} for d in digests
        ],
        "synthesis": _verify_claims(data.get("synthesis") or [], by_number, 1, 10),
        "agreements": _verify_claims(data.get("agreements") or [], by_number, 2, 6),
        "disagreements": _verify_claims(data.get("disagreements") or [], by_number, 2, 6),
    }
