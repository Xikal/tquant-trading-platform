#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-18080}"
SMOKE_PORT="${SMOKE_PORT:-18081}"
RUNTIME_DIR="$ROOT_DIR/.runtime"
BACKEND_LOG="$RUNTIME_DIR/prod_preflight_backend.log"
PREFLIGHT_DB_PATH="$RUNTIME_DIR/prod_preflight.db"
PREFLIGHT_RUNTIME_ENV="$RUNTIME_DIR/runtime.env.prod-preflight"

mkdir -p "$RUNTIME_DIR"
rm -f "$PREFLIGHT_DB_PATH" "$PREFLIGHT_DB_PATH-shm" "$PREFLIGHT_DB_PATH-wal" "$PREFLIGHT_RUNTIME_ENV"

./scripts/version_sync.py --check >/dev/null

cd "$ROOT_DIR/frontend"
read -r VERSION_NAME VERSION_CODE < <(python3 - <<'PY' "$ROOT_DIR/VERSION.json"
import json
import sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
print(data.get("version", "1.0.0"), int(data.get("build_number", 1)))
PY
)
VITE_NATIVE_VERSION_CODE="${VITE_NATIVE_VERSION_CODE:-$VERSION_CODE}" \
VITE_NATIVE_VERSION_NAME="${VITE_NATIVE_VERSION_NAME:-$VERSION_NAME}" \
VITE_API_BASE_URL="${VITE_API_BASE_URL:-https://weisilianghua.cloud/api}" \
npm run build:native >/dev/null
npx cap sync android >/dev/null
cd "$ROOT_DIR"
python3 ./scripts/harden_native_release_config.py >/dev/null
./scripts/native_release_check.py >/dev/null

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
DATABASE_URL="sqlite:///$PREFLIGHT_DB_PATH" \
RUNTIME_ENV_PATH="$PREFLIGHT_RUNTIME_ENV" \
BASE_ENV_PATH="$RUNTIME_DIR/nonexistent.env" \
AUTH_SECRET_KEY="prod-preflight-secret-0123456789abcdef0123456789abcdef0123456789abcdef" \
ADMIN_API_TOKEN="prod-preflight-admin-token" \
RUNTIME_BACKGROUND_JOBS_ENABLED=false \
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" >/dev/null 2>&1 || true
  wait "$BACKEND_PID" >/dev/null 2>&1 || true
  rm -f "$PREFLIGHT_DB_PATH" "$PREFLIGHT_DB_PATH-shm" "$PREFLIGHT_DB_PATH-wal" "$PREFLIGHT_RUNTIME_ENV"
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
AUTH_JSON="$(curl -sS -X POST "http://127.0.0.1:${BACKEND_PORT}/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"prod_preflight","password":"ProdPreflight12345!","display_name":"Prod Preflight"}')"
AUTH_TOKEN="$(python3 - <<'PY' "$AUTH_JSON"
import json, sys
print(json.loads(sys.argv[1]).get("access_token", ""))
PY
)"
if [[ -z "$AUTH_TOKEN" ]]; then
  echo "Failed to obtain preflight auth token: $AUTH_JSON" >&2
  exit 1
fi
SETTINGS_JSON="$(curl -sS "http://127.0.0.1:${BACKEND_PORT}/api/settings" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Admin-Token: prod-preflight-admin-token")"
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
