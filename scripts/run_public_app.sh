#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime"
BACKEND_LOG="$RUNTIME_DIR/backend.log"
TUNNEL_LOG="$RUNTIME_DIR/tunnel.log"
BACKEND_PID_FILE="$RUNTIME_DIR/backend.pid"
TUNNEL_PID_FILE="$RUNTIME_DIR/tunnel.pid"
PUBLIC_URL_FILE="$RUNTIME_DIR/public_url.txt"
TUNNEL_PROVIDER_FILE="$RUNTIME_DIR/tunnel_provider.txt"
SPAWN_HELPER="$ROOT_DIR/scripts/spawn_detached.py"

extract_tunnel_url() {
  grep -Eo 'https://[a-zA-Z0-9.-]+\.(lhr\.life|localhost\.run|loca\.lt)' "$TUNNEL_LOG" \
    | grep -v 'admin\.localhost\.run\|localhost\.run/docs' \
    | tail -n 1 \
    || true
}

verify_public_url() {
  local url="$1"
  [[ -n "$url" ]] || return 1
  curl --max-time 10 -s "${url%/}/readyz" | grep -q '"status":"ok"'
}

stop_tunnel_only() {
  if [[ -f "$TUNNEL_PID_FILE" ]]; then
    kill "$(cat "$TUNNEL_PID_FILE")" >/dev/null 2>&1 || true
    rm -f "$TUNNEL_PID_FILE"
  fi
}

start_tunnel() {
  local provider="$1"
  : >"$TUNNEL_LOG"
  if [[ "$provider" == "localhost.run" ]]; then
    python3 "$SPAWN_HELPER" --cwd "$ROOT_DIR" --log "$TUNNEL_LOG" -- \
      ssh -tt -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R 80:127.0.0.1:8000 nokey@localhost.run
    return
  fi

  python3 "$SPAWN_HELPER" --cwd "$ROOT_DIR" --log "$TUNNEL_LOG" -- \
    npx --yes localtunnel --port 8000
}

mkdir -p "$RUNTIME_DIR"
rm -f "$PUBLIC_URL_FILE"
rm -f "$TUNNEL_PROVIDER_FILE"

"$ROOT_DIR/scripts/stop_public_app.sh" >/dev/null 2>&1 || true

"$ROOT_DIR/scripts/prod_preflight.sh" >/dev/null

cd "$ROOT_DIR/backend"
BACKEND_PID="$(python3 "$SPAWN_HELPER" --cwd "$ROOT_DIR/backend" --log "$BACKEND_LOG" -- .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000)"
echo "$BACKEND_PID" >"$BACKEND_PID_FILE"

for _ in $(seq 1 30); do
  if curl --max-time 2 -s http://127.0.0.1:8000/api/settings >/dev/null; then
    break
  fi
  sleep 1
done

if ! curl --max-time 2 -s http://127.0.0.1:8000/api/settings >/dev/null; then
  echo "Backend failed to start. See $BACKEND_LOG" >&2
  exit 1
fi

ROOT_HTML="$(curl -sS http://127.0.0.1:8000/)"
if ! echo "$ROOT_HTML" | grep -q '<div id="root"></div>'; then
  echo "Frontend index was not served correctly. See $BACKEND_LOG" >&2
  exit 1
fi

cd "$ROOT_DIR"
TUNNEL_URL=""
TUNNEL_PROVIDER=""

for candidate in "localhost.run" "localtunnel"; do
  TUNNEL_PID="$(start_tunnel "$candidate")"
  echo "$TUNNEL_PID" >"$TUNNEL_PID_FILE"

  for _ in $(seq 1 40); do
    TUNNEL_URL="$(extract_tunnel_url)"
    if verify_public_url "$TUNNEL_URL"; then
      TUNNEL_PROVIDER="$candidate"
      break
    fi
    sleep 1
  done

  if [[ -n "$TUNNEL_PROVIDER" ]]; then
    break
  fi

  stop_tunnel_only
done

if [[ -n "$TUNNEL_URL" ]]; then
  echo "$TUNNEL_URL" >"$PUBLIC_URL_FILE"
fi

if [[ -n "$TUNNEL_PROVIDER" ]]; then
  echo "$TUNNEL_PROVIDER" >"$TUNNEL_PROVIDER_FILE"
else
  "$ROOT_DIR/scripts/stop_public_app.sh" >/dev/null 2>&1 || true
  echo "Public tunnel verification failed. See $TUNNEL_LOG" >&2
  exit 1
fi

echo "backend_pid=$(cat "$BACKEND_PID_FILE")"
echo "tunnel_pid=$(cat "$TUNNEL_PID_FILE")"
echo "tunnel_provider=$TUNNEL_PROVIDER"
echo "public_url=${TUNNEL_URL:-pending}"
