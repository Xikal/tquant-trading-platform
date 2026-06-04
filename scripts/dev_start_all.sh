#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export DATABASE_URL="${DATABASE_URL:-sqlite:///./data/t_quant.db}"
export RUNTIME_BACKGROUND_JOBS_ENABLED="${RUNTIME_BACKGROUND_JOBS_ENABLED:-false}"

trap 'kill 0' EXIT

./scripts/run_platform_component.sh web &
./scripts/run_platform_component.sh runtime-worker &

wait
