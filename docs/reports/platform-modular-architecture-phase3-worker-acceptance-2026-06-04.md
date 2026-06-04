# Platform Modular Architecture Phase 3 Acceptance

Date: 2026-06-04.

Scope: Phase 3 only. This pass verifies that long-running platform work can be
submitted, claimed, monitored, retried and completed through the existing worker
runtime. It does not change strategy rules, ranking, `strategy_policy`,
`production_score`, or deployment.

## Runtime Components

Verified components:

- `backend/app/services/tasks/queue.py`
  - enqueue
  - claim
  - heartbeat
  - progress
  - events
  - retry and failure state
  - artifact event persistence
  - stale running task recovery
- `backend/app/services/tasks/registry.py`
  - task handler registry
  - `analytics_task_registry()`
- `backend/app/services/tasks/worker.py`
  - standalone `RuntimeTaskWorker`
  - one-shot and forever modes
- `backend/scripts/analytics_worker.py`
  - independent analytics worker entrypoint
- `backend/app/services/tasks/analytics_handlers.py`
  - long-running analytics/backtest task handlers

## Required Long Tasks

The analytics registry exposes the Phase 3 task types:

- `data_backfill_24m`
- `analytics_export_daily_bars`
- `analytics_quality_check`
- `strategy_24m_duckdb_report`
- `backtest_all_strategies_24m`

These tasks are claimed by `RuntimeTaskWorker` through the registry rather than
being executed directly by Web routes.

## Minimum Worker Execution

The Phase 3 guard tests execute minimum reproducible worker tasks:

- a probe task that calls heartbeat, progress and artifact APIs
- a failing probe task that confirms retry and `run_after`
- an `analytics_quality_check` task on an empty test DB, which returns explicit
  failure quality and enqueues `data_backfill_24m`

The `analytics_quality_check` test demonstrates the intended behavior for
missing data: the task does not fabricate daily bars and does not return fake
success. It records `daily_bars_empty` and creates a queued backfill task.

## Existing Worker Coverage

Existing tests also cover:

- `RuntimeTaskQueue` event/status lifecycle
- stale running task recovery
- retry backoff
- analytics worker progress and artifact persistence
- data quality SLA refresh task execution
- data repair dry-run task execution

## Validation Commands

Command:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_platform_modular_architecture_phase3.py \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_analytics_worker.py \
  -q
```

Expected result for this phase:

```text
all tests pass
```

## Phase 3 Verdict

Phase 3 is accepted for the architecture baseline:

- Long task registry exists.
- Required Phase 3 task types are registered.
- Worker claim, heartbeat, progress, retry, artifact and failure behavior are
  covered by tests.
- Missing data creates explicit blocked/fail state and queued recovery work.
- Web routes should submit these tasks and read task status rather than running
  heavy work in request threads.

No deployment was performed.
