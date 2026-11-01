"""Queue and run research-intelligence analyses in the background.

Paper profiles are cached per document and reused by comparisons and gap analyses;
a profile is rebuilt automatically when the document's text (its chunks) changes.
"""

import logging
import threading
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.exc import ObjectDeletedError

from app.ai.providers import ChatProvider, ProviderError
from app.ai.registry import AIServices
from app.core.config import Settings
from app.models.analysis import Analysis, AnalysisKind, AnalysisStatus, PaperProfile
from app.models.library import Chunk, Document, DocumentAuthor, collection_documents
from app.models.project import project_documents
from app.models.report import Report
from app.reports import builders
from app.research_analysis import detective, gaps, synthesis
from app.research_analysis.evidence import chunk_signature
from app.research_analysis.markdown import comparison_markdown, detective_markdown, gaps_markdown
from app.research_analysis.profile import FIELDS, STEPS, build_profile
from app.services import citation_service
from app.services.activity_service import log_activity
from app.services.errors import InvalidRequestError, NotFoundError

logger = logging.getLogger("researchos.analysis")

LIMITS = {
    AnalysisKind.PROFILE: (1, 1),
    AnalysisKind.DETECTIVE: (1, 1),
    AnalysisKind.COMPARISON: (2, 6),
    AnalysisKind.GAP_ANALYSIS: (2, 12),
    AnalysisKind.THEME_SUMMARY: (1, 15),
    AnalysisKind.SUMMARY: (1, 10),
    AnalysisKind.METHODOLOGY: (2, 15),
    AnalysisKind.PROPOSAL: (2, 12),
}
REPORT_TYPES = {
    AnalysisKind.COMPARISON: "comparison",
    AnalysisKind.GAP_ANALYSIS: "gap_analysis",
    AnalysisKind.DETECTIVE: "detective",
    AnalysisKind.SUMMARY: "summary",
    AnalysisKind.METHODOLOGY: "methodology",
    AnalysisKind.PROPOSAL: "proposal",
}


class AnalysisCancelled(Exception):
    pass


# --- Creation & queries ------------------------------------------------------------------


def resolve_document_ids(
    db: Session,
    document_ids: list[int],
    collection_id: int | None,
    project_id: int | None,
) -> list[int]:
    ids = list(dict.fromkeys(document_ids))
    if collection_id is not None:
        ids += list(
            db.scalars(
                select(collection_documents.c.document_id).where(
                    collection_documents.c.collection_id == collection_id
                )
            )
        )
    if project_id is not None:
        ids += list(
            db.scalars(
                select(project_documents.c.document_id).where(
                    project_documents.c.project_id == project_id
                )
            )
        )
    return list(dict.fromkeys(ids))


def create_analysis(
    db: Session,
    *,
    kind: AnalysisKind,
    document_ids: list[int],
    provider: ChatProvider,
    params: dict[str, Any] | None = None,
) -> Analysis:
    low, high = LIMITS[kind]
    if not low <= len(document_ids) <= high:
        noun = "document" if high == 1 else "documents"
        raise InvalidRequestError(
            f"Select {low} {noun}." if low == high else f"Select between {low} and {high} {noun}."
        )
    docs = {d.id: d for d in db.scalars(select(Document).where(Document.id.in_(document_ids)))}
    missing = [i for i in document_ids if i not in docs]
    if missing:
        raise NotFoundError(f"Document {missing[0]} not found")
    for doc_id in document_ids:
        if db.scalar(select(Chunk.id).where(Chunk.document_id == doc_id).limit(1)) is None:
            raise InvalidRequestError(f"“{docs[doc_id].title}” has no extracted text to analyse.")

    existing = db.scalars(
        select(Analysis).where(
            Analysis.kind == kind,
            Analysis.status.in_([AnalysisStatus.PENDING, AnalysisStatus.RUNNING]),
        )
    )
    for analysis in existing:
        if analysis.document_ids == document_ids and analysis.params == (params or {}):
            return analysis  # the same work is already queued

    first = docs[document_ids[0]].title
    titles = {
        AnalysisKind.PROFILE: f"Paper profile: {first}",
        AnalysisKind.DETECTIVE: f"Paper Detective: {first}",
        AnalysisKind.COMPARISON: (
            f"Comparison: {first} vs {docs[document_ids[1]].title}"
            if len(document_ids) == 2
            else f"Comparison of {len(document_ids)} papers"
        ),
        AnalysisKind.THEME_SUMMARY: f"Theme summary: {(params or {}).get('theme_name', 'theme')}",
        AnalysisKind.SUMMARY: (
            f"Research summary: {first}"
            if len(document_ids) == 1
            else f"Research summary of {len(document_ids)} papers"
        ),
        AnalysisKind.METHODOLOGY: f"Methodology analysis of {len(document_ids)} papers",
        AnalysisKind.PROPOSAL: (
            f"Research proposal: {(params or {})['topic']}"
            if (params or {}).get("topic")
            else "Research proposal draft"
        ),
        AnalysisKind.GAP_ANALYSIS: (params or {}).get("label")
        or f"Research gaps across {len(document_ids)} papers",
    }
    analysis = Analysis(
        kind=kind,
        title=titles[kind][:300],
        document_ids=document_ids,
        params=params or {},
        provider=provider.name,
        model=provider.model,
        progress_message="Waiting in queue",
    )
    db.add(analysis)
    db.commit()
    return analysis


def get_analysis(db: Session, analysis_id: int) -> Analysis:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise NotFoundError(f"Analysis {analysis_id} not found")
    return analysis


def list_analyses(
    db: Session, kind: AnalysisKind | None = None, document_id: int | None = None, limit: int = 50
) -> list[Analysis]:
    stmt = select(Analysis).order_by(Analysis.created_at.desc(), Analysis.id.desc())
    if kind is not None:
        stmt = stmt.where(Analysis.kind == kind)
    rows = list(db.scalars(stmt.limit(500)))
    if document_id is not None:
        rows = [a for a in rows if document_id in a.document_ids]
    return rows[:limit]


def cancel_analysis(db: Session, analysis_id: int) -> Analysis:
    analysis = get_analysis(db, analysis_id)
    if analysis.status in (AnalysisStatus.PENDING, AnalysisStatus.RUNNING):
        analysis.status = AnalysisStatus.CANCELLED
        analysis.progress_message = "Cancelled"
        db.commit()
    return analysis


def delete_analysis(db: Session, analysis_id: int) -> None:
    analysis = get_analysis(db, analysis_id)
    if analysis.status in (AnalysisStatus.PENDING, AnalysisStatus.RUNNING):
        analysis.status = AnalysisStatus.CANCELLED
        db.flush()
    db.delete(analysis)
    db.commit()


def get_profile(db: Session, document_id: int) -> tuple[PaperProfile, bool] | None:
    """The cached profile and whether it is stale (document text changed since)."""
    profile = db.get(PaperProfile, document_id)
    if profile is None:
        return None
    chunks = list(db.scalars(select(Chunk).where(Chunk.document_id == document_id)))
    return profile, profile.chunk_signature != chunk_signature(chunks)


# --- Execution ----------------------------------------------------------------------------


class _Runner:
    def __init__(self, db: Session, analysis: Analysis, provider: ChatProvider, settings: Settings):
        self.db, self.analysis, self.provider, self.settings = db, analysis, provider, settings
        self.total_steps = 1
        self.done_steps = 0

    def step(self, message: str) -> None:
        try:
            self.db.refresh(self.analysis, ["status"])
        except ObjectDeletedError:
            raise AnalysisCancelled from None  # deleted while running
        if self.analysis.status == AnalysisStatus.CANCELLED:
            raise AnalysisCancelled
        self.analysis.progress = round(min(self.done_steps / self.total_steps, 0.99), 3)
        self.analysis.progress_message = message[:300]
        self.db.commit()
        self.done_steps += 1

    def chunks(self, document_id: int) -> list[Chunk]:
        return list(
            self.db.scalars(
                select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index)
            )
        )

    def ensure_profile(self, doc: Document, force: bool = False) -> dict[str, Any]:
        chunks = self.chunks(doc.id)
        signature = chunk_signature(chunks)
        profile = self.db.get(PaperProfile, doc.id)
        if profile is not None and profile.chunk_signature == signature and not force:
            self.done_steps += len(STEPS)
            return profile.fields

        def on_step(index: int, name: str) -> None:
            self.step(f"Reading “{doc.title[:80]}”: {name} ({index + 1}/{len(STEPS)})")

        fields, used = build_profile(
            doc.title, chunks, self.provider, self.settings.analysis_excerpt_chars, on_step
        )
        if profile is None:
            profile = PaperProfile(document_id=doc.id)
            self.db.add(profile)
        profile.provider, profile.model = self.provider.name, self.provider.model
        profile.fields, profile.chunk_signature, profile.passages_used = fields, signature, used
        self.db.commit()
        return fields


def _documents(db: Session, ids: list[int]) -> list[Document]:
    docs = {
        d.id: d
        for d in db.scalars(
            select(Document)
            .where(Document.id.in_(ids))
            .options(selectinload(Document.authors).selectinload(DocumentAuthor.author))
        )
    }
    return [docs[i] for i in ids if i in docs]


def _latest_detective_results(db: Session, document_ids: list[int]) -> dict[int, dict[str, Any]]:
    found: dict[int, dict[str, Any]] = {}
    rows = db.scalars(
        select(Analysis)
        .where(Analysis.kind == AnalysisKind.DETECTIVE, Analysis.status == AnalysisStatus.DONE)
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
    )
    for analysis in rows:
        doc_id = analysis.document_ids[0] if analysis.document_ids else None
        if doc_id in document_ids and doc_id not in found and analysis.result:
            found[doc_id] = analysis.result
    return found


def _run(runner: _Runner) -> tuple[dict[str, Any], str | None]:
    """Execute the analysis. Returns (result, markdown report or None)."""
    analysis, db = runner.analysis, runner.db
    docs = _documents(db, analysis.document_ids)
    if len(docs) != len(analysis.document_ids):
        raise ProviderError("Some documents were deleted after the analysis was queued.")
    model = f"{analysis.provider} · {analysis.model}"

    if analysis.kind == AnalysisKind.PROFILE:
        runner.total_steps = len(STEPS)
        runner.ensure_profile(docs[0], force=True)
        return {"document_id": docs[0].id}, None

    if analysis.kind == AnalysisKind.DETECTIVE:
        runner.total_steps = 1
        runner.step(f"Reviewing “{docs[0].title[:80]}”")
        result = detective.investigate(
            docs[0].title,
            runner.chunks(docs[0].id),
            runner.provider,
            runner.settings.analysis_excerpt_chars + 2000,
        )
        result["document"] = {"id": docs[0].id, "title": docs[0].title}
        return result, detective_markdown(analysis.title, result, model)

    synthesis_step = analysis.kind in (
        AnalysisKind.GAP_ANALYSIS,
        AnalysisKind.THEME_SUMMARY,
        AnalysisKind.PROPOSAL,
    )
    runner.total_steps = len(STEPS) * len(docs) + (1 if synthesis_step else 0)
    profiles = {doc.id: runner.ensure_profile(doc) for doc in docs}
    style = analysis.params.get("style", "apa")
    cites = {c.id: c for c in citation_service.load(db, [d.id for d in docs])}

    if analysis.kind == AnalysisKind.SUMMARY:
        markdown = builders.summary_markdown(
            analysis.title,
            [(cites.get(d.id), d.title, profiles[d.id]) for d in docs],
            analysis.model,
            style,
        )
        return {"document_ids": analysis.document_ids}, markdown

    if analysis.kind == AnalysisKind.METHODOLOGY:
        detective_results = _latest_detective_results(db, [d.id for d in docs])
        markdown = builders.methodology_markdown(
            analysis.title,
            [(cites.get(d.id), d.title, profiles[d.id], detective_results.get(d.id)) for d in docs],
            analysis.model,
            style,
        )
        return {"document_ids": analysis.document_ids}, markdown

    if analysis.kind == AnalysisKind.COMPARISON:
        result = {
            "documents": [
                {
                    "id": d.id,
                    "title": d.title,
                    "year": d.publication_year,
                    "authors": [link.author.full_name for link in d.authors],
                }
                for d in docs
            ],
            "fields": [{"key": f.key, "label": f.label} for f in FIELDS],
            "profiles": {str(doc_id): fields for doc_id, fields in profiles.items()},
        }
        return result, comparison_markdown(analysis.title, result, model)

    digests = [
        gaps.PaperDigest(f"P{i + 1}", d.id, d.title, d.publication_year, profiles[d.id])
        for i, d in enumerate(docs)
    ]
    if analysis.kind == AnalysisKind.PROPOSAL:
        runner.step(f"Drafting a proposal from {len(docs)} papers")
        gap_result = None
        gap_id = analysis.params.get("gap_analysis_id")
        if gap_id is not None:
            gap = db.get(Analysis, gap_id)
            if gap is not None and gap.status == AnalysisStatus.DONE:
                gap_result = gap.result
        result = builders.draft_proposal(
            runner.provider, digests, analysis.params.get("topic"), gap_result
        )
        markdown = builders.proposal_markdown(
            analysis.title,
            result,
            {d.label: cites.get(d.document_id) for d in digests},
            analysis.model,
            style,
        )
        return result, markdown

    if analysis.kind == AnalysisKind.THEME_SUMMARY:
        runner.step(f"Writing a synthesis of {len(docs)} papers")
        result = synthesis.summarise_theme(
            analysis.params.get("theme_name", "Theme"),
            analysis.params.get("research_question"),
            digests,
            runner.provider,
        )
        return result, None

    runner.step(f"Looking for gaps across {len(docs)} papers")
    result = gaps.find_gaps(digests, runner.provider, analysis.params.get("focus"))
    return result, gaps_markdown(analysis.title, result, model)


def process_next(
    session_factory: Callable[[], Session], ai: AIServices, settings: Settings
) -> bool:
    """Run one pending analysis to completion. Returns False if the queue was empty."""
    with session_factory() as db:
        analysis = db.scalar(
            select(Analysis)
            .where(Analysis.status == AnalysisStatus.PENDING)
            .order_by(Analysis.created_at, Analysis.id)
            .limit(1)
        )
        if analysis is None:
            return False
        analysis.status = AnalysisStatus.RUNNING
        analysis.progress_message = "Starting"
        db.commit()
        try:
            runner = _Runner(db, analysis, ai.chat(analysis.provider), settings)
            result, report_markdown = _run(runner)
        except AnalysisCancelled:
            return True
        except ProviderError as exc:
            db.rollback()
            _fail(db, analysis.id, str(exc))
            return True
        except Exception:
            logger.exception("Analysis %s failed", analysis.id)
            db.rollback()
            _fail(db, analysis.id, "The analysis failed unexpectedly. Check the backend log.")
            return True

        try:
            db.refresh(analysis)
        except ObjectDeletedError:
            return True
        if analysis.status == AnalysisStatus.CANCELLED:
            return True
        analysis.result = result
        analysis.status = AnalysisStatus.DONE
        analysis.progress, analysis.progress_message = 1.0, "Done"
        if report_markdown is not None:
            report = Report(
                title=analysis.title,
                report_type=REPORT_TYPES[analysis.kind],
                content_markdown=report_markdown,
                source_document_ids=analysis.document_ids,
                model_used=f"{analysis.provider} · {analysis.model}",
            )
            db.add(report)
            db.flush()
            analysis.report_id = report.id
        log_activity(
            db,
            action="analysis.completed",
            entity_type="analysis",
            entity_id=analysis.id,
            summary=f"Finished {analysis.title[:200]}",
        )
        db.commit()
        return True


def _fail(db: Session, analysis_id: int, message: str) -> None:
    analysis = db.get(Analysis, analysis_id)
    if analysis is not None and analysis.status != AnalysisStatus.CANCELLED:
        analysis.status = AnalysisStatus.FAILED
        analysis.error = message
        analysis.progress_message = "Failed"
        db.commit()


def reset_interrupted(session_factory: Callable[[], Session]) -> None:
    with session_factory() as db:
        for analysis in db.scalars(
            select(Analysis).where(Analysis.status == AnalysisStatus.RUNNING)
        ):
            analysis.status = AnalysisStatus.PENDING
            analysis.progress_message = "Restarting after interruption"
        db.commit()


class AnalysisWorker:
    """Background thread that runs queued analyses one at a time."""

    POLL_SECONDS = 3.0

    def __init__(self, session_factory: Callable[[], Session], ai: AIServices, settings: Settings):
        self._session_factory, self._ai, self._settings = session_factory, ai, settings
        self._wake, self._stop = threading.Event(), threading.Event()
        self._thread = threading.Thread(target=self._run, name="researchos-analysis", daemon=True)

    def start(self) -> None:
        reset_interrupted(self._session_factory)
        self._thread.start()

    def notify(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                worked = process_next(self._session_factory, self._ai, self._settings)
            except Exception:
                logger.exception("Analysis worker error")
                worked = False
            if not worked:
                self._wake.wait(self.POLL_SECONDS)
                self._wake.clear()
