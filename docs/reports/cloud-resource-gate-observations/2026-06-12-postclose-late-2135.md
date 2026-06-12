# Cloud Resource Gate Observation

- Generated at: `2026-06-12T13:31:26.213607+00:00`
- Checkpoint: `postclose-late-2135`
- Source: `ubuntu@43.143.243.97`
- Evaluation: `blocking`
- D5 embedded scheduler ready: `false`
- D5 blockers: kernel_oom_logs_present, full_trading_day_observation_incomplete, scheduler_provider_warning_lines=160, runtime_nonterminal_task_count=1
- Blocking: kernel_oom_logs_present
- Warnings: swap_used_pct=35.03, scheduler_provider_warning_lines=160, runtime_nonterminal_task_count=1, mysql_slow_queries=133

## Host

| Metric | Value |
| --- | --- |
| Date | `Fri Jun 12 21:31:21 CST 2026` |
| Uptime | `21:31:21 up 4 days, 10:15, 752 users,  load average: 0.12, 0.19, 0.28` |
| Memory available MB | 1007 |
| Swap used percent | 35.03 |
| Root used percent | 63 |
| Root inode used percent | 13 |

## Containers

| Container | CPU | Memory | Memory % |
| --- | ---: | ---: | ---: |
| `tquant-runtime-scheduler-mysql` | 0.00% | 351.4MiB / 640MiB | 54.90% |
| `tquant-runtime-worker-mysql` | 0.00% | 330.4MiB / 768MiB | 43.02% |
| `tquant-mysql` | 0.45% | 815MiB / 1.5GiB | 53.06% |
| `tquant-app-mysql` | 0.12% | 331.8MiB / 768MiB | 43.20% |
| `tquant-frontend-web` | 0.00% | 2.664MiB / 128MiB | 2.08% |
| `tquant-go-bff-gateway` | 0.00% | 7.934MiB / 128MiB | 6.20% |
| `tquant-go-market-read-service` | 0.00% | 6.664MiB / 128MiB | 5.21% |
| `tquant-go-scan-worker` | 0.00% | 4.953MiB / 128MiB | 3.87% |
| `tquant-redis` | 0.52% | 4.152MiB / 128MiB | 3.24% |

## HTTP

| Path | Status | Time | Error |
| --- | ---: | ---: | --- |
| `/readyz` | 200 | 0.004039 | `` |
| `/api/monitor` | 404 | 0.003808 | `` |
| `/api/monitor/snapshot` | 401 | 0.003193 | `` |
| `/api/priority-board` | 404 | 0.002968 | `` |
| `/api/screeners/low-buy/priority-board` | 401 | 0.002756 | `` |
| `/api/runtime-tasks/summary` | 401 | 0.002628 | `` |
| `/next/monitor` | 200 | 0.003415 | `` |
| `/next/monitor/market` | 200 | 0.003421 | `` |
| `/next/strategy-tracking` | 200 | 0.003474 | `` |
| `/next/analysis` | 200 | 0.003664 | `` |
| `/next/backtest` | 200 | 0.003274 | `` |
| `/next/data` | 200 | 0.003308 | `` |
| `/next/settings` | 200 | 0.003512 | `` |

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
| `low_buy_materialization_refresh` | failed | 280 | 2026-06-12 11:31:42 | 2026-06-12 13:05:11 |
| `market_pulse_refresh` | succeeded | 93 | 2026-06-12 11:31:33 | 2026-06-12 12:49:28 |
| `monitor_snapshot_refresh` | succeeded | 93 | 2026-06-12 11:31:33 | 2026-06-12 12:49:29 |
| `latest_data_watchdog` | succeeded | 24 | 2026-06-12 11:34:25 | 2026-06-12 13:27:50 |
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
