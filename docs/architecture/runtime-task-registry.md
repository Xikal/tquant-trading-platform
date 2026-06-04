# RuntimeTask Registry

Status: P0 governance baseline, 2026-06-04. This document describes the
declarative task registry in `backend/app/services/tasks/registry.py`.

The registry is not a new queue implementation. `RuntimeTaskQueue` remains the
durable status, retry, event, artifact and idempotency store. The registry is
the governance layer used to declare which worker owns each task type.

## Registry Fields

| Field | Meaning |
| --- | --- |
| `task_type` | Stable queue task type string. |
| `owner_role` | Owning domain: `quant`, `data`, or `devops`. |
| `worker` | Runtime component expected to claim the task: `runtime`, `analytics`, `backtest`, `scheduler`, or `web`. |
| `retry_policy` | Queue retry policy name; current default is `queue_backoff`. |
| `max_attempts` | Default expected retry attempts for governance and review. |
| `artifact_kind` | Expected artifact class: `none`, `metrics`, `snapshot`, `report`, or `parquet`. |
| `idempotency_required` | Whether production enqueues should provide a stable idempotency key. |
| `expected_runtime_p95_ms` | Budget used by worker health and future alerting. |

## Current Ownership

| Worker | Source | Scope |
| --- | --- | --- |
| `runtime` | `RUNTIME_TASK_REGISTRY` entries with `worker="runtime"` | hot data refresh, materialization, monitor snapshots, research tasks, ML/factor tasks and platform automation |
| `analytics` | `RUNTIME_TASK_REGISTRY` entries with `worker="analytics"` | 24M data backfill, Parquet export, quality checks, DuckDB reports and track-record refresh |
| `backtest` | persistent `BacktestRun` queue | full backtest execution outside request threads |
| `scheduler` | runtime scheduler heartbeat | background scheduling only; it does not directly execute registered queue payloads |

## Guard Rails

- `backend/tests/test_runtime_task_registry_governance.py` verifies runtime and
  analytics worker claim scopes match the registry.
- `backend/tests/test_web_route_no_heavy_compute.py` verifies route modules
  submit registered task types and do not directly call worker handlers.
- Web routes may enqueue registered tasks through
  `backend/app/api/routes/heavy_task_helpers.py`.
- Web routes must not call `execute_heavy_research_task`, DuckDB report
  builders, Parquet export, `RuntimeWorker`, or `BacktestWorker` directly.

## Production Boundary

The registry does not change production ranking. It does not modify
`strategy_policy.py`, `participates_in_priority_board`, `production_score`,
priority board ordering, Strategy Engine Shadow behavior, or Execution Model
Preview behavior.
