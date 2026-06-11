# Cloud Core Worker Resource Runbook

## Scope

This runbook reduces cloud resource contention without changing strategy semantics, `production_score`, priority-board ordering, or low-buy production policy. Use it only after a read-only baseline has been captured.

## Protected Core

Do not stop these services during the resource-contention mitigation path:

| Service | Reason |
|---|---|
| `tquant-app-mysql` | API and frontend-next static entry |
| `tquant-mysql` | Core fact source |
| `tquant-redis` | Cache and event backend |
| `tquant-go-bff-gateway` | Monitor and priority hot-read aggregation |
| `tquant-go-market-read-service` | Quote hot-read service |
| `tquant-go-scan-worker` | Lightweight scan acceleration |
| `tquant-runtime-worker-mysql` | Core task consumer |

Core runtime tasks must continue to enqueue and complete:

- `monitor_snapshot_refresh`
- `market_pulse_refresh`
- `market_quote_cache_refresh`
- `low_buy_materialization_refresh`
- `strategy_tracking_snapshot_refresh`
- `latest_data_watchdog`

## Non-Core Stop Profile

Use this profile to reduce background pressure while keeping the core trading-read path online:

| Setting or service | Target | Effect |
|---|---|---|
| `PLATFORM_AUTOPILOT_ENABLED` | `false` | Stops autopilot task pressure |
| `RUNTIME_LOW_PRIORITY_TASKS_PAUSED` | `true` | Prevents low-priority analytics/backtest/ML/factor/data repair/research tasks from being claimed |
| `MARKET_REVIEW_ENABLED` | `false` | Stops midday/close review report generation |
| `RUNTIME_STARTUP_CACHE_PREWARM_ENABLED` | `false` | Avoids startup prewarm competing with interactive reads |
| `RUNTIME_STARTUP_HISTORY_PREWARM_ENABLED` | `false` | Avoids history prewarm competing with worker tasks |
| `RUNTIME_WORKER_RECYCLE_RSS_MB` | optional, e.g. `700` | Lets runtime-worker exit only after a task finishes when RSS is above the threshold; Docker restart policy brings it back |
| `analytics-worker` | on demand | Runs only through the analytics profile when needed |
| `backtest-worker` | not resident | Long backtests stay out of cloud steady state |

## Read-Only Baseline

Run before any production write:

```bash
ssh -i "$CLOUD_SSH_KEY" -o StrictHostKeyChecking=no "$CLOUD_USER@$CLOUD_HOST" '
set -e
date
uptime
free -m
df -h /
df -ih /
cd /home/ubuntu/gupiao-upload
sudo docker compose -f docker-compose.mysql.yml ps --format "table {{.Name}}\t{{.Status}}"
sudo docker stats --no-stream --format "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | sort
sudo docker system df
curl -sS -o /tmp/readyz.json -w "readyz %{http_code} %{time_total}\n" --max-time 10 http://127.0.0.1:18090/readyz
'
```

For runtime queue evidence:

```bash
ssh -i "$CLOUD_SSH_KEY" -o StrictHostKeyChecking=no "$CLOUD_USER@$CLOUD_HOST" "
cd /home/ubuntu/gupiao-upload &&
sudo docker exec tquant-mysql sh -lc 'mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -D \"\$MYSQL_DATABASE\" -e \"SELECT status, task_type, priority, COUNT(*) AS cnt, MIN(created_at) AS oldest, MAX(updated_at) AS latest FROM runtime_tasks WHERE status IN ('\''queued'\'', '\''running'\'', '\''failed'\'') GROUP BY status, task_type, priority ORDER BY FIELD(status, '\''running'\'', '\''queued'\'', '\''failed'\''), priority DESC, cnt DESC LIMIT 80; SELECT task_type, status, COUNT(*) AS cnt, MAX(updated_at) AS latest FROM runtime_tasks WHERE created_at >= NOW() - INTERVAL 24 HOUR GROUP BY task_type, status ORDER BY cnt DESC LIMIT 80;\"'
"
```

## Authorized Stop Commands

Run only after the operator has explicit approval to modify the remote `.env` and recreate `app`, `runtime-worker`, and `runtime-scheduler`.

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
set -e
cd /home/ubuntu/gupiao-upload
cp .env ".env.resource-stop-backup.$(date +%Y%m%d%H%M%S)"
python3 - <<'"'"'PY'"'"'
from pathlib import Path

path = Path(".env")
pairs = {
    "PLATFORM_AUTOPILOT_ENABLED": "false",
    "RUNTIME_LOW_PRIORITY_TASKS_PAUSED": "true",
    "MARKET_REVIEW_ENABLED": "false",
    "RUNTIME_STARTUP_CACHE_PREWARM_ENABLED": "false",
    "RUNTIME_STARTUP_HISTORY_PREWARM_ENABLED": "false",
    # Optional D6 worker-memory guard; keep disabled until sustained RSS
    # pressure is proven by docker stats/top evidence.
    # "RUNTIME_WORKER_RECYCLE_RSS_MB": "700",
}
lines = path.read_text(encoding="utf-8").splitlines()
seen = set()
out = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in pairs:
        out.append(f"{key}={pairs[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, value in pairs.items():
    if key not in seen:
        out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate app runtime-worker runtime-scheduler
'
```

This command must not restart MySQL, Redis, Go services, or frontend-web.

## Worker Memory Recycle Guard

Use this only after D4/D6 observation proves the runtime worker keeps a high resident set after tasks finish. It does not interrupt a running task: the worker checks RSS after a task has been marked succeeded, failed, or skipped, then exits cleanly if the threshold is reached. Docker `restart: unless-stopped` starts a fresh worker process.

Example enablement for a `768m` worker container:

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
set -e
cd /home/ubuntu/gupiao-upload
cp .env ".env.worker-recycle-backup.$(date +%Y%m%d%H%M%S)"
grep -q "^RUNTIME_WORKER_RECYCLE_RSS_MB=" .env \
  && sed -i "s/^RUNTIME_WORKER_RECYCLE_RSS_MB=.*/RUNTIME_WORKER_RECYCLE_RSS_MB=700/" .env \
  || printf "\nRUNTIME_WORKER_RECYCLE_RSS_MB=700\n" >> .env
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate runtime-worker
'
```

Rollback:

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
set -e
cd /home/ubuntu/gupiao-upload
cp .env.worker-recycle-backup.YYYYMMDDHHMMSS .env
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate runtime-worker
'
```

Post-check:

```bash
sudo docker inspect tquant-runtime-worker-mysql --format "{{.RestartCount}} {{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}"
sudo docker stats --no-stream tquant-runtime-worker-mysql
```

## Embedded Scheduler Cutover

Use this only after the stop profile has passed observation and the operator has explicit approval to stop the standalone scheduler.

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
set -e
cd /home/ubuntu/gupiao-upload
cp .env ".env.scheduler-backup.$(date +%Y%m%d%H%M%S)"
python3 - <<'"'"'PY'"'"'
from pathlib import Path

path = Path(".env")
pairs = {
    "RUNTIME_WORKER_EMBED_SCHEDULER": "true",
    "RUNTIME_SCHEDULER_BACKGROUND_JOBS_ENABLED": "false",
}
lines = path.read_text(encoding="utf-8").splitlines()
seen = set()
out = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in pairs:
        out.append(f"{key}={pairs[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, value in pairs.items():
    if key not in seen:
        out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate runtime-worker
sudo docker rm -f tquant-runtime-scheduler-mysql
'
```

Verify heartbeat after cutover:

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" "
cd /home/ubuntu/gupiao-upload &&
sudo docker exec tquant-mysql sh -lc 'mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -D \"\$MYSQL_DATABASE\" -e \"SELECT component, worker_id, status, updated_at FROM platform_component_heartbeats WHERE component = '\''runtime-scheduler'\'' ORDER BY updated_at DESC LIMIT 5;\"'
"
```

Expected worker id: `runtime-worker-embedded-scheduler`.

## Observation

Collect every 30 minutes during the stop-profile window and at least at open, midday, close, and post-close after scheduler cutover:

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
date
uptime
free -m
cd /home/ubuntu/gupiao-upload
sudo docker stats --no-stream --format "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | sort
curl -sS -o /tmp/readyz.json -w "readyz %{http_code} %{time_total}\n" --max-time 10 http://127.0.0.1:18090/readyz
curl -sS -o /tmp/snapshot.json -w "monitor_snapshot %{http_code} %{time_total}\n" --max-time 20 http://127.0.0.1:18090/api/monitor/snapshot
curl -sS -o /tmp/priority.json -w "priority_board %{http_code} %{time_total}\n" --max-time 20 http://127.0.0.1:18090/api/screeners/low-buy/priority-board
'
```

Unauthenticated protected APIs may return `401`; timeout or `5xx` is the failure signal.

## Rollback

Stop-profile rollback:

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
set -e
cd /home/ubuntu/gupiao-upload
cp .env.resource-stop-backup.YYYYMMDDHHMMSS .env
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate app runtime-worker runtime-scheduler
'
```

Embedded-scheduler rollback:

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
set -e
cd /home/ubuntu/gupiao-upload
cp .env.scheduler-backup.YYYYMMDDHHMMSS .env
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate runtime-worker runtime-scheduler
'
```

## Report Fields

Every rollout report must include:

- git status before and after
- exact authorized commands run
- whether any write/restart/cleanup/deploy occurred
- uptime, load, memory, swap, disk, inode
- `docker ps`, `docker stats`, `docker system df`
- core runtime task status
- scheduler heartbeat
- `/readyz` and core API status and latency
- rollback command for each write
- P0/P1/P2/P3 risks with evidence
