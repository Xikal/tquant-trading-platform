# Platform Architecture Performance Review

Status: A7 completed with one failed sample and one passing sample  
Date: 2026-06-04  
Scope: online read-only performance and stability comparison for the currently
deployed platform, plus a local-code-state boundary note

## Boundary

This report covers online evidence collected from the currently deployed
service at `http://43.143.243.97:18090`. The A2-A6 local changes in this working
tree have not been deployed, so online measurements do not include the new
runtime task observability API or frontend worker observability panel.

No deployment, restart, data mutation, or destructive command was executed for
A7.

## Commands

```bash
curl -sS --max-time 10 http://43.143.243.97:18090/readyz

ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97 \
  "sudo docker ps --format '{{.Names}} {{.Status}}' | grep -E 'tquant-(app|runtime-worker|runtime-scheduler|backtest-worker|analytics-worker|mysql|redis)'"

python3 scripts/measure_cloud_go_rust_performance.py --samples 8
python3 scripts/measure_cloud_go_rust_performance.py --samples 8
```

The project does not currently have `scripts/check_cloud_performance.py`; A7
used the existing `scripts/measure_cloud_go_rust_performance.py` performance
script and recorded the generated JSON reports.

## Online Health

`/readyz` returned:

```json
{"status":"ok","app":"维斯量化交易平台","checks":{"database":true,"frontend_dist":true,"analytics_dependencies":true},"errors":[]}
```

Container status:

| Container | Status |
|---|---|
| `tquant-runtime-scheduler-mysql` | `Up 3 hours (healthy)` |
| `tquant-backtest-worker-mysql` | `Up 3 hours` |
| `tquant-analytics-worker-mysql` | `Up 3 hours (healthy)` |
| `tquant-runtime-worker-mysql` | `Up 3 hours (healthy)` |
| `tquant-app-mysql` | `Up 3 hours (healthy)` |
| `tquant-mysql` | `Up 7 hours (healthy)` |
| `tquant-redis` | `Up 12 days (healthy)` |

The backtest worker is running but still lacks a Docker healthcheck, so it is
not shown as `(healthy)` by Docker.

## Performance Samples

| Report | Time | Overall |
|---|---|---|
| `docs/reports/gupiao-cloud-performance-2026-06-04-162901.json` | 16:29:01 | `ok=true` |
| `docs/reports/gupiao-cloud-performance-2026-06-04-163020.json` | 16:30:20 | `ok=true` |
| `docs/reports/gupiao-cloud-performance-2026-06-04-195129.json` | 19:51:29 | `ok=false` |
| `docs/reports/gupiao-cloud-performance-2026-06-04-195304.json` | 19:53:04 | `ok=true` |

Selected p95 latency:

| Metric | 16:29 p95 ms | 16:30 p95 ms | 19:51 p95 ms | 19:53 p95 ms |
|---|---:|---:|---:|---:|
| readyz | 11.189 | 15.417 | 6.986 | 19.996 |
| monitor BFF | 235.940 | 35.025 | 852.110 | 81.728 |
| market pulse | 49.566 | 14.483 | 142.851 | 69.948 |
| priority board | 146.492 | 59.750 | 1101.142 | 71.934 |
| watchlist signals | 23.933 | 10.342 | 152.383 | 14.459 |
| scan worker accept | 428.732 | 180.119 | 232.889 | 224.940 |

Status codes stayed stable:

| Metric | Online status |
|---|---|
| readyz | `200` |
| monitor BFF | `200` |
| market pulse | `200` |
| priority board | `200` |
| watchlist signals | `200` |
| scan worker accept | `202` |

The 19:51 run failed threshold checks because `monitor_bff` p95 was
`852.110 ms` and `priority_board` p95 was `1101.142 ms`, both above the script
threshold of `500 ms`. The 19:53 run passed threshold checks, but warning-level
observability alerts remained.

## Observability Alerts

| Report | BFF timeouts | BFF status failures | Market unresolved misses | Market fallbacks | Quote cache coverage |
|---|---:|---:|---:|---:|---:|
| 16:29 | 10 | 1 | 20 | 5 | 10000 bps |
| 16:30 | 12 | 2 | 28 | 7 | 10000 bps |
| 19:51 | 45 | 3 | 171 | 81 | 10000 bps |
| 19:53 | 47 | 4 | 183 | 84 | 10000 bps |

Interpretation:

- Quote cache coverage for the measured symbols stayed complete.
- BFF partial source timeouts increased in the later samples.
- Market-read unresolved misses and fallback counts increased in the later
  samples.
- The warnings did not prevent the second A7 sample from passing latency
  thresholds, but they are not a long-term stability green light.

## Runtime And Worker Metrics

The deployed API does not yet expose the A6 local runtime task observability
endpoints, because A6 was not deployed in this follow-up run. Therefore these
A7 metrics remain partially unavailable online:

| Metric | A7 online availability | Evidence |
|---|---|---|
| Runtime task submit latency | partial | `scan_worker_accept` returned `202`, p95 `232.889/224.940 ms` in the two A7 samples |
| Analytics task claim latency | not available | no deployed worker observability endpoint yet |
| DuckDB report task duration | not available online | local DuckDB report command is covered in final verification |
| Worker failure rate | partial | containers running; no deployed task failure endpoint yet |
| Queue longest wait | not available | local A6 endpoint implemented, not deployed |

## Stability Conclusion

The currently deployed platform is online and the second A7 measurement passed
the script thresholds. The first A7 measurement failed due to p95 spikes on
monitor BFF and priority board. Warning-level observability alerts persisted in
both A7 samples, especially BFF source timeouts and market-read fallback/miss
counts.

Next performance work should investigate slow Python source endpoints behind
the BFF, market-read fallback volume, unresolved miss reasons, and a Docker or
application heartbeat for the backtest worker. The local A6 observability
surface should be deployed in a controlled release before using queue wait time
and worker failure rate as online acceptance gates.
