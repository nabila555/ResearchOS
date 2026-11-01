from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard_service import build_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardSummary)
def dashboard(db: DbSession) -> DashboardSummary:
    return build_dashboard(db)
