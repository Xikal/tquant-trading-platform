# MySQL Runtime Root Cause Review - 2026-06-12

## Scope

This is the D6 read-only root-cause review for the cloud resource contention remediation plan. It focuses on MySQL, runtime task queue pressure, slow query evidence, worker/scheduler pressure, and API/page latency.

No online write operation was executed in this review.

## Current Decision

Do not execute D5 embedded scheduler yet.

Reason: the core service is available and short-window resource usage is improved, but scheduler provider warnings are still active, swap remains non-trivial, and MySQL slow-query evidence points to read-path and queue-query work that should be handled before moving scheduler load into runtime-worker.

## Read-Only Evidence

Collection time: `2026-06-12 01:18-01:20 CST`.

Server: `ubuntu@43.143.243.97`.

Project dir: `/home/ubuntu/gupiao-upload`.

Local git status before review: clean.

## Resource Snapshot

| Area | Evidence | Status |
|---|---|---|
| Host load | `0.21, 0.30, 0.29` | pass |
| Memory | `3723MiB total`, `1580MiB available` | pass |
| Swap | `792MiB / 1987MiB` | warning |
| Disk | root `34G / 59G` (`61%`) | pass |
| Inode | `12%` | pass |
| Docker images | `14.1GB`, reclaimable `10.69GB` | warning; cleanup requires authorization |
| Docker build cache | `7.221GB`, reclaimable `2.485GB` | warning; cleanup requires authorization |

## Container Snapshot

| Container | CPU | Memory | Status |
|---|---:|---:|---|
| `tquant-app-mysql` | `0.12%` | `45.33MiB / 768MiB` | healthy |
| `tquant-runtime-worker-mysql` | `0.00%` | `218MiB / 768MiB` | healthy |
| `tquant-runtime-scheduler-mysql` | `0.00%` | `356.2MiB / 640MiB` | healthy but provider warnings present |
| `tquant-mysql` | `0.42%` | `660.6MiB / 1.5GiB` | healthy |
| `tquant-redis` | `0.50%` | `5.645MiB / 128MiB` | healthy |
| `tquant-go-bff-gateway` | `0.00%` | `4.785MiB / 128MiB` | healthy |
| `tquant-go-market-read-service` | `0.00%` | `7.91MiB / 128MiB` | healthy |
| `tquant-go-scan-worker` | `0.00%` | `5.852MiB / 128MiB` | healthy |

## HTTP/API Latency

Unauthenticated smoke:

| Path | Status | Time |
|---|---:|---:|
| `/readyz` | `200` | `0.004038s` |
| `/api/monitor` | `404` | `0.003590s` |
| `/api/monitor/snapshot` | `401` | `0.003636s` |
| `/api/priority-board` | `404` | `0.004050s` |
| `/api/screeners/low-buy/priority-board` | `401` | `0.003432s` |
| `/api/runtime-tasks/summary` | `401` | `0.002870s` |
| `/next/monitor` | `200` | `0.004383s` |
| `/next/monitor/market` | `200` | `0.003457s` |
| `/next/strategy-tracking` | `200` | `0.003208s` |
| `/next/analysis` | `200` | `0.003705s` |
| `/next/backtest` | `200` | `0.003408s` |
| `/next/data` | `200` | `0.003280s` |
| `/next/settings` | `200` | `0.003117s` |

Authenticated read-only samples:

| Path | Status | Sample time |
|---|---:|---:|
| `/api/runtime-tasks/summary` | `200` | `0.146879s` to `0.257809s` across 10 samples |
| `/api/monitor/snapshot` | `401` | auth cookie required; admin header alone is insufficient |
| `/api/screeners/low-buy/priority-board` | `401` | auth cookie required; admin header alone is insufficient |
| `/api/settings` | `401` | auth cookie required; admin header alone is insufficient |

Interpretation: the public page shell and readiness path are fast. Runtime task summary is not failing but is materially slower than static page shell checks because it aggregates `runtime_tasks`.

## MySQL Status

| Metric | Value | Interpretation |
|---|---:|---|
| `Threads_connected` | `9` | not connection-saturated |
| `Threads_running` | `2` | not CPU/thread-saturated at sample time |
| `max_connections` | `120` | sufficient headroom |
| `Slow_queries` | `16` | slow SQL exists and must guide D6 work |
| `Connections` | `1410` | normal cumulative activity |
| `Aborted_connects` | `5` | low but should continue monitoring |
| `Created_tmp_disk_tables` | `0` | no evidence of disk temp-table pressure |
| `Created_tmp_tables` | `218` | moderate |
| `innodb_buffer_pool_size` | `536870912` | 512MiB |
| `Innodb_buffer_pool_bytes_data` | `520044544` | buffer pool is nearly full |
| `Innodb_buffer_pool_pages_free` | `1024` | limited free pool pages |
| `Innodb_buffer_pool_wait_free` | `0` | no wait pressure observed |

Interpretation: MySQL is not currently failing from connections or active threads. The 512MiB buffer pool is almost fully used, which is expected with `daily_bar_snapshots` at `866.06MiB`; it explains memory pressure sensitivity, but the immediate slow-path evidence is query shape and task scheduling rather than max connections.

## Largest Tables

| Table | Rows | Total MB | Data MB | Index MB |
|---|---:|---:|---:|---:|
| `daily_bar_snapshots` | `2,857,088` | `866.06` | `328.83` | `537.23` |
| `key_level_snapshots` | `18,813` | `284.41` | `266.75` | `17.66` |
| `low_buy_strategy_pool_snapshots` | `62,087` | `55.09` | `22.23` | `32.86` |
| `low_buy_result_snapshots` | `2,870` | `50.50` | `48.56` | `1.94` |
| `runtime_tasks` | `44,365` | `47.58` | `37.55` | `10.03` |
| `runtime_task_events` | `146,776` | `38.08` | `34.56` | `3.52` |
| `system_settings` | `167` | `13.53` | `13.52` | `0.02` |

Interpretation: `daily_bar_snapshots` dominates both table and index footprint. Runtime queue tables are not huge, but they are large enough that unbounded summary queries and stale failed rows matter operationally.

## Slow Query Evidence

Top statement digests by total DB time:

| Digest summary | Count | Total sec | Avg ms | Rows examined |
|---|---:|---:|---:|---:|
| `SELECT daily_bar_snapshots.trade_date, open_price, close_price...` | `71,851` | `94.407` | `1.314` | `10,495,745` |
| `SELECT key_level_snapshots...` | `73,580` | `14.670` | `0.199` | `73,572` |
| `SELECT instruments...` | `71,851` | `13.356` | `0.186` | `71,851` |
| `SELECT daily_bar_snapshots symbol/trade_date close/high/low...` | `21` | `3.703` | `176.322` | `439,740` |
| `SELECT daily_bar_snapshots trade_date, COUNT(symbol)... GROUP BY trade_date` | `12` | `3.461` | `288.383` | `3,435,924` |
| `SELECT daily_bar_snapshots pct_chg WHERE instrument_type/date` | `192` | `2.993` | `15.590` | `1,000,512` |
| `SELECT daily_bar_snapshots trade_date, COUNT(id) GROUP BY trade_date` | `192` | `2.562` | `13.342` | `5,002,752` |
| `SELECT system_settings... FROM system_settings` | `129` | `2.051` | `15.896` | `33,282` |
| `SELECT task_type,status,COUNT(*) FROM runtime_tasks WHERE created_at >= NOW() - INTERVAL ...` | `1` | `1.823` | `1822.709` | `45,921` |

Slow log tail shows:

- Priority board / read-path query: `low_buy_result_snapshots` over 30 trade dates, `508 rows`, `0.56-0.61s`.
- Daily bar history range query: `daily_bar_snapshots` for many symbols over ~6 months, `20,940 rows`, `0.79-1.77s`.
- Runtime worker claim query with long `task_type IN (...)` and paused low-priority exclusion, `0.625s`.
- Runtime task summary diagnostic query, `45,911 rows examined`, `1.835s`.
- `system_settings` full scan: `129` executions, `33,282 rows examined`, caused by reading all settings repeatedly despite only `167` current rows.
- Provider fallback writes and scheduler heartbeat updates around `0.25-0.46s` when MySQL is busy.

## EXPLAIN Evidence

`daily_bar_snapshots` indexes:

| Index | Columns |
|---|---|
| `uq_daily_bar_snapshot` | `symbol,trade_date` |
| `ix_daily_bar_snapshots_trade_date` | `trade_date` |
| `ix_daily_date_symbol` | `trade_date,symbol` |
| `ix_daily_type_date_symbol` | `instrument_type,trade_date,symbol` |
| `ix_daily_bar_snapshots_symbol` | `symbol` |
| `ix_daily_bar_snapshots_instrument_type` | `instrument_type` |

Observed EXPLAIN:

| Query | Key | Rows | Extra |
|---|---|---:|---|
| `SELECT DISTINCT trade_date ... ORDER BY trade_date DESC LIMIT 20` | `ix_daily_date_symbol` | `512` | `Using index for group-by; Using temporary; Using filesort` |
| `COUNT by trade_date WHERE instrument_type='stock' GROUP BY trade_date LIMIT 60` | `ix_daily_type_date_symbol` | `1,428,544` | `Backward index scan; Using index` |
| `COUNT one day WHERE trade_date='2026-06-11' AND instrument_type='stock'` | `ix_daily_type_date_symbol` | `9,604` | `Using index` |
| `fetch symbols range ORDER BY symbol,trade_date` | `uq_daily_bar_snapshot` | `479` | `Using index condition` |

Interpretation: there are useful indexes, but the date-coverage aggregation still scans large ranges. This is a better candidate for read-model caching/materialization than simply adding more indexes blindly.

## Runtime Queue Status

Recent two-hour task summary:

| Task | Status | Count | Latest |
|---|---|---:|---|
| `strategy_tracking_snapshot_refresh` | succeeded | `49` | `2026-06-11 15:59:43` |
| `a_key_level_materialization_refresh` | succeeded | `22` | `2026-06-11 16:00:44` |
| `latest_data_watchdog` | succeeded | `7` | `2026-06-11 15:58:10` |
| `hermes_platform_autopilot` | succeeded | `4` | `2026-06-11 15:38:56` |
| `low_buy_materialization_refresh` | succeeded | `2` | `2026-06-11 17:11:48` |

Non-terminal tasks:

| Status | Task | Priority | Count | Oldest |
|---|---|---:|---:|---|
| queued | `data_quality_sla_refresh` | `22` | `2` | `2026-06-10 07:01:31` |

Recent 24h failures:

| Task | Count | Latest | Error summary |
|---|---:|---|---|
| `low_buy_materialization_refresh` | `206` | `2026-06-11 09:01:00` | missing strategies `first_board`, `late_session_strong_support`, `volume_shrink` |
| `low_buy_materialization_refresh` | `19` | `2026-06-11 13:43:35` | multiple missing strategies including `breakout_support`, `classic_retrace`, etc. |
| `low_buy_materialization_refresh` | `2` | `2026-06-11 08:44:12` | multiple missing strategies |

Interpretation:

- Current core queue is not backing up.
- Old queued `data_quality_sla_refresh` is non-core/noise under the current resource profile and should be marked or cancelled only with DB-write authorization.
- Failed `low_buy_materialization_refresh` rows are historical operational noise. They do not prove current core failure because later `low_buy_materialization_refresh` succeeded at `17:11:48`.
- Duplicate success counts for A-key and strategy-tracking are still visible inside time windows that include the pre-dedupe period. Continue observing after the dedupe deployment.

## Scheduler And Provider Pressure

Scheduler logs still show repeated provider pressure:

- `market provider circuit open` for `akshare`, `eastmoney`, `openbb`, `local`.
- EastMoney spot page `RemoteDisconnected`.
- AkShare fallback decode failure: response starts with `<`.
- `fetch_board_breadth_frame` timeout around `4000ms`.
- remote BFF market-read request failed for `/api/market-read/v1/intraday-latest-batch`.

Impact:

- This keeps standalone `runtime-scheduler` useful as a blast-radius boundary.
- It is not safe to merge scheduler into runtime-worker until provider timeouts/fallbacks stop producing sustained warning bursts over a full trading day.

## Root Cause Classification

### P1: Daily Bar Read Path Dominates MySQL Slow Time

Evidence:

- `daily_bar_snapshots` is the largest table: `866.06MB`.
- Top digest is daily bar snapshot reads: `94.407s` total DB time.
- Group-by coverage queries scan `1.4M-5.0M` rows in observed digests.
- Slow log has `daily_bar_snapshots` range reads taking `0.79-1.77s`.

Impact:

- Makes MySQL buffer pool pressure and API/task latency worse during materialization or strategy-tracking refresh.
- Can reintroduce worker and scheduler contention even after non-core tasks are paused.

Likely root cause:

- Repeated hot reads over `daily_bar_snapshots` for recent-date coverage and symbol history.
- Some read paths are still calculating coverage from raw bars instead of using a compact materialized coverage/read model.

Recommended fix:

1. Add or reuse a daily coverage materialized read model for:
   - latest complete trade date,
   - stock count by trade date,
   - recent complete trade dates.
2. Route `backend/app/repositories/low_buy/daily_history.py` coverage methods to the materialized read model with fallback to raw bars.
3. Keep raw `fetch_rows_for_symbols` semantics unchanged; only cache/short-circuit coverage metadata first.
4. Add EXPLAIN-based tests or repository tests for the new read model query shape.

Authorization:

- Code change and deploy required.
- If a new table/index is needed, schema migration and production DB write require explicit authorization.

### P1: Scheduler Provider Fallback Still Generates Pressure

Evidence:

- Provider circuits repeatedly open in scheduler logs.
- EastMoney and AkShare fallback failures repeat.
- This is still present after non-core stop and worker recycle guard.

Impact:

- Makes D5 scheduler embed unsafe.
- Can trigger CPU/network wait bursts and generate DB writes to market regime/system settings when fallback paths update snapshots.

Likely root cause:

- External provider instability combined with frequent scheduler attempts.
- Fallback paths still retry or refresh too aggressively when all providers are degraded.

Recommended fix:

1. Add a provider-degraded cooldown/read-through guard for scheduler tasks.
2. Prefer stale cached market snapshot when all providers are circuit-open instead of attempting repeated live fallbacks.
3. Add log-rate limiting for repeated provider circuit-open messages.
4. Keep UI data freshness labels explicit; do not silently fake live freshness.

Authorization:

- Code change and deploy required.
- No strategy scoring change required.

### P2: Runtime Task Summary And Queue Queries Need Narrower Index/Read Model

Evidence:

- Runtime task diagnostic query examined `45,911` rows and took `1.835s`.
- `/api/runtime-tasks/summary` took `0.146-0.258s` across 10 samples.
- `runtime_tasks` has `44,365` rows and `runtime_task_events` has `146,776` rows.

Impact:

- Admin/runtime observability can become slow during task churn.
- Queue claim query is indexed but still has a long `task_type IN` plus low-priority exclusion.

Likely root cause:

- Summary queries scan broad historical task data.
- Old failed and queued rows add noise.

Recommended fix:

1. Keep low-priority pause enabled.
2. Add a summary read model or restrict summary aggregates by recent window and indexed predicates.
3. Consider an index for `created_at,status,task_type` or `status,created_at,task_type` only after EXPLAIN on the exact production query.
4. With DB-write authorization, cancel or mark stale non-core `data_quality_sla_refresh` tasks and archive historical failed task noise.

Authorization:

- Query/code change and deploy required.
- Any index/schema change or task status update requires separate DB-write authorization.

### P2: System Settings Full Scan And Repeated Heartbeat Writes Are Noisy

Evidence:

- Digest `SELECT system_settings... FROM system_settings` ran `129` times and examined `33,282` rows.
- Slow log shows heartbeat updates taking `0.28s` while MySQL is busy.

Impact:

- Not the largest cost, but contributes to background DB churn.

Likely root cause:

- Some settings paths load all rows repeatedly instead of fetching specific keys or caching.
- Heartbeat writes are frequent enough to appear in slow logs under pressure.

Recommended fix:

1. Audit settings reads and convert all-settings scans on hot paths to keyed reads or short TTL cache.
2. Keep heartbeat writes but avoid duplicate heartbeat keys where possible.
3. Do not remove heartbeat observability; it is needed for D5 gate.

Authorization:

- Code change and deploy required.

### P3: Docker Image/Build Cache Is Large But Not Current P0

Evidence:

- Docker images: `14.1GB`, reclaimable `10.69GB`.
- Build cache: `7.221GB`, reclaimable `2.485GB`.
- Disk root still `61%`; inode `12%`.

Impact:

- Not causing current failure, but increases deployment risk and future disk pressure.

Recommended fix:

- Plan a separate authorized cleanup window using bounded prune commands that do not touch volumes.

Authorization:

- Cleanup requires explicit authorization.

## What Is Not The Current Root Cause

| Candidate | Evidence | Conclusion |
|---|---|---|
| Frontend memory | `tquant-frontend-web` `2.176MiB / 128MiB`; pages return `200` in milliseconds | not root cause |
| MySQL connection exhaustion | `Threads_connected=9`, `Threads_running=2`, `max_connections=120` | not current root cause |
| Redis pressure | `5.645MiB / 128MiB` | not root cause |
| Disk full | root `61%`, inode `12%` | not current root cause |
| Core worker RSS | `218MiB / 768MiB` after recycle guard | improved; continue observing |

## Recommended Fix Plan

### Step 1: Keep Current Stop Profile And Observe Full Trading Day

- Keep `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true`.
- Keep `PLATFORM_AUTOPILOT_ENABLED=false`.
- Keep `MARKET_REVIEW_ENABLED=false` or degraded.
- Keep `RUNTIME_WORKER_RECYCLE_RSS_MB=700`.
- Keep standalone scheduler until D5 gate passes.

### Step 2: Daily Bar Coverage Read Model

Files to inspect/modify:

- `backend/app/repositories/low_buy/daily_history.py`
- `backend/app/services/daily_bar_refresh.py`
- `backend/app/services/data_quality/sla.py`
- migration file if a new materialized table is needed
- focused repository tests

Acceptance:

- Priority board ordering and `production_score` unchanged.
- Coverage/latest-date queries no longer scan million-row ranges on hot paths.
- Existing low-buy read path tests still pass.

### Step 3: Provider Degraded Cooldown

Files to inspect/modify:

- `backend/app/services/market/providers/router.py`
- `backend/app/services/market/spot_snapshot.py`
- `backend/app/runtime/background_jobs.py`
- scheduler/provider tests

Acceptance:

- When all providers are circuit-open, scheduler uses stale cached snapshot and records degraded freshness instead of repeating live fallback bursts.
- No fake live freshness.
- Core monitor and priority board still render.

### Step 4: Runtime Task Summary Optimization

Files to inspect/modify:

- `backend/app/services/tasks/queue.py`
- `backend/app/api/routes/runtime_tasks.py`
- possible migration/index only after EXPLAIN proof

Acceptance:

- `/api/runtime-tasks/summary` remains below an agreed p95 budget under current task volume.
- Low-priority pause visibility remains.
- Historical failures do not hide current core status.

### Step 5: Authorized DB Cleanup/Archive

Only after authorization:

- Cancel/mark stale queued non-core `data_quality_sla_refresh`.
- Archive or mark historical failed `low_buy_materialization_refresh` noise if agreed.
- Do not delete business data.

## Suggested Authorized Commands For Later

These commands are recorded for review only. They were not executed.

```sql
-- Example only: exact task IDs/statuses must be reviewed before use.
UPDATE runtime_tasks
SET status = 'cancelled',
    error_message = 'cancelled after resource remediation review: stale non-core queued task',
    updated_at = NOW(),
    finished_at = NOW()
WHERE status = 'queued'
  AND task_type = 'data_quality_sla_refresh'
  AND created_at < NOW() - INTERVAL 12 HOUR;
```

```bash
# Example only: bounded Docker cache cleanup; requires separate authorization.
sudo docker builder prune --filter until=72h
```

## Operations Not Executed

- No `.env` change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No schema/index change.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.

## Next Gate

D5 scheduler embed remains closed until:

1. `scripts/collect_cloud_resource_gate_observation.py --full-trading-day-complete` returns `d5_gate.ready=true`.
2. Provider warning bursts are resolved or proven harmless across a full trading day.
3. MySQL slow-path fixes are either completed or explicitly deferred with user authorization.
4. User approves a maintenance window to stop the standalone scheduler.
