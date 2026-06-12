# Worker Runbook

Date: 2026-06-04.

This runbook covers independent worker operation for the modular monolith
baseline. It is not a microservice split; workers reuse the same codebase and
database contracts as Web.

## Worker Types

| Worker | Entry point | Queue / source | Heavy work |
|---|---|---|---|
| Runtime worker | `python -m app.workers.runtime_worker` | `runtime_tasks` | data backfill, latest-bar refresh, low-buy materialization, repair tasks |
| Runtime scheduler | `python -m app.workers.runtime_scheduler` | scheduled enqueue logic | close refresh, watchdog, periodic data-quality enqueue |
| Analytics worker | `backend/scripts/analytics_worker.py` | analytics RuntimeTask registry | On-demand Parquet export, DuckDB strategy report, analytics quality checks |

Local wrappers:

```bash
scripts/run_platform_component.sh runtime-worker
scripts/run_platform_component.sh scheduler
scripts/run_platform_component.sh analytics-worker
```

## Runtime Worker

Health:

- `runtime_worker.heartbeat` exists and is recent
- critical runtime tasks are not queued longer than the runbook threshold
- failures are explicit: `blocked`, `stale`, `no_data`, `insufficient`, or
  task-specific failure reason

Inspect:

```bash
docker compose -f docker-compose.mysql.yml logs --tail=200 runtime-worker
docker compose -f docker-compose.mysql.yml exec mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "select task_type,status,count(*) from t_quant.runtime_tasks group by task_type,status;"
```

Recover:

```bash
docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate runtime-worker
```

Do not re-run heavy data refresh from Web request paths. Queue a runtime task or
start the worker.

## Runtime Scheduler

Health:

- scheduler container is running
- scheduled task enqueue logs are present
- duplicate scheduler loops are not enabled in Web

Recover:

```bash
docker compose -f docker-compose.mysql.yml up -d --no-build --force-recreate runtime-scheduler
```

Web must keep `RUNTIME_BACKGROUND_JOBS_ENABLED=false`; scheduler owns periodic
enqueue.

### Scheduler Grey Mode

`runtime-worker` may embed scheduler loops only during an explicit grey run:

```bash
python3 scripts/verify_d5_scheduler_embed_gate.py \
  --summary docs/reports/cloud-resource-trading-day-gate-summary-2026-06-12.json \
  --fail-on-blocked

DEPLOY_D5_GATE_SUMMARY=docs/reports/cloud-resource-trading-day-gate-summary-2026-06-12.json \
scripts/quick_cloud_deploy.sh --scope worker --embed-runtime-scheduler
```

The embedded path keeps using the runtime background leader lock and records a
`runtime-scheduler` heartbeat with worker id `runtime-worker-embedded-scheduler`.
Do not stop the independent scheduler or run the embed deploy until the D5 gate
confirms one full trading day of periodic enqueue, latest-data watchdog, quote
refresh, materialization refresh, and close-publish behavior. Roll back by setting
`RUNTIME_WORKER_EMBED_SCHEDULER=false` and recreating `runtime-scheduler`.

## Analytics Worker

Analytics, long backtest, ML, and factor-mining work is not part of the
small-host always-on profile. Keep these task families gated by
`RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true` on resident runtime processes, and run
`analytics-worker` only for an explicit maintenance window or one-shot job.

Health:

- `duckdb` and `pyarrow` import successfully
- analytics task registry can claim `analytics_export_daily_bars`,
  `analytics_quality_check`, `strategy_24m_duckdb_report`, and related analytics
  tasks
- output manifests and reports are written as artifacts, not production facts

Inspect:

```bash
docker compose --profile analytics -f docker-compose.mysql.yml logs --tail=200 analytics-worker
docker compose --profile analytics -f docker-compose.mysql.yml exec analytics-worker python -c "import duckdb, pyarrow; print('analytics-ready')"
```

Recover:

```bash
docker compose --profile analytics -f docker-compose.mysql.yml up -d --no-build --force-recreate analytics-worker
```

If dependencies are missing, analytics-worker should fail fast. Do not silently
fall back to Web computation.

Stop after low-frequency analytics work completes:

```bash
docker compose --profile analytics -f docker-compose.mysql.yml stop analytics-worker
```

Before making analytics-worker resident, record the reason, expected runtime,
resource budget, rollback command, and confirmation that core monitor,
low-buy, priority-board, strategy tracking, latest-data watchdog, MySQL, Redis,
and Go hot-read services will not be stopped.

## Backtest Worker

Health:

- strategy research artifacts are reviewed through runtime/analytics task status
- long-running analytics jobs report progress or a bounded failure reason
- `portfolio_backtest_metrics` remains the final portfolio fact source

Inspect:

```bash
docker compose --profile analytics -f docker-compose.mysql.yml logs --tail=200 analytics-worker
```

Recover:

```bash
docker compose --profile analytics -f docker-compose.mysql.yml up -d --no-build --force-recreate analytics-worker
```

Do not parallelize `portfolio_backtest_metrics` by month or recompute max5/max10
outside the audited portfolio path.

## Local Smoke

Inspect commands without starting processes:

```bash
scripts/run_platform_component.sh web --print-command
scripts/run_platform_component.sh runtime-worker --print-command
scripts/run_platform_component.sh scheduler --print-command
scripts/run_platform_component.sh analytics-worker --print-command
```

For a local Web + runtime-worker pair:

```bash
scripts/dev_start_all.sh
```

For a one-shot analytics task claim in a prepared local database:

```bash
scripts/run_platform_component.sh analytics-worker --once
```

## Escalation

If Web is healthy but data is stale, inspect runtime-worker and scheduler first.
If analysis reports are missing, inspect analytics-worker. Avoid treating a stale
analysis artifact as a production trading signal.
