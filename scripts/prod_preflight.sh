#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-18080}"
SMOKE_PORT="${SMOKE_PORT:-18081}"
RUNTIME_DIR="$ROOT_DIR/.runtime"
BACKEND_LOG="$RUNTIME_DIR/prod_preflight_backend.log"

mkdir -p "$RUNTIME_DIR"

./scripts/version_sync.py --check >/dev/null

cd "$ROOT_DIR/frontend"
npm run build >/dev/null

cd "$ROOT_DIR/backend"
if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing backend virtualenv python at backend/.venv/bin/python" >&2
  exit 1
fi

.venv/bin/python -m compileall app >/dev/null

cd "$ROOT_DIR"
BACKEND_PORT="$SMOKE_PORT" ./scripts/qa_smoke.sh >/dev/null

cd "$ROOT_DIR/backend"
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in $(seq 1 40); do
  if curl --max-time 2 -s "http://127.0.0.1:${BACKEND_PORT}/healthz" | grep -q '"status":"ok"'; then
    break
  fi
  sleep 1
done

if ! curl --max-time 2 -s "http://127.0.0.1:${BACKEND_PORT}/healthz" | grep -q '"status":"ok"'; then
  echo "Backend failed to become healthy. See $BACKEND_LOG" >&2
  exit 1
fi

ROOT_HTML="$(curl -sS "http://127.0.0.1:${BACKEND_PORT}/")"
SETTINGS_JSON="$(curl -sS "http://127.0.0.1:${BACKEND_PORT}/api/settings")"
READY_JSON="$(curl -sS "http://127.0.0.1:${BACKEND_PORT}/readyz")"

python3 - <<'PY' "$ROOT_HTML" "$SETTINGS_JSON" "$READY_JSON"
import json
import sys

html = sys.argv[1]
settings = json.loads(sys.argv[2])
ready = json.loads(sys.argv[3])

assert "<div id=\"root\"></div>" in html, "frontend root container not found"
assert "assets/index-" in html, "built frontend assets not linked"
assert isinstance(settings.get("data_source"), str), "settings API unavailable in single-port mode"
assert ready.get("status") == "ok", f"readyz not ok: {ready}"
assert ready.get("checks", {}).get("database") is True, "database readiness check failed"
assert ready.get("checks", {}).get("frontend_dist") is True, "frontend readiness check failed"
print("prod-preflight:ok")
PY

echo "Production preflight passed."
