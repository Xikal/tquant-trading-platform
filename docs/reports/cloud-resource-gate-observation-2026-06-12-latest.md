# Cloud Resource Gate Observation

- Generated at: `2026-06-11T18:29:46.609440+00:00`
- Source: `ubuntu@43.143.243.97`
- Evaluation: `warning`
- D5 embedded scheduler ready: `false`
- D5 blockers: full_trading_day_observation_incomplete, scheduler_provider_warnings_present, runtime_nonterminal_task_count=2
- Blocking: none
- Warnings: scheduler_provider_warnings_present, runtime_nonterminal_task_count=2, mysql_slow_queries=48

## Host

| Metric | Value |
| --- | --- |
| Date | `Fri Jun 12 02:29:42 CST 2026` |
| Uptime | `02:29:42 up 3 days, 15:13, 664 users,  load average: 0.54, 0.73, 0.65` |
| Memory available MB | 1392 |
| Swap used percent | 33.47 |
| Root used percent | 62 |
| Root inode used percent | 13 |

## Containers

| Container | CPU | Memory | Memory % |
| --- | ---: | ---: | ---: |
| `tquant-runtime-scheduler-mysql` | 15.70% | 261.1MiB / 640MiB | 40.80% |
| `tquant-runtime-worker-mysql` | 0.00% | 294.8MiB / 768MiB | 38.39% |
| `tquant-mysql` | 0.74% | 849.3MiB / 1.5GiB | 55.29% |
| `tquant-app-mysql` | 0.13% | 52.37MiB / 768MiB | 6.82% |
| `tquant-frontend-web` | 0.00% | 2.707MiB / 128MiB | 2.11% |
| `tquant-go-bff-gateway` | 0.00% | 5.121MiB / 128MiB | 4.00% |
| `tquant-go-market-read-service` | 0.00% | 11.21MiB / 128MiB | 8.76% |
| `tquant-go-scan-worker` | 0.00% | 6.047MiB / 128MiB | 4.72% |
| `tquant-redis` | 0.55% | 9.156MiB / 128MiB | 7.15% |

## HTTP

| Path | Status | Time | Error |
| --- | ---: | ---: | --- |
| `/readyz` | 200 | 0.00641 | `` |
| `/api/monitor` | 404 | 0.003028 | `` |
| `/api/monitor/snapshot` | 401 | 0.003192 | `` |
| `/api/priority-board` | 404 | 0.002695 | `` |
| `/api/screeners/low-buy/priority-board` | 401 | 0.002956 | `` |
| `/api/runtime-tasks/summary` | 401 | 0.003058 | `` |
| `/next/monitor` | 200 | 0.003716 | `` |
| `/next/monitor/market` | 200 | 0.003703 | `` |
| `/next/strategy-tracking` | 200 | 0.004065 | `` |
| `/next/analysis` | 200 | 0.003738 | `` |
| `/next/backtest` | 200 | 0.003391 | `` |
| `/next/data` | 200 | 0.003536 | `` |
| `/next/settings` | 200 | 0.003794 | `` |

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
