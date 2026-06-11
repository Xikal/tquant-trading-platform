# Cloud Resource Contention Trading Day Observation - 2026-06-12

## Scope

This report is the D5 gate observation template and current decision record for the cloud resource contention remediation plan. It is read-only unless a later section explicitly records an authorized operation.

## Current Decision

D5 embedded scheduler is not executed yet.

Reason: the worker recycle guard is now live and the current worker RSS is low, but this is still a short post-rollout window. The plan requires a longer stable window, preferably a full trading day, before moving standalone scheduler work into runtime-worker.

Latest read-only gate snapshot: `docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md`.

At `2026-06-12 02:54:06 CST`, the platform is online and no P0 blocker was observed, but D5 remains blocked because the observation is not a full trading day and scheduler provider warnings are still present. The previous duplicate A-key / strategy-tracking two-hour window warning is absent, and the two old `data_quality_sla_refresh` non-terminal rows were cancelled through the authorized D6 queue cleanup recorded below.

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

Checkpoint collector naming:

```bash
cd /Users/j/Documents/gupiao
CHECKPOINT=09:15
STAMP=$(date +%Y%m%d-%H%M)
python3 scripts/collect_cloud_resource_gate_observation.py \
  --ssh-host 43.143.243.97 \
  --ssh-user ubuntu \
  --ssh-key /Users/j/Downloads/gupiao.pem \
  --journal-since "2026-06-12 00:00:00" \
  --docker-logs-since 15m \
  --checkpoint-label "$CHECKPOINT" \
  --json-output "docs/reports/cloud-resource-gate-observations/2026-06-12-${CHECKPOINT/:/}-${STAMP}.json" \
  --markdown-output "docs/reports/cloud-resource-gate-observations/2026-06-12-${CHECKPOINT/:/}-${STAMP}.md"
```

After all required checkpoints are collected, summarize them:

```bash
python3 scripts/summarize_cloud_resource_gate_observations.py \
  docs/reports/cloud-resource-gate-observations/2026-06-12-*.json \
  --json-output docs/reports/cloud-resource-trading-day-gate-summary-2026-06-12.json \
  --markdown-output docs/reports/cloud-resource-trading-day-gate-summary-2026-06-12.md \
  --fail-on-d5-blocked
```

Expected:

- The summary reads local JSON snapshots only.
- Missing any required checkpoint keeps `d5_ready=false`.
- Sustained provider pressure, worker pressure, queue backlog, duplicate core tasks, or HTTP failures keep D5 blocked.
- Low-frequency provider recovery probes below threshold remain warnings, not D5 blockers.

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
| MySQL stability | no new kernel OOM; MySQL healthy; memory below limit | short-window pass with slow-query warning; `tquant-mysql` `853MiB / 1.5GiB`; `Threads_connected=9`; `Threads_running=2`; `Slow_queries=48` |
| Worker headroom | worker RSS remains controlled across task cycles; no restart loop | short-window pass; `tquant-runtime-worker-mysql` `294.8MiB / 768MiB` (`38.39%`) |
| Scheduler pressure | provider/circuit warnings do not cause sustained CPU/RSS pressure | not passed; scheduler provider warning lines still present after D6 provider guard |
| Queue health | no sustained core backlog; no repeated A-key/strategy-tracking duplicates after successful same-day task | short-window pass; non-terminal queue is empty after authorized stale `data_quality_sla_refresh` cancellation |
| API/page health | `/readyz` 200; core pages 200; protected APIs fast 401 when unauthenticated | short-window pass; `/readyz` 200; all checked `/next/*` pages 200; protected APIs 401 |
| Strategy semantics | low-buy read path and production scoring tests pass | passed locally before this template |
| Authorization | user explicitly authorizes D5 maintenance action | already broadly authorized, but gate still pending |

## Latest Read-Only Snapshot

| Area | Evidence | Status |
|---|---|---|
| Host | load average `0.45, 0.28, 0.30`; memory available `1418MiB`; swap used `661MiB / 1987MiB` (`33.27%`) | warning |
| Disk | root `34G / 59G` (`62%`); inode `13%` | pass |
| app/API | `tquant-app-mysql` `59.37MiB / 768MiB`; `/readyz` `200` in `0.003887s` | pass |
| runtime-worker | `294.8MiB / 768MiB` (`38.39%`) | pass |
| runtime-scheduler | `254.4MiB / 640MiB` (`39.75%`) | warning: provider logs still present |
| MySQL | `853MiB / 1.5GiB`; `Threads_connected=9`; `Threads_running=2`; `Slow_queries=48` | warning: slow query count exists |
| Redis | `4.957MiB / 128MiB` | pass |
| frontend-next | `/next/monitor`, `/next/monitor/market`, `/next/strategy-tracking`, `/next/analysis`, `/next/backtest`, `/next/data`, `/next/settings` all `200` | pass |
| protected APIs | `/api/monitor/snapshot`, `/api/screeners/low-buy/priority-board`, `/api/runtime-tasks/summary` all `401` quickly | pass |
| queue | no queued/running rows; recent summary only shows `low_buy_materialization_refresh` successes | pass |

Automated evaluation:

```text
status=warning
d5_gate.ready=false
d5_gate.blockers=full_trading_day_observation_incomplete, scheduler_provider_warnings_present
warnings=scheduler_provider_warnings_present, mysql_slow_queries=48
```

## 2026-06-12 02:54 CST Decision Update

The latest gate refresh improves the queue signal compared with the `02:48 CST` snapshot: the old non-terminal `data_quality_sla_refresh` rows are no longer blockers. Core HTTP/page checks remain healthy and no blocking condition was observed. D5 is still not allowed because the full trading-day requirement is incomplete and board-breadth provider warnings are still visible in the standalone scheduler logs.

Recommended next action:

1. Do not stop `runtime-scheduler` and do not enable embedded scheduler yet.
2. Continue the full trading-day collector checkpoints with the provider guard already deployed to `runtime-scheduler`.
3. Re-run the collector at the required trading-day checkpoints and only consider D5 after `d5_gate.ready=true` with `--full-trading-day-complete`.

## D6 Authorized Non-Core Queue Cleanup - 2026-06-12 02:53 CST

The D6 root-cause review had identified two old queued `data_quality_sla_refresh` rows as non-core data repair residue. With the user's broad execution authorization, these rows were cancelled through the existing `RuntimeTaskQueue.cancel()` API instead of raw SQL, so each row also received a `runtime_task_events` cancellation event.

Pre-check target rows:

| Task id | Task type | Status | Priority | Created at | Active key |
|---:|---|---|---:|---|---|
| `41913` | `data_quality_sla_refresh` | `queued` | `22` | `2026-06-10 07:01:31` | `data_quality_sla_refresh:daily_bars:production_universe:2026-06-10` |
| `44330` | `data_quality_sla_refresh` | `queued` | `22` | `2026-06-11 07:01:19` | `data_quality_sla_refresh:daily_bars:production_universe:2026-06-11` |

Execution:

```text
RuntimeTaskQueue.cancel(41913)
RuntimeTaskQueue.cancel(44330)
reason=cancelled after cloud resource remediation review: stale non-core data_quality_sla_refresh queued task
```

Post-check evidence:

| Task id | Status | Finished at | Latest event |
|---:|---|---|---|
| `41913` | `cancelled` | `2026-06-11 18:53:58 UTC` | `cancelled` |
| `44330` | `cancelled` | `2026-06-11 18:53:59 UTC` | `cancelled` |

Impact:

- Removed `runtime_nonterminal_task_count=2` from the D5 blocker list.
- Did not delete rows or business data.
- Did not touch MySQL schema, indexes, low-buy strategy policy, `production_score`, or priority-board ordering.
- Did not change `.env`, containers, nginx/systemd, Docker images, or service topology.

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

## D5 Operations Not Executed In Latest Gate

- No `.env` change.
- No D5 Docker restart/recreate/remove.
- No scheduler stop.
- No D5 DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.

The D6 provider-degraded guard was deployed separately as a scheduler-only mitigation and is recorded in `docs/reports/provider-degraded-cooldown-market-regime-optimization-2026-06-12.md` and `docs/reports/cloud-resource-contention-remediation-2026-06-11.md`.
The D6 non-core queue metadata write is recorded above and is separate from D5 scheduler embed.

## 2026-06-12 03:17 CST Decision Update

A follow-up D6 scheduler-only mitigation was applied because the standalone scheduler was still producing `fetch_board_breadth_frame` provider warnings every 90-135 seconds. The hard-coded 60 second market-regime provider degraded cooldown was replaced with a declared 300 second setting and deployed only to `runtime-scheduler`.

Scope:

- Rebuilt and recreated `tquant-runtime-scheduler-mysql` only.
- Did not change `.env`.
- Did not restart app/API, core `runtime-worker`, MySQL, Redis, Go services, frontend/nginx, systemd, or nginx.
- Did not write database rows or change schema/indexes.
- Did not execute D5 scheduler embed and did not stop the standalone scheduler.

Immediate evidence:

| Area | Evidence |
|---|---|
| Config | scheduler reports `market_regime_provider_degraded_cooldown_seconds=300.0` |
| Warning cadence | warning count stayed at `8` from `03:11` to `03:15 CST`, then a single recovery probe appeared after roughly 5 minutes |
| `/readyz` | `200`, `0.003822s` immediately after scheduler-only rollout |
| Latest collector | `status=warning`, `d5_gate.ready=false`, blockers `full_trading_day_observation_incomplete`, `scheduler_provider_warnings_present` |
| Resource | host memory available `1382MiB`; swap used `33.06%`; worker `273.5MiB / 768MiB`; MySQL `857.3MiB / 1.5GiB` |

Decision:

1. Continue keeping `runtime-scheduler` standalone.
2. Do not execute D5 embedded scheduler yet.
3. Continue full trading-day observation. The provider warning blocker can only be cleared after a fresh observation window proves the warnings are no longer sustained under trading-day load.

## 2026-06-12 03:25 CST Tooling Update

The D5 observation tooling now supports checkpoint labels and trading-day summary generation.

Changed local tooling:

- `scripts/collect_cloud_resource_gate_observation.py` accepts `--checkpoint-label`.
- `scripts/summarize_cloud_resource_gate_observations.py` summarizes multiple checkpoint JSON snapshots.
- Required checkpoints are `09:15`, `09:35`, `10:30`, `11:30`, `13:05`, `14:55`, `15:10`, `15:30`.
- The summary keeps D5 blocked if any required checkpoint is missing, or if any snapshot has sustained D5 blockers.

Validation:

```text
backend/tests/test_cloud_resource_gate_observation.py: 10 passed
ad-hoc online read-only checkpoint: status=warning, blockers=full_trading_day_observation_incomplete
single-checkpoint summary: d5_ready=false, blockers=full_trading_day_observation_incomplete
```

Operations:

- No `.env` change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.

Decision remains unchanged: D5 embedded scheduler is still closed until the complete trading-day checkpoint set passes.

## 2026-06-12 03:36 CST Read-Only Gate Refresh

Another ad-hoc read-only collector run was executed for D6 root-cause evidence:

```bash
python3 scripts/collect_cloud_resource_gate_observation.py \
  --ssh-host 43.143.243.97 \
  --ssh-user ubuntu \
  --ssh-key /Users/j/Downloads/gupiao.pem \
  --journal-since "2026-06-12 00:00:00" \
  --docker-logs-since 2h \
  --checkpoint-label ad-hoc-d6-root-cause \
  --json-output /tmp/gupiao-cloud-resource-gate-d6-root-cause.json \
  --markdown-output /tmp/gupiao-cloud-resource-gate-d6-root-cause.md
```

Result:

```text
status=warning
d5_gate.ready=false
d5_gate.blockers=full_trading_day_observation_incomplete, scheduler_provider_warning_lines=28
warnings=scheduler_provider_warning_lines=28, mysql_slow_queries=51
```

Snapshot:

| Area | Evidence | Status |
|---|---|---|
| Host | load average `0.37, 0.26, 0.28`; memory available `1364MiB`; swap used `655MiB / 1987MiB` (`32.96%`) | warning |
| runtime-worker | `273.5MiB / 768MiB` (`35.62%`) | pass |
| runtime-scheduler | `250.1MiB / 640MiB` (`39.08%`); provider warning lines `28` | blocker for D5 |
| MySQL | `859.2MiB / 1.5GiB`; `Threads_connected=9`; `Threads_running=2`; `Slow_queries=51` | warning |
| HTTP/pages | `/readyz` 200; all checked `/next/*` pages 200; protected APIs 401 quickly | pass |
| Runtime tasks | recent summary only `low_buy_materialization_refresh` succeeded, count `6` | pass |

Platform budget verifier was also run read-only against the live containers:

```bash
python3 scripts/verify_platform_budget.py \
  --ssh-host 43.143.243.97 \
  --ssh-user ubuntu \
  --ssh-key /Users/j/Downloads/gupiao.pem \
  --json-output /tmp/gupiao-platform-budget-d6-root-cause.json \
  --markdown-output /tmp/gupiao-platform-budget-d6-root-cause.md
```

Result:

```text
status=ok
blocking=none
warnings=none
pool_budget_total=20
Threads_connected=9
Threads_running=2
```

Important env evidence:

| Role | Evidence |
|---|---|
| web | `RUNTIME_BACKGROUND_JOBS_ENABLED=false`, `TQUANT_ANALYTICS_ENABLED=false`, `PLATFORM_AUTOPILOT_ENABLED=false` |
| runtime-worker | `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true`, `RUNTIME_WORKER_EMBED_SCHEDULER=false`, `RUNTIME_WORKER_RECYCLE_RSS_MB=700`, startup prewarm disabled |
| runtime-scheduler | `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true`, `RUNTIME_BACKGROUND_JOBS_ENABLED=true`, `MARKET_REVIEW_ENABLED=false` |

Interpretation:

1. The first-layer stop profile and budget guard are currently correct.
2. D5 is blocked by full trading-day incompleteness and sustained scheduler provider pressure, not by budget-verifier failures.
3. Do not stop `runtime-scheduler` and do not enable embedded scheduler.

Operations not executed in this refresh:

- No `.env` change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.

## 2026-06-12 04:15 CST D6 Scheduler-Only Backoff Rollout And Gate Refresh

With user authorization, the D6 provider backoff change was deployed to the standalone `runtime-scheduler` only. This was not a D5 scheduler-embed cutover.

Online write scope:

| Item | Evidence |
|---|---|
| Backup | `/home/ubuntu/gupiao-upload/.runtime/manual-hotfix-backups/provider-backoff-20260612035652` |
| Uploaded files | `backend/app/core/config.py`, `backend/app/services/market/regime.py`, `docker-compose.mysql.yml`, `scripts/verify_platform_budget.py` |
| Build/recreate | `runtime-scheduler` only |
| Scheduler after | started `2026-06-11T19:57:06.919385169Z`, healthy, restart `0` |
| App unchanged | started `2026-06-11T15:40:10.021531795Z` before and after |
| Worker unchanged | started `2026-06-11T16:33:27.439851625Z` before and after |
| MySQL unchanged | started `2026-06-11T15:42:42.993726302Z` before and after |
| Runtime setting | scheduler reports `300.0 1800.0 2.0` for degraded cooldown, max cooldown, and backoff factor |

Short post-rollout observation:

| Time | Board-breadth warning count since scheduler restart | Interpretation |
|---|---:|---|
| `03:57 CST` | `5` | initial startup probe |
| `04:03 CST` | `10` | second probe after roughly 5 minutes |
| `04:08 CST` | `10` | no third probe on old 5 minute cadence |
| `04:13 CST` | `15` | third probe after roughly 10 minutes, matching backoff |
| `04:14 CST` | `15` | stable after third probe |

Formal collector after rollout:

```text
generated_at=2026-06-11T20:15:46Z
host_time=2026-06-12 04:15:42 CST
status=warning
d5_gate.ready=false
d5_gate.blockers=full_trading_day_observation_incomplete
blocking=none
warnings=scheduler_provider_warning_lines_observed=18, mysql_slow_queries=55
```

Resource snapshot:

| Area | Evidence | Status |
|---|---|---|
| Host | load `0.50, 0.31, 0.28`; memory available `1349MiB`; swap used `649MiB / 1987MiB` (`32.66%`) | warning |
| runtime-scheduler | `255.1MiB / 640MiB` (`39.86%`) | pass |
| runtime-worker | `296.1MiB / 768MiB` (`38.55%`) | pass |
| MySQL | `863.2MiB / 1.5GiB`; `Threads_connected=9`; `Threads_running=2`; `Slow_queries=55` | warning |
| HTTP/pages | `/readyz` 200; all checked `/next/*` pages 200; protected APIs 401 quickly | pass |
| Runtime tasks | recent summary only `low_buy_materialization_refresh` succeeded, count `6` | pass |

Platform budget verifier after rollout:

```text
status=ok
warnings=none
blocking=none
```

Decision:

1. The D6 provider pressure blocker is improved in the fresh short window.
2. D5 embedded scheduler is still not allowed because the full trading-day checkpoint set is incomplete.
3. Continue standalone `runtime-scheduler` until a full trading-day summary reports `d5_gate.ready=true`.

Operations not executed in this rollout:

- No online `.env` change.
- No app/API restart.
- No core `runtime-worker` restart.
- No MySQL/Redis/Go/frontend/nginx change.
- No DB write.
- No schema/index change.
- No Docker cleanup.
- No D5 scheduler embed.
- No standalone scheduler stop.

## 2026-06-12 04:22 CST Pre-D5 Waiting Snapshot

Current local time was `2026-06-12 04:22 CST`, which is outside the required D5 checkpoint schedule. No D5 checkpoint can be counted yet; the first required checkpoint remains `09:15 CST`.

Read-only collector:

```bash
python3 scripts/collect_cloud_resource_gate_observation.py \
  --ssh-host 43.143.243.97 \
  --ssh-user ubuntu \
  --ssh-key /Users/j/Downloads/gupiao.pem \
  --journal-since "2026-06-12 00:00:00" \
  --docker-logs-since 30m \
  --checkpoint-label pre-d5-wait-0422 \
  --json-output docs/reports/cloud-resource-gate-observation-2026-06-12-latest.json \
  --markdown-output docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md
```

Result:

```text
generated_at=2026-06-11T20:23:01Z
host_time=2026-06-12 04:22:57 CST
status=warning
d5_gate.ready=false
d5_gate.blockers=full_trading_day_observation_incomplete
blocking=none
warnings=scheduler_provider_warning_lines_observed=18, mysql_slow_queries=55
```

Snapshot:

| Area | Evidence | Status |
|---|---|---|
| Host | load `0.58, 0.58, 0.40`; memory available `1337MiB`; swap used `32.66%`; root `63%`; inode `13%` | warning: swap still present |
| runtime-scheduler | `254.4MiB / 640MiB`; board warnings last 30m `15`; healthy | pass |
| runtime-worker | `296.1MiB / 768MiB`; healthy | pass |
| MySQL | `863.9MiB / 1.5GiB`; `Threads_connected=9`; `Threads_running=2`; `Slow_queries=55` | warning |
| HTTP/pages | `/readyz` 200; `/next/monitor`, `/next/monitor/market`, `/next/strategy-tracking`, `/next/analysis`, `/next/backtest`, `/next/data`, `/next/settings` all 200 | pass |
| Runtime tasks | recent summary only `low_buy_materialization_refresh` succeeded, count `4` | pass |
| Platform budget verifier | `status=ok`, `warnings=none`, `blocking=none` | pass |

Decision:

1. D6 provider backoff remains below D5 provider-pressure blocking threshold in this pre-market window.
2. D5 remains closed only because the full trading-day checkpoint set has not started.
3. Do not enable embedded scheduler yet.
4. Next required action is the `09:15 CST` checkpoint collection.

Operations not executed in this snapshot:

- No `.env` change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.

## 2026-06-12 04:48 CST Premarket Read-Only Checkpoint

This premarket checkpoint was collected before the first required `09:15 CST`
trading-day checkpoint, so it does not count toward full trading-day completion.
It is kept as continuity evidence while waiting for the formal D5 observation
window to start.

Read-only collector:

```bash
python3 scripts/collect_cloud_resource_gate_observation.py \
  --ssh-host 43.143.243.97 \
  --ssh-user ubuntu \
  --ssh-key /Users/j/Downloads/gupiao.pem \
  --journal-since "2026-06-12 00:00:00" \
  --docker-logs-since 30m \
  --checkpoint-label premarket-0448 \
  --json-output docs/reports/cloud-resource-gate-observations/2026-06-12-0448.json \
  --markdown-output docs/reports/cloud-resource-gate-observations/2026-06-12-0448.md
```

Result:

```text
generated_at=2026-06-11T20:48:36Z
host_time=2026-06-12 04:48:32 CST
status=warning
d5_gate.ready=false
d5_gate.blockers=full_trading_day_observation_incomplete
blocking=none
warnings=scheduler_provider_warning_lines_observed=5, mysql_slow_queries=55
```

Snapshot:

| Area | Evidence | Status |
|---|---|---|
| Host | load `0.36, 0.33, 0.28`; memory available `1346MiB`; swap used `32.46%`; root `63%`; inode `13%` | warning: swap still present |
| runtime-scheduler | `255MiB / 640MiB`; warning lines observed `5` | pass, down from earlier sustained warning window |
| runtime-worker | `296.1MiB / 768MiB`; CPU sample `22.50%` | pass |
| MySQL | `869MiB / 1.5GiB`; `Threads_connected=9`; `Threads_running=2`; `Slow_queries=55` | warning |
| HTTP/pages | `/readyz` 200; `/next/monitor`, `/next/monitor/market`, `/next/strategy-tracking`, `/next/analysis`, `/next/backtest`, `/next/data`, `/next/settings` all 200 | pass |
| Runtime tasks | recent summary only `low_buy_materialization_refresh` succeeded, count `2` | pass |

The current checkpoint summary was regenerated from local JSON snapshots:

```text
d5_ready=false
d5_blockers=full_trading_day_observation_incomplete
```

Decision:

1. D5 embedded scheduler remains closed.
2. The provider warning pressure is improved in the current premarket window.
3. The next required action remains the formal `09:15 CST` checkpoint collection.

Operations not executed in this checkpoint:

- No `.env` change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.

## 2026-06-12 04:51 CST Supervisor Waiting State

Local supervisor check:

```text
local_time=2026-06-12 04:51:46 CST
git_status=clean
strategy_policy_diff_lines=0
d5_ready=false
d5_blockers=full_trading_day_observation_incomplete
```

The formal D5 observation window has not started. The next valid checkpoint is
`09:15 CST`; running another collector before that time would only create another
premarket continuity snapshot and would not satisfy the full trading-day gate.

Next command to run at `09:15 CST`:

```bash
python3 scripts/collect_cloud_resource_gate_observation.py \
  --ssh-host 43.143.243.97 \
  --ssh-user ubuntu \
  --ssh-key /Users/j/Downloads/gupiao.pem \
  --journal-since "2026-06-12 00:00:00" \
  --docker-logs-since 30m \
  --checkpoint-label 09:15 \
  --json-output docs/reports/cloud-resource-gate-observations/2026-06-12-0915.json \
  --markdown-output docs/reports/cloud-resource-gate-observations/2026-06-12-0915.md
```

Decision:

1. D5 embedded scheduler remains closed.
2. Do not stop standalone `runtime-scheduler`.
3. Keep waiting for the formal checkpoint sequence.

Operations not executed in this supervisor check:

- No `.env` change.
- No Docker restart/recreate/remove.
- No scheduler stop.
- No DB write.
- No nginx/systemd change.
- No Docker cleanup.
- No deployment or cutover.
