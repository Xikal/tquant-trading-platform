# Cloud Resource Gate Observation

- Generated at: `2026-06-12T13:53:57.912794+00:00`
- Checkpoint: `postclose-current-2155`
- Source: `ubuntu@43.143.243.97`
- Evaluation: `warning`
- D5 embedded scheduler ready: `false`
- D5 blockers: full_trading_day_observation_incomplete, runtime_nonterminal_task_count=1
- Blocking: none
- Warnings: scheduler_provider_warning_lines_observed=10, runtime_nonterminal_task_count=1, mysql_slow_queries=133

## Host

| Metric | Value |
| --- | --- |
| Date | `Fri Jun 12 21:53:53 CST 2026` |
| Uptime | `21:53:53 up 4 days, 10:38, 756 users,  load average: 0.18, 0.19, 0.21` |
| Memory available MB | 1043 |
| Swap used percent | 34.98 |
| Root used percent | 63 |
| Root inode used percent | 13 |

## Containers

| Container | CPU | Memory | Memory % |
| --- | ---: | ---: | ---: |
| `tquant-runtime-scheduler-mysql` | 0.00% | 355.5MiB / 640MiB | 55.54% |
| `tquant-runtime-worker-mysql` | 0.00% | 330.4MiB / 768MiB | 43.02% |
| `tquant-mysql` | 0.54% | 816.1MiB / 1.5GiB | 53.13% |
| `tquant-app-mysql` | 0.12% | 331.8MiB / 768MiB | 43.21% |
| `tquant-frontend-web` | 0.00% | 2.668MiB / 128MiB | 2.08% |
| `tquant-go-bff-gateway` | 0.00% | 7.938MiB / 128MiB | 6.20% |
| `tquant-go-market-read-service` | 0.00% | 6.492MiB / 128MiB | 5.07% |
| `tquant-go-scan-worker` | 0.00% | 5.137MiB / 128MiB | 4.01% |
| `tquant-redis` | 0.47% | 4.137MiB / 128MiB | 3.23% |

## HTTP

| Path | Status | Time | Error |
| --- | ---: | ---: | --- |
| `/readyz` | 200 | 0.004245 | `` |
| `/api/monitor` | 404 | 0.004208 | `` |
| `/api/monitor/snapshot` | 401 | 0.003705 | `` |
| `/api/priority-board` | 404 | 0.00333 | `` |
| `/api/screeners/low-buy/priority-board` | 401 | 0.003324 | `` |
| `/api/runtime-tasks/summary` | 401 | 0.003204 | `` |
| `/next/monitor` | 200 | 0.004666 | `` |
| `/next/monitor/market` | 200 | 0.003849 | `` |
| `/next/strategy-tracking` | 200 | 0.003797 | `` |
| `/next/analysis` | 200 | 0.003794 | `` |
| `/next/backtest` | 200 | 0.00407 | `` |
| `/next/data` | 200 | 0.003769 | `` |
| `/next/settings` | 200 | 0.003589 | `` |

## MySQL

| Metric | Value |
| --- | ---: |
| `Slow_queries` | 133 |
| `Threads_cached` | 6 |
| `Threads_connected` | 10 |
| `Threads_created` | 19 |
| `Threads_running` | 2 |
| `innodb_buffer_pool_size` | 536870912 |
| `max_connections` | 120 |

## Runtime Tasks

| Task | Status | Count | Oldest | Latest |
| --- | --- | ---: | --- | --- |
| `low_buy_materialization_refresh` | failed | 212 | 2026-06-12 11:54:24 | 2026-06-12 13:05:11 |
| `latest_data_watchdog` | succeeded | 25 | 2026-06-12 11:54:25 | 2026-06-12 13:52:49 |
| `market_pulse_refresh` | succeeded | 16 | 2026-06-12 12:46:46 | 2026-06-12 12:49:28 |
| `monitor_snapshot_refresh` | succeeded | 16 | 2026-06-12 12:46:46 | 2026-06-12 12:49:29 |
| `low_buy_materialization_refresh` | succeeded | 6 | 2026-06-12 13:05:03 | 2026-06-12 13:19:38 |
| `strategy_tracking_snapshot_refresh` | succeeded | 1 | 2026-06-12 13:09:38 | 2026-06-12 13:11:00 |

## Operations Not Executed

- No .env change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.
