# Web Heavy Task Inventory

Status: Phase 1 inventory, 2026-06-04.

Scan anchors:

- `RuntimeTaskQueue`
- `enqueue`
- `BackgroundTasks`
- `subprocess`
- `ProcessPool`
- `ThreadPool`
- `backfill`
- `parquet`
- `duckdb`
- `24m`
- `backtest`
- `materializ`
- `scan`
- `train`
- `optimiz`
- `refresh`

## Already Worker Or Queue Backed

| Entry | Current behavior | Phase 1 verdict |
| --- | --- | --- |
| `POST /api/runtime-tasks` | Enqueues `RuntimeTaskCreate`; list/get/events/stream expose status | Compliant task submission/status surface |
| `POST /api/data-quality/backfill` | Enqueues `data_quality_backfill` through `RuntimeTaskQueue` | Compliant |
| `POST /api/data-quality/repair` | Enqueues `data_repair_run` | Compliant |
| `POST /api/factor-mining/tasks/evaluate` | Enqueues `factor_mining_evaluate` | Compliant queued alternative |
| `GET /internal/scan-worker/v1/run` | Enqueues Python low-buy materialization reference from internal worker path | Compliant orchestration endpoint |
| `GET /api/market/pulse` | Returns latest pulse or placeholder, enqueues `market_pulse_refresh` when stale/requested | Compliant cached read plus enqueue |
| `POST /api/admin-metrics/latest-data/refresh` | Calls latest-data close refresh enqueue chain | Compliant admin repair trigger |
| `POST /api/backtests` | Creates queued `BacktestRun`; `BacktestWorker` executes | Compliant |
| `POST /api/backtests/optimize` | Creates queued optimization task | Compliant, should remain worker consumed |
| `POST /api/backtests/validate` | Creates queued validation task | Compliant, should remain worker consumed |
| `backend/scripts/analytics_worker.py` | Runs `RuntimeTaskWorker` with analytics registry | Compliant independent worker |

Note: `refresh=sync` on `GET /api/market/pulse` currently still returns the
cached snapshot path and enqueues refresh; it is not a request-thread full
rebuild.

## Must Stay Out Of Web In Later Phases

| Entry | Current risk | Required next phase |
| --- | --- | --- |
| `GET /api/screeners/low-buy` | Synchronous screener call with scan limits up to 480 | Move heavier/full scan paths to materialized read model or runtime task in Phase 3 |
| `GET /api/screeners/low-buy/execution-backtest` | Request-time execution backtest | Workerize or require existing backtest job surface in Phase 5 |
| `POST /api/research/backtests` | Legacy hidden route runs research backtest directly | Retire or redirect to `/api/backtests` queued jobs |
| `POST /api/backtests/etf-t0-minute` | Computes minute backtest from request payload | Keep only bounded research payloads or enqueue when payload grows |
| `POST /api/backtests/etf-t0-research` | Computes research report from request payload | Workerize report generation if used for large samples |
| `GET /api/backtests/{run_id}/portfolio-optimization` | Runs portfolio optimization in request thread | Convert to queued research task before expanding usage |
| `GET /api/backtests/{run_id}/position-policy-research?train_shadow=true` | Optional request-time shadow training | Force training path through worker before enabling broader access |
| `POST /api/ml-signals/build-samples` | Builds ML samples directly | Queue for non-trivial sample windows |
| `POST /api/ml-signals/train` | Trains ML signal model directly | Move to runtime/research worker |
| `POST /api/ml-signals/incremental-train` | Incremental training in request thread | Move to runtime/research worker |
| `POST /api/factor-mining/factors/{factor_key}/evaluate` | Direct evaluation exists beside queued alternative | Prefer `/tasks/evaluate`; migrate direct endpoint to queued mode |
| `POST /api/factor-mining/iterate` | Potential repeated factor evaluation loop | Queue for multi-round runs |
| `POST /api/analysis/analyze/batch` | Bounded to 10 symbols but still synchronous | Keep bounded; queue if expanded |
| `GET /api/paper/performance/smart-t-backtest` | Paper smart-T backtest runs on request path | Queue if lookback/sample size expands |
| `POST /api/paper/backtest-comparison` | Compares paper and backtest data in request path | Keep read-only and bounded; queue large comparisons |

## Contract And DTO Evidence

- OpenAPI export source: `backend/scripts/export_openapi_schema.py`
- Tracked schema: `docs/contracts/openapi.json`
- Generated frontend type source: `frontend/src/generated/api-types.ts`
- Frontend chain: `cd frontend && npm run api:check`
- Existing generated-type wrapper example: `frontend/src/api/backtests.ts`

Remaining handwritten wrapper hotspots include `frontend/src/api/dataQuality.ts`,
`frontend/src/api/runtimeTasks.ts`, `frontend/src/api/mlSignals.ts`,
`frontend/src/api/quantParameters.ts` and adjacent API files. They are migration
backlog. New API wrappers should not add duplicate DTO definitions when the
OpenAPI path or component type already exists.

## Phase 1 Acceptance Result

Phase 1 acceptance is satisfied when:

1. This inventory is present and indexed.
2. `docs/architecture/current-boundary-map.md` records the current boundaries.
3. The contract chain can export and regenerate frontend types.
4. Guard tests confirm the critical runtime/analytics worker task types remain
   registered.

No production ordering, strategy thresholds, `strategy_policy`, or
`production_score` behavior is changed by this inventory.
