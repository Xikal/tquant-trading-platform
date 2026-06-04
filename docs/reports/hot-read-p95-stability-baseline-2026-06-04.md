# Hot Read P95 Stability Baseline

Generated at: 2026-06-04 Asia/Shanghai

## Source

- Command: `python3 scripts/measure_cloud_go_rust_performance.py --samples 8 || true`
- JSON: `docs/reports/gupiao-cloud-performance-2026-06-04-091743.json`
- Result: `ok=false`

## Metrics

| Metric | Value |
| --- | ---: |
| quote cache coverage bps | `10000` |
| quote cache requested/cached | `1057/1057` |
| Go market-read checked/returned/missing | `20/20/0` |
| monitor_bff p50/p95 | `117.309ms / 632.379ms` |
| market_pulse p50/p95 | `80.917ms / 123.733ms` |
| priority_board p50/p95 | `272.200ms / 347.882ms` |
| watchlist_signals p50/p95 | `69.823ms / 252.322ms` |
| scan_worker_accept p50/p95 | `413.374ms / 519.451ms` |
| scan_worker_accept statuses | `[202]` |
| BFF partial classified | `149/149` |
| BFF partial timeout/status/decode/other | `147/2/0/0` |
| Go market-read cache misses | `39142` |
| Go market-read MySQL fallbacks | `36873` |
| Go market-read unresolved/fallback | `2269/606` |

## Failure Or Blocked Reason

- The command generated a complete report but returned `ok=false`.
- Threshold failures:
  - `monitor_bff` p95 was `632.379ms`, above the script threshold `500ms` and the plan target `<30ms`.
  - `scan_worker_accept` p95 was `519.451ms`, above the script threshold `500ms`.
- `priority_board` p95 was `347.882ms`, above the plan target `<40ms`.
- Quote cache coverage was healthy: `10000 bps`, `1057/1057` readable after warmup.
- Go market-read sample was healthy for the sampled demand set: `20/20`, missing `0`.
- Observability warnings remained high:
  - BFF partial source timeouts: `147`
  - Go market-read unresolved misses: `2269`
  - Go market-read fallbacks: `606`

## Initial Interpretation

- The current regression is concentrated in hot-read p95 and warning counters, not in quote cache coverage.
- BFF partial warnings are fully classified but still too frequent. The largest classified timeout sources are `market_breadth`, `sector_relative_strength`, `paired_hedge`, `market_pulse`, `monitor_snapshot`, and `monitor_review`.
- Go market-read still reports unresolved sample reasons as `not_in_cache`; the next tasks must make reasons bounded and reduce fallback volume without changing production ranking.
- Redis/cache timeout did not fail this baseline run, but the immediately prior online sampling file `docs/reports/gupiao-cloud-performance-2026-06-04-085113.json` failed with remote protocol disconnect plus Redis socket read timeout. Task 1 remains required.

## Production Boundary

- No strategy rule, production ranking, `strategy_policy`, or `production_score` change was made in this baseline step.
- Live quote overlay remains display-only and must not affect sorting fields.
