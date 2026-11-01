from fastapi import APIRouter

from app.api.routes import (
    analyses,
    assistant,
    citations,
    dashboard,
    documents,
    graph,
    health,
    library,
    projects,
    reviews,
    system,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(system.router)
api_router.include_router(dashboard.router)
api_router.include_router(projects.router)
api_router.include_router(documents.router)
api_router.include_router(library.router)
api_router.include_router(assistant.router)
api_router.include_router(analyses.router)
api_router.include_router(citations.router)
api_router.include_router(graph.router)
api_router.include_router(reviews.router)
