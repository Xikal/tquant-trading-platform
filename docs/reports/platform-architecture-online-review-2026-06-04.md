# Platform Architecture Online Review

Status: A1 online evidence collected  
Date: 2026-06-04  
Scope: read-only online architecture acceptance evidence for Web, workers,
analytics dependencies, deploy sync mode, and performance reports

## Commands

```bash
curl -sS --max-time 10 http://43.143.243.97:18090/readyz

ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97 \
  "sudo docker ps --format '{{.Names}} {{.Status}}' | grep -E 'tquant-(app|runtime-worker|runtime-scheduler|backtest-worker|analytics-worker|mysql|redis)'"

ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97 \
  "sudo docker exec tquant-analytics-worker-mysql python -c 'import duckdb, pyarrow; from app.core.database import ping_database; print(duckdb.__version__); print(pyarrow.__version__); print(ping_database())'"

ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97 \
  "sudo docker logs --tail=80 tquant-analytics-worker-mysql 2>&1"
```

No deployment, restart, data mutation, or task submission was performed in A1.

## Web Health

```json
{"status":"ok","app":"维斯量化交易平台","checks":{"database":true,"frontend_dist":true,"analytics_dependencies":true},"errors":[]}
```

Result: Web readyz is healthy and analytics dependencies are visible from the
Web health check.

## Container State

| Container | State |
|---|---|
| `tquant-runtime-scheduler-mysql` | `Up 3 hours (healthy)` |
| `tquant-backtest-worker-mysql` | `Up 3 hours` |
| `tquant-analytics-worker-mysql` | `Up 3 hours (healthy)` |
| `tquant-runtime-worker-mysql` | `Up 3 hours (healthy)` |
| `tquant-app-mysql` | `Up 3 hours (healthy)` |
| `tquant-mysql` | `Up 7 hours (healthy)` |
| `tquant-redis` | `Up 12 days (healthy)` |

Backtest worker is running but has no configured Docker healthcheck:

```text
no_healthcheck
running true 2026-06-04T08:21:04.143874104Z
```

Follow-up: add a backtest-worker healthcheck or heartbeat endpoint if operations
need `healthy` instead of Docker `running`.

## Analytics Worker Evidence

Dependency check:

```text
1.5.3
22.0.0
None
```

Interpretation:

- DuckDB imports successfully.
- PyArrow imports successfully.
- `ping_database()` returned no error.

Registered task types from worker log:

```text
analytics_export_daily_bars
analytics_quality_check
backtest_all_strategies_24m
data_backfill_24m
data_quality_backfill
data_quality_sla_refresh
data_repair_run
decision_context_24m_report
portfolio_execution_24m_report
realized_outcome_refresh
strategy_24m_duckdb_report
strategy_drift_refresh
```

## Deploy Evidence

Latest successful run:

- GitHub Actions run: `26939035586`
- Deploy job: `79476390009`
- Head SHA: `1824b363a3bfdf4b2900fe4c2e881ab4e6bf1335`
- Conclusion: `success`

Deploy sync metrics:

```text
requested_mode=delta-package
sync_mode=package-only
changed_count=0
deleted_count=0
delta_bytes=0
full_bytes=6477745
upload_seconds=397
fallback_reason=invalid_remote_manifest
```

Current remote manifest status after the successful deployment:

```text
manifest_ok 1 2343 47777433
```

Interpretation: the final deployment used the safe package-only fallback because
the previous remote manifest was invalid during the deploy step. The currently
stored remote manifest is valid, so a later deployment can test actual delta
upload behavior.

## Performance Evidence

Two successful online performance runs were already collected after the latest
deploy:

| Report | Result |
|---|---|
| `docs/reports/gupiao-cloud-performance-2026-06-04-162901.json` | `ok=true` |
| `docs/reports/gupiao-cloud-performance-2026-06-04-163020.json` | `ok=true` |

Selected p95 values:

| Metric | Round 1 p95 ms | Round 2 p95 ms |
|---|---:|---:|
| readyz | 11.189 | 15.417 |
| monitor BFF | 235.940 | 35.025 |
| market pulse | 49.566 | 14.483 |
| scan worker accept | 428.732 | 180.119 |

## Conclusion

A1 online evidence is complete. The platform is online with Web, runtime
scheduler, runtime worker, analytics worker, backtest worker, MySQL, and Redis
running independently. The only observed operational gap is that backtest worker
is `running` without a Docker healthcheck.
