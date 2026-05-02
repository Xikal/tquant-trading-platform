#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT_DIR/.runtime/mysql/mysql.pid"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  kill "$PID" >/dev/null 2>&1 || true
  rm -f "$PID_FILE"
  echo "stopped mysql pid=$PID"
else
  echo "mysql not running"
fi
