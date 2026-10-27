#!/usr/bin/env bash
# AutoScout developer scripts (macOS/Linux)
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-}" in
  backend-dev)
    cd backend
    python -m uvicorn app.main:app --reload --port 8000
    ;;
  frontend-dev)
    cd frontend
    npm run dev
    ;;
  test)
    cd backend
    python -m pytest -q
    ;;
  *)
    echo "Usage: scripts/dev.sh [backend-dev|frontend-dev|test]" >&2
    exit 1
    ;;
esac
