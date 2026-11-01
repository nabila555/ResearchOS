# Development status

_Last updated: 2026-11-02 · version 0.3.0_

| Phase | Status |
|---|---|
| 1. Foundation | ✅ complete (0.1.0) |
| 2. Research Library | ✅ complete (0.2.0) |
| 3. AI Assistant | ✅ complete (0.3.0) |
| 4. Research Intelligence | ⏳ next |
| 5–6 | planned (see [docs/ROADMAP.md](docs/ROADMAP.md)) |

## Phase 3: AI Assistant ✅

### Done

**Providers** (`backend/app/ai/`)
- Provider protocol for chat (streaming) and embeddings; `AIServices` registry built from settings.
- **Ollama** (default, local): streaming `/api/chat` (low temperature, configurable context and
  timeout), `/api/embed` with `nomic-embed-text` task prefixes. Clear errors for "not running"
  and "model not installed" (with the `ollama pull` command).
- **Claude API** (optional): official `anthropic` SDK, `claude-opus-5-5`, streaming, effort
  `medium`, **server-side refusal fallback** (`fallbacks: "default"`); refusals are reported, not
  shown as answers. Available only when `ANTHROPIC_API_KEY` is set **and** the user ticks the
  consent box in Settings. Embeddings always stay local.

**Indexing**
- Migration `0003`: `chunk_embeddings` (float32 vectors per chunk and model), `index_jobs`,
  `chat_sessions`, `chat_messages`, `app_settings`, and `documents.ai_index_status/error`.
- A background worker thread embeds new and edited documents. Jobs live in the database,
  survive restarts, and wait (rather than fail) while Ollama or the model is unavailable. Up to 3
  attempts are made for real errors. Documents imported before 0.3 are queued automatically.
- Re-index from Settings ("Index missing & failed") or per document ("Retry").

**Retrieval** (`services/retrieval_service.py`)
- Hybrid search: in-memory NumPy cosine similarity over SQLite-stored vectors (reloads
  automatically on change) plus FTS5 BM25 with stop words removed, merged by Reciprocal Rank
  Fusion. Max 3 passages per document, character budget, minimum similarity (0.45) so unrelated
  questions retrieve nothing.
- Scope: whole library, collection, project, or specific documents.
- Falls back to keyword-only search, and says so, when embeddings are unavailable.

**Answering with verified citations** (`services/assistant_service.py`)
- Strict prompt: sources only, cite `[n]` after every claim, a fixed sentence when evidence is
  insufficient, flag disagreements, label interpretation.
- **No passages → no model call**: the reply states that the sources don't cover the question.
- After generation, citations are parsed and checked against the passages actually sent.
  Unknown numbers are flagged as invalid; an answer with no valid citation is marked
  **Unverified**.
- Statuses: cites sources / insufficient evidence / unverified / declined / error. Chat history
  (last 6 messages, old citation markers stripped) supports follow-up questions.
- Streaming NDJSON API: `user_message → sources → delta… → done | error`.

**API**: `GET /api/assistant/status`, `PUT /api/assistant/settings`, `POST /api/assistant/reindex`,
`POST /api/assistant/retrieve`, chat CRUD under `/api/assistant/sessions`, and
`POST /api/assistant/sessions/{id}/messages` (streaming).

**Frontend**
- Assistant page: chat list (picker on small screens), streaming answers rendered as safe
  Markdown (no raw HTML or images), citation chips (red and struck through when unverifiable),
  per-answer source list with full passages and **links that open the document at the cited
  page**, status badges, notes, scope picker, stop button, readiness notices (Ollama down,
  model missing, indexing progress, cloud in use), and example questions.
- Settings: provider choice, explicit cloud consent, index progress and re-index.
- Library: "AI search" index status per document with Retry; `?page=N` deep links.

**Tests**
- Backend: **102 pytest tests** (27 new), using deterministic fake providers: indexing, waiting
  for the provider without failing, re-queue on edit, embeddings removed on delete, hybrid and
  scoped retrieval, keyword fallback, vector cache reload, citation parsing and verification,
  no model call without evidence, uncited answers flagged, mid-stream errors, history, consent
  enforcement, Ollama NDJSON / missing model / offline, Claude request shape and refusal handling.
- Frontend: **28 Vitest tests** (citation linking, chips, Markdown safety, NDJSON stream parsing,
  consent error); `tsc`, ESLint, and `next build` pass.
- **Real end-to-end check with Ollama** (`llama3.1:8b`, `nomic-embed-text`, CPU-only Ryzen 7 4800HS):
  - Relevant passages scored 0.78–0.84 similarity; an unrelated question retrieved nothing.
  - A factual question was answered correctly with valid citations (about 40 s).
  - A question whose answer wasn't in the paper (participants' age) got "not enough evidence" (24 s).
  - An off-topic question was declined in under 0.1 s without calling the model.
  - In the browser: streaming, citation chips, the source panel, deep links, settings, and the mobile layout.
  - Test data was removed afterwards.

### Known limitations
- CPU-only generation is slow: about 25–35 s before the first token with 8B models. A smaller
  model (`OLLAMA_CHAT_MODEL=llama3.2:3b`) is faster but follows citation rules less reliably.
- Citation checks confirm that a cited passage was provided, not that it fully supports the
  sentence. Claim-level entailment checking is a candidate for Phase 4.
- Text extraction still runs synchronously during upload; only embedding is in the background.
- The Claude path was tested with a mocked SDK client, not live (no API key on this machine).
- Changing `OLLAMA_EMBED_MODEL` requires re-indexing (Settings → "Index missing & failed" after
  marking documents, or re-import). Old vectors are ignored, not mixed.

## Phase 2: Research Library ✅
Upload (PDF/DOCX/MD/TXT) with validation, URL import with SSRF protection, notes; extraction,
metadata heuristics with source tracking, page-aware chunking; FTS5 search; collections, tags,
filters, facets; library, document page, and Ctrl+K quick search. See git history for details.

## Phase 1: Foundation ✅
FastAPI + SQLite backend, Next.js shell, theme, dashboard, projects, settings.

## Phase 4: Research Intelligence ⏳ next
- [ ] Per-paper structured extraction (objectives, questions, methods, datasets, sample sizes,
      findings, limitations, frameworks), each field linked to supporting passages, cached
- [ ] Paper comparison table ("not reported" instead of guesses)
- [ ] Research Gap Finder (literature-supported vs. AI hypotheses clearly separated)
- [ ] Research Paper Detective (analytical observations, not accusations)
- [ ] Background job runner reused for long analyses, with progress

## Phase 5: Knowledge Management
- [ ] Knowledge graph (React Flow) · Literature review workspace · Citation manager (APA/MLA/Chicago/IEEE, BibTeX)

## Phase 6: Export & Polish
- [ ] Reports + Markdown export · PDF export · Performance · E2E tests · Docs
