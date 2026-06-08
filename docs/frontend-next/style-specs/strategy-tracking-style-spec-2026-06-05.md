# Strategy Tracking Web Style Spec - 2026-06-05

## Binding Image

- Web style image: `docs/frontend-next/style-specs/images/strategy-tracking-web.png`
- Current route: `/strategy-tracking`
- New `frontend-next` route: `/strategy-tracking`
- Approved Web viewport: `1440x900`

## Source Anchors

- Plan: `docs/frontend-next-solid-parallel-development-plan-2026-06-05.md`
- Tokens: `frontend/src/styles/foundation/tokens.css`
- Workspace CSS: `frontend/src/styles/workspace/workspace-strategy-tracking.css`
- Page/component sources: `frontend/src/features/strategy-tracking/StrategyTrackingPage.tsx`, `StrategyTrackingConclusionBar.tsx`, `StrategyTrackingModeToggle.tsx`, `StrategyTrackingTable.tsx`, `StrategyTrackingFilters.tsx`, `StrategyReviewWorkspacePanel.tsx`, `StrategyTrackingDetailDrawer.tsx`

## Visible Section Order

1. Fixed sidebar and sticky topbar.
2. `StrategyTrackingConclusionBar`; if data is missing, fallback hero with title "策略跟踪".
3. Filter panel with mode toggle and "筛选条件" button.
4. Alert stack for stale/missing/board filter/partial errors.
5. Main signal list panel with section head and segmented control: "跟踪复盘", "涨幅", "风险".
6. Dense virtual/table signal list.
7. Secondary panel with analysis tabs: diagnostics, holding, drift, promotion/review workspace when flags allow.
8. Detail drawer and filters drawer are off-canvas and not visible in baseline image.

## Density Rules

- Page root `.strategy-tracking-page` is grid gap `8px`.
- Filter panel padding `8px`; toolbar gap `8px`.
- Top summary grid uses compact stat tiles; conclusion compact variant uses `7px 8px` tiles.
- Main table/list must keep compact row height and nowrap numeric cells.
- Secondary tabs use Ant `size="small"` and `8px` navigation spacing.

## Color Token Mapping

- Background/surfaces/borders use `--bg-base`, `--bg-elevated`, `--bg-subtle`, `--border`.
- Text uses `--text-1`, `--text-2`, `--text-3`.
- Brand filters and active states use `--brand` and `--brand-soft`.
- Strategy outcome/status tones use existing success/warning/error and market tokens only.

## Typography And Spacing

- Title fallback is 18px from `--font-title`; regular panel labels are 12-14px.
- Active filter text and helper descriptions use `--font-meta` 12px.
- Table cells and metric values use tabular numerals.
- Use 4px/6px/8px increments already present in `workspace-strategy-tracking.css`.

## Component Inventory

- `StrategyTrackingConclusionBar`
- `StrategyTrackingModeToggle`
- `StrategyTrackingFilters`
- `StrategyTrackingTable`
- `StrategyTrackingPerformanceTable`
- `StrategyTrackingReviewPanel`
- `StrategyTrackingDiagnosticsPanel`
- `StrategyTrackingHoldingAnalysisPanel`
- `DriftMonitorPanel`
- `PromotionReviewPanel`
- `StrategyReviewWorkspacePanel`
- `StrategyTrackingDetailDrawer`

## Web Layout Behavior

- This route does not show the inline `PagePriorityStrip`.
- Filters drawer opens from the side; it must not reserve layout space in baseline.
- Main list and secondary panel should remain vertically stacked, not side-by-side, to preserve current information order.
- Stale/missing alerts appear between filters and main list without layout shift elsewhere.
- Production and observation semantics stay explicit; observation rows must not look like confirmed buy actions.

## Visual Non-Goals

- Do not convert this page into a card board or new Kanban surface.
- Do not hide warnings/partial errors in icons only.
- Do not add new scoring colors or reorder server-provided result rows.
- Do not broaden the route into paper/backtest controls.

## Screenshot Parity Checklist

- [ ] `1440x900` screenshot shows conclusion, filters, main list, and secondary analysis tabs in this order.
- [ ] Dense 8px spacing and compact typography match old CSS.
- [ ] Segmented control and filter button retain Ant small control hierarchy.
- [ ] Status and market tones use only current tokens.
- [ ] Drawers are absent from baseline but documented for interactions.
