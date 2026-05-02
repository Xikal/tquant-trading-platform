#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_URL_FILE="$ROOT_DIR/.runtime/mysql/mysql_app_url.txt"

if [[ ! -f "$APP_URL_FILE" ]]; then
  echo "MySQL app URL file not found: $APP_URL_FILE" >&2
  exit 1
fi

APP_URL="$(cat "$APP_URL_FILE")"

"$ROOT_DIR/backend/.venv/bin/python" "$ROOT_DIR/backend/scripts/db_admin.py" migrate \
  --source-url "sqlite:///./backend/data/t_quant.db" \
  --target-url "$APP_URL" \
  --activate
