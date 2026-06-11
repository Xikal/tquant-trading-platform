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
