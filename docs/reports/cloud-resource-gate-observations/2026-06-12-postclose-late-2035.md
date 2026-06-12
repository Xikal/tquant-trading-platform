# Cloud Resource Gate Observation

- Generated at: `2026-06-12T12:34:39.424002+00:00`
- Checkpoint: `postclose-late-2035`
- Source: `ubuntu@43.143.243.97`
- Evaluation: `blocking`
- D5 embedded scheduler ready: `false`
- D5 blockers: kernel_oom_logs_present, full_trading_day_observation_incomplete, runtime_worker_signal_logs_present, runtime_nonterminal_task_count=2
- Blocking: kernel_oom_logs_present
- Warnings: swap_used_pct=36.64, runtime_worker_signal_logs_present, scheduler_provider_warning_lines_observed=10, runtime_nonterminal_task_count=2, mysql_slow_queries=117

## Host

| Metric | Value |
| --- | --- |
| Date | `Fri Jun 12 20:34:30 CST 2026` |
| Uptime | `20:34:30 up 4 days,  9:18, 727 users,  load average: 0.57, 0.32, 0.28` |
| Memory available MB | 734 |
| Swap used percent | 36.64 |
| Root used percent | 63 |
| Root inode used percent | 13 |

## Containers

| Container | CPU | Memory | Memory % |
| --- | ---: | ---: | ---: |
| `tquant-runtime-scheduler-mysql` | 0.00% | 329.9MiB / 640MiB | 51.54% |
| `tquant-runtime-worker-mysql` | 0.01% | 585.8MiB / 768MiB | 76.28% |
| `tquant-mysql` | 0.51% | 874.3MiB / 1.5GiB | 56.92% |
| `tquant-app-mysql` | 0.14% | 337.9MiB / 768MiB | 44.00% |
| `tquant-frontend-web` | 0.00% | 2.566MiB / 128MiB | 2.01% |
| `tquant-go-bff-gateway` | 0.00% | 8.137MiB / 128MiB | 6.36% |
| `tquant-go-market-read-service` | 0.00% | 6.316MiB / 128MiB | 4.93% |
| `tquant-go-scan-worker` | 0.00% | 6.098MiB / 128MiB | 4.76% |
| `tquant-redis` | 0.50% | 4.73MiB / 128MiB | 3.70% |

## HTTP

| Path | Status | Time | Error |
| --- | ---: | ---: | --- |
| `/readyz` | 200 | 0.00387 | `` |
| `/api/monitor` | 404 | 0.003482 | `` |
| `/api/monitor/snapshot` | 401 | 0.003617 | `` |
| `/api/priority-board` | 404 | 0.002991 | `` |
| `/api/screeners/low-buy/priority-board` | 401 | 0.003319 | `` |
| `/api/runtime-tasks/summary` | 401 | 0.002823 | `` |
| `/next/monitor` | 200 | 0.004133 | `` |
| `/next/monitor/market` | 200 | 0.003511 | `` |
| `/next/strategy-tracking` | 200 | 0.003497 | `` |
| `/next/analysis` | 200 | 0.003483 | `` |
| `/next/backtest` | 200 | 0.003515 | `` |
| `/next/data` | 200 | 0.004138 | `` |
| `/next/settings` | 200 | 0.003344 | `` |

## MySQL

| Metric | Value |
| --- | ---: |
| `Slow_queries` | 117 |
| `Threads_cached` | 5 |
| `Threads_connected` | 10 |
| `Threads_created` | 15 |
| `Threads_running` | 2 |
| `innodb_buffer_pool_size` | 536870912 |
| `max_connections` | 120 |

## Runtime Tasks

| Task | Status | Count | Oldest | Latest |
| --- | --- | ---: | --- | --- |
| `market_pulse_refresh` | succeeded | 388 | 2026-06-12 10:34:47 | 2026-06-12 11:45:08 |
| `monitor_snapshot_refresh` | succeeded | 383 | 2026-06-12 10:34:47 | 2026-06-12 11:45:10 |
| `low_buy_materialization_refresh` | failed | 355 | 2026-06-12 10:34:54 | 2026-06-12 12:34:28 |
| `latest_data_watchdog` | succeeded | 24 | 2026-06-12 10:39:25 | 2026-06-12 12:34:28 |
| `low_buy_materialization_refresh` | queued | 1 | 2026-06-12 12:34:28 | 2026-06-12 12:34:28 |

## Operations Not Executed

- No .env change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.
