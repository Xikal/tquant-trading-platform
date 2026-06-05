# Monitor Page Split Baseline

Date: 2026-06-05

## Git Status

```text
?? docs/monitor-page-split-development-plan-2026-06-05.md
```

## Current Monitor Surface

- Route: `/monitor`
- Page component: `frontend/src/features/monitor/MonitorPage.tsx`
- Panel modules: `frontend/src/features/monitor/MonitorPage.panels.tsx`, `frontend/src/features/monitor/MonitorMoreTabs.tsx`
- Data hook: `frontend/src/features/trading-workspace/useMonitorData.ts`
- Workspace data owner: `frontend/src/features/trading-workspace/TradingWorkspace.tsx`
- BFF path: `/bff/v1/workspace/monitor`
- Priority board path: `monitor_snapshot.priority_board`

## Split Boundary

- `/monitor`: realtime action desk.
- `/monitor/market`: market context desk.

## Hard Boundaries

- No deployment.
- No production strategy semantic changes.
- No `strategy_policy.py` changes.
- No priority-board ranking, production score, or production sorting changes.
- No BFF contract split in Phase 1.
- No `monitor_snapshot.priority_board` read-path change.
- No duplicated SSE or quote stream.
