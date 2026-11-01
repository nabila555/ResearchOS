import re

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import select

from app.api.deps import AppSettings, DbSession
from app.models.analysis import AnalysisKind, AnalysisStatus
from app.models.report import Report
from app.reports.pdf import markdown_to_pdf
from app.research_analysis.profile import FIELDS
from app.schemas.analysis import (
    AnalysisCreate,
    AnalysisRead,
    AnalysisSummary,
    PaperProfileRead,
    ProfileField,
    ReportRead,
    ReportSummary,
)
from app.services import analysis_service
from app.services.assistant_service import resolve_chat_provider
from app.services.errors import InvalidRequestError, NotFoundError

router = APIRouter(tags=["analyses"])


def _notify(request: Request) -> None:
    worker = getattr(request.app.state, "analysis_worker", None)
    if worker is not None:
        worker.notify()


@router.post("/analyses", response_model=AnalysisRead, status_code=status.HTTP_202_ACCEPTED)
def create_analysis(
    data: AnalysisCreate, request: Request, db: DbSession, settings: AppSettings
) -> AnalysisRead:
    ai = request.app.state.ai
    provider = ai.chat(resolve_chat_provider(db, settings, ai))
    document_ids = list(data.document_ids)
    if data.kind == AnalysisKind.PROPOSAL and data.gap_analysis_id is not None:
        gap = analysis_service.get_analysis(db, data.gap_analysis_id)
        if gap.kind != AnalysisKind.GAP_ANALYSIS or gap.status != AnalysisStatus.DONE:
            raise InvalidRequestError("Choose a finished gap analysis to build the proposal on.")
        if not document_ids and data.collection_id is None and data.project_id is None:
            document_ids = list(gap.document_ids)
    ids = analysis_service.resolve_document_ids(
        db, document_ids, data.collection_id, data.project_id
    )
    params: dict = {}
    if data.kind in (AnalysisKind.SUMMARY, AnalysisKind.METHODOLOGY, AnalysisKind.PROPOSAL):
        params["style"] = data.style
    if data.kind == AnalysisKind.PROPOSAL:
        if data.topic and data.topic.strip():
            params["topic"] = data.topic.strip()
        if data.gap_analysis_id is not None:
            params["gap_analysis_id"] = data.gap_analysis_id
    if data.kind == AnalysisKind.GAP_ANALYSIS:
        if data.focus and data.focus.strip():
            params["focus"] = data.focus.strip()
        if data.collection_id is not None and not data.document_ids:
            from app.models.library import Collection

            collection = db.get(Collection, data.collection_id)
            if collection is not None:
                params["label"] = f"Research gaps: {collection.name}"
    analysis = analysis_service.create_analysis(
        db, kind=data.kind, document_ids=ids, provider=provider, params=params
    )
    _notify(request)
    return AnalysisRead.model_validate(analysis)


@router.get("/analyses", response_model=list[AnalysisSummary])
def list_analyses(
    db: DbSession, kind: AnalysisKind | None = None, document_id: int | None = None, limit: int = 50
) -> list[AnalysisSummary]:
    rows = analysis_service.list_analyses(db, kind, document_id, min(max(limit, 1), 200))
    return [AnalysisSummary.model_validate(a) for a in rows]


@router.get("/analyses/{analysis_id}", response_model=AnalysisRead)
def get_analysis(analysis_id: int, db: DbSession) -> AnalysisRead:
    return AnalysisRead.model_validate(analysis_service.get_analysis(db, analysis_id))


@router.post("/analyses/{analysis_id}/cancel", response_model=AnalysisRead)
def cancel_analysis(analysis_id: int, db: DbSession) -> AnalysisRead:
    return AnalysisRead.model_validate(analysis_service.cancel_analysis(db, analysis_id))


@router.post(
    "/analyses/{analysis_id}/rerun",
    response_model=AnalysisRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def rerun_analysis(
    analysis_id: int, request: Request, db: DbSession, settings: AppSettings
) -> AnalysisRead:
    original = analysis_service.get_analysis(db, analysis_id)
    ai = request.app.state.ai
    provider = ai.chat(resolve_chat_provider(db, settings, ai))
    analysis = analysis_service.create_analysis(
        db,
        kind=original.kind,
        document_ids=list(original.document_ids),
        provider=provider,
        params=dict(original.params),
    )
    _notify(request)
    return AnalysisRead.model_validate(analysis)


@router.delete("/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(analysis_id: int, db: DbSession) -> Response:
    analysis_service.delete_analysis(db, analysis_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/documents/{document_id}/profile", response_model=PaperProfileRead)
def get_profile(document_id: int, db: DbSession) -> PaperProfileRead:
    found = analysis_service.get_profile(db, document_id)
    if found is None:
        raise NotFoundError("This paper has no profile yet.")
    profile, stale = found
    return PaperProfileRead(
        document_id=document_id,
        provider=profile.provider,
        model=profile.model,
        stale=stale,
        passages_used=profile.passages_used,
        fields=[
            ProfileField(
                key=f.key,
                label=f.label,
                status=profile.fields.get(f.key, {}).get("status", "not_reported"),
                statements=profile.fields.get(f.key, {}).get("statements", []),
            )
            for f in FIELDS
        ],
        updated_at=profile.updated_at,
    )


@router.get("/reports", response_model=list[ReportSummary])
def list_reports(db: DbSession, report_type: str | None = None) -> list[ReportSummary]:
    stmt = select(Report).order_by(Report.created_at.desc(), Report.id.desc()).limit(500)
    if report_type:
        stmt = stmt.where(Report.report_type == report_type)
    return [ReportSummary.model_validate(r) for r in db.scalars(stmt)]


def _get_report(db: DbSession, report_id: int) -> Report:
    report = db.get(Report, report_id)
    if report is None:
        raise NotFoundError(f"Report {report_id} not found")
    return report


@router.get("/reports/{report_id}", response_model=ReportRead)
def get_report(report_id: int, db: DbSession) -> ReportRead:
    return ReportRead.model_validate(_get_report(db, report_id))


@router.get("/reports/{report_id}/download")
def download_report(report_id: int, db: DbSession) -> Response:
    report = _get_report(db, report_id)
    return Response(
        content=report.content_markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_filename(report)}.md"'},
    )


@router.get("/reports/{report_id}/pdf")
def download_report_pdf(report_id: int, db: DbSession) -> Response:
    report = _get_report(db, report_id)
    return Response(
        content=markdown_to_pdf(report.content_markdown, report.title),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_filename(report)}.pdf"'},
    )


def _filename(report: Report) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", report.title).strip("-")[:80] or "report"


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(report_id: int, db: DbSession) -> Response:
    db.delete(_get_report(db, report_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
