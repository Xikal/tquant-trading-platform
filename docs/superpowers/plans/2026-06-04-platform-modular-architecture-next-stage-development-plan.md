# Platform Modular Architecture Next Stage Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the next stage of the modular-monolith baseline by moving remaining heavy Web entrypoints into workers, promoting the Analytics DuckDB/Parquet chain into an operational worker/scheduler path, gradually wiring Strategy Engine and Execution Model adapters with golden parity, reducing frontend information noise, and adding independent online runtime acceptance plus delta upload deployment acceleration.

**Architecture:** Keep the platform as a modular monolith with independently runnable Web, runtime-worker, scheduler, analytics-worker, and backtest-worker processes. Web only accepts lightweight reads, task submission, and task status queries. Heavy compute, backfill, 24-month analytics, DuckDB reporting, batch validation, strategy research, and broad backtests run through `RuntimeTaskQueue` or the existing backtest worker. DuckDB/Parquet remains an analytics/reporting layer and never becomes the production fact source.

**Tech Stack:** FastAPI, SQLAlchemy, MySQL, Redis, RuntimeTaskQueue, Python workers, DuckDB/Parquet analytics services, Vite/React/AntD frontend, OpenAPI generated frontend types, existing shell deploy scripts.

---

## Baseline Inputs

Read before implementation:

- `AGENTS.md`
- `docs/engineering-conventions.md`
- `docs/README.md`
- `docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md`
- `docs/reports/web-heavy-task-inventory-2026-06-04.md`
- `docs/reports/platform-modular-architecture-phase2-analytics-acceptance-2026-06-04.md`
- `docs/reports/platform-modular-architecture-phase3-worker-acceptance-2026-06-04.md`
- `docs/reports/platform-modular-architecture-phase4-strategy-engine-acceptance-2026-06-04.md`
- `docs/reports/platform-modular-architecture-phase5-execution-model-acceptance-2026-06-04.md`
- `docs/reports/platform-modular-architecture-phase6-frontend-information-acceptance-2026-06-04.md`
- `docs/reports/platform-modular-architecture-phase7-deployment-acceptance-2026-06-04.md`
- `docs/operations/deployment-topology-runbook.md`
- `docs/operations/worker-runbook.md`

Current accepted baseline:

- `RuntimeTaskQueue` supports enqueue, list, get, events, claim, heartbeat, progress, retry, artifact, success, and failure.
- `backend/scripts/analytics_worker.py` runs an analytics task registry.
- Existing analytics handlers include `data_backfill_24m`, `analytics_export_daily_bars`, `analytics_quality_check`, `strategy_24m_duckdb_report`, and `backtest_all_strategies_24m`.
- `backend/app/services/analytics/` contains Parquet export, manifest, quality, DuckDB repository, and report query services.
- `backend/app/services/strategy_engine/` contains the first adapter/gate/output baseline.
- `backend/app/services/execution_model/` contains the first event/rule/recommendation/portfolio preview baseline.
- `frontend/src/features/trading-workspace/pageResponsibilities.ts` is the frontend page responsibility source.
- `scripts/run_platform_component.sh` exposes Web, runtime-worker, scheduler, analytics-worker, and backtest-worker commands.
- Deploy currently defaults to package upload and avoids remote GitHub clone/fetch through `DEPLOY_SYNC_MODE=package-only`.

## Hard Boundaries

- Do not split the application into many microservices.
- Do not rewrite the platform from scratch.
- Do not modify `strategy_policy`.
- Do not introduce a new production ranking source or replace low-buy, priority board, front-row weighted, or existing production sorting.
- Do not let `research_only`, `watch_only`, `near_entry`, Shadow, or Paper states bypass production gates.
- Do not let live quote overlays influence production sorting, `priority_score`, `production_score`, `buy_signal_state`, or `elite_watch_score`.
- Do not run heavy compute, full scans, 24-month exports, DuckDB reports, bulk strategy validation, or large backtests in a Web request.
- Do not use DuckDB/Parquet as a production trading fact source.
- Do not create fake daily bars, fake scores, or fake recommendations.
- Missing or stale data must surface as `blocked`, `no_data`, `stale`, `partial`, or `research_only`.
- Do not add framework-level dependencies.
- Do not add a Web background loop.
- OpenAPI remains the API contract source. Frontend types must be generated from `docs/contracts/openapi.json`.
- Deployment is only part of B6 acceptance. B1-B5 are local/CI implementation batches and must not deploy by themselves.

## Batch Rules

- Run `git status --short` before each batch.
- If the worktree is dirty, inspect relevant diffs before editing and only make minimal changes for that batch.
- Complete code, contract, tests, and report for one batch before starting the next.
- Commit each accepted batch separately.
- Keep feature flags and rollback switches explicit where behavior can affect production surfaces.
- Use golden parity before replacing any strategy, backtest, or paper-trading path.

## B0 - Baseline Gate And Scope Lock

**Purpose:** Establish a clean implementation baseline and freeze the exact migration list before touching code.

**Files to read:**

- `docs/reports/web-heavy-task-inventory-2026-06-04.md`
- `backend/app/api/routes/runtime_tasks.py`
- `backend/app/services/tasks/queue.py`
- `backend/app/services/tasks/worker.py`
- `backend/app/services/tasks/registry.py`
- `backend/app/services/tasks/analytics_handlers.py`
- `backend/app/runtime/background_jobs.py`
- `.github/workflows/ci.yml`
- `scripts/deploy_cloud_server.sh`
- `scripts/quick_cloud_deploy.sh`

**Files to create/update:**

- `docs/reports/platform-next-stage-baseline-2026-06-04.md`

**Steps:**

- [ ] Run `git status --short` and record the result.
- [ ] Re-read the baseline documents and accepted phase reports.
- [ ] Record current OpenAPI export/generation commands and frontend `api:check` command.
- [ ] Record current Web heavy task inventory and mark which entries are B1 migration targets, B2 analytics targets, B3 strategy targets, B4 execution targets, or intentionally bounded synchronous reads.
- [ ] Record current deploy mode: `DEPLOY_SYNC_MODE=package-only`, full package upload path, frontend-hot path, and current remote Git fallback behavior.
- [ ] Write `docs/reports/platform-next-stage-baseline-2026-06-04.md` with baseline, target batches, non-goals, and acceptance order.

**Acceptance commands:**

```bash
cd /Users/j/Documents/gupiao
git status --short
git diff --check
```

**Acceptance criteria:**

- Baseline report exists and lists B1-B6 targets.
- No code behavior changes in B0.
- Worktree contains only the baseline report when B0 is complete.

---

## B1 - Web Heavy Task Migration

**Purpose:** Move remaining heavy or expandable Web request paths to `RuntimeTaskQueue`; keep Web as task submit/status plus bounded read-only responses.

**Primary targets from the inventory:**

- `GET /api/screeners/low-buy`
- `GET /api/screeners/low-buy/execution-backtest`
- `POST /api/research/backtests`
- `POST /api/backtests/etf-t0-minute`
- `POST /api/backtests/etf-t0-research`
- `GET /api/backtests/{run_id}/portfolio-optimization`
- `GET /api/backtests/{run_id}/position-policy-research?train_shadow=true`
- `POST /api/ml-signals/build-samples`
- `POST /api/ml-signals/train`
- `POST /api/ml-signals/incremental-train`
- `POST /api/factor-mining/factors/{factor_key}/evaluate`
- `POST /api/factor-mining/iterate`
- `POST /api/analysis/analyze/batch`
- `GET /api/paper/performance/smart-t-backtest`
- `POST /api/paper/backtest-comparison`

**Files to inspect and modify as needed:**

- `backend/app/api/routes/runtime_tasks.py`
- `backend/app/models/schema_defs/phase4.py`
- `backend/app/services/tasks/queue.py`
- `backend/app/services/tasks/handlers.py`
- `backend/app/services/tasks/registry.py`
- `backend/app/services/tasks/analytics_handlers.py`
- `backend/app/api/routes/screeners.py`
- `backend/app/api/routes/backtests.py`
- `backend/app/api/routes/research.py`
- `backend/app/api/routes/ml_signals.py`
- `backend/app/api/routes/factor_mining.py`
- `backend/app/api/routes/analysis.py`
- `backend/app/api/routes/paper.py`
- `frontend/src/api/runtimeTasks.ts`
- frontend API wrappers for changed routes
- `docs/contracts/openapi.json`
- `frontend/src/generated/api-types.ts`

**Files to create/update:**

- `backend/tests/test_web_heavy_task_migration.py`
- `backend/tests/test_runtime_task_contracts.py`
- `docs/reports/platform-next-stage-b1-web-heavy-task-migration-2026-06-04.md`

**Implementation steps:**

- [ ] Add or reuse typed `RuntimeTaskCreate` helpers for the migrated task types.
- [ ] For each heavy endpoint, classify the allowed Web behavior:
  - bounded lightweight read stays synchronous;
  - large sample windows, training, optimization, report generation, full scan, and broad backtest return `202` plus `task_id`;
  - previously hidden legacy direct execution paths redirect to the queued task surface or return a documented deprecation response with queued replacement.
- [ ] Add task handlers for migrated types that do not already exist.
- [ ] Ensure each handler writes progress events, artifact metadata, and terminal status.
- [ ] Ensure failed or insufficient-data paths return explicit `blocked`, `no_data`, `stale`, `partial`, or `research_only` statuses.
- [ ] Preserve existing production sorting fields and strategy rules.
- [ ] Update OpenAPI and frontend generated types.
- [ ] Update frontend wrappers so new queued responses are typed from generated OpenAPI types, not duplicate handwritten DTOs.
- [ ] Add route tests proving heavy mode does not execute compute in the request thread.
- [ ] Add worker tests proving migrated tasks execute through the registry and produce artifacts or terminal failure details.
- [ ] Update the B1 report with endpoint-by-endpoint before/after behavior.

**Acceptance commands:**

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_web_heavy_task_migration.py \
  backend/tests/test_runtime_task_contracts.py \
  backend/tests/test_phase4_runtime_worker_tasks.py \
  -q

PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/export_openapi_schema.py
cd frontend && npm run api:check && npm run lint && npm test -- --run
cd /Users/j/Documents/gupiao && git diff --check && git status --short
```

**Acceptance criteria:**

- Every B1 target either stays explicitly bounded or returns queued task status for heavy work.
- Web request paths do not run full scans, training, optimization, large sample building, or large reports.
- OpenAPI and generated frontend types are in sync.
- Existing production ranking fields are unchanged.

**Suggested commit:**

```text
architecture: migrate heavy web tasks to runtime queue
```

---

## B2 - Analytics Production Chain

**Purpose:** Make the 24-month Parquet export, manifest, quality check, DuckDB strategy report, and data backfill chain worker/scheduler-ready.

**Files to inspect and modify as needed:**

- `backend/app/services/analytics/exporters.py`
- `backend/app/services/analytics/manifest.py`
- `backend/app/services/analytics/quality.py`
- `backend/app/services/analytics/duckdb_repository.py`
- `backend/app/services/analytics/report_queries.py`
- `backend/app/services/tasks/analytics_handlers.py`
- `backend/app/runtime/background_jobs.py`
- `backend/scripts/analytics_worker.py`
- `backend/scripts/export_analytics_parquet.py`
- `backend/scripts/run_duckdb_strategy_report.py`
- `docs/reports/strategy_24m_duckdb_report.md`

**Files to create/update:**

- `backend/tests/test_analytics_production_chain.py`
- `backend/tests/test_analytics_worker_handlers.py`
- `docs/reports/platform-next-stage-b2-analytics-production-chain-2026-06-04.md`

**Implementation steps:**

- [ ] Confirm `analytics_export_daily_bars` accepts `months`, `end_date`, `output_root`, and `create_backfill_task`.
- [ ] Make the manifest include dataset, months, date range, row counts, symbol counts, coverage, source DB timestamp, generated_at, quality status, and artifact paths.
- [ ] If 24-month data is insufficient, mark export as `blocked` and enqueue or link a `data_backfill_24m` task. Do not generate fake bars.
- [ ] Ensure `analytics_quality_check` can consume the latest manifest and report `ok`, `blocked`, `no_data`, or `stale`.
- [ ] Ensure `strategy_24m_duckdb_report` consumes an explicit manifest or latest manifest and records artifacts.
- [ ] Wire scheduler/background jobs to enqueue analytics tasks on a controlled schedule without adding Web loops.
- [ ] Add a minimal real task smoke test through `RuntimeTaskWorker` using a test DB and temporary output root.
- [ ] Update scripts so manual CLI and worker handler behavior stay aligned.
- [ ] Update the B2 report with manifest sample, blocked sample, and successful report sample.

**Acceptance commands:**

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_analytics_production_chain.py \
  backend/tests/test_analytics_worker_handlers.py \
  backend/tests/test_phase4_runtime_worker_tasks.py \
  -q

PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/export_analytics_parquet.py \
  --dataset daily_bars \
  --months 24 \
  --output-root /tmp/gupiao-analytics-acceptance \
  --no-create-backfill-task

PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/run_duckdb_strategy_report.py \
  --months 24 \
  --output-root /tmp/gupiao-analytics-acceptance \
  --output-md /tmp/gupiao-strategy-24m-duckdb-report.md \
  --output-json /tmp/gupiao-strategy-24m-duckdb-report.json

git diff --check && git status --short
```

**Acceptance criteria:**

- 24-month analytics export produces a manifest or an explicit blocked result.
- DuckDB report can be generated from a manifest.
- Data insufficiency enqueues or links a backfill task and does not silently pass.
- Worker and CLI behavior match.

**Suggested commit:**

```text
analytics: operationalize 24m parquet duckdb chain
```

---

## B3 - Strategy Engine Adapter Integration

**Purpose:** Route existing strategy paths through `strategy_engine` adapters in shadow/parity mode first, then enable safe read-path adoption without changing production sorting.

**Files to inspect and modify as needed:**

- `backend/app/services/strategy_engine/__init__.py`
- `backend/app/services/strategy_engine/outputs.py`
- `backend/app/services/strategy_engine/gates.py`
- `backend/app/services/strategy_engine/low_buy_adapter.py`
- `backend/app/services/low_buy/priority_board.py`
- `backend/app/services/low_buy/production_scoring.py`
- `backend/app/services/strategy_tracking.py`
- `backend/app/services/strategy_tracking_daily.py`
- `backend/app/services/paper/`
- `backend/app/core/config.py`

**Files to create/update:**

- `backend/tests/test_strategy_engine_adapter_golden.py`
- `backend/tests/test_strategy_engine_production_gate_guards.py`
- `docs/reports/platform-next-stage-b3-strategy-engine-integration-2026-06-04.md`

**Implementation steps:**

- [ ] Add or confirm a feature flag such as `STRATEGY_ENGINE_ADAPTER_ENABLED=false` for production-facing adoption.
- [ ] Add adapter outputs with `production_score`, `watch_score`, `score_components`, `exclusion_reasons`, and `warning_tags`.
- [ ] Keep `near_entry` as watch-only.
- [ ] Keep `research_only` out of production ranking.
- [ ] Keep `front_row_only` from becoming a hard production filter unless an existing rule already does so.
- [ ] Build golden fixtures from existing strategy outputs before adoption.
- [ ] Compare adapter outputs against existing fields for priority board and strategy tracking paths.
- [ ] If parity fails, leave adapter in shadow mode and report the exact field differences.
- [ ] If parity passes, allow read-path consumers to display adapter explanation fields without altering ordering.
- [ ] Update B3 report with golden hashes, field-level parity, flag defaults, and rollback instructions.

**Acceptance commands:**

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_strategy_engine_adapter_golden.py \
  backend/tests/test_strategy_engine_production_gate_guards.py \
  backend/tests/test_low_buy_priority_board_strategy_variants.py \
  backend/tests/test_low_buy_production_scoring.py \
  -q

git diff --check && git status --short
```

**Acceptance criteria:**

- Adapter output matches existing strategy facts for production fields.
- Production ordering, `strategy_policy`, scoring formulae, and gate behavior are unchanged.
- New explanation fields are display/research safe.
- Feature flag rollback is documented.

**Suggested commit:**

```text
strategy: add strategy engine adapter parity path
```

---

## B4 - Execution Model Integration

**Purpose:** Gradually make backtest and paper trading reuse shared signal, order, fill, position, and exit rules through the execution model, first in parallel verification mode.

**Files to inspect and modify as needed:**

- `backend/app/services/execution_model/__init__.py`
- `backend/app/services/execution_model/events.py`
- `backend/app/services/execution_model/rules.py`
- `backend/app/services/execution_model/portfolio_preview.py`
- `backend/app/services/execution_model/recommendations.py`
- `backend/app/services/backtest/`
- `backend/app/services/paper/`
- `backend/app/api/routes/backtests.py`
- `backend/app/api/routes/paper.py`

**Files to create/update:**

- `backend/tests/test_execution_model_backtest_golden.py`
- `backend/tests/test_execution_model_paper_golden.py`
- `backend/tests/test_execution_model_position_exit_rules.py`
- `docs/reports/platform-next-stage-b4-execution-model-integration-2026-06-04.md`

**Implementation steps:**

- [ ] Confirm event model fields for signal, order, fill, position, exit, and risk decision.
- [ ] Add an execution-model preview path for backtest results without replacing the canonical backtest engine.
- [ ] Add a paper-trading preview path for fills and positions without changing live paper state mutation until parity passes.
- [ ] Compare max5/max10, realized fills, position count, cash, drawdown, exit reason, and risk tags against current outputs.
- [ ] Keep `portfolio_backtest_metrics` as the final fact source for 24-month portfolio metrics.
- [ ] Do not split monthly max5/max10 and merge them independently.
- [ ] Add feature flag such as `EXECUTION_MODEL_SHARED_RULES_ENABLED=false` for replacement behavior.
- [ ] Update B4 report with golden hashes, drift table, accepted display-only fields, and rollback path.

**Acceptance commands:**

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_execution_model_backtest_golden.py \
  backend/tests/test_execution_model_paper_golden.py \
  backend/tests/test_execution_model_position_exit_rules.py \
  backend/tests/test_backtest_engine_regression.py \
  -q

git diff --check && git status --short
```

**Acceptance criteria:**

- Backtest and paper previews can run through shared execution-model rules.
- Existing canonical outputs stay golden-equal until an explicit later replacement batch.
- Strategy recommendations can classify variants as keep, downweight, default-off, or delete-candidate without changing production behavior.

**Suggested commit:**

```text
execution: wire shared model parity previews
```

---

## B5 - Frontend Information Denoising

**Purpose:** Use `pageResponsibilities.ts` to reduce repeated, crowded, and low-priority information across core pages while preserving complete access to details.

**Pages in scope:**

- Realtime Monitor
- Strategy Tracking
- Paper Trading
- Data Console
- Backtest Center

**Files to inspect and modify as needed:**

- `frontend/src/features/trading-workspace/pageResponsibilities.ts`
- `frontend/src/features/trading-workspace/pageResponsibilities.test.ts`
- `frontend/src/features/monitor/`
- `frontend/src/features/strategy-tracking/`
- `frontend/src/features/paper/`
- `frontend/src/features/data-console/`
- `frontend/src/features/backtest/`
- `frontend/src/ui/table/DataTable.tsx`
- `frontend/src/ui/list/VirtualCardList.tsx`
- shared page layout/style files used by the pages above

**Files to create/update:**

- `frontend/src/features/trading-workspace/pageInformationHierarchy.test.ts`
- page-specific tests only where existing coverage is missing
- `docs/reports/platform-next-stage-b5-frontend-information-denoising-2026-06-04.md`

**Implementation steps:**

- [ ] For each page, define first-screen primary question, secondary details, and drill-down sections in `pageResponsibilities.ts`.
- [ ] Remove duplicated summary blocks where the same facts already appear in the page-level summary.
- [ ] Use `DataTable` for new large tables and `VirtualCardList` for long card lists.
- [ ] Keep details accessible through tabs, drawers, or explicit sections; do not hide required data.
- [ ] Avoid cards inside cards, layout squeezing, and overlapping text.
- [ ] Preserve stale, partial, blocked, and data-quality warnings.
- [ ] Ensure feature-flag-off states do not leave empty holes.
- [ ] Add frontend tests for responsibility mapping and the most important page render states.
- [ ] Produce desktop and mobile screenshots for the B5 report if visual changes are substantial.

**Acceptance commands:**

```bash
cd /Users/j/Documents/gupiao/frontend
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run analyze
cd /Users/j/Documents/gupiao && git diff --check && git status --short
```

**Acceptance criteria:**

- Each page has one clear first-screen priority and no duplicated critical summaries.
- Large tables/lists use existing scalable components.
- Stale/partial/blocked warnings remain visible.
- No card nesting, text overlap, or empty flag-off surfaces are introduced.
- Bundle budget remains within the current guardrail.

**Suggested commit:**

```text
frontend: denoise trading workspace pages
```

---

## B6 - Independent Runtime Online Acceptance And Delta Upload Deployment

**Purpose:** Verify independent Web/worker/scheduler operation online and add a faster deployment path based on delta upload instead of full package upload or remote Git fetch.

**Deployment boundary:** This is the only batch that includes deployment. If executed as an implementation task, the task prompt must explicitly authorize deployment. B1-B5 must not deploy.

### B6A - Independent Runtime Acceptance

**Files to inspect and modify as needed:**

- `scripts/run_platform_component.sh`
- `scripts/dev_start_all.sh`
- `scripts/quick_cloud_deploy.sh`
- `scripts/deploy_cloud_server.sh`
- `docs/operations/deployment-topology-runbook.md`
- `docs/operations/worker-runbook.md`
- `PRODUCTION_RUNBOOK.md`
- `.github/workflows/ci.yml`

**Files to create/update:**

- `backend/tests/test_independent_runtime_components.py`
- `backend/tests/test_cloud_deploy_scripts.py`
- `docs/reports/platform-next-stage-b6-independent-runtime-online-acceptance-2026-06-04.md`

**Implementation steps:**

- [ ] Confirm `web`, `runtime-worker`, `scheduler`, `analytics-worker`, and `backtest-worker` can print and run independently.
- [ ] Add health checks for Web readyz, runtime task queue heartbeat, scheduler enqueue health, analytics worker claim health, and backtest worker status.
- [ ] Add rollback documentation for each independently restarted process.
- [ ] Verify a queued analytics task and a queued backtest/research task can be claimed by their intended worker.
- [ ] Update runbooks with exact local and production commands.

### B6B - Delta Upload Deployment Acceleration

**Problem to solve:** Full package upload avoids remote GitHub network failures but still transfers the whole repository package. For repeat deploys, upload only changed files plus a deletion manifest, then rebuild/restart only the affected scope.

**Files to inspect and modify as needed:**

- `scripts/deploy_cloud_server.sh`
- `scripts/quick_cloud_deploy.sh`
- `scripts/one_click_cloud_deploy.sh`
- `scripts/cloud_ssh_lib.sh`
- `.github/workflows/ci.yml`
- `backend/tests/test_cloud_deploy_scripts.py`
- `docs/operations/deployment-topology-runbook.md`

**New deploy mode:**

- Add `DEPLOY_SYNC_MODE=delta-package`.
- Keep `DEPLOY_SYNC_MODE=package-only` as safe fallback.
- Keep remote Git sync disabled by default in CI.

**Delta upload design:**

- [ ] Build a local deploy manifest with relative path, sha256, size, and file mode for all files included by the existing full package rules.
- [ ] Store the last successful remote manifest under the release, for example `.runtime/deploy-manifest.json`.
- [ ] Compare local and remote manifests over SSH and compute:
  - changed files;
  - new files;
  - deleted files;
  - critical files that force full package fallback.
- [ ] Critical files must include at least `Dockerfile`, compose files, deploy scripts, requirements/lock files, Alembic migrations, generated OpenAPI/types, frontend build artifacts, and worker entrypoints.
- [ ] Package only changed/new files plus `deploy-delta-manifest.json` and `deploy-delete-manifest.json`.
- [ ] Apply the delta on the remote by copying the current release to a staging directory, applying changed files, applying safe deletions, validating required paths, then atomically replacing the release.
- [ ] Never delete `.env`, `.runtime`, databases, backups, local virtualenvs, uploaded artifacts, or runtime data.
- [ ] If the remote manifest is missing, changed-file ratio is too high, critical validation fails, or staging validation fails, automatically fall back to full `package-only`.
- [ ] Log deploy metrics:
  - sync mode;
  - changed file count;
  - deleted file count;
  - delta package bytes;
  - estimated full package bytes;
  - upload seconds;
  - fallback reason if any.
- [ ] Extend `quick_cloud_deploy.sh` with `--sync-mode <delta-package|package-only|git-inplace|git-clone>` or equivalent env passthrough.
- [ ] Update GitHub Actions deploy job to use `DEPLOY_SYNC_MODE=delta-package` after local tests pass, while preserving full package fallback.
- [ ] Add tests for manifest generation, deletion safety, fallback behavior, CLI parsing, and CI env propagation.

**B6B acceptance commands:**

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_cloud_deploy_scripts.py -q

DEPLOY_SYNC_MODE=delta-package scripts/one_click_cloud_deploy.sh --dry-run
DEPLOY_SYNC_MODE=package-only scripts/one_click_cloud_deploy.sh --dry-run

git diff --check && git status --short
```

**B6B acceptance criteria:**

- Repeat deploys can use delta upload without remote GitHub clone/fetch.
- Full package fallback remains automatic and tested.
- Remote deletion is safe and manifest-bounded.
- Deploy logs show enough metrics to compare full upload versus delta upload.

### B6C - Online Acceptance

**Online steps after local tests and commit:**

- [ ] Push the accepted branch to `main`.
- [ ] Wait for GitHub Actions deploy job success.
- [ ] Confirm deploy log shows `DEPLOY_SYNC_MODE=delta-package` or a documented fallback to `package-only`.
- [ ] Confirm Web readyz and public domain checks pass.
- [ ] Confirm `runtime-worker`, `runtime-scheduler`, `analytics-worker`, and `backtest-worker` containers/processes are running.
- [ ] Queue one minimal runtime task and verify claim, heartbeat, progress, and terminal status.
- [ ] Queue one analytics export/report smoke task or verify the scheduled analytics queue path.
- [ ] Run two online performance/health rounds.
- [ ] Update final B6 report with deploy run ID, job result, delta upload metrics, worker health, task results, and rollback procedure.

**Online acceptance commands:**

```bash
cd /Users/j/Documents/gupiao
git push origin HEAD:main

python3 scripts/measure_cloud_go_rust_performance.py --samples 8
python3 scripts/measure_cloud_go_rust_performance.py --samples 8
```

**Acceptance criteria:**

- Deploy job succeeds.
- Online Web, runtime-worker, scheduler, analytics-worker, and backtest-worker are independently healthy.
- At least one worker task can be queued and completed or fails with an explicit bounded reason.
- Delta upload is used or safely falls back to full package with a recorded reason.
- No production ranking, strategy policy, or strategy score behavior changes.

**Suggested commit:**

```text
deploy: add delta upload and independent runtime acceptance
```

---

## Final Full Acceptance

Run after B1-B6 are complete:

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

Final reports:

- `docs/reports/platform-next-stage-baseline-2026-06-04.md`
- `docs/reports/platform-next-stage-b1-web-heavy-task-migration-2026-06-04.md`
- `docs/reports/platform-next-stage-b2-analytics-production-chain-2026-06-04.md`
- `docs/reports/platform-next-stage-b3-strategy-engine-integration-2026-06-04.md`
- `docs/reports/platform-next-stage-b4-execution-model-integration-2026-06-04.md`
- `docs/reports/platform-next-stage-b5-frontend-information-denoising-2026-06-04.md`
- `docs/reports/platform-next-stage-b6-independent-runtime-online-acceptance-2026-06-04.md`
- `docs/reports/platform-modular-architecture-next-stage-final-acceptance-2026-06-04.md`

Final response must include:

- Completed batches.
- Modified files.
- New files.
- Test results.
- OpenAPI/generated type status.
- Web heavy task migration status.
- Worker task independent execution status.
- DuckDB/Parquet report generation status.
- Delta upload deployment metrics and fallback status.
- Remaining risks and rollback path.
- Deployment status.
- Explicit production-sorting impact conclusion.

## Rollback Summary

- B1: disable migrated route-specific flags or use existing queued task fallback; Web remains capable of task submission/status.
- B2: disable scheduled analytics tasks; keep CLI/manual export; DuckDB/Parquet remains reporting-only.
- B3: set `STRATEGY_ENGINE_ADAPTER_ENABLED=false`.
- B4: set `EXECUTION_MODEL_SHARED_RULES_ENABLED=false`.
- B5: revert page layout commits; data contracts remain unchanged.
- B6: set `DEPLOY_SYNC_MODE=package-only` to disable delta upload; restart individual workers through the existing deployment topology runbook.

## Production Sorting Impact

This plan must not affect production sorting. The only allowed production-visible changes are:

- heavy work is submitted to workers instead of running in Web requests;
- analytics artifacts and reports become easier to produce;
- strategy and execution adapters expose parity-checked explanation or preview fields;
- frontend information hierarchy is cleaner;
- deployment can upload less data through delta packages;
- independent process health is easier to verify.

No batch may change `strategy_policy`, production ranking order, low-buy rules, priority board scoring, front-row weighted scoring, or portfolio/backtest fact sources without a separate explicit plan and golden parity approval.
