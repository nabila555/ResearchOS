# Development status

_Last updated: 2026-11-02 · version 1.0.0_

| Phase | Status |
|---|---|
| 1. Foundation | ✅ complete (0.1.0) |
| 2. Research Library | ✅ complete (0.2.0) |
| 3. AI Assistant | ✅ complete (0.3.0) |
| 4. Research Intelligence | ✅ complete (0.4.0) |
| 5. Knowledge Management | ✅ complete (0.5.0) |
| 6. Export & Polish | ✅ complete (1.0.0) |

## Phase 6: Export & Polish ✅

### Done

**Reports**
- New report types, generated in the background like other analyses:
  - **Research summary** (1–10 papers) and **Methodology analysis** (2–15 papers): assembled from
    verified profiles with **no additional model call**. The methodology report adds author
    limitations, a reproducibility table from Paper Detective runs and a reference list.
  - **Research proposal** (2–12 papers, optionally built on a finished gap analysis, with a topic):
    model-drafted (constrained JSON). Background and problem sentences must cite real papers and
    are flagged otherwise. Questions, objectives, methods, contributions and risks are labelled
    as proposals. Formatted in-text citations and references in the chosen style.
  - **Literature review → Save as report** (snapshot of the export).
- **Reports page** (new sidebar item between Research Projects and Settings): filter by type, a
  safe Markdown viewer with tables, Markdown/PDF download, print, delete, and a *New report*
  panel with progress. Dashboard "Recent reports" links there; analysis results also offer PDF.
- **PDF export** works fully offline: Markdown → HTML (raw HTML disabled) → PyMuPDF Story layout
  with a print stylesheet, footer title, page numbers and PDF metadata. About 50 ms per report.
- A shared `replace_paper_labels` helper turns model-written "P1" / "(P1, P2)" labels into proper
  narrative or parenthetical citations (found in the real proposal output).

**Performance** (`backend/scripts/benchmark.py`, synthetic 500 papers / 10,000 chunks):
- Full-text search went from **226 ms to 63 ms** by generating highlighted snippets only for the
  results page (previously for up to 4,000 matching passages).
- The knowledge graph went from **35,869 to 4,690 edges** by keeping each paper's 3 strongest
  shared-reference links (a widely cited classic connected every pair). Browser layout uses
  fewer iterations above 300 nodes (1.07 s → 0.56 s at 639 nodes).
- Every other endpoint is under about 110 ms (see the README table).

**Usability**
- `start.ps1` / `start.sh`: first-run setup (venv, pip, npm), Ollama check, port-conflict check,
  dev or `-Production` mode, and clean shutdown of both servers (child processes included).
- Both servers now bind to `127.0.0.1` only (the production run showed Next.js listening on the
  LAN by default).
- `docs/USER_GUIDE.md`: end-to-end workflow, how to read verification labels, privacy, backup.

**Tests**: backend **145** (10 new: PDF rendering and HTML safety, summary without extra model
calls, methodology with and without Detective data, proposal verification and gap reuse, report
endpoints and filters, save-review, limits, graph edge cap, snippet paging, label replacement).
Frontend **38** (report rendering with tables and line breaks, HTML/image safety). `next build`
passes.

**Verified for real**:
- The start script in production mode (startup, both servers answering, and shutdown when one
  stops); the port guard.
- `llama3.1:8b` proposal from a gap analysis in 140 s; the summary and methodology reports were
  instant because profiles were cached.
- The methodology PDF was inspected visually.
- Reports page: list, viewer, tables with line breaks, download links.

### Known limitations
- **Proposals inherit the verification limit:** in testing the model attributed "learning style"
  (an idea from a gap hypothesis) to a paper that never mentions it. The citation was structurally
  valid, so it wasn't flagged. Treat proposals as drafts to check, which the report header says.
- **PDF layout is simplified** compared with the screen (PyMuPDF's HTML engine). Very wide tables
  wrap tightly.
- **Uploads are processed while you wait;** only embedding and analyses run in the background.
  Typical papers take 1–2 s; very large scanned PDFs take longer.
- **No browser end-to-end test suite** (for example Playwright) is included; UI flows were verified
  manually in the in-app browser each phase.
- **Licence:** AGPL-3.0 (see `LICENSE`), compatible with PyMuPDF.

## Phase 5: Knowledge Management ✅

### Done

**Citation Manager** (`backend/app/citations.py`, deterministic, no AI)
- APA 7, MLA 9, Chicago author-date (17th) and IEEE for journal articles, web pages and other
  documents. Name parsing handles "Family, Given", particles (van der, de…) and hyphenated
  initials (J.-P.); APA's 20-author rule, MLA/Chicago/IEEE et al. rules; italics carried as
  structured parts (copy pastes as rich text into Word or Docs).
- Missing elements are **left out and reported** (authors, year, volume, pages, DOI/URL); APA
  "n.d." where the style defines it. Titles are used as stored (no automatic re-casing).
- New editable citation fields on documents: volume, issue, pages, publisher (migration `0005`).
- In-text (parenthetical and narrative) citations; alphabetical bibliographies, or numbered in
  citation order for IEEE.
- Export: BibTeX (escaped, unique keys, `--` page ranges, `@online` with `urldate`), RIS, Markdown
  and plain text. The page offers copy-one, copy-bibliography, filter and per-collection scope.

**Knowledge Graph** (React Flow + d3-force layout)
- Nodes: papers, authors, topics (tags), concepts (keywords shared by ≥2 papers), collections.
  Edges come only from real data: authorship, tags, keywords, collections, **semantic similarity**
  (mean chunk embeddings, adjustable threshold) and **shared references**.
- Per-paper expansion adds method, research-question and finding nodes from *verified* profile
  statements only, each linking to its page and quote.
- Layer toggles, collection scope, highlight search, neighbourhood focus, a side panel listing
  connections with edge reasons, minimap, and light/dark mode.

**Literature Review workspace**
- Reviews (title, research question, introduction, citation style) → themes (name, description,
  order) → sources (order, per-source note).
- **Suggest themes**: groups papers by embedding similarity (no text generation), names groups
  from shared keywords/tags, and reports unindexed papers.
- **AI theme synthesis** (background job over verified profile statements): every sentence must
  cite papers *in that theme*. Sentences without valid support are flagged; agreements and
  disagreements need ≥2 papers. Re-running after changing a theme's papers shows "stale".
- **Export to Markdown**: introduction, themes with cited synthesis (narrative citations
  replace any "P1" labels the model wrote; no duplicate parenthetical), supported agreements and
  disagreements, sources per theme with notes, and a formatted reference list in the chosen style.
- An outline view links to each section.

**Tests**: backend **135** (23 new: every style for a journal article, missing data, web,
report, in-text and narrative citations, bibliography order, BibTeX escaping and keys, RIS,
graph layers, keyword normalisation, similarity edges, scope, verified-only detail nodes, review
CRUD, reordering, duplicates, empty-theme guard, synthesis verification, stale detection, export
with citations in APA and IEEE, label replacement, theme suggestions). Frontend **36** (citation
rendering, rich-text copy with HTML escaping and plain-text fallback, graph layout). `next build`
passes.

**Real end-to-end check** (`llama3.1:8b`):
- **Theme synthesis** of 2 papers took 95 s (profiles were cached). All 4 synthesis sentences were
  correctly attributed. The model's 4 one-paper "agreements/disagreements" were correctly flagged
  and left out of the export.
- **Review export** produced readable prose with proper APA in-text citations and a reference list.
- **Browser:** the citation page (italics, style switching, missing-field hints, export links), the
  graph (edges, similarity link, side panel, expansion to 5 verified detail nodes), and the review
  page (outline, synthesis, flagged claims).

Bugs found and fixed during this phase:
- Stale review state was returned after editing themes.
- IEEE dropped the DOI for papers without a venue.
- "P1/P2" labels leaked into exported prose.
- Double citations appeared in sentences that already named a paper.
- Wide detail nodes overlapped in the graph.

### Known limitations
- Citation formatting covers the common cases (journal article, web page, report-like document);
  books, chapters, conference papers and theses are formatted as generic documents. Title casing
  is not converted.
- A paper whose journal is unknown is cited as a generic document. Add the journal under
  *Edit details* to get the article format.
- Graph layout is computed in the browser; very large libraries (>300 papers) are capped.
- Shared-reference edges need identical reference strings (after normalisation); differently
  formatted references to the same work are not matched.
- Synthesis verification checks which papers a sentence cites, not whether the sentence is a
  faithful summary of them.
- The two fictional test papers now also have a review (“Sleep, screens and memory in
  students”) and journal details on one of them; delete them when you no longer need them.

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

## Beyond 1.0 (ideas, not commitments)
- OCR for scanned PDFs (Tesseract, free) and background extraction for very large files.
- Claim-level verification (an NLI model checks that a cited passage *entails* the statement).
- Books, chapters, conference papers and theses as citation types; DOI lookup via Crossref (opt-in).
- Browser end-to-end tests (Playwright) and packaged installers.
- Optional PostgreSQL + pgvector backend for very large shared libraries.
