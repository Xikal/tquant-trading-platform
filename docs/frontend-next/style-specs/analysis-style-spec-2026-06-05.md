# Analysis Web Style Spec - 2026-06-05

## Binding Image

- Web style image: `docs/frontend-next/style-specs/images/analysis-web.png`
- Current route: `/analysis`
- New `frontend-next` route: `/analysis`
- Approved Web viewport: `1440x900`

## Source Anchors

- Plan: `docs/frontend-next-solid-parallel-development-plan-2026-06-05.md`
- Tokens/CSS: `frontend/src/styles/foundation/tokens.css`, `frontend/src/styles/workspace/workspace.css`
- Page/component sources: `frontend/src/features/analysis/AnalysisPage.tsx`, `frontend/src/features/workspace-shared/WorkspacePageIntro.tsx`, `WorkspaceComponents.tsx`, `MiniKlineChart.tsx`, `frontend/src/features/key-levels/KeyLevelPanel.tsx`

## Visible Section Order

1. Fixed sidebar, sticky topbar, then inline `PagePriorityStrip`.
2. Hero panel with "量化分析", direct decision summary, action button, and pills.
3. Two-column decision/control row: current recommendation on the left, input controls on the right.
4. Identity/metrics panel and batch-analysis panel.
5. Full-width "分析关键位观察".
6. Full-width "K线与指标" with chart metadata, dark mini-kline, and context pills.
7. Full-width execution-plan collapse.
8. Anomaly panel appears after key levels when anomaly data exists.

## Density Rules

- Use `.tq-analysis-page`: two columns `minmax(0, 1fr) minmax(300px, 340px)`, gap `--sp-2`.
- Grid areas stay: hero, decision/control, identity/batch, key-levels, chart, plan, anomaly.
- Control grid uses 3 columns for numeric fields; search spans full width.
- Batch list uses 6px gap and 7px item padding.
- Mini-kline height remains about 210px with dark `--brand-ink` surface.

## Color Token Mapping

- Page/panels use standard workspace tokens.
- Decision/action tone maps to `up`, `warn`, `neutral` using market/success/warning tokens from existing components.
- Mini-kline surface uses `--brand-ink`; chart metadata uses `--text-3`.
- Inputs retain current Ant/input styling through compatibility wrappers.

## Typography And Spacing

- Page root uses `--fs-micro` and line-height `1.35`.
- Hero title remains compact through `WorkspacePageIntro`; do not use marketing hero type.
- Chart metadata uses `"IBM Plex Mono", monospace`, `--fs-micro`, and 16px horizontal gaps.
- Copy stays plain trading wording: "当前可以", "当前先不下单", "模拟下单".

## Component Inventory

- `WorkspacePageIntro`
- `SearchField`, `NumberField`, `SelectField`, `TextField`
- `PanelTitle`, `InfoPill`, `MetricGrid`, `ContextRow`, `LineList`, `Callout`
- `StockIdentity`
- `KeyLevelPanel`
- `MiniKline`
- Ant `Collapse` for execution plan.

## Web Layout Behavior

- Right control column is fixed-width-ish and stays aligned with the decision panel on desktop.
- Long decision text may wrap inside `InfoPill`; it must not overflow horizontally.
- Chart and plan sections span the full content width below the first two rows.
- Batch results show at most the top visible candidates in the first screen, preserving scroll below.
- The route may open paper order modal from action, but modal is not part of baseline image.

## Visual Non-Goals

- Do not make analysis look like a consumer search landing page.
- Do not add new chart style, candlestick palette, or AI illustration.
- Do not remove priority strip for this page.
- Do not change trading decision wording or risk hierarchy.

## Screenshot Parity Checklist

- [ ] `1440x900` screenshot shows priority strip, hero, decision/control row, identity/batch row, key levels, and chart.
- [ ] Two-column analysis grid matches old desktop proportions.
- [ ] Dark mini-kline uses current `--brand-ink` treatment.
- [ ] Form/control density remains 12-14px with 6-8px gaps.
- [ ] Text hierarchy stays direct and trading-focused.
