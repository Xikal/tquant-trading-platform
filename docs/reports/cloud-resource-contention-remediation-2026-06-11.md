# Cloud Resource Contention Remediation Baseline - 2026-06-11

## Scope

按 `docs/superpowers/plans/2026-06-11-cloud-resource-contention-final-remediation.md` 执行 D0 只读基线。目标是确认线上资源争抢、核心服务可用性、runtime task 分布，以及后续止血和 scheduler 合并的证据基础。

## Server

| Item | Value |
|---|---|
| Time | `Thu Jun 11 23:13:07 CST 2026` |
| Host | `ubuntu@43.143.243.97` |
| Project dir | `/home/ubuntu/gupiao-upload` |
| Public IP entry | `https://43.143.243.97` |
| Domain entry | `https://weisilianghua.cloud` |

## Git Status

`git status --short` before D0 local report creation:

```text

```

The worktree was clean. This report is the only D0 local artifact.

## Resource Snapshot

| Metric | Value | Status |
|---|---:|---|
| Uptime | `3 days, 11:57` | normal |
| Load average | `1.12 / 1.09 / 1.11` | acceptable |
| Memory | `3723MiB total / 3471MiB used / 251MiB available` | risk |
| Swap | `1987MiB total / 945MiB used` | risk |
| Root disk | `32G / 59G, 56%` | ok |
| inode | `392K / 3.8M, 11%` | ok |
| Docker images | `11.48GB, 8.066GB reclaimable` | cleanup candidate, not memory root cause |
| Docker volumes | `10.88GB, 0B reclaimable` | observe |
| Docker build cache | `5.551GB` | cleanup candidate, not memory root cause |

## Container Snapshot

| Container | Status | CPU | Memory |
|---|---|---:|---:|
| `tquant-app-mysql` | Up healthy | `0.12%` | `538.6MiB / 768MiB` |
| `tquant-frontend-web` | Up healthy | `0.00%` | `2.406MiB / 128MiB` |
| `tquant-go-bff-gateway` | Up healthy | `0.00%` | `3.5MiB / 128MiB` |
| `tquant-go-market-read-service` | Up healthy | `0.00%` | `6.422MiB / 128MiB` |
| `tquant-go-scan-worker` | Up healthy | `0.00%` | `2.195MiB / 128MiB` |
| `tquant-mysql` | Up healthy | `18.02%` | `1004MiB / 1GiB` |
| `tquant-redis` | Up healthy | `0.64%` | `4.34MiB / 128MiB` |
| `tquant-runtime-scheduler-mysql` | Up healthy | `0.00%` | `329.5MiB / 640MiB` |
| `tquant-runtime-worker-mysql` | Up healthy | `91.33%` | `722.5MiB / 768MiB` |
| `tquant-analytics-worker-mysql` | Exited 137, 2 days ago | n/a | n/a |
| `tquant-prometheus` | Exited 0, 2 days ago | n/a | n/a |
| `tquant-grafana` | Exited 0, 2 days ago | n/a | n/a |
| `tquant-migration-mysql` | Exited 0 | n/a | n/a |

## Runtime Queue Snapshot

Current non-terminal and failed groups:

| Status | Task type | Priority | Count | Oldest | Latest |
|---|---|---:|---:|---|---|
| running | `a_key_level_materialization_refresh` | 45 | 1 | `2026-06-11 15:11:55` | `2026-06-11 15:11:58` |
| queued | `strategy_tracking_snapshot_refresh` | 35 | 1 | `2026-06-11 15:12:25` | `2026-06-11 15:12:25` |
| queued | `data_quality_sla_refresh` | 22 | 2 | `2026-06-10 07:01:31` | `2026-06-11 07:01:19` |
| failed | `analytics_export_*` | 900 | 8 | `2026-06-08 05:14:02` | `2026-06-08 05:14:14` |
| failed | `monitor_snapshot_refresh` | 60 | 584 | `2026-05-07 08:49:56` | `2026-06-08 07:28:23` |
| failed | `a_key_level_materialization_refresh` | 45 | 457 | `2026-06-02 08:30:34` | `2026-06-03 15:21:01` |
| failed | `low_buy_materialization_refresh` | 35 | 283 | `2026-05-26 08:26:30` | `2026-06-11 08:59:53` |
| failed | `low_buy_materialization_refresh` | 30 | 424 | `2026-06-08 07:05:33` | `2026-06-11 13:43:35` |
| failed | `low_buy_materialization_refresh` | 24 | 146 | `2026-06-10 07:01:31` | `2026-06-11 09:01:00` |

Last 24h high-volume groups:

| Task type | Status | Count | Latest |
|---|---|---:|---|
| `low_buy_materialization_refresh` | succeeded | 714 | `2026-06-11 14:58:27` |
| `strategy_tracking_snapshot_refresh` | succeeded | 431 | `2026-06-11 15:11:58` |
| `market_quote_cache_refresh` | succeeded | 385 | `2026-06-11 07:07:11` |
| `hermes_platform_autopilot` | succeeded | 292 | `2026-06-11 15:11:46` |
| `a_key_level_materialization_refresh` | succeeded | 230 | `2026-06-11 15:11:46` |
| `low_buy_materialization_refresh` | failed | 230 | `2026-06-11 13:43:35` |
| `market_pulse_refresh` | succeeded | 215 | `2026-06-11 14:58:42` |
| `monitor_snapshot_refresh` | succeeded | 129 | `2026-06-11 14:59:19` |
| `latest_data_watchdog` | succeeded | 98 | `2026-06-11 15:11:46` |

## Runtime Environment Flags

| Container | Relevant current values |
|---|---|
| `tquant-runtime-worker-mysql` | `PLATFORM_AUTOPILOT_ENABLED=true`, `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=false`, `RUNTIME_WORKER_EMBED_SCHEDULER=false`, startup prewarm disabled |
| `tquant-runtime-scheduler-mysql` | `MARKET_REVIEW_ENABLED=true`, `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=false`, `RUNTIME_WORKER_EMBED_SCHEDULER=false`, startup prewarm disabled |
| `tquant-app-mysql` | `PLATFORM_AUTOPILOT_ENABLED=false`, `RUNTIME_BACKGROUND_JOBS_ENABLED=false`, `TQUANT_ANALYTICS_ENABLED=false`, `APP_WORKERS=1` |

## HTTP/API Verification

| URL | Result | Notes |
|---|---|---|
| `http://127.0.0.1:18090/readyz` | `200`, `0.045s` | database/frontend checks true |
| `https://43.143.243.97/readyz` | `200`, `0.016s` | IP HTTPS reachable |
| `https://weisilianghua.cloud/readyz` | `200`, `0.140s` | domain reachable in this baseline |
| `http://127.0.0.1:18090/api/monitor` | `404`, `0.012s` | planned alias is not a real endpoint |
| `http://127.0.0.1:18090/api/priority-board` | `404`, `0.004s` | planned alias is not a real endpoint |
| `http://127.0.0.1:18090/api/monitor/snapshot` | `401`, `0.005s` | actual protected monitor endpoint exists |
| `http://127.0.0.1:18090/api/screeners/low-buy/priority-board` | `401`, `0.003s` | actual protected priority endpoint exists |
| `http://127.0.0.1:18090/api/runtime-tasks/summary` | `401`, `0.003s` | admin endpoint protected |
| `http://127.0.0.1:18090/next/monitor` | `200`, `0.012s` | SPA shell renders |
| `http://127.0.0.1:18090/next/monitor/market` | `200`, `0.006s` | SPA shell renders |
| `http://127.0.0.1:18090/next/strategy-tracking` | `200`, `0.011s` | SPA shell renders |

## Candidate Non-Core Stops

| Item | Recommendation | Evidence | Expected impact |
|---|---|---|---|
| `PLATFORM_AUTOPILOT_ENABLED` on runtime worker | set false | 292 succeeded `hermes_platform_autopilot` tasks in 24h | reduce non-core queue churn |
| `RUNTIME_LOW_PRIORITY_TASKS_PAUSED` | set true | failed analytics/backtest/research tasks exist; low-priority pause currently false | prevent research/analytics/data repair tasks from claiming runtime capacity |
| `MARKET_REVIEW_ENABLED` | set false unless user depends on reports | market review enabled and ran 2 times | stop optional review reports |
| standalone `runtime-scheduler` | consolidate after D4 observation | 329.5MiB constant memory | save about 300-400MiB after embedded scheduler is proven |
| `analytics-worker` | keep on-demand | already exited 137 | avoid reintroducing memory pressure |
| `backtest-worker` | keep removed/on-demand | no running container | avoid research load on cloud |
| Prometheus/Grafana | keep stopped | already exited | no core functional impact |

## Risks

| Severity | Finding | Evidence | Impact |
|---|---|---|---|
| P1 | Memory headroom is critically low | available memory `251MiB`, swap used `945MiB` | API/page latency and worker stability risk |
| P1 | Runtime worker is near resource limit | `91.33% CPU`, `722.5MiB / 768MiB` | core materialization may contend with Web/MySQL |
| P1 | MySQL is at memory limit | `1004MiB / 1GiB` | DB pressure can amplify API latency |
| P2 | Non-core autopilot still runs in worker | `PLATFORM_AUTOPILOT_ENABLED=true`, 292 successes in 24h | avoidable worker/DB churn |
| P2 | Low-priority pause not active | worker/scheduler `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=false` | analytics/research/data repair can compete with core tasks |
| P2 | Historical failed tasks are large | `monitor_snapshot_refresh` 584 failed, key-level 457 failed, low-buy failed groups total 853 | observability noise; cleanup/archival requires separate authorization |
| P3 | Planned API aliases are not valid | `/api/monitor` and `/api/priority-board` return 404 | scripts should use real endpoints or page/API checks |

## No Write Operations

D0 did not modify remote `.env`, compose files, database rows, containers, images, volumes, nginx, or system services. The only write is this local Markdown report.

## Decision

Proceed to D1-D3 local implementation, then D4 authorized non-core stop. The D0 evidence supports immediate resource contention mitigation because the server is already in swap pressure and the worker is close to its memory/CPU limits.

## D4 Authorized Non-Core Stop - 2026-06-11 23:39 CST

### Pre-Change Snapshot

| Metric | Value | Status |
|---|---:|---|
| Time | `2026-06-11 23:39:22 +0800` | observed |
| Load average | `1.59 / 1.68 / 1.43` | elevated but usable |
| Memory | `3723MiB total / 3322MiB used / 401MiB available` | risk |
| Swap | `1987MiB total / 1046MiB used` | risk |
| MySQL memory | `1022MiB / 1GiB` | P1, at limit |
| runtime worker memory | `666MiB / 768MiB` | risk |
| runtime scheduler memory | `358.1MiB / 640MiB` | consolidation candidate |
| `/readyz` | `200`, `0.082s` | ok |

Pre-change `.env` had startup prewarm disabled, but did not explicitly set `PLATFORM_AUTOPILOT_ENABLED`, `RUNTIME_LOW_PRIORITY_TASKS_PAUSED`, or `MARKET_REVIEW_ENABLED`.

### Executed Write Operations

User had already granted execution authorization for the current scheme. The D4 operation was limited to non-core stop flags and controlled recreation of the Python app/runtime containers:

| Item | Value |
|---|---|
| Remote env backup | `/home/ubuntu/gupiao-upload/.env.resource-stop-backup.20260611233954` |
| Updated flags | `PLATFORM_AUTOPILOT_ENABLED=false`, `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true`, `MARKET_REVIEW_ENABLED=false`, `RUNTIME_STARTUP_CACHE_PREWARM_ENABLED=false`, `RUNTIME_STARTUP_HISTORY_PREWARM_ENABLED=false` |
| Recreated containers | `app`, `runtime-worker`, `runtime-scheduler` via `docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate app runtime-worker runtime-scheduler` |
| Not touched | MySQL, Redis, Go hot-read services, Go scan worker, frontend/nginx, Docker cleanup, DB data, nginx/systemd |

This keeps monitor,行情缓存,低吸榜,priority board,策略追踪 on cloud, while disabling non-core autopilot/research-style load and low-priority task execution.

### Immediate Post-Check

| Metric | Before D4 | After D4 | Result |
|---|---:|---:|---|
| Available memory | `401MiB` | `1173MiB` | improved |
| Swap used | `1046MiB` | `485MiB` | improved |
| app memory | n/a | `222.5MiB / 768MiB` | normal |
| runtime worker memory | `666MiB / 768MiB` | `194.5MiB / 768MiB` | improved after restart and low-priority pause |
| runtime scheduler memory | `358.1MiB / 640MiB` | `152.3MiB / 640MiB` | improved after restart and market review off |
| MySQL memory | `1022MiB / 1GiB` | `1023MiB / 1GiB` | still P1 |
| `/readyz` | `200`, `0.082s` | `200`, `0.195s` | available |
| protected monitor/priority APIs | n/a | `401`, fast | expected auth guard |

Confirmed container env:

| Container | Confirmed values |
|---|---|
| `tquant-runtime-worker-mysql` | `PLATFORM_AUTOPILOT_ENABLED=false`, `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true`, startup prewarm false, `RUNTIME_WORKER_EMBED_SCHEDULER=false` |
| `tquant-runtime-scheduler-mysql` | `MARKET_REVIEW_ENABLED=false`, `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true`, startup prewarm false, `RUNTIME_WORKER_EMBED_SCHEDULER=false` |

### P1 Incident During D4 Observation

At `2026-06-11 23:40:54 +0800`, immediately after a heavier runtime task aggregate query, the kernel reported MySQL cgroup OOM:

```text
Memory cgroup out of memory: Killed process 536963 (mysqld) ... anon-rss:977468kB
```

The MySQL container restarted and recovered automatically. `/readyz` returned `200` shortly after recovery. This confirms the D0/D4 finding that MySQL's previous `1GiB` limit was too tight and could still interrupt service even after non-core worker load was reduced.

## D6 MySQL Memory Stabilization - 2026-06-11 23:42 CST

Because D4 surfaced a real MySQL OOM, the next action was a minimal MySQL resource-limit stabilization. No schema, DB rows, indexes, buffer pool variables, or query code were changed.

| Item | Value |
|---|---|
| Remote env backup | `/home/ubuntu/gupiao-upload/.env.mysql-memory-backup.20260611234239` |
| Updated flags | `MYSQL_MEM_LIMIT=1536m`, `MYSQL_MEMSWAP_LIMIT=2048m` |
| Recreated containers | `mysql` only via `docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate mysql` |
| Not touched | DB data, MySQL config file, Redis, Web, Go services, runtime containers, Docker cleanup |

Post-D6 MySQL became healthy in 3 checks:

| Metric | Value | Status |
|---|---:|---|
| MySQL inspect | `restart=0 oom=false status=running health=healthy` | ok |
| MySQL memory limit | `1.5GiB` | increased |
| MySQL memswap limit | `2GiB` | increased |
| MySQL memory at first post-check | `613.8MiB / 1.5GiB` | ok |
| MySQL memory at 23:45 | `845MiB / 1.5GiB` | watch |
| InnoDB buffer pool | `536870912` bytes | unchanged |
| `max_connections` | `120` | unchanged |
| `Threads_connected` | `9` | normal |
| `Threads_running` | `2` | normal |
| `Slow_queries` | `5` | low but watch |

## Post-D6 Read-Only Stability Snapshot - 2026-06-11 23:46 CST

| Area | Result |
|---|---|
| uptime/load | `up 3 days, 12:30`, load `0.99 / 1.18 / 1.31` |
| memory | `3723MiB total / 2828MiB used / 894MiB available` |
| swap | `1987MiB total / 277MiB used` |
| disk | root `32G / 59G, 56%`; inode `392K / 3.8M, 11%` |
| container health | MySQL/app/runtime-worker/runtime-scheduler/frontend/Go/Redis all healthy |
| OOM after 23:42 | no new kernel OOM entries observed |

Container resource sample:

| Container | CPU | Memory | Status |
|---|---:|---:|---|
| `tquant-mysql` | `19.65%` | `845MiB / 1.5GiB` | healthy |
| `tquant-runtime-worker-mysql` | `66.13%` | `555.3MiB / 768MiB` | healthy, still CPU-active |
| `tquant-runtime-scheduler-mysql` | `26.26%` | `234.3MiB / 640MiB` | healthy |
| `tquant-app-mysql` | `0.12%` | `226MiB / 768MiB` | healthy |
| `tquant-redis` | `0.58%` | `3.938MiB / 128MiB` | healthy |
| Go hot-read/BFF/scan | `0.00%` sample | `<8MiB each` | healthy |
| frontend/nginx | `0.00%` | `3.008MiB / 128MiB` | healthy |

HTTP/API checks used the actual deployed entrypoint `18090`:

| URL | Result | Notes |
|---|---|---|
| `http://127.0.0.1:18090/readyz` | `200`, `0.003856s` | ok |
| `https://43.143.243.97/readyz` | `200`, `0.015088s` | ok |
| `https://weisilianghua.cloud/readyz` | `200`, `0.015647s` | ok in this sample |
| `/api/monitor/snapshot` | `401`, `0.002951s` | expected auth guard |
| `/api/screeners/low-buy/priority-board` | `401`, `0.002767s` | expected auth guard |
| `/api/runtime-tasks/summary` | `401`, `0.003801s` | expected admin guard |
| `/api/settings` | `401`, `0.003533s` | expected auth guard |

Frontend shell checks:

| Page | Result |
|---|---|
| `/next/monitor` | `200`, `0.005232s`, 847 bytes |
| `/next/monitor/market` | `200`, `0.003585s`, 847 bytes |
| `/next/paper` | `200`, `0.003638s`, 847 bytes |
| `/next/strategy-tracking` | `200`, `0.005443s`, 847 bytes |
| `/next/analysis` | `200`, `0.003859s`, 847 bytes |
| `/next/backtest` | `200`, `0.003718s`, 847 bytes |
| `/next/data` | `200`, `0.004572s`, 847 bytes |
| `/next/settings` | `200`, `0.003779s`, 847 bytes |

Runtime task sample used actual DB name `t_quant`:

| Task type | Status | Count in last 2h | Latest |
|---|---|---:|---|
| `latest_data_watchdog` | succeeded | 21 | `2026-06-11 15:39:03` |
| `low_buy_materialization_refresh` | succeeded | 28 | `2026-06-11 14:58:27` |
| `market_pulse_refresh` | succeeded | 4 | `2026-06-11 14:58:42` |
| `monitor_snapshot_refresh` | succeeded | 5 | `2026-06-11 14:59:19` |
| `strategy_tracking_snapshot_refresh` | succeeded | 118 | `2026-06-11 15:46:12` |
| `strategy_tracking_snapshot_refresh` | queued | 1 | `2026-06-11 15:46:21` |

Current non-terminal queue sample:

| Status | Count | Oldest | Latest |
|---|---:|---|---|
| queued | 3 | `2026-06-10 07:01:31` | `2026-06-11 15:46:21` |
| running | 1 | `2026-06-11 15:46:11` | `2026-06-11 15:46:12` |

Heartbeat source note: worker/component heartbeats are stored in `system_settings`, not a separate heartbeat table. Current values at `23:48 CST`:

| Key | Value summary |
|---|---|
| `platform_component.heartbeat.runtime-worker` | `worker_id=runtime-758c134e30fc`, `updated_at=2026-06-11T15:48:26`, `status=running` |
| `runtime_worker.heartbeat` | same runtime-worker payload |
| `platform_component.heartbeat.runtime-scheduler` | `worker_id=runtime-scheduler`, `updated_at=2026-06-11T15:48:36`, `status=running` |
| `platform_component.heartbeat.analytics-worker` | stale from `2026-06-09T08:15:10`; container intentionally not running |
| `platform_component.heartbeat.backtest-worker` | stale from `2026-06-09T11:07:26`; container intentionally not running |

## Short Follow-Up Observation - 2026-06-11 23:49 CST

| Area | Result | Interpretation |
|---|---|---|
| load | `1.12 / 1.14 / 1.27` | usable |
| memory | `3723MiB total / 3107MiB used / 615MiB available` | improved vs D0, but headroom is shrinking again |
| swap | `1987MiB total / 370MiB used` | still far below D0, but not zero |
| MySQL | `1.01GiB / 1.5GiB`, `restart=0`, `oom=false`, healthy | D6 limit is absorbing prior OOM pressure |
| runtime worker | `708.8MiB / 768MiB`, `restart=3`, `oom=false`, healthy | still close to limit during materialization |
| runtime scheduler | `284.2MiB / 640MiB`, CPU sample `71.18%`, healthy | active scheduler/provider work is still expensive |
| `/readyz` local/domain | local `200` in `0.005s`; domain `200` in `0.020s` | available |
| OOM after 23:42 | none | D6 appears effective in short window |

Runtime queue at `23:49 CST`:

| Status | Task | Evidence |
|---|---|---|
| running | `a_key_level_materialization_refresh` | id `46158`, priority `45`, worker `runtime-758c134e30fc`, progress `5` |
| queued | `data_quality_sla_refresh` | ids `41913`, `44330`, old non-core/data-quality backlog |

Recent 15-minute successes:

| Task type | Succeeded count | Latest |
|---|---:|---|
| `strategy_tracking_snapshot_refresh` | 20 | `2026-06-11 15:49:57` |
| `a_key_level_materialization_refresh` | 6 | `2026-06-11 15:49:23` |
| `latest_data_watchdog` | 2 | `2026-06-11 15:48:14` |
| `hermes_platform_autopilot` | 1 | `2026-06-11 15:38:56`; likely queued before D4 stop/recreate |

Log evidence:

| Component | Signal |
|---|---|
| runtime worker | transient MySQL connection error immediately after MySQL recreate: `Can't connect to server on 'mysql' (115)`; process restarted and is now healthy |
| runtime scheduler | repeated market provider circuit-open/timeouts and EastMoney/AkShare fallback failures around `15:47-15:49 UTC`; this explains the high scheduler CPU sample and is a separate provider/network pressure source |

This follow-up strengthens the D5 gate decision: D5 should not be executed immediately after D6, because runtime worker memory has already returned near its container limit and scheduler/provider work is still active. The next safe step is observation and provider/task-pressure diagnosis, not collapsing scheduler into the worker in the same short window.

## Updated Risk Register

| Severity | Finding | Evidence | Impact | Decision |
|---|---|---|---|---|
| P1 | MySQL old `1GiB` memory limit caused OOM | kernel OOM at `23:40:54`; MySQL killed at ~`977MiB` anon RSS | short DB interruption and possible API stalls | mitigated by D6 limit increase; observe |
| P1 | Worker remains close to memory limit during materialization | `708.8MiB / 768MiB` at `23:49`, running `a_key_level_materialization_refresh` | can still contend or OOM under heavier jobs | keep D4 flags; observe longer before D5 |
| P2 | Standalone scheduler still consumes memory and CPU | `284.2MiB / 640MiB`, CPU sample `71.18%`, provider timeout/circuit-open logs | consolidation can free memory but may move pressure into worker | D5 pending; diagnose provider/timeouts first |
| P2 | D5 heartbeat acceptance must use settings-backed source | current source is `system_settings` keys `runtime_worker.heartbeat` and `platform_component.heartbeat.*` | wrong probe can miss duplicate scheduler or stale worker | D5 must verify `runtime-scheduler` worker id becomes `runtime-worker-embedded-scheduler` |
| P2 | Historical queue residue remains | 3 queued, oldest `2026-06-10 07:01:31`; failed history from D0 | observability noise and possible stale work | no cleanup this round; requires separate authorization |
| P3 | First post-D6 probe initially used wrong local port and DB name | corrected probes use `18090` and `t_quant` | no product impact | report only corrected evidence |

## Current Decision After D4/D6

D4 stop profile remains active and has materially reduced memory/swap pressure. D6 MySQL memory limit increase remains active and directly addresses the observed MySQL cgroup OOM.

D5 embedded scheduler is not executed yet. Reason: D4 observation exposed a real MySQL OOM, and the plan requires scheduler consolidation only after the stop profile is stable. Before D5, run at least one longer stability window and preferably a complete trading-day observation after the MySQL limit increase.

## Rollback Commands Not Executed

These commands are recorded for controlled rollback only; they were not executed in this report update.

D4 rollback:

```bash
cd /home/ubuntu/gupiao-upload
cp .env.resource-stop-backup.20260611233954 .env
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate app runtime-worker runtime-scheduler
```

D6 rollback:

```bash
cd /home/ubuntu/gupiao-upload
cp .env.mysql-memory-backup.20260611234239 .env
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate mysql
```

D6 rollback is not recommended unless the larger MySQL memory limit causes new host-level pressure; the prior `1GiB` limit has direct OOM evidence.

## Next Steps Requiring Authorization / Gate

| Step | Action | Gate |
|---|---|---|
| D4 observe | Continue read-only checks for memory/swap, OOM, runtime queue, `/readyz`, protected API latency | no new authorization needed for read-only |
| D5 prepare | Use `system_settings` heartbeat keys in acceptance checks; verify current standalone scheduler and later embedded scheduler worker id | local/read-only first |
| D5 execute | Enable `RUNTIME_WORKER_EMBED_SCHEDULER=true`, disable standalone scheduler, remove `tquant-runtime-scheduler-mysql` only through explicit embedded deploy path | wait for stability window and user confirmation if doing live |
| D6 deepen | If p95/API or task evidence still shows bottleneck, analyze MySQL slow queries, index coverage, connection pool, and hot-read paths | query-only first; schema/query changes need separate implementation gate |
| D7 | Treat domain TLS/SNI/RST as separate network-entry workstream | separate plan |

## D6 Root-Cause Follow-Up - 2026-06-11 23:54 CST

Read-only follow-up showed the service remained available, but runtime pressure had not been eliminated:

| Area | Evidence | Interpretation |
|---|---|---|
| memory | `3723MiB total / 3129MiB used / 593MiB available`; swap `329MiB` | better than D0, but still tight |
| MySQL | `1.015GiB / 1.5GiB`, `restart=0`, `oom=false`, healthy | D6 limit held; no new OOM after `23:42` |
| runtime worker | `767.9MiB / 768MiB`, CPU `69.00%` | worker can still hit container memory ceiling |
| runtime scheduler | `252.5MiB / 640MiB` | scheduler is healthy but still contributes background pressure |
| HTTP | `/readyz` local/IP/domain `200`; protected APIs return expected `401` in ~3-5ms | online entry is usable |
| frontend shell | `/next/monitor`, `/next/monitor/market`, `/next/strategy-tracking`, `/next/analysis`, `/next/backtest`, `/next/data`, `/next/settings` all `200` | SPA shell reachable |

Task evidence:

| Task type | 2h succeeded count | Duration evidence |
|---|---:|---|
| `strategy_tracking_snapshot_refresh` | `119+` | average about `1.74s`, max `16s` |
| `a_key_level_materialization_refresh` | `48+` | average about `124s`, max `1406s` |
| `latest_data_watchdog` | `22` | short duration |
| `low_buy_materialization_refresh` | `28` | average about `33.68s`, max `267s` |

Root-cause judgment:

- The queue's existing idempotency only dedupes non-terminal active tasks. After a task succeeds, `active_idempotency_key` is cleared, so the scheduler can enqueue and rerun the same trade-date work on every interval.
- `a_key_level_materialization_refresh:2026-06-11` and `strategy_tracking_snapshot_refresh:2026-06-11:30` repeated heavily in the 2h window.
- This is a resource-contention problem, not a production strategy semantics problem. It does not require changing `strategy_policy.py`, `production_score`, or priority-board ordering.

Implemented local D6 code mitigation, not deployed yet:

| File | Change |
|---|---|
| `backend/app/services/latest_data_close_refresh.py` | A-key materialization and strategy-tracking snapshot enqueue now reuse an existing succeeded same-idempotency task instead of creating another row. |
| `backend/tests/test_latest_data_close_refresh.py` | Added coverage proving succeeded A-key/strategy-tracking tasks are reused and no duplicate runtime rows are created. |

Verification:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_latest_data_close_refresh.py backend/tests/test_key_levels_materialization_readiness.py::test_after_close_enqueues_a_key_level_materialization_with_stable_idempotency_key
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_platform_budget_verifier.py backend/tests/test_runtime_task_queue.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_independent_runtime_components.py
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py
```

Results: `14 passed`, `73 passed`, `32 passed`; only the existing LibreSSL urllib3 warning appeared.

D6 deployment gate at this observation point:

- This mitigation was committed locally only after review; it had not been deployed in this `23:54 CST` observation window.
- Deploying it should reduce repeated worker-heavy materialization after the first successful same-day run.
- After deployment, observe whether `a_key_level_materialization_refresh` drops from dozens per 2h to at most one successful same-day run plus any active/retry case.
- D5 scheduler embed should still wait until this D6 mitigation is deployed and observed, because collapsing scheduler into a worker already near `768MiB` would increase risk.

## D6 Minimal Online Code Deploy - 2026-06-12 00:10 CST

The repeated close-refresh dedupe fix was deployed through the narrowest available live path: backup and upload one Python source file, rebuild the shared Python image, and recreate only `runtime-scheduler`. The target source of the repeated enqueue was the scheduler. `app`, `runtime-worker`, MySQL, Redis, Go services, frontend/nginx, DB data, nginx, systemd, volumes, and cleanup paths were not touched in this step.

### Executed Write Operations

| Item | Value |
|---|---|
| Remote source backup | `/home/ubuntu/gupiao-upload/backend/app/services/latest_data_close_refresh.py.d6-dedupe-backup.20260612000708` |
| Uploaded source | `/home/ubuntu/gupiao-upload/backend/app/services/latest_data_close_refresh.py` |
| Backup source size | `15417` bytes |
| Uploaded source size | `16360` bytes |
| Uploaded source checksum | `98572760c7b9117045935e74561ef257a36ea3d66afa1ba27c9cdb3bf26c2680` |
| Build command | `sudo docker compose -f docker-compose.mysql.yml build runtime-scheduler` |
| Recreate command | `sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --no-build --force-recreate runtime-scheduler` |
| Scheduler new image | `sha256:02b58e3659d76ebbc9ac68a06b5369ef30f356cb363c3b1cc9f971840372ef0f` |
| Scheduler started at | `2026-06-11T16:10:54.689527959Z` (`2026-06-12 00:10:54 CST`) |

### Container Scope Verification

| Container | Image / start evidence | Result |
|---|---|---|
| `tquant-runtime-scheduler-mysql` | image `sha256:02b58e...`, started `2026-06-11T16:10:54Z`, `restart=0`, `oom=false`, `health=healthy` | recreated as intended |
| `tquant-runtime-worker-mysql` | image `sha256:e98cc59...`, started `2026-06-11T15:42:45Z`, `health=healthy` | unchanged in this step |
| `tquant-app-mysql` | image `sha256:e98cc59...`, started `2026-06-11T15:40:10Z`, `health=healthy` | unchanged |
| `tquant-mysql` | image `sha256:669b2d...`, started `2026-06-11T15:42:42Z`, `health=healthy` | unchanged |
| `tquant-redis` | image `sha256:286bd4...`, started `2026-06-09T08:04:11Z`, `health=healthy` | unchanged |
| Go BFF/read/scan | started `2026-06-11T13:44:13-19Z`, all healthy | unchanged |
| `tquant-frontend-web` | started `2026-06-11T13:44:20Z`, healthy | unchanged |

### Code Load Verification

The scheduler container loaded the expected dedupe code:

```text
has_dedupe True
has_strategy_tracking_helper True
def _enqueue_unless_succeeded(db: Session, payload: RuntimeTaskCreate) -> RuntimeTaskOut:
    if payload.idempotency_key and hasattr(db, "execute"):
        existing = _succeeded_task(db, payload.idempotency_key)
        if existing is not None:
            return RuntimeTaskQueue(db).get(int(existing.id))
    return RuntimeTaskQueue(db).enqueue(payload)
```

### Post-Deploy Health Snapshot

| Area | Evidence | Result |
|---|---|---|
| host load after cooldown | `0.54 / 1.05 / 1.04` | acceptable |
| memory after cooldown | `3723MiB total / 2584MiB used / 1139MiB available` | materially better than D0 |
| swap after build cooldown | `919MiB used / 1987MiB` | elevated by live build; observe |
| root disk / inode | `/` `60%`; inode `12%` | ok |
| MySQL | `622.6MiB / 1.5GiB`, `Threads_connected=10`, `Threads_running=2`, `Slow_queries=14` | healthy, no new OOM |
| runtime worker | `712.1MiB / 768MiB` | still close to limit; keep D5 gated |
| runtime scheduler | `342.9MiB / 640MiB` | healthy after recreate |
| Redis | `used_memory=1.28M`, `evicted_keys=0`, `connected_clients=5`, `dbsize=8` | healthy |
| OOM since scheduler deploy | no kernel OOM entries since `2026-06-12 00:10:00` | ok |

HTTP/API checks:

| URL | Result | Notes |
|---|---|---|
| `http://127.0.0.1:18090/readyz` | `200`, `0.031632s` | ok |
| `http://127.0.0.1:18090/api/monitor/snapshot` | `401`, `0.006349s` | expected auth guard |
| `http://127.0.0.1:18090/api/screeners/low-buy/priority-board` | `401`, `0.008704s` | expected auth guard |
| `http://127.0.0.1:18090/api/runtime-tasks/summary` | `401`, `0.004691s` | expected admin guard |
| `/next/monitor` | `200`, `0.006479s` | SPA shell reachable |
| `/next/monitor/market` | `200`, `0.004981s` | SPA shell reachable |
| `/next/strategy-tracking` | `200`, `0.003997s` | SPA shell reachable |
| `https://43.143.243.97/readyz` | local `200`, `0.107719s`; server-side `200`, `0.063657s` | ok |
| `https://weisilianghua.cloud/readyz` | local TLS reset once; server-side `200`, `0.275077s` |公网链路/SNI风险仍未解决 |
| `https://www.aigupiao.me/readyz` | local timeout; server-side connect failed | not a confirmed live entry |

### Runtime Queue Verification

After the scheduler was recreated, the dedupe-sensitive same-day tasks stopped being repeatedly created:

| Window | Evidence | Interpretation |
|---|---|---|
| last 20 minutes at `00:14:57 CST` | `strategy_tracking_snapshot_refresh` succeeded `8`, latest `15:59:40 UTC`; `a_key_level_materialization_refresh` succeeded `4`, latest `15:59:40 UTC` | these were pre-deploy rows |
| since scheduler deploy at `16:10:54 UTC` | only `low_buy_materialization_refresh` succeeded `1`, created `16:11:31 UTC` | no new A-key or strategy-tracking duplicate rows after deploy |
| latest sensitive rows | newest A-key `id=46184`, created `15:59:40 UTC`; newest strategy-tracking `id=46185`, created `15:59:40 UTC` | dedupe working for the repeated close-refresh path |
| non-terminal queue | old `data_quality_sla_refresh` ids `41913`, `44330` only | no new core backlog from this deploy |

Heartbeat source remains `system_settings`:

| Key | Updated at | Value summary |
|---|---|---|
| `platform_component.heartbeat.runtime-scheduler` | `2026-06-11 16:15:59` | `worker_id=runtime-scheduler`, `status=running` |
| `platform_component.heartbeat.runtime-worker` | `2026-06-11 16:15:57` | `worker_id=runtime-758c134e30fc`, `status=running` |
| `runtime_worker.heartbeat` | `2026-06-11 16:15:57` | same runtime-worker payload |

### Remaining Risk After Deploy

| Severity | Finding | Evidence | Decision |
|---|---|---|---|
| P1 | runtime worker memory remains close to the `768MiB` cap | `712.1MiB / 768MiB` after cooldown | do not execute D5 until a longer stability window passes |
| P1 | domain public path remains unstable from at least one client path | local `weisilianghua.cloud` returned TLS reset while server-side curl returned `200` | handle in D7 network-entry workstream |
| P2 | market provider failures continue | scheduler logs show EastMoney/AkShare timeouts/circuit-open warnings | separate provider/network-pressure diagnosis |
| P2 | swap is still non-zero after live image build | `919MiB` at cooldown sample | observe after build pressure decays; not enough for D5 approval |

### Rollback Command Not Executed

Recorded for controlled rollback only:

```bash
cd /home/ubuntu/gupiao-upload
cp backend/app/services/latest_data_close_refresh.py.d6-dedupe-backup.20260612000708 backend/app/services/latest_data_close_refresh.py
sudo docker compose -f docker-compose.mysql.yml build runtime-scheduler
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --no-build --force-recreate runtime-scheduler
```

Rollback is not recommended unless the scheduler shows new enqueue regressions or health failures. The deployed change only affects duplicate enqueue behavior after a same-idempotency task has already succeeded; it does not change strategy policy, scoring, or priority-board ordering.

## D5 Gate Recheck And D6 Worker Guard - 2026-06-12 00:22 CST

D5 was not executed. Although the user had granted execution authorization, the plan requires a longer stable observation window after D6 and preferably a complete trading-day observation before collapsing the standalone scheduler into the runtime worker. Current evidence fails that gate because the runtime worker still has very little headroom.

### Read-Only Gate Evidence

| Area | Evidence | Interpretation |
|---|---|---|
| time | `2026-06-12 00:22:40 +0800` | about 12 minutes after scheduler dedupe deploy |
| load | `0.18 / 0.41 / 0.71` | host load is low |
| memory | `3723MiB total / 2581MiB used / 1141MiB available` | host memory better than D0 |
| swap | `905MiB used / 1987MiB` | still materially used |
| disk / inode | `/` `60%`; inode `12%` | ok |
| MySQL | `640.1MiB / 1.5GiB`, `Threads_connected=9`, `Threads_running=2`, `Max_used_connections=12`, `Slow_queries=15` | stable after D6 limit |
| runtime worker | `752.5MiB / 768MiB`, `97.98%`, CPU sample `75.72%` | D5 gate fail |
| runtime scheduler | `365.2MiB / 640MiB`, `57.06%` | still active but isolated |
| Redis | `used_memory=1.33M`, `evicted_keys=0`, `connected_clients=5`, `dbsize=9` | ok |
| OOM since D6 | no kernel OOM entries since `2026-06-12 00:10:00` | ok |

Three additional samples confirmed the worker memory pressure is sustained, not a single stats spike:

| Time CST | Worker | Scheduler | MySQL | Notes |
|---|---:|---:|---:|---|
| `00:23:08` | `713MiB / 768MiB`, `92.84%` | `412.9MiB / 640MiB`, `64.51%` | `644.8MiB / 1.5GiB` | scheduler healthcheck caused transient CPU spike |
| `00:23:40` | `713MiB / 768MiB`, `92.84%` | `366.6MiB / 640MiB`, `57.28%` | `645.1MiB / 1.5GiB` | stable but still high worker RSS |
| `00:24:12` | `713MiB / 768MiB`, `92.84%` | `365.5MiB / 640MiB`, `57.11%` | `645.5MiB / 1.5GiB` | D5 remains unsafe |

Runtime task evidence after D6 code deploy remains positive:

| Query | Result | Interpretation |
|---|---|---|
| all tasks since `2026-06-11 16:10:54 UTC` | only `low_buy_materialization_refresh` succeeded `1` | repeated A-key and strategy-tracking rows stopped |
| dedupe-sensitive tasks since deploy | no new `a_key_level_materialization_refresh`, `strategy_tracking_snapshot_refresh`, `latest_data_watchdog`, or `hermes_platform_autopilot` rows | D6 dedupe is working in the short window |
| queued/running | old `data_quality_sla_refresh` ids `41913`, `44330` only | no new core backlog |

HTTP/API and page checks:

| URL | Result |
|---|---|
| `http://127.0.0.1:18090/readyz` | `200`, `0.003803s` |
| `http://127.0.0.1:18090/api/monitor` | `404`, expected legacy alias absence |
| `http://127.0.0.1:18090/api/monitor/snapshot` | `401`, expected auth guard |
| `http://127.0.0.1:18090/api/priority-board` | `404`, expected legacy alias absence |
| `http://127.0.0.1:18090/api/screeners/low-buy/priority-board` | `401`, expected auth guard |
| `http://127.0.0.1:18090/api/runtime-tasks/summary` | `401`, expected admin guard |
| `/next/monitor` | `200`, `0.003445s` |
| `/next/monitor/market` | `200`, `0.004109s` |
| `/next/strategy-tracking` | `200`, `0.003659s` |

Heartbeat source is current and still shows standalone scheduler mode:

| Key | Updated at | Worker id |
|---|---|---|
| `platform_component.heartbeat.runtime-scheduler` | `2026-06-11 16:22:29` | `runtime-scheduler` |
| `platform_component.heartbeat.runtime-worker` | `2026-06-11 16:22:43` | `runtime-758c134e30fc` |
| `runtime_worker.heartbeat` | `2026-06-11 16:22:43` | `runtime-758c134e30fc` |

### Decision

| Decision | Status | Reason |
|---|---|---|
| Execute D5 embedded scheduler now | no | would move scheduler work into a worker already at `92-98%` of memory limit |
| Keep standalone scheduler isolated | yes | contains scheduler/provider pressure away from the worker |
| Continue D6 worker root-cause mitigation | yes | worker RSS remains high after duplicate-task fix |
| Deploy or enable new worker recycle guard now | no | code is local only in this section; live enablement requires a focused worker deploy and post-deploy observation |

### Local D6 Worker Guard Implemented

To address sustained worker RSS without changing strategy semantics, a default-off runtime worker recycle guard was added locally:

| File | Change |
|---|---|
| `backend/app/core/config.py` | Adds `runtime_worker_recycle_rss_mb: int = 0` default-off setting. |
| `backend/app/workers/runtime_worker.py` | After a task has completed and status has been written, checks current RSS; if RSS is at or above the configured threshold, exits with code `0` so Docker can restart a fresh worker process. |
| `docker-compose.mysql.yml` | Passes `RUNTIME_WORKER_RECYCLE_RSS_MB` into `runtime-worker`; default remains `0`. |
| `.env.docker.example`, `.env.deploy.local.example` | Documents the default-off guard. |
| `scripts/verify_platform_budget.py` | Reports warning `worker_recycle_rss_mb_disabled` when the guard is not enabled in resource-stabilization checks. |
| `docs/operations/cloud-core-worker-resource-runbook.md` | Adds enablement, rollback, and post-check commands. |

This guard does not interrupt running tasks and does not alter low-buy strategy policy, production scoring, or priority-board ordering. It is a process-lifetime guard at a task boundary.

### Local Verification

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_phase4_runtime_worker_tasks.py::test_runtime_worker_recycle_guard_defaults_off \
  backend/tests/test_phase4_runtime_worker_tasks.py::test_runtime_worker_recycle_guard_triggers_after_task \
  backend/tests/test_platform_budget_verifier.py::test_platform_budget_report_warns_when_worker_recycle_guard_disabled \
  backend/tests/test_independent_runtime_components.py::test_mysql_compose_keeps_web_light_and_workers_independent \
  backend/tests/test_cloud_performance_script.py::test_mysql_compose_exposes_low_priority_task_pause_to_workers

PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_platform_budget_verifier.py
```

Results: `5 passed`, `10 passed`; only the existing LibreSSL urllib3 warning appeared.

### Worker Guard Initial Rollout Command

This was the planned worker-only deployment command before live enablement:

```bash
cd /home/ubuntu/gupiao-upload
cp .env ".env.worker-recycle-backup.$(date +%Y%m%d%H%M%S)"
grep -q "^RUNTIME_WORKER_RECYCLE_RSS_MB=" .env \
  && sed -i "s/^RUNTIME_WORKER_RECYCLE_RSS_MB=.*/RUNTIME_WORKER_RECYCLE_RSS_MB=700/" .env \
  || printf "\nRUNTIME_WORKER_RECYCLE_RSS_MB=700\n" >> .env
sudo docker compose -f docker-compose.mysql.yml build runtime-worker
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --no-build --force-recreate runtime-worker
```

Rollback command:

```bash
cd /home/ubuntu/gupiao-upload
cp .env.worker-recycle-backup.YYYYMMDDHHMMSS .env
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate runtime-worker
```

## D6 Worker Recycle Guard Online Verification - 2026-06-12 00:47 CST

After the local guard implementation, a focused online worker rollout was applied and then verified read-only. The current live worker now has `RUNTIME_WORKER_RECYCLE_RSS_MB=700`, while the standalone scheduler remains separate and D5 embedded scheduler remains unexecuted.

### Current Online State

| Area | Evidence | Interpretation |
|---|---|---|
| time | `2026-06-12 00:47:49 CST` | current verification point |
| uptime/load | `up 3 days, 13:32`, load `0.25 / 0.31 / 0.38` | host load is low |
| memory | `3723MiB total / 2067MiB used / 1656MiB available` | materially better than D0/D4 |
| swap | `816MiB used / 1987MiB` | still non-zero; observe |
| root disk / inode | `/` `34G / 59G`, `61%`; inode `12%` | ok |
| MySQL | `626.7MiB / 1.5GiB`, restart `0`, `oom=false`, healthy | D6 MySQL limit holding |
| runtime worker | `162.1MiB / 768MiB`, restart `0`, `oom=false`, healthy | guard-enabled worker currently has headroom |
| runtime scheduler | `357.9MiB / 640MiB`, restart `0`, healthy | still standalone by design |
| app | `42.34MiB / 768MiB`, healthy | ok |
| OOM since `2026-06-12 00:00` | no kernel OOM entries | ok |

Current runtime-worker environment:

| Key | Value |
|---|---|
| `PLATFORM_AUTOPILOT_ENABLED` | `false` |
| `RUNTIME_LOW_PRIORITY_TASKS_PAUSED` | `true` |
| `RUNTIME_WORKER_EMBED_SCHEDULER` | `false` |
| `RUNTIME_WORKER_RECYCLE_RSS_MB` | `700` |
| `RUNTIME_BACKGROUND_ROLE` | `worker` |
| `RUNTIME_BACKGROUND_JOBS_ENABLED` | `false` |

Current runtime-scheduler environment:

| Key | Value |
|---|---|
| `MARKET_REVIEW_ENABLED` | `false` |
| `RUNTIME_LOW_PRIORITY_TASKS_PAUSED` | `true` |
| `RUNTIME_WORKER_EMBED_SCHEDULER` | `false` |
| `RUNTIME_BACKGROUND_ROLE` | `scheduler` |
| `RUNTIME_BACKGROUND_JOBS_ENABLED` | `true` |

### HTTP/API/Page Verification

| URL | Result |
|---|---|
| `http://127.0.0.1:18090/readyz` | `200`, `0.004068s` |
| `http://127.0.0.1:18090/api/monitor` | `404`, expected legacy alias absence |
| `http://127.0.0.1:18090/api/monitor/snapshot` | `401`, expected auth guard |
| `http://127.0.0.1:18090/api/priority-board` | `404`, expected legacy alias absence |
| `http://127.0.0.1:18090/api/screeners/low-buy/priority-board` | `401`, expected auth guard |
| `http://127.0.0.1:18090/api/runtime-tasks/summary` | `401`, expected admin guard |
| `/next/monitor` | `200`, `0.003194s` |
| `/next/monitor/market` | `200`, `0.004036s` |
| `/next/strategy-tracking` | `200`, `0.003709s` |

### Task And Heartbeat Verification

MySQL status:

| Metric | Value |
|---|---:|
| `Threads_connected` | `8` |
| `Threads_running` | `2` |
| `Slow_queries` | `15` |
| `max_connections` | `120` |
| `innodb_buffer_pool_size` | `536870912` |

Non-terminal queue:

| Status | Task type | Priority | Count | Oldest | Latest |
|---|---|---:|---:|---|---|
| queued | `data_quality_sla_refresh` | `22` | `2` | `2026-06-10 07:01:31` | `2026-06-11 07:01:19` |

Latest dedupe-sensitive core rows remain pre-D6-dedupe or the single post-deploy low-buy row:

| Task | Latest row evidence |
|---|---|
| `a_key_level_materialization_refresh` | latest `id=46184`, created `2026-06-11 15:59:40`, succeeded `16:00:44` |
| `strategy_tracking_snapshot_refresh` | latest `id=46185`, created `2026-06-11 15:59:40`, succeeded `15:59:43` |
| `low_buy_materialization_refresh` | latest `id=46186`, created `2026-06-11 16:11:31`, succeeded `16:12:02` |

Heartbeat source is `system_settings` with columns `key`, `value`, `updated_at`:

| Key | Updated at | Worker id |
|---|---|---|
| `platform_component.heartbeat.runtime-scheduler` | `2026-06-11 16:49:09` | `runtime-scheduler` |
| `platform_component.heartbeat.runtime-worker` | `2026-06-11 16:49:15` | `runtime-8a2ddf90d9f2` |
| `runtime_worker.heartbeat` | `2026-06-11 16:49:15` | `runtime-8a2ddf90d9f2` |

Worker logs for the last 30 minutes showed no recycle/error/OOM lines. Scheduler logs still showed provider pressure:

- repeated `market provider circuit open` for `akshare`, `eastmoney`, `openbb`, `local`
- `EastMoney first spot page failed`
- `AkShare stock spot fallback failed: Can not decode value starting with character '<'`
- one remote BFF market-read batch warning

### Current Decision

| Decision | Status | Reason |
|---|---|---|
| Keep D4/D6 stop profile | yes | memory and swap are materially better, core APIs/pages are available |
| Keep worker recycle guard enabled | yes | worker RSS has reset to a low baseline and the guard is task-boundary only |
| Execute D5 embedded scheduler now | no | worker has only been observed for a short post-rollout window; plan requires longer stability, preferably a full trading day |
| Treat provider failures as remaining P2 | yes | scheduler logs continue to show source/circuit pressure |

The D5 gate remains closed until a complete trading-day observation proves worker RSS, MySQL, swap, queue dedupe, and provider pressure are stable. The target embedded heartbeat after D5 would be `worker_id=runtime-worker-embedded-scheduler`; current heartbeat correctly remains `runtime-scheduler`.

### Rollback Command Not Executed

Recorded for controlled rollback only, using the live backup timestamp recorded during worker rollout:

```bash
cd /home/ubuntu/gupiao-upload
cp .env.worker-recycle-backup.20260612003237 .env
cp backend/app/core/config.py.d6-worker-recycle-backup.20260612003237 backend/app/core/config.py
cp backend/app/workers/runtime_worker.py.d6-worker-recycle-backup.20260612003237 backend/app/workers/runtime_worker.py
cp docker-compose.mysql.yml.d6-worker-recycle-backup.20260612003237 docker-compose.mysql.yml
sudo docker compose -f docker-compose.mysql.yml build runtime-worker
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --no-build --force-recreate runtime-worker
```

Rollback is not recommended unless worker recycle causes task loss, restart loops, or a regression in core task completion. No such regression is visible in the current verification window.

## D6 MySQL Runtime Root Cause Review - 2026-06-12 01:20 CST

Detailed report: `docs/reports/mysql-runtime-root-cause-review-2026-06-12.md`.

This D6 pass was read-only and did not execute `.env` changes, container restarts, DB writes, schema/index changes, cleanup, nginx/systemd changes, deployment, or cutover.

Current conclusion:

| Decision | Status | Reason |
|---|---|---|
| Execute D5 embedded scheduler | no | scheduler provider warnings remain active, swap is still non-zero, and MySQL slow-query evidence should be addressed before moving scheduler pressure into runtime-worker |
| Treat MySQL connections as root cause | no | `Threads_connected=9`, `Threads_running=2`, `max_connections=120` showed connection headroom |
| Treat daily bar read paths as P1 | yes | `daily_bar_snapshots` is the largest table and dominates slow digest time; coverage/group-by paths scan large ranges |
| Treat runtime task observability as P2 | yes | broad `runtime_tasks` summary/diagnostic queries examined about `45k` rows in the sample |
| Keep standalone scheduler for now | yes | provider timeout/circuit-open bursts should stay isolated until a complete trading-day gate passes |

Recommended next implementation work stays in D6, not D5:

1. Add or reuse a daily-bar coverage read model for latest complete trade date, recent complete dates, and stock count by trade date.
2. Add provider degraded cooldown/read-through behavior so scheduler tasks prefer stale cached market snapshots when all live providers are circuit-open.
3. Narrow runtime task summary/read-model queries after EXPLAIN on exact production SQL.
4. Defer any schema/index changes or historical task cleanup until a separate DB-write authorization window.

### D6 Daily-Bar Coverage Read Model Local Optimization - 2026-06-12

Implementation report: `docs/reports/daily-bar-coverage-read-model-optimization-2026-06-12.md`.

The first D6 read-path mitigation was implemented locally without schema/index changes. `DailyHistoryRepository.latest_complete_trade_date()` now builds a repository-local recent-date coverage model by first selecting recent `trade_date` candidates and then counting only those dates with `trade_date IN (...)`. `stock_count_by_trade_date()` can reuse the same counted values inside the repository instance.

This keeps raw daily-bar history fetches, priority board ordering, `production_score`, and strategy semantics unchanged. It directly addresses the root-cause evidence that broad `daily_bar_snapshots` coverage/group-by queries were scanning large historical ranges.

## Write Operation Summary So Far

| Category | Executed? | Details |
|---|---|---|
| Local docs/code commits | yes | D1-D3 local implementation, D6 dedupe fix, D6 worker guard implementation, integrated plan, and this report update |
| Online `.env` changes | yes | D4 non-core stop flags, D6 MySQL memory limits, D6 worker recycle threshold `RUNTIME_WORKER_RECYCLE_RSS_MB=700` |
| Online source upload | yes | D6 minimal upload of `latest_data_close_refresh.py`; D6 worker guard upload of `config.py`, `runtime_worker.py`, `docker-compose.mysql.yml`, each with remote backup |
| Container recreates | yes | D4 app/runtime-worker/runtime-scheduler; D6 mysql; D6 minimal runtime-scheduler recreate; D6 worker guard runtime-worker recreate |
| Docker build | yes | D6 rebuild of `runtime-scheduler`; D6 rebuild of `runtime-worker` |
| D5 scheduler embed | no | not executed; current worker memory fails the gate |
| Worker recycle guard live enablement | yes | `RUNTIME_WORKER_RECYCLE_RSS_MB=700`; current worker healthy with RSS about `162MiB / 768MiB` |
| Docker cleanup/image prune/volume prune | no | not executed |
| DB schema/data changes | no | not executed |
| nginx/systemd changes | no | not executed |
| strategy policy or scoring changes | no | `strategy_policy.py`, `production_score`, priority ordering untouched |
