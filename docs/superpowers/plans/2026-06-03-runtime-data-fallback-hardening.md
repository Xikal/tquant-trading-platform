# Runtime Data Fallback Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate silent latest-data gaps by making daily bar refresh, low-buy materialization, worker health, queue backlog, frontend warnings, and runbook recovery observable and self-healing.

**Architecture:** Keep Web request handlers read-first and lightweight. Runtime scheduler enqueues close-refresh checks, runtime worker consumes refresh/materialization tasks, daily-bar refresh validates the target trade date, and UI/API surfaces expose explicit fallback state instead of silently returning empty recommendations.

**Tech Stack:** FastAPI, SQLAlchemy, DB-backed `runtime_tasks`, Vite/React/Ant Design, Vitest, pytest.

---

## Current Root Cause And Boundary

Observed on 2026-06-03:

- Local Web process was running with `DATABASE_URL=sqlite:///./data/t_quant.db` and `RUNTIME_BACKGROUND_JOBS_ENABLED=false`.
- No long-running `python -m app.workers.runtime_worker` process was visible.
- `runtime_tasks` contained `low_buy_materialization_refresh` rows stuck in `queued` with no `started_at`.
- `daily_bar_snapshots` latest complete date was `2026-05-29`; expected after close was `2026-06-03`; `2026-06-03` daily bars were `0`.
- The priority board correctly degraded to empty/wait state instead of inventing recommendations.

Hard boundary:

- Do not lower strategy thresholds to hide missing data.
- Do not compute heavy scans in Web request paths.
- Do not fabricate daily bars, fake scores, or fake recommendations.
- Fallback means repair, queue, warn, and block safely; it does not mean “recommend anyway.”

## Files

Create:

- `backend/app/services/runtime_worker_health.py` - worker heartbeat, backlog inspection, and readiness summary.
- `backend/tests/test_runtime_worker_health.py` - unit coverage for stale heartbeat and queued critical tasks.
- `frontend/src/features/data-console/RuntimeFallbackPanel.tsx` - compact UI panel for worker/backlog/latest-data state.
- `frontend/src/features/data-console/RuntimeFallbackPanel.test.tsx` - frontend display tests.
- `docs/operations/runtime-data-fallback-runbook.md` - operational recovery commands and SQL checks.

Modify:

- `backend/app/workers/runtime_worker.py` - write heartbeat and pass task payload fields to refresh handlers.
- `backend/app/services/daily_bar_refresh.py` - accept `expected_trade_date`, validate post-refresh count, and report insufficient coverage.
- `backend/app/services/latest_data_close_refresh.py` - include worker/backlog hints in close-refresh result and chain next-step enqueue after successful daily refresh.
- `backend/app/services/low_buy_materialization.py` - ensure materialization success republishes latest state and includes missing-strategy result.
- `backend/app/api/routes/data_quality.py` - add `/data-quality/runtime-fallback` read endpoint.
- `backend/app/services/data_quality/schemas.py` - add response schemas for runtime fallback status.
- `frontend/src/api/dataQuality.ts` - add runtime fallback API type and fetcher.
- `frontend/src/features/data-console/DataConsolePage.tsx` - load and render runtime fallback status.
- `frontend/src/features/data-console/DataHealthOverview.tsx` - add strong warning when worker/backlog blocks latest data.
- `frontend/src/types/settings.ts` or generated types only if current local type organization requires it.
- `docs/contracts/openapi.json` and `frontend/src/generated/api-types.ts` - regenerate after backend schema changes.
- `PRODUCTION_RUNBOOK.md` - link to the new runtime data fallback runbook.

Do not expand these already-large files except with narrowly scoped changes:

- `backend/app/runtime/background_jobs.py` is 510 lines; avoid adding new logic here unless absolutely necessary.
- `backend/app/workers/runtime_worker.py` is 517 lines; keep additions small and move reusable health logic to `runtime_worker_health.py`.

## Task 1: Runtime Worker Health Service

**Files:**

- Create: `backend/app/services/runtime_worker_health.py`
- Create: `backend/tests/test_runtime_worker_health.py`
- Modify: `backend/app/workers/runtime_worker.py`

- [ ] **Step 1: Write tests for stale/missing heartbeat and queued critical tasks**

Create `backend/tests/test_runtime_worker_health.py` with tests that seed `system_settings` and `runtime_tasks` and assert:

```python
from __future__ import annotations

from datetime import datetime, timedelta

from app.models.entities import RuntimeTask, SystemSetting
from app.services.runtime_worker_health import build_runtime_fallback_status, record_runtime_worker_heartbeat


def test_runtime_fallback_status_blocks_when_worker_heartbeat_missing(db_session):
    status = build_runtime_fallback_status(db_session, now=datetime(2026, 6, 3, 16, 0, 0))

    assert status["worker_status"] == "missing"
    assert status["blocking"] is True
    assert "runtime worker" in status["message"].lower()


def test_runtime_fallback_status_blocks_when_critical_task_stuck(db_session):
    db_session.add(
        SystemSetting(
            key="runtime_worker.heartbeat",
            value='{"worker_id":"runtime-test","updated_at":"2026-06-03T15:59:30","status":"running"}',
        )
    )
    db_session.add(
        RuntimeTask(
            task_type="low_buy_materialization_refresh",
            status="queued",
            priority=35,
            payload_json='{"expected_trade_date":"2026-06-03"}',
            idempotency_key="low_buy_materialization_refresh:2026-06-03",
            active_idempotency_key="low_buy_materialization_refresh:2026-06-03",
            created_at=datetime(2026, 6, 3, 15, 45, 0),
        )
    )
    db_session.commit()

    status = build_runtime_fallback_status(db_session, now=datetime(2026, 6, 3, 16, 0, 0))

    assert status["worker_status"] == "running"
    assert status["blocking"] is True
    assert status["critical_queued_count"] == 1
    assert status["oldest_critical_queued_age_seconds"] >= 900


def test_record_runtime_worker_heartbeat_updates_setting(db_session):
    record_runtime_worker_heartbeat(
        db_session,
        worker_id="runtime-test",
        now=datetime(2026, 6, 3, 16, 0, 0),
    )

    status = build_runtime_fallback_status(db_session, now=datetime(2026, 6, 3, 16, 0, 10))

    assert status["worker_status"] == "running"
    assert status["worker_id"] == "runtime-test"
    assert status["blocking"] is False
```

- [ ] **Step 2: Run tests and confirm they fail**

Run:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/pytest backend/tests/test_runtime_worker_health.py -q
```

Expected: fails because `runtime_worker_health.py` does not exist.

- [ ] **Step 3: Implement `runtime_worker_health.py`**

Implement:

- `CRITICAL_TASK_TYPES = {"daily_bar_refresh", "low_buy_materialization_refresh", "strategy_tracking_snapshot_refresh", "a_key_level_materialization_refresh", "monitor_snapshot_refresh"}`
- `record_runtime_worker_heartbeat(db, worker_id, now=None) -> None`
- `build_runtime_fallback_status(db, now=None) -> dict`

Required output fields:

```python
{
    "worker_status": "running" | "stale" | "missing",
    "worker_id": str,
    "heartbeat_updated_at": str,
    "heartbeat_age_seconds": int | None,
    "critical_queued_count": int,
    "oldest_critical_queued_at": str,
    "oldest_critical_queued_age_seconds": int | None,
    "blocking": bool,
    "message": str,
    "recovery_actions": list[str],
}
```

Thresholds:

- heartbeat stale after 120 seconds.
- critical queued task is blocking after 600 seconds.

Use `SystemSetting.key == "runtime_worker.heartbeat"` and JSON value. Keep DB queries bounded.

- [ ] **Step 4: Wire heartbeat into `RuntimeWorker.run_forever` and `run_once`**

Modify `backend/app/workers/runtime_worker.py`:

- call `record_runtime_worker_heartbeat(db, worker_id=self.worker_id)` at the start of `run_once`.
- call it again after a task succeeds or fails.
- do not make heartbeat failure stop the worker; log and continue.

- [ ] **Step 5: Run tests**

Run:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/pytest backend/tests/test_runtime_worker_health.py backend/tests/test_phase4_runtime_worker_tasks.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/runtime_worker_health.py backend/app/workers/runtime_worker.py backend/tests/test_runtime_worker_health.py
git commit -m "feat: add runtime worker fallback health"
```

## Task 2: Deterministic Daily Bar Refresh Fallback

**Files:**

- Modify: `backend/app/services/daily_bar_refresh.py`
- Modify: `backend/app/workers/runtime_worker.py`
- Modify: `backend/tests/test_provider_v6_rectification.py`
- Modify: `backend/tests/test_phase4_runtime_worker_tasks.py`

- [ ] **Step 1: Add failing test for expected trade date propagation**

In `backend/tests/test_phase4_runtime_worker_tasks.py`, add a test that monkeypatches `DailyBarRefreshService.refresh_latest` and calls:

```python
result = runtime_worker._execute_task(
    "daily_bar_refresh",
    {"limit": 6000, "expected_trade_date": "2026-06-03"},
    db,
)
assert result["expected_trade_date"] == "2026-06-03"
```

Expected captured call includes `expected_trade_date="2026-06-03"`.

- [ ] **Step 2: Add failing test for insufficient post-refresh coverage**

In `backend/tests/test_provider_v6_rectification.py`, add a test that simulates a refresh where fewer than 4500 rows exist after completion. Expected response:

```python
assert result["ok"] is False
assert result["status"] == "insufficient_daily_bars"
assert result["trade_date"] == "2026-06-03"
assert result["daily_bar_count"] < result["min_daily_bar_count"]
```

- [ ] **Step 3: Run tests and confirm they fail**

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/pytest \
  backend/tests/test_phase4_runtime_worker_tasks.py::test_runtime_worker_passes_expected_trade_date_to_daily_bar_refresh \
  backend/tests/test_provider_v6_rectification.py::test_daily_bar_refresh_reports_insufficient_daily_bars \
  -q
```

- [ ] **Step 4: Implement expected-date support**

Change `DailyBarRefreshService.refresh_latest` signature:

```python
def refresh_latest(
    self,
    *,
    limit: int = 6000,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    expected_trade_date: str | None = None,
) -> dict[str, Any]:
```

Use:

```python
trade_date = expected_trade_date or expected_low_buy_trade_date(self.db)
```

At the end, query `DailyHistoryRepository(self.db).stock_count_by_trade_date(trade_date)` and include:

- `daily_bar_count`
- `min_daily_bar_count`
- `status`

If count is below `MIN_STOCK_DAILY_BARS`, return `ok=False` and `status="insufficient_daily_bars"`.

- [ ] **Step 5: Pass payload in worker**

Modify the `daily_bar_refresh` branch in `backend/app/workers/runtime_worker.py` to call:

```python
return DailyBarRefreshService(db).refresh_latest(
    limit=int(payload.get("limit") or 6000),
    expected_trade_date=str(payload.get("expected_trade_date") or "") or None,
)
```

- [ ] **Step 6: Run tests**

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/pytest \
  backend/tests/test_provider_v6_rectification.py \
  backend/tests/test_phase4_runtime_worker_tasks.py \
  backend/tests/test_latest_data_close_refresh.py \
  -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/daily_bar_refresh.py backend/app/workers/runtime_worker.py backend/tests/test_provider_v6_rectification.py backend/tests/test_phase4_runtime_worker_tasks.py
git commit -m "fix: validate daily bar refresh target date"
```

## Task 3: Close-Refresh Self-Healing Chain

**Files:**

- Modify: `backend/app/services/latest_data_close_refresh.py`
- Modify: `backend/app/workers/runtime_worker.py`
- Modify: `backend/app/services/low_buy_materialization.py`
- Modify: `backend/tests/test_latest_data_close_refresh.py`
- Modify: `backend/tests/test_phase4_runtime_worker_tasks.py`

- [ ] **Step 1: Add tests for post-daily-refresh chaining**

In `backend/tests/test_phase4_runtime_worker_tasks.py`, add a test:

- monkeypatch `DailyBarRefreshService.refresh_latest` to return `{"ok": True, "trade_date": "2026-06-03", "daily_bar_count": 4950}`.
- monkeypatch `enqueue_latest_data_close_refresh` to capture it was called after daily refresh.
- call `_execute_task("daily_bar_refresh", {"expected_trade_date": "2026-06-03"}, db)`.
- assert result includes `next_refresh_check.action`.

- [ ] **Step 2: Add tests for materialization publish state**

In `backend/tests/test_latest_data_close_refresh.py`, add a case where:

- daily bars are complete.
- strategy snapshots are complete.
- `publish_latest_trade_date_if_ready` returns success.
- result action is `publish_latest_trade_date`.

Existing tests already cover much of this; extend assertions to include worker/backlog fields after Task 4 if needed.

- [ ] **Step 3: Implement daily-refresh next check**

In `runtime_worker.py`, after a successful `daily_bar_refresh`, call:

```python
if result.get("ok"):
    from app.services.latest_data_close_refresh import enqueue_latest_data_close_refresh
    result["next_refresh_check"] = enqueue_latest_data_close_refresh(db)
```

If `daily_bar_refresh` returns insufficient coverage, do not enqueue materialization.

- [ ] **Step 4: Ensure low-buy materialization publishes latest state**

In `backend/app/services/low_buy_materialization.py`, after Python fallback or Go scan succeeds, ensure `publish_latest_trade_date_if_ready` is called with the strategies used. The returned payload must include:

```python
"publish_status": status,
"published_trade_date": status.get("published_trade_date", "")
```

If strategies remain missing, return `ok=False` with `missing_strategies` rather than silently succeeding.

- [ ] **Step 5: Run tests**

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/pytest \
  backend/tests/test_latest_data_close_refresh.py \
  backend/tests/test_phase4_runtime_worker_tasks.py \
  backend/tests/test_key_levels_materialization_readiness.py \
  -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/latest_data_close_refresh.py backend/app/workers/runtime_worker.py backend/app/services/low_buy_materialization.py backend/tests/test_latest_data_close_refresh.py backend/tests/test_phase4_runtime_worker_tasks.py
git commit -m "fix: chain latest data refresh tasks"
```

## Task 4: Runtime Fallback API And Data Console Warning

**Files:**

- Modify: `backend/app/services/data_quality/schemas.py`
- Modify: `backend/app/api/routes/data_quality.py`
- Modify: `frontend/src/api/dataQuality.ts`
- Create: `frontend/src/features/data-console/RuntimeFallbackPanel.tsx`
- Create: `frontend/src/features/data-console/RuntimeFallbackPanel.test.tsx`
- Modify: `frontend/src/features/data-console/DataConsolePage.tsx`
- Modify: `frontend/src/features/data-console/DataHealthOverview.tsx`
- Modify after generation: `docs/contracts/openapi.json`
- Modify after generation: `frontend/src/generated/api-types.ts`

- [ ] **Step 1: Add backend API test**

Add a test in an existing data-quality route test file or create `backend/tests/test_data_quality_runtime_fallback.py`.

Expected endpoint:

```http
GET /api/data-quality/runtime-fallback
```

Expected JSON includes:

```json
{
  "worker_status": "missing",
  "blocking": true,
  "critical_queued_count": 0,
  "message": "runtime worker heartbeat missing"
}
```

- [ ] **Step 2: Add schema and route**

In `backend/app/services/data_quality/schemas.py`, define `RuntimeFallbackStatusResponse` with the fields from Task 1.

In `backend/app/api/routes/data_quality.py`, add:

```python
@router.get("/runtime-fallback", response_model=RuntimeFallbackStatusResponse)
def get_runtime_fallback_status(db: Session = Depends(get_db)) -> RuntimeFallbackStatusResponse:
    return RuntimeFallbackStatusResponse(**build_runtime_fallback_status(db))
```

- [ ] **Step 3: Add frontend fetcher**

In `frontend/src/api/dataQuality.ts`, add:

```ts
export interface RuntimeFallbackStatus {
  worker_status: "running" | "stale" | "missing" | string;
  worker_id: string;
  heartbeat_updated_at: string;
  heartbeat_age_seconds: number | null;
  critical_queued_count: number;
  oldest_critical_queued_at: string;
  oldest_critical_queued_age_seconds: number | null;
  blocking: boolean;
  message: string;
  recovery_actions: string[];
}

export function fetchRuntimeFallbackStatus() {
  return apiGet<RuntimeFallbackStatus>("/data-quality/runtime-fallback");
}
```

Use the repo's actual `apiGet` helper name if `dataQuality.ts` uses a different import.

- [ ] **Step 4: Create `RuntimeFallbackPanel.tsx`**

Render:

- green state when `worker_status === "running"` and `blocking === false`.
- warning state when heartbeat stale or queued critical task exists.
- compact recovery actions list.
- no technical English such as `queued`, `stale`, `worker` in visible copy if existing data console wording avoids raw internals; use Chinese labels like `后台未响应` and `关键刷新排队过久`.

- [ ] **Step 5: Add frontend tests**

In `RuntimeFallbackPanel.test.tsx`, render:

- missing heartbeat state: assert text includes `后台未运行`.
- queued critical task state: assert text includes `关键刷新排队过久`.
- normal state: assert text includes `后台正常`.

- [ ] **Step 6: Wire page**

In `DataConsolePage.tsx`, fetch runtime fallback status with the same query style used for SLA/coverage.

Pass status to:

- `DataHealthOverview` for top-level warning.
- `RuntimeFallbackPanel` for detail display.

- [ ] **Step 7: Regenerate contracts**

```bash
cd /Users/j/Documents/gupiao/frontend
npm run api:check
```

Expected: OpenAPI export, generated types, and typecheck pass.

- [ ] **Step 8: Run tests**

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/pytest backend/tests/test_data_quality_runtime_fallback.py backend/tests/test_runtime_worker_health.py -q
cd /Users/j/Documents/gupiao/frontend
npm run test -- RuntimeFallbackPanel DataConsolePage
npm run lint
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/data_quality/schemas.py backend/app/api/routes/data_quality.py backend/tests/test_data_quality_runtime_fallback.py frontend/src/api/dataQuality.ts frontend/src/features/data-console/RuntimeFallbackPanel.tsx frontend/src/features/data-console/RuntimeFallbackPanel.test.tsx frontend/src/features/data-console/DataConsolePage.tsx frontend/src/features/data-console/DataHealthOverview.tsx docs/contracts/openapi.json frontend/src/generated/api-types.ts
git commit -m "feat: surface runtime data fallback status"
```

## Task 5: Local/Production Runbook And Startup Guard

**Files:**

- Create: `docs/operations/runtime-data-fallback-runbook.md`
- Modify: `PRODUCTION_RUNBOOK.md`
- Modify if present/appropriate: `scripts/dev_start_all.sh` or create `scripts/dev_start_all.sh`
- Modify: `backend/tests/test_cloud_deploy_scripts.py`

- [ ] **Step 1: Write runbook**

Create `docs/operations/runtime-data-fallback-runbook.md` with:

- one-command local startup for Web and runtime worker.
- docker compose startup for `app runtime-worker runtime-scheduler`.
- SQL checks:

```sql
select trade_date, count(*) from daily_bar_snapshots group by trade_date order by trade_date desc limit 5;
select task_type, status, count(*) from runtime_tasks group by task_type, status;
select value from system_settings where `key` = 'low_buy.latest_data';
select value from system_settings where `key` = 'runtime_worker.heartbeat';
```

- repair commands:

```bash
cd /Users/j/Documents/gupiao/backend
PYTHONPATH=. DATABASE_URL=sqlite:///./data/t_quant.db .venv/bin/python -m app.workers.runtime_worker
```

and docker:

```bash
docker compose -f docker-compose.mysql.yml up -d runtime-worker runtime-scheduler
docker compose -f docker-compose.mysql.yml logs -f runtime-worker
```

- decision table:

| Symptom | Likely Cause | Action |
|---|---|---|
| critical tasks queued > 10 min | worker stopped | start runtime-worker |
| daily bars below 4500 | data source or refresh incomplete | rerun daily refresh, inspect provider logs |
| materialization missing | strategy snapshot not built | enqueue latest close refresh |
| page empty with warning | safe fallback active | fix data pipeline, do not lower strategy threshold |

- [ ] **Step 2: Link from `PRODUCTION_RUNBOOK.md`**

Add a short section:

```markdown
### Runtime Data Fallback

Latest-data gaps, stuck `runtime_tasks`, or empty priority board recovery steps are documented in [runtime-data-fallback-runbook.md](docs/operations/runtime-data-fallback-runbook.md).
```

Use the correct relative path from `PRODUCTION_RUNBOOK.md`.

- [ ] **Step 3: Add local startup script if missing**

If no script exists, create `scripts/dev_start_all.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export DATABASE_URL="${DATABASE_URL:-sqlite:///./data/t_quant.db}"
export RUNTIME_BACKGROUND_JOBS_ENABLED="${RUNTIME_BACKGROUND_JOBS_ENABLED:-false}"
trap 'kill 0' EXIT
(cd backend && PYTHONPATH=. .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
(cd backend && PYTHONPATH=. .venv/bin/python -m app.workers.runtime_worker) &
wait
```

Mark executable:

```bash
chmod +x scripts/dev_start_all.sh
```

- [ ] **Step 4: Add deployment/startup guard tests**

Extend `backend/tests/test_cloud_deploy_scripts.py` to assert:

- `docker-compose.mysql.yml` includes `runtime-worker`.
- `docker-compose.mysql.yml` includes `runtime-scheduler`.
- deploy script starts both services.

Existing tests already cover part of this; add runtime fallback wording/runbook assertions if not covered.

- [ ] **Step 5: Run tests**

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/pytest backend/tests/test_cloud_deploy_scripts.py -q
```

- [ ] **Step 6: Commit**

```bash
git add docs/operations/runtime-data-fallback-runbook.md PRODUCTION_RUNBOOK.md scripts/dev_start_all.sh backend/tests/test_cloud_deploy_scripts.py
git commit -m "docs: add runtime data fallback runbook"
```

## End-To-End Acceptance

Run after all tasks:

```bash
cd /Users/j/Documents/gupiao
git status --short
PYTHONPATH=backend:. backend/.venv/bin/pytest \
  backend/tests/test_runtime_worker_health.py \
  backend/tests/test_latest_data_close_refresh.py \
  backend/tests/test_phase4_runtime_worker_tasks.py \
  backend/tests/test_provider_v6_rectification.py \
  backend/tests/test_data_quality_runtime_fallback.py \
  backend/tests/test_cloud_deploy_scripts.py \
  -q

cd /Users/j/Documents/gupiao/frontend
npm run test -- RuntimeFallbackPanel DataConsolePage workspaceFamilyQuality
npm run typecheck
npm run lint
npm run api:check
```

Manual local verification:

```bash
cd /Users/j/Documents/gupiao
scripts/dev_start_all.sh
```

In another shell:

```bash
curl -s http://127.0.0.1:8000/readyz
curl -s http://127.0.0.1:8000/api/data-quality/runtime-fallback
```

Expected:

- runtime fallback status reports `worker_status=running` within 120 seconds.
- no critical queued tasks older than 600 seconds after worker has time to consume them.
- daily refresh task failure is explicit when daily bars remain below 4500.
- priority board remains conservative when latest data is missing.

Database acceptance:

```sql
select trade_date, count(*) as c
from daily_bar_snapshots
group by trade_date
order by trade_date desc
limit 5;

select task_type, status, count(*) as c
from runtime_tasks
where task_type in (
  'daily_bar_refresh',
  'low_buy_materialization_refresh',
  'strategy_tracking_snapshot_refresh',
  'a_key_level_materialization_refresh',
  'monitor_snapshot_refresh'
)
group by task_type, status;

select value
from system_settings
where `key` in ('low_buy.latest_data', 'runtime_worker.heartbeat');
```

Success criteria:

- Latest post-close trade date has at least `4500` stock daily bars or is explicitly blocked with a visible reason.
- `low_buy.latest_data` is published only when required strategy snapshots exist.
- Stuck critical queue is visible in API and frontend.
- Worker absence is visible within 120 seconds.
- No fake candidate appears when data is incomplete.

## Rollback

If deployment shows unexpected failures:

1. Stop `runtime-worker` and `runtime-scheduler`; Web remains read-only and safe.
2. Revert commits in reverse order.
3. Keep `runtime-data-fallback-runbook.md` if it helps operations, unless it references removed APIs.
4. Confirm priority board still returns conservative empty/wait state instead of recommendations from stale data.

## Prompt For Implementation Agent

```text
你是 Codex，在 /Users/j/Documents/gupiao 执行开发。请严格按照 docs/superpowers/plans/2026-06-03-runtime-data-fallback-hardening.md 落地“运行时数据兜底机制完善”。

硬边界：
1. 不降低选股/低吸策略门槛，不制造假推荐票。
2. Web 请求路径不得新增重计算；刷新、补数、物化只能走 runtime-worker/runtime-scheduler。
3. 兜底含义是补数、重试、告警、阻断和降级展示，不是用旧数据冒充新数据。
4. 遵守 docs/engineering-conventions.md；大文件只做窄改，新逻辑拆到新模块。
5. 每个 Task 按文档顺序执行，测试通过后再进入下一 Task，能提交就分 Task 提交。

必须优先确认：
- git status --short
- 当前 DATABASE_URL 和是否已有 runtime-worker 进程
- runtime_tasks 是否有 critical queued 积压

验收必须执行：
- PYTHONPATH=backend:. backend/.venv/bin/pytest backend/tests/test_runtime_worker_health.py backend/tests/test_latest_data_close_refresh.py backend/tests/test_phase4_runtime_worker_tasks.py backend/tests/test_provider_v6_rectification.py backend/tests/test_data_quality_runtime_fallback.py backend/tests/test_cloud_deploy_scripts.py -q
- cd frontend && npm run test -- RuntimeFallbackPanel DataConsolePage workspaceFamilyQuality
- cd frontend && npm run typecheck && npm run lint && npm run api:check

最终交付：
- 列出修改文件
- 列出测试结果
- 给出本地/生产如何启动 worker 和检查数据是否断档
- 若仍有阻塞，明确是 worker、数据源、队列还是策略物化哪一层
```
