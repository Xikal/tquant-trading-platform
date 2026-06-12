# Cloud Resource Contention Remediation Baseline - 2026-06-12

## Scope

按 `docs/superpowers/plans/2026-06-11-cloud-resource-contention-final-remediation.md` 继续执行云服务器资源争抢治理。本报告是 `2026-06-12 04:35-04:38 CST` 的 D0 只读复核，用于确认 D4/D6 后当前线上资源、容器、RuntimeTask、HTTP/API 和 D5 scheduler gate 状态。

本轮只读复核未执行部署、切流、容器重启、Docker 清理、线上 `.env` 修改、数据库写入、nginx/systemd 变更或 scheduler 停止。

## Server

| Item | Value |
|---|---|
| Local time | `2026-06-12 04:35:15 CST` |
| Remote time | `2026-06-12 04:36:44 CST` |
| Host | `ubuntu@43.143.243.97` |
| Project dir | `/home/ubuntu/gupiao-upload` |
| Current D5 state | before first required `09:15 CST` checkpoint |

## Git Status

`git status --short` before creating this report:

```text

```

The local worktree was clean.

## Resource Snapshot

| Metric | Value | Status |
|---|---:|---|
| Uptime | `up 3 days, 17:20` | normal |
| Load average | `0.11 / 0.20 / 0.26` | normal |
| Memory | `3723MiB total / 2373MiB used / 1349MiB available` | improved vs D0/D4 |
| Swap | `1987MiB total / 646MiB used` | warning: still present |
| Root disk | `36G / 59G, 63%` | ok, watch growth |
| inode | `475K / 3.8M, 13%` | ok |
| Docker images | `14.2GB`, reclaimable `10.79GB` | cleanup candidate, not executed |
| Docker volumes | `10.55GB`, reclaimable `0B` | observe |
| Docker build cache | `7.414GB`, reclaimable `2.678GB` | cleanup candidate, not executed |

## Container Snapshot

| Container | Status | CPU | Memory | Assessment |
|---|---|---:|---:|---|
| `tquant-app-mysql` | Up 5h healthy | `0.12%` | `60.38MiB / 768MiB` | ok |
| `tquant-frontend-web` | running in Docker stats | `1.52%` | `4.262MiB / 128MiB` | ok |
| `tquant-go-bff-gateway` | Up 7h healthy | `2.38%` | `5.203MiB / 128MiB` | ok |
| `tquant-go-market-read-service` | Up 7h healthy | `0.00%` | `7.938MiB / 128MiB` | ok |
| `tquant-go-scan-worker` | Up 7h healthy | `0.00%` | `6.02MiB / 128MiB` | ok |
| `tquant-mysql` | Up 5h healthy | `0.79%` | `868MiB / 1.5GiB` | improved after D6, still primary watch item |
| `tquant-redis` | Up 2d healthy | `0.49%` | `4.957MiB / 128MiB` | ok |
| `tquant-runtime-scheduler-mysql` | Up 39m healthy | `0.00%` | `254MiB / 640MiB` | still standalone, D5 not executed |
| `tquant-runtime-worker-mysql` | Up 4h healthy | `0.00%` | `296.1MiB / 768MiB` | ok |

Note: `docker compose -f docker-compose.mysql.yml ps` did not list `tquant-frontend-web`, but `docker stats` shows it running. This is expected when frontend is managed outside the monolith compose scope.

## Runtime Queue Snapshot

Last 4h groups:

| Task type | Status | Count | Latest |
|---|---|---:|---|
| `low_buy_materialization_refresh` | succeeded | 8 | `2026-06-11 19:57:59` |
| `data_quality_sla_refresh` | cancelled | 2 | `2026-06-11 18:53:58` |

Core task groups over the last 8h:

| Task type | Status | Count | Latest |
|---|---|---:|---|
| `latest_data_watchdog` | succeeded | 39 | `2026-06-11 15:58:10` |
| `low_buy_materialization_refresh` | failed | 2 | `2026-06-11 13:43:35` |
| `low_buy_materialization_refresh` | succeeded | 44 | `2026-06-11 19:57:59` |
| `market_pulse_refresh` | succeeded | 4 | `2026-06-11 14:58:42` |
| `monitor_snapshot_refresh` | succeeded | 5 | `2026-06-11 14:59:19` |
| `strategy_tracking_snapshot_refresh` | succeeded | 225 | `2026-06-11 15:59:43` |

Non-terminal/failed groups:

| Status | Task type | Priority | Count | Oldest | Latest |
|---|---|---:|---:|---|---|
| failed | `analytics_export_strategy_tracking_snapshots` | 900 | 1 | `2026-06-08 05:14:02` | `2026-06-08 05:14:03` |
| failed | `analytics_export_paper_review_reports` | 900 | 1 | `2026-06-08 05:14:02` | `2026-06-08 05:14:14` |
| failed | `analytics_export_market_review_reports` | 900 | 1 | `2026-06-08 05:14:02` | `2026-06-08 05:14:14` |
| failed | `analytics_export_analysis_logs` | 900 | 1 | `2026-06-08 05:14:02` | `2026-06-08 05:14:14` |
| failed | `analytics_export_backtest_daily_snapshots` | 900 | 1 | `2026-06-08 05:14:02` | `2026-06-08 05:14:14` |
| failed | `analytics_export_backtest_trades` | 900 | 1 | `2026-06-08 05:14:02` | `2026-06-08 05:14:14` |
| failed | `analytics_export_backtest_runs` | 900 | 1 | `2026-06-08 05:14:02` | `2026-06-08 05:14:03` |
| failed | `analytics_export_low_buy_result_snapshots` | 900 | 1 | `2026-06-08 05:14:02` | `2026-06-08 05:14:03` |
| failed | `analytics_export_key_level_snapshots` | 900 | 1 | `2026-06-08 05:14:02` | `2026-06-08 05:14:03` |
| failed | `monitor_snapshot_refresh` | 60 | 584 | `2026-05-07 08:49:56` | `2026-06-08 07:28:23` |
| failed | `a_key_level_materialization_refresh` | 45 | 457 | `2026-06-02 08:30:34` | `2026-06-03 15:21:01` |
| failed | `low_buy_materialization_refresh` | 35 | 283 | `2026-05-26 08:26:30` | `2026-06-11 08:59:53` |
| failed | `low_buy_materialization_refresh` | 30 | 424 | `2026-06-08 07:05:33` | `2026-06-11 13:43:35` |
| failed | `low_buy_materialization_refresh` | 24 | 146 | `2026-06-10 07:01:31` | `2026-06-11 09:01:00` |
| failed | `data_backfill_24m` | 20 | 2 | `2026-05-30 10:46:41` | `2026-05-30 11:09:40` |
| failed | `daily_bar_refresh` | 20 | 2 | `2026-05-28 07:01:25` | `2026-05-28 07:01:59` |
| failed | `strategy_24m_duckdb_report` | 10 | 2 | `2026-05-30 11:00:16` | `2026-05-30 11:15:10` |

Interpretation:

- No queued/running core backlog was observed in this snapshot.
- The large failed groups are historical and predate the current D4/D6 state.
- Low-priority export failures remain observability noise, not active load, because `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true` is live on worker/scheduler.

## Scheduler Heartbeat

Heartbeats are stored in `system_settings` under `platform_component.heartbeat.*`.

| Key | Updated at | Value |
|---|---|---|
| `platform_component.heartbeat.runtime-worker` | `2026-06-11 20:38:36` | `worker_id=runtime-8a2ddf90d9f2`, `status=running` |
| `platform_component.heartbeat.runtime-scheduler` | `2026-06-11 20:38:20` | `worker_id=runtime-scheduler`, `status=running` |

Interpretation:

- D5 embedded scheduler has not been executed.
- The standalone scheduler is still active.
- Expected embedded worker id `runtime-worker-embedded-scheduler` is not present, which is correct before D5.

## Runtime Environment Flags

| Container | Relevant values |
|---|---|
| `tquant-runtime-worker-mysql` | `PLATFORM_AUTOPILOT_ENABLED=false`, `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true`, `RUNTIME_WORKER_EMBED_SCHEDULER=false`, `RUNTIME_WORKER_RECYCLE_RSS_MB=700`, startup prewarm disabled |
| `tquant-runtime-scheduler-mysql` | `MARKET_REVIEW_ENABLED=false`, `RUNTIME_BACKGROUND_JOBS_ENABLED=true`, `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true`, `RUNTIME_WORKER_EMBED_SCHEDULER=false` |

Scheduler provider warnings:

| Window | Count |
|---|---:|
| last 30m `all board strategies failed` lines | 0 |

## HTTP/API Verification

| Path | Status | Time | Body summary |
|---|---:|---:|---|
| `/readyz` | 200 | `0.003884s` | ok |
| `/api/monitor` | 404 | `0.004643s` | API alias not found |
| `/api/monitor/snapshot` | 401 | `0.003279s` | auth required |
| `/api/priority-board` | 404 | `0.002982s` | API alias not found |
| `/api/screeners/low-buy/priority-board` | 401 | `0.002901s` | auth required |
| `/api/runtime-tasks/summary` | 401 | `0.002809s` | admin token required |
| `/next/monitor` | 200 | `0.003442s` | frontend-next shell |
| `/next/monitor/market` | 200 | `0.003400s` | frontend-next shell |
| `/next/strategy-tracking` | 200 | `0.003701s` | frontend-next shell |
| `/next/analysis` | 200 | `0.003927s` | frontend-next shell |
| `/next/backtest` | 200 | `0.003632s` | frontend-next shell |
| `/next/data` | 200 | `0.003656s` | frontend-next shell |
| `/next/settings` | 200 | `0.003660s` | frontend-next shell |

## Current Assessment

| Area | State | Evidence | Risk |
|---|---|---|---|
| Current online availability | usable | `/readyz` 200; main `/next/*` pages 200 | low |
| Resource contention | improved | available memory `1349MiB`; worker `296.1MiB`; scheduler `254MiB` | swap still `646MiB` |
| MySQL | improved but watch | `868MiB / 1.5GiB`, no immediate OOM in this snapshot | remains largest memory process |
| Low-priority load | stopped from claiming | env flags true on worker/scheduler | historical failed noise remains |
| Provider pressure | improved | scheduler provider warning count last 30m `0` | must recheck at market hours |
| D5 scheduler merge | not allowed yet | local time `04:35 CST`, first checkpoint remains `09:15 CST`; heartbeat still standalone | full trading day incomplete |

## Root Cause Direction

Current evidence supports the staged plan:

1. D4 non-core stop and D6 MySQL memory limit stabilization materially improved available memory and worker RSS.
2. Remaining swap usage and MySQL RSS mean the root cause is not fully closed.
3. D5 scheduler consolidation can reduce another constant process, but only after a full trading-day checkpoint set proves no queue/provider/MySQL regressions.
4. Historical failed RuntimeTask rows are noise and should not be deleted without a separate archival/cleanup authorization.

## Next Step

Do not execute D5 yet. The next valid checkpoint is `2026-06-12 09:15 CST`. Required action then:

```bash
python3 scripts/collect_cloud_resource_gate_observation.py \
  --ssh-host 43.143.243.97 \
  --ssh-user ubuntu \
  --ssh-key /Users/j/Downloads/gupiao.pem \
  --journal-since "2026-06-12 00:00:00" \
  --docker-logs-since 30m \
  --checkpoint-label trading-day-0915 \
  --json-output docs/reports/cloud-resource-gate-observations/2026-06-12-0915.json \
  --markdown-output docs/reports/cloud-resource-gate-observations/2026-06-12-0915.md
```

## Operations Not Executed

- No `.env` change.
- No Docker restart/recreate/stop/remove.
- No `runtime-scheduler` stop.
- No MySQL/Redis/Web/Go/frontend action.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.
- No `strategy_policy.py` change.
- No production strategy, `production_score`, or `priority_board` sorting change.

## D1 Example File Gap Closed - 2026-06-12 21:39 CST

The original D1 plan referenced `.env.production.example`, but the repository only had `.env.deploy.local.example`, `.env.docker.example`, and `backend/.env.example`. A new `.env.production.example` was added as documentation only. It is not loaded automatically by the app and does not change compose defaults or production runtime behavior.

The file now records the authorized resource-contention stop profile:

| Setting | Example value | Purpose |
|---|---|---|
| `PLATFORM_AUTOPILOT_ENABLED` | `false` | stop autopilot task pressure |
| `RUNTIME_LOW_PRIORITY_TASKS_PAUSED` | `true` | pause analytics/backtest/ML/factor/data repair/research task claims |
| `MARKET_REVIEW_ENABLED` | `false` | stop optional market review generation |
| `RUNTIME_STARTUP_CACHE_PREWARM_ENABLED` | `false` | avoid startup cache pressure |
| `RUNTIME_STARTUP_HISTORY_PREWARM_ENABLED` | `false` | avoid startup history pressure |
| `RUNTIME_WORKER_EMBED_SCHEDULER` | `false` | keep D5 scheduler cutover gated |
| `RUNTIME_SCHEDULER_BACKGROUND_JOBS_ENABLED` | `true` | keep standalone scheduler path unchanged before D5 |
| `RUNTIME_WORKER_RECYCLE_RSS_MB` | `0` | keep worker recycle guard disabled unless evidence justifies it |

Guard test added:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_cloud_deploy_scripts.py::test_production_env_example_documents_resource_stop_profile_only \
  backend/tests/test_cloud_deploy_scripts.py::test_cloud_deploy_does_not_write_removed_paper_auto_trading_flag \
  backend/tests/test_platform_budget_verifier.py \
  backend/tests/test_runtime_task_queue.py::test_runtime_task_queue_pauses_configured_low_priority_tasks \
  backend/tests/test_runtime_task_queue.py::test_runtime_task_summary_reports_paused_low_priority_backlog
```

Result: `15 passed`, with only the existing LibreSSL urllib3 warning.

The new example explicitly avoids `PAPER_AUTO_TRADING_ENABLED`, `PAPER_PERF_ARCHIVE_ENABLED`, `MYSQL_ROOT_PASSWORD`, and `AUTH_SECRET_KEY`.

## D2/D3 Budget Recheck - 2026-06-12 21:39 CST

Read-only verifier report:

- `docs/reports/platform-budget-current-2026-06-12-post-d1-gap-fix.md`
- `docs/reports/platform-budget-current-2026-06-12-post-d1-gap-fix.json`

Summary:

| Area | Evidence |
|---|---|
| evaluation | `ok`, no warnings, no blocking |
| MySQL | `max_connections=120`, `Threads_connected=10`, `Threads_running=2` |
| pool budget | total `20`, target `40` |
| web | background jobs `false`, analytics `false`, pool budget `4` |
| runtime-worker | `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true`, `RUNTIME_WORKER_EMBED_SCHEDULER=false`, `RUNTIME_WORKER_RECYCLE_RSS_MB=700` |
| runtime-scheduler | `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true`, `RUNTIME_WORKER_EMBED_SCHEDULER=false`, `MARKET_REVIEW_ENABLED=false` |

Interpretation:

- Current online budget state has no embedded-scheduler residue.
- Worker and scheduler both have low-priority pause active.
- D5 remains blocked by the trading-day gate and prior blocker evidence; this budget recheck alone does not authorize scheduler cutover.

Additional operations not executed in this D1/D2 recheck:

- No remote `.env` write.
- No container restart/recreate/remove.
- No DB write.
- No Docker cleanup.
- No deployment or cutover.

## D2/D4 Container Residency Budget Recheck - 2026-06-12 21:51 CST

The budget verifier was tightened to distinguish a container object that exists from a container that is actually running. This matters for optional/on-demand workers: an exited `analytics-worker` should remain visible in Docker state, but must not be counted as a resident resource consumer or active DB pool budget.

Read-only verifier report:

- `docs/reports/platform-budget-current-2026-06-12-container-state.md`
- `docs/reports/platform-budget-current-2026-06-12-container-state.json`

Summary:

| Area | Evidence |
|---|---|
| evaluation | `ok`, no warnings, no blocking |
| MySQL | `max_connections=120`, `Threads_connected=10`, `Threads_running=2` |
| running pool budget | total `16`, target `40` |
| web | `running`, pool budget `4`, background jobs `false`, analytics `false` |
| runtime-worker | `running`, pool budget `6`, low-priority pause `true`, embedded scheduler `false`, recycle RSS `700` |
| runtime-scheduler | `running`, pool budget `6`, low-priority pause `true`, market review `false` |
| analytics-worker | container exists but status `exited`; running `false`; runtime pool budget `0`; configured pool budget `4` |

Interpretation:

- The optional `analytics-worker` is not currently a resident resource consumer.
- The earlier `container_present=true` budget view was too coarse because it counted configured env for an exited container.
- Current always-on DB pool pressure is Web + runtime-worker + runtime-scheduler only: `4 + 6 + 6 = 16`.
- D5 still remains blocked by the full trading-day gate; this observation does not authorize stopping standalone `runtime-scheduler`.

Additional operations not executed in this D2/D4 recheck:

- No remote `.env` write.
- No container restart/recreate/remove/stop.
- No DB write.
- No Docker cleanup.
- No deployment or cutover.

## D5 Post-Close Checkpoint - 2026-06-12 21:55 CST

Read-only gate observation:

- `docs/reports/cloud-resource-gate-observations/2026-06-12-postclose-current-2155.md`
- `docs/reports/cloud-resource-gate-observations/2026-06-12-postclose-current-2155.json`

Summary:

| Area | Evidence |
|---|---|
| evaluation | `warning`; no blocking |
| D5 ready | `false` |
| D5 blockers | `full_trading_day_observation_incomplete`, `runtime_nonterminal_task_count=1` |
| host memory | available `1043MB`, swap used `34.98%` |
| root disk / inode | `63%` / `13%` |
| runtime-worker | `330.4MiB / 768MiB`, memory `43.02%` |
| runtime-scheduler | `355.5MiB / 640MiB`, memory `55.54%` |
| MySQL | `816.1MiB / 1.5GiB`, `Threads_connected=10`, `Threads_running=2`, `Slow_queries=133` |
| HTTP | `/readyz` 200; main `/next/*` pages 200; protected APIs 401 as expected |
| runtime tasks | one queued `data_quality_sla_refresh`; recent `latest_data_watchdog` succeeded through `13:52:49 UTC` |

Trading-day gate summary was regenerated with this seventh snapshot:

- `docs/reports/cloud-resource-trading-day-gate-summary-2026-06-12.md`
- `docs/reports/cloud-resource-trading-day-gate-summary-2026-06-12.json`

Current D5 gate state:

- `checkpoint_count=7`
- missing checkpoints: `10:30`, `11:30`, `13:05`, `15:10`, `15:30`
- `d5_ready=false`
- D5 remains blocked; standalone `runtime-scheduler` must not be stopped or merged yet.

Additional operations not executed in this D5 checkpoint:

- No remote `.env` write.
- No container restart/recreate/remove/stop.
- No scheduler stop.
- No DB write.
- No Docker cleanup.
- No deployment or cutover.

## D5 Nonterminal Queue Diagnosis - 2026-06-12 21:58 CST

Read-only MySQL query checked the remaining non-terminal RuntimeTask that blocks the latest D5 checkpoint.

Evidence:

| Field | Value |
|---|---|
| task id | `47413` |
| task type | `data_quality_sla_refresh` |
| status | `queued` |
| priority | `22` |
| idempotency key | `data_quality_sla_refresh:daily_bars:production_universe:2026-06-12` |
| created_at / updated_at | `2026-06-12 07:01:28 UTC` |
| payload | daily-bars SLA, `production_universe`, `2026-06-12`, reason `after_close_latest_data` |
| registered worker | analytics-worker |
| current analytics-worker residency | exited / not running, per container-state budget check |

Interpretation:

- This queue item is not a core runtime-worker task.
- It is owned by analytics-worker and is expected to remain queued while analytics-worker is intentionally not resident.
- It does not directly affect monitor, market quote cache, low-buy board, priority board, or strategy tracking.
- It still appears as a D5 gate blocker because the current gate treats any queued/running RuntimeTask as non-terminal pressure.

Recommended authorized fix:

- If the goal is to keep analytics-worker non-resident, cancel this stale non-core task through `RuntimeTaskQueue.cancel()` with an audit reason.
- Do not use raw SQL for cancellation unless the app queue API is unavailable.
- Do not start analytics-worker just to process this single non-core task unless the user explicitly chooses to run analytics on demand.

Additional operations not executed in this queue diagnosis:

- No task cancellation.
- No DB write.
- No analytics-worker start.
- No container restart/recreate/remove/stop.
- No deployment or cutover.
