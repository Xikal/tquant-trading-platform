# Frontend Next Legacy UI Architecture Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `frontend-next/` UI/DOM architecture with the old `frontend/` workspace UI architecture while keeping the SolidJS/TanStack/Worker/Charts technical foundation.

**Architecture:** `frontend/` remains read-only and production-capable. `frontend-next/` keeps its current data/API/runtime stack, but adopts a legacy-compatible shell, shared UI DOM contract, style adapter, and page region structure so old workspace CSS and screenshots are meaningful parity references.

**Tech Stack:** SolidJS, TypeScript, Vite, TanStack Router/Query/Table/Virtual, Solid signals, Web Workers, Lightweight Charts, local CSS copied from the current React frontend.

---

## File Structure

Create:

- `frontend-next/src/legacy-shell/LegacyAppShell.tsx`
- `frontend-next/src/legacy-shell/LegacySidebar.tsx`
- `frontend-next/src/legacy-shell/LegacyTopbar.tsx`
- `frontend-next/src/legacy-shell/LegacyPageContent.tsx`
- `frontend-next/src/legacy-shell/legacyNavConfig.ts`
- `frontend-next/src/legacy-shell/legacyShellStyles.ts`
- `frontend-next/src/legacy-shell/legacyShell.test.tsx`
- `frontend-next/src/shared/styles/legacy-solid-adapter.css`

Modify:

- `frontend-next/src/app/AppShell.tsx`
- `frontend-next/src/app/routeTree.tsx`
- `frontend-next/src/index.tsx`
- `frontend-next/src/shared/ui/Button.tsx`
- `frontend-next/src/shared/ui/Panel.tsx`
- `frontend-next/src/shared/ui/Tabs.tsx`
- `frontend-next/src/shared/ui/Segmented.tsx`
- `frontend-next/src/shared/ui/DataTable.tsx`
- `frontend-next/src/shared/ui/MetricGrid.tsx`
- `frontend-next/src/shared/ui/StockCard.tsx`
- `frontend-next/src/shared/ui/EmptyState.tsx`
- `frontend-next/src/features/shared/PageScaffold.tsx`
- `frontend-next/src/features/monitor-action/MonitorActionPage.tsx`
- `frontend-next/src/features/paper/PaperPage.tsx`
- Other page files only after pilot page screenshot parity passes.

Read-only references:

- `frontend/src/features/trading-workspace/TradingWorkspaceChrome.tsx`
- `frontend/src/features/trading-workspace/AppSidebar.tsx`
- `frontend/src/features/trading-workspace/Topbar.tsx`
- `frontend/src/features/trading-workspace/workspaceShellStyles.ts`
- `frontend/src/features/workspace-shared/StockCard.tsx`
- `frontend/src/ui/surfaces/Panel.tsx`
- `frontend/src/ui/table/DataTable.tsx`
- `frontend/src/styles/workspace/*.css`

---

### Task 0: Baseline Guard

**Files:**
- Read: `/Users/j/Documents/gupiao/AGENTS.md`
- Read: `/Users/j/Documents/gupiao/docs/engineering-conventions.md`
- Read: `/Users/j/Documents/gupiao/docs/frontend-next-legacy-ui-architecture-migration-development-doc-2026-06-06.md`
- Read: `/Users/j/Documents/gupiao/docs/frontend-next/style-specs/*.md`

- [ ] **Step 1: Capture initial status**

Run:

```bash
cd /Users/j/Documents/gupiao
git status --short
```

Expected: old `frontend/src/features/trading-workspace/TradingWorkspaceChrome.test.ts` may already be dirty; do not edit or revert it.

- [ ] **Step 2: Capture current new screenshots**

Run:

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run screenshot:parity
```

Expected: all routes captured without navigation/app/API errors.

- [ ] **Step 3: Confirm no old frontend edits**

Run:

```bash
cd /Users/j/Documents/gupiao
git diff -- frontend
```

Expected: no changes from this task. If unrelated pre-existing diff exists, leave it untouched and mention it in report.

---

### Task 1: Legacy Shell

**Files:**
- Create: `frontend-next/src/legacy-shell/LegacyAppShell.tsx`
- Create: `frontend-next/src/legacy-shell/LegacySidebar.tsx`
- Create: `frontend-next/src/legacy-shell/LegacyTopbar.tsx`
- Create: `frontend-next/src/legacy-shell/LegacyPageContent.tsx`
- Create: `frontend-next/src/legacy-shell/legacyNavConfig.ts`
- Create: `frontend-next/src/legacy-shell/legacyShellStyles.ts`
- Create: `frontend-next/src/legacy-shell/legacyShell.test.tsx`
- Modify: `frontend-next/src/app/AppShell.tsx`

- [ ] **Step 1: Write shell contract test**

Create `legacyShell.test.tsx` with assertions for these strings/classes after render:

```tsx
expect(html).toContain("legacy-workspace-shell");
expect(html).toContain("legacy-sidebar");
expect(html).toContain("legacy-topbar");
expect(html).toContain("维斯量化");
expect(html).toContain("实时行动");
expect(html).toContain("系统配置");
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm test -- --run src/legacy-shell/legacyShell.test.tsx
```

Expected: FAIL because shell files do not exist yet.

- [ ] **Step 3: Implement shell constants**

In `legacyShellStyles.ts`, export Solid-compatible style objects for:

```ts
export const SIDEBAR_WIDTH = 220;
export const SIDEBAR_COLLAPSED_WIDTH = 64;
export const LEGACY_CONTENT_MAX_WIDTH = 1440;
```

Include style objects equivalent to old `WORKSPACE_SHELL_STYLE`, `CONTENT_MAIN_STYLE`, and `CONTENT_INNER_STYLE`.

- [ ] **Step 4: Implement navigation config**

In `legacyNavConfig.ts`, define routes in old frontend order:

```ts
monitor, monitor-market, analysis, playbook, strategy-tracking, backtest, paper, data, settings
```

Each item must include page, label, path, legacyPath, and icon name.

- [ ] **Step 5: Implement `LegacySidebar`**

Render brand, nav links, selected state, local icon wrapper, and no `Next Shadow` subtitle.

- [ ] **Step 6: Implement `LegacyTopbar`**

Render page title, monitor segmented switch when on monitor routes, paper refresh slot, market opportunity/risk/pulse chips, and user menu slot.

- [ ] **Step 7: Implement `LegacyAppShell` and wire `AppShell`**

Wrap existing `props.children` without changing route guards or page data logic.

- [ ] **Step 8: Run shell tests**

Run:

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm test -- --run src/legacy-shell/legacyShell.test.tsx
```

Expected: PASS.

---

### Task 2: Shared UI DOM Contract

**Files:**
- Modify: `frontend-next/src/shared/ui/Panel.tsx`
- Modify: `frontend-next/src/shared/ui/Button.tsx`
- Modify: `frontend-next/src/shared/ui/Tabs.tsx`
- Modify: `frontend-next/src/shared/ui/Segmented.tsx`
- Modify: `frontend-next/src/shared/ui/DataTable.tsx`
- Modify: `frontend-next/src/shared/ui/MetricGrid.tsx`
- Modify: `frontend-next/src/shared/ui/StockCard.tsx`
- Modify: `frontend-next/src/shared/ui/EmptyState.tsx`
- Test: `frontend-next/src/shared/ui/__tests__/wrappers.test.tsx`

- [ ] **Step 1: Extend wrapper tests**

Add assertions:

```tsx
expect(panelHtml).toContain("panel tq-panel");
expect(panelHtml).toContain("tq-panel__header");
expect(panelHtml).toContain("tq-panel__body--md");
expect(tableHtml).toContain("tq-table-wrap");
expect(stockHtml).toContain("tq-stock-card__body");
expect(stockHtml).toContain("tq-stock-card__score");
```

- [ ] **Step 2: Run tests and verify failures**

Run:

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm test -- --run src/shared/ui/__tests__/wrappers.test.tsx
```

Expected: FAIL until wrappers output legacy-compatible DOM.

- [ ] **Step 3: Update `Panel`**

Root class must include `panel tq-panel`. Header class must be `tq-panel__header`. Body class must be `tq-panel__body tq-panel__body--md`.

- [ ] **Step 4: Update `Button`, `Tabs`, `Segmented`**

Use local classes plus Ant-compatible aliases only for CSS matching:

```text
tq-button ant-btn ant-btn-default
tq-button tq-button--primary ant-btn ant-btn-primary
```

Do not import Ant.

- [ ] **Step 5: Update `DataTable`**

Keep TanStack Table. Output `tq-table-wrap`, `tq-table`, sticky header, compact cell class hooks, and stable row keys.

- [ ] **Step 6: Update `MetricGrid`**

Use old stat tile structure:

```text
tq-stat-tile
tq-stat-tile__label
tq-stat-tile__value
```

- [ ] **Step 7: Update `StockCard`**

Output key old class names:

```text
tq-stock-card
tq-stock-card__body
tq-stock-identity
tq-stock-card__badge-row
tq-stock-card__score
tq-stock-card__operation
tq-stock-card__execution-hint
```

- [ ] **Step 8: Run wrapper tests**

Run:

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm test -- --run src/shared/ui/__tests__/wrappers.test.tsx
```

Expected: PASS.

---

### Task 3: Style Entry And Adapter

**Files:**
- Create: `frontend-next/src/shared/styles/legacy-solid-adapter.css`
- Modify: `frontend-next/src/index.tsx`
- Verify: `frontend-next/src/shared/styles/legacy-workspace/*.css`

- [ ] **Step 1: Verify complete old CSS copy**

Run:

```bash
cd /Users/j/Documents/gupiao
find frontend/src/styles/workspace -maxdepth 1 -type f -name '*.css' | sort
find frontend-next/src/shared/styles/legacy-workspace -maxdepth 1 -type f -name '*.css' | sort
```

Expected: same workspace CSS file set.

- [ ] **Step 2: Fix CSS import order**

In `frontend-next/src/index.tsx`, keep this order:

```ts
import "./shared/styles/tokens.css";
import "./shared/styles/legacy-workspace.css";
import "./shared/styles/legacy-solid-adapter.css";
```

- [ ] **Step 3: Write adapter CSS**

Only write Solid DOM mapping in `legacy-solid-adapter.css`. Do not edit copied old CSS. Include shell class mapping, wrapper aliases, page grid overrides, and responsive guards.

- [ ] **Step 4: Run CSS/order validation**

Run:

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run build
```

Expected: PASS and no missing CSS import errors.

---

### Task 4: Pilot Page `/next/monitor`

**Files:**
- Read: `frontend/src/features/monitor/MonitorActionPage.tsx`
- Read: `frontend/src/features/monitor/MonitorPage.panels.tsx`
- Modify: `frontend-next/src/features/monitor-action/MonitorActionPage.tsx`
- Modify: `frontend-next/src/features/monitor-action/monitor-action.css`

- [ ] **Step 1: Compare old and new section order**

Document the old order in the task note:

```text
实时监控
生产优先榜
我的持仓
关键位/量价标签
AI 榜单解读
生产顺序核对
运行时/数据质量
```

- [ ] **Step 2: Rebuild DOM structure**

Use `Panel`, `MetricGrid`, `DataTable`, `StockCard`, and old class names. Do not change model/API logic.

- [ ] **Step 3: Preserve production order**

Ensure production priority list is rendered in server order. Any client filter must be display-only.

- [ ] **Step 4: Screenshot**

Run:

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run screenshot:parity
```

Expected: `/next/monitor` captured with no page/API errors.

---

### Task 5: Pilot Page `/next/paper`

**Files:**
- Read: `frontend/src/features/paper/PaperTradingPage.tsx`
- Read: `frontend/src/features/paper/PaperTradingSections.tsx`
- Read: `frontend/src/features/paper/PaperMechaActionPanel.tsx`
- Modify: `frontend-next/src/features/paper/PaperPage.tsx`
- Modify: `frontend-next/src/features/paper/paper-page.css`

- [ ] **Step 1: Restore old first-screen layout**

Use old structure:

```text
left: account metrics + holdings + tabs
right: mecha HUD
below: details/log/tabs
```

- [ ] **Step 2: Keep mecha display-only**

Mecha props and visual state must not affect API writes, ranking, score, or signals.

- [ ] **Step 3: Keep write guard**

If safe write contract is absent, show shadow/blocked state. Do not fake live success.

- [ ] **Step 4: Screenshot**

Run:

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run screenshot:parity
```

Expected: `/next/paper` captured with old-style density and no API/page errors.

---

### Task 6: Remaining Page Batch

**Files:**
- Modify: `frontend-next/src/features/strategy-tracking/*`
- Modify: `frontend-next/src/features/monitor-market/*`
- Modify: `frontend-next/src/features/analysis/*`
- Modify: `frontend-next/src/features/playbook/*`
- Modify: `frontend-next/src/features/backtest/*`
- Modify: `frontend-next/src/features/data-console/*`
- Modify: `frontend-next/src/features/settings/*`

- [ ] **Step 1: Migrate one page at a time**

Order:

```text
strategy-tracking
monitor-market
analysis
playbook
backtest
data
settings
```

- [ ] **Step 2: For each page, read old source**

Use the source mapping in `docs/frontend-next-legacy-ui-architecture-migration-development-doc-2026-06-06.md`.

- [ ] **Step 3: Rebuild DOM/class/section order**

Keep current Solid model/query logic. Change structure and wrapper usage first. Functional parity gaps remain tracked in gap docs.

- [ ] **Step 4: Run screenshot after each page**

Run:

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run screenshot:parity
```

Expected: route captured with no page/API errors.

---

### Task 7: Final Verification And Report

**Files:**
- Modify: `docs/reports/frontend-next-acceptance-2026-06-05.md`
- Modify: `docs/reports/frontend-next-open-items-2026-06-05.md`
- Update screenshots under `docs/reports/frontend-next-density-review-2026-06-06/`

- [ ] **Step 1: Run frontend-next checks**

Run:

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run screenshot:parity
```

Expected: all pass.

- [ ] **Step 2: Run final repository checks**

Run:

```bash
cd /Users/j/Documents/gupiao
git diff --check
git status --short
```

Expected: `git diff --check` has no output. Status may still show unrelated old dirty file.

- [ ] **Step 3: Update screenshot review directory**

Copy current screenshots:

```bash
cp docs/reports/frontend-next-screenshots-2026-06-05/monitor-action-web.png docs/reports/frontend-next-density-review-2026-06-06/next-monitor.png
cp docs/reports/frontend-next-screenshots-2026-06-05/monitor-market-web.png docs/reports/frontend-next-density-review-2026-06-06/next-monitor-market.png
cp docs/reports/frontend-next-screenshots-2026-06-05/paper-web.png docs/reports/frontend-next-density-review-2026-06-06/next-paper.png
cp docs/reports/frontend-next-screenshots-2026-06-05/strategy-tracking-web.png docs/reports/frontend-next-density-review-2026-06-06/next-strategy-tracking.png
cp docs/reports/frontend-next-screenshots-2026-06-05/analysis-web.png docs/reports/frontend-next-density-review-2026-06-06/next-analysis.png
cp docs/reports/frontend-next-screenshots-2026-06-05/playbook-web.png docs/reports/frontend-next-density-review-2026-06-06/next-playbook.png
cp docs/reports/frontend-next-screenshots-2026-06-05/backtest-web.png docs/reports/frontend-next-density-review-2026-06-06/next-backtest.png
cp docs/reports/frontend-next-screenshots-2026-06-05/data-console-web.png docs/reports/frontend-next-density-review-2026-06-06/next-data.png
cp docs/reports/frontend-next-screenshots-2026-06-05/settings-web.png docs/reports/frontend-next-density-review-2026-06-06/next-settings.png
```

- [ ] **Step 4: Report**

Report must include:

```text
initial/final git status
new/modified files
completed agents/phases
old frontend unchanged: yes/no
backend changed: yes/no
visual parity per page
test results
performance or bundle notes
platform impact
rollback
remaining items
cutover authorization needed: yes
```
