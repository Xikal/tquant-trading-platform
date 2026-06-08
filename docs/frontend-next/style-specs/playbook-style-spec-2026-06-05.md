# Playbook Web Style Spec - 2026-06-05

## Binding Image

- Web style image: `docs/frontend-next/style-specs/images/playbook-web.png`
- Current route: `/playbook` (`/low-buy` remains a legacy alias)
- New `frontend-next` route: `/playbook`
- Approved Web viewport: `1440x900`

## Source Anchors

- Plan: `docs/frontend-next-solid-parallel-development-plan-2026-06-05.md`
- Tokens/CSS: `frontend/src/styles/foundation/tokens.css`, `frontend/src/styles/workspace/workspace.css`, `frontend/src/styles/workspace/workspace-ritual.css`
- Page/component sources: `frontend/src/features/playbook/PlaybookPage.tsx`, `frontend/src/features/workspace-shared/WorkspacePageIntro.tsx`, `WorkspaceComponents.tsx`, `frontend/src/ui/list/VirtualCardList.tsx`, `frontend/src/features/ritual-ui/*`

## Visible Section Order

1. Fixed sidebar, sticky topbar, and inline `PagePriorityStrip`.
2. Hero panel with "选股宝典", strategy summary, refresh action, status pills.
3. Ritual compact strip and strategy tab buttons under hero.
4. Metrics grid for samples, hit rate, average return, drawdown.
5. Left column "最近表现".
6. Left column dark "今日主看".
7. Right column candidate tabs panel.
8. Candidate tab body with dense virtual list rows and row actions.

## Density Rules

- Use `.tq-playbook-page`: grid gap `6px`, columns `minmax(300px, 380px) minmax(0, 1fr)`.
- Areas stay: hero full width, performance/focus left, candidates right.
- Metrics grid is compact, forced to 3 columns with `--sp-1` gap.
- Candidate tab body max height `min(52vh, 520px)` and own vertical scroll.
- Dense candidate row grid: name, action details, score/risk, seal, actions; 5-6px padding.

## Color Token Mapping

- Standard panels use workspace light tokens.
- "今日主看" stays dark with `--brand-ink`, light text, and subtle brand outline.
- Ritual components keep current approved colors from `workspace-ritual.css`; no expansion into new theme.
- Candidate status tones use existing up/warn/down/neutral mapping.

## Typography And Spacing

- Page root is `--fs-micro`, line-height `1.32`.
- Dense rows use single-line ellipsis for name/details.
- Strategy tabs use small Ant buttons.
- Dark focus panel copy remains compact and readable, not hero-scale.

## Component Inventory

- `WorkspacePageIntro`
- `RitualFortuneStrip`, `RitualLuckyDraw`, `RitualSignalSeal`
- `MetricGrid`
- `PanelTitle`, `Callout`, `InfoPill`, `EmptyState`
- `Tabs`
- `VirtualCardList`
- Dense candidate row buttons: "详情", "分析".

## Web Layout Behavior

- Candidate tabs own the main scroll region and must not push the left performance/focus panels out of first screen.
- The active candidate section defaults to the first non-empty section.
- `/low-buy` may route to this page but implementation reference is `/playbook`.
- Page priority strip is present above hero.
- Strategy tab changes may refetch data but visual shell remains stable.

## Visual Non-Goals

- Do not create a new discovery/marketplace design.
- Do not turn ritual elements into page-dominant decoration.
- Do not show research-only strategies as production buy rows unless current data says so.
- Do not replace dense rows with oversized stock cards.

## Screenshot Parity Checklist

- [ ] `1440x900` screenshot shows hero, metrics, left performance/focus, and right candidate tabs.
- [ ] Candidate list is dense and scroll-contained.
- [ ] Dark "今日主看" panel uses current `--brand-ink` styling.
- [ ] Ritual strip remains compact and secondary.
- [ ] `/playbook` visual matches old Web route density.
