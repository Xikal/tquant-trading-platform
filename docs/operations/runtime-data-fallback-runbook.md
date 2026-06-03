# Runtime Data Fallback Runbook

## Local Startup

Run Web and the runtime worker together:

```bash
cd /Users/j/Documents/gupiao
scripts/dev_start_all.sh
```

The script keeps Web request paths read-first. Refresh, repair, and materialization tasks are consumed by `runtime-worker`.

Manual worker-only run:

```bash
cd /Users/j/Documents/gupiao/backend
PYTHONPATH=. DATABASE_URL=sqlite:///./data/t_quant.db .venv/bin/python -m app.workers.runtime_worker
```

Manual Hermes daily-bar watchdog:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/hermes_daily_bar_watchdog.py --trade-date 2026-06-03 --no-notify
PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/hermes_daily_bar_watchdog.py --force-notify
```

## Production Startup

```bash
docker compose -f docker-compose.mysql.yml up -d app runtime-worker runtime-scheduler
docker compose -f docker-compose.mysql.yml logs -f runtime-worker
docker compose -f docker-compose.mysql.yml logs -f runtime-scheduler
```

## API Checks

```bash
curl -s http://127.0.0.1:8000/readyz
curl -s http://127.0.0.1:8000/api/data-quality/runtime-fallback
```

Expected healthy state:

- `worker_status=running`
- `blocking=false`
- `critical_queued_count=0`, or no critical task older than 600 seconds

## SQL Checks

```sql
select trade_date, count(*) from daily_bar_snapshots group by trade_date order by trade_date desc limit 5;
select task_type, status, count(*) from runtime_tasks group by task_type, status;
select value from system_settings where `key` = 'low_buy.latest_data';
select value from system_settings where `key` = 'runtime_worker.heartbeat';
```

Critical queue detail:

```sql
select id, task_type, status, created_at, started_at, locked_by
from runtime_tasks
where task_type in (
  'daily_bar_refresh',
  'low_buy_materialization_refresh',
  'strategy_tracking_snapshot_refresh',
  'a_key_level_materialization_refresh',
  'monitor_snapshot_refresh'
)
and status in ('queued', 'running')
order by created_at asc
limit 20;
```

## Repair Commands

Queue close-refresh follow-up from the API/runtime task surface; do not compute in Web request paths. For direct worker recovery:

```bash
docker compose -f docker-compose.mysql.yml up -d runtime-worker runtime-scheduler
docker compose -f docker-compose.mysql.yml logs -f runtime-worker
```

If daily bars remain below the minimum after refresh, inspect provider logs and rerun the daily refresh task from the data console. Do not lower strategy thresholds or publish stale recommendations.

## Decision Table

| Symptom | Likely Cause | Action |
|---|---|---|
| critical tasks queued > 10 min | worker stopped | start runtime-worker |
| daily bars below 4500 | data source or refresh incomplete | rerun daily refresh, inspect provider logs |
| materialization missing | strategy snapshot not built | enqueue latest close refresh |
| page empty with warning | safe fallback active | fix data pipeline, do not lower strategy threshold |

## Boundaries

- Fallback means repair, queue, warn, and block safely.
- Do not fabricate daily bars, scores, or recommendation tickets.
- Do not lower low-buy or strategy thresholds to hide missing data.
- Web handlers should not perform heavy refresh, scan, or materialization work.
