# MySQL And Core Worker Root-Cause Review

- Time: `2026-06-12 20:44-20:46 CST`
- Server: `ubuntu@43.143.243.97`
- Scope: read-only D6 evidence after D5 gate rejection
- Related gate: `docs/reports/cloud-resource-trading-day-gate-summary-2026-06-12.md`

## Executive Summary

D5 must stay closed. The main current instability is not Web reachability: core
pages and protected API shells respond quickly. The blocking issue is the
background low-buy materialization loop repeatedly failing because production
required strategy snapshots for `2026-06-12` do not exist.

The resource symptom is a worker/queue storm:

- `low_buy_materialization_refresh` failed `1010` times in the last 8 hours.
- The same missing set appears every time:
  `first_board`, `late_session_strong_support`, `volume_shrink`.
- `low_buy.latest_data` is still `pending` even though `daily_bar_count=5211`
  and `post_close_daily_bars_ready=true`.
- Runtime worker reached `99.96%` memory at the 14:55 checkpoint and the kernel
  logged an OOM kill at `15:02 CST`.

## Read-Only Commands

The review used only read operations:

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97
docker stats --no-stream
mysql SHOW GLOBAL STATUS / SHOW VARIABLES / SELECT ...
docker logs --since ...
curl -sS -o /dev/null ...
```

No DB write, Docker restart, env change, cleanup, deployment, or scheduler stop
was executed.

## MySQL Facts

| Metric | Value |
|---|---:|
| Threads_connected | 9 |
| Threads_running | 2 |
| Threads_created | 15 |
| Slow_queries | 118 |
| max_connections | 120 |
| innodb_buffer_pool_size | 536870912 |
| long_query_time | 0.2 |
| slow_query_log | ON |
| Database size | 1524.3 MiB |

Largest tables:

| Table | Size | Rows |
|---|---:|---:|
| daily_bar_snapshots | 866.1 MiB | 2862299 |
| key_level_snapshots | 330.5 MiB | 23538 |
| runtime_tasks | 56.6 MiB | 49721 |
| low_buy_strategy_pool_snapshots | 55.1 MiB | 62087 |
| low_buy_result_snapshots | 50.5 MiB | 3984 |
| runtime_task_events | 50.1 MiB | 192322 |

Assessment: no connection pressure was observed. Slow query growth is real, but
the immediate functional risk is repeated runtime task failure and retry churn.

## Runtime Task Evidence

Last 8 hours:

| Task | Status | Count | Oldest | Latest |
|---|---|---:|---|---|
| market_pulse_refresh | succeeded | 1458 | 2026-06-12 07:15:04 | 2026-06-12 11:45:08 |
| monitor_snapshot_refresh | succeeded | 1444 | 2026-06-12 07:15:04 | 2026-06-12 11:45:10 |
| low_buy_materialization_refresh | failed | 1010 | 2026-06-12 07:01:28 | 2026-06-12 12:44:34 |
| market_quote_cache_refresh | succeeded | 260 | 2026-06-12 04:55:21 | 2026-06-12 07:04:54 |
| latest_data_watchdog | succeeded | 64 | 2026-06-12 07:29:25 | 2026-06-12 12:44:28 |
| low_buy_materialization_refresh | queued | 2 | 2026-06-12 12:44:28 | 2026-06-12 12:44:34 |
| data_quality_sla_refresh | queued | 1 | 2026-06-12 07:01:28 | 2026-06-12 07:01:28 |

Failure reasons:

| Reason | Priority | Status | Count |
|---|---:|---|---:|
| latest_low_buy_materialization | 30 | failed | 463 |
| after_close_latest_data | 35 | failed | 334 |
| after_close_latest_data_close_review | 24 | failed | 170 |
| priority_board_latest_missing | 35 | failed | 39 |
| latest_data_watchdog_ok_close_review | 24 | failed | 7 |

Recent failure payloads are all variants of the same condition:

```text
low_buy_materialization_refresh incomplete:
missing_required_strategies=['first_board','late_session_strong_support','volume_shrink']
```

## Low-Buy Snapshot Presence

For `2026-06-12`, the required production strategy snapshots are missing.

Observed low-buy scan/result records:

| Date | Strategy | Scan | Results |
|---|---|---:|---:|
| 2026-06-11 | first_board | 1 | 40 |
| 2026-06-11 | late_session_strong_support | 1 | 2 |
| 2026-06-11 | volume_shrink | 1 | 14 |
| 2026-06-10 | first_board | 1 | 40 |
| 2026-06-10 | late_session_strong_support | 1 | 3 |
| 2026-06-10 | volume_shrink | 1 | 11 |

There were no `low_buy_scan_snapshots` or `low_buy_result_snapshots` rows for
`2026-06-12` in the sampled result. `low_buy.latest_data` confirms:

```text
expected_trade_date=2026-06-12
published_trade_date=
status=pending
daily_bar_count=5211
post_close_daily_bars_ready=true
missing_strategies=first_board,late_session_strong_support,volume_shrink
```

## Go Scan-Worker Interpretation

`tquant-go-scan-worker` is not the direct writer. It is a Go orchestrator over
the Python reference path:

```text
production_scan_enabled=true
production_write_enabled=true
strategy_engine=python_reference
scan_worker_role=go_orchestrated_reference
scan_accepted_total=2314
scan_failures_total=4
snapshot_writes_total=0
```

`snapshot_writes_total=0` is consistent with the Go service returning `202
accepted`; writes happen later through the Python runtime task. Therefore the
current failure should be fixed in the Python runtime/task scheduling path, not
by treating Go scan-worker as the source of truth.

## HTTP Surface

Unauthenticated read-only sampling:

| Path | Status | Time range |
|---|---:|---:|
| /readyz | 200 | 0.0036-0.0039s |
| /next/monitor | 200 | 0.0034-0.0042s |
| /next/monitor/market | 200 | 0.0032-0.0037s |
| /next/strategy-tracking | 200 | 0.0030-0.0036s |
| /next/analysis | 200 | 0.0030-0.0033s |
| /next/backtest | 200 | 0.0031-0.0036s |
| /next/data | 200 | 0.0030-0.0038s |
| /next/settings | 200 | 0.0030-0.0036s |
| /api/monitor/snapshot | 401 | 0.0024-0.0030s |
| /api/screeners/low-buy/priority-board | 401 | 0.0025-0.0030s |
| /api/runtime-tasks/summary | 401 | 0.0025-0.0031s |

The surface is reachable, but this does not prove authenticated BFF p95 because
the existing p95 script registers a temporary user and is not strictly read-only.

## Findings

### P1: Low-Buy Materialization Failure Loop

Evidence:

- `low_buy_materialization_refresh` failed `1010` times in 8 hours.
- Failures repeat every minute after close.
- Required production strategy snapshots are absent for `2026-06-12`.
- `low_buy.latest_data` remains `pending`.

Impact:

- Priority board/latest low-buy publication remains stale or pending.
- Runtime worker burns CPU/DB/IO retrying work that cannot currently publish.
- This retry storm plausibly contributed to the 14:55 worker memory ceiling and
  the 15:02 kernel OOM.

Root-cause judgment:

- The worker keeps treating missing required snapshots as retryable task
  failure.
- After-close, scheduler/watchdog/priority-board paths all enqueue variants of
  the same work.
- The system lacks a gate that says: "daily bars are ready, but required
  strategy snapshots for this trade date are absent; pause or back off until a
  producer actually creates them."

Recommended fix:

1. Add a bounded backoff / idempotency guard for `low_buy_materialization_refresh`
   when `missing_required_strategies` is the only failure reason.
2. Keep production semantics unchanged: do not fake-publish, do not drop
   `first_board`, `late_session_strong_support`, or `volume_shrink`, and do not
   change priority-board ordering or scores.
3. Add an explicit status path such as `blocked_missing_required_snapshots` so
   UI/monitor can show stale reason without retrying every minute.
4. Investigate why the producer did not create `2026-06-12` scan/result
   snapshots. If a manual run is required, propose it separately and execute
   only with authorization.

### P1: D5 Embedded Scheduler Must Remain Closed

Evidence:

- 14:55 checkpoint: runtime-worker `767.7MiB / 768MiB` (`99.96%`).
- Kernel OOM at `15:02 CST`.
- Late post-close snapshot still had `kernel_oom_logs_present`.

Impact:

- Merging scheduler into runtime-worker would put more load into the same
  process group that already hit memory limit under close-pressure.

Recommended fix:

- Keep standalone scheduler until a full new trading-day gate passes with no OOM,
  no runtime-worker memory blocker, and no materialization retry storm.

### P2: MySQL Slow Query Growth

Evidence:

- `Slow_queries` increased from `89` at 15:07 to `118` at 20:44.
- Database is not connection-bound (`Threads_connected=9`, `Threads_running=2`).
- Largest table is `daily_bar_snapshots` at `866.1 MiB`.

Impact:

- Slow reads can amplify worker and API latency during refresh periods.

Recommended fix:

- After the low-buy retry storm is stopped, run slow-log analysis and query-count
  tests. Only then optimize indexes or read paths.

### P2: Non-Core Queue Residue

Evidence:

- `data_quality_sla_refresh` remains queued from `2026-06-12 07:01:28` with
  priority `22`.

Impact:

- It is not the primary pressure source, but it violates the desired "non-core
  stopped/paused" posture.

Recommended fix:

- Treat as a separate authorized queue hygiene item. Do not clean it in an
  observation-only pass.

## Proposed Next Development Tasks

1. Add queue guard tests for duplicate `latest_low_buy_materialization`,
   `after_close_latest_data`, and `after_close_latest_data_close_review` paths.
2. Add an admin/runtime observation field for `missing_required_strategies` and
   next retry time.
3. Re-run required strategy tests:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_low_buy_read_paths.py \
  backend/tests/test_low_buy_priority_board_strategy_variants.py \
  backend/tests/test_low_buy_production_scoring.py \
  backend/tests/test_low_buy_materialization_priority_board.py \
  backend/tests/test_phase4_runtime_worker_tasks.py
```

## Local Fix Implemented

After the root-cause evidence was recorded, a local code fix was implemented
without changing strategy semantics:

1. `refresh_latest_low_buy_materialization()` now treats Go scan-worker
   `accepted=true` / `status=accepted` as asynchronous acceptance, not as a
   completed scan. It falls back to the Python reference path in the same worker
   before attempting to publish.
2. Runtime worker now converts a materialization result with
   `stale_reason=missing_required_strategies` into a terminal skipped task with
   `status=blocked_missing_required_snapshots`, instead of retrying it as a
   generic failure.
3. Low-buy materialization enqueue paths now reuse a same-trade-date blocked
   task instead of requeueing when the only known blocker is missing required
   strategy snapshots.
4. After-close close-review followups now return
   `blocked_missing_required_snapshots` for the same idempotency key instead of
   creating another low-buy close-review materialization task.

Production behavior remains blocked when required strategy snapshots are absent:
the fix does not fake-publish, does not remove required strategies, and does not
change priority-board scoring or ordering.

Validation:

```text
backend/tests/test_low_buy_materialization_priority_board.py
backend/tests/test_phase4_runtime_worker_tasks.py
backend/tests/test_low_buy_read_paths.py
backend/tests/test_low_buy_priority_board_strategy_variants.py
backend/tests/test_low_buy_production_scoring.py
backend/tests/test_cloud_resource_gate_observation.py
backend/tests/test_runtime_task_queue.py
backend/tests/test_independent_runtime_components.py
backend/tests/test_platform_budget_verifier.py
backend/tests/test_cloud_deploy_scripts.py
backend/tests/test_latest_data_close_refresh.py
152 passed, 1 warning
```

## Online Hotfix Deployment And Acceptance

Time: `2026-06-12 21:05-21:22 CST`

Authorized online writes executed:

| Item | Value |
|---|---|
| Uploaded files | `backend/app/services/low_buy_materialization.py`, `backend/app/workers/runtime_worker.py`, `backend/app/services/latest_data_close_refresh.py` |
| First remote backup | `/home/ubuntu/gupiao-upload/.runtime/manual-hotfix-backups/low-buy-retry-storm-20260612210533` |
| Second remote backup | `/home/ubuntu/gupiao-upload/.runtime/manual-hotfix-backups/low-buy-blocked-requeue-20260612211447` |
| Recreated containers | `tquant-runtime-worker-mysql`, `tquant-runtime-scheduler-mysql` |
| Not recreated | `tquant-app-mysql`, `tquant-mysql`, `tquant-redis`, `tquant-frontend-web`, `tquant-go-bff-gateway`, `tquant-go-market-read-service`, `tquant-go-scan-worker` |
| Embedded scheduler | not enabled |

Container health after hotfix:

| Container | StartedAt | Health |
|---|---|---|
| `tquant-app-mysql` | `2026-06-11T15:40:10Z` | healthy |
| `tquant-runtime-worker-mysql` | `2026-06-12T13:15:20Z` | healthy |
| `tquant-runtime-scheduler-mysql` | `2026-06-12T13:15:27Z` | healthy |
| `tquant-mysql` | `2026-06-11T15:42:42Z` | healthy |
| `tquant-redis` | `2026-06-09T08:04:11Z` | healthy |
| `tquant-go-bff-gateway` | `2026-06-11T13:44:19Z` | healthy |
| `tquant-go-market-read-service` | `2026-06-11T13:44:13Z` | healthy |
| `tquant-go-scan-worker` | `2026-06-11T13:44:16Z` | healthy |

HTTP checks after hotfix:

| Path | Status | Time |
|---|---:|---:|
| `/readyz` | 200 | 0.008184s |
| `/next/monitor` | 200 | 0.004127s |
| `/next/strategy-tracking` | 200 | 0.005777s |
| `/api/bff/v1/manifest` | 401 | 0.005433s |
| `/api/screeners/low-buy/priority-board` | 401 | 0.003687s |
| `/api/settings/runtime` | 401 | 0.002764s |

Runtime queue acceptance at `21:21:52 CST`:

| Window | Result |
|---|---|
| Last 10 minutes | `low_buy_materialization_refresh`: `1 succeeded`, `0 failed`, `0 queued`, `0 running` |
| Latest task | `51514 succeeded`, finished `2026-06-12 13:19:39 UTC` |
| Latest result missing list | `[]` |
| Required snapshots created | `first_board` 40 rows for `2026-06-12`; `volume_shrink` 9 rows for `2026-06-12` |
| Runtime logs | no new `low_buy_materialization_refresh` RuntimeError/Traceback in the sampled window |

Resource snapshot after hotfix:

| Container | CPU | Memory |
|---|---:|---:|
| `tquant-runtime-worker-mysql` | 21.82% | 330.4MiB / 768MiB |
| `tquant-runtime-scheduler-mysql` | 0.00% | 351.9MiB / 640MiB |
| `tquant-mysql` | 0.79% | 814.8MiB / 1.5GiB |
| `tquant-app-mysql` | 0.12% | 331.8MiB / 768MiB |

Assessment: the retry storm is stopped in the observed window. D5 remains
closed because the prior trading-day gate still contains OOM evidence and the
full formal checkpoint set is incomplete.

## Operations Not Executed After Hotfix

- No `.env` change.
- No MySQL/Redis/Web/Go/frontend restart or recreate.
- No scheduler stop.
- No direct DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No image/cache/volume/binlog cleanup.
- No frontend deploy or cutover.
- No embedded scheduler cutover.
- No `strategy_policy.py` change.
