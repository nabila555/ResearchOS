# ResearchOS roadmap

Each phase ends with working, tested features and an updated `DEVELOPMENT_STATUS.md`.
Estimates assume one developer working part-time.

| Phase | Scope | Exit criteria | Estimate |
|---|---|---|---|
| **1. Foundation** ✅ | Monorepo, FastAPI + SQLite, full core schema, Next.js shell, sidebar, light/dark theme, dashboard, research projects CRUD, AI/system status, test setups | Both apps run locally, tests green, dashboard shows live DB data | done |
| **2. Research Library** ✅ | Alembic; upload PDF/DOCX/TXT/MD with validation; URL import; notes; extraction with page numbers; metadata extraction + manual editing; collections; tags; FTS5 search; filters (author, topic, year, type); document detail view; add documents to projects | Import a real PDF, see correct pages/metadata, find it by full-text search | done |
| **3. AI Assistant** ✅ | Background import/embedding jobs; provider abstraction (Ollama + optional Claude with consent); chunk embeddings; NumPy vector index; hybrid retrieval; streaming chat; page-level citations with verification; "insufficient evidence" handling; chat history | Answers cite document + page; questions outside the sources are declined | done |
| **4. Research Intelligence** ✅ | Per-paper structured extraction (objectives, methods, datasets, sample size, findings, limitations…) cached; comparison table; gap finder (evidence vs. hypotheses separated); paper detective | Comparison of 3 papers fills only cells with supporting passages | done |
| **5. Knowledge Management** ✅ | Concept/method/finding extraction → knowledge graph in React Flow; literature review workspace (themes, outlines, cited summaries); citation manager (APA 7, MLA, Chicago, IEEE; BibTeX export) | Export a cited literature review to Markdown | done |
| **6. Export & Polish** ✅ | Report generation and history; Markdown export; PDF export (browser print stylesheet first, then WeasyPrint if needed); performance (background jobs, pagination); E2E tests; docs | All reports exportable; performance budget met on a 500-paper library | done |

## Ordering rationale

- The library (Phase 2) produces the page-aware chunks every AI feature depends on.
- Retrieval with verified citations (Phase 3) is the trust foundation; Phase 4–5
  analyses reuse it rather than prompting models with whole papers.
- Per-paper structured extraction (Phase 4) is cached and then reused by comparison,
  gap finding, the knowledge graph, and literature reviews, which keeps CPU-only
  inference practical.

All six phases are complete (version 1.0.0). Ideas beyond 1.0 are listed at the end of
[DEVELOPMENT_STATUS.md](../DEVELOPMENT_STATUS.md).
