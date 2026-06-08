# Backtest Web Style Spec - 2026-06-05

## Binding Image

- Web style image: `docs/frontend-next/style-specs/images/backtest-web.png`
- Current route: `/backtest`
- New `frontend-next` route: `/backtest`
- Approved Web viewport: `1440x900`

## Source Anchors

- Plan: `docs/frontend-next-solid-parallel-development-plan-2026-06-05.md`
- Tokens/CSS: `frontend/src/styles/foundation/tokens.css`, `frontend/src/styles/workspace/workspace.css`, `frontend/src/styles/workspace/workspace-backtest.css`
- Page/component sources: `frontend/src/features/backtest/BacktestPage.tsx`, `BacktestDashboard.tsx`, `backtestPageLayoutStyles.ts`, `BacktestSubmitPanel.tsx`, `BacktestDashboard.panels.tsx`, `BacktestResearchPanel.tsx`, `ComparePanel.tsx`, `AttributionPanel.tsx`

## Visible Section Order

1. Fixed sidebar and sticky topbar.
2. Compact dark backtest hero/header: title "回测页", task summary, metric pills, status legend rail.
3. Small tabs: "提交任务", "结果概览", "成交明细", "ETF T0", "研究闭环".
4. Default submit tab body: left submit/config panel, right run list panel.
5. Result overview tab alternative: run detail panel and equity chart.
6. Trades/research tabs use dense tables and chart panels but are not first visible in baseline.

## Density Rules

- Backtest page grid gap `8px`, font size `12`, line-height `1.32`.
- Hero grid uses desktop columns `minmax(150px, 220px) minmax(0, 1fr) minmax(120px, 180px)`.
- Submit tab desktop grid uses `minmax(280px, 360px) minmax(0, 1fr)`.
- Overview tab desktop grid uses `minmax(280px, 0.88fr) minmax(360px, 1.12fr)`.
- Backtest tables keep nowrap cells and hidden wrapper overflow.

## Color Token Mapping

- Page background remains `--bg-base`.
- Hero uses existing dark gradient from `backtestHeroStyle`: rgba(11,20,34) to rgba(17,27,45), cyan border, gold inset.
- Header pills use translucent white on dark with slate labels.
- Body panels use current light workspace surfaces.
- Backtest status labels use `STATUS_META` tone mapping through existing style helpers.

## Typography And Spacing

- Hero title is 13px bold; summary is 12px.
- Backtest kicker/labels use compact uppercase/monospace where current styles do.
- Inputs and date fields must keep minimum width handling from `.backtest-page`.
- No enlarged report typography in task forms or tables.

## Component Inventory

- `BacktestDashboard`
- `BacktestSubmitPanel`
- `RunListPanel`
- `RunDetailPanel`
- `EquityPanel`
- `TradesPanel`
- `BacktestResearchPanel`
- `BacktestResearchTabs`
- `ComparePanel`
- `AttributionPanel`
- Status legend rail and header pills.

## Web Layout Behavior

- Default active tab is "提交任务" unless a selected run causes "结果概览"; style must support both without changing shell.
- Long run lists and tables scroll inside panels/table wrappers.
- Research/optimization forms remain behind their tabs and must not crowd the first screen.
- This route does not show inline `PagePriorityStrip`.
- Heavy backtest computation remains Worker/server-side; frontend style must not imply client-only compute.

## Visual Non-Goals

- Do not redesign the backtest header into a full analytics hero.
- Do not introduce new chart palettes beyond existing backtest chart theme.
- Do not add production-promotion affordances outside current governance controls.
- Do not increase form density into unreadable sub-10px text.

## Screenshot Parity Checklist

- [ ] `1440x900` screenshot shows dark compact header and small tabs.
- [ ] Submit tab has left form/config and right run list.
- [ ] Header colors match `backtestHeroStyle`.
- [ ] Tables/forms stay dense without horizontal page overflow.
- [ ] Status legend remains compact and secondary.
