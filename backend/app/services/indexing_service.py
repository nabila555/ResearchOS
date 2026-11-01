"""Background embedding of document chunks for semantic search.

Jobs are rows in ``index_jobs`` so they survive restarts. A single worker thread
processes them one at a time. When the embedding provider is unreachable (Ollama
not running) jobs stay pending and the worker backs off instead of failing them.
"""

import logging
import threading
from collections.abc import Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.ai.providers import ProviderError, ProviderUnavailableError
from app.ai.registry import AIServices
from app.ai.vector_index import to_blob
from app.models.ai import ChunkEmbedding, IndexJob, IndexStatus, JobStatus
from app.models.library import Chunk, Document

logger = logging.getLogger("researchos.indexing")

MAX_ATTEMPTS = 3


def enqueue(db: Session, document_ids: list[int]) -> int:
    """Queue documents for (re-)indexing. The caller commits. Returns the number queued."""
    queued = 0
    for doc_id in dict.fromkeys(document_ids):
        already = db.scalar(
            select(IndexJob.id).where(
                IndexJob.document_id == doc_id,
                IndexJob.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
            )
        )
        if already is None:
            db.add(IndexJob(document_id=doc_id))
            queued += 1
        db.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(ai_index_status=IndexStatus.PENDING.value, ai_index_error=None)
        )
    return queued


def enqueue_unindexed(db: Session, include_failed: bool = True) -> int:
    statuses = [IndexStatus.NONE.value] + ([IndexStatus.FAILED.value] if include_failed else [])
    ids = list(db.scalars(select(Document.id).where(Document.ai_index_status.in_(statuses))))
    return enqueue(db, ids)


def reset_interrupted_jobs(db: Session) -> None:
    """Jobs left RUNNING by a crash or restart go back to the queue."""
    db.execute(
        update(IndexJob)
        .where(IndexJob.status == JobStatus.RUNNING)
        .values(status=JobStatus.PENDING)
    )
    db.commit()


def _claim_next(db: Session) -> IndexJob | None:
    job = db.scalar(
        select(IndexJob)
        .where(IndexJob.status == JobStatus.PENDING)
        .order_by(IndexJob.created_at, IndexJob.id)
        .limit(1)
    )
    if job is not None:
        job.status = JobStatus.RUNNING
        job.attempts += 1
        db.commit()
    return job


def _embed_document(db: Session, ai: AIServices, document_id: int, batch_size: int) -> None:
    model = ai.embedder.model
    rows = db.execute(
        select(Chunk.id, Chunk.text)
        .outerjoin(
            ChunkEmbedding,
            (ChunkEmbedding.chunk_id == Chunk.id) & (ChunkEmbedding.model == model),
        )
        .where(Chunk.document_id == document_id, ChunkEmbedding.chunk_id.is_(None))
        .order_by(Chunk.chunk_index)
    ).all()
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        vectors = ai.embedder.embed_documents([text for _, text in batch])
        for (chunk_id, _), vector in zip(batch, vectors, strict=True):
            db.add(
                ChunkEmbedding(
                    chunk_id=chunk_id, model=model, dim=len(vector), vector=to_blob(vector)
                )
            )
        db.commit()  # keep progress if a later batch fails


def process_next(
    session_factory: Callable[[], Session], ai: AIServices, batch_size: int = 16
) -> bool:
    """Process one pending job. Returns False when there was nothing to do.

    Raises ProviderUnavailableError (after re-queueing the job) so the caller can back off.
    """
    with session_factory() as db:
        job = _claim_next(db)
        if job is None:
            return False
        job_id, document_id = job.id, job.document_id
        try:
            _embed_document(db, ai, document_id, batch_size)
        except ProviderUnavailableError:
            db.rollback()
            # Waiting for the provider doesn't count as a failed attempt.
            db.execute(
                update(IndexJob)
                .where(IndexJob.id == job_id)
                .values(status=JobStatus.PENDING, attempts=IndexJob.attempts - 1)
            )
            db.commit()
            raise
        except Exception as exc:  # any per-document failure is recorded, not fatal
            db.rollback()
            message = (
                str(exc) if isinstance(exc, ProviderError) else "Indexing failed unexpectedly."
            )
            logger.exception("Indexing document %s failed", document_id)
            job = db.get(IndexJob, job_id)
            if job is None:
                return True
            final = job.attempts >= MAX_ATTEMPTS or isinstance(exc, ProviderError)
            job.status = JobStatus.FAILED if final else JobStatus.PENDING
            job.error = message
            if final:
                db.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(ai_index_status=IndexStatus.FAILED.value, ai_index_error=message)
                )
            db.commit()
            return True

        job = db.get(IndexJob, job_id)
        if job is not None:
            job.status = JobStatus.DONE
            job.error = None
        # The document may have been deleted meanwhile; update() is then a no-op.
        db.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(ai_index_status=IndexStatus.READY.value, ai_index_error=None)
        )
        db.commit()
        return True


class IndexWorker:
    """Single background thread that drains the index job queue."""

    IDLE_POLL_SECONDS = 5.0
    UNAVAILABLE_BACKOFF_SECONDS = 30.0

    def __init__(self, session_factory: Callable[[], Session], ai: AIServices, batch_size: int):
        self._session_factory = session_factory
        self._ai = ai
        self._batch_size = batch_size
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="researchos-indexer", daemon=True)
        self.waiting_for_provider = False

    def start(self) -> None:
        with self._session_factory() as db:
            reset_interrupted_jobs(db)
        self._thread.start()

    def notify(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout=10)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                worked = process_next(self._session_factory, self._ai, self._batch_size)
                self.waiting_for_provider = False
            except ProviderUnavailableError:
                self.waiting_for_provider = True
                self._wake.wait(self.UNAVAILABLE_BACKOFF_SECONDS)
                self._wake.clear()
                continue
            except Exception:
                logger.exception("Index worker error")
                worked = False
            if not worked:
                self._wake.wait(self.IDLE_POLL_SECONDS)
                self._wake.clear()
