# Cloud Resource Gate Observation

- Generated at: `2026-06-11T18:54:10.850271+00:00`
- Source: `ubuntu@43.143.243.97`
- Evaluation: `warning`
- D5 embedded scheduler ready: `false`
- D5 blockers: full_trading_day_observation_incomplete, scheduler_provider_warnings_present
- Blocking: none
- Warnings: scheduler_provider_warnings_present, mysql_slow_queries=48

## Host

| Metric | Value |
| --- | --- |
| Date | `Fri Jun 12 02:54:06 CST 2026` |
| Uptime | `02:54:06 up 3 days, 15:38, 673 users,  load average: 0.45, 0.28, 0.30` |
| Memory available MB | 1418 |
| Swap used percent | 33.27 |
| Root used percent | 62 |
| Root inode used percent | 13 |

## Containers

| Container | CPU | Memory | Memory % |
| --- | ---: | ---: | ---: |
| `tquant-runtime-scheduler-mysql` | 0.00% | 254.4MiB / 640MiB | 39.75% |
| `tquant-runtime-worker-mysql` | 0.00% | 294.8MiB / 768MiB | 38.39% |
| `tquant-mysql` | 0.43% | 853MiB / 1.5GiB | 55.53% |
| `tquant-app-mysql` | 0.14% | 59.37MiB / 768MiB | 7.73% |
| `tquant-frontend-web` | 0.00% | 2.711MiB / 128MiB | 2.12% |
| `tquant-go-bff-gateway` | 0.00% | 5.094MiB / 128MiB | 3.98% |
| `tquant-go-market-read-service` | 0.00% | 7.641MiB / 128MiB | 5.97% |
| `tquant-go-scan-worker` | 2.45% | 5.898MiB / 128MiB | 4.61% |
| `tquant-redis` | 0.49% | 4.957MiB / 128MiB | 3.87% |

## HTTP

| Path | Status | Time | Error |
| --- | ---: | ---: | --- |
| `/readyz` | 200 | 0.003887 | `` |
| `/api/monitor` | 404 | 0.003443 | `` |
| `/api/monitor/snapshot` | 401 | 0.00378 | `` |
| `/api/priority-board` | 404 | 0.002725 | `` |
| `/api/screeners/low-buy/priority-board` | 401 | 0.002681 | `` |
| `/api/runtime-tasks/summary` | 401 | 0.003536 | `` |
| `/next/monitor` | 200 | 0.003255 | `` |
| `/next/monitor/market` | 200 | 0.003192 | `` |
| `/next/strategy-tracking` | 200 | 0.003345 | `` |
| `/next/analysis` | 200 | 0.003259 | `` |
| `/next/backtest` | 200 | 0.003134 | `` |
| `/next/data` | 200 | 0.003067 | `` |
| `/next/settings` | 200 | 0.003102 | `` |

## MySQL

| Metric | Value |
| --- | ---: |
| `Slow_queries` | 48 |
| `Threads_cached` | 4 |
| `Threads_connected` | 9 |
| `Threads_created` | 13 |
| `Threads_running` | 2 |
| `innodb_buffer_pool_size` | 536870912 |
| `max_connections` | 120 |

## Runtime Tasks

| Task | Status | Count | Oldest | Latest |
| --- | --- | ---: | --- | --- |
| `low_buy_materialization_refresh` | succeeded | 6 | 2026-06-11 17:11:29 | 2026-06-11 18:28:45 |

## Operations Not Executed

- No .env change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.
