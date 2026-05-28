#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-18120}"
RUNTIME_DIR="$ROOT_DIR/.runtime"
SMOKE_DB_PATH="$RUNTIME_DIR/app_api_smoke.db"
BACKEND_LOG="$RUNTIME_DIR/app_api_smoke_backend.log"

mkdir -p "$RUNTIME_DIR"
cp -f "$ROOT_DIR/backend/data/t_quant.db" "$SMOKE_DB_PATH"

cd "$ROOT_DIR/backend"
if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing backend virtualenv python at backend/.venv/bin/python" >&2
  exit 1
fi

DATABASE_URL="sqlite:///$SMOKE_DB_PATH" \
AUTH_SECRET_KEY="app-api-smoke-secret-0123456789abcdef0123456789abcdef0123456789abcdef" \
ADMIN_API_TOKEN="app-api-smoke-admin-token" \
RUNTIME_BACKGROUND_JOBS_ENABLED=false \
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

AUTH_JSON="$(curl -sS -X POST "http://127.0.0.1:${BACKEND_PORT}/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"app_api_smoke","password":"AppApiSmoke12345!","display_name":"App API Smoke"}')"
if python3 - <<'PY' "$AUTH_JSON"
import json, sys
payload = json.loads(sys.argv[1])
raise SystemExit(0 if "access_token" in payload else 1)
PY
then
  :
else
  AUTH_JSON="$(curl -sS -X POST "http://127.0.0.1:${BACKEND_PORT}/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"app_api_smoke","password":"AppApiSmoke12345!"}')"
fi
AUTH_TOKEN="$(python3 - <<'PY' "$AUTH_JSON"
import json, sys
print(json.loads(sys.argv[1]).get("access_token", ""))
PY
)"
if [[ -z "$AUTH_TOKEN" ]]; then
  echo "Failed to obtain app API smoke auth token: $AUTH_JSON" >&2
  exit 1
fi
AUTH_HEADER=(-H "Authorization: Bearer $AUTH_TOKEN")

BOOTSTRAP_JSON="$(curl -sS "http://127.0.0.1:${BACKEND_PORT}/api/app/bootstrap")"
WATCHLIST_UPSERT_JSON="$(curl -sS -X POST "http://127.0.0.1:${BACKEND_PORT}/api/app/watchlist" "${AUTH_HEADER[@]}" -H "Content-Type: application/json" -d '{"symbol":"510300","name":"沪深300ETF","base_position":1200,"available_position":900,"cost_basis":3.45,"memo":"app-smoke"}')"
HOME_JSON="$(curl -sS "http://127.0.0.1:${BACKEND_PORT}/api/app/home" "${AUTH_HEADER[@]}")"
WATCHLIST_DETAIL_JSON="$(curl -sS "http://127.0.0.1:${BACKEND_PORT}/api/app/watchlist/510300" "${AUTH_HEADER[@]}")"
LOW_BUY_JSON="$(curl -sS "http://127.0.0.1:${BACKEND_PORT}/api/app/low-buy?limit=4&scan_limit=48&scan_mode=quick" "${AUTH_HEADER[@]}")"

LOW_BUY_SYMBOL="$(
  python3 - <<'PY' "$LOW_BUY_JSON"
import json
import sys

payload = json.loads(sys.argv[1])
for item in payload.get("confirmed_candidates", []) + payload.get("watch_candidates", []):
    symbol = item.get("symbol")
    if symbol:
        print(symbol)
        break
PY
)"

if [[ -n "$LOW_BUY_SYMBOL" ]]; then
  LOW_BUY_DETAIL_JSON="$(curl -sS "http://127.0.0.1:${BACKEND_PORT}/api/app/low-buy/${LOW_BUY_SYMBOL}?scan_limit=24" "${AUTH_HEADER[@]}")"
else
  LOW_BUY_DETAIL_JSON="{}"
fi

python3 - <<'PY' "$BOOTSTRAP_JSON" "$WATCHLIST_UPSERT_JSON" "$HOME_JSON" "$WATCHLIST_DETAIL_JSON" "$LOW_BUY_JSON" "$LOW_BUY_DETAIL_JSON"
import json
import sys

bootstrap = json.loads(sys.argv[1])
watchlist_upsert = json.loads(sys.argv[2])
home = json.loads(sys.argv[3])
watchlist_detail = json.loads(sys.argv[4])
low_buy = json.loads(sys.argv[5])
low_buy_detail = json.loads(sys.argv[6])

assert bootstrap["app_name"] == "A股短线做T助手", f"unexpected app name: {bootstrap}"
assert bootstrap["feature_flags"]["watchlist_enabled"] is True, "watchlist feature should be enabled"
assert watchlist_upsert["symbol"] == "510300", f"watchlist upsert failed: {watchlist_upsert}"
assert home["summary"]["total"] >= 1, f"home summary total should be >= 1: {home}"
assert any(item["symbol"] == "510300" for item in home["items"]), "home items should include seeded watchlist symbol"
assert watchlist_detail["symbol"] == "510300", f"watchlist detail mismatch: {watchlist_detail}"
assert low_buy["strategy"]["strategy_key"] == "first_board", f"low-buy strategy mismatch: {low_buy}"
assert isinstance(low_buy["priority_board"]["items"], list), "priority board items should be a list"
assert "confirmed_candidates" in low_buy and "watch_candidates" in low_buy, "low-buy should return candidate buckets"
assert isinstance(low_buy["confirmed_candidates"], list), "confirmed_candidates should be a list"
assert isinstance(low_buy["watch_candidates"], list), "watch_candidates should be a list"
if low_buy_detail:
    assert low_buy_detail["candidate"]["symbol"], f"low-buy detail missing candidate symbol: {low_buy_detail}"
print("app-api-smoke:ok")
PY
