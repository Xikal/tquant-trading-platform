# Cloud Resource Gate Observation

- Generated at: `2026-06-12T14:35:46.251093+00:00`
- Checkpoint: `post-sla-disable-2236`
- Source: `ubuntu@43.143.243.97`
- Evaluation: `warning`
- D5 embedded scheduler ready: `false`
- D5 blockers: full_trading_day_observation_incomplete, scheduler_provider_warning_lines=160, runtime_nonterminal_task_count=2
- Blocking: none
- Warnings: scheduler_provider_warning_lines=160, runtime_nonterminal_task_count=2, mysql_slow_queries=145

## Host

| Metric | Value |
| --- | --- |
| Date | `Fri Jun 12 22:35:38 CST 2026` |
| Uptime | `22:35:38 up 4 days, 11:19, 789 users,  load average: 0.33, 0.45, 0.46` |
| Memory available MB | 1197 |
| Swap used percent | 33.42 |
| Root used percent | 62 |
| Root inode used percent | 13 |

## Containers

| Container | CPU | Memory | Memory % |
| --- | ---: | ---: | ---: |
| `tquant-runtime-scheduler-mysql` | 100.33% | 354.5MiB / 640MiB | 55.39% |
| `tquant-runtime-worker-mysql` | 5.62% | 326.4MiB / 768MiB | 42.50% |
| `tquant-app-mysql` | 0.11% | 229.8MiB / 768MiB | 29.92% |
| `tquant-mysql` | 5.18% | 698.8MiB / 1.5GiB | 45.49% |
| `tquant-frontend-web` | 0.00% | 2.008MiB / 128MiB | 1.57% |
| `tquant-go-bff-gateway` | 0.00% | 7.734MiB / 128MiB | 6.04% |
| `tquant-go-market-read-service` | 0.00% | 9.93MiB / 128MiB | 7.76% |
| `tquant-go-scan-worker` | 0.00% | 5.094MiB / 128MiB | 3.98% |
| `tquant-redis` | 0.56% | 4.605MiB / 128MiB | 3.60% |

## HTTP

| Path | Status | Time | Error |
| --- | ---: | ---: | --- |
| `/readyz` | 200 | 0.00412 | `` |
| `/api/monitor` | 404 | 0.00444 | `` |
| `/api/monitor/snapshot` | 401 | 0.003201 | `` |
| `/api/priority-board` | 404 | 0.002569 | `` |
| `/api/screeners/low-buy/priority-board` | 401 | 0.002632 | `` |
| `/api/runtime-tasks/summary` | 401 | 0.003326 | `` |
| `/next/monitor` | 200 | 0.004793 | `` |
| `/next/monitor/market` | 200 | 0.004892 | `` |
| `/next/strategy-tracking` | 200 | 0.004753 | `` |
| `/next/analysis` | 200 | 0.005071 | `` |
| `/next/backtest` | 200 | 0.004266 | `` |
| `/next/data` | 200 | 0.003436 | `` |
| `/next/settings` | 200 | 0.00372 | `` |

## MySQL

| Metric | Value |
| --- | ---: |
| `Slow_queries` | 145 |
| `Threads_cached` | 4 |
| `Threads_connected` | 11 |
| `Threads_created` | 23 |
| `Threads_running` | 2 |
| `innodb_buffer_pool_size` | 536870912 |
| `max_connections` | 120 |

## Runtime Tasks

| Task | Status | Count | Oldest | Latest |
| --- | --- | ---: | --- | --- |
| `low_buy_materialization_refresh` | failed | 91 | 2026-06-12 12:35:57 | 2026-06-12 13:05:11 |
| `latest_data_watchdog` | succeeded | 23 | 2026-06-12 12:39:25 | 2026-06-12 14:27:47 |
| `market_pulse_refresh` | succeeded | 16 | 2026-06-12 12:46:46 | 2026-06-12 12:49:28 |
| `monitor_snapshot_refresh` | succeeded | 16 | 2026-06-12 12:46:46 | 2026-06-12 12:49:29 |
| `low_buy_materialization_refresh` | succeeded | 7 | 2026-06-12 13:05:03 | 2026-06-12 14:19:10 |
| `data_quality_sla_refresh` | cancelled | 1 | 2026-06-12 14:03:05 | 2026-06-12 14:32:48 |
| `latest_data_watchdog` | queued | 1 | 2026-06-12 14:34:09 | 2026-06-12 14:34:09 |
| `low_buy_materialization_refresh` | running | 1 | 2026-06-12 14:32:24 | 2026-06-12 14:32:27 |
| `strategy_tracking_snapshot_refresh` | succeeded | 1 | 2026-06-12 13:09:38 | 2026-06-12 13:11:00 |

## Operations Not Executed

- No .env change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.
