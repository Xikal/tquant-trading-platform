#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

cd "$ROOT_DIR/frontend-next"
npm run build

cd "$ROOT_DIR/backend"
if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing backend virtualenv python at backend/.venv/bin/python" >&2
  exit 1
fi

exec .venv/bin/python -m uvicorn app.main:app --host "$HOST" --port "$PORT"
