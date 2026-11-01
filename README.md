<div align="center">

# ResearchOS

**A private, local-first research workspace with AI that cites its sources.**

Collect papers, understand them, find the gaps, and write a properly cited literature review,
all on your own computer, with free and open-source tools.

[![CI](https://github.com/nabila555/ResearchOS/actions/workflows/ci.yml/badge.svg)](https://github.com/nabila555/ResearchOS/actions/workflows/ci.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![Node 20.9+](https://img.shields.io/badge/node-20.9%2B-339933?logo=node.js&logoColor=white)
![Runs offline](https://img.shields.io/badge/AI-local%20%28Ollama%29-black)

[Features](#features) · [Quick start](#quick-start) · [User guide](docs/USER_GUIDE.md) ·
[Architecture](docs/ARCHITECTURE.md) · [Contributing](CONTRIBUTING.md)

</div>

---

## Why ResearchOS?

Most AI research tools send your documents to the cloud and give answers you can't check.
ResearchOS takes the opposite approach:

- **Zero cost, no accounts.** No paid APIs, subscriptions or cloud services. AI runs locally
  through [Ollama](https://ollama.com).
- **Private by default.** Your files, database and search index stay in one folder on your
  machine. A cloud model (Claude API) is optional and used only after you explicitly consent.
- **Verifiable, not just plausible.** Every AI statement links to the page it came from, and
  **code** checks each link: the cited passage must exist, the quote must appear in it, and every
  number must match. Anything that fails is labelled *unverified*, never shown as fact. When your
  sources don't answer a question, the assistant says so instead of guessing.

## Features

| | |
|---|---|
| 📚 **Research library** | Import PDF, Word, Markdown, text, web articles and notes. Automatic title, author, year, DOI, abstract, keyword and reference extraction, with guessed values flagged for review. Collections, tags, projects, filters, and full-text search showing the matching page (**Ctrl/⌘ K** from anywhere). |
| 💬 **AI assistant** | Ask questions about your library. Answers come only from your sources, with page-level citation chips you can open. Search can be limited to a collection or project. Answers stream as they are written. |
| 🧾 **Paper profiles** | Objective, research questions, framework, methods, data, sample, findings, limitations and future work, each statement with a verified page link. |
| ⚖️ **Paper comparison** | Side-by-side tables for 2–6 papers; "not reported" instead of guesses. |
| 🔍 **Research gap finder** | Underexplored areas, contradictions, missing perspectives, methodological limits and research questions. **Literature-supported** findings are kept strictly separate from **AI hypotheses**. |
| 🕵️ **Paper Detective** | Careful observations on claims, methods, possible bias and reproducibility, framed as prompts for your own reading rather than accusations. |
| 🕸️ **Knowledge graph** | Interactive map of papers, authors, topics, concepts, semantic similarity and shared references; expand a paper into its verified methods and findings. |
| ✍️ **Literature review workspace** | Organise sources into themes (with grouping suggestions), generate cited theme syntheses, and export the review to Markdown with formatted in-text citations and references. |
| 📎 **Citation manager** | APA 7, MLA 9, Chicago and IEEE; copy as rich text; export BibTeX, RIS or Markdown. Missing details are flagged, never invented. |
| 📄 **Reports** | Research summaries, methodology analyses, comparisons, gap reports, literature reviews and AI-drafted research proposals, downloadable as Markdown or **PDF** (rendered offline). |

## Quick start

### 1. Install the prerequisites (once)

| Tool | Version | Windows | macOS | Linux |
|---|---|---|---|---|
| Python | 3.11+ | `winget install Python.Python.3.12` | `brew install python@3.12` | your package manager |
| Node.js | 20.9+ (LTS) | `winget install OpenJS.NodeJS.LTS` | `brew install node` | [nodejs.org](https://nodejs.org) |
| Ollama | latest | `winget install Ollama.Ollama` | [ollama.com/download](https://ollama.com/download) | `curl -fsSL https://ollama.com/install.sh \| sh` |

Then download the two free local models (about 5 GB, once):

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

> 8 GB RAM? Use `ollama pull llama3.2:3b` and set `OLLAMA_CHAT_MODEL=llama3.2:3b` in `.env`
> (see [Configuration](#configuration)).

### 2. Get the code

```bash
git clone https://github.com/nabila555/ResearchOS.git
cd ResearchOS
```

### 3. Start ResearchOS

**Windows (PowerShell):**

```powershell
.\start.ps1
```

**macOS / Linux:**

```bash
./start.sh
```

The first run creates a Python environment and installs all dependencies (a few minutes). Then
open **http://localhost:3000**. Press `Ctrl+C` in the terminal to stop.

Add `-Production` (Windows) or `--production` (macOS/Linux) for an optimised build with faster
pages. Both servers listen only on your computer (`127.0.0.1`).

> **"Running scripts is disabled on this system"?** Run
> `powershell -ExecutionPolicy Bypass -File .\start.ps1` instead.

### 4. First steps

1. **Settings**: check that Ollama and both models show as detected.
2. **Research Library → Add**: upload a few papers (or drag them onto the page).
3. **AI Assistant**: ask *"What are the main findings across these papers?"*

The [user guide](docs/USER_GUIDE.md) walks through everything else.

<details>
<summary><strong>Manual start (two terminals)</strong></summary>

**Backend:**

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API documentation: http://127.0.0.1:8000/docs. The database and `data/` folder are created,
and migrations are applied, automatically on start.

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

</details>

## Configuration

Everything works without configuration. To change defaults, copy `.env.example` to `.env` in the
project root:

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_CHAT_MODEL` | `llama3.1:8b` | Local model for answers and analyses |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Local model for semantic search |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Where Ollama runs |
| `OLLAMA_GENERATION_TIMEOUT_SECONDS` | `600` | Raise if long answers time out on slow machines |
| `MAX_UPLOAD_MB` | `50` | Upload size limit |
| `ANALYSIS_EXCERPT_CHARS` | `7000` | Text read per analysis pass (raise with a larger context window) |
| `DATA_DIR` | `data` | Where documents, database and index are stored |
| `ANTHROPIC_API_KEY` | *(empty)* | **Optional** Claude API; also requires the consent box in Settings |

If the backend runs elsewhere, copy `frontend/.env.example` to `frontend/.env.local` and set
`NEXT_PUBLIC_API_URL`.

## How it works

```
Browser ── Next.js 16 · TypeScript · Tailwind · React Flow
   │  JSON over HTTP (127.0.0.1 only)
FastAPI ── services ── SQLite (+ FTS5 full-text search)
   ├── document processing: PyMuPDF, python-docx, BeautifulSoup
   ├── retrieval: local embeddings + BM25, fused (RRF)
   ├── research analysis: profiles, comparison, gaps, detective, synthesis
   │      └── every model output is verified in code before it is shown
   └── AI providers: Ollama (default) │ Claude API (optional, consent-gated)
```

- **Retrieval-augmented answers.** Documents are split into page-aware passages, embedded
  locally, and searched with hybrid semantic and keyword search. The model sees only numbered
  passages and must cite them. If nothing relevant is found, the model is never called.
- **Structured, constrained output.** Analyses use JSON-schema-constrained generation, then a
  verifier checks every statement's excerpt, quote and numbers.
- **Background jobs.** Indexing and analyses run in durable background queues, so you can keep
  working.

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Hardware

| Profile | RAM | Experience |
|---|---|---|
| Minimum | 8 GB | Library, search, citations; 3B models for AI (slower, less precise) |
| Recommended | 16 GB | 8B models on CPU: about 25–40 s per answer, about 3 min to profile a paper |
| Comfortable | 32 GB or a GPU with 8 GB+ VRAM | Larger or faster models |

The app itself is fast. On a 500-paper synthetic library (laptop CPU), search takes about 60 ms,
assistant retrieval about 110 ms, and PDF export about 50 ms. See the
[benchmark](backend/scripts/benchmark.py).

## Development

```bash
# Backend: tests and lint
cd backend
pip install -r requirements-dev.txt
python -m pytest
python -m ruff check app tests

# Frontend: tests, types, lint, production build
cd frontend
npm test
npm run typecheck
npm run lint
npm run build
```

Tests never need Ollama or the internet: AI providers are replaced by deterministic fakes, and
sample PDFs and Word files are generated on the fly. Every push runs the same checks in
[GitHub Actions](.github/workflows/ci.yml).

Database changes use Alembic; migrations run automatically at startup. After changing a model:

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
```

<details>
<summary><strong>Project structure</strong></summary>

```
ResearchOS/
├── backend/                  FastAPI application (Python)
│   ├── app/
│   │   ├── api/              HTTP routes
│   │   ├── ai/               AI providers (Ollama, Claude), vector index
│   │   ├── core/             configuration, database, migrations
│   │   ├── document_processing/   validation, extraction, metadata, chunking, URL import
│   │   ├── models/           database tables
│   │   ├── reports/          report builders, Markdown → PDF
│   │   ├── research_analysis/     profiles, gaps, detective, synthesis, evidence checks
│   │   ├── schemas/          request/response models
│   │   ├── services/         business logic
│   │   └── citations.py      APA / MLA / Chicago / IEEE, BibTeX, RIS
│   ├── migrations/           Alembic migrations
│   ├── scripts/benchmark.py  performance benchmark
│   └── tests/                pytest suite
├── frontend/                 Next.js application (TypeScript)
│   ├── app/                  pages (App Router)
│   ├── components/           UI by feature
│   ├── hooks/ lib/ services/ types/
│   └── tests/                Vitest suite
├── docs/                     user guide, architecture, roadmap
├── data/                     your library (created at runtime, git-ignored)
├── start.ps1 · start.sh      one-command start
└── DEVELOPMENT_STATUS.md     what is done, known limitations, ideas
```

</details>

## Troubleshooting

| Problem | Solution |
|---|---|
| **"Backend not reachable"** in the app | Start the backend (or use the start script). Make sure port 8000 is free. |
| **Ollama not detected** | Start the Ollama app or run `ollama serve`, then click *Re-check* in Settings. |
| A model shows **not installed** | `ollama pull <model>` using the exact name shown. |
| Answers are slow or time out | Normal on a CPU (25–40 s with 8B). Use a smaller model or raise `OLLAMA_GENERATION_TIMEOUT_SECONDS`. |
| Documents stay **"Indexing…"** | Ollama is not running or `nomic-embed-text` is missing; indexing resumes automatically. |
| Assistant says **"not enough evidence"** | Check the document is *Indexed* (document page), widen the scope to "Whole library", or use the paper's terminology. |
| Analysis is **queued** for a long time | Analyses run one at a time; each new paper takes about 3 minutes to profile on a CPU. |
| Analysis **failed: incomplete JSON** | The model hit its output limit. Retry, or use a stronger model. |
| PDF says **"No text could be extracted"** | It is a scanned image. Run it through OCR (e.g. [OCRmyPDF](https://ocrmypdf.readthedocs.io), free) first. |
| Citation shows **Missing: volume / pages / doi** | Document → *Edit details* → Citation details. Missing values are never guessed. |
| `pip` fails building **pyyaml / faiss / chromadb** or asks for **Visual C++** | Your Python is too new for some optional wheels. Use the provided `requirements.txt` as-is, or Python 3.12. |
| `'node' is not recognized` after installing Node | Open a new terminal so `PATH` refreshes. |
| **"Running scripts is disabled"** (Windows) | `powershell -ExecutionPolicy Bypass -File .\start.ps1` |

More: [user guide](docs/USER_GUIDE.md) and [known limitations](DEVELOPMENT_STATUS.md).

## Privacy and security

- Documents, database, embeddings and reports stay in `data/` on your computer.
- Uploads are validated by content, not just by file extension. Files are size-limited and
  stored under content hashes, and paths are confined to the data folder.
- URL import fetches only public addresses (SSRF protection on every redirect).
- AI output is rendered as text or sanitised Markdown; raw HTML from models is never executed.
- Cloud AI is off by default and needs both an API key and an explicit consent setting. Only the
  question and matching passages are sent, never whole files.

Found a vulnerability? See [SECURITY.md](SECURITY.md).

## Roadmap and status

ResearchOS 1.0 completes all six planned phases (foundation, library, assistant, research
intelligence, knowledge management, export and polish). See [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md)
for what each phase includes, honest known limitations, and ideas beyond 1.0 (OCR, claim-level
verification, more citation types, browser end-to-end tests).

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md). In short: open an issue
first for larger changes, keep features honest (no placeholder functionality), and include tests.

## License

ResearchOS is licensed under the **GNU Affero General Public License v3.0**. See [LICENSE](LICENSE).
You may use, modify and share it. If you run a modified version for others over a network, you
must make your source code available to them.

## Acknowledgements

Built on excellent free software: [FastAPI](https://fastapi.tiangolo.com),
[Next.js](https://nextjs.org), [Ollama](https://ollama.com), [PyMuPDF](https://pymupdf.readthedocs.io),
[SQLite](https://sqlite.org), [React Flow](https://reactflow.dev), [Radix UI](https://www.radix-ui.com),
[Tailwind CSS](https://tailwindcss.com) and many more listed in `backend/requirements.txt` and
`frontend/package.json`.
