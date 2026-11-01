# Development status

_Last updated: 2026-11-02 · version 0.2.0_

| Phase | Status |
|---|---|
| 1. Foundation | ✅ complete (0.1.0) |
| 2. Research Library | ✅ complete (0.2.0) |
| 3. AI Assistant | ⏳ next |
| 4–6 | planned (see [docs/ROADMAP.md](docs/ROADMAP.md)) |

## Phase 2: Research Library ✅

### Done

**Database & migrations**
- Alembic set up (`backend/migrations`). The API applies migrations on startup.
  Existing Phase 1 databases (created without migration history) are stamped at
  `0001` and upgraded in place, with data kept.
- `0002`: author lookup index; SQLite **FTS5** full-text indexes: `chunks_fts`
  (passage text, kept in sync by triggers) and `documents_fts` (title, authors,
  abstract, keywords; maintained by the search service), with porter stemming.

**Document processing** (`backend/app/document_processing/`)
- Validation: extension allow-list (`.pdf .docx .txt .md .markdown`), content
  sniffing (PDF magic bytes, DOCX zip structure, zip-bomb guard, binary text
  rejection), size limit (`MAX_UPLOAD_MB`, enforced while streaming), filename sanitising.
- Storage: content-addressed `data/documents/<sha[:2]>/<sha>.<ext>`. Uploaded
  names never become paths, resolved paths are confined to the store, and empty
  folders are pruned on delete.
- Extraction: PDF (PyMuPDF, per page, encrypted and damaged files rejected with
  clear messages, warning shown for scanned PDFs with no text layer), DOCX
  (paragraphs, headings, tables), Markdown (YAML front matter), plain text
  (UTF-8 with cp1252 fallback), HTML (Highwire `citation_*` meta tags, boilerplate removed).
- Metadata: title (PDF metadata, then largest text on page 1, then filename),
  authors (metadata or a strict name-line heuristic), year (published/accepted/©/arXiv
  patterns only), DOI, abstract, keywords, references. Each field records its
  source; heuristic values are flagged in the UI for checking, and nothing is guessed.
- Chunking: ~1,000-character passages with 150-character overlap, split on
  paragraph and sentence boundaries, keeping `page_start`/`page_end` and the section heading.
- URL import: http/https only, SSRF protection (blocks private, loopback,
  link-local and metadata IPs on every redirect), size cap, content-type allow-list,
  PDFs-by-URL go through the PDF pipeline.

**API**
- `POST /api/documents/upload` (multipart + optional JSON options: collections, projects, tags)
- `POST /api/documents/url`, `POST /api/documents/notes`
- `GET /api/documents` with `q` (FTS, BM25 ranking, snippets + matched page), `doc_type`
  (multi), `tag`, `collection_id`, `project_id`, `author`, `year_from`, `year_to`,
  `sort` (relevance/added/title/year), pagination
- `GET/PATCH/DELETE /api/documents/{id}`; `PUT …/tags`, `…/collections`, `…/projects`;
  `GET …/chunks?page=`; `GET …/file` (inline, `nosniff`)
- `GET/POST/PATCH/DELETE /api/collections`, `GET /api/tags`, `DELETE /api/tags/{id}`,
  `GET /api/library/facets`
- Duplicate files and URLs return `409` with `existing_document_id`; errors map to
  400/404/409/413/415/422 with readable messages.

**Frontend**
- Library page: filters kept in the URL (collections, type, year range, author,
  tags), debounced full-text search with highlighted snippets and page numbers,
  sorting, pagination, active-filter chips, collection create/rename/delete.
- Import dialog: drag-and-drop or browse, multi-file queue with upload progress,
  per-file success/duplicate/error states, URL import, notes, optional
  collection/project/tags. You can also drop files anywhere on the Library page.
- Document page: metadata with "detected automatically, please check" notice, edit
  details, tags, collections and project checklists, abstract, keywords, extracted
  text by page/section with page jump, references, open original file, remove.
  Notes are editable in place and re-indexed on save.
- Global quick search (**Ctrl/⌘ K**) from anywhere.
- Dashboard: recent documents link to the library; import quick actions.

**Tests**
- Backend: **75 pytest tests**, covering heuristics, extraction on generated PDF/DOCX/
  Markdown/HTML, chunking, validation, path safety, SSRF/redirect blocking, upload
  limits, duplicates, search (stemming, prefix, hostile FTS input), filters,
  facets, collections, tags, notes, deletion, URL import via a mock transport,
  and the Phase 1 → 2 database upgrade. Ruff clean.
- Frontend: **22 Vitest tests**; `tsc`, ESLint, and `next build` pass.
- Manual browser check: drag-and-drop import of a PDF and a DOCX, duplicate
  detection, search with highlights, document page, tagging, metadata edit, file
  download, URL safety error, notes, quick search, collections, project linking,
  dashboard. Test data was removed afterwards.

### Known limitations
- Import is synchronous: a very large PDF keeps the request open while it is
  processed (typical papers take under 1–2 s). This moves to a background job queue
  in Phase 3, alongside embeddings.
- Scanned PDFs need OCR (not supported yet; the app warns).
- Author and title heuristics are tuned for typical article layouts. Unusual
  layouts may give empty fields, which you can edit.
- Two-column PDFs follow PyMuPDF's content-stream order, which is usually correct
  but not always.
- Full-text search requires SQLite. PostgreSQL falls back to simple `LIKE` matching.
- Your local database still contains the test project “Sleep and memory
  consolidation” and the activity entries from manual testing.

## Phase 1: Foundation ✅
FastAPI + SQLite backend, core schema, health/system status, dashboard and
projects APIs; Next.js shell with sidebar, light/dark theme, dashboard, projects,
settings; honest placeholders for unbuilt sections.

## Phase 3: AI Assistant ⏳ next
- [ ] Background job queue for import and embedding (status: pending → processing → ready/failed)
- [ ] Provider abstraction (Ollama generate/stream/embed; optional Claude with explicit consent)
- [ ] Chunk embeddings + NumPy vector index; hybrid retrieval with FTS5
- [ ] Chat with streaming, page citations, citation verification, insufficient-evidence handling
- [ ] Chat history

## Phase 4: Research Intelligence
- [ ] Per-paper structured extraction (cached) · Paper comparison · Gap finder · Paper detective

## Phase 5: Knowledge Management
- [ ] Knowledge graph (React Flow) · Literature review workspace · Citation manager (APA/MLA/Chicago/IEEE, BibTeX)

## Phase 6: Export & Polish
- [ ] Reports + Markdown export · PDF export · Performance · E2E tests · Docs
