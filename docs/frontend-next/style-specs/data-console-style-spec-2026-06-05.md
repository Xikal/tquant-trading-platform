# Data Console Web Style Spec - 2026-06-05

## Binding Image

- Web style image: `docs/frontend-next/style-specs/images/data-console-web.png`
- Current route: `/data`
- New `frontend-next` route: `/data`
- Approved Web viewport: `1440x900`

## Source Anchors

- Plan: `docs/frontend-next-solid-parallel-development-plan-2026-06-05.md`
- Tokens/CSS: `frontend/src/styles/foundation/tokens.css`, `frontend/src/features/data-console/DataConsolePage.module.css`
- Page/component sources: `frontend/src/features/data-console/DataConsolePage.tsx`, `DataHealthOverview.tsx`, `TradeDataGateCard.tsx`, `RuntimeFallbackPanel.tsx`, `DataSourceHealthPanel.tsx`, `CoveragePanel.tsx`, `WorkerObservabilityPanel.tsx`, `CollectionJobsPanel.tsx`, `DataRepairPanel.tsx`, `InstrumentInspectorPanel.tsx`, `frontend/src/features/settings/EtfUniverseAdminCard.tsx`

## Visible Section Order

1. Fixed sidebar and sticky topbar.
2. Admin-only page; non-admin state shows a single warning panel.
3. "今日数据能不能用" full-width panel.
4. Conclusion grid: "今日数据状态" left, "能否用于交易" and "后台兜底状态" on the right/second column structure.
5. "日常巡检" full-width panel.
6. Two-column grid: "数据来源是否正常" and "数据完整度".
7. "数据维护" panel with "后台任务观测".
8. Management token gate.
9. Collapsed maintenance accordions: data jobs, repair, instrument inspector, ETF/stock pool.

## Density Rules

- Root `.page` grid gap `--sp-3` and no horizontal overflow.
- `.conclusionGrid` desktop columns `minmax(0, 1.15fr) minmax(0, 0.85fr)`.
- `.grid` desktop columns `repeat(2, minmax(0, 1fr))`.
- Section internals use `--sp-2`/`--sp-3` gaps.
- Maintenance gate uses `minmax(0, 1fr) minmax(220px, 320px)` and 1px border.

## Color Token Mapping

- Standard workspace tokens only: `--bg-base`, `--bg-elevated`, `--bg-subtle`, `--border`, `--text-1`, `--text-2`.
- Status text uses `--success`, `--warning`, `--error`.
- Confirmation/warning blocks use current color-mix with `--warning`.
- No custom data-console palette beyond these tokens.

## Typography And Spacing

- Section `h3` uses current small body size and tight line-height.
- Details, muted text, empty states use `--fs-micro` with `--lh-base`.
- Numeric fields use tabular alignment and right alignment where current CSS applies.
- Copy must stay direct: "今日数据能不能用", "能否用于交易", "后台兜底状态".

## Component Inventory

- `Panel`
- `Alert`
- `DataHealthOverview`
- `TradeDataGateCard`
- `RuntimeFallbackPanel`
- `DataSourceHealthPanel`
- `CoveragePanel`
- `WorkerObservabilityPanel`
- `CollectionJobsPanel`
- `DataRepairPanel`
- `InstrumentInspectorPanel`
- `EtfUniverseAdminCard`
- Ant `Collapse`, `Input.Password`.

## Web Layout Behavior

- This route does not show inline `PagePriorityStrip`.
- Admin token gate controls only maintenance actions; read-only status sections remain visible.
- Accordions default collapsed as in old page.
- Below 1199px conclusion and patrol grids stack; Web reference is desktop wide.
- No background polling controls or backend loops may be introduced by style work.

## Visual Non-Goals

- Do not change backend contracts or add new data maintenance flows.
- Do not hide blocked/stale states behind icons.
- Do not redesign the page into a generic admin console.
- Do not add charts unless already present in current panels.

## Screenshot Parity Checklist

- [ ] `1440x900` screenshot shows the three main panels in order.
- [ ] Conclusion and patrol grids use current two-column desktop layout.
- [ ] Maintenance token gate and collapsed accordions are visible.
- [ ] Status colors match success/warning/error tokens.
- [ ] Page remains dense and no horizontal overflow appears.
