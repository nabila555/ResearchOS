from fastapi import APIRouter

from app.api.routes import assistant, dashboard, documents, health, library, projects, system

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(system.router)
api_router.include_router(dashboard.router)
api_router.include_router(projects.router)
api_router.include_router(documents.router)
api_router.include_router(library.router)
api_router.include_router(assistant.router)
