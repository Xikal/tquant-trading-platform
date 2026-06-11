# Runtime Task Summary Read Model Optimization - 2026-06-12

## Scope

This D6 change narrows the `/api/runtime-tasks/summary` task-type aggregate so old terminal task history no longer dominates the admin observability payload or forces a broad historical `GROUP BY task_type`.

No production strategy logic, `production_score`, priority-board sorting, low-buy policy, scheduler cutover, online configuration, or database schema was changed.

## Evidence

The D6 MySQL root-cause review recorded:

- `runtime_tasks` had about `44k` rows.
- A runtime task diagnostic query examined about `45k` rows and took `1.835s`.
- `/api/runtime-tasks/summary` took `0.146s` to `0.258s` across sampled authenticated requests.

The broad historical task-type aggregate was noisy because old succeeded/failed task types could rank above current queued/running/recent work.

## Change

File changed:

- `backend/app/services/tasks/queue.py`

`RuntimeTaskQueue.summary()` now keeps full `status_counts` semantics, but limits `task_type_counts` to:

- tasks created inside the requested recent window; or
- active non-terminal tasks that are still queued/running.

This keeps current backlog and recent work visible while avoiding a task-type leaderboard driven by old terminal task history.

Test changed:

- `backend/tests/test_runtime_task_queue.py`

Added `test_runtime_task_summary_type_counts_use_recent_or_active_window` to prove old succeeded task history does not appear in `task_type_counts`, while all-time `status_counts` still includes the historical succeeded rows.

## Behavior Kept

- `queued`, `running`, `failed`, `succeeded_recent`, `retrying`, `paused_queued`, and `claimable_queued` remain available.
- Low-priority pause visibility remains available through `paused_task_types` and `paused_task_type_counts`.
- `skipped` remains a terminal status and still appears in `status_counts`.
- Runtime queue claim/retry/skip semantics are unchanged.

## Verification

Executed locally:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_runtime_task_queue.py::test_runtime_task_summary_type_counts_use_recent_or_active_window
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_runtime_task_queue.py
```

Results:

- Targeted test: `1 passed`
- Runtime task queue tests: `13 passed`

## Risk

`task_type_counts` is now a recent-or-active view instead of an all-history leaderboard. This is intentional for operational observability. Historical terminal totals remain visible through `status_counts`, and detailed task history remains available through the task list endpoint.

## Operations Not Executed

- No online `.env` change.
- No Docker restart/recreate/remove.
- No scheduler stop or embed cutover.
- No DB write.
- No schema/index change.
- No nginx/systemd change.
- No cleanup.
- No deployment or cutover.

## Next

Run the plan-required regression set before commit:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_platform_budget_verifier.py backend/tests/test_runtime_task_queue.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_independent_runtime_components.py
```

D5 scheduler embed remains closed until the full trading-day gate proves worker RSS, MySQL, swap, queue dedupe, and provider pressure are stable.
