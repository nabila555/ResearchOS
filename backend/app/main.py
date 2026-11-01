"""FastAPI application factory.

Run locally with:  uvicorn app.main:app --reload --port 8000
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import api_router
from app.core.config import Settings, get_settings
from app.core.database import create_db_engine, create_session_factory
from app.core.migrations import run_migrations
from app.document_processing.types import (
    ExtractionError,
    FileTooLargeError,
    InvalidFileError,
    ProcessingError,
    UnsupportedFileTypeError,
)
from app.document_processing.web import FetchError, UnsafeUrlError
from app.services.errors import ServiceError

logger = logging.getLogger("researchos")

PROCESSING_STATUS: dict[type[ProcessingError], int] = {
    UnsupportedFileTypeError: 415,
    FileTooLargeError: 413,
    InvalidFileError: 400,
    ExtractionError: 422,
    UnsafeUrlError: 400,
    FetchError: 422,
}


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def _service_error(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse({"detail": exc.message, **exc.extra}, status_code=exc.status_code)

    @app.exception_handler(ProcessingError)
    async def _processing_error(_: Request, exc: ProcessingError) -> JSONResponse:
        code = next((c for t, c in PROCESSING_STATUS.items() if isinstance(exc, t)), 400)
        return JSONResponse({"detail": str(exc)}, status_code=code)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.ensure_directories()
        engine = create_db_engine(settings.resolved_database_url)
        run_migrations(engine)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        logger.info("ResearchOS %s started (data dir: %s)", __version__, settings.data_dir)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Local-first research operating system API.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )
    _register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
