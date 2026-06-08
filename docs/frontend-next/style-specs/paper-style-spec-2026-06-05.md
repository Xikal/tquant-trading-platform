# Paper Trading Web Style Spec - 2026-06-05

## Binding Image

- Web style image: `docs/frontend-next/style-specs/images/paper-web.png`
- Current route: `/paper`
- New `frontend-next` route: `/next/paper`
- Approved Web viewport: `1440x900`

Binding note: `paper-web.png` is the authenticated legacy `/paper` screenshot captured by `START_LEGACY_FRONTEND=1 npm run screenshot:parity`; it includes the old mecha avatar/HUD/effects and supersedes the earlier simplified placeholder style image.

## Source Anchors

- Plan: `docs/frontend-next-solid-parallel-development-plan-2026-06-05.md`
- Tokens: `frontend/src/styles/foundation/tokens.css`
- Workspace CSS: `frontend/src/styles/workspace/workspace-paper.css`, `frontend/src/styles/workspace/workspace-paper-mecha.css`
- Page/component sources: `frontend/src/features/paper/PaperTradingPage.tsx`, `frontend/src/features/paper/PaperConclusionBar.tsx`, `frontend/src/features/paper/PaperMechaActionPanel.tsx`, `frontend/src/features/paper/PaperTodayActionPanel.tsx`, `frontend/src/features/paper/PaperTradingSections.tsx`, `frontend/src/features/paper/PaperDetailTabs.tsx`

## Visible Section Order

1. Fixed sidebar and sticky topbar.
2. Hero grid: left `PaperConclusionBar`, right `PaperMechaActionPanel`.
3. Embedded positions inside the conclusion surface.
4. Paper mecha display-only avatar/action HUD.
5. Dark execution console/log area inside the HUD.
6. Optional trading-experience panels: "持仓纪律" and "T 归因" below hero when flags are on.
7. `PaperDetailTabs` containing positions, orders, trades, performance, risk, runs, and ledger repair.
8. Order modal is not visible in the baseline image.

## Density Rules

- Page stack uses vertical `Space` gap `8px`, `fontSize: 12`, line-height `1.32`.
- Hero grid uses Ant `Row` gutter `[8, 8]`; desktop split is `xl=16/8`.
- `paper-conclusion` uses 10px radius, 6px padding, white surface, and existing 0 10 26 shadow.
- Embedded positions use 6 columns on desktop, 5px gap, 6-7px card padding.
- HUD uses 12px radius, 14px padding, console min-height about 228px.
- Detail tabs and tables must stay dense; mobile card fallback is out of scope for this Web spec.

## Color Token Mapping

- Normal panels use `--bg-elevated`, `--border`, `--text-1`, `--text-2`.
- Summary tiles use `rgb(248 250 252)` and `rgb(226 232 240)` as in `workspace-paper.css`.
- HUD console uses `rgba(2, 6, 23, 0.9)` with slate/cyan/green/red log tokens from the old CSS.
- Paper mecha highlight colors stay current orange/red/green/cyan values from `workspace-paper.css`.
- Market up/down values keep `--mkt-up` and `--mkt-down`.

## Typography And Spacing

- Paper page copy is mostly 10-13px.
- HUD title uses monospace, uppercase, 12px, 0.05em letter spacing as currently defined.
- Console log text uses monospace 10px.
- Account and PnL values use tabular numeric alignment.

## Component Inventory

- `PaperConclusionBar`
- `PaperPositionsPanel` embedded mode
- `PaperMechaActionPanel`
- `PaperMechaAvatar`
- `PaperTodayActionPanel`
- `HoldingDisciplinePanel`
- `TTradeAttributionPanel`
- `PaperDetailTabs`
- `OrderEntryModal`
- Ledger repair and review-history panels inside tabs.

## Web Layout Behavior

- Left conclusion surface and right mecha HUD align to equal hero height.
- The paper mecha and execution log are display-only; they must not become autonomous trading controls.
- Detail tabs own the lower scroll work; tables and long lists must not create page-level horizontal overflow.
- If optional trading-experience flags are off, the detail tabs move directly under the hero grid without leaving a visual hole.
- Keep current "只提醒/模拟" boundary in copy hierarchy; no live order/autotrade affordance may be introduced by style work.

## Visual Non-Goals

- Do not redesign the mecha avatar or replace it with new generated art.
- Do not add casino/game styling beyond the existing paper mecha treatment.
- Do not increase card radius or whitespace beyond current dense dashboard values.
- Do not introduce live trading CTAs or automatic execution wording.

## Screenshot Parity Checklist

- [x] `1440x900` screenshot shows the conclusion panel and mecha HUD side by side.
- [x] Embedded positions are visible in the conclusion surface.
- [x] HUD console uses the old dark execution-log treatment.
- [x] Detail tabs start below the hero with dense table/list structure.
- [x] All colors are sourced from current paper/workspace CSS.
