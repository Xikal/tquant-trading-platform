# Legacy Frontend Optimization Acceptance Report

Date: 2026-06-06
Scope: `frontend/` only

## Baseline

- git status before work: pre-existing `frontend/src/features/trading-workspace/TradingWorkspaceChrome.test.ts` modified; multiple pre-existing `frontend-next` docs/directories untracked; this run added `docs/superpowers/plans/2026-06-06-legacy-frontend-optimization.md`.
- typecheck: pass (`npm run typecheck`)
- vitest: pass (`npm test -- --run`, 80 files / 275 tests)
- lint: pass (`npm run lint`)
- build: pass (`npm run build`)
- analyze: pass (`npm run analyze`)
- analyze first_screen_js_gzip_kb: 318
- analyze total_gzip_kb: 818.49
- analyze baseline_first_screen_js_gzip_kb: 400
- analyze first_screen_js_gzip_reduction_pct: 20.5
- monitor BFF smoke normal: fail at baseline; BFF request count was 1 but an extra `/api/screeners/low-buy/priority-board` fallback request was issued when the smoke BFF payload carried an empty priority board.
- monitor BFF smoke 500: pass
- monitor BFF smoke auth: pass

## Batch Results

### Batch 1: Monitor BFF First-Screen Cleanup

- files changed:
  - `frontend/src/features/trading-workspace/useMonitorData.ts`
  - `frontend/src/features/trading-workspace/monitorWorkspaceLoaders.ts`
  - `frontend/src/features/trading-workspace/monitorWorkspaceLoaders.test.ts`
  - `frontend/src/features/trading-workspace/monitorRefreshState.ts`
  - `frontend/src/features/trading-workspace/monitorRefreshState.test.ts`
  - `frontend/scripts/smoke-monitor-bff.mjs`
- focused tests: pass (`npm test -- --run src/features/trading-workspace/useMonitorData.test.ts src/features/trading-workspace/useMonitorWorkspaceBff.test.ts src/features/trading-workspace/monitorWorkspaceLoaders.test.ts src/features/trading-workspace/monitorRefreshState.test.ts`, 4 files / 26 tests)
- typecheck: pass (`npm run typecheck`)
- lint: pass (`npm run lint`)
- build: pass (`npm run build`)
- full vitest: pass (`npm test -- --run`, 82 files / 285 tests)
- monitor BFF smoke normal: pass
- monitor BFF smoke 500: pass
- monitor BFF smoke auth: pass
- note: normal smoke now uses the current nested `monitor_snapshot.priority_board` BFF contract with a populated board, so the first-screen path no longer issues the legacy `/api/screeners/low-buy/priority-board` fallback in the healthy aggregate case.

### Batch 2: Unified Freshness And Degraded-State UI

- files changed:
  - `frontend/src/features/workspace-shared/dataFreshnessViewModel.ts`
  - `frontend/src/features/workspace-shared/dataFreshnessViewModel.test.ts`
  - `frontend/src/features/monitor/MonitorActionPage.tsx`
  - `frontend/src/features/monitor/MonitorActionPage.test.tsx`
  - `frontend/src/features/playbook/PlaybookPage.tsx`
  - `frontend/src/features/trading-workspace/PlaybookPage.test.tsx`
  - `frontend/src/features/settings/LatestDataStatusCard.tsx`
- focused tests: pass (`npm test -- --run src/features/workspace-shared/dataFreshnessViewModel.test.ts src/features/monitor/MonitorActionPage.test.tsx src/features/trading-workspace/PlaybookPage.test.tsx src/features/settings/SettingsPage.test.tsx`, 4 files / 19 tests)
- typecheck: pass (`npm run typecheck`)
- lint: pass (`npm run lint`)
- full vitest: pass (`npm test -- --run`, 83 files / 290 tests)
- build: pass (`npm run build`)
- stale copy: monitor priority board and playbook stale surfaces now share `数据已过期，仅供复盘` while preserving the backend stale reason.

### Batch 3: Route Bundle Budget Tightening

- files changed:
  - `frontend/scripts/check-bundle-budget.mjs`
  - `frontend/scripts/check-bundle-budget.test.mjs`
- route budget test: pass (`npm test -- --run scripts/check-bundle-budget.test.mjs`, 1 file / 6 tests)
- build: pass (`npm run build`)
- analyze: pass (`npm run analyze`)
- typecheck: pass (`npm run typecheck`)
- lint: pass (`npm run lint`)
- full vitest: pass (`npm test -- --run`, 83 files / 292 tests)
- analyze first_screen_js_gzip_kb: 318
- analyze total_gzip_kb: 819.59
- forbidden lazy/heavy route chunks in first-screen-js: guarded by `check-bundle-budget.mjs` for `BacktestPage-`, `PaperTradingPage-`, `SettingsPage-`, `DataConsolePage-`, `StrategyTrackingPage-`, and `echarts-`.

### Batch 4: Settings And Paper Page View Models

- files changed:
  - `frontend/src/features/settings/SettingsPage.viewModel.ts`
  - `frontend/src/features/settings/SettingsPage.viewModel.test.ts`
  - `frontend/src/features/settings/SettingsPage.tsx`
  - `frontend/src/features/paper/paperTradingStatus.ts`
  - `frontend/src/features/paper/paperTradingStatus.test.ts`
  - `frontend/src/features/paper/PaperTradingPage.tsx`
- focused tests: pass (`npm test -- --run src/features/settings/SettingsPage.viewModel.test.ts src/features/settings/SettingsPage.test.tsx src/features/paper/paperTradingStatus.test.ts src/features/trading-workspace/PaperTradingPage.test.tsx`, 4 files / 21 tests)
- typecheck: pass (`npm run typecheck`)
- lint: pass (`npm run lint`)
- full vitest: pass (`npm test -- --run`, 85 files / 298 tests)
- build: pass (`npm run build`)
- page behavior: Settings API calls, save handlers, feature-flag actions, and Paper UI store/event handlers remain in page components; only pure derived state moved to helpers.

### Batch 5: Core Workflow Browser Smoke

- files changed:
  - `frontend/scripts/smoke-core-workflow.mjs`
  - `frontend/scripts/smoke-core-workflow-fixtures.mjs`
  - `frontend/scripts/smoke-core-workflow-payloads.mjs`
  - `frontend/package.json`
- script check: pass (`node --check scripts/smoke-core-workflow.mjs && node --check scripts/smoke-core-workflow-fixtures.mjs && node --check scripts/smoke-core-workflow-payloads.mjs`)
- build: pass (`npm run build`)
- core workflow smoke normal: pass (`FRONTEND_SMOKE_URL=http://127.0.0.1:4173 npm run smoke:core-workflow`)
- core workflow smoke stale: pass (`CORE_WORKFLOW_SMOKE_SCENARIO=stale FRONTEND_SMOKE_URL=http://127.0.0.1:4173 npm run smoke:core-workflow`)
- monitor BFF smoke: pass (`npm run smoke:monitor-bff`)
- typecheck: pass (`npm run typecheck`)
- lint: pass (`npm run lint`)
- full vitest: pass (`npm test -- --run`, 85 files / 298 tests)
- route coverage: `/monitor -> /playbook -> /backtest -> /paper -> /settings` direct-entry workflow renders in one authenticated browser session; stale monitor smoke asserts visible `仅供复盘` / `数据已过期` copy.

## Residual Risk

- No production deployment was run in this pass.
- The smoke uses mocked API payloads; live backend contract drift still needs the existing online smoke/deployment gate before production rollout.
