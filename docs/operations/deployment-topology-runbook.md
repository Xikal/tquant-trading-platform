# Deployment Topology Runbook

Date: 2026-06-04.

This platform stays a modular monolith. The deploy topology separates process
roles so Web handles light reads/task submission/status while heavy refresh,
analytics, and backtest work runs outside Web.

## Process Roles

| Role | Production service | Local command | Responsibility |
|---|---|---|---|
| Web/API | `app` | `scripts/run_platform_component.sh web` | FastAPI app, lightweight reads, task submission, task status |
| Runtime worker | `runtime-worker` | `scripts/run_platform_component.sh runtime-worker` | data refresh, materialization, repair, close-refresh tasks |
| Runtime scheduler | `runtime-scheduler` | `scripts/run_platform_component.sh scheduler` | schedules runtime tasks, does not serve Web requests |
| Analytics worker | `analytics-worker` | `scripts/run_platform_component.sh analytics-worker` | Parquet export, DuckDB reports, data-quality analytics tasks |
| Backtest worker | `backtest-worker` | `scripts/run_platform_component.sh backtest-worker` | queued backtest jobs and long-running backtest execution |
| MySQL | `mysql` | local SQLite only for development | production operational fact store |
| Redis | `redis` | optional locally | cache/rate-limit support |

Production service names come from `docker-compose.mysql.yml`. Local commands
are intentionally thin wrappers around the same Python module entrypoints.

## Health Checks

Use these checks before and after process restarts:

```bash
curl -fsS http://127.0.0.1:${CLOUD_APP_PORT:-18090}/readyz
curl -fsS http://127.0.0.1:${CLOUD_APP_PORT:-18090}/metrics
docker compose -f docker-compose.mysql.yml ps
docker compose -f docker-compose.mysql.yml logs --tail=120 runtime-worker
docker compose -f docker-compose.mysql.yml logs --tail=120 runtime-scheduler
docker compose -f docker-compose.mysql.yml logs --tail=120 analytics-worker
docker compose -f docker-compose.mysql.yml logs --tail=120 backtest-worker
```

Worker-specific checks:

- Runtime worker heartbeat: `runtime_worker.heartbeat`
- Runtime tasks: queued/running/failed age and task type
- Analytics dependencies: `duckdb` and `pyarrow` import check
- Backtest worker: queued job age and stuck running jobs
- DB connectivity: `/readyz` database check and worker logs

## Restart Matrix

| Operation | Command | Expected effect |
|---|---|---|
| Restart Web only | `docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate app` | Existing queued tasks remain in `runtime_tasks` / backtest tables |
| Restart runtime worker | `docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate runtime-worker` | Claimed tasks recover through queue retry/failure rules |
| Restart scheduler | `docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate runtime-scheduler` | New scheduled tasks resume; existing queued tasks stay intact |
| Restart analytics worker | `docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate analytics-worker` | Analytics tasks continue after claim/retry handling |
| Restart backtest worker | `docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate backtest-worker` | Queued backtests continue; running jobs must be inspected before retry |

Do not enable background scheduling loops in the Web process. Web defaults keep
`RUNTIME_BACKGROUND_JOBS_ENABLED=false`.

## Deploy Script Entry Points

Safe defaults:

```bash
scripts/one_click_cloud_deploy.sh --safe
scripts/quick_cloud_deploy.sh --verify-only
```

Scoped paths:

```bash
scripts/one_click_cloud_deploy.sh --scope frontend-hot --frontend-hot-required
scripts/one_click_cloud_deploy.sh --scope go
scripts/one_click_cloud_deploy.sh --scope all --full
```

Local single-process entrypoints:

```bash
scripts/run_platform_component.sh web
scripts/run_platform_component.sh runtime-worker
scripts/run_platform_component.sh scheduler
scripts/run_platform_component.sh analytics-worker
scripts/run_platform_component.sh backtest-worker
```

Use `--print-command` to inspect the exact command without starting a process.

## Rollback

1. Stop write-heavy workers before restoring data:

   ```bash
   docker compose -f docker-compose.mysql.yml stop runtime-scheduler runtime-worker analytics-worker backtest-worker
   ```

2. Restore the database backup or previous MySQL volume snapshot.
3. Recreate Web and workers from the previous image/tag.
4. Run `/readyz`, `/metrics`, runtime worker heartbeat, and queue-age checks.
5. Restart workers only after Web and DB are healthy.

## Boundaries

- DuckDB/Parquet is analysis/reporting only and is not a production trading fact
  source.
- Web does not recompute 24-month reports, Parquet export, batch strategy
  validation, or data backfill in request paths.
- Production ranking and strategy gates are not changed by restarting workers or
  re-running analysis reports.
