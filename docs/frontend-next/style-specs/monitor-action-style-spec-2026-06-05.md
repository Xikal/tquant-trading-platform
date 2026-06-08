# Monitor Action Web Style Spec - 2026-06-05

## Binding Image

- Web style image: `docs/frontend-next/style-specs/images/monitor-action-web.png`
- Current route: `/monitor`
- New `frontend-next` route: `/monitor`
- Approved Web viewport: `1440x900`

## Source Anchors

- Plan: `docs/frontend-next-solid-parallel-development-plan-2026-06-05.md`
- Tokens: `frontend/src/styles/foundation/tokens.css`
- Workspace shell: `frontend/src/features/trading-workspace/TradingWorkspaceChrome.tsx`, `frontend/src/features/trading-workspace/workspaceShellStyles.ts`
- Page/component sources: `frontend/src/features/monitor/MonitorActionPage.tsx`, `frontend/src/features/monitor/MonitorConclusionBar.tsx`, `frontend/src/features/monitor/MonitorPage.panels.tsx`, `frontend/src/features/workspace-shared/WorkspaceComponents.tsx`, `frontend/src/features/workspace-shared/StockCard.tsx`, `frontend/src/ui/list/VirtualCardList.tsx`

## Visible Section Order

1. Fixed dark left sidebar and sticky light topbar from the current workspace shell.
2. Status strip only when notice text exists.
3. Monitor conclusion bar across the first row.
4. Key-level alerts and "个股关键位观察" under the conclusion summary.
5. Main two-column action region: production priority board on the left, holdings input/watchlist on the right.
6. Priority board local controls: title/actions, strategy lane tabs, lane status card, context info pills, market gate, risk badges, notices, family strip.
7. Virtualized priority stock-card list with first-screen scroll boundary.
8. Holdings panel with "我的持仓", primary callout, and virtualized watch-card list.
9. Holding entry drawer is off-canvas and not visible in the baseline image.

## Density Rules

- Preserve `monitorGridStyle(false)`: `minmax(0, 1fr) minmax(360px, 440px)`, areas `"summary summary"`, `"priority input"`, `"etf etf"`, gap `clamp(12px, 1vw, 16px)`.
- Panels use `.panel`: 1px `--line`, 8px radius, `--card`, `clamp(8px, 0.85vw, 12px)` padding, small shadow.
- Priority/watch lists use `VirtualCardList` with `estimateSize` about `164-170`, `maxHeight` `620`, and `8px` row gap.
- Stock cards preserve compact A-share density: 7-9px padding, 6px internal gaps, pill badges, operation grid, tabular numeric quote fields.
- Ant small card/header density must remain: 34px min header, 8px body padding, tabs bottom margin 8px.

## Color Token Mapping

- Page background: `--bg-base #f4f6fa`.
- Panel/card surface: `--bg-elevated #ffffff`; secondary fills: `--bg-subtle #eef1f6`.
- Border: `--border #e2e8f0` / legacy `--line`.
- Primary text: `--text-1 #0f1b2d`; secondary: `--text-2 #5a6a7e`; tertiary: `--text-3 #94a3b8`.
- Sidebar/mini chart dark surface: `--brand-ink #0b1f3a`.
- Primary action: `--brand #2563eb`; gold board action: `--accent-gold #c8922f`.
- Market data only: up `--mkt-up #c62828`, down `--mkt-down #1f8b4c`, flat `--mkt-flat #5a6a7e`.

## Typography And Spacing

- Font family follows root token: `"IBM Plex Sans", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif`.
- Page/body text is dense: 12-14px, line-height `1.3-1.5`; no hero-scale type.
- Section title hierarchy uses current `PanelTitle`/`SectionHeader`: `13-16px`, 600-700 weight.
- Quote/code-like identifiers use tabular numerals and monospace where current card metadata does.
- Spacing follows 4px grid tokens `--sp-1` to `--sp-5`; avoid freeform large gaps.

## Component Inventory

- Workspace shell: `AppSidebar`, `Topbar`, `StatusStrip`, dialogs.
- Monitor primitives: `MonitorConclusionBar`, `KeyLevelAlerts`, `KeyLevelPanel`, `MarketStateGatePanel`, `RiskFilterBadges`, `FamilyStrip`.
- Shared primitives: `PanelTitle`, `Callout`, `ContextRow`, `InfoPill`, `EmptyState`.
- Lists/cards: `VirtualCardList`, `MonitorPriorityStockCard`, `MonitorWatchStockCard`, `StockCard`-compatible rows.
- Controls: small Ant buttons, strategy lane tabs, holding entry drawer.

## Web Layout Behavior

- Left sidebar is fixed at `220px` expanded or `64px` collapsed; desktop content column starts after the sidebar.
- Topbar is sticky at the top with 56px height and light surface.
- Inner content max width is 1440px and centered.
- The priority and holdings lists scroll inside their own virtualized list regions; page-level overflow must not create horizontal scroll.
- Priority board order is server-owned; client workers may not reorder production priority cards.
- New symbols may use the existing subtle enter animation, honoring `prefers-reduced-motion`.

## Visual Non-Goals

- No new trading theme, gradients, decorative illustrations, or third-party default component skin.
- Do not replace stock cards with generic tables.
- Do not change production board sorting, score wording, market gate semantics, or risk copy hierarchy.
- Do not add mobile layout requirements in this phase.

## Screenshot Parity Checklist

- [ ] `1440x900` screenshot includes fixed sidebar, sticky topbar, summary row, priority board, and holdings panel.
- [ ] Colors match current tokens, especially `--brand-ink`, `--bg-base`, `--bg-elevated`, and market red/green.
- [ ] Priority and watch cards keep current padding, badge density, and tabular numeric alignment.
- [ ] List scroll boundaries match `maxHeight` and do not stretch the page horizontally.
- [ ] All visible copy hierarchy matches the old route labels: "实时行动台", "生产优先榜", "我的持仓".
