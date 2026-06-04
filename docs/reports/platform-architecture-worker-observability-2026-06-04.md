# Platform Architecture Worker Observability

Status: A6 completed  
Date: 2026-06-04  
Scope: RuntimeTaskQueue and data console worker observability

## Change

Added read-only RuntimeTaskQueue observability endpoints:

- `GET /api/runtime-tasks/summary`
- `GET /api/runtime-tasks/workers`
- `GET /api/runtime-tasks/failures`
- `GET /api/runtime-tasks/artifacts`

The data console now shows a "后台任务观测" section with:

- queued/running/failed/retrying/recent succeeded counts
- longest queued wait
- worker heartbeat/current task ids
- recent failed tasks and reasons
- task artifact paths

## Boundaries

- No new Web background loop was added.
- No route runs heavy tasks in the request thread.
- Observability endpoints only read `runtime_tasks`, `runtime_task_events`, and
  heartbeat settings.
- Artifact paths are manifest/report/output links from existing task payloads or
  results; they are not treated as production trading facts.

## Verification

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_runtime_task_contracts.py \
  backend/tests/test_runtime_worker_health.py \
  -q
```

Result:

```text
13 passed, 1 warning
```

```bash
cd frontend && npm run api:check
```

Result: OpenAPI export, generated types, and TypeScript check passed.

```bash
cd frontend && npm test -- --run src/features/data-console/DataConsolePage.test.tsx
```

Result:

```text
1 passed, 11 tests passed
```

## Production Impact

No deployment was performed. Runtime worker observability is available through
read-only API and UI surfaces once this code is deployed in a later approved
deployment window.
