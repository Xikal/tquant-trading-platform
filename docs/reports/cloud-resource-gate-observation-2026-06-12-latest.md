# Cloud Resource Gate Observation

- Generated at: `2026-06-11T18:04:48.920521+00:00`
- Source: `ubuntu@43.143.243.97`
- Evaluation: `warning`
- D5 embedded scheduler ready: `false`
- D5 blockers: full_trading_day_observation_incomplete, scheduler_provider_warnings_present, runtime_nonterminal_task_count=2
- Blocking: none
- Warnings: swap_used_pct=37.44, scheduler_provider_warnings_present, runtime_nonterminal_task_count=2, mysql_slow_queries=17

## Host

| Metric | Value |
| --- | --- |
| Date | `Fri Jun 12 02:04:44 CST 2026` |
| Uptime | `02:04:44 up 3 days, 14:48, 634 users,  load average: 0.27, 0.31, 0.33` |
| Memory available MB | 1488 |
| Swap used percent | 37.44 |
| Root used percent | 61 |
| Root inode used percent | 12 |

## Containers

| Container | CPU | Memory | Memory % |
| --- | ---: | ---: | ---: |
| `tquant-runtime-worker-mysql` | 0.00% | 218MiB / 768MiB | 28.38% |
| `tquant-runtime-scheduler-mysql` | 1.10% | 377.7MiB / 640MiB | 59.02% |
| `tquant-mysql` | 0.41% | 710.4MiB / 1.5GiB | 46.25% |
| `tquant-app-mysql` | 0.13% | 48.32MiB / 768MiB | 6.29% |
| `tquant-frontend-web` | 0.00% | 2.617MiB / 128MiB | 2.04% |
| `tquant-go-bff-gateway` | 0.00% | 4.988MiB / 128MiB | 3.90% |
| `tquant-go-market-read-service` | 0.00% | 7.598MiB / 128MiB | 5.94% |
| `tquant-go-scan-worker` | 0.00% | 5.828MiB / 128MiB | 4.55% |
| `tquant-redis` | 0.48% | 5.719MiB / 128MiB | 4.47% |

## HTTP

| Path | Status | Time | Error |
| --- | ---: | ---: | --- |
| `/readyz` | 200 | 0.003812 | `` |
| `/api/monitor` | 404 | 0.003846 | `` |
| `/api/monitor/snapshot` | 401 | 0.003457 | `` |
| `/api/priority-board` | 404 | 0.003088 | `` |
| `/api/screeners/low-buy/priority-board` | 401 | 0.003123 | `` |
| `/api/runtime-tasks/summary` | 401 | 0.002697 | `` |
| `/next/monitor` | 200 | 0.003334 | `` |
| `/next/monitor/market` | 200 | 0.003291 | `` |
| `/next/strategy-tracking` | 200 | 0.003236 | `` |
| `/next/analysis` | 200 | 0.003245 | `` |
| `/next/backtest` | 200 | 0.003184 | `` |
| `/next/data` | 200 | 0.003414 | `` |
| `/next/settings` | 200 | 0.003284 | `` |

## MySQL

| Metric | Value |
| --- | ---: |
| `Slow_queries` | 17 |
| `Threads_cached` | 3 |
| `Threads_connected` | 9 |
| `Threads_created` | 12 |
| `Threads_running` | 2 |
| `innodb_buffer_pool_size` | 536870912 |
| `max_connections` | 120 |

## Runtime Tasks

| Task | Status | Count | Oldest | Latest |
| --- | --- | ---: | --- | --- |
| `low_buy_materialization_refresh` | succeeded | 2 | 2026-06-11 16:11:31 | 2026-06-11 17:11:48 |

## Operations Not Executed

- No .env change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.
