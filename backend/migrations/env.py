"""Alembic environment.

Uses the connection handed over by the app (see app.core.migrations) or, when run
from the CLI, the database URL from app settings.
"""

from alembic import context
from sqlalchemy import Connection

from app import models  # noqa: F401  (registers all tables)
from app.core.config import get_settings
from app.core.database import Base, create_db_engine

target_metadata = Base.metadata


def include_name(name: str | None, type_: str, _parent_names: object) -> bool:
    # FTS5 virtual tables (and their shadow tables) are managed by hand in migrations.
    return not (type_ == "table" and name is not None and "_fts" in name)


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite needs batch mode for ALTER TABLE
        compare_type=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    _run(connection)
else:
    settings = get_settings()
    settings.ensure_directories()
    engine = create_db_engine(settings.resolved_database_url)
    with engine.connect() as conn:
        _run(conn)
    engine.dispose()
