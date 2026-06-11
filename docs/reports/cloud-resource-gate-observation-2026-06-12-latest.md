# Cloud Resource Gate Observation

- Generated at: `2026-06-11T17:14:05.340136+00:00`
- Source: `ubuntu@43.143.243.97`
- Evaluation: `warning`
- D5 embedded scheduler ready: `false`
- D5 blockers: full_trading_day_observation_incomplete, scheduler_provider_warnings_present, runtime_nonterminal_task_count=2, duplicate_success_window:strategy_tracking_snapshot_refresh=56, duplicate_success_window:a_key_level_materialization_refresh=26
- Blocking: none
- Warnings: swap_used_pct=39.96, scheduler_provider_warnings_present, runtime_nonterminal_task_count=2, duplicate_success_window:strategy_tracking_snapshot_refresh=56, duplicate_success_window:a_key_level_materialization_refresh=26, mysql_slow_queries=16

## Host

| Metric | Value |
| --- | --- |
| Date | `Fri Jun 12 01:14:00 CST 2026` |
| Uptime | `01:14:00 up 3 days, 13:58, 628 users,  load average: 0.27, 0.33, 0.29` |
| Memory available MB | 1571 |
| Swap used percent | 39.96 |
| Root used percent | 60 |
| Root inode used percent | 12 |

## Containers

| Container | CPU | Memory | Memory % |
| --- | ---: | ---: | ---: |
| `tquant-runtime-worker-mysql` | 0.00% | 218MiB / 768MiB | 28.38% |
| `tquant-runtime-scheduler-mysql` | 0.00% | 353.7MiB / 640MiB | 55.27% |
| `tquant-mysql` | 0.51% | 656.1MiB / 1.5GiB | 42.71% |
| `tquant-app-mysql` | 0.13% | 45.26MiB / 768MiB | 5.89% |
| `tquant-frontend-web` | 0.00% | 2.176MiB / 128MiB | 1.70% |
| `tquant-go-bff-gateway` | 0.00% | 4.676MiB / 128MiB | 3.65% |
| `tquant-go-market-read-service` | 0.00% | 9.562MiB / 128MiB | 7.47% |
| `tquant-go-scan-worker` | 0.00% | 6.031MiB / 128MiB | 4.71% |
| `tquant-redis` | 0.50% | 5.078MiB / 128MiB | 3.97% |

## HTTP

| Path | Status | Time | Error |
| --- | ---: | ---: | --- |
| `/readyz` | 200 | 0.004601 | `` |
| `/api/monitor` | 404 | 0.003873 | `` |
| `/api/monitor/snapshot` | 401 | 0.004064 | `` |
| `/api/priority-board` | 404 | 0.003328 | `` |
| `/api/screeners/low-buy/priority-board` | 401 | 0.003347 | `` |
| `/api/runtime-tasks/summary` | 401 | 0.003556 | `` |
| `/next/monitor` | 200 | 0.003983 | `` |
| `/next/monitor/market` | 200 | 0.004128 | `` |
| `/next/strategy-tracking` | 200 | 0.00385 | `` |
| `/next/analysis` | 200 | 0.00353 | `` |
| `/next/backtest` | 200 | 0.004476 | `` |
| `/next/data` | 200 | 0.003683 | `` |
| `/next/settings` | 200 | 0.0034 | `` |

## MySQL

| Metric | Value |
| --- | ---: |
| `Slow_queries` | 16 |
| `Threads_cached` | 2 |
| `Threads_connected` | 10 |
| `Threads_created` | 12 |
| `Threads_running` | 2 |
| `innodb_buffer_pool_size` | 536870912 |
| `max_connections` | 120 |

## Runtime Tasks

| Task | Status | Count | Oldest | Latest |
| --- | --- | ---: | --- | --- |
| `strategy_tracking_snapshot_refresh` | succeeded | 56 | 2026-06-11 15:14:19 | 2026-06-11 15:59:43 |
| `a_key_level_materialization_refresh` | succeeded | 26 | 2026-06-11 15:14:19 | 2026-06-11 16:00:44 |
| `latest_data_watchdog` | succeeded | 8 | 2026-06-11 15:16:27 | 2026-06-11 15:58:10 |
| `hermes_platform_autopilot` | succeeded | 5 | 2026-06-11 15:16:28 | 2026-06-11 15:38:56 |
| `low_buy_materialization_refresh` | succeeded | 2 | 2026-06-11 16:11:31 | 2026-06-11 17:11:48 |

## Operations Not Executed

- No .env change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.
