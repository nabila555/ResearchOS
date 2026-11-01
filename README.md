# ResearchOS

A local-first, open-source **research operating system**: collect, organise, analyse,
and connect research material with AI that runs on your own machine and cites its sources.

> **Status:** Phases 1–4 complete: foundation, research library, AI assistant, and research
> intelligence (paper profiles, comparison, gap finder, paper detective). See [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md)
> and the [roadmap](docs/ROADMAP.md). Sections not built yet are labelled with their
> phase in the sidebar and explain what's planned; they contain no non-functional controls.

- **Zero cost:** no paid APIs, subscriptions, or cloud services required.
- **Private by default:** documents, database, and embeddings live in `data/`.
- **Research library:** import PDFs, Word, Markdown, text, web articles and notes;
  automatic metadata (verify-before-trust), collections, tags, filters, and full-text
  search with page-level snippets. Press **Ctrl/⌘ K** to search from anywhere.
- **Research intelligence:** evidence-linked paper profiles, side-by-side comparison tables, a
  research gap finder that separates literature-supported findings from AI hypotheses, and a
  Paper Detective for critical reading. Every statement is checked against the quoted page.
- **Honest AI assistant:** answers only from your sources, cites document and page for every
  claim, checks each citation against the passages it was given, and says so when the evidence
  is insufficient. Runs locally on Ollama; the Claude API is optional and needs your consent.

## Stack

Next.js 16 · TypeScript · Tailwind v4 · Radix/shadcn-style UI · TanStack Query ·
FastAPI · SQLAlchemy 2 · SQLite · Ollama (local LLMs) · Pytest · Vitest.
Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Requirements

| Tool | Version | Install (Windows) |
|---|---|---|
| Python | 3.11+ (tested on 3.15) | python.org or `winget install Python.Python.3.12` |
| Node.js | 20.9+ (tested on 26) | `winget install OpenJS.NodeJS.LTS` |
| Ollama | optional until Phase 3 | `winget install Ollama.Ollama` or ollama.com/download |

## Quick start

### 1. Backend (terminal 1)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://127.0.0.1:8000/docs. The SQLite database and `data/` folders are
created automatically on first start, and database migrations are applied
automatically every time the backend starts.

### 2. Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

### 3. Local AI (needed for the assistant)

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

Install Ollama first (`winget install Ollama.Ollama` on Windows, or ollama.com/download).
Settings → **Re-check** confirms detection. Documents are embedded automatically in the
background; progress shows in Settings.

On 8 GB RAM machines use a smaller model (e.g. `ollama pull llama3.2:3b`, then set
`OLLAMA_CHAT_MODEL=llama3.2:3b` in `.env`). Expect 25–40 s per answer for 8B models on a CPU.

**Optional: the Claude API.** Set `ANTHROPIC_API_KEY` in `.env`, restart the backend, then in
Settings choose *Claude API* **and** tick the consent box. Only the question and the matched
passages are sent; embeddings stay local.

### Configuration

Copy `.env.example` to `.env` in the project root. All values are optional.
For a non-default backend URL, copy `frontend/.env.example` to `frontend/.env.local`.

## Tests and checks

```bash
cd backend
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check app tests
```

```bash
cd frontend
npm test
npm run typecheck
npm run lint
npm run build
```

## Database migrations

Schema changes use Alembic (`backend/migrations`). The API runs `alembic upgrade head`
on startup, so you normally don't run anything. When you change a model:

```bash
cd backend
.venv\Scripts\alembic revision --autogenerate -m "describe the change"
```

Review the generated file in `backend/migrations/versions/` before committing it.

## Project layout

```
researchos/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers (HTTP only)
│   │   ├── core/             # config, database engine/session
│   │   ├── models/           # SQLAlchemy tables
│   │   ├── schemas/          # Pydantic request/response models
│   │   ├── services/         # business logic
│   │   ├── ai/               # providers (Ollama, optional Claude), registry, vector index
│   │   ├── document_processing/  # validation, storage, extraction, metadata, chunking, URL fetch
│   │   └── research_analysis/    # comparison, gaps, detective (Phase 4)
│   ├── migrations/           # Alembic migrations
│   └── tests/                # pytest (sample PDFs/DOCX are generated, see tests/fixtures)
├── frontend/
│   ├── app/                  # routes (App Router)
│   ├── components/           # ui/, layout/, dashboard/, projects/, settings/
│   ├── hooks/                # TanStack Query hooks
│   ├── lib/                  # api client, utils
│   ├── services/             # typed API endpoint functions
│   ├── types/                # API types mirroring backend schemas
│   ├── migrations/           # Alembic migrations
│   └── tests/                # pytest (sample PDFs/DOCX are generated, see tests/fixtures)                # Vitest
├── data/                     # created at runtime, git-ignored
│   ├── documents/  embeddings/  database/
└── docs/                     # architecture, roadmap
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Dashboard shows **"Backend not reachable"** | Start the backend (step 1). Check that port 8000 is free: `netstat -ano \| findstr :8000`. |
| `pip install` fails building **pyyaml / faiss / chromadb** | You installed an extra the project doesn't use (e.g. `uvicorn[standard]`). Use `requirements.txt` as-is. Very new Pythons lack some wheels; Python 3.12 always works. |
| `Microsoft Visual C++ 14.0 is required` | Same cause as above: a package without a wheel for your Python. Don't install build tools; use the pinned requirements or Python 3.12. |
| `'node' is not recognized` after installing Node | Open a new terminal so PATH refreshes. |
| CORS error in browser console | Frontend runs on a different origin; add it to `CORS_ORIGINS` in `.env` and restart the backend. |
| Settings shows **Ollama not detected** | Start the Ollama app (or `ollama serve`), then click *Re-check*. Custom host? Set `OLLAMA_BASE_URL`. |
| Assistant says **“Ollama is not running”** | Start the Ollama app (system tray) or run `ollama serve`. |
| Answers take a long time | Normal on a CPU (25–40 s for 8B). Use a smaller model, or raise `OLLAMA_GENERATION_TIMEOUT_SECONDS` if answers time out. |
| Documents stay **“Indexing…”** | Ollama is down or `nomic-embed-text` isn't pulled; indexing resumes on its own once it's available. Check Settings → AI assistant. |
| Assistant answers **“not enough evidence”** for something you imported | Check the document's *AI search* status is *Indexed*, widen the scope picker to “Whole library”, or rephrase with the paper's terminology. |
| Cloud provider refused with **“Enable this explicitly in Settings”** | Tick the consent box under Settings → AI assistant (only after reading what is sent). |
| Comparison / gap analysis is “Queued” for a long time | Analyses run one at a time in the background; each new paper takes about 3 minutes to profile on a CPU. Progress shows on the page. |
| Analysis **failed: incomplete JSON** | The model hit its output limit. Retry, or use a stronger model (`OLLAMA_CHAT_MODEL`). |
| Many fields **“Not reported”** for a long paper | Only the most relevant excerpts are read per pass; raise `ANALYSIS_EXCERPT_CHARS` (and `OLLAMA_NUM_CTX`) if you have the RAM. |
| Model shows **not installed** | `ollama pull <model>` with the exact name shown, or change `OLLAMA_CHAT_MODEL` / `OLLAMA_EMBED_MODEL`. |
| Upload fails with **“does not look like a valid PDF”** | The file's contents don't match its extension (e.g. a renamed file). Re-export it as a real PDF. |
| **“The PDF is password-protected”** | Remove the password in your PDF reader (Print → Save as PDF) and import again. |
| Imported PDF warns **“No text could be extracted”** | It is a scanned image. OCR isn't supported yet; run it through an OCR tool (e.g. OCRmyPDF, free) first. |
| Title/authors wrong or missing | Open the document → **Edit details**. Auto-detected fields are listed in the notice at the top. |
| **“Importing from local or private network addresses is not allowed”** | URL import only fetches public websites (SSRF protection). Download the file and upload it instead. |
| **413** / “exceeds the … MB limit” | Raise `MAX_UPLOAD_MB` in `.env` and restart the backend. |
| `alembic` error on startup | Make sure only one backend is running, and check that `data/database/` is writable. As a last resort, back up `data/` and start with a fresh database. |
| Timestamps look hours off | Fixed in 0.1.0 (UTC-aware timestamps). Update and restart the backend. |
| Reset all local data | Stop the backend and delete the `data/` folder. **This permanently deletes your library.** |

## Licence

Intended to be open source (licence to be chosen). Note that PyMuPDF is AGPL-3.0; see
docs/ARCHITECTURE.md §2.
