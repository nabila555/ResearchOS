"""Apply Alembic migrations programmatically on startup."""

import logging

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

from app.core.config import BACKEND_DIR

logger = logging.getLogger("researchos")

# Schema that Phase 1 created with metadata.create_all (before Alembic existed).
BASELINE_REVISION = "0001"


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def run_migrations(engine: Engine) -> None:
    config = _alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names())
        if "alembic_version" not in tables and "projects" in tables:
            # Database from Phase 1: adopt it at the baseline instead of recreating tables.
            logger.info("Existing database without migration history; stamping baseline")
            command.stamp(config, BASELINE_REVISION)
        command.upgrade(config, "head")
