"""library search index

Adds an author lookup index and SQLite FTS5 full-text indexes:

* ``chunks_fts``: external-content index over ``chunks.text``, kept in sync by triggers.
* ``documents_fts``: document-level fields (title, authors, abstract, keywords);
  rowid = documents.id, maintained by ``app.services.search_service``.

FTS5 is SQLite-specific. On other databases the full-text tables are skipped and
search falls back to LIKE queries (see search_service).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-02 01:55:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TOKENIZER = "porter unicode61 remove_diacritics 2"


def upgrade() -> None:
    with op.batch_alter_table("document_authors", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_document_authors_author_id"), ["author_id"], unique=False
        )

    if op.get_bind().dialect.name != "sqlite":
        return

    op.execute(
        f"""CREATE VIRTUAL TABLE chunks_fts USING fts5(
            text, content='chunks', content_rowid='id', tokenize='{TOKENIZER}'
        )"""
    )
    op.execute(
        """CREATE TRIGGER chunks_fts_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
        END"""
    )
    op.execute(
        """CREATE TRIGGER chunks_fts_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
        END"""
    )
    op.execute(
        """CREATE TRIGGER chunks_fts_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
            INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
        END"""
    )
    op.execute("INSERT INTO chunks_fts(chunks_fts) VALUES ('rebuild')")

    op.execute(
        f"""CREATE VIRTUAL TABLE documents_fts USING fts5(
            title, authors, abstract, keywords, tokenize='{TOKENIZER}'
        )"""
    )
    # Documents are deleted with ON DELETE CASCADE elsewhere; keep the index in step.
    op.execute(
        """CREATE TRIGGER documents_fts_ad AFTER DELETE ON documents BEGIN
            DELETE FROM documents_fts WHERE rowid = old.id;
        END"""
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS documents_fts_ad")
        op.execute("DROP TABLE IF EXISTS documents_fts")
        op.execute("DROP TRIGGER IF EXISTS chunks_fts_au")
        op.execute("DROP TRIGGER IF EXISTS chunks_fts_ad")
        op.execute("DROP TRIGGER IF EXISTS chunks_fts_ai")
        op.execute("DROP TABLE IF EXISTS chunks_fts")

    with op.batch_alter_table("document_authors", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_document_authors_author_id"))
