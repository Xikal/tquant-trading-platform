# Performance Next Round Acceptance

Generated at: 2026-06-03 Asia/Shanghai

## Source

- Plan: `docs/superpowers/plans/2026-06-03-performance-next-round-final-development-plan.md`
- Baseline report: `docs/reports/performance-next-round-baseline-2026-06-03.md`
- Local head before deployment: `c61723b6`
- Deployed head: `eb8121de`
- GitHub Actions run: `26887176708`

## Completed Changes

1. BFF partial warnings now carry bounded `source`, `reason`, `status_code`, `timeout_ms`, `fallback_source`, and `message` fields across Python BFF and Go BFF.
2. BFF partial metrics now expose source/reason attribution while preserving the existing reason-only counters.
3. Go market-read and Python quote-cache coverage now report bounded unresolved symbol reasons and preserve legacy symbol samples.
4. `scan_worker_accept` measurement now treats `accepted`, `queued`, `busy`, `duplicate`, and `fallback_available` as non-fatal states, and only marks real failure states as failures.
5. Hot read paths now batch quote overlay reads with `get_many_json_cache`/`read_local_quote_snapshots`, preserving item ordering and ranking fields.
6. Frontend AntD controls were split further into check/switch/radio/value chunks, and the single-chunk budget was tightened to `110KB` gzip.
7. 24M data-prep spike now attempts real daily-bar input loading, explicitly reports `blocked`/`no_data`, and keeps fixture parity as a fallback only.
8. Deployment scripts now dump container diagnostics when health checks fail and `quick_cloud_deploy.sh --performance-verify` runs two sampled online validation rounds by default.

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

Deployment completed successfully:

| Job | Result |
| --- | --- |
| GitHub Actions run `26887176708` | success |
| `frontend` | success, 1m56s |
| `backend` | success, 3m57s |
| `go-rust` | success, 3m40s |
| `deploy` | success, 11m29s |

Post-deploy cloud validation ran twice with `python3 scripts/measure_cloud_go_rust_performance.py --samples 8`.

| Report | Result | Failures |
| --- | --- | --- |
| `docs/reports/gupiao-cloud-performance-2026-06-03-213141.json` | `ok=true` | `[]` |
| `docs/reports/gupiao-cloud-performance-2026-06-03-223954.json` | `ok=true` | `[]` |

Online p95 results:

| Metric | Baseline | Round 1 | Round 2 | Best Delta | Round 2 Delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| `monitor_bff` p95 | 34.103ms | 16.345ms | 301.181ms | -52.07% | +783.15% |
| `market_pulse` p95 | 20.250ms | 13.715ms | 316.477ms | -32.27% | +1462.85% |
| `priority_board` p95 | 56.168ms | 63.237ms | 211.840ms | +12.59% | +277.18% |
| `watchlist_signals` p95 | 22.227ms | 22.891ms | 167.464ms | +2.99% | +653.42% |
| `scan_worker_accept` p95 | 270.605ms | 157.386ms | 210.629ms | -41.84% | -25.16% |

Coverage and fallback checks:

| Check | Round 1 | Round 2 | Verdict |
| --- | ---: | ---: | --- |
| Quote cache coverage | 10000 bps | 10000 bps | pass |
| Go market-read sample missing | 0/20 | 0/20 | pass |
| `scan_worker_accept` statuses | `[202]` | `[202]` | pass |
| Rust finance math available | true | true | pass |
| Rust migrated function hits | 6 | 6 | pass |

Observability counters remained classified but still show upstream/cache warnings:

| Warning | Round 1 | Round 2 |
| --- | ---: | ---: |
| BFF partial timeout | 2 | 6 |
| BFF partial status | 1 | 1 |
| BFF partial classified | 3/3 | 7/7 |
| Go market-read unresolved misses | 4 | 90 |
| Go market-read fallbacks | 1 | 46 |

Success-standard verdict:

| Standard | Result |
| --- | --- |
| quote cache coverage stays `10000 bps` | pass |
| Go market-read small sample missing `0` | pass |
| `scan_worker_accept` has no true failure state in two rounds | pass |
| `priority_board` p95 `<40ms` | not met online |
| `monitor_bff` p95 `<30ms` | met in round 1, not met in round 2 |
| max frontend chunk `<110KB` gzip | pass |
| all tests pass | pass |
| deploy job success | pass |
| no production ranking impact | pass |

## Metric Deltas

Frontend bundle deltas are recorded above. Online runtime deltas are mixed: first round confirmed faster `monitor_bff`, `market_pulse`, and `scan_worker_accept`; second round had cloud/runtime jitter and did not satisfy the strict p95 targets for hot read endpoints. The measurement script still returned `ok=true` because project gates use the broader Level 3 threshold and true-failure checks rather than strict cloud p95 as a CI blocker.

Overall confirmed improvements:

- max chunk gzip: `126.46KB -> 105.42KB`, down `16.64%`.
- `scan_worker_accept` p95: `270.605ms -> 157.386ms` best round, down `41.84%`; second round still down `25.16%`.
- quote cache coverage: stayed at `10000 bps` across deployment and both validation rounds.
- Go market-read sample missing: stayed `0/20` in both validation rounds.
- BFF partial warnings are now classified (`3/3`, `7/7`) instead of un-attributed.

## Risks And Follow-ups

- Local real 24M daily-bar prep could not run because the configured local MySQL endpoint was unavailable; the script reports this as `blocked` instead of treating fixture data as real.
- Strict cloud p95 targets are not stable yet: `priority_board <40ms` was not met, and `monitor_bff <30ms` was not sustained across both rounds.
- Go market-read unresolved/fallback counters increased in the second round while sample coverage remained complete. This needs a follow-up focused on cache warmup durability and unresolved reason reduction.
- BFF partial timeout/status warnings remain classified but non-zero. This needs a follow-up focused on the slow Python source behind partial responses.
- `total_gzip_kb` increased by `1.93KB`, within the plan limit of `+5KB`.

## Rollback

- Revert deployment commit range through `eb8121de`, or redeploy the previous successful release backup from the cloud host if an operational regression appears.
- Frontend chunk rollback is limited to `frontend/vite.config.*` and bundle budget scripts.
- Backend observability/read-path rollback is limited to BFF partial attribution, market-read unresolved samples, scan-worker status parsing, read-model quote batching, runtime fallback hardening, deployment diagnostics, and the non-production 24M spike script.

## Production Ranking Impact

No production ranking impact. This round did not modify `strategy_policy`, did not create or wire `production_score`, did not replace low-buy, priority board, front-row weighted, or any production sorting, and did not change strategy scoring formulas, selection rules, position rules, or backtest portfolio constraints.
