#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BASE_URL="${1:-http://127.0.0.1:18080}"
OUT_SUFFIX="$(
  python3 - <<'PY' "$BASE_URL"
import re
import sys

value = sys.argv[1].strip().lower()
value = re.sub(r"^https?://", "", value)
value = re.sub(r"[^a-z0-9._-]+", "_", value).strip("_")
print(value or "default")
PY
)"
OUT_DIR="$ROOT_DIR/.runtime/ui-smoke/$OUT_SUFFIX"
INSERTED_SYMBOLS=()

mkdir -p "$OUT_DIR"

cleanup() {
  for symbol in "${INSERTED_SYMBOLS[@]:-}"; do
    curl -sS -X DELETE "$BASE_URL/api/watchlist/$symbol" >/dev/null || true
  done
}
trap cleanup EXIT

TEMP_PAYLOADS="$(
  python3 - <<'PY' "$BASE_URL"
import json
import sys
import urllib.request

base_url = sys.argv[1].rstrip("/")
candidates = [
    ("600519", "贵州茅台", 500, 500, 1588.0, "UI smoke temp stock"),
    ("510300", "沪深300ETF", 1200, 800, 3.456, "UI smoke temp etf"),
    ("159915", "创业板ETF", 1500, 900, 2.145, "UI smoke temp etf"),
    ("688981", "中芯国际", 400, 400, 48.6, "UI smoke temp stock"),
]
with urllib.request.urlopen(f"{base_url}/api/watchlist", timeout=10) as response:
    existing = {item["symbol"] for item in json.load(response)}

selected = []
for row in candidates:
    if row[0] in existing:
        continue
    selected.append(
        json.dumps(
            {
                "symbol": row[0],
                "name": row[1],
                "base_position": row[2],
                "available_position": row[3],
                "cost_basis": row[4],
                "memo": row[5],
            },
            ensure_ascii=False,
        )
    )
    if len(selected) == 2:
        break

for payload in selected:
    print(payload)
PY
)"

while IFS= read -r payload; do
  [[ -z "$payload" ]] && continue
  symbol="$(python3 - <<'PY' "$payload"
import json, sys
print(json.loads(sys.argv[1])["symbol"])
PY
)"
  curl -sS -X POST "$BASE_URL/api/watchlist" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null
  INSERTED_SYMBOLS+=("$symbol")
done <<< "$TEMP_PAYLOADS"

if [[ "${#INSERTED_SYMBOLS[@]}" -gt 0 ]]; then
  joined_symbols="$(IFS=,; echo "${INSERTED_SYMBOLS[*]}")"
  signals_ready=0
  for _ in $(seq 1 3); do
    signals_json="$(
      python3 - <<'PY' "$BASE_URL"
import sys
import urllib.request

base_url = sys.argv[1].rstrip("/")
try:
    with urllib.request.urlopen(f"{base_url}/api/watchlist/signals", timeout=3) as response:
        print(response.read().decode("utf-8"))
except Exception:
    print("[]")
PY
    )"
    if python3 - <<'PY' "$signals_json" "$joined_symbols"
import json
import sys

payload = json.loads(sys.argv[1] or "[]")
symbols = {item["symbol"] for item in payload}
required = {item for item in sys.argv[2].split(",") if item}
if required and required.issubset(symbols):
    raise SystemExit(0)
raise SystemExit(1)
PY
    then
      signals_ready=1
      break
    fi
    sleep 1
  done
  if [[ "$signals_ready" -ne 1 ]]; then
    echo "[ui-smoke] inserted symbols did not become ready in time, continue with page smoke" >&2
  fi
fi

BACKTEST_JSON="$(curl -sS -X POST "$BASE_URL/api/backtests" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"510300","lookback_bars":180,"bar_period":"5m","initial_position":1000,"walk_forward_windows":3}')"

python3 - <<'PY' "$BACKTEST_JSON"
import json
import sys

payload = json.loads(sys.argv[1])
for key in ("symbol", "total_trades", "profit_factor", "walk_forward_score"):
    assert key in payload, f"backtest payload missing {key}"
print("ui-backtest:ok")
PY

DASHBOARD_SIGNALS_JSON="$(
  python3 - <<'PY' "$BASE_URL"
import json
import sys
import urllib.request

base_url = sys.argv[1].rstrip("/")
try:
    with urllib.request.urlopen(f"{base_url}/api/watchlist/signals", timeout=12) as response:
        print(response.read().decode("utf-8"))
except Exception:
    print("[]")
PY
)"
DASHBOARD_WAIT_SELECTOR="$(
  python3 - <<'PY' "$DASHBOARD_SIGNALS_JSON"
import json
import sys

payload = json.loads(sys.argv[1] or "[]")
if payload:
    print(f"text={payload[0]['symbol']}")
else:
    print("text=已持仓做T信号扫描")
PY
)"

echo "[ui-smoke] dashboard -> $BASE_URL/"
npx --yes playwright screenshot \
  --channel=chrome \
  --device="Desktop Chrome" \
  --full-page \
  --wait-for-selector="$DASHBOARD_WAIT_SELECTOR" \
  --wait-for-timeout=3000 \
  --timeout=30000 \
  "$BASE_URL/" \
  "$OUT_DIR/dashboard.png" >/dev/null

echo "[ui-smoke] settings -> $BASE_URL/settings"
npx --yes playwright screenshot \
  --channel=chrome \
  --device="Desktop Chrome" \
  --full-page \
  --wait-for-selector='text=当前运行快照' \
  --wait-for-timeout=1500 \
  --timeout=20000 \
  "$BASE_URL/settings" \
  "$OUT_DIR/settings.png" >/dev/null

echo "[ui-smoke] analysis -> $BASE_URL/analysis"
npx --yes playwright screenshot \
  --channel=chrome \
  --device="Desktop Chrome" \
  --full-page \
  --wait-for-selector='text=输入持仓信息后' \
  --wait-for-timeout=1500 \
  --timeout=30000 \
  "$BASE_URL/analysis" \
  "$OUT_DIR/analysis.png" >/dev/null

echo "[ui-smoke] research -> $BASE_URL/research"
npx --yes playwright screenshot \
  --channel=chrome \
  --device="Desktop Chrome" \
  --full-page \
  --wait-for-selector='text=运行回测' \
  --wait-for-timeout=1500 \
  --timeout=20000 \
  "$BASE_URL/research" \
  "$OUT_DIR/research.png" >/dev/null

echo "UI smoke passed. Screenshots saved to $OUT_DIR"
