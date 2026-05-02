#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"

echo "[healthz]"
curl -sS "${BASE_URL%/}/healthz"
printf "\n\n[readyz]\n"
curl -sS "${BASE_URL%/}/readyz"
printf "\n\n[runtime]\n"
curl -sS "${BASE_URL%/}/api/settings/runtime"
printf "\n"
