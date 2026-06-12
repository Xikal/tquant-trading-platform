# Deployment Topology Runbook

Date: 2026-06-04.

This platform stays a modular monolith. The deploy topology separates process
roles so Web handles light reads/task submission/status while refresh and
analytics work runs outside Web.

## Process Roles

| Role | Production service | Local command | Responsibility |
|---|---|---|---|
| Web/API | `app` | `scripts/run_platform_component.sh web` | FastAPI app, lightweight reads, task submission, task status |
| Runtime worker | `runtime-worker` | `scripts/run_platform_component.sh runtime-worker` | data refresh, materialization, repair, close-refresh tasks |
| Runtime scheduler | `runtime-scheduler` | `scripts/run_platform_component.sh scheduler` | schedules runtime tasks, does not serve Web requests |
| Analytics worker | `analytics-worker` profile | `scripts/run_platform_component.sh analytics-worker` | On-demand Parquet export, DuckDB reports, data-quality analytics tasks |
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
docker compose --profile analytics -f docker-compose.mysql.yml logs --tail=120 analytics-worker
```

Worker-specific checks:

- Runtime worker heartbeat: `runtime_worker.heartbeat`
- Runtime tasks: queued/running/failed age and task type
- Analytics dependencies: `duckdb` and `pyarrow` import check
- DB connectivity: `/readyz` database check and worker logs

## Restart Matrix

| Operation | Command | Expected effect |
|---|---|---|
| Restart Web only | `docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate app` | Existing queued tasks remain in `runtime_tasks` / backtest tables |
| Restart runtime worker | `docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate runtime-worker` | Claimed tasks recover through queue retry/failure rules |
| Restart scheduler | `docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate runtime-scheduler` | New scheduled tasks resume; existing queued tasks stay intact |
| Restart analytics worker on demand | `docker compose --profile analytics -f docker-compose.mysql.yml up -d --no-build --force-recreate analytics-worker` | Analytics tasks continue after claim/retry handling |

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
scripts/one_click_cloud_deploy.sh --scope frontend-next --frontend-next-required
scripts/one_click_cloud_deploy.sh --scope go
scripts/one_click_cloud_deploy.sh --scope all --full
```

Retired frontend scopes are intentionally blocked:

```bash
python3 scripts/deploy_scope.py --scope frontend-hot
python3 scripts/deploy_scope.py --scope frontend-legacy
```

Both commands must return `blocked` and tell the operator to deploy
`frontend-next` instead. Do not reintroduce `frontend-hot`,
`frontend-legacy`, `html-root`, or `/__legacy/assets/` as a production path.

Delta upload path:

```bash
DEPLOY_SYNC_MODE=delta-package scripts/one_click_cloud_deploy.sh --scope all
DEPLOY_SYNC_MODE=package-only scripts/one_click_cloud_deploy.sh --scope all
```

`delta-package` compares the local deploy manifest with
`.runtime/deploy-manifest.json` on the current release. It uploads changed/new
files plus a manifest-bounded delete list. Missing manifests, critical path
changes, high change ratios, unsafe deletes, or remote staging validation
automatically fall back to `package-only`. Remote GitHub clone/fetch remains
explicit opt-in through `git-inplace` or `git-clone`.

Deploy logs must include:

```text
sync_mode=<delta-package|package-only>
changed_count=<n>
deleted_count=<n>
delta_bytes=<bytes>
full_bytes=<bytes>
upload_seconds=<seconds>
fallback_reason=<reason|none>
```

Local single-process entrypoints:

```bash
scripts/run_platform_component.sh web
scripts/run_platform_component.sh runtime-worker
scripts/run_platform_component.sh scheduler
scripts/run_platform_component.sh analytics-worker
```

Use `--print-command` to inspect the exact command without starting a process.

## Optional Analytics Worker

`analytics-worker` is not part of the default always-on small-host profile. Start
and verify it only when running analytics exports, 24-month DuckDB reports, or
data-quality repair tasks:

```bash
docker compose --profile analytics -f docker-compose.mysql.yml up -d --no-build --force-recreate analytics-worker
docker compose --profile analytics -f docker-compose.mysql.yml exec analytics-worker python -c "import duckdb, pyarrow; from app.core.database import ping_database; ping_database(); print('analytics-ready')"
```

For deployment scripts, pass the explicit switch:

```bash
DEPLOY_WITH_ANALYTICS_WORKER=1 scripts/deploy_cloud_server.sh
scripts/quick_cloud_deploy.sh --with-analytics-worker
```

After the job finishes, stop only the optional profile service:

```bash
docker compose --profile analytics -f docker-compose.mysql.yml stop analytics-worker
```

Default deploy and verify flows print `analytics_worker:skipped_on_demand` when
the optional worker is intentionally absent.

## Scheduler Grey Flag

The default topology still runs the independent `runtime-scheduler` container.
For small-host memory grey validation, `runtime-worker` can embed the scheduler
only when `RUNTIME_WORKER_EMBED_SCHEDULER=true`. Keep the independent scheduler
running until one full trading day confirms scheduled enqueue, latest-data
watchdog, and close-publish behavior. If validation fails, set
`RUNTIME_WORKER_EMBED_SCHEDULER=false` and recreate `runtime-scheduler`.

## Rollback

Per-process rollback/restart:

```bash
docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate app
docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate runtime-worker
docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate runtime-scheduler
docker compose --profile analytics -f docker-compose.mysql.yml up -d --no-build --force-recreate analytics-worker
```

Release rollback:

1. Stop write-heavy workers before restoring data:

   ```bash
   docker compose --profile analytics -f docker-compose.mysql.yml stop runtime-scheduler runtime-worker analytics-worker
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
