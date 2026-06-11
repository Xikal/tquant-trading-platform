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

## Write Operation Summary So Far

| Category | Executed? | Details |
|---|---|---|
| Local docs/code commits | yes | D1-D3 local implementation and this report update |
| Online `.env` changes | yes | D4 non-core stop flags, D6 MySQL memory limits |
| Container recreates | yes | D4 app/runtime-worker/runtime-scheduler; D6 mysql |
| Docker cleanup/image prune/volume prune | no | not executed |
| DB schema/data changes | no | not executed |
| nginx/systemd changes | no | not executed |
| strategy policy or scoring changes | no | `strategy_policy.py`, `production_score`, priority ordering untouched |
