# Platform Next Stage Baseline

Date: 2026-06-04

Scope: B0 baseline gate for the next-stage modular architecture plan. This
report records the current implementation facts and freezes the B1-B6
acceptance order before behavior changes.

## Worktree Gate

Initial command:

```bash
git status --short
```

Result:

```text
?? docs/superpowers/plans/2026-06-04-platform-modular-architecture-next-stage-development-plan.md
```

The untracked plan file is treated as user-provided authoritative input. It is
not modified or cleaned by B0.

## Required Baseline Documents Read

- `AGENTS.md`
- `docs/engineering-conventions.md`
- `docs/README.md`
- `docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md`
- `docs/superpowers/plans/2026-06-04-platform-modular-architecture-next-stage-development-plan.md`
- `docs/reports/web-heavy-task-inventory-2026-06-04.md`
- `docs/reports/platform-modular-architecture-phase2-analytics-acceptance-2026-06-04.md`
- `docs/reports/platform-modular-architecture-phase3-worker-acceptance-2026-06-04.md`
- `docs/reports/platform-modular-architecture-phase4-strategy-engine-acceptance-2026-06-04.md`
- `docs/reports/platform-modular-architecture-phase5-execution-model-acceptance-2026-06-04.md`
- `docs/reports/platform-modular-architecture-phase6-frontend-information-acceptance-2026-06-04.md`
- `docs/reports/platform-modular-architecture-phase7-deployment-acceptance-2026-06-04.md`
- `docs/operations/deployment-topology-runbook.md`
- `docs/operations/worker-runbook.md`

## Current OpenAPI Contract Chain

OpenAPI export source:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/export_openapi_schema.py
```

Tracked outputs:

- `docs/contracts/openapi.json`
- `docs/contracts/openapi.hash`

Frontend generated type command:

```bash
cd frontend
npm run api:generate
```

Generated output:

- `frontend/src/generated/api-types.ts`

Frontend contract check:

```bash
cd frontend
npm run api:check
```

`api:check` runs OpenAPI export, generated type regeneration, and TypeScript
typecheck.

## Current Runtime Task Baseline

`backend/app/api/routes/runtime_tasks.py` exposes the Web task surface:

- `POST /api/runtime-tasks`
- `GET /api/runtime-tasks`
- `GET /api/runtime-tasks/{task_id}`
- `GET /api/runtime-tasks/{task_id}/events`
- `GET /api/runtime-tasks/{task_id}/stream`

`backend/app/services/tasks/queue.py` currently supports:

- enqueue and idempotency
- list and get
- events
- claim
- heartbeat
- progress
- retry and failure
- artifact events through `TaskContext`
- stale running task recovery

`backend/app/services/tasks/worker.py` provides `RuntimeTaskWorker` with
one-shot and forever execution. Handlers are resolved through
`TaskHandlerRegistry`.

Registered analytics/runtime heavy task handlers include:

- `data_backfill_24m`
- `data_quality_backfill`
- `analytics_export_daily_bars`
- `analytics_quality_check`
- `strategy_24m_duckdb_report`
- `decision_context_24m_report`
- `portfolio_execution_24m_report`
- `backtest_all_strategies_24m`
- `data_quality_sla_refresh`
- `data_repair_run`
- `realized_outcome_refresh`
- `strategy_drift_refresh`

`backend/scripts/analytics_worker.py` is the current independent analytics
worker entrypoint.

## Current Web Heavy Task Inventory

The accepted inventory marks these routes as already queue-backed or compliant:

| Entry | Current status |
|---|---|
| `POST /api/runtime-tasks` | task submission and status surface |
| `POST /api/data-quality/backfill` | enqueues `data_quality_backfill` |
| `POST /api/data-quality/repair` | enqueues `data_repair_run` |
| `POST /api/factor-mining/tasks/evaluate` | queued factor evaluation alternative |
| `GET /internal/scan-worker/v1/run` | internal worker orchestration endpoint |
| `GET /api/market/pulse` | cached read plus refresh enqueue |
| `POST /api/admin-metrics/latest-data/refresh` | close refresh enqueue chain |
| `POST /api/backtests` | creates queued `BacktestRun` |
| `POST /api/backtests/optimize` | queued optimization |
| `POST /api/backtests/validate` | queued validation |
| `backend/scripts/analytics_worker.py` | independent analytics worker |

The next-stage migration or bounding targets are:

| Entry | B target | Baseline decision |
|---|---|---|
| `GET /api/screeners/low-buy` | B1 | keep bounded/materialized reads; queue heavier/full scan paths |
| `GET /api/screeners/low-buy/execution-backtest` | B1/B4 | move request-time execution backtest to queued or bounded preview path |
| `POST /api/research/backtests` | B1 | retire/redirect direct legacy research execution to queued jobs |
| `POST /api/backtests/etf-t0-minute` | B1 | keep small bounded payloads or enqueue larger research runs |
| `POST /api/backtests/etf-t0-research` | B1 | queue large report generation |
| `GET /api/backtests/{run_id}/portfolio-optimization` | B1/B4 | convert expandable optimization to queued research task |
| `GET /api/backtests/{run_id}/position-policy-research?train_shadow=true` | B1/B4 | force training through worker |
| `POST /api/ml-signals/build-samples` | B1 | queue non-trivial sample builds |
| `POST /api/ml-signals/train` | B1 | queue training |
| `POST /api/ml-signals/incremental-train` | B1 | queue incremental training |
| `POST /api/factor-mining/factors/{factor_key}/evaluate` | B1 | prefer queued task endpoint |
| `POST /api/factor-mining/iterate` | B1 | queue multi-round iterations |
| `POST /api/analysis/analyze/batch` | B1 | keep 10-symbol bound; queue if expanded |
| `GET /api/paper/performance/smart-t-backtest` | B1/B4 | queue if lookback/sample expands |
| `POST /api/paper/backtest-comparison` | B1/B4 | keep read-only bounded; queue large comparisons |

## Analytics Baseline

The accepted Phase 2 baseline exists:

- `backend/app/services/analytics/exporters.py` exports 24-month `daily_bars`
  Parquet datasets.
- `backend/app/services/analytics/manifest.py` writes versioned manifests and
  `daily_bars.latest.json`.
- `backend/app/services/analytics/quality.py` checks 24-month coverage and can
  enqueue `data_backfill_24m`.
- `backend/app/services/analytics/duckdb_repository.py` reads analytics
  artifacts with DuckDB.
- `backend/app/services/analytics/report_queries.py` builds the strategy 24M
  DuckDB report.
- `backend/scripts/export_analytics_parquet.py` and
  `backend/scripts/run_duckdb_strategy_report.py` are the current CLI paths.

B2 will operationalize this chain for worker/scheduler use, ensure manifest
fields are complete, and keep blocked/no_data/stale/partial behavior explicit.

## Strategy Engine Baseline

The accepted Phase 4 baseline exists under:

- `backend/app/services/strategy_engine/outputs.py`
- `backend/app/services/strategy_engine/gates.py`
- `backend/app/services/strategy_engine/low_buy_adapter.py`

Current boundary rules:

- `research_only` does not produce production score.
- non-production strategies do not enter priority-board production scoring.
- `near_entry` stays watch-only.
- Shadow/Paper and `front_row_only` do not bypass production gates.
- Existing `strategy_policy`, low-buy scoring, priority board sorting,
  `priority_score`, `production_score`, `buy_signal_state`, and
  `elite_watch_score` are not replaced.

B3 will add golden parity around adapter adoption and may expose explanation
fields only when production ordering remains unchanged.

## Execution Model Baseline

The accepted Phase 5 baseline exists under:

- `backend/app/services/execution_model/events.py`
- `backend/app/services/execution_model/rules.py`
- `backend/app/services/execution_model/portfolio_preview.py`
- `backend/app/services/execution_model/recommendations.py`

Current boundary rules:

- shared event objects exist for signal, order, fill, position, and exit
- shared lot, cost, availability, and return helpers are test-covered
- max5/max10 remains delegated to `portfolio_backtest_metrics`
- the module is not connected as a replacement for current backtest or paper
  mutation paths

B4 will add parallel preview/golden checks for backtest and paper paths while
keeping canonical fact sources unchanged.

## Frontend Baseline

The accepted Phase 6 baseline centralizes responsibility mapping in:

- `frontend/src/features/trading-workspace/pageResponsibilities.ts`

Pages in scope for B5:

- Realtime Monitor
- Strategy Tracking
- Paper Trading
- Data Console
- Backtest Center

B5 will use the responsibility map to reduce repeated summaries and improve
information hierarchy while preserving stale, partial, blocked, and data-quality
warnings.

## Independent Runtime Baseline

`scripts/run_platform_component.sh` supports these independently runnable
components:

- `web`
- `runtime-worker`
- `scheduler`
- `analytics-worker`
- `backtest-worker`

Runbooks:

- `docs/operations/deployment-topology-runbook.md`
- `docs/operations/worker-runbook.md`

Production compose roles already separate Web, runtime worker, runtime
scheduler, analytics worker, and backtest worker. Web keeps
`WEB_RUNTIME_BACKGROUND_JOBS_ENABLED=false` during deploy.

## Deploy Baseline

Current deploy default:

```bash
DEPLOY_SYNC_MODE=package-only
```

`scripts/deploy_cloud_server.sh` currently:

- resolves scope as `all`, `frontend-hot`, `go`, or `ops`
- builds a full package with `.git`, local runtimes, local DBs, caches,
  `frontend/node_modules`, and `frontend/dist` excluded
- verifies required package paths before upload
- uploads the package by `cloud_scp_to`
- extracts into a new remote release directory
- copies forward `.runtime` and `.env`
- backs up the previous release
- replaces the release directory
- builds/restarts Web, runtime scheduler, runtime worker, backtest worker, and
  analytics worker for `all` scope

`frontend-hot` has a separate dist-only package path.

Remote Git behavior:

- `remote_deploy_from_git` is skipped for `frontend-hot` and for
  `DEPLOY_SYNC_MODE=package-only`.
- If `DEPLOY_SYNC_MODE` is not `package-only`, the script can still attempt
  `git-inplace` or `git-clone` and falls back to package upload when remote Git
  sync is unavailable.
- GitHub Actions currently sets `DEPLOY_SYNC_MODE=package-only`.

B6 will add `DEPLOY_SYNC_MODE=delta-package`, preserve `package-only` fallback,
and keep remote GitHub clone/fetch disabled by default.

## B1-B6 Locked Scope

B1 Web heavy task migration:

- Web remains limited to light reads, task submission, and task status.
- Large training, full scans, optimization, report generation, and broad
  backtests return queued task information or stay explicitly bounded.
- OpenAPI and generated frontend types must be updated if contracts change.

B2 Analytics production chain:

- 24-month `daily_bars` Parquet export, manifest, quality check, DuckDB report,
  and backfill linkage are worker/scheduler ready.
- DuckDB/Parquet remains analytics/reporting only.

B3 Strategy Engine adapter:

- Adapter outputs are golden-checked.
- `production_score`, `watch_score`, `score_components`,
  `exclusion_reasons`, and `warning_tags` may be exposed.
- Production sorting, `strategy_policy`, low-buy, priority board,
  front-row weighted, and strategy tracking production fields do not change.

B4 Execution Model integration:

- Signal/order/fill/position/exit previews run in parallel.
- Backtest and paper outputs are golden-compared before any replacement.
- `portfolio_backtest_metrics` remains final metrics fact source.

B5 Frontend information denoising:

- Core pages use `pageResponsibilities.ts` to prioritize first-screen
  information.
- Content remains complete and warnings stay visible.
- No nested cards, squeezing, overlap, or empty feature-flag holes are
  introduced.

B6 Independent online acceptance and delta upload:

- Add `DEPLOY_SYNC_MODE=delta-package`.
- Generate local deploy manifest with relative path, sha256, size, and mode.
- Store the last successful remote manifest.
- Upload only changed/new files plus deletion manifest when safe.
- Deletions are manifest-bounded and never remove `.env`, `.runtime`,
  databases, backups, virtualenvs, uploaded artifacts, or runtime data.
- Missing manifest, high change ratio, critical file changes, or validation
  failures fall back to `package-only`.
- Deploy logs include sync mode, changed count, deleted count, delta bytes, full
  bytes, upload seconds, and fallback reason.
- Online validation checks Web, runtime worker, scheduler, analytics worker, and
  backtest worker independently.

## Non-Goals And Hard Boundaries

- Do not split into many microservices.
- Do not rewrite the platform.
- Do not modify `strategy_policy`.
- Do not introduce or connect a new production ranking source.
- Do not replace low-buy, priority board, front-row weighted, or existing
  production sorting.
- Do not let `research_only`, `watch_only`, `near_entry`, Shadow, or Paper
  bypass production gates.
- Do not add Web background loops.
- Do not add framework-level dependencies.
- Do not fake bars, fake scores, or fake recommendations.
- Do not treat DuckDB/Parquet as a production trading fact source.
- Do not deploy during B1-B5.

## Acceptance Order

Each batch must finish code, contracts, tests, report, `git diff --check`,
`git status --short`, and a batch commit before the next batch starts.

Final full acceptance after B1-B6:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q

cd /Users/j/Documents/gupiao/frontend
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run analyze

cd /Users/j/Documents/gupiao
git diff --check
git status --short
```

B6 online acceptance includes:

```bash
git push origin HEAD:main
python3 scripts/measure_cloud_go_rust_performance.py --samples 8
python3 scripts/measure_cloud_go_rust_performance.py --samples 8
```

## B0 Verdict

B0 scope is locked. No code behavior changes are made in this batch. Production
sorting impact is none.
