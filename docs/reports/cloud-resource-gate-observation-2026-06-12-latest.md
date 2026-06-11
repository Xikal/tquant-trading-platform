# Cloud Resource Gate Observation

- Generated at: `2026-06-11T20:23:01.614869+00:00`
- Checkpoint: `pre-d5-wait-0422`
- Source: `ubuntu@43.143.243.97`
- Evaluation: `warning`
- D5 embedded scheduler ready: `false`
- D5 blockers: full_trading_day_observation_incomplete
- Blocking: none
- Warnings: scheduler_provider_warning_lines_observed=18, mysql_slow_queries=55

## Host

| Metric | Value |
| --- | --- |
| Date | `Fri Jun 12 04:22:57 CST 2026` |
| Uptime | `04:22:57 up 3 days, 17:07, 713 users,  load average: 0.58, 0.58, 0.40` |
| Memory available MB | 1337 |
| Swap used percent | 32.66 |
| Root used percent | 63 |
| Root inode used percent | 13 |

## Containers

| Container | CPU | Memory | Memory % |
| --- | ---: | ---: | ---: |
| `tquant-runtime-scheduler-mysql` | 0.00% | 254.4MiB / 640MiB | 39.75% |
| `tquant-runtime-worker-mysql` | 0.49% | 296.1MiB / 768MiB | 38.55% |
| `tquant-mysql` | 0.84% | 863.9MiB / 1.5GiB | 56.25% |
| `tquant-app-mysql` | 0.13% | 60.25MiB / 768MiB | 7.85% |
| `tquant-frontend-web` | 0.00% | 2.711MiB / 128MiB | 2.12% |
| `tquant-go-bff-gateway` | 0.00% | 5.246MiB / 128MiB | 4.10% |
| `tquant-go-market-read-service` | 2.42% | 7.891MiB / 128MiB | 6.16% |
| `tquant-go-scan-worker` | 0.00% | 5.887MiB / 128MiB | 4.60% |
| `tquant-redis` | 0.52% | 4.961MiB / 128MiB | 3.88% |

## HTTP

| Path | Status | Time | Error |
| --- | ---: | ---: | --- |
| `/readyz` | 200 | 0.00364 | `` |
| `/api/monitor` | 404 | 0.003864 | `` |
| `/api/monitor/snapshot` | 401 | 0.003114 | `` |
| `/api/priority-board` | 404 | 0.002513 | `` |
| `/api/screeners/low-buy/priority-board` | 401 | 0.002654 | `` |
| `/api/runtime-tasks/summary` | 401 | 0.002576 | `` |
| `/next/monitor` | 200 | 0.003549 | `` |
| `/next/monitor/market` | 200 | 0.003113 | `` |
| `/next/strategy-tracking` | 200 | 0.003143 | `` |
| `/next/analysis` | 200 | 0.003156 | `` |
| `/next/backtest` | 200 | 0.003259 | `` |
| `/next/data` | 200 | 0.003104 | `` |
| `/next/settings` | 200 | 0.003187 | `` |

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
| `low_buy_materialization_refresh` | succeeded | 4 | 2026-06-11 18:24:35 | 2026-06-11 19:57:59 |

## Operations Not Executed

- No .env change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.
