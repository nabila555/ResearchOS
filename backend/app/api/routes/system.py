from fastapi import APIRouter

from app import __version__
from app.ai.ollama import get_ollama_status
from app.api.deps import AppSettings
from app.schemas.system import AIStatus, AnthropicStatus, StorageStatus, SystemStatus

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status", response_model=SystemStatus)
async def system_status(settings: AppSettings) -> SystemStatus:
    db_url = settings.resolved_database_url
    return SystemStatus(
        app_name=settings.app_name,
        version=__version__,
        environment=settings.environment,
        storage=StorageStatus(
            data_dir=str(settings.data_dir),
            database_backend=db_url.split(":", 1)[0].split("+", 1)[0],
            max_upload_mb=settings.max_upload_mb,
        ),
        ai=AIStatus(
            active_provider=settings.ai_provider,
            ollama=await get_ollama_status(settings),
            anthropic=AnthropicStatus(
                configured=settings.anthropic_api_key is not None,
                model=settings.anthropic_model,
            ),
        ),
    )
