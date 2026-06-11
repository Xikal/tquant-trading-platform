# Cloud Resource Contention Trading Day Observation - 2026-06-12

## Scope

This report is the D5 gate observation template and current decision record for the cloud resource contention remediation plan. It is read-only unless a later section explicitly records an authorized operation.

## Current Decision

D5 embedded scheduler is not executed yet.

Reason: the worker recycle guard is now live and the current worker RSS is low, but this is still a short post-rollout window. The plan requires a longer stable window, preferably a full trading day, before moving standalone scheduler work into runtime-worker.

## Must Keep Running

| Service / capability | Requirement |
|---|---|
| MySQL | healthy, no OOM |
| Redis | healthy, no eviction pressure |
| app / API | `/readyz` 200; protected APIs return 401 quickly when unauthenticated |
| frontend-next | core `/next/*` pages return 200 |
| Go hot-read / scan | containers healthy |
| runtime-worker | core tasks complete; RSS controlled by recycle guard if needed |
| runtime-scheduler | remains standalone until D5 gate passes |
| low-buy / priority board / strategy tracking | task freshness and semantics unchanged |

## Observation Schedule

Record all sections below at these Beijing-time checkpoints:

| Time | Purpose | Completed |
|---|---|---|
| 09:15 | pre-open baseline | no |
| 09:35 | after open pressure | no |
| 10:30 | sustained morning load | no |
| 11:30 | midday close | no |
| 13:05 | afternoon reopen | no |
| 14:55 | close pressure | no |
| 15:10 | post-close tasks | no |
| 15:30 | close-refresh cooldown | no |

## Read-Only Commands

### Host And Containers

```bash
ssh -i /Users/j/Downloads/gupiao.pem -o StrictHostKeyChecking=no ubuntu@43.143.243.97 '
set -e
cd /home/ubuntu/gupiao-upload
date
uptime
free -m
df -h /
df -ih /
sudo docker compose -f docker-compose.mysql.yml ps --format "table {{.Name}}\t{{.Status}}"
sudo docker stats --no-stream --format "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | sort
sudo journalctl -k --since "2026-06-12 00:00:00" --no-pager | egrep -i "out of memory|oom|killed process" | tail -40 || true
'
```

### HTTP And Pages

```bash
ssh -i /Users/j/Downloads/gupiao.pem -o StrictHostKeyChecking=no ubuntu@43.143.243.97 '
for path in /readyz /api/monitor /api/monitor/snapshot /api/priority-board /api/screeners/low-buy/priority-board /api/runtime-tasks/summary /next/monitor /next/monitor/market /next/strategy-tracking /next/analysis /next/backtest /next/data /next/settings; do
  curl -sS -o /tmp/gupiao-observe.out -w "$path %{http_code} %{time_total}\n" --max-time 20 "http://127.0.0.1:18090$path" || true
done
'
```

### MySQL, Queue, Heartbeats

```bash
ssh -i /Users/j/Downloads/gupiao.pem -o StrictHostKeyChecking=no ubuntu@43.143.243.97 "
cd /home/ubuntu/gupiao-upload &&
sudo docker exec tquant-mysql sh -lc 'mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -D \"\$MYSQL_DATABASE\" -e \"SHOW GLOBAL STATUS LIKE '\''Threads_%'\''; SHOW GLOBAL STATUS LIKE '\''Slow_queries'\''; SHOW VARIABLES LIKE '\''max_connections'\''; SHOW VARIABLES LIKE '\''innodb_buffer_pool_size'\''; SELECT task_type,status,COUNT(*) cnt,MIN(created_at) oldest,MAX(updated_at) latest FROM runtime_tasks WHERE created_at >= NOW() - INTERVAL 2 HOUR GROUP BY task_type,status ORDER BY cnt DESC, task_type LIMIT 60; SELECT status,task_type,priority,COUNT(*) cnt,MIN(created_at) oldest,MAX(updated_at) latest FROM runtime_tasks WHERE status IN ('\''queued'\'','\''running'\'') GROUP BY status,task_type,priority ORDER BY FIELD(status,'\''running'\'','\''queued'\''),priority DESC,cnt DESC LIMIT 40; SELECT \\\`key\\\`,updated_at,LEFT(value,220) value_prefix FROM system_settings WHERE \\\`key\\\` IN ('\''platform_component.heartbeat.runtime-scheduler'\'','\''platform_component.heartbeat.runtime-worker'\'','\''runtime_worker.heartbeat'\'') ORDER BY \\\`key\\\`;\"'
"
```

## Gate Criteria For D5

All criteria must pass before enabling embedded scheduler:

| Criterion | Required evidence | Current status |
|---|---|---|
| MySQL stability | no new kernel OOM; MySQL healthy; memory below limit | pending full-day observation |
| Worker headroom | worker RSS remains controlled across task cycles; no restart loop | pending full-day observation |
| Scheduler pressure | provider/circuit warnings do not cause sustained CPU/RSS pressure | pending full-day observation |
| Queue health | no sustained core backlog; no repeated A-key/strategy-tracking duplicates after successful same-day task | pending full-day observation |
| API/page health | `/readyz` 200; core pages 200; protected APIs fast 401 when unauthenticated | pending full-day observation |
| Strategy semantics | low-buy read path and production scoring tests pass | passed locally before this template |
| Authorization | user explicitly authorizes D5 maintenance action | already broadly authorized, but gate still pending |

## D5 Command Not Executed

The command below is recorded for later use only after the gate passes:

```bash
cd /home/ubuntu/gupiao-upload
cp .env ".env.scheduler-embed-backup.$(date +%Y%m%d%H%M%S)"
python3 - <<'PY'
from pathlib import Path
path = Path('.env')
pairs = {
    'RUNTIME_WORKER_EMBED_SCHEDULER': 'true',
    'RUNTIME_SCHEDULER_BACKGROUND_JOBS_ENABLED': 'false',
}
lines = path.read_text(encoding='utf-8').splitlines()
seen = set()
out = []
for line in lines:
    key = line.split('=', 1)[0] if '=' in line else ''
    if key in pairs:
        out.append(f'{key}={pairs[key]}')
        seen.add(key)
    else:
        out.append(line)
for key, value in pairs.items():
    if key not in seen:
        out.append(f'{key}={value}')
path.write_text('\n'.join(out) + '\n', encoding='utf-8')
PY
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate runtime-worker
sudo docker rm -f tquant-runtime-scheduler-mysql
```

Expected post-D5 heartbeat if later executed:

| Key | Expected worker id |
|---|---|
| `platform_component.heartbeat.runtime-scheduler` | `runtime-worker-embedded-scheduler` |

## Operations Not Executed In This Template

- No `.env` change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.
