#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export DATABASE_URL="${DATABASE_URL:-sqlite:///./data/t_quant.db}"
export RUNTIME_BACKGROUND_JOBS_ENABLED="${RUNTIME_BACKGROUND_JOBS_ENABLED:-false}"

trap 'kill 0' EXIT

(cd backend && PYTHONPATH=. .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${BACKEND_PORT:-8000}") &
(cd backend && PYTHONPATH=. .venv/bin/python -m app.workers.runtime_worker) &

wait
