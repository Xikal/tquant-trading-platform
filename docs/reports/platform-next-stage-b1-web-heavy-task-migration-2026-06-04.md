# Platform Next Stage B1 Web Heavy Task Migration

Date: 2026-06-04

Scope: B1 only. This batch moves expandable Web request paths into
`RuntimeTaskQueue` while preserving bounded synchronous reads. It does not
modify `strategy_policy`, production ranking, low-buy scoring, priority board,
front-row weighted logic, `production_score`, or paper/shadow gates.

## Worktree Gate

Initial B1 status after B0 commit:

```text
?? docs/superpowers/plans/2026-06-04-platform-modular-architecture-next-stage-development-plan.md
```

The untracked plan file is user-provided authority input and is not staged by
B1.

## Runtime Task Surface

Added shared route helpers:

- `backend/app/api/routes/heavy_task_helpers.py`
  - `enqueue_runtime_task(...)`
  - `queued_task_response(...)`

Added runtime worker dispatcher:

- `backend/app/workers/heavy_research_tasks.py`
  - validates payloads through existing schema models
  - executes migrated heavy research, ML, factor, analysis, paper and ETF tasks
  - returns explicit blocked status for empty `analysis_batch`

Updated runtime worker behavior:

- B1 task types are included in `RUNTIME_WORKER_TASK_TYPES`.
- `ml_signal_incremental_train` and `factor_mining_evaluate` remain on their
  existing runtime-worker handlers.
- Runtime worker now writes progress events at claim and pre-success boundaries
  in addition to the existing started/succeeded/failed task events.

## Endpoint Migration Matrix

| Endpoint | B1 behavior |
| --- | --- |
| `GET /api/screeners/low-buy` | bounded/materialized reads stay synchronous; `scan_mode=full` with `scan_limit > 120` queues `low_buy_materialization_refresh` |
| `GET /api/screeners/low-buy/execution-backtest` | queues `low_buy_execution_backtest` |
| `POST /api/research/backtests` | queues `legacy_research_backtest` |
| `POST /api/backtests/etf-t0-minute` | small payloads stay synchronous; `bars > 480` queues `etf_t0_minute_backtest` |
| `POST /api/backtests/etf-t0-research` | small payloads stay synchronous; `bars > 480` or parameter grids above 16 queue `etf_t0_research_report` |
| `GET /api/backtests/{run_id}/portfolio-optimization` | queues `backtest_portfolio_optimization` |
| `GET /api/backtests/{run_id}/position-policy-research?train_shadow=true` | queues `backtest_position_policy_research`; `train_shadow=false` remains the bounded read/research preview path |
| `POST /api/ml-signals/build-samples` | queues `ml_signal_build_samples` |
| `POST /api/ml-signals/train` | queues `ml_signal_train` |
| `POST /api/ml-signals/incremental-train` | queues `ml_signal_incremental_train` |
| `POST /api/factor-mining/factors/{factor_key}/evaluate` | queues `factor_mining_evaluate` |
| `POST /api/factor-mining/iterate` | queues `factor_mining_iterate` |
| `POST /api/analysis/analyze/batch` | existing 10-symbol synchronous bound remains; `queue=true` queues `analysis_batch`; over-limit requests remain rejected |
| `GET /api/paper/performance/smart-t-backtest` | bounded default stays synchronous; larger sample windows or explicit date ranges queue `paper_smart_t_backtest` |
| `POST /api/paper/backtest-comparison` | queues `paper_backtest_comparison` |

## Contract And Frontend

OpenAPI and generated types were regenerated from the backend contract:

- `docs/contracts/openapi.json`
- `docs/contracts/openapi.hash`
- `frontend/src/generated/api-types.ts`

Frontend wrappers now type queued responses from generated OpenAPI component
types through `frontend/src/api/runtimeTasks.ts`. Updated callers show queued
task ids for ML training, portfolio optimization, and ETF T0 heavy responses
instead of treating queued task payloads as finished reports.

## Tests

Backend targeted acceptance:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_web_heavy_task_migration.py \
  backend/tests/test_runtime_task_contracts.py \
  backend/tests/test_phase4_runtime_worker_tasks.py \
  -q
```

Result before final B1 commit: pass.

Contract and frontend acceptance:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/export_openapi_schema.py
cd frontend && npm run api:check && npm run lint && npm test -- --run
```

Result before final B1 commit: pass.

## Production Sorting Verdict

B1 does not change production sorting. The migrated routes only change where
heavy work runs. Existing low-buy output fields, priority board ordering,
strategy tracking fields, `production_score`, `priority_score`,
`elite_watch_score`, `buy_signal_state`, and `strategy_policy` are not modified.

Research, shadow, paper, watch-only, and `near_entry` states remain non-production
surfaces and do not bypass existing gates.

