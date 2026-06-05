# Monitor Page Split Acceptance

Date: 2026-06-05

## Routes

- `/monitor`: realtime action desk.
- `/monitor/market`: market context desk.

## BFF/API

- Phase 1 kept `/bff/v1/workspace/monitor` as the shared monitor data source.
- Phase 2 adds an optional backward-compatible view projection query:
  - `/bff/v1/workspace/monitor?view=full` remains the default legacy-compatible payload.
  - `/bff/v1/workspace/monitor?view=action` returns action-desk data plus compact market pulse, and trims full market context fields.
  - `/bff/v1/workspace/monitor?view=market` keeps the `priority_board` compatibility alias and trims watchlist action payload.
- Priority board still reads from the existing monitor payload path: `monitor_snapshot.priority_board`.
- OpenAPI and generated frontend types were updated for the optional `view` query parameter.
- OpenAPI hash after Phase 2: `0704afb10053824e1a7da970a42ee53a783cc92c268ab8b5cc5df5c2b534f05c`.

## Realtime

- Monitor data is active for both `monitor` and `monitor-market` through `isMonitorDataPage(page)`.
- `useMonitorData` remains created once in `TradingWorkspace`.
- Quote stream ownership remains inside `useMonitorData`; no page-level `useQuoteStream` call was added.
- Page entry and route switches refresh the matching BFF view once through the existing `useMonitorData` pipeline.
- Static search confirmed new page components do not create `EventSource` or quote stream subscriptions.

## Tests

```text
cd /Users/j/Documents/gupiao/frontend
npm run api:check
PASS

npm run typecheck
PASS

npm run lint
PASS

npm test -- --run
PASS: Test Files 76 passed (76), Tests 240 passed (240)

npm run build
PASS

cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_bff_*.py backend/tests/test_go_bff_shadow.py -q
PASS: 28 passed, 1 warning

cd /Users/j/Documents/gupiao/go-services/bff-gateway
go test ./...
PASS

cd /Users/j/Documents/gupiao
git diff --check
PASS

cd /Users/j/Documents/gupiao/frontend
npm run dev -- --host 127.0.0.1 --port 5174
curl http://127.0.0.1:5174/monitor
PASS: 200 text/html
curl http://127.0.0.1:5174/monitor/market
PASS: 200 text/html
```

Note: the full Vitest run prints an expected guard-fixture stderr line for `badStore.ts`, but exits with code 0 and all tests pass.

## Platform Impact

Conclusion: no production strategy semantic change, no production ranking change, no `strategy_policy.py` change, no priority-board score or sorting change.

## Phase 2 Performance Risk

- Browser request ownership is unchanged: `TradingWorkspace` still creates a single `useMonitorData` instance.
- `/monitor` uses the `action` projection and avoids full market-context payload on action desk refresh.
- `/monitor/market` uses the `market` projection and requests market-context sources only for that page.
- No live/cloud hot-read p95 measurement was run in this task because no deployment was authorized.

## Rollback

- Route rollback: remove `monitor-market` from `PAGE_PATHS`, `PATH_PAGE_MAP`, navigation, and `WorkspacePageContent`.
- BFF projection rollback: stop passing `view` from the frontend; backend defaults to `view=full`.
- `/monitor` continues to serve the realtime action desk through the compatibility `MonitorPage` wrapper.

## Deployment

Not deployed. No commit and no push were performed in this task.
