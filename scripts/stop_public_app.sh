#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime"

for pid_file in "$RUNTIME_DIR/backend.pid" "$RUNTIME_DIR/tunnel.pid"; do
  if [[ -f "$pid_file" ]]; then
    pid="$(cat "$pid_file")"
    kill "$pid" >/dev/null 2>&1 || true
    rm -f "$pid_file"
  fi
done

rm -f "$RUNTIME_DIR/public_url.txt" "$RUNTIME_DIR/tunnel_provider.txt"
