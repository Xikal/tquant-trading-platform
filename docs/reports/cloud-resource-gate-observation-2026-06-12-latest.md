# Cloud Resource Gate Observation

- Generated at: `2026-06-11T19:17:37.699938+00:00`
- Source: `ubuntu@43.143.243.97`
- Evaluation: `warning`
- D5 embedded scheduler ready: `false`
- D5 blockers: full_trading_day_observation_incomplete, scheduler_provider_warnings_present
- Blocking: none
- Warnings: scheduler_provider_warnings_present, mysql_slow_queries=51

## Host

| Metric | Value |
| --- | --- |
| Date | `Fri Jun 12 03:17:33 CST 2026` |
| Uptime | `03:17:33 up 3 days, 16:01, 685 users,  load average: 0.24, 0.38, 0.39` |
| Memory available MB | 1382 |
| Swap used percent | 33.06 |
| Root used percent | 62 |
| Root inode used percent | 13 |

## Containers

| Container | CPU | Memory | Memory % |
| --- | ---: | ---: | ---: |
| `tquant-runtime-scheduler-mysql` | 0.00% | 252.9MiB / 640MiB | 39.51% |
| `tquant-runtime-worker-mysql` | 0.00% | 273.5MiB / 768MiB | 35.61% |
| `tquant-mysql` | 0.37% | 857.3MiB / 1.5GiB | 55.81% |
| `tquant-app-mysql` | 0.12% | 59.61MiB / 768MiB | 7.76% |
| `tquant-frontend-web` | 2.55% | 2.711MiB / 128MiB | 2.12% |
| `tquant-go-bff-gateway` | 2.46% | 5.215MiB / 128MiB | 4.07% |
| `tquant-go-market-read-service` | 0.00% | 8.328MiB / 128MiB | 6.51% |
| `tquant-go-scan-worker` | 0.00% | 5.793MiB / 128MiB | 4.53% |
| `tquant-redis` | 0.49% | 5.746MiB / 128MiB | 4.49% |

## HTTP

| Path | Status | Time | Error |
| --- | ---: | ---: | --- |
| `/readyz` | 200 | 0.003957 | `` |
| `/api/monitor` | 404 | 0.004059 | `` |
| `/api/monitor/snapshot` | 401 | 0.008328 | `` |
| `/api/priority-board` | 404 | 0.00314 | `` |
| `/api/screeners/low-buy/priority-board` | 401 | 0.002942 | `` |
| `/api/runtime-tasks/summary` | 401 | 0.003287 | `` |
| `/next/monitor` | 200 | 0.008677 | `` |
| `/next/monitor/market` | 200 | 0.003925 | `` |
| `/next/strategy-tracking` | 200 | 0.003733 | `` |
| `/next/analysis` | 200 | 0.003962 | `` |
| `/next/backtest` | 200 | 0.004004 | `` |
| `/next/data` | 200 | 0.005518 | `` |
| `/next/settings` | 200 | 0.003506 | `` |

## MySQL

| Metric | Value |
| --- | ---: |
| `Slow_queries` | 51 |
| `Threads_cached` | 4 |
| `Threads_connected` | 9 |
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
