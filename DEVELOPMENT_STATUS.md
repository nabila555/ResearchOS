# Development status

_Last updated: 2026-11-02 · version 0.4.0_

| Phase | Status |
|---|---|
| 1. Foundation | ✅ complete (0.1.0) |
| 2. Research Library | ✅ complete (0.2.0) |
| 3. AI Assistant | ✅ complete (0.3.0) |
| 4. Research Intelligence | ✅ complete (0.4.0) |
| 5. Knowledge Management | ⏳ next |
| 6 | planned (see [docs/ROADMAP.md](docs/ROADMAP.md)) |

## Phase 4: Research Intelligence ✅

### Done

**Evidence-linked paper profiles** (`backend/app/research_analysis/profile.py`)
- 10 fields per paper: objective, research questions, theoretical framework, methodology,
  data/materials, sample size, population/setting, key findings, limitations, future research.
- Three focused passes (overview, methods, results), each with its own excerpts chosen by
  section and keywords within `ANALYSIS_EXCERPT_CHARS` (default 7,000, fits an 8k context).
  The references section is never sent.
- **Constrained JSON**: Ollama's `format` (JSON schema → grammar); Claude structured outputs
  (`output_config.format`), with refusal fallback.
- **Verification in code** (`evidence.py`): every statement must cite a provided excerpt, include
  a verbatim quote found in that excerpt (near-verbatim allowed), and every number in the
  statement must appear in the excerpt. Field status: verified / partly verified / unverified /
  not reported. Unverified statements are shown faded with the reason.
- Profiles are cached per document, flagged **stale** when the text changes (content hash), and
  reused by comparisons and gap analyses.

**Paper Comparison**: 2–6 papers. Profiles are built as needed, then a side-by-side table with page
links on every cell and "Not reported" instead of guesses. No extra model call for the table.

**Research Gap Finder**: 2–12 papers or a whole collection, optional focus. One model call over
compact digests made only from *verified* profile statements, in six categories: underexplored
areas, contradictions, missing perspectives, methodological limitations, future directions, and
research questions. **Labels are enforced**:
- An item marked "literature" must name existing papers.
- A contradiction needs two papers.
- Proposed research questions are always hypotheses.
- Unknown paper references are reported.

The UI filters literature-supported items from AI hypotheses.

**Research Paper Detective**: per paper, up to 8 observations (unsupported claims, weak arguments,
methodological limitations, potential bias, missing information, reproducibility) with severity.
Quoted observations are verified; "absence" observations are labelled as based only on the
analysed excerpts. There is also a 6-item reproducibility checklist (a claimed item whose quote
can't be verified is shown as such). The wording is cautious by design.

**Jobs & reports**
- `analyses` table and a background worker: queued → running (progress messages) → done, failed
  or cancelled. Identical queued work is de-duplicated; you can retry or run again; interrupted
  runs restart.
- Finished comparisons, gap analyses and detective runs are saved as **Markdown reports**
  (`/api/reports`, download button), and appear on the dashboard.
- The cloud-consent rule from Phase 3 applies to every analysis.

**Frontend**: Paper Comparison page (document picker, run history, comparison table), Research
Gap Finder page (collection or papers, focus, literature/hypothesis filter), and Paper profile and
Detective cards on each document page. Progress cards show cancel, retry and the report
download.

**Tests**: backend **112** (10 new, using scripted fake output containing a wrong number, a
nonexistent excerpt, a fabricated quote, mislabelled literature, a one-paper contradiction, an
unknown paper, cancellation, de-duplication, failure, consent, report download). Frontend
**32** (evidence chips, field rendering). `next build` passes.

**Real end-to-end check** (`llama3.1:8b`, CPU-only):

| Analysis | Time | Result |
|---|---|---|
| Profile of a 2-page study | 3 min 11 s | All 10 fields correct, every statement verified |
| Paper Detective | 2 min 21 s | 8 sensible observations, quotes verified, absences labelled |
| Comparison of 2 papers (one profile cached) | 2 min 39 s | Accurate table |
| Gap analysis of 2 papers | ~2 min | Labels enforced; see the limitations below |

Browser check: comparison table with page links and report download, gap results with the
literature/hypothesis filter, and the profile and Detective cards on the document page (which
found and fixed a bug where Detective results were not loaded).

### Known limitations (honest)
- **Verification is structural, not semantic.** It proves a quote and its numbers come from the
  paper, not that the statement is in the right field or interprets the quote correctly. Seen in
  testing: "48 participants" filed under *Data / materials*; a "contradiction" between findings on
  different topics (the prompt has since been tightened). Claim-level entailment checking would
  need a stronger model or an NLI model.
- 8B models make judgement errors in the Detective, for example marking statistical methods
  "not found" although a regression was described. The UI presents output as prompts for your
  own reading.
- Speed: about 1 minute per model step on a CPU, so profiling 10 new papers takes about 30 minutes
  (it runs in the background and is cached).
- Long papers: only the most relevant ~7,000 characters per pass are read. "Not reported" can mean
  "not in the excerpts read".
- Your local library still contains the two fictional test papers (“Screen Time Before Bed…”,
  “Sleep Spindles Predict…”) with their profiles, analyses and reports. Remove them from the
  Library when you no longer need them.

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
  sentence. Claim-level entailment checking is still open (Phase 4 added quote and number checks
  for analyses).
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

## Phase 5: Knowledge Management ⏳ next
- [ ] Knowledge graph (React Flow) · Literature review workspace · Citation manager (APA/MLA/Chicago/IEEE, BibTeX)

## Phase 6: Export & Polish
- [ ] Reports + Markdown export · PDF export · Performance · E2E tests · Docs
