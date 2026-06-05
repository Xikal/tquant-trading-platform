# Frontend Next Solid Parallel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a parallel high-performance frontend in `frontend-next/` using SolidJS + TypeScript while preserving all current platform functionality, current visual style, current API contracts, and the existing `frontend/` implementation until shadow verification is complete.

**Architecture:** The current `frontend/` remains untouched and production-capable. `frontend-next/` is a separate Vite/SolidJS application that consumes the same FastAPI OpenAPI contract, BFF endpoints, auth flow, and backend data. The new app uses signals-first state, TanStack Query/Router/Virtual, Web Workers, Canvas/WebGL charts, optional Rust/WASM pure compute, and screenshot/data parity gates before any route cutover.

**Tech Stack:** SolidJS, TypeScript, Vite, TanStack Router, TanStack Query for Solid, TanStack Virtual/Table, Solid signals, Web Workers, Lightweight Charts, ECharts adapter for low-frequency charts, optional Rust/WASM, Vitest, Playwright.

---

## 1. Non-Negotiable Scope

### Must Keep

1. Existing `frontend/` code unchanged during new frontend development.
2. Existing backend behavior unchanged unless a later explicit task proves a frontend-only path impossible.
3. Existing visual style, page density, colors, spacing, typography, table/card density, copy tone, and interaction hierarchy.
4. All current core functionality:
   - monitor action desk
   - monitor market context desk
   - analysis
   - playbook
   - strategy tracking
   - paper trading
   - backtest
   - data console
   - settings
   - auth
5. Existing platform strategy semantics, production ranking, `priority_board`, production score, and feature flag gates.
6. OpenAPI/generated types as the contract source.
7. Rollback to current `frontend/` at any time.

### Must Not Do

1. Do not deploy.
2. Do not modify `strategy_policy.py`.
3. Do not change production strategy semantics.
4. Do not change priority-board sorting or production score.
5. Do not modify `frontend/` while building `frontend-next/`, except for a later explicit cutover task after verification.
6. Do not change the visual design or introduce a new theme.
7. Do not use third-party default component styling directly.
8. Do not let Worker/WASM become the only compute path; fallback is required.
9. Do not move strategy logic into the frontend.
10. Do not store backend secrets in the client.

## 2. Target Architecture

```text
backend / BFF / OpenAPI
        |
        v
frontend-next/src/generated/api-types.ts
        |
        v
typed API client
        |
        v
TanStack Query snapshot cache
        |
        +--> Solid signals realtime store
        +--> Web Worker derived view models
        |
        v
Solid feature pages
        |
        +--> virtual table/list
        +--> chart islands
        +--> current-style UI wrappers
```

### Runtime Data Rules

1. BFF snapshot remains the source for first-screen monitor data.
2. SSE/delta streams update only live fields.
3. Production ranking remains server-owned.
4. Frontend workers may sort/filter local display-only lists, but must not reorder production priority board unless the server already provided that order.
5. `monitor_snapshot.priority_board` remains the priority-board read path unless the backend contract intentionally adds a compatible alias.

## 3. Directory Structure

```text
frontend-next/
  package.json
  package-lock.json
  vite.config.ts
  tsconfig.json
  tsconfig.node.json
  index.html
  public/
  scripts/
    export-openapi.mjs
    compare-with-legacy.mjs
    perf-profile.mjs
    screenshot-parity.mjs
  src/
    app/
      App.tsx
      AppProviders.tsx
      AppShell.tsx
      ErrorBoundary.tsx
      env.ts
      routeTree.ts
    generated/
      api-types.ts
    shared/
      api/
        client.ts
        auth.ts
        queryKeys.ts
        errors.ts
      config/
        featureFlags.ts
        routes.ts
      realtime/
        liveQuoteSignals.ts
        sseClient.ts
        marketSession.ts
      workers/
        protocol.ts
        computeSync.ts
        workerClient.ts
        compute.worker.ts
      styles/
        tokens.css
        workspace-compat.css
        responsive.css
      ui/
        Button.tsx
        Panel.tsx
        Tabs.tsx
        Tag.tsx
        MetricGrid.tsx
        DataGrid.tsx
        VirtualList.tsx
        StockCard.tsx
        EmptyState.tsx
        StatusPill.tsx
      charts/
        KlineChart.tsx
        EchartsIsland.tsx
        chartDownsample.ts
      testing/
        fixtures.ts
        legacyParity.ts
        renderWithProviders.tsx
    features/
      auth/
      monitor-action/
      monitor-market/
      analysis/
      playbook/
      strategy-tracking/
      paper/
      backtest/
      data-console/
      settings/
```

## 4. Technology Decisions

| Concern | Decision | Reason |
|---|---|---|
| UI framework | SolidJS + TypeScript | Fine-grained updates for realtime trading dashboards |
| Routing | TanStack Router | Typed, nested, lazy route architecture |
| Server state | TanStack Query for Solid | Mature query cache and request state handling |
| Realtime state | Solid signals | Field-level updates for quote/clock/PnL |
| Large lists | TanStack Virtual | Stable DOM count and high scroll performance |
| Tables | TanStack Table + Virtual | Flexible high-density table model |
| Realtime K-line | Lightweight Charts | Mature financial charting and fast canvas rendering |
| Low-frequency charts | ECharts adapter | Preserve current chart behavior where realtime is not needed |
| Data transforms | Web Worker | Keep sort/filter/derive/downsample off main thread |
| Pure numeric hotspots | Rust/WASM optional | Only after worker telemetry proves CPU pressure |
| Visual style | current frontend compatibility layer | No visual redesign; screenshot parity required |

## 5. Visual Style Preservation

The new frontend must look like the current frontend.

### Style Sources

Extract from:

```text
frontend/src/styles/workspace/workspace.css
frontend/src/styles/foundation/tokens.css
frontend/src/features/workspace-shared/WorkspaceComponents.tsx
frontend/src/features/workspace-shared/StockCard.tsx
frontend/src/ui/table/DataTable.tsx
frontend/src/ui/list/VirtualCardList.tsx
```

### Rules

1. Do not design a new theme.
2. Reuse current colors, radii, density, borders, shadows, and copy tone.
3. Third-party components must be wrapped with `frontend-next/src/shared/ui/*`.
4. Current style wrappers must be implemented before feature pages.
5. Use screenshot parity instead of subjective design review.
6. Keep the paper mecha avatar and execution log elements, but isolate them in the paper feature and keep them display-only.

## 6. Page Style Specs And Layout Images

Every target page must have approved desktop and mobile style images before feature implementation starts. These images are binding implementation references, not visual redesign concepts.

### Required Style Spec Artifacts

```text
docs/frontend-next/style-specs/monitor-action-style-spec-2026-06-05.md
docs/frontend-next/style-specs/monitor-market-style-spec-2026-06-05.md
docs/frontend-next/style-specs/paper-style-spec-2026-06-05.md
docs/frontend-next/style-specs/strategy-tracking-style-spec-2026-06-05.md
docs/frontend-next/style-specs/analysis-style-spec-2026-06-05.md
docs/frontend-next/style-specs/playbook-style-spec-2026-06-05.md
docs/frontend-next/style-specs/backtest-style-spec-2026-06-05.md
docs/frontend-next/style-specs/data-console-style-spec-2026-06-05.md
docs/frontend-next/style-specs/settings-style-spec-2026-06-05.md
```

Each style spec must contain:

1. Desktop style image path.
2. Mobile style image path.
3. Current route and new route.
4. Visible section order.
5. Panel, card, table, list, chart, and toolbar density rules.
6. Color token mapping from the current frontend.
7. Typography and spacing rules.
8. Component inventory.
9. Responsive collapse behavior.
10. Visual non-goals.
11. Screenshot parity checklist.

### Required Style Images

```text
docs/frontend-next/style-specs/images/monitor-action-desktop.png
docs/frontend-next/style-specs/images/monitor-action-mobile.png
docs/frontend-next/style-specs/images/monitor-market-desktop.png
docs/frontend-next/style-specs/images/monitor-market-mobile.png
docs/frontend-next/style-specs/images/paper-desktop.png
docs/frontend-next/style-specs/images/paper-mobile.png
docs/frontend-next/style-specs/images/strategy-tracking-desktop.png
docs/frontend-next/style-specs/images/strategy-tracking-mobile.png
docs/frontend-next/style-specs/images/analysis-desktop.png
docs/frontend-next/style-specs/images/analysis-mobile.png
docs/frontend-next/style-specs/images/playbook-desktop.png
docs/frontend-next/style-specs/images/playbook-mobile.png
docs/frontend-next/style-specs/images/backtest-desktop.png
docs/frontend-next/style-specs/images/backtest-mobile.png
docs/frontend-next/style-specs/images/data-console-desktop.png
docs/frontend-next/style-specs/images/data-console-mobile.png
docs/frontend-next/style-specs/images/settings-desktop.png
docs/frontend-next/style-specs/images/settings-mobile.png
```

### Image Source Rules

1. Preferred source: run the existing `frontend/`, capture current page screenshots at desktop and mobile widths, and use those captures as the style images.
2. Allowed fallback: if the current page does not exist or the new split page has no exact old equivalent, compose the image only from current frontend style tokens, current components, and the approved layout plan.
3. Forbidden: new visual direction, new theme, decorative redesign, or generated concept art.
4. The image must show the actual page structure to implement, including header, tabs, side panels, tables, charts, cards, logs, empty states when relevant, and responsive behavior.

### Binding Implementation Rule

1. No feature page implementation may start until its style spec and desktop/mobile style images exist.
2. No feature page may be accepted until screenshot parity matches the approved style images for layout, section order, colors, typography, density, spacing, responsive collapse, and copy hierarchy.
3. Any deviation from a style image must be recorded in the page style spec and approved before coding continues.

## 7. Functional Parity Matrix

| Current Route | New Route | Module | Priority | Parity Gate |
|---|---|---|---|---|
| `/monitor` | `/next/monitor` | `monitor-action` | P0 | BFF data parity, live quote parity, screenshot parity |
| `/monitor/market` | `/next/monitor/market` | `monitor-market` | P0 | market state, breadth, pulse, sector/ETF parity |
| `/analysis` | `/next/analysis` | `analysis` | P1 | analysis result, K-line, status parity |
| `/playbook` | `/next/playbook` | `playbook` | P1 | strategy copy and performance fields parity |
| `/strategy-tracking` | `/next/strategy-tracking` | `strategy-tracking` | P0 | strategy state, review center, table parity |
| `/paper` | `/next/paper` | `paper` | P0 | paper order/holding/performance/mecha/log parity |
| `/backtest` | `/next/backtest` | `backtest` | P1 | run list, result chart, report parity |
| `/data` | `/next/data` | `data-console` | P2 | source health and task state parity |
| `/settings` | `/next/settings` | `settings` | P2 | flags/settings/auth guard parity |

## 8. Multi-Agent Workstreams

### Agent A: Architecture And Scaffold

Responsible for:

1. Create `frontend-next/`.
2. Configure Vite, SolidJS, TypeScript, lint, tests, build.
3. Configure route skeleton.
4. Configure shared providers and app shell.

Must not touch:

```text
frontend/
backend/
```

### Agent B: Contract And API Layer

Responsible for:

1. Generate `frontend-next/src/generated/api-types.ts`.
2. Build typed API client.
3. Build auth handling.
4. Build TanStack Query keys.
5. Build contract smoke tests.

Must not change OpenAPI unless explicitly authorized.

### Agent C: Current-Style UI System

Responsible for:

1. Extract style tokens from current frontend.
2. Build `shared/ui` wrappers.
3. Build `DataGrid`, `VirtualList`, `StockCard`, `MetricGrid`.
4. Create all page style specs and desktop/mobile style images.
5. Add screenshot parity fixtures.

Must not invent new visual language.

### Agent D: Realtime, Worker, And Charts

Responsible for:

1. Implement live quote signals.
2. Implement SSE client.
3. Implement Worker protocol and fallback.
4. Implement K-line chart and ECharts adapter.
5. Implement performance telemetry.

Must not move production strategy logic to the frontend.

### Agent E: Core Feature Pages

Responsible for:

1. `/next/monitor`.
2. `/next/monitor/market`.
3. `/next/paper`.
4. `/next/strategy-tracking`.

### Agent F: Secondary Feature Pages

Responsible for:

1. `/next/analysis`.
2. `/next/playbook`.
3. `/next/backtest`.
4. `/next/data`.
5. `/next/settings`.

### Agent G: QA, Parity, And Cutover

Responsible for:

1. Old/new screenshot comparison.
2. Old/new API payload comparison.
3. Performance profile.
4. E2E smoke tests.
5. Cutover runbook.
6. Acceptance report.

## 9. Development Phases

### Phase 0: Baseline And Architecture Lock

Create:

```text
docs/reports/frontend-next-baseline-2026-06-05.md
docs/frontend-next-architecture-design-2026-06-05.md
docs/frontend-next-feature-parity-matrix-2026-06-05.md
docs/frontend-next-cutover-runbook-2026-06-05.md
docs/frontend-next/style-specs/*.md
docs/frontend-next/style-specs/images/*.png
```

Acceptance:

1. Current `git status --short` recorded.
2. Current frontend routes and features inventoried.
3. Current style sources inventoried.
4. Current performance baselines referenced.
5. Cutover remains opt-in.
6. Every target page has desktop and mobile style images.

### Phase 1: Scaffold `frontend-next/`

Create `frontend-next/` with:

```text
SolidJS
TypeScript
Vite
Vitest
Playwright
TanStack Router
TanStack Query for Solid
TanStack Virtual/Table
Lightweight Charts
ECharts
```

Acceptance commands:

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run typecheck
npm run lint
npm test -- --run
npm run build
```

### Phase 2: Contract And API Layer

Build:

```text
src/generated/api-types.ts
src/shared/api/client.ts
src/shared/api/auth.ts
src/shared/api/queryKeys.ts
src/shared/api/errors.ts
```

Acceptance:

1. Generated types come from `../docs/contracts/openapi.json`.
2. No handwritten duplicate DTOs for existing OpenAPI responses.
3. API client keeps snake_case fields as contract fields.
4. Contract smoke tests pass.

### Phase 3: Current-Style UI System

Build:

```text
src/shared/styles/tokens.css
src/shared/styles/workspace-compat.css
src/shared/ui/*
```

Acceptance:

1. Components match current density and style.
2. No third-party default visual style leaks.
3. Desktop and mobile page style images exist.
4. Screenshot parity snapshots pass against approved style images.

### Phase 4: Realtime, Worker, And Chart Infrastructure

Build:

```text
src/shared/realtime/*
src/shared/workers/*
src/shared/charts/*
```

Acceptance:

1. SSE supports snapshot + delta.
2. Worker has sync fallback.
3. K-line chart supports incremental update.
4. Worker tasks are measured.
5. WASM remains disabled unless telemetry proves need.

### Phase 5: Core Pages

Implement:

```text
/next/monitor
/next/monitor/market
/next/paper
/next/strategy-tracking
```

Acceptance:

1. Current core workflows exist.
2. Data parity with old frontend passes.
3. Screenshot parity passes against approved page style images.
4. No production ranking changes.
5. Paper mecha avatar and execution log are preserved as display/review elements.

### Phase 6: Secondary Pages

Implement:

```text
/next/analysis
/next/playbook
/next/backtest
/next/data
/next/settings
```

Acceptance:

1. All current routes have a new frontend counterpart.
2. Empty/error/loading/disabled states exist.
3. Feature flags are respected.
4. Screenshot parity passes against approved page style images.

### Phase 7: Full Parity And Shadow Run

Run:

```text
old frontend: /...
new frontend: /next/...
same backend
same user
same API payloads
```

Acceptance:

1. Two trading days of shadow use with no P0/P1 issue.
2. API request count does not regress.
3. SSE connection count does not duplicate.
4. Hot-read targets remain within accepted budget.
5. New frontend performance beats old frontend on target pages.
6. Screenshot parity passes against approved page style images.

### Phase 8: Optional Cutover

Only after explicit user approval.

Options:

1. Keep new frontend under `/next/*`.
2. Route selected pages to new frontend.
3. Switch default frontend entry.

Rollback:

```text
NEW_FRONTEND_ENABLED=false
```

## 10. Performance Targets

| Metric | Target |
|---|---:|
| `/next/monitor` first interactive | < 650ms local profile |
| `/next/monitor` route switch | < 500ms |
| `/next/strategy-tracking` route switch | < 500ms |
| K-line incremental update | < 16ms/frame target |
| Large list scroll | near 60fps |
| Long tasks | 0 in local profile |
| First-screen JS gzip | lower than old frontend or justified |
| Duplicate SSE streams | 0 |
| BFF request count regression | 0 |

## 11. Validation Commands

New frontend:

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run e2e
npm run perf:compare
npm run screenshot:parity
```

`npm run screenshot:parity` must compare `/next/*` screenshots against the approved images in `docs/frontend-next/style-specs/images/`.

Old frontend must remain green:

```bash
cd /Users/j/Documents/gupiao/frontend
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
```

Repository checks:

```bash
cd /Users/j/Documents/gupiao
git diff --check
git status --short
```

Backend tests are only required if backend/API files are changed:

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
```

## 12. Cutover Gates

Cutover is forbidden until all are true:

1. `frontend/` remains available and green.
2. `frontend-next/` passes all validation commands.
3. All feature routes have parity reports.
4. Every page has approved desktop/mobile style images and screenshot parity passes for both breakpoints.
5. Contract parity passes.
6. Strategy state and production ranking displays match old frontend.
7. No duplicate SSE streams.
8. No BFF request count regression.
9. New frontend performance is equal or better on core pages.
10. User explicitly approves cutover.

## 13. Risk Register

| Risk | Mitigation |
|---|---|
| New frontend drifts visually | Current-style wrappers and screenshot parity |
| Feature page starts without a visual source of truth | Block implementation until style spec and images exist |
| Strategy field semantics drift | Generated types, contract tests, parity fixtures |
| Production priority order changes | Server order is source; no frontend production re-sort |
| Duplicate live streams | Central SSE client and connection count tests |
| Third-party style leakage | All third-party controls wrapped in `shared/ui` |
| Worker/WASM changes semantics | Sync fallback and deterministic fixture parity |
| Backend scope creep | Phase 1-7 frontend-only unless explicitly approved |
| Cutover risk | Keep `/next/*` shadow route and `NEW_FRONTEND_ENABLED=false` rollback |

## 14. Implementation Prompt

```text
你在 /Users/j/Documents/gupiao 仓库工作。本轮目标是按并行新前端方案新建 frontend-next/，使用 SolidJS + TypeScript + Vite + TanStack + Signals + Web Worker + Canvas/Lightweight Charts，完整复刻现有前端功能和视觉风格。旧 frontend/ 必须保留不变；后端代码尽量不动；充分验证后才允许后续对接新前端。

开始前必须阅读：
/Users/j/Documents/gupiao/AGENTS.md
/Users/j/Documents/gupiao/docs/engineering-conventions.md
/Users/j/Documents/gupiao/docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md
/Users/j/Documents/gupiao/docs/architecture/current-boundary-map.md
/Users/j/Documents/gupiao/docs/frontend-performance-islands-worker-wasm-development-plan-2026-06-05.md
/Users/j/Documents/gupiao/docs/monitor-page-split-development-plan-2026-06-05.md
/Users/j/Documents/gupiao/docs/frontend-next-solid-parallel-development-plan-2026-06-05.md

开始前必须执行：
cd /Users/j/Documents/gupiao
git status --short

硬边界：
1. 不部署。
2. 不修改 strategy_policy.py。
3. 不修改生产策略语义、生产排序、production_score、priority_board 口径。
4. 不修改旧 frontend/，除非后续有明确 cutover 授权；本轮只新建 frontend-next/ 和必要文档。
5. 后端代码尽量不动；第一阶段不得拆 BFF/API 契约。
6. 页面风格、样式、密度、文案语气按现有前端，不做视觉重设计。
7. 每个页面开发前必须先产出样式图，严格按照样式图开发；没有样式图不得开始页面实现。
8. 样式图优先从旧 frontend/ 当前页面截图生成；旧页面不存在时，只能用现有前端风格和已批准布局组合生成，不得重新设计视觉。
9. 不直接使用第三方默认样式，必须通过 frontend-next/src/shared/ui wrapper。
10. Worker/WASM 只做显示层数据变换和纯计算，不做生产策略判断。
11. 机甲头像和实施/执行日志只作为模拟盘 display/review 元素，不参与生产排序或信号计算。

架构目标：
- frontend/ 继续保持现状和可回滚。
- frontend-next/ 独立新前端：SolidJS + TypeScript + Vite。
- 使用 TanStack Router/Query/Virtual/Table。
- 使用 Solid signals 做高频行情状态。
- 使用 Web Worker 做 sort/filter/derive/downsample，并保留 sync fallback。
- 使用 Lightweight Charts 做实时 K 线，ECharts adapter 只保留低频图表。
- 使用 OpenAPI generated types；不得手写重复 DTO。
- 新前端先挂 /next/*，充分 shadow/parity 验证后再讨论切流。

多 Agent 并行：
A 架构/脚手架：创建 frontend-next/、Vite/Solid/TS、路由骨架、providers、app shell。
B 契约/API：生成 api-types、typed API client、auth、query keys、contract smoke。
C UI 风格系统：从旧前端提取 tokens/workspace 样式，先产出每个页面 desktop/mobile 样式图和 style spec，再构建 shared/ui wrappers、DataGrid、VirtualList、StockCard、MetricGrid，并做截图 parity。
D 实时/Worker/图表：SSE、signals、Worker protocol/fallback、KlineChart、ECharts adapter、telemetry。
E 核心页面：/next/monitor、/next/monitor/market、/next/paper、/next/strategy-tracking。
F 次级页面：/next/analysis、/next/playbook、/next/backtest、/next/data、/next/settings。
G QA/验收：旧新数据 parity、截图 parity、性能 profile、E2E、cutover runbook、acceptance report。

执行阶段：
P0 生成 docs/reports/frontend-next-baseline-2026-06-05.md、docs/frontend-next-architecture-design-2026-06-05.md、docs/frontend-next-feature-parity-matrix-2026-06-05.md、docs/frontend-next-cutover-runbook-2026-06-05.md、docs/frontend-next/style-specs/*.md、docs/frontend-next/style-specs/images/*.png。
P1 新建 frontend-next/ 脚手架和基础命令。
P2 建契约/API 层，OpenAPI 从 ../docs/contracts/openapi.json 生成。
P3 建现有风格兼容 UI 系统，不做视觉重设计。
P4 建 realtime/worker/chart 基础设施。
P5 实现核心页面 /next/monitor、/next/monitor/market、/next/paper、/next/strategy-tracking。
P6 实现 /next/analysis、/next/playbook、/next/backtest、/next/data、/next/settings。
P7 做旧新 shadow 验证、截图 parity、数据 parity、性能对比。
P8 只在用户明确授权后做 cutover；默认不切流。

新前端必须支持命令：
cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run e2e
npm run perf:compare
npm run screenshot:parity

旧前端必须保持通过：
cd /Users/j/Documents/gupiao/frontend
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build

最后运行：
cd /Users/j/Documents/gupiao
git diff --check
git status --short

输出报告：
生成 docs/reports/frontend-next-acceptance-2026-06-05.md，包含：
1. 初始 git status。
2. frontend-next/ 架构和目录。
3. 新旧功能 parity 矩阵。
4. 每个页面的样式图路径和视觉/截图 parity 结果。
5. 数据/API parity 结果。
6. SSE/请求数量是否重复。
7. 性能对比。
8. 测试命令和结果。
9. 是否修改后端/旧前端。
10. 是否影响平台功能：明确回答“不影响”或说明风险。
11. 回滚方式。
12. 未完成项和需要用户确认项。

最终回复必须包含：
- 新建了哪些目录/文件。
- 哪些 Agent/阶段完成。
- 旧 frontend/ 是否保持未改。
- 后端是否改动。
- 新旧功能 parity 结果。
- 测试结果。
- 性能对比。
- 是否影响平台功能：明确回答“不影响”或说明风险。
- 下一步是否需要用户授权 cutover。
```
