# Platform Hot Read Performance - 2026-06-05

## Baseline

- Source: `docs/reports/gupiao-cloud-performance-2026-06-04-235739.json`
- `monitor_bff`: p95 `1171.832ms`, target `<500ms`, ideal `<300ms`
- `priority_board`: p95 `876.476ms`, target `<500ms`, ideal `<250ms`
- BFF partial timeout: `5`
- market-read unresolved: `8`
- market-read fallback: `2`

## Local Changes

- Go BFF workspace monitor now reports per-source timings through `source_timings`.
- Go BFF cache now supports fresh TTL plus stale TTL. Monitor stale cache hits return immediately with `stale=true`, `refresh_queued=true`, `stale_reason=go_bff_stale_cache_background_refresh`, while a background refresh updates the cache.
- Python BFF partial errors now include `elapsed_ms`, and monitor workspace includes `source_timings`.
- Priority board Web route downgrades normal `refresh=sync` requests to `async`; only admin plus `PRIORITY_BOARD_WEB_SYNC_REFRESH_ENABLED=true` can run sync refresh.
- Priority board read model/cache responses expose `read_path`, `stale`, `stale_reason`, and `refresh_queued`.
- Priority board live quote overlay has a bounded default budget of `80ms`; timeout returns the stable read model payload without changing order.
- Daily bar refresh success explicitly queues `low_buy_materialization_refresh` for priority board/read model rebuild.
- Market quote warmup demand now includes core index/ETF proxies used by market pulse and sector screens.
- Cloud performance measurement now reports:
  - `monitor_bff_sources`
  - `priority_board_breakdown`
  - `go_bff_cache_hit_rate`
  - `go_bff_partial_errors_by_source`
  - `go_bff_metrics_delta`
  - `go_market_metrics_delta`

## Local Verification

- `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_cloud_performance_script.py -q`
- `cd go-services/bff-gateway && go test ./...`
- `cd go-services/market-read-service && go test ./...`
- `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_runtime_task_queue.py backend/tests/test_runtime_task_contracts.py -q`
- `git diff --check`
- `cd frontend && npm run api:check`
- `cd frontend && npm run lint`
- `cd frontend && npm test -- --run src/state/serverQueries/monitor.test.ts`
- `cd frontend && npm run build`

## Deployment Status

- Deployed to `43.143.243.97` with:
  - `./scripts/one_click_cloud_deploy.sh --scope all --host 43.143.243.97 --key /Users/j/Downloads/gupiao.pem`
- Remote services verified healthy:
  - `tquant-app-mysql`
  - `tquant-go-bff-gateway`
  - `tquant-go-market-read-service`
  - runtime scheduler/worker, analytics worker, backtest worker
- Not pushed.

## Online Acceptance

Command, twice:

```bash
python3 scripts/measure_cloud_go_rust_performance.py --samples 8
python3 scripts/measure_cloud_go_rust_performance.py --samples 8
```

| Report | ok | failures | monitor_bff p95 | priority_board p95 | BFF timeout | BFF partial | market unresolved | market fallback | quote_missing | coverage |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `docs/reports/gupiao-cloud-performance-2026-06-05-012124.json` | true | `[]` | `193.362ms` | `163.228ms` | `0` | `0` | `0` | `0` | `0` | `10000bps` |
| `docs/reports/gupiao-cloud-performance-2026-06-05-012235.json` | true | `[]` | `20.531ms` | `103.539ms` | `0` | `0` | `0` | `0` | `0` | `10000bps` |

Result:

- `monitor_bff` target `<500ms` met; ideal `<300ms` met in both rounds.
- `priority_board` target `<500ms` met; ideal `<250ms` met in both rounds.
- BFF timeout cleared.
- market-read unresolved/fallback warnings cleared during both sampling windows.

## Boundaries

- `backend/app/services/low_buy/strategy_policy.py` was not modified.
- Production low-buy / priority_board / front-row weighted / strategy tracking sorting was not replaced.
- Strategy Engine remains Shadow.
- Execution Model remains Preview.
- DuckDB/Parquet remains analysis/reporting only.
- Web requests do not synchronously run heavy priority board rebuilds.
