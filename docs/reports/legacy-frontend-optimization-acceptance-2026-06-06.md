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

## Residual Risk

- Batch 2 still needs to unify stale/degraded/waiting copy across monitor, playbook, and latest-data settings surfaces.
