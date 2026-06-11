# Current Boundary Map

Status: Phase 1 architecture baseline, 2026-06-04.

This document records the current module boundaries before the next phases move
more work out of the Web process. It is not a microservice split plan.

## Runtime Boundary

| Layer | Current locations | Allowed responsibility |
| --- | --- | --- |
| Web API | `backend/app/api/routes/` | Lightweight reads, task submission, task status, cached/read-model payloads |
| Runtime queue | `backend/app/services/tasks/queue.py` | Durable enqueue, claim, heartbeat, progress, retry, events, stale recovery |
| Runtime task registry | `backend/app/services/tasks/registry.py`, `docs/architecture/runtime-task-registry.md` | Declarative task owner/worker/retry/artifact/idempotency governance; source for worker claim-scope guard tests |
| Runtime worker | `backend/app/workers/runtime_worker.py` | Latest data refresh, quote cache, AKey materialization, low-buy materialization, monitor snapshots, research refresh tasks |
| Analytics worker | `backend/scripts/analytics_worker.py`, `backend/app/services/tasks/analytics_handlers.py` | 24-month backfill, Parquet export, DuckDB reports, data quality checks, analytics artifacts |
| Backtest worker | `backend/app/services/backtest_worker.py` | Persistent backtest job execution outside request threads |
| Analytics layer | `backend/app/services/analytics/` | Parquet manifests, DuckDB read queries, report generation; never production trading facts |
| Backtest domain | `backend/app/services/backtest/` and backtest job services | Signal evaluation replay, broker simulation, persistence and reporting |
| Frontend contract | `docs/contracts/openapi.json`, `frontend-next/src/generated/api-types.ts` | Generated API contract types used by frontend wrappers |

## Contract Chain

1. FastAPI app exposes the OpenAPI schema.
2. `backend/scripts/export_openapi_schema.py` writes `docs/contracts/openapi.json`
   and `docs/contracts/openapi.hash`.
3. `frontend-next/package.json` runs:
   - `api:export`
   - `api:generate`
   - `api:check`
4. `openapi-typescript` generates `frontend-next/src/generated/api-types.ts`.
5. `npm run typecheck` fails if wrappers using generated `paths` or
   `components` drift from the backend contract.

New or modified frontend API wrappers must prefer generated types from
`frontend-next/src/generated/api-types.ts`. Existing handwritten wrappers are a
migration backlog, not a pattern for new endpoints.

## Existing Workerized Capabilities

`RuntimeTaskQueue` already supports:

- enqueue and idempotency keys
- list/get/events
- claim with worker id
- heartbeat and stale running recovery
- progress events
- succeeded/failed/retry status

`RUNTIME_TASK_REGISTRY` declares every RuntimeTask task type with its owner
role, expected worker, retry policy, artifact kind, idempotency expectation and
runtime budget. New RuntimeTask types must be added to the registry and covered
by the worker-scope guard tests before routes enqueue them.

`RuntimeWorker` currently claims these architecture-critical task types:

- `daily_bar_refresh`
- `latest_data_watchdog`
- `a_key_level_materialization_refresh`
- `low_buy_materialization_refresh`
- `market_pulse_refresh`
- `market_quote_cache_refresh`
- `monitor_snapshot_refresh`
- `factor_mining_evaluate`

`analytics_task_registry()` currently registers:

- `data_backfill_24m`
- `analytics_export_daily_bars`
- `analytics_quality_check`
- `strategy_24m_duckdb_report`
- `backtest_all_strategies_24m`
- data quality and production track-record refresh tasks

Backtest execution is already represented by persistent `BacktestRun` rows and
consumed by `BacktestWorker`.

## Web Process Rules

The Web process may:

- return cached/read-model payloads
- enqueue durable tasks
- expose task status, progress and artifacts
- perform bounded validation and authorization

The Web process must not perform:

- 24-month data backfills
- Parquet export
- DuckDB report generation
- full-market strategy scans
- 24-month all-strategy backtests
- ML model training
- bulk strategy validation
- request-time recomputation that can block user traffic

Any exception must be explicitly bounded, documented and migrated in a later
phase if it grows beyond lightweight request work.

## Phase Status

Phase 1 is limited to boundary inventory, contract-chain verification and
guard tests. Phase 2 through Phase 7 remain implementation work and must not be
considered complete from this baseline alone.

No production ranking, strategy scoring, `strategy_policy`, or
`production_score` behavior is changed by this Phase 1 baseline.
