#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/5] Python compile"
backend/.venv/bin/python -m compileall backend/app backend/tests/test_backend_refactor_foundation.py backend/tests/test_bff_routes.py -q

echo "[2/5] Python tests"
(cd backend && .venv/bin/python -m pytest \
  tests/test_backend_refactor_foundation.py \
  tests/test_finance_performance_math.py \
  tests/test_bff_routes.py \
  tests/test_security_headers.py \
  tests/test_performance_regression.py \
  -q)

echo "[3/5] Docker compose config"
if command -v docker >/dev/null 2>&1; then
  docker compose -f docker-compose.mysql.yml config --quiet
else
  echo "skip: docker not installed"
  backend/.venv/bin/python - <<'PY'
import yaml
from pathlib import Path

with Path("docker-compose.mysql.yml").open() as handle:
    payload = yaml.safe_load(handle)
services = payload.get("services", {})
required = {"app", "runtime-worker", "backtest-worker", "mysql", "redis", "go-bff-gateway"}
missing = sorted(required - set(services))
if missing:
    raise SystemExit(f"docker-compose.mysql.yml missing services: {missing}")
print(f"compose yaml parsed services={len(services)}")
PY
fi

echo "[4/5] Go services"
if command -v go >/dev/null 2>&1; then
  (cd go-services/bff-gateway && go test ./...)
  (cd go-services/market-read-service && go test ./...)
  (cd go-services/scan-worker && go test ./...)
else
  echo "skip: go not installed"
fi

echo "[5/5] Rust optional crate"
if command -v cargo >/dev/null 2>&1; then
  (cd rust/tquant-rs && PYO3_PYTHON="${PYO3_PYTHON:-$(command -v python3)}" PYO3_USE_ABI3_FORWARD_COMPATIBILITY="${PYO3_USE_ABI3_FORWARD_COMPATIBILITY:-1}" cargo test)
else
  echo "skip: cargo not installed"
fi

echo "backend refactor foundation verification completed"
