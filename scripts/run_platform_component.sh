#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: scripts/run_platform_component.sh <component> [--print-command] [component args]

Components:
  web               FastAPI/Gunicorn-compatible local Web process
  runtime-worker    RuntimeTask worker for refresh/materialization jobs
  analytics-worker  Analytics RuntimeTask worker with DuckDB/Parquet dependency check
  backtest-worker   On-demand backtest DB worker
  scheduler         Runtime scheduler process

This is a local process entrypoint. Production uses docker-compose.mysql.yml
services with the same component names.
EOF
}

component="${1:-}"
if [[ -z "$component" || "$component" == "--help" || "$component" == "-h" ]]; then
  usage
  exit 0
fi
shift

PRINT_COMMAND=0
if [[ "${1:-}" == "--print-command" ]]; then
  PRINT_COMMAND=1
  shift
fi

print_or_run() {
  local command_text="$1"
  shift
  if [[ "$PRINT_COMMAND" == "1" ]]; then
    printf '%s\n' "$command_text"
    return 0
  fi
  "$@"
}

case "$component" in
  web)
    command_text='cd backend && DATABASE_URL=${DATABASE_URL:-sqlite:///./data/t_quant.db} RUNTIME_BACKGROUND_JOBS_ENABLED=${RUNTIME_BACKGROUND_JOBS_ENABLED:-false} PYTHONPATH=. .venv/bin/python -m uvicorn app.main:app --host ${BACKEND_HOST:-127.0.0.1} --port ${BACKEND_PORT:-8000}'
    if [[ "$PRINT_COMMAND" == "1" ]]; then
      print_or_run "$command_text"
      exit 0
    fi
    cd "$ROOT_DIR/backend"
    export DATABASE_URL="${DATABASE_URL:-sqlite:///./data/t_quant.db}"
    export RUNTIME_BACKGROUND_JOBS_ENABLED="${RUNTIME_BACKGROUND_JOBS_ENABLED:-false}"
    exec .venv/bin/python -m uvicorn app.main:app --host "${BACKEND_HOST:-127.0.0.1}" --port "${BACKEND_PORT:-8000}" "$@"
    ;;
  runtime-worker)
    command_text='cd backend && DATABASE_URL=${DATABASE_URL:-sqlite:///./data/t_quant.db} PYTHONPATH=. .venv/bin/python -m app.workers.runtime_worker'
    if [[ "$PRINT_COMMAND" == "1" ]]; then
      print_or_run "$command_text"
      exit 0
    fi
    cd "$ROOT_DIR/backend"
    export DATABASE_URL="${DATABASE_URL:-sqlite:///./data/t_quant.db}"
    exec .venv/bin/python -m app.workers.runtime_worker "$@"
    ;;
  analytics-worker)
    command_text='DATABASE_URL=${DATABASE_URL:-sqlite:///backend/data/t_quant.db} PYTHONPATH=backend backend/.venv/bin/python backend/scripts/analytics_worker.py'
    if [[ "$PRINT_COMMAND" == "1" ]]; then
      print_or_run "$command_text"
      exit 0
    fi
    cd "$ROOT_DIR"
    export DATABASE_URL="${DATABASE_URL:-sqlite:///backend/data/t_quant.db}"
    export PYTHONPATH="${PYTHONPATH:-backend}"
    exec backend/.venv/bin/python backend/scripts/analytics_worker.py "$@"
    ;;
  backtest-worker)
    command_text='DATABASE_URL=${DATABASE_URL:-sqlite:///backend/data/t_quant.db} PYTHONPATH=backend backend/.venv/bin/python scripts/backtest_worker.py'
    if [[ "$PRINT_COMMAND" == "1" ]]; then
      print_or_run "$command_text"
      exit 0
    fi
    cd "$ROOT_DIR"
    export DATABASE_URL="${DATABASE_URL:-sqlite:///backend/data/t_quant.db}"
    export PYTHONPATH="${PYTHONPATH:-backend}"
    exec backend/.venv/bin/python scripts/backtest_worker.py "$@"
    ;;
  scheduler)
    command_text='cd backend && DATABASE_URL=${DATABASE_URL:-sqlite:///./data/t_quant.db} RUNTIME_BACKGROUND_ROLE=${RUNTIME_BACKGROUND_ROLE:-scheduler} RUNTIME_BACKGROUND_JOBS_ENABLED=${RUNTIME_BACKGROUND_JOBS_ENABLED:-true} PYTHONPATH=. .venv/bin/python -m app.workers.runtime_scheduler'
    if [[ "$PRINT_COMMAND" == "1" ]]; then
      print_or_run "$command_text"
      exit 0
    fi
    cd "$ROOT_DIR/backend"
    export DATABASE_URL="${DATABASE_URL:-sqlite:///./data/t_quant.db}"
    export RUNTIME_BACKGROUND_ROLE="${RUNTIME_BACKGROUND_ROLE:-scheduler}"
    export RUNTIME_BACKGROUND_JOBS_ENABLED="${RUNTIME_BACKGROUND_JOBS_ENABLED:-true}"
    exec .venv/bin/python -m app.workers.runtime_scheduler "$@"
    ;;
  *)
    echo "unknown component: $component" >&2
    usage >&2
    exit 2
    ;;
esac
