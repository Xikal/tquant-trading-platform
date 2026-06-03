# Performance Next Round Acceptance

Generated at: 2026-06-03 Asia/Shanghai

## Source

- Plan: `docs/superpowers/plans/2026-06-03-performance-next-round-final-development-plan.md`
- Baseline report: `docs/reports/performance-next-round-baseline-2026-06-03.md`
- Local head before deployment: `c61723b6`

## Completed Changes

1. BFF partial warnings now carry bounded `source`, `reason`, `status_code`, `timeout_ms`, `fallback_source`, and `message` fields across Python BFF and Go BFF.
2. BFF partial metrics now expose source/reason attribution while preserving the existing reason-only counters.
3. Go market-read and Python quote-cache coverage now report bounded unresolved symbol reasons and preserve legacy symbol samples.
4. `scan_worker_accept` measurement now treats `accepted`, `queued`, `busy`, `duplicate`, and `fallback_available` as non-fatal states, and only marks real failure states as failures.
5. Hot read paths now batch quote overlay reads with `get_many_json_cache`/`read_local_quote_snapshots`, preserving item ordering and ranking fields.
6. Frontend AntD controls were split further into check/switch/radio/value chunks, and the single-chunk budget was tightened to `110KB` gzip.
7. 24M data-prep spike now attempts real daily-bar input loading, explicitly reports `blocked`/`no_data`, and keeps fixture parity as a fallback only.

## Local Validation

| Command | Result |
| --- | --- |
| `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q` | `1210 passed, 1 warning` |
| `cd frontend && npm run api:check` | passed |
| `cd frontend && npm run lint` | passed |
| `cd frontend && npm test -- --run` | `60 files / 175 tests passed` |
| `cd frontend && npm run build` | passed |
| `cd frontend && npm run analyze` | passed |

Known local warning: `urllib3` reports LibreSSL/OpenSSL compatibility during Python commands. This is the existing import-time environment warning and did not fail tests.

## Frontend Bundle

| Metric | Baseline | Final Local | Delta |
| --- | ---: | ---: | ---: |
| max chunk gzip | 126.46KB | 105.42KB | -16.64% |
| first_screen gzip | 319.95KB | 319.43KB | -0.16% |
| total gzip | 797.06KB | 798.99KB | +0.24% |

Top local chunks after Task 5:

| Chunk | gzip KB |
| --- | ---: |
| `antd-check-controls-DCGRb4dV.js` | 105.42 |
| `antd-core-BzAQGpzi.js` | 104.18 |
| `echarts-charts-CK4dBMWO.js` | 99.75 |
| `echarts-components-DpCUDnhF.js` | 89.55 |
| `antd-display-DFSPjeSv.js` | 54.18 |

Budget result: `first_screen_js_gzip_kb=319.43`, `total_gzip_kb=798.99`, largest bundle-report chunk `105.42KB`; all pass the tightened budget.

## 24M Spike

Command:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/backtest_24m_precompute_spike.py --count 240
```

Result:

- Real daily-bar path: `blocked`
- Reason: `database_unavailable:OperationalError`
- Executed fallback source: `fixture`
- `portfolio_backtest_metrics` remains the final executor.
- `productionized=false`
- max5 parity: `true`
- max10 parity: `true`
- all parity fields: `true`

Fixture parity snapshot:

| Metric | baseline max5 | precompute max5 |
| --- | ---: | ---: |
| profit_factor | 2.5163 | 2.5163 |
| avg_trade_return_pct | 1.0633 | 1.0633 |
| portfolio_return_pct | 28.8896 | 28.8896 |
| max_drawdown_pct | -1.0952 | -1.0952 |
| trade_count | 120 | 120 |
| candidate_count | 240 | 240 |

This is not recommended for productionization because the real-data path was locally blocked and the fallback result is fixture-only.

## Online Acceptance

Pending deployment and two cloud validation runs.

## Metric Deltas

Local frontend deltas are recorded above. Online p95 and warning deltas will be filled after deployment.

## Risks And Follow-ups

- Local real 24M daily-bar prep could not run because the configured local MySQL endpoint was unavailable; the script reports this as `blocked` instead of treating fixture data as real.
- `priority_board` and `monitor_bff` success thresholds must be confirmed online after deployment; local tests prove behavior and ordering invariants, not cloud p95.
- `total_gzip_kb` increased by `1.93KB`, within the plan limit of `+5KB`.

## Rollback

- Revert the deployment commit range from `45b26f50` through the final acceptance commit.
- Frontend chunk rollback is limited to `frontend/vite.config.*` and bundle budget scripts.
- Backend observability/read-path rollback is limited to BFF partial attribution, market-read unresolved samples, scan-worker status parsing, read-model quote batching, and the non-production 24M spike script.

## Production Ranking Impact

No production ranking impact. This round did not modify `strategy_policy`, did not create or wire `production_score`, did not replace low-buy, priority board, front-row weighted, or any production sorting, and did not change strategy scoring formulas, selection rules, position rules, or backtest portfolio constraints.
