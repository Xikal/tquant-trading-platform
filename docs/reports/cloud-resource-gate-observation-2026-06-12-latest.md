# Cloud Resource Gate Observation

- Generated at: `2026-06-11T18:48:47.526027+00:00`
- Source: `ubuntu@43.143.243.97`
- Evaluation: `warning`
- D5 embedded scheduler ready: `false`
- D5 blockers: full_trading_day_observation_incomplete, scheduler_provider_warnings_present, runtime_nonterminal_task_count=2
- Blocking: none
- Warnings: scheduler_provider_warnings_present, runtime_nonterminal_task_count=2, mysql_slow_queries=48

## Host

| Metric | Value |
| --- | --- |
| Date | `Fri Jun 12 02:48:43 CST 2026` |
| Uptime | `02:48:43 up 3 days, 15:32, 666 users,  load average: 0.21, 0.20, 0.32` |
| Memory available MB | 1378 |
| Swap used percent | 33.32 |
| Root used percent | 62 |
| Root inode used percent | 13 |

## Containers

| Container | CPU | Memory | Memory % |
| --- | ---: | ---: | ---: |
| `tquant-runtime-scheduler-mysql` | 0.00% | 255.3MiB / 640MiB | 39.89% |
| `tquant-runtime-worker-mysql` | 0.00% | 294.8MiB / 768MiB | 38.39% |
| `tquant-mysql` | 5.01% | 852.2MiB / 1.5GiB | 55.48% |
| `tquant-app-mysql` | 0.13% | 52.54MiB / 768MiB | 6.84% |
| `tquant-frontend-web` | 0.00% | 2.711MiB / 128MiB | 2.12% |
| `tquant-go-bff-gateway` | 0.00% | 5.141MiB / 128MiB | 4.02% |
| `tquant-go-market-read-service` | 2.43% | 7.656MiB / 128MiB | 5.98% |
| `tquant-go-scan-worker` | 0.00% | 5.816MiB / 128MiB | 4.54% |
| `tquant-redis` | 0.47% | 4.961MiB / 128MiB | 3.88% |

## HTTP

| Path | Status | Time | Error |
| --- | ---: | ---: | --- |
| `/readyz` | 200 | 0.003816 | `` |
| `/api/monitor` | 404 | 0.003784 | `` |
| `/api/monitor/snapshot` | 401 | 0.003208 | `` |
| `/api/priority-board` | 404 | 0.002666 | `` |
| `/api/screeners/low-buy/priority-board` | 401 | 0.002683 | `` |
| `/api/runtime-tasks/summary` | 401 | 0.002963 | `` |
| `/next/monitor` | 200 | 0.003952 | `` |
| `/next/monitor/market` | 200 | 0.003337 | `` |
| `/next/strategy-tracking` | 200 | 0.003102 | `` |
| `/next/analysis` | 200 | 0.003132 | `` |
| `/next/backtest` | 200 | 0.003072 | `` |
| `/next/data` | 200 | 0.002996 | `` |
| `/next/settings` | 200 | 0.00323 | `` |

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
