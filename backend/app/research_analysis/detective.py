"""Research Paper Detective: careful, evidence-linked critical reading of one paper.

Observations are framed as analytical notes, not accusations. Each one either
quotes the excerpt it concerns (and the quote is verified) or is explicitly an
"absence" observation, which only means "not found in the analysed excerpts".
"""

from typing import Any

from app.ai.providers import ChatProvider
from app.models.library import Chunk
from app.research_analysis.evidence import (
    Excerpt,
    Focus,
    check_statement,
    evidence_record,
    format_excerpts,
    select_excerpts,
)

MAX_OBSERVATIONS = 8

CATEGORIES = {
    "unsupported_claim": "Claim that may not be fully supported",
    "weak_argument": "Weak or incomplete argument",
    "methodological_limitation": "Methodological limitation",
    "potential_bias": "Potential bias",
    "missing_information": "Missing information",
    "reproducibility": "Reproducibility concern",
}

CHECKLIST = {
    "data_availability": "Data availability",
    "code_availability": "Code / materials availability",
    "preregistration": "Preregistration",
    "sample_size_justification": "Sample size justification",
    "statistical_methods": "Statistical methods described",
    "conflicts_of_interest": "Funding / conflicts of interest",
}

FOCUS = Focus(
    sections=("abstract", "method", "result", "discussion", "limitation", "conclusion", "data"),
    keywords=(
        "significant",
        "p <",
        "sample",
        "participants",
        "random",
        "control",
        "bias",
        "limitation",
        "available",
        "code",
        "data",
        "preregist",
        "funding",
        "conflict",
    ),
    prefer_start=True,
)

SYSTEM_PROMPT = """You review ONE research paper critically and fairly, using only its \
numbered excerpts.

Write analytical observations, not accusations. Use cautious wording such as \
"The excerpts do not report ...", "The conclusion that ... may not be fully supported because ...".

Rules:
- Each observation has a category, a severity (low, medium, high), the excerpt number it concerns \
("source") and a short quote copied word-for-word from that excerpt.
- For something that is missing, use source 0 and an empty quote. You only see excerpts, so say \
"not found in the excerpts" rather than claiming the paper lacks it.
- At most 8 observations, most important first. Do not invent content.
- Checklist: "reported" (with source and verbatim quote), "not_found" (not in the \
excerpts), or "unclear"."""


def schema() -> dict[str, Any]:
    check_item = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["reported", "not_found", "unclear"]},
            "source": {"type": "integer"},
            "quote": {"type": "string"},
        },
        "required": ["status", "source", "quote"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "observations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": list(CATEGORIES)},
                        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                        "observation": {"type": "string"},
                        "source": {"type": "integer"},
                        "quote": {"type": "string"},
                    },
                    "required": ["category", "severity", "observation", "source", "quote"],
                    "additionalProperties": False,
                },
            },
            "checklist": {
                "type": "object",
                "properties": {key: check_item for key in CHECKLIST},
                "required": list(CHECKLIST),
                "additionalProperties": False,
            },
        },
        "required": ["observations", "checklist"],
        "additionalProperties": False,
    }


def verify(data: dict[str, Any], excerpts: list[Excerpt]) -> dict[str, Any]:
    by_n = {e.n: e for e in excerpts}
    observations = []
    for raw in (data.get("observations") or [])[:MAX_OBSERVATIONS]:
        text = str(raw.get("observation", "")).strip()[:800]
        if not text:
            continue
        category = (
            raw.get("category") if raw.get("category") in CATEGORIES else "missing_information"
        )
        severity = (
            raw.get("severity") if raw.get("severity") in ("low", "medium", "high") else "low"
        )
        source = raw.get("source") if isinstance(raw.get("source"), int) else 0
        quote = str(raw.get("quote", ""))
        if source == 0:
            observations.append(
                {
                    "category": category,
                    "severity": severity,
                    "observation": text,
                    "kind": "absence",
                    "evidence": None,
                }
            )
            continue
        excerpt = by_n.get(source)
        # Observations criticise the text: check the quote, not numbers in the critique.
        verified, reason = check_statement("", quote, excerpt)
        observations.append(
            {
                "category": category,
                "severity": severity,
                "observation": text,
                "kind": "quoted",
                "evidence": evidence_record(excerpt, quote, verified, reason),
            }
        )

    checklist = []
    raw_checklist = data.get("checklist") or {}
    for key, label in CHECKLIST.items():
        item = raw_checklist.get(key) or {}
        status = (
            item.get("status")
            if item.get("status") in ("reported", "not_found", "unclear")
            else "unclear"
        )
        evidence = None
        if status == "reported":
            source = item.get("source")
            excerpt = by_n.get(source) if isinstance(source, int) else None
            verified, reason = check_statement("", str(item.get("quote", "")), excerpt)
            evidence = evidence_record(excerpt, str(item.get("quote", "")), verified, reason)
            if not verified:
                status = "unverified"
        checklist.append({"key": key, "label": label, "status": status, "evidence": evidence})
    return {"observations": observations, "checklist": checklist}


def investigate(
    title: str, chunks: list[Chunk], provider: ChatProvider, budget_chars: int
) -> dict[str, Any]:
    excerpts = select_excerpts(chunks, FOCUS, budget_chars)
    if not excerpts:
        return {"observations": [], "checklist": [], "excerpts_analyzed": 0}
    prompt = f"Paper: “{title}”\n\nExcerpts:\n\n{format_excerpts(excerpts)}"
    result = verify(
        provider.generate_json(SYSTEM_PROMPT, prompt, schema(), max_tokens=1800), excerpts
    )
    result["excerpts_analyzed"] = len(excerpts)
    result["excerpt_pages"] = sorted({e.page_start for e in excerpts if e.page_start is not None})
    return result
