# Cloud Resource Gate Observation

- Generated at: `2026-06-11T20:15:46.614633+00:00`
- Checkpoint: `single-snapshot`
- Source: `ubuntu@43.143.243.97`
- Evaluation: `warning`
- D5 embedded scheduler ready: `false`
- D5 blockers: full_trading_day_observation_incomplete
- Blocking: none
- Warnings: scheduler_provider_warning_lines_observed=18, mysql_slow_queries=55

## Host

| Metric | Value |
| --- | --- |
| Date | `Fri Jun 12 04:15:42 CST 2026` |
| Uptime | `04:15:42 up 3 days, 16:59, 702 users,  load average: 0.50, 0.31, 0.28` |
| Memory available MB | 1349 |
| Swap used percent | 32.66 |
| Root used percent | 63 |
| Root inode used percent | 13 |

## Containers

| Container | CPU | Memory | Memory % |
| --- | ---: | ---: | ---: |
| `tquant-runtime-scheduler-mysql` | 0.00% | 255.1MiB / 640MiB | 39.86% |
| `tquant-runtime-worker-mysql` | 0.00% | 296.1MiB / 768MiB | 38.55% |
| `tquant-mysql` | 0.38% | 863.2MiB / 1.5GiB | 56.20% |
| `tquant-app-mysql` | 0.12% | 60.22MiB / 768MiB | 7.84% |
| `tquant-frontend-web` | 0.00% | 2.707MiB / 128MiB | 2.11% |
| `tquant-go-bff-gateway` | 0.00% | 5.184MiB / 128MiB | 4.05% |
| `tquant-go-market-read-service` | 0.00% | 8.094MiB / 128MiB | 6.32% |
| `tquant-go-scan-worker` | 0.00% | 5.828MiB / 128MiB | 4.55% |
| `tquant-redis` | 0.48% | 4.977MiB / 128MiB | 3.89% |

## HTTP

| Path | Status | Time | Error |
| --- | ---: | ---: | --- |
| `/readyz` | 200 | 0.003832 | `` |
| `/api/monitor` | 404 | 0.003562 | `` |
| `/api/monitor/snapshot` | 401 | 0.003128 | `` |
| `/api/priority-board` | 404 | 0.002731 | `` |
| `/api/screeners/low-buy/priority-board` | 401 | 0.002557 | `` |
| `/api/runtime-tasks/summary` | 401 | 0.003045 | `` |
| `/next/monitor` | 200 | 0.00327 | `` |
| `/next/monitor/market` | 200 | 0.003475 | `` |
| `/next/strategy-tracking` | 200 | 0.003318 | `` |
| `/next/analysis` | 200 | 0.003836 | `` |
| `/next/backtest` | 200 | 0.003525 | `` |
| `/next/data` | 200 | 0.003331 | `` |
| `/next/settings` | 200 | 0.003207 | `` |

## MySQL

| Metric | Value |
| --- | ---: |
| `Slow_queries` | 55 |
| `Threads_cached` | 4 |
| `Threads_connected` | 9 |
| `Threads_created` | 13 |
| `Threads_running` | 2 |
| `innodb_buffer_pool_size` | 536870912 |
| `max_connections` | 120 |

## Runtime Tasks

| Task | Status | Count | Oldest | Latest |
| --- | --- | ---: | --- | --- |
| `low_buy_materialization_refresh` | succeeded | 6 | 2026-06-11 18:16:45 | 2026-06-11 19:57:59 |

## Operations Not Executed

- No .env change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.
