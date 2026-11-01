"""In-memory cosine-similarity search over embeddings stored in SQLite.

Vectors live in ``chunk_embeddings`` (float32 blobs). The index loads them into a
normalised NumPy matrix per embedding model and reloads automatically when the
stored set changes, so writers never have to invalidate it. Brute-force search
over 100k x 768 vectors takes well under 100 ms on a laptop CPU.
"""

import threading
from dataclasses import dataclass

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ai import ChunkEmbedding
from app.models.library import Chunk


def to_blob(vector: list[float]) -> bytes:
    return np.asarray(vector, dtype="<f4").tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype="<f4")


@dataclass
class _Matrix:
    signature: tuple[int, int]
    chunk_ids: np.ndarray
    document_ids: np.ndarray
    vectors: np.ndarray  # rows L2-normalised


class VectorIndex:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, _Matrix] = {}

    @staticmethod
    def _signature(db: Session, model: str) -> tuple[int, int]:
        count, id_sum = db.execute(
            select(func.count(), func.coalesce(func.sum(ChunkEmbedding.chunk_id), 0)).where(
                ChunkEmbedding.model == model
            )
        ).one()
        return int(count), int(id_sum)

    def _load(self, db: Session, model: str) -> _Matrix:
        signature = self._signature(db, model)
        cached = self._cache.get(model)
        if cached is not None and cached.signature == signature:
            return cached
        rows = db.execute(
            select(ChunkEmbedding.chunk_id, Chunk.document_id, ChunkEmbedding.vector)
            .join(Chunk, Chunk.id == ChunkEmbedding.chunk_id)
            .where(ChunkEmbedding.model == model)
        ).all()
        if rows:
            vectors = np.vstack([from_blob(r[2]) for r in rows]).astype(np.float32)
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            vectors /= np.where(norms == 0, 1, norms)
        else:
            vectors = np.zeros((0, 0), dtype=np.float32)
        matrix = _Matrix(
            signature=signature,
            chunk_ids=np.array([r[0] for r in rows], dtype=np.int64),
            document_ids=np.array([r[1] for r in rows], dtype=np.int64),
            vectors=vectors,
        )
        self._cache[model] = matrix
        return matrix

    def size(self, db: Session, model: str) -> int:
        return self._signature(db, model)[0]

    def search(
        self,
        db: Session,
        model: str,
        query: list[float],
        k: int,
        document_ids: set[int] | None = None,
        min_similarity: float = 0.0,
    ) -> list[tuple[int, float]]:
        """Return up to ``k`` (chunk_id, cosine similarity) pairs, best first."""
        with self._lock:
            matrix = self._load(db, model)
        if matrix.vectors.shape[0] == 0:
            return []
        q = np.asarray(query, dtype=np.float32)
        if q.shape[0] != matrix.vectors.shape[1]:
            return []  # embedding model changed dimension; needs re-indexing
        q /= np.linalg.norm(q) or 1.0
        scores = matrix.vectors @ q
        if document_ids is not None:
            mask = np.isin(matrix.document_ids, np.fromiter(document_ids, dtype=np.int64))
            scores = np.where(mask, scores, -np.inf)
        k = min(k, scores.shape[0])
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return [
            (int(matrix.chunk_ids[i]), float(scores[i]))
            for i in top
            if np.isfinite(scores[i]) and scores[i] >= min_similarity
        ]
