#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DRY_RUN=1
CLEAN_PYCACHE=0
CLEAN_FRONTEND_DIST=0

usage() {
  cat <<'EOF'
Usage: scripts/clean_local_artifacts.sh [--pycache] [--frontend-next-dist] [--apply]

Local-only cleanup. Default is dry-run.

Options:
  --pycache        Remove Python __pycache__ directories and *.pyc files.
  --frontend-next-dist
                   Remove frontend-next/dist.
  --apply          Actually remove files. Without this flag, only prints targets.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pycache)
      CLEAN_PYCACHE=1
      shift
      ;;
    --frontend-next-dist|--frontend-dist)
      CLEAN_FRONTEND_DIST=1
      shift
      ;;
    --apply)
      DRY_RUN=0
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf 'unknown option: %s\n' "$1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ "$CLEAN_PYCACHE" != "1" && "$CLEAN_FRONTEND_DIST" != "1" ]]; then
  usage
  exit 2
fi

remove_path() {
  local target="$1"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %s\n' "$target"
  else
    rm -rf "$target"
    printf '[removed] %s\n' "$target"
  fi
}

if [[ "$CLEAN_PYCACHE" == "1" ]]; then
  while IFS= read -r path; do
    remove_path "$path"
  done < <(find "$ROOT_DIR/backend/app" "$ROOT_DIR/backend/tests" "$ROOT_DIR/backend/scripts" "$ROOT_DIR/scripts" \( -name '__pycache__' -o -name '*.pyc' \) 2>/dev/null | sort)
fi

if [[ "$CLEAN_FRONTEND_DIST" == "1" && -d "$ROOT_DIR/frontend-next/dist" ]]; then
  remove_path "$ROOT_DIR/frontend-next/dist"
fi
