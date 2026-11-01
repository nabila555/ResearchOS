#!/usr/bin/env bash
# Start ResearchOS (backend + frontend) on macOS / Linux. The first run installs dependencies.
#   ./start.sh               development mode (hot reload)
#   ./start.sh --production  optimised build, faster pages
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
PYTHON="$BACKEND/.venv/bin/python"

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "ERROR: '$1' not found. $2" >&2; exit 1; }
}
need npm "Install Node.js LTS from https://nodejs.org"

if [ ! -x "$PYTHON" ]; then
  need python3 "Install Python 3.11+ from https://python.org"
  echo "Creating the Python environment (first run only)..."
  python3 -m venv "$BACKEND/.venv"
  "$PYTHON" -m pip install --upgrade pip --quiet
  "$PYTHON" -m pip install -r "$BACKEND/requirements.txt"
fi

if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "Installing frontend packages (first run only)..."
  (cd "$FRONTEND" && npm install)
fi

if curl -fsS --max-time 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
  echo "Ollama is running."
else
  echo "Ollama is not running: the library works, but AI features need it (https://ollama.com)."
fi

FRONTEND_CMD="dev"
if [ "${1:-}" = "--production" ]; then
  echo "Building the frontend..."
  (cd "$FRONTEND" && npm run build)
  FRONTEND_CMD="start"
fi

cleanup() {
  trap - INT TERM EXIT
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  echo "Stopped."
}
trap cleanup INT TERM EXIT

(cd "$BACKEND" && exec "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!
(cd "$FRONTEND" && exec npm run "$FRONTEND_CMD") &
FRONTEND_PID=$!

echo
echo "ResearchOS is starting:"
echo "  App:      http://localhost:3000"
echo "  API docs: http://127.0.0.1:8000/docs"
echo "Press Ctrl+C to stop both servers."
wait -n "$BACKEND_PID" "$FRONTEND_PID"
echo "A server stopped; shutting down."
