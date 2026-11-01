# ResearchOS architecture

ResearchOS is a **local-first research workspace**. Everything (documents, database,
embeddings, and AI inference) runs on the user's machine. Cloud AI is an optional,
explicitly enabled add-on and never a requirement.

## 1. System overview

```
┌────────────────────────── Browser ───────────────────────────┐
│  Next.js 16 (App Router) · TypeScript · Tailwind v4          │
│  shadcn-style components (Radix) · TanStack Query · Lucide   │
│  React Flow (graph, P5) · Recharts (stats, P6)               │
└───────────────────────────┬──────────────────────────────────┘
                            │ JSON over HTTP (localhost only)
┌───────────────────────────▼──────────────────────────────────┐
│  FastAPI backend (Python)                                    │
│  api/ ─► services/ ─► models/ (SQLAlchemy 2)                 │
│              │                                               │
│              ├─► document_processing/  PyMuPDF, python-docx, │
│              │                         BeautifulSoup, md     │
│              ├─► retrieval  (chunks + local vector index)    │
│              ├─► research_analysis/  compare, gaps, detective│
│              └─► ai/  provider abstraction                   │
│                     ├─ OllamaProvider   (default, local)     │
│                     └─ AnthropicProvider (optional, opt-in)  │
└──────┬──────────────────────┬────────────────────┬───────────┘
       │                      │                    │
  data/database/        data/documents/      data/embeddings/
  researchos.db         original files       vector matrices
  (SQLite, WAL)         (hash-named)         (reserved; vectors
                                             live in SQLite)
```

### Layering rules

| Layer | Responsibility | May depend on |
|---|---|---|
| `api/routes` | HTTP: parse/validate input, map errors to status codes | services, schemas |
| `schemas` | Pydantic request/response contracts | models (enums only) |
| `services` | Business logic and transactions | models, ai, processing |
| `models` | ORM tables | core.database |
| `ai` | Talk to LLM/embedding providers through one interface | core.config |
| `document_processing` | Bytes → text + metadata + page-aware chunks | nothing app-specific |
| `research_analysis` | Multi-step analyses built on retrieval + ai | services, ai |

The frontend mirrors this: `services/` (API calls) → `hooks/` (TanStack Query) →
`components/` (UI) → `app/` (routes). Types in `types/api.ts` mirror backend schemas.

## 2. Zero-cost verification

| Need | Choice | Cost | Offline |
|---|---|---|---|
| UI framework | Next.js, React, Tailwind, Radix, Lucide | MIT/free | ✔ (fonts bundled via `geist` package) |
| API | FastAPI, Uvicorn, Pydantic | MIT/BSD | ✔ |
| Database | SQLite (built into Python) | free | ✔ |
| Full-text search | SQLite FTS5 | free | ✔ |
| PDF / DOCX / HTML | PyMuPDF (AGPL), python-docx, BeautifulSoup | free | ✔ |
| LLM inference | Ollama + open-weight models (Llama 3.1, Qwen, Mistral…) | free | ✔ |
| Embeddings | Ollama `nomic-embed-text` (or `mxbai-embed-large`) | free | ✔ |
| Vector search | NumPy cosine similarity over a local matrix (see §5) | free | ✔ |
| Graph / charts | React Flow (MIT), Recharts (MIT) | free | ✔ |
| Tests | Pytest, Vitest, Testing Library | free | ✔ |
| Optional cloud AI | Claude API | paid, **opt-in only** | ✘ |

> **PyMuPDF licence note:** PyMuPDF is AGPL-3.0. That is fine for a personal or
> open-source (AGPL-compatible) project. If ResearchOS is ever distributed under a
> permissive licence or commercially, swap in `pypdf` (BSD) behind the same
> extractor interface.

## 3. Database schema (SQLite, SQLAlchemy 2)

Implemented now (Phase 1) so later phases don't need disruptive migrations:

```
documents ─────────────┬──< document_authors >── authors
  id, title, doc_type   ├──< document_tags >───── tags
  status, error_message ├──< collection_documents >── collections
  source_url, file_path ├──< project_documents >──── projects ──< reports
  original_filename     └──< chunks
  file_hash, file_size, mime_type          id, document_id, chunk_index,
  abstract, publication_year, venue, doi   page_start, page_end, section,
  keywords[], reference_list[], page_count text, char_count
  language, extra_metadata{}, note_body
  created_at, updated_at

projects   id, name, description, research_question, status(active|paused|completed|archived)
reports    id, title, report_type, content_markdown, project_id?, source_document_ids[], model_used
activities id, action, entity_type, entity_id, summary, created_at   (no document contents)
```

Implemented in Phase 2 (migration `0002`): `chunks_fts` (FTS5, external content
over `chunks.text`, kept in sync by triggers) and `documents_fts` (FTS5 over title,
authors, abstract, keywords; rowid = document id, written by `search_service`).
Both use the `porter unicode61 remove_diacritics 2` tokenizer. Search queries are
rebuilt from plain terms (each quoted, last one prefix-matched), so user input can
never inject FTS syntax.

Implemented in Phase 3 (migration `0003`): `chunk_embeddings` (chunk_id + model → float32
blob), `index_jobs` (durable embedding queue), `chat_sessions` (title, scope JSON),
`chat_messages` (content, provider/model, status, `sources` sent, `cited` / `invalid_citations`,
`grounded`, notes), `app_settings` (chat provider, cloud consent), and
`documents.ai_index_status` / `ai_index_error`.

Implemented in Phase 4 (migration `0004`): `paper_profiles` (document_id → evidence-linked
fields JSON, chunk content hash for staleness) and `analyses` (kind, status, progress, document
ids, params, result JSON, provider/model, linked report).

**Evidence verification (Phase 4).** Model output is generated with JSON-schema constrained
decoding and then checked in code. Each statement must reference a provided excerpt, include a
quote that appears in that excerpt (normalised; ≥85% word overlap for near-verbatim), and contain
no number absent from the excerpt. Failing statements are kept but flagged *unverified* with the
reason, never silently shown as fact. Gap-finder labels (literature vs. hypothesis) are enforced
after generation.

Planned tables (added with Alembic migrations in their phase):

| Phase | Table | Purpose |
|---|---|---|
| 5 | `concepts`, `document_concepts`, `relations` | Knowledge-graph nodes and typed edges with evidence chunk ids |
| 5 | `review_themes`, `review_items` | Literature-review workspace |
| 5 | `references` (CSL-JSON fields + `missing_fields[]`) | Citation manager; missing fields are flagged, never invented |

Migrations: Alembic, applied automatically at startup (`app/core/migrations.py`).
A database created by Phase 1's `create_all` is stamped at `0001` and upgraded.

Conventions: integer primary keys; UTC timezone-aware timestamps (a `UTCDateTime`
type decorator restores the UTC offset that SQLite drops); enums stored as strings;
JSON columns for list-like metadata; `ON DELETE CASCADE` for join tables;
`PRAGMA foreign_keys=ON` and WAL mode on every SQLite connection.

## 4. AI provider abstraction (Phase 3)

```python
class AIProvider(Protocol):
    name: str
    async def status(self) -> ProviderStatus
    async def generate(self, messages, *, temperature, max_tokens, json_schema=None) -> Generation
    def stream(self, messages, ...) -> AsyncIterator[str]
    async def embed(self, texts: list[str]) -> list[list[float]]
```

- `OllamaProvider` talks to `http://127.0.0.1:11434` (`/api/chat`, `/api/embed`).
- `AnthropicProvider` is only constructed when `ANTHROPIC_API_KEY` is set **and** the
  user enables it in Settings. The UI shows which provider produced every answer, and
  any request that would send document text to a cloud provider needs explicit consent.
- Embeddings always stay local (Ollama), even when Claude is used for generation.

## 5. RAG pipeline (Phase 2–3)

1. **Import**: validate extension + magic bytes + size, hash (SHA-256) for dedupe,
   store as `data/documents/<hash>.<ext>` (never a user-controlled path).
2. **Extract**: PyMuPDF per page (text + PDF metadata); DOCX paragraphs; Markdown/
   text as-is; URLs fetched once with `httpx` and cleaned with BeautifulSoup.
3. **Metadata**: title, authors, year, abstract, keywords, DOI, and the references
   section using heuristics on the first pages and PDF metadata. Fields that cannot
   be found stay empty and are shown as "not found", never guessed.
4. **Chunk**: ~800–1,200 characters with ~150 overlap, split on paragraph/sentence
   boundaries, never across pages without recording `page_start`/`page_end`.
5. **Embed** (background worker): batch through Ollama (`nomic-embed-text` with
   `search_document:` / `search_query:` prefixes); store float32 vectors in `chunk_embeddings`.
   The in-memory index reloads when the stored set changes (count + id checksum).
6. **Retrieve**: cosine similarity (NumPy, minimum 0.45) and FTS5 BM25 (stop words removed),
   merged with Reciprocal Rank Fusion; scope filter; max 3 passages per document; character budget.
   If nothing matches, the model is not called.
7. **Generate**: the prompt contains only numbered source passages; the model must
   cite `[n]` for each claim and answer "The provided sources do not contain enough
   evidence…" otherwise.
8. **Verify**: citations are parsed and checked against the passages actually sent;
   unknown `[n]` markers are stripped and flagged. The UI renders each citation as
   *document title, p. X* linked to the passage.

**Why not FAISS/ChromaDB?** Neither publishes wheels for Python 3.15 (installed on
this machine), and both are overkill for a personal library. Brute-force NumPy
cosine search over 100k chunks × 768 dims (~300 MB float32) takes well under 100 ms
on a laptop CPU. The vector index sits behind a `VectorIndex` interface so FAISS,
`sqlite-vec`, or pgvector can be dropped in later without touching callers.

## 6. Security & privacy

- Backend binds to `127.0.0.1`; CORS restricted to the frontend origin(s).
- Upload validation: extension allow-list (`.pdf .docx .txt .md`), magic-byte check,
  `MAX_UPLOAD_MB` limit, streamed to disk, filename never used as a path.
- All file access resolves inside `DATA_DIR`; path traversal is rejected.
- URL import blocks private/loopback addresses (SSRF) and limits response size.
- Secrets only via environment; `SecretStr` keeps them out of reprs, and `/api/system/status`
  only reports *whether* a key is configured (covered by a test).
- Logs record IDs and actions, never document text or prompts.

## 7. Hardware guidance

| Profile | RAM | What runs well |
|---|---|---|
| Minimum | 8 GB | Library, search, citations; 3–4B models (`llama3.2:3b`, `qwen2.5:3b`) for AI, slowly |
| Recommended | 16 GB | 7–8B models at Q4 (`llama3.1:8b`, `qwen2.5:7b`) on CPU, ~5–12 tokens/s |
| Comfortable | 32 GB and/or GPU with ≥8 GB VRAM | 8–14B models quickly; large libraries |

This development machine (Ryzen 7 4800HS, 16 GB RAM, integrated Radeon) sits in the
*Recommended* tier: expect 8B models to run on CPU at a usable but not fast speed.
Disk: ~5 GB per 8B model, plus about 2× the size of your document library.

## 8. Technical risks

| Risk | Impact | Mitigation |
|---|---|---|
| Local 7–8B models hallucinate or ignore citation instructions | Wrong claims | Strict prompts, citation verification against sent passages, "insufficient evidence" path, low temperature, show sources beside every answer |
| CPU-only inference is slow for long analyses (comparison, gap finding) | Poor UX | Map-reduce over per-paper extractions cached in `analyses`; streaming; background jobs with progress |
| PDF extraction quality (two columns, scanned PDFs, equations) | Bad chunks/metadata | PyMuPDF block sorting; detect empty text layers and flag "scanned PDF, OCR needed" (Tesseract as optional later add-on) |
| Metadata extraction is heuristic | Incomplete citations | Editable metadata; never fabricate; optional DOI lookup via Crossref (free, online, opt-in) |
| Brand-new Python 3.15 lacks some wheels (pyyaml, faiss, chromadb) | Install failures | Dependencies chosen to have 3.15 wheels; documented fallback to Python 3.12 |
| Schema evolution on SQLite | Data loss on upgrade | Alembic migrations (added in Phase 2) run on startup; Phase 1 databases are adopted in place |
| Context window limits of local models (often 8k) | Truncated context | Token budgeting in the retriever, summarise-then-synthesise for multi-paper tasks |
| AGPL licence of PyMuPDF | Licensing constraints if relicensed | Extractor interface allows switching to `pypdf` |
