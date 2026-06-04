# Platform Modular Architecture Phase 6 Acceptance

Date: 2026-06-04.

Scope: Phase 6 only. This pass establishes a frontend information hierarchy
baseline and removes one known nested-card layout risk in the paper-trading
surface. It does not change strategy logic, production ranking, paper order
semantics, backtest semantics, API contracts, or backend runtime behavior.

## Page Responsibility Baseline

Added a typed responsibility map for the five decision surfaces covered by
Phase 6:

- Real-time monitor: "what to watch today"
- Strategy tracking: "what happened after the signal"
- Paper trading: "how execution performed"
- Data center: "whether data is reliable"
- Backtest center: "whether the strategy should be kept"

Each entry now defines:

- core user question
- first-screen conclusion
- primary sections
- detail sections
- empty-state fallback
- feature-flag fallback
- required heavy-list surface (`DataTable` / `VirtualCardList`)

The global command palette now reads hints for these pages from the same
responsibility map, reducing duplicated wording drift.

## Layout Cleanup

`PaperTradingSummaryBar` no longer renders metric cards inside an outer AntD
Card. Its metrics use flat `.paper-summary-metric` tiles instead. This keeps the
legacy paper summary component aligned with the Phase 6 rule against nested
cards while preserving the existing metric values and tones.

## Non-Changes

This phase intentionally does not:

- redesign all monitor / strategy / paper / data / backtest pages
- move or remove existing business information
- change any API response or generated OpenAPI type
- change any feature flag default
- change `strategy_policy`
- change `production_score`, `priority_score`, `buy_signal_state`, or ranking
- change paper-trading order, fill, risk, or account semantics
- deploy the application

## Added Tests

New tests:

- `frontend/src/features/trading-workspace/pageResponsibilities.test.ts`
  - guards the five-page responsibility map
  - requires empty-state and feature-flag fallback text
  - confirms heavy lists are assigned to `DataTable` / `VirtualCardList`
- `frontend/src/features/paper/PaperTradingSummaryBar.test.tsx`
  - guards that the summary component uses flat metric tiles instead of nested
    AntD cards

## Validation Commands

Required targeted frontend validation:

```bash
cd frontend
npm test -- pageResponsibilities PaperTradingSummaryBar
npm run typecheck
npm run lint
npm run api:check
```

Actual result:

```text
npm test -- pageResponsibilities PaperTradingSummaryBar: 2 files / 4 tests passed
npm run typecheck: passed
npm run lint: passed
npm run api:check: passed, OpenAPI hash unchanged
npm test -- --run: 63 files / 183 tests passed
npm run build: passed
```

## Phase 6 Verdict

Phase 6 is accepted as a frontend information-denoising baseline:

- Page responsibilities are centralized and test-covered.
- Empty / feature-flag fallback expectations are explicit.
- Heavy-list surface expectations are explicit.
- A known paper-summary nested-card pattern is removed.
- Full page redesign remains out of scope for this phase and can proceed
  incrementally against the new responsibility map.

No deployment was performed.
