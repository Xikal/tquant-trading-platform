# Quote Cache Coverage Optimization And Online Acceptance

Generated at: 2026-06-03 18:32 Asia/Shanghai

## Scope

- Optimized quote cache coverage validation for small-sample and hot-demand checks.
- Deployed commit `90a29c0eb19df53429e290ac5fa2b991b52a67f2` to `main`.
- Ran online acceptance in order after deployment.
- No strategy rule, production ranking, `production_score`, or `strategy_policy` change was introduced by the quote cache work.

## Code Changes

- `backend/app/services/market_quote_cache_refresh.py`
  - Coverage is now measured after write by reading cache back with `read_local_quote_snapshot`.
  - Refresh response now exposes `requested_count`, `cached_count`, and read-back based `missing_count`.
  - Daily-bar fallback still fills missing realtime quotes, but coverage only passes when the final cache is readable.
- `scripts/measure_cloud_go_rust_performance.py`
  - Online acceptance now runs quote cache warmup before hot endpoint p95 sampling.
  - Warmup uses `DEFAULT_LIMIT` instead of the previous small `80` sample.
  - Go market-read validation uses the warmup demand sample first, with liquidity top20 only as fallback.
  - Warmup coverage below target, batch missing symbols, or unavailable quote quality are explicit failures.
- Tests:
  - Added read-back coverage tests for fallback completion and write/read mismatch.
  - Added script guard checks so future changes keep quote cache warmup before API p95 sampling.

## Local Validation

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_market_quote_cache_refresh.py -q`
  - `5 passed, 1 warning`
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_cloud_performance_script.py backend/tests/test_market_quote_cache_refresh.py -q`
  - `9 passed, 1 warning`
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_market_quote_cache_coverage.py backend/tests/test_market_quote_cache_refresh.py backend/tests/test_cloud_performance_script.py -q`
  - `14 passed, 1 warning`
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_market_quote_cache_refresh.py backend/tests/test_cloud_performance_script.py backend/tests/test_performance_regression.py -q`
  - `14 passed, 1 warning`
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q`
  - `1203 passed, 1 warning`
- `python3 scripts/check_backend_perf_budget.py --metrics-file /tmp/tquant-backend-compute-metrics.prom || true`
  - `ok: true`
  - Level 1 Rust fallback ratio: `0 bps`
  - Level 3 local quote coverage sample in `/tmp` remained stale at `0 bps`; this is a non-strict cloud巡检 item and was revalidated online after deployment.
- `git diff --check`
  - passed

## Deployment

- GitHub Actions run: `26877713871`
- Head SHA: `90a29c0eb19df53429e290ac5fa2b991b52a67f2`
- Result: `success`
- Jobs:
  - `backend`: success
  - `frontend`: success
  - `go-rust`: success
  - `deploy`: success
- Deploy completed at: `2026-06-03T10:17:11Z`

## Online Acceptance Order

1. Deployment job completion confirmed.
2. `/readyz` and container health checked.
3. Quote cache warmup and read-back coverage measured.
4. Go market-read small sample checked from warmup demand symbols.
5. Hot endpoint p50/p95 measured.
6. Rust finance smoke and Go scan-worker status checked.
7. Observability warnings reviewed.

## Online Acceptance Results

Final passing report:

- JSON: `docs/reports/gupiao-cloud-performance-2026-06-03-182321.json`
- Overall: `ok: true`
- Failures: `[]`

### Quote Cache Coverage

| Metric | Value |
| --- | ---: |
| warmup requested | 1051 |
| quotes refreshed | 1051 |
| Redis writes | 1051 |
| read-back cached | 1051 |
| warmup missing | 0 |
| coverage bps | 10000 |
| Redis quote keys | 1051 |
| Go market-read symbols checked | 20 |
| Go market-read items returned | 20 |
| Go market-read missing | 0 |
| data_quality | fresh |

Conclusion: quote cache small-sample coverage is now fully covered online. The deployed path proves coverage by post-write read-back, not by quote fetch count alone.

### Hot Endpoint P95

| Endpoint | Status | p50 ms | p95 ms |
| --- | --- | ---: | ---: |
| `/readyz` | `[200]` | 5.000 | 5.557 |
| monitor_bff | `[200]` | 18.099 | 34.103 |
| market_pulse | `[200]` | 16.876 | 20.250 |
| priority_board | `[200]` | 37.393 | 56.168 |
| watchlist_signals | `[200]` | 10.899 | 22.227 |
| scan_worker_accept | `[202]` | 175.466 | 270.605 |

### Rust And Go

- Rust finance math smoke:
  - available: `true`
  - hits: `6`
  - fallbacks: `0`
- Go scan-worker status:
  - `ok: true`
  - `production_readiness: python_reference_orchestrator`
  - `scan_failures_total: 0`
  - ranking consistency: `python_reference_order`

## First Online Run Note

First report:

- JSON: `docs/reports/gupiao-cloud-performance-2026-06-03-181945.json`
- Overall: `ok: false`
- Failure: `scan_worker_accept` had statuses `[202, 500]`, p95 `582.401 ms`.

Quote cache in that same failed run was already healthy:

- warmup requested/cached: `1051/1051`
- coverage bps: `10000`
- Go market-read checked/returned: `20/20`
- missing: `0`
- data_quality: `fresh`

After the first run, container health was checked and all key services were healthy. Three manual scan-worker accept calls returned `202 Accepted`. A second full online acceptance run passed with no failures. The first scan-worker failure is therefore recorded as post-deploy transient noise, not a quote cache coverage failure.

## Observability Warnings

Final passing run still reported warning-level observability items:

- BFF partial timeout count: `2`
- BFF partial status failures: `1`
- Go market-read unresolved misses metric: `9`
- Go market-read fallbacks metric: `3`

These did not block acceptance because:

- quote cache warmup coverage was `100%`;
- Go market-read validation sample had `0` missing symbols;
- all hot endpoints returned 200;
- the script's final `ok` was true.

Follow-up: inspect source-level partial errors and market-read historical fallback counters separately. They are warning-level operational telemetry, not a blocker for this quote cache coverage optimization.

## Production Impact

- No replacement of low-buy, priority board, front-row weighted, or existing production ranking.
- No `production_score` generated.
- No `strategy_policy` modification.
- Live quote overlay and quote cache warmup do not change production ordering.
- Rollback path: revert `90a29c0eb19df53429e290ac5fa2b991b52a67f2` or redeploy the previous release backup if an operational regression appears.
