# Hot Read P95 Stability Acceptance

Generated at: 2026-06-04 Asia/Shanghai

## Completed Tasks

- Task 1: Redis cache fail-open and measurement retry.
- Task 2: Priority board stable read model cache.
- Task 3: Monitor BFF source timeout budgets and partial degradation.
- Task 4: Quote cache demand warmup and Go market-read reason reduction.

## Local Validation

| Command | Result |
| --- | --- |
| `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q` | `1246 passed, 1 warning` |
| `cd frontend && npm run api:check` | pass; OpenAPI hash `29ed1b0d0b2c4041d56713f9b4894da633a94b46012df687d57d851b3911e8c0` |
| `cd frontend && npm run lint` | pass; bundle budget check pass |
| `cd frontend && npm test -- --run` | pass; `61 files / 179 tests` |
| `cd frontend && npm run build` | pass |
| `cd frontend && npm run analyze` | pass; largest gzip chunk `105.42KB`, first-screen gzip `319.57KB`, total gzip `800.63KB` |
| `git diff --check` | pass |

Vitest prints the expected state-separation negative fixture text for `badStore.ts`; the command exits `0` and all tests pass.

## Local Bundle Metrics

| Metric | Value |
| --- | ---: |
| largest gzip chunk | `105.42KB` |
| first_screen_js_gzip_kb | `319.57KB` |
| total_gzip_kb | `800.63KB` |

Top chunks:

| Chunk | Gzip KB |
| --- | ---: |
| `antd-check-controls-DCGRb4dV.js` | `105.42` |
| `antd-core-BzAQGpzi.js` | `104.18` |
| `echarts-charts-CK4dBMWO.js` | `99.75` |
| `echarts-components-DpCUDnhF.js` | `89.55` |
| `antd-display-DFSPjeSv.js` | `54.18` |

## Implementation Notes

- Redis/distributed cache read and write timeouts now fail open by default and emit bounded cache-operation metrics.
- Online performance measurement retries transient remote protocol/cache timeout failures once and preserves retry evidence.
- Priority board stable read model cache is keyed by date, variant, cache key, and user filter hash; cached payload validates through the existing response schema and does not mutate ranking fields.
- Monitor BFF now applies source-level budgets to noncritical review/hourly sources, returns shaped defaults, and reports `partial_errors` by bounded source and reason.
- Frontend monitor refresh preserves main BFF data and surfaces partial warnings through the existing notice path.
- Quote cache warmup now builds a deterministic hot demand set from priority board, monitor board, watchlist, paper positions, strategy tracking, and hot sector members through runtime-worker owned refresh tasks.
- Go market-read unresolved samples and metrics now use bounded reasons: `not_in_demand_set`, `cache_write_failed`, `cache_read_miss`, `mysql_fallback_missing`, `stale_quote`, and `schema_mismatch`.

## Production Boundary

- No `strategy_policy` change.
- No `production_score` creation or replacement.
- No production ranking replacement.
- No low-buy, priority board, front-row weighted, or existing production sorting replacement.
- Live quote overlay remains display-only and does not affect `priority_score`, `production_score`, `buy_signal_state`, or `elite_watch_score`.
- Quote warmup runs through runtime-worker/runtime-scheduler paths; no Web background loop was added.

## Online Deployment

| Item | Result |
| --- | --- |
| GitHub Actions run | pending Task 6 |
| deploy job | pending Task 6 |
| deployed head | pending Task 6 |

## Online Acceptance

| Metric | Baseline | Round 1 | Round 2 | Verdict |
| --- | ---: | ---: | ---: | --- |
| quote cache coverage bps | `10000` | pending | pending | pending |
| Go market-read missing | `0` | pending | pending | pending |
| monitor_bff p95 | `632.379ms` | pending | pending | pending |
| priority_board p95 | `347.882ms` | pending | pending | pending |
| scan_worker_accept statuses | `[202]` | pending | pending | pending |
| BFF partial warnings | `149` | pending | pending | pending |
| Go unresolved/fallback | `2269/606` | pending | pending | pending |

## Success Criteria

- `priority_board` p95 stable `<40ms`: pending online validation.
- `monitor_bff` p95 stable `<30ms`: pending online validation.
- quote cache coverage `10000 bps`: pending online validation.
- Go market-read missing `0`: pending online validation.
- Redis/cache timeout does not fail whole run: pending online validation.
- frontend largest gzip chunk `<110KB`: pass locally.
- deploy job success: pending Task 6.

## Remaining Risks

- Online p95 targets depend on deployed cache warmup state and cloud runtime load; Task 6 must use two fresh cloud acceptance rounds before final verdict.
- There is one unrelated untracked file not part of this plan: `docs/superpowers/plans/2026-06-04-monitor-priority-board-latency-online-remediation.md`.

## Rollback

- Set `DISTRIBUTED_CACHE_FAIL_OPEN_ENABLED=false` to restore strict cache errors.
- Set `PRIORITY_BOARD_STABLE_READ_MODEL_ENABLED=false` to bypass stable read model cache.
- Set `MONITOR_BFF_SOURCE_BUDGET_ENABLED=false` to restore previous BFF source behavior.
- Set `QUOTE_CACHE_DEMAND_WARMUP_ENABLED=false` to restore previous quote warmup scope.
- Redeploy previous successful commit if a production regression appears.
