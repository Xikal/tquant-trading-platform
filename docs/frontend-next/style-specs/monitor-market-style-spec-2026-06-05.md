# Monitor Market Web Style Spec - 2026-06-05

## Binding Image

- Web style image: `docs/frontend-next/style-specs/images/monitor-market-web.png`
- Current route: `/monitor/market`
- New `frontend-next` route: `/monitor/market`
- Approved Web viewport: `1440x900`

## Source Anchors

- Plan: `docs/frontend-next-solid-parallel-development-plan-2026-06-05.md`
- Tokens: `frontend/src/styles/foundation/tokens.css`
- Workspace shell: `frontend/src/features/trading-workspace/TradingWorkspaceChrome.tsx`, `frontend/src/features/trading-workspace/workspaceShellStyles.ts`
- Page/component sources: `frontend/src/features/monitor/MonitorMarketPage.tsx`, `frontend/src/features/monitor/MonitorSharedPanels.tsx`, `frontend/src/features/monitor/MarketStateGatePanel.tsx`, `frontend/src/features/monitor/SectorLeaderGatePanel.tsx`, `frontend/src/features/monitor/InstrumentSyncProgress.tsx`

## Visible Section Order

1. Fixed dark sidebar and sticky topbar.
2. Full-width "市场总闸 / 数据质量" gate panel.
3. Inline market quality pills: market state, data status, breadth, pulse, ETF opportunity.
4. Two-column market main grid.
5. "市场宽度与日内脉冲" card with breadth strip, hourly pulse, and market key levels.
6. "板块轮动与龙头确认" card.
7. ETF T0 / paired hedge panel.
8. Monitor review panel.
9. "运行时 / 同步状态" card with summary and instrument sync progress.

## Density Rules

- Use `.monitor-market-page`: grid gap `12px`.
- Wide layout uses `.monitor-market-page--wide .monitor-market-main`: `repeat(2, minmax(0, 1fr))`, gap `12px`.
- All cards stay `size="small"` compatible: 34px header, 8px body, dense 12-13px copy.
- Gate panel and market cards must set `min-width: 0` and avoid horizontal overflow.
- Info pills remain compact with 5-8px padding and 6px radius.

## Color Token Mapping

- Page background `--bg-base`; card background `--bg-elevated`; subtle rows `--bg-subtle`.
- Border `--border` / `--line`; text `--text-1`, `--text-2`, `--text-3`.
- Market pass/reduce/block states use current success/warning/error tokens only.
- Market up/down ratios use `--mkt-up` and `--mkt-down` only for data values.
- No additional palette beyond existing tokens.

## Typography And Spacing

- Body and card copy: `--font-body`/`--fs-micro` 12-13px.
- Section labels use current `PanelTitle`/Ant small-card title scale.
- Numeric market fields use tabular numerals.
- Grid rhythm uses `8px` and `12px`; no large marketing spacing.

## Component Inventory

- `MarketStateGatePanel`
- `InfoPill`, `Callout`, `PanelTitle`
- `MarketBreadthStrip`, `HourlyAllMarketPulse`
- `KeyLevelPanel`
- `SectorLeaderGatePanel`
- `MonitorEtfT0Panel`
- `MonitorReviewPanel`
- `MonitorMarketSummaryPanel`
- `InstrumentSyncProgress`

## Web Layout Behavior

- The top gate panel stays first and full width.
- Below `xl`, the two-column market grid stacks to one column; Web reference is the wide desktop version.
- Long review or sync details scroll within their panel body if needed; the page may scroll vertically.
- Empty/degraded market context keeps the same structure and shows the current warning callout.
- No priority strip appears on this route.

## Visual Non-Goals

- Do not merge the market page back into the action desk.
- Do not invent new macro dashboard visuals or oversized chart modules.
- Do not add dark cards except where the old component already uses dark chart surfaces.
- Do not change market gate semantics or data quality wording.

## Screenshot Parity Checklist

- [ ] `1440x900` screenshot shows the gate panel first and the two-column market grid below.
- [ ] Compact card headers, body spacing, and info pill density match the old page.
- [ ] Market up/down/status colors use existing semantic tokens.
- [ ] Runtime/sync panel remains visible in the first-screen structure.
- [ ] No horizontal overflow or new decorative backgrounds are present.
