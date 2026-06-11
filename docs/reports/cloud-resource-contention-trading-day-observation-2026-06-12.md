# Cloud Resource Contention Trading Day Observation - 2026-06-12

## Scope

This report is the D5 gate observation template and current decision record for the cloud resource contention remediation plan. It is read-only unless a later section explicitly records an authorized operation.

## Current Decision

D5 embedded scheduler is not executed yet.

Reason: the worker recycle guard is now live and the current worker RSS is low, but this is still a short post-rollout window. The plan requires a longer stable window, preferably a full trading day, before moving standalone scheduler work into runtime-worker.

Latest read-only gate snapshot: `docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md`.

At `2026-06-12 01:14:00 CST`, the platform is online and no P0 blocker was observed, but D5 remains blocked because the observation is not a full trading day and there are still scheduler provider warnings, queued old `data_quality_sla_refresh` tasks, and duplicate A-key / strategy-tracking successes inside the last two-hour query window.

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

Preferred repeatable collector:

```bash
cd /Users/j/Documents/gupiao
python3 scripts/collect_cloud_resource_gate_observation.py \
  --ssh-host 43.143.243.97 \
  --ssh-user ubuntu \
  --ssh-key /Users/j/Downloads/gupiao.pem \
  --journal-since "2026-06-12 00:00:00" \
  --docker-logs-since 2h \
  --json-output docs/reports/cloud-resource-gate-observation-2026-06-12-latest.json \
  --markdown-output docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md
```

Expected:

- Read-only collection only.
- `d5_gate.ready=false` means do not embed scheduler.
- `d5_gate.ready=true` requires `--full-trading-day-complete` and still needs a maintenance-window decision before any online write.

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
| MySQL stability | no new kernel OOM; MySQL healthy; memory below limit | short-window pass; `tquant-mysql` `656.1MiB / 1.5GiB`; `Threads_connected=10`; `Threads_running=2`; `Slow_queries=16` |
| Worker headroom | worker RSS remains controlled across task cycles; no restart loop | short-window pass; `tquant-runtime-worker-mysql` `218MiB / 768MiB` (`28.38%`) |
| Scheduler pressure | provider/circuit warnings do not cause sustained CPU/RSS pressure | not passed; scheduler provider warning lines still present |
| Queue health | no sustained core backlog; no repeated A-key/strategy-tracking duplicates after successful same-day task | not passed; old queued `data_quality_sla_refresh=2`; last two-hour window still includes `strategy_tracking_snapshot_refresh=56`, `a_key_level_materialization_refresh=26` from pre-dedupe period |
| API/page health | `/readyz` 200; core pages 200; protected APIs fast 401 when unauthenticated | short-window pass; `/readyz` 200; all checked `/next/*` pages 200; protected APIs 401 |
| Strategy semantics | low-buy read path and production scoring tests pass | passed locally before this template |
| Authorization | user explicitly authorizes D5 maintenance action | already broadly authorized, but gate still pending |

## Latest Read-Only Snapshot

| Area | Evidence | Status |
|---|---|---|
| Host | load average `0.27, 0.33, 0.29`; memory available `1571MiB`; swap used `794MiB / 1987MiB` (`39.96%`) | warning |
| Disk | root `34G / 59G` (`60%`); inode `12%` | pass |
| app/API | `tquant-app-mysql` `45.26MiB / 768MiB`; `/readyz` `200` in `0.004601s` | pass |
| runtime-worker | `218MiB / 768MiB` (`28.38%`) | pass |
| runtime-scheduler | `353.7MiB / 640MiB` (`55.27%`) | warning: provider logs still present |
| MySQL | `656.1MiB / 1.5GiB`; `Threads_connected=10`; `Threads_running=2`; `Slow_queries=16` | warning: slow query count exists |
| Redis | `5.078MiB / 128MiB` | pass |
| frontend-next | `/next/monitor`, `/next/monitor/market`, `/next/strategy-tracking`, `/next/analysis`, `/next/backtest`, `/next/data`, `/next/settings` all `200` | pass |
| protected APIs | `/api/monitor/snapshot`, `/api/screeners/low-buy/priority-board`, `/api/runtime-tasks/summary` all `401` quickly | pass |
| queue | queued `data_quality_sla_refresh=2`; duplicate-success window still includes pre-dedupe A-key and strategy-tracking counts | warning |

Automated evaluation:

```text
status=warning
d5_gate.ready=false
d5_gate.blockers=full_trading_day_observation_incomplete, scheduler_provider_warnings_present, runtime_nonterminal_task_count=2, duplicate_success_window:strategy_tracking_snapshot_refresh=56, duplicate_success_window:a_key_level_materialization_refresh=26
```

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
