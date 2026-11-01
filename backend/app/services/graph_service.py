"""Knowledge graph of the library, built only from data that exists.

Edges and their evidence:
* authored, tagged, keyword, in_collection: library metadata.
* similar: cosine similarity of the papers' mean chunk embeddings (local index).
* shared_references: identical reference-list entries (normalised).
Paper detail nodes (methods, findings, research questions) come from *verified*
statements of the paper's profile, so every node can be traced to a page.
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.vector_index import from_blob
from app.models.ai import ChunkEmbedding
from app.models.analysis import PaperProfile
from app.models.library import Chunk, Document, DocumentAuthor, DocumentType
from app.services.errors import NotFoundError
from app.services.retrieval_service import Scope

MAX_PAPERS = 300
SIMILAR_PER_PAPER = 3
DETAIL_FIELDS = {
    "methodology": ("method", "uses method"),
    "research_questions": ("question", "asks"),
    "key_findings": ("finding", "reports"),
}


@dataclass
class Graph:
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: dict[str, dict[str, Any]] = field(default_factory=dict)

    def node(self, node_id: str, kind: str, label: str, **data: Any) -> None:
        if node_id not in self.nodes:
            self.nodes[node_id] = {"id": node_id, "type": kind, "label": label, "data": data}

    def edge(
        self, source: str, target: str, kind: str, weight: float = 1.0, label: str | None = None
    ) -> None:
        a, b = (
            sorted((source, target))
            if kind in ("similar", "shared_references")
            else (source, target)
        )
        edge_id = f"{kind}:{a}:{b}"
        if edge_id not in self.edges:
            self.edges[edge_id] = {
                "id": edge_id,
                "source": a,
                "target": b,
                "type": kind,
                "weight": round(weight, 3),
                "label": label,
            }

    def as_dict(self) -> dict[str, Any]:
        degree: Counter[str] = Counter()
        for e in self.edges.values():
            degree[e["source"]] += 1
            degree[e["target"]] += 1
        for node in self.nodes.values():
            node["data"]["degree"] = degree[node["id"]]
        return {
            "nodes": list(self.nodes.values()),
            "edges": list(self.edges.values()),
            "stats": dict(Counter(n["type"] for n in self.nodes.values())),
        }


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _paper_vectors(db: Session, model: str, ids: list[int]) -> dict[int, np.ndarray]:
    rows = db.execute(
        select(Chunk.document_id, ChunkEmbedding.vector)
        .join(ChunkEmbedding, ChunkEmbedding.chunk_id == Chunk.id)
        .where(ChunkEmbedding.model == model, Chunk.document_id.in_(ids))
    ).all()
    grouped: dict[int, list[np.ndarray]] = defaultdict(list)
    for doc_id, blob in rows:
        grouped[doc_id].append(from_blob(blob))
    vectors = {}
    for doc_id, vecs in grouped.items():
        mean = np.mean(np.vstack(vecs), axis=0)
        norm = np.linalg.norm(mean)
        if norm:
            vectors[doc_id] = mean / norm
    return vectors


def build_graph(
    db: Session,
    *,
    scope: Scope,
    embed_model: str,
    include: set[str],
    similarity_threshold: float = 0.75,
    min_keyword_papers: int = 2,
) -> dict[str, Any]:
    stmt = (
        select(Document)
        .where(Document.doc_type != DocumentType.NOTE)
        .options(
            selectinload(Document.authors).selectinload(DocumentAuthor.author),
            selectinload(Document.tags),
            selectinload(Document.collections),
        )
        .order_by(Document.created_at.desc())
        .limit(MAX_PAPERS)
    )
    allowed = scope.document_filter(db)
    if allowed is not None:
        stmt = stmt.where(Document.id.in_(allowed))
    docs = list(db.scalars(stmt))
    graph = Graph()

    for doc in docs:
        graph.node(
            f"paper:{doc.id}",
            "paper",
            doc.title,
            document_id=doc.id,
            year=doc.publication_year,
            doc_type=doc.doc_type.value,
        )

        if "author" in include:
            for link in doc.authors:
                graph.node(f"author:{link.author.id}", "author", link.author.full_name)
                graph.edge(f"author:{link.author.id}", f"paper:{doc.id}", "authored")
        if "topic" in include:
            for tag in doc.tags:
                graph.node(f"topic:{tag.id}", "topic", tag.name)
                graph.edge(f"paper:{doc.id}", f"topic:{tag.id}", "tagged")
        if "collection" in include:
            for collection in doc.collections:
                graph.node(f"collection:{collection.id}", "collection", collection.name)
                graph.edge(f"paper:{doc.id}", f"collection:{collection.id}", "in_collection")

    if "keyword" in include:
        papers_by_keyword: dict[str, set[int]] = defaultdict(set)
        label: dict[str, str] = {}
        for doc in docs:
            for keyword in doc.keywords or []:
                key = _normalise(keyword)
                if key:
                    papers_by_keyword[key].add(doc.id)
                    label.setdefault(key, keyword.strip())
        for key, papers in papers_by_keyword.items():
            if len(papers) >= min_keyword_papers:
                graph.node(f"keyword:{key}", "keyword", label[key], papers=len(papers))
                for doc_id in papers:
                    graph.edge(f"paper:{doc_id}", f"keyword:{key}", "keyword")

    if "similar" in include and len(docs) > 1:
        vectors = _paper_vectors(db, embed_model, [d.id for d in docs])
        ids = list(vectors)
        if len(ids) > 1:
            matrix = np.vstack([vectors[i] for i in ids])
            sims = matrix @ matrix.T
            for row, doc_id in enumerate(ids):
                order = np.argsort(-sims[row])
                added = 0
                for col in order:
                    if col == row or sims[row, col] < similarity_threshold:
                        continue
                    graph.edge(
                        f"paper:{doc_id}",
                        f"paper:{ids[col]}",
                        "similar",
                        float(sims[row, col]),
                        f"{sims[row, col]:.2f} similar",
                    )
                    added += 1
                    if added >= SIMILAR_PER_PAPER:
                        break

    if "shared_references" in include:
        cited_by: dict[str, set[int]] = defaultdict(set)
        for doc in docs:
            for reference in doc.reference_list or []:
                key = _normalise(reference)[:80]
                if len(key) >= 20:
                    cited_by[key].add(doc.id)
        shared: Counter[tuple[int, int]] = Counter()
        for papers in cited_by.values():
            ordered = sorted(papers)
            for i, a in enumerate(ordered):
                for b in ordered[i + 1 :]:
                    shared[(a, b)] += 1
        for (a, b), count in shared.items():
            graph.edge(
                f"paper:{a}",
                f"paper:{b}",
                "shared_references",
                count,
                f"{count} shared reference{'s' if count != 1 else ''}",
            )

    return graph.as_dict()


def paper_details(db: Session, document_id: int) -> dict[str, Any]:
    """Method / question / finding nodes for one paper from its verified profile."""
    if db.get(Document, document_id) is None:
        raise NotFoundError(f"Document {document_id} not found")
    profile = db.get(PaperProfile, document_id)
    graph = Graph()
    if profile is None:
        return {**graph.as_dict(), "has_profile": False}
    paper = f"paper:{document_id}"
    for field_key, (kind, relation) in DETAIL_FIELDS.items():
        statements = profile.fields.get(field_key, {}).get("statements", [])
        for index, statement in enumerate(statements):
            evidence = statement["evidence"]
            if not evidence.get("verified"):
                continue  # only traceable statements become graph nodes
            node_id = f"{kind}:{document_id}:{index}"
            graph.node(
                node_id,
                kind,
                statement["text"],
                document_id=document_id,
                page=evidence.get("page_start"),
                quote=evidence.get("quote"),
            )
            graph.edge(paper, node_id, f"{kind}_of", label=relation)
    return {**graph.as_dict(), "has_profile": True}
