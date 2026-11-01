"""Structured, evidence-linked extraction of one paper ("paper profile").

The paper is processed in three focused steps (overview, methods, results), each
with its own excerpts, so even an 8k-context local model sees the relevant text.
"""

from collections.abc import Callable
from dataclasses import dataclass
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

MAX_STATEMENTS = 6


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    hint: str
    multiple: bool


@dataclass(frozen=True)
class Step:
    name: str
    focus: Focus
    fields: tuple[FieldSpec, ...]


STEPS: tuple[Step, ...] = (
    Step(
        "overview",
        Focus(
            sections=(
                "abstract",
                "introduction",
                "background",
                "framework",
                "literature",
                "related",
            ),
            keywords=(
                "aim",
                "objective",
                "purpose",
                "investigat",
                "examin",
                "hypothes",
                "question",
                "theory",
                "framework",
                "model",
            ),
            prefer_start=True,
        ),
        (
            FieldSpec(
                "research_objective", "Research objective", "what the study set out to do", False
            ),
            FieldSpec(
                "research_questions",
                "Research questions / hypotheses",
                "explicit questions or hypotheses",
                True,
            ),
            FieldSpec(
                "theoretical_framework",
                "Theoretical framework",
                "named theories or conceptual models used",
                False,
            ),
        ),
    ),
    Step(
        "methods",
        Focus(
            sections=(
                "method",
                "material",
                "data",
                "participant",
                "experiment",
                "design",
                "procedure",
            ),
            keywords=(
                "participant",
                "sample",
                "n =",
                "recruit",
                "dataset",
                "data",
                "collected",
                "design",
                "procedure",
                "measure",
                "survey",
                "interview",
                "random",
            ),
        ),
        (
            FieldSpec(
                "methodology", "Methodology & design", "study design and main methods", False
            ),
            FieldSpec(
                "dataset", "Data / materials", "datasets, corpora, instruments or materials", False
            ),
            FieldSpec(
                "sample_size",
                "Sample size",
                "number of participants/cases/items exactly as stated",
                False,
            ),
            FieldSpec(
                "population", "Population / setting", "who or what was studied, where", False
            ),
        ),
    ),
    Step(
        "results",
        Focus(
            sections=("result", "finding", "discussion", "limitation", "conclusion", "future"),
            keywords=(
                "found",
                "result",
                "show",
                "significant",
                "correlat",
                "effect",
                "suggest",
                "limitation",
                "future",
                "further research",
            ),
        ),
        (
            FieldSpec("key_findings", "Key findings", "main empirical results", True),
            FieldSpec("limitations", "Limitations", "limitations the authors acknowledge", True),
            FieldSpec(
                "future_research", "Future research", "directions the authors recommend", True
            ),
        ),
    ),
)

FIELDS: tuple[FieldSpec, ...] = tuple(f for step in STEPS for f in step.fields)

SYSTEM_PROMPT = """You extract structured information from numbered excerpts of ONE research paper.

Rules:
- Use only the excerpts. Do not use outside knowledge or guess.
- If the excerpts do not state a field, set "reported" to false and "statements" to [].
- Each statement is short and factual. "source" is the excerpt number it comes from.
- "quote" must be copied word-for-word from that excerpt (5 to 30 words) and must \
support the statement.
- Copy numbers exactly as written; never compute or round them.
- Report what the authors state; do not add your own evaluation."""

_STATEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "source": {"type": "integer"},
        "quote": {"type": "string"},
    },
    "required": ["text", "source", "quote"],
    "additionalProperties": False,
}


def step_schema(step: Step) -> dict[str, Any]:
    field_schema = {
        "type": "object",
        "properties": {
            "reported": {"type": "boolean"},
            "statements": {"type": "array", "items": _STATEMENT_SCHEMA},
        },
        "required": ["reported", "statements"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {f.key: field_schema for f in step.fields},
        "required": [f.key for f in step.fields],
        "additionalProperties": False,
    }


def step_prompt(title: str, step: Step, excerpts: list[Excerpt]) -> str:
    wanted = "\n".join(
        f"- {f.key}: {f.hint}{' (one statement per item)' if f.multiple else ' (one statement)'}"
        for f in step.fields
    )
    return (
        f"Paper: “{title}”\n\nExcerpts:\n\n{format_excerpts(excerpts)}\n\n"
        f"Extract these fields:\n{wanted}"
    )


def field_status(statements: list[dict[str, Any]]) -> str:
    if not statements:
        return "not_reported"
    verified = sum(1 for s in statements if s["evidence"]["verified"])
    if verified == len(statements):
        return "verified"
    return "partial" if verified else "unverified"


def parse_step(step: Step, data: dict[str, Any], excerpts: list[Excerpt]) -> dict[str, Any]:
    by_n = {e.n: e for e in excerpts}
    fields: dict[str, Any] = {}
    for spec in step.fields:
        raw = data.get(spec.key) or {}
        statements: list[dict[str, Any]] = []
        if raw.get("reported"):
            items = raw.get("statements") or []
            for item in items[: MAX_STATEMENTS if spec.multiple else 1]:
                text = str(item.get("text", "")).strip()[:500]
                if not text:
                    continue
                quote = str(item.get("quote", ""))
                source = item.get("source")
                excerpt = by_n.get(source) if isinstance(source, int) else None
                verified, reason = check_statement(text, quote, excerpt)
                statements.append(
                    {"text": text, "evidence": evidence_record(excerpt, quote, verified, reason)}
                )
        fields[spec.key] = {"status": field_status(statements), "statements": statements}
    return fields


def build_profile(
    title: str,
    chunks: list[Chunk],
    provider: ChatProvider,
    budget_chars: int,
    on_step: Callable[[int, str], None] | None = None,
) -> tuple[dict[str, Any], int]:
    """Run all extraction steps. Returns (fields, number of distinct excerpts used)."""
    fields: dict[str, Any] = {}
    used: set[int] = set()
    for index, step in enumerate(STEPS):
        if on_step:
            on_step(index, step.name)
        excerpts = select_excerpts(chunks, step.focus, budget_chars)
        used.update(e.chunk_id for e in excerpts)
        if not excerpts:
            fields.update(
                {f.key: {"status": "not_reported", "statements": []} for f in step.fields}
            )
            continue
        data = provider.generate_json(
            SYSTEM_PROMPT, step_prompt(title, step, excerpts), step_schema(step), max_tokens=1200
        )
        fields.update(parse_step(step, data, excerpts))
    return fields, len(used)
