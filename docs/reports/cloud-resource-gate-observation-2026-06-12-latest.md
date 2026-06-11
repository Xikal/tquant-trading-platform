# Cloud Resource Gate Observation

- Generated at: `2026-06-11T19:22:37.486604+00:00`
- Source: `ubuntu@43.143.243.97`
- Evaluation: `warning`
- D5 embedded scheduler ready: `false`
- D5 blockers: full_trading_day_observation_incomplete
- Blocking: none
- Warnings: scheduler_provider_warning_lines_observed=18, mysql_slow_queries=51

## Host

| Metric | Value |
| --- | --- |
| Date | `Fri Jun 12 03:22:33 CST 2026` |
| Uptime | `03:22:33 up 3 days, 16:06, 688 users,  load average: 0.18, 0.29, 0.34` |
| Memory available MB | 1390 |
| Swap used percent | 33.01 |
| Root used percent | 62 |
| Root inode used percent | 13 |

## Containers

| Container | CPU | Memory | Memory % |
| --- | ---: | ---: | ---: |
| `tquant-runtime-scheduler-mysql` | 0.00% | 253.4MiB / 640MiB | 39.60% |
| `tquant-runtime-worker-mysql` | 0.14% | 273.5MiB / 768MiB | 35.61% |
| `tquant-mysql` | 0.39% | 857.8MiB / 1.5GiB | 55.85% |
| `tquant-app-mysql` | 0.14% | 59.73MiB / 768MiB | 7.78% |
| `tquant-frontend-web` | 0.00% | 2.707MiB / 128MiB | 2.11% |
| `tquant-go-bff-gateway` | 0.00% | 5.254MiB / 128MiB | 4.10% |
| `tquant-go-market-read-service` | 0.00% | 7.883MiB / 128MiB | 6.16% |
| `tquant-go-scan-worker` | 0.00% | 5.816MiB / 128MiB | 4.54% |
| `tquant-redis` | 1.37% | 6.055MiB / 128MiB | 4.73% |

## HTTP

| Path | Status | Time | Error |
| --- | ---: | ---: | --- |
| `/readyz` | 200 | 0.005995 | `` |
| `/api/monitor` | 404 | 0.003902 | `` |
| `/api/monitor/snapshot` | 401 | 0.003471 | `` |
| `/api/priority-board` | 404 | 0.002695 | `` |
| `/api/screeners/low-buy/priority-board` | 401 | 0.002775 | `` |
| `/api/runtime-tasks/summary` | 401 | 0.002616 | `` |
| `/next/monitor` | 200 | 0.003231 | `` |
| `/next/monitor/market` | 200 | 0.003289 | `` |
| `/next/strategy-tracking` | 200 | 0.003645 | `` |
| `/next/analysis` | 200 | 0.003156 | `` |
| `/next/backtest` | 200 | 0.003205 | `` |
| `/next/data` | 200 | 0.003092 | `` |
| `/next/settings` | 200 | 0.003287 | `` |

## MySQL

| Metric | Value |
| --- | ---: |
| `Slow_queries` | 51 |
| `Threads_cached` | 5 |
| `Threads_connected` | 8 |
| `Threads_created` | 13 |
| `Threads_running` | 2 |
| `innodb_buffer_pool_size` | 536870912 |
| `max_connections` | 120 |

## Runtime Tasks

| Task | Status | Count | Oldest | Latest |
| --- | --- | ---: | --- | --- |
| `low_buy_materialization_refresh` | succeeded | 6 | 2026-06-11 18:11:29 | 2026-06-11 19:11:35 |

## Operations Not Executed

- No .env change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.
