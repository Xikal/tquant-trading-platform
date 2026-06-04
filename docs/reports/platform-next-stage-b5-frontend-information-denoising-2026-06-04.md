# Platform Next Stage B5 Frontend Information Denoising

Date: 2026-06-04

Scope: B5 only. This batch uses `pageResponsibilities.ts` to make the five core
workspace pages carry a consistent information hierarchy. It does not remove
required content, change API calls, or alter trading/strategy behavior.

## Worktree Gate

Initial B5 status after B4 commit:

```text
?? docs/superpowers/plans/2026-06-04-platform-modular-architecture-next-stage-development-plan.md
```

The untracked plan file remains user-provided authority input and is not staged
by B5.

## Implementation

Updated `frontend/src/features/trading-workspace/pageResponsibilities.ts` with
explicit hierarchy fields:

- `primaryQuestion`
- `detailQuestion`
- `drilldownPattern`

Added `PagePriorityStrip`:

- rendered only for realtime monitor, strategy tracking, paper trading, data
  console, and backtest center
- uses a slim full-width band, not a card
- shows first-screen, detail, and drilldown layers as compact chips
- keeps content derived from the responsibility map so individual pages do not
  duplicate long summaries

Updated CSS in `workspace-primitives-intro.css`:

- responsive grid on desktop
- single column on mobile
- no card nesting and no fixed-width text overflow

## Page Hierarchy

| Page | First-screen priority | Detail layer |
| --- | --- | --- |
| Realtime Monitor | market state, production priority board, holdings, key levels | ETF T0, market review, hourly snapshots |
| Strategy Tracking | signal performance, risk distribution, review conclusion, relative strength | signal detail, holding analysis, drift, trading experience |
| Paper Trading | positions, orders, real return, risk | automation logs, strategy performance, reconciliation, reviews |
| Data Console | source health, coverage, backfill tasks, quality gate | runtime fallback, vendor status, task queue, sync log |
| Backtest Center | 24M report, OOS validation, portfolio return, recommendations | run records, attribution, correlation, capacity research |

## Tests

Acceptance command:

```bash
cd frontend
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run analyze
```

Result before B5 commit: pass.

## Production Sorting Verdict

B5 is frontend-only. It does not change production ordering, API contracts,
strategy scoring, worker tasks, data facts, or paper/backtest facts.

