# TQuant Go Services

This directory contains production-ready Go sidecar services for read-heavy
backend paths. They are enabled through explicit runtime URLs and internal
service tokens, with Python fallbacks preserved for rollback.

## Services

- `bff-gateway`: read-only BFF gateway. It can aggregate workspace reads and
  proxy to the Python BFF with `X-TQuant-Bff-Hop=1`.
- `market-read-service`: read-only market snapshot service. It reads the Redis
  local quote cache written by Python and can return quote batches, sector
  relative strength, and intraday key levels without calling external data
  providers.
- `scan-worker`: production scan orchestrator. It owns the scheduled scan entry
  point, calls the Python strategy reference through an internal endpoint, and
  only publishes latest snapshots when the reference write succeeds.

## Safety Rules

- Go scan-worker is the production entry point for scheduled low-buy scans.
  Python remains the business-rule fallback/reference behind the internal call.
- Internal calls must use `X-Internal-Service-Token` in production.
- Python remains the fallback path.

## Acceptance

Run the reusable gate before enabling or changing the services:

```bash
python scripts/verify_go_rust_performance_acceptance.py
```

The script runs Go tests for all services, Rust tests, and a Python/Rust seam
performance budget, then writes
`docs/reports/go-rust-performance-acceptance-2026-05-25.json`.
