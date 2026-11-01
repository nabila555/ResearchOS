# Contributing to ResearchOS

Thanks for your interest in improving ResearchOS. This guide covers how to set up a development
environment, the standards changes are held to, and how to submit them.

## Principles

Every change should keep ResearchOS:

1. **Free and local-first.** No feature may require a paid service, account or cloud upload.
   Optional cloud features must be off by default and need explicit user consent.
2. **Honest.** No placeholder buttons or simulated features. If something isn't built, it isn't
   shown. AI output must cite its sources and be verified in code where possible; unverifiable
   output is labelled as such.
3. **Private and safe.** Validate inputs, keep file access inside the data folder, never log
   document content, and keep secrets out of source code.

## Development setup

Prerequisites: Python 3.11+, Node.js 20.9+, and optionally [Ollama](https://ollama.com) for
manual AI testing (the automated tests don't need it).

```bash
git clone https://github.com/nabila555/ResearchOS.git
cd ResearchOS

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev
```

## Before you open a pull request

Run the same checks as CI:

```bash
# backend/
python -m ruff check app tests
python -m ruff format app tests
python -m pytest

# frontend/
npm run lint
npm run typecheck
npm test
npm run build
```

### Tests

- Backend tests use deterministic fake AI providers (`backend/tests/fixtures/fake_ai.py`) and
  generate sample PDFs and Word files on the fly. Never call a real model or the network in tests.
- Add tests for new endpoints, services and verification logic. Bug fixes should include a test
  that fails without the fix.
- Frontend logic and rendering tests live in `frontend/tests/` (Vitest + Testing Library).

### Database changes

Models live in `backend/app/models/`. After changing one, create a migration and commit it:

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
```

Review the generated file: autogenerate must not touch the FTS5 virtual tables.

### Code style

- Python: ruff (line length 100), type hints, business logic in `app/services/`, thin routes.
- TypeScript: strict mode, API types in `frontend/types/api.ts`, data access through
  `frontend/services/` and the hooks in `frontend/hooks/`.
- UI: handle loading, error and empty states; keep components accessible (labels, keyboard).
- Comments explain *why*, not *what*.

## Submitting changes

1. For anything larger than a small fix, open an issue first to discuss the approach.
2. Create a branch from `main` (`fix/…`, `feat/…`, `docs/…`).
3. Keep commits focused, with clear messages in the imperative mood ("Add RIS import").
4. Update the docs (`README.md`, `docs/`, `DEVELOPMENT_STATUS.md`) when behaviour changes.
5. Open a pull request and fill in the checklist.

## Reporting bugs and security issues

Use the issue templates for bugs and feature requests. **Do not report security vulnerabilities
in public issues.** See [SECURITY.md](SECURITY.md).

## Licence

By contributing, you agree that your contributions are licensed under the
[GNU AGPL v3.0](LICENSE), the same licence as the project.
