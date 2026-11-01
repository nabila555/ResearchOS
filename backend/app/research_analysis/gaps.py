"""Research gap finder over a set of paper profiles.

Literature-supported findings and AI-generated hypotheses are kept apart, and the
classification is enforced after generation: an item labelled "literature" must
name papers that exist; a contradiction must name at least two; proposed research
questions are always hypotheses.
"""

from dataclasses import dataclass
from typing import Any

from app.ai.providers import ChatProvider

MAX_ITEMS = 5

CATEGORIES: tuple[tuple[str, str, str], ...] = (
    (
        "underexplored_areas",
        "Underexplored areas",
        "topics, populations or settings the papers barely cover",
    ),
    ("contradictions", "Contradictory findings", "results that disagree between papers"),
    (
        "missing_perspectives",
        "Missing perspectives",
        "viewpoints, disciplines or stakeholders absent from the set",
    ),
    (
        "methodological_limitations",
        "Methodological limitations",
        "recurring weaknesses in designs, samples or measures",
    ),
    (
        "future_directions",
        "Future research directions",
        "directions the papers recommend or that follow from the gaps",
    ),
    (
        "research_questions",
        "Potential research questions",
        "concrete new questions worth investigating",
    ),
)

ALWAYS_HYPOTHESIS = {"research_questions"}
NEEDS_TWO_PAPERS = {"contradictions"}

SYSTEM_PROMPT = """You are a careful research analyst. You receive structured summaries of papers \
labelled P1, P2, ... from the user's library. Identify research gaps across them.

Rules:
- "basis": "literature" only when the summaries directly support the item; list those \
papers in "papers".
- "basis": "hypothesis" for anything you infer, extrapolate or propose. Hypotheses are \
welcome but must be labelled.
- A contradiction means two or more papers report incompatible results on the SAME question \
(e.g. one finds an effect, another finds none). Findings about different topics are not \
contradictions. Name at least two papers.
- Research questions are your proposals: always "hypothesis".
- Never invent papers, findings or numbers. Refer to papers only as P1, P2, ...
- At most 5 items per category. Return an empty list when the summaries say nothing useful."""

_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "statement": {"type": "string"},
        "basis": {"type": "string", "enum": ["literature", "hypothesis"]},
        "papers": {"type": "array", "items": {"type": "integer"}},
        "rationale": {"type": "string"},
    },
    "required": ["statement", "basis", "papers", "rationale"],
    "additionalProperties": False,
}

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {key: {"type": "array", "items": _ITEM_SCHEMA} for key, _, _ in CATEGORIES},
    "required": [key for key, _, _ in CATEGORIES],
    "additionalProperties": False,
}

DIGEST_FIELDS = (
    ("research_objective", "Objective"),
    ("methodology", "Methods"),
    ("sample_size", "Sample"),
    ("population", "Population"),
    ("key_findings", "Findings"),
    ("limitations", "Limitations"),
    ("future_research", "Future research"),
)


@dataclass
class PaperDigest:
    label: str  # "P1"
    document_id: int
    title: str
    year: int | None
    fields: dict[str, Any]


def digest_text(paper: PaperDigest, max_chars: int = 1400) -> str:
    """Compact summary built only from *verified* profile statements."""
    lines = [f"{paper.label}: “{paper.title}”{f' ({paper.year})' if paper.year else ''}"]
    for key, label in DIGEST_FIELDS:
        statements = [
            s["text"]
            for s in paper.fields.get(key, {}).get("statements", [])
            if s["evidence"]["verified"]
        ]
        lines.append(f"  {label}: {'; '.join(statements) if statements else 'not reported'}")
    return "\n".join(lines)[:max_chars]


def build_prompt(papers: list[PaperDigest], focus: str | None) -> str:
    wanted = "\n".join(f"- {key}: {hint}" for key, _, hint in CATEGORIES)
    focus_line = f"\nFocus the analysis on: {focus}\n" if focus else ""
    return (
        "Paper summaries:\n\n"
        + "\n\n".join(digest_text(p) for p in papers)
        + f"\n{focus_line}\nReturn these categories:\n{wanted}"
    )


def verify(data: dict[str, Any], papers: list[PaperDigest]) -> dict[str, Any]:
    by_number = {i + 1: p for i, p in enumerate(papers)}
    categories = []
    for key, label, _ in CATEGORIES:
        items = []
        for raw in (data.get(key) or [])[:MAX_ITEMS]:
            statement = str(raw.get("statement", "")).strip()[:600]
            if not statement:
                continue
            refs = [n for n in dict.fromkeys(raw.get("papers") or []) if isinstance(n, int)]
            valid = [n for n in refs if n in by_number]
            invalid = [n for n in refs if n not in by_number]
            basis = (
                raw.get("basis")
                if raw.get("basis") in ("literature", "hypothesis")
                else "hypothesis"
            )
            notes = []
            if invalid:
                notes.append(
                    "Referred to papers that are not in the set: "
                    + ", ".join(f"P{n}" for n in invalid)
                )
            if key in ALWAYS_HYPOTHESIS and basis == "literature":
                basis = "hypothesis"
            if basis == "literature" and not valid:
                basis = "hypothesis"
                notes.append(
                    "Labelled as literature-supported without naming a paper; "
                    "shown as a hypothesis."
                )
            if key in NEEDS_TWO_PAPERS and basis == "literature" and len(valid) < 2:
                basis = "hypothesis"
                notes.append("A contradiction needs at least two papers; shown as a hypothesis.")
            items.append(
                {
                    "statement": statement,
                    "basis": basis,
                    "rationale": str(raw.get("rationale", "")).strip()[:800],
                    "papers": [
                        {
                            "label": f"P{n}",
                            "document_id": by_number[n].document_id,
                            "title": by_number[n].title,
                        }
                        for n in valid
                    ],
                    "notes": notes,
                }
            )
        categories.append({"key": key, "label": label, "items": items})
    return {"categories": categories}


def find_gaps(
    papers: list[PaperDigest], provider: ChatProvider, focus: str | None
) -> dict[str, Any]:
    data = provider.generate_json(
        SYSTEM_PROMPT, build_prompt(papers, focus), SCHEMA, max_tokens=2000
    )
    result = verify(data, papers)
    result["papers"] = [
        {"label": p.label, "document_id": p.document_id, "title": p.title, "year": p.year}
        for p in papers
    ]
    result["focus"] = focus
    return result
