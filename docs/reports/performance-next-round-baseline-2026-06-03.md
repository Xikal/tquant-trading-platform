# Performance Next Round Baseline

Generated at: 2026-06-03 Asia/Shanghai

## Source

- Command: `python3 scripts/measure_cloud_go_rust_performance.py --samples 8`
- JSON: `docs/reports/gupiao-cloud-performance-2026-06-03-184822.json`
- Result: `ok=true`
- Failures: `[]`

## Online Metrics

| Metric | Value |
| --- | ---: |
| quote cache coverage bps | 10000 |
| quote cache requested/cached | 1050/1050 |
| Go market-read checked/returned/missing | 20/20/0 |
| Go market-read data_quality | fresh |
| monitor_bff p50/p95 | 11.619ms / 74.002ms |
| market_pulse p50/p95 | 12.140ms / 18.555ms |
| priority_board p50/p95 | 33.766ms / 115.566ms |
| watchlist_signals p50/p95 | 11.097ms / 17.978ms |
| scan_worker_accept p50/p95 | 135.365ms / 163.396ms |
| scan_worker_accept statuses | `[202]` |

## Warnings

- BFF partial timeout: 30
- BFF partial status: 3
- BFF partial decode: 0
- Go market-read unresolved misses: 81
- Go market-read fallbacks: 26
- Go market-read partials: 2
- Go market-read cache misses: 21160
- Go market-read MySQL fallbacks: 21079

## Blocked Or No Data

- No blocked/no_data items in the baseline command itself; the report returned `ok=true`.
- The raw JSON file is ignored by `.gitignore` (`docs/reports/*-performance-*.json`) and is kept locally as machine evidence. This Markdown report records the human-readable baseline for version control.

## Initial Interpretation

- Quote cache coverage remains healthy at 100%, and the Go market-read warmup sample returned 20/20 with no missing symbols.
- The current weak points are warning attribution and historical/new counter growth:
  - BFF partial failures are classified by reason but not yet sufficiently attributable by source in the human report.
  - Go market-read counters show high Redis miss/MySQL fallback volume and 81 unresolved misses despite the warmup sample passing.
- `priority_board` p95 is currently 115.566ms, above the target `<40ms`.
- `monitor_bff` p95 is currently 74.002ms, above the target `<30ms`.
- `scan_worker_accept` is currently stable for this run with status `[202]` and p95 163.396ms.

## Production Boundary

- No strategy rule, production ranking, `strategy_policy`, or `production_score` change was made in this baseline step.
