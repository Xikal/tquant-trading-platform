#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"

AUTH_HEADERS=()
if [[ -n "${RUNTIME_SNAPSHOT_AUTH_TOKEN:-}" ]]; then
  AUTH_HEADERS+=(-H "Authorization: Bearer ${RUNTIME_SNAPSHOT_AUTH_TOKEN}")
fi
if [[ -n "${ADMIN_API_TOKEN:-}" ]]; then
  AUTH_HEADERS+=(-H "X-Admin-Token: ${ADMIN_API_TOKEN}")
fi

echo "[healthz]"
curl -sS "${BASE_URL%/}/healthz"
printf "\n\n[readyz]\n"
curl -sS "${BASE_URL%/}/readyz"
printf "\n\n[runtime]\n"
if [[ ${#AUTH_HEADERS[@]} -eq 0 ]]; then
  echo "runtime skipped: set ADMIN_API_TOKEN or RUNTIME_SNAPSHOT_AUTH_TOKEN for protected runtime settings"
else
  curl -sS "${AUTH_HEADERS[@]}" "${BASE_URL%/}/api/settings/runtime"
fi
printf "\n"
