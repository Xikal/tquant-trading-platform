# Legacy Frontend Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不迁移 `frontend-next`、不替换 React/AntD/Vite/ECharts 的前提下，把旧前端 `frontend/` 的核心交易链路优化到“首屏更轻、数据状态一致、异常可恢复、页面更可维护、验收可自动化”的端态。

**Architecture:** 保持旧前端 SPA 架构，继续使用路由级 lazy、TanStack Query、BFF 聚合、既有 `VirtualCardList`/`VirtualGrid`/`ChartIsland` 和 bundle budget。优化围绕 `/monitor -> /playbook -> /backtest -> /paper -> /settings` 主链路做收口，不做全站重写，不触碰 `frontend-next/`。

**Tech Stack:** React 18, TypeScript, Vite 8, Ant Design 6, TanStack Query 5, Zustand, ECharts, Vitest, Playwright.

---

## Scope

### In Scope

- 旧前端路径：`frontend/`
- 核心 Web 路由：`/monitor`、`/monitor/market`、`/playbook`、`/backtest`、`/paper`、`/settings`
- 首屏数据链路：`frontend/src/features/trading-workspace/useMonitorData.ts`
- BFF 聚合与降级：`frontend/src/features/trading-workspace/useMonitorWorkspaceBff.ts`
- 过期/降级/等待发布状态：`frontend/src/features/workspace-shared/*`、`frontend/src/features/settings/LatestDataStatusCard.tsx`、`frontend/src/features/monitor/*`
- 首屏包体预算：`frontend/scripts/bundle-report.mjs`、`frontend/scripts/check-bundle-budget.mjs`、`frontend/vite.config.ts`
- 浏览器冒烟：`frontend/scripts/smoke-monitor-bff.mjs` 和新增核心链路 smoke 脚本

### Out Of Scope

- 不改 `frontend-next/`
- 不迁移旧前端到 Next/Solid/Svelte/SSR
- 不替换 AntD、ECharts、Vite
- 不新增移动端专项
- 不改股票策略口径、生产排序、推荐分、仓位和风控规则
- 不让 Web 前端新增后台 loop 或重计算任务
- 不清理与本计划无关的未提交文件

## Current Facts

- `frontend/src/features/trading-workspace/useMonitorData.ts` 约 898 行，仍承担首屏请求编排、BFF fallback、lane 切换、状态写入、刷新队列等多重职责。
- `frontend/src/features/settings/SettingsPage.tsx` 约 423 行，接近工程规范的 React 页面评审阈值。
- `frontend/src/features/settings/LatestDataStatusCard.tsx`、`frontend/src/features/monitor/MonitorActionPage.tsx`、`frontend/src/features/playbook/PlaybookPage.tsx` 已各自展示 stale/degraded/waiting 状态，但状态视图模型仍可继续统一。
- `frontend/vite.config.ts` 已有 AntD/ECharts 手动分包，`frontend/scripts/check-bundle-budget.mjs` 已存在，可直接作为性能回归门。
- `frontend/scripts/smoke-monitor-bff.mjs` 已验证 `/monitor` BFF 请求数、legacy 请求回退和 500/auth 场景，但还缺核心工作流 smoke。

## Hard Rules

1. 每批开始前执行 `git status --short`，保护既有用户改动。
2. 每批只改本批列出的文件；如必须扩大范围，先补充计划再执行。
3. 新增或修改旧前端源码时，遵守 `docs/engineering-conventions.md` 的文件规模和模块边界。
4. 服务端响应数据继续以 TanStack Query/BFF 为主，不复制进 Zustand。
5. `stale`、`degraded`、`blocked`、`no_data`、`research_only` 必须显式展示，不能用空态或成功态掩盖。
6. 推荐票和优先榜一旦过期，只能作为复盘/观察展示，不能在文案上暗示今日可交易。
7. 每批完成后至少运行对应 Vitest、`npm run lint`、`npm run typecheck`；涉及首屏或路由的批次必须跑 smoke。
8. 生产部署不属于本计划默认动作，除非用户当轮明确要求部署。

## File Structure Plan

### Create

- `frontend/src/features/workspace-shared/dataFreshnessViewModel.ts`
  - 统一旧前端的数据新鲜度、过期、降级、等待发布、复盘只读状态。
- `frontend/src/features/workspace-shared/dataFreshnessViewModel.test.ts`
  - 覆盖推荐票过期、交易日正常、发布滞后、部分降级、等待生成。
- `frontend/src/features/trading-workspace/monitorWorkspaceLoaders.ts`
  - 从 `useMonitorData.ts` 拆出 BFF 优先加载、legacy fallback、runtime/hourly 补偿加载的纯函数。
- `frontend/src/features/trading-workspace/monitorWorkspaceLoaders.test.ts`
  - 覆盖 BFF 成功、BFF disabled、BFF 500、snapshot 空榜 fallback、auth error。
- `frontend/src/features/trading-workspace/monitorRefreshState.ts`
  - 从 `useMonitorData.ts` 拆出 in-flight/queued refresh 状态机。
- `frontend/src/features/trading-workspace/monitorRefreshState.test.ts`
  - 覆盖重复刷新排队、includeRuntime 合并、页面切换后的应用门控。
- `frontend/scripts/smoke-core-workflow.mjs`
  - Playwright mock API 冒烟 `/monitor -> /playbook -> /backtest -> /paper -> /settings`。
- `frontend/src/features/settings/SettingsPage.viewModel.ts`
  - 从 `SettingsPage.tsx` 拆出设置页状态分组、卡片配置和状态摘要。
- `frontend/src/features/settings/SettingsPage.viewModel.test.ts`
  - 覆盖设置页数据状态、令牌缺失、补数可用性。
- `docs/reports/legacy-frontend-optimization-acceptance-2026-06-06.md`
  - 记录每批验收结果、bundle 指标、smoke 结果和剩余风险。

### Modify

- `frontend/src/features/trading-workspace/useMonitorData.ts`
  - 缩小为 hook 编排层，调用 loader/state machine/view model。
- `frontend/src/features/trading-workspace/useMonitorData.test.ts`
  - 增加 hook 周边行为回归，保留已有 view/lane 测试。
- `frontend/src/features/trading-workspace/useMonitorWorkspaceBff.ts`
  - 保留 BFF feature flag 和 priority-board parity，暴露 loader 需要的稳定 helper。
- `frontend/src/features/trading-workspace/useMonitorWorkspaceBff.test.ts`
  - 增加 BFF-first 首屏和 legacy fallback 请求数保护。
- `frontend/src/features/monitor/MonitorActionPage.tsx`
  - 使用统一 freshness view model 展示优先榜状态。
- `frontend/src/features/monitor/MonitorPage.helpers.ts`
  - 收敛 monitor 状态文案和 tone。
- `frontend/src/features/playbook/PlaybookPage.tsx`
  - 使用统一 freshness view model 展示选股宝典 stale/复盘提示。
- `frontend/src/features/settings/LatestDataStatusCard.tsx`
  - 使用统一 freshness view model 展示交易日、发布滞后、本地滞后和补数提示。
- `frontend/src/features/settings/SettingsPage.tsx`
  - 拆出 view model 后只保留页面布局与事件绑定。
- `frontend/scripts/bundle-report.mjs`
  - 校准 `first-screen-js` 分类，避免把 lazy feature 误记入或漏记首屏。
- `frontend/scripts/check-bundle-budget.mjs`
  - 加入核心路由 chunk 名称白名单/预算说明检查。
- `frontend/package.json`
  - 增加 `smoke:core-workflow` 脚本。

---

## Milestones

### Batch 0: Baseline And Guardrail Check

**Purpose:** 记录当前旧前端基线，避免后续用主观体感判断优化成败。

**Files:**
- Create: `docs/reports/legacy-frontend-optimization-acceptance-2026-06-06.md`
- Read only: `frontend/dist/`, `frontend/package.json`, `frontend/scripts/*`

- [ ] **Step 1: Confirm working tree before edits**

Run:

```bash
git status --short
```

Expected:

```text
仅记录当前脏文件；不 revert、不清理、不修改 frontend-next/。
```

- [ ] **Step 2: Run baseline frontend checks**

Run:

```bash
cd frontend
npm run typecheck
npm test -- --run
npm run lint
npm run build
npm run analyze
```

Expected:

```text
typecheck/lint/test/build/analyze 全部通过；若 analyze 生成 dist/bundle-report.json，记录 first_screen_js_gzip_kb、total_gzip_kb、Top 10 chunks。
```

- [ ] **Step 3: Run existing monitor BFF smoke**

Run:

```bash
cd frontend
npm run build
npm run preview -- --host 127.0.0.1 > /tmp/gupiao-frontend-preview.log 2>&1 &
FRONTEND_SMOKE_URL=http://127.0.0.1:4173 node ./scripts/smoke-monitor-bff.mjs
MONITOR_BFF_SMOKE_SCENARIO=500 FRONTEND_SMOKE_URL=http://127.0.0.1:4173 node ./scripts/smoke-monitor-bff.mjs
MONITOR_BFF_SMOKE_SCENARIO=auth FRONTEND_SMOKE_URL=http://127.0.0.1:4173 node ./scripts/smoke-monitor-bff.mjs
```

Expected:

```text
dist/monitor-bff-smoke-report.json 中 ok=true；正常场景 bff_count=1，legacy_monitor_count=0。
```

- [ ] **Step 4: Write acceptance baseline report**

Add this section to `docs/reports/legacy-frontend-optimization-acceptance-2026-06-06.md`:

```markdown
# Legacy Frontend Optimization Acceptance Report

Date: 2026-06-06
Scope: frontend/ only

## Baseline

- git status before work: `<paste git status summary>`
- typecheck: `<pass/fail>`
- vitest: `<pass/fail>`
- lint: `<pass/fail>`
- build: `<pass/fail>`
- analyze first_screen_js_gzip_kb: `<value>`
- analyze total_gzip_kb: `<value>`
- monitor BFF smoke ok: `<true/false>`

## Batch Results

Pending.

## Residual Risk

Pending.
```

- [ ] **Step 5: Commit**

Run:

```bash
git add docs/reports/legacy-frontend-optimization-acceptance-2026-06-06.md
git commit -m "docs: record legacy frontend optimization baseline"
```

Expected:

```text
Commit only the acceptance report. Do not stage unrelated files.
```

---

### Batch 1: Monitor BFF First-Screen Cleanup

**Purpose:** 把 `/monitor` 首屏加载收敛成 BFF 优先、legacy fallback 明确、lane 切换懒加载，减少 `useMonitorData.ts` 的职责和首屏请求面。

**Files:**
- Create: `frontend/src/features/trading-workspace/monitorWorkspaceLoaders.ts`
- Create: `frontend/src/features/trading-workspace/monitorWorkspaceLoaders.test.ts`
- Create: `frontend/src/features/trading-workspace/monitorRefreshState.ts`
- Create: `frontend/src/features/trading-workspace/monitorRefreshState.test.ts`
- Modify: `frontend/src/features/trading-workspace/useMonitorData.ts`
- Modify: `frontend/src/features/trading-workspace/useMonitorData.test.ts`
- Modify: `frontend/src/features/trading-workspace/useMonitorWorkspaceBff.ts`
- Modify: `frontend/src/features/trading-workspace/useMonitorWorkspaceBff.test.ts`

- [ ] **Step 1: Write loader tests before implementation**

Create `frontend/src/features/trading-workspace/monitorWorkspaceLoaders.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import { loadMonitorWorkspaceFirstScreen } from "./monitorWorkspaceLoaders";

describe("loadMonitorWorkspaceFirstScreen", () => {
  it("uses the BFF action view for monitor first screen", async () => {
    const fetchWorkspace = vi.fn(async () => ({ monitor_snapshot: { priority_board: { items: [{ symbol: "600000" }] } } }));
    const fetchLegacy = vi.fn();
    const result = await loadMonitorWorkspaceFirstScreen({
      page: "monitor",
      priorityLimit: 12,
      includeRuntime: false,
      bffEnabled: true,
      fetchWorkspace,
      fetchLegacy,
      fetchPriorityBoardFallback: vi.fn(async () => null),
      fetchHourlyHistory: vi.fn(),
      fetchRuntime: vi.fn(),
      hasAdminToken: () => false,
    });

    expect(fetchWorkspace).toHaveBeenCalledWith(12, "action");
    expect(fetchLegacy).not.toHaveBeenCalled();
    expect(result.source).toBe("bff");
  });

  it("falls back to legacy only when the aggregate endpoint is explicitly disabled", async () => {
    const disabled = new Error("monitor BFF aggregate disabled") as Error & { status: number };
    disabled.status = 404;
    const fetchWorkspace = vi.fn(async () => {
      throw disabled;
    });
    const fetchLegacy = vi.fn(async () => ({ source: "legacy" }));

    const result = await loadMonitorWorkspaceFirstScreen({
      page: "monitor",
      priorityLimit: 12,
      includeRuntime: false,
      bffEnabled: true,
      fetchWorkspace,
      fetchLegacy,
      fetchPriorityBoardFallback: vi.fn(async () => null),
      fetchHourlyHistory: vi.fn(),
      fetchRuntime: vi.fn(),
      hasAdminToken: () => false,
    });

    expect(result.source).toBe("legacy");
    expect(fetchLegacy).toHaveBeenCalledTimes(1);
  });

  it("returns a retryable error for transient BFF failures instead of issuing legacy fan-out", async () => {
    const transient = new Error("upstream timeout") as Error & { status: number };
    transient.status = 500;
    const fetchLegacy = vi.fn();

    await expect(loadMonitorWorkspaceFirstScreen({
      page: "monitor",
      priorityLimit: 12,
      includeRuntime: false,
      bffEnabled: true,
      fetchWorkspace: vi.fn(async () => {
        throw transient;
      }),
      fetchLegacy,
      fetchPriorityBoardFallback: vi.fn(async () => null),
      fetchHourlyHistory: vi.fn(),
      fetchRuntime: vi.fn(),
      hasAdminToken: () => false,
    })).rejects.toThrow("upstream timeout");

    expect(fetchLegacy).not.toHaveBeenCalled();
  });
});
```

Run:

```bash
cd frontend
npm test -- --run src/features/trading-workspace/monitorWorkspaceLoaders.test.ts
```

Expected:

```text
FAIL because monitorWorkspaceLoaders.ts does not exist yet.
```

- [ ] **Step 2: Implement monitor workspace loader**

Create `frontend/src/features/trading-workspace/monitorWorkspaceLoaders.ts` with these exported functions and types:

```ts
import type { MonitorWorkspaceData, MonitorWorkspaceView } from "./useMonitorWorkspaceBff";
import type { Page } from "../workspace-shared/workspaceTypes";
import { isMonitorBffDisabled } from "./useMonitorWorkspaceBff";

export type MonitorFirstScreenLoadSource = "bff" | "legacy";

export interface MonitorFirstScreenLoadResult {
  source: MonitorFirstScreenLoadSource;
  workspace?: MonitorWorkspaceData;
  legacy?: unknown;
  priorityBoardFallback?: unknown;
  hourlyHistory?: unknown;
  runtime?: unknown;
}

export interface MonitorFirstScreenLoadOptions {
  page: Page;
  priorityLimit: number;
  includeRuntime: boolean;
  bffEnabled: boolean;
  fetchWorkspace: (priorityLimit: number, view: MonitorWorkspaceView) => Promise<MonitorWorkspaceData>;
  fetchLegacy: (includeRuntime: boolean) => Promise<unknown>;
  fetchPriorityBoardFallback: (workspace: MonitorWorkspaceData | null) => Promise<unknown | null>;
  fetchHourlyHistory: () => Promise<unknown>;
  fetchRuntime: () => Promise<unknown>;
  hasAdminToken: () => boolean;
}

export async function loadMonitorWorkspaceFirstScreen(options: MonitorFirstScreenLoadOptions): Promise<MonitorFirstScreenLoadResult> {
  if (!options.bffEnabled) {
    return { source: "legacy", legacy: await options.fetchLegacy(options.includeRuntime) };
  }
  try {
    const workspace = await options.fetchWorkspace(options.priorityLimit, monitorWorkspaceViewForPage(options.page));
    const priorityBoardFallback = await options.fetchPriorityBoardFallback(workspace);
    const [hourlyHistory, runtime] = await Promise.all([
      workspace.hourly_snapshot_history ? Promise.resolve(null) : options.fetchHourlyHistory(),
      options.includeRuntime && options.hasAdminToken() && !("runtime" in workspace) ? options.fetchRuntime() : Promise.resolve(null),
    ]);
    return { source: "bff", workspace, priorityBoardFallback, hourlyHistory, runtime };
  } catch (error) {
    if (isMonitorBffDisabled(error)) {
      return { source: "legacy", legacy: await options.fetchLegacy(options.includeRuntime) };
    }
    throw error;
  }
}

export function monitorWorkspaceViewForPage(page: Page): MonitorWorkspaceView {
  if (page === "monitor") return "action";
  if (page === "monitor-market") return "market";
  return "full";
}
```

Run:

```bash
cd frontend
npm test -- --run src/features/trading-workspace/monitorWorkspaceLoaders.test.ts
```

Expected:

```text
PASS.
```

- [ ] **Step 3: Write refresh state tests**

Create `frontend/src/features/trading-workspace/monitorRefreshState.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { createMonitorRefreshState } from "./monitorRefreshState";

describe("createMonitorRefreshState", () => {
  it("queues duplicate refreshes while a request is in flight", () => {
    const state = createMonitorRefreshState();
    expect(state.start({ includeRuntime: false })).toEqual({ status: "started", includeRuntime: false });
    expect(state.start({ includeRuntime: true })).toEqual({ status: "queued", includeRuntime: true });
  });

  it("merges includeRuntime for queued refreshes", () => {
    const state = createMonitorRefreshState();
    state.start({ includeRuntime: true });
    state.start({ includeRuntime: false });
    expect(state.finish()).toEqual({ next: { includeRuntime: true } });
  });

  it("clears the queue after the queued refresh is consumed", () => {
    const state = createMonitorRefreshState();
    state.start({ includeRuntime: false });
    state.start({ includeRuntime: true });
    state.finish();
    expect(state.finish()).toEqual({ next: null });
  });
});
```

Run:

```bash
cd frontend
npm test -- --run src/features/trading-workspace/monitorRefreshState.test.ts
```

Expected:

```text
FAIL because monitorRefreshState.ts does not exist yet.
```

- [ ] **Step 4: Implement refresh state machine**

Create `frontend/src/features/trading-workspace/monitorRefreshState.ts`:

```ts
export interface MonitorRefreshRequest {
  includeRuntime: boolean;
}

export interface MonitorRefreshStartResult {
  status: "started" | "queued";
  includeRuntime: boolean;
}

export function createMonitorRefreshState() {
  let inFlight = false;
  let queued: MonitorRefreshRequest | null = null;

  return {
    start(request: MonitorRefreshRequest): MonitorRefreshStartResult {
      if (inFlight) {
        queued = { includeRuntime: Boolean(queued?.includeRuntime || request.includeRuntime) };
        return { status: "queued", includeRuntime: queued.includeRuntime };
      }
      inFlight = true;
      return { status: "started", includeRuntime: request.includeRuntime };
    },
    finish(): { next: MonitorRefreshRequest | null } {
      const next = queued;
      queued = null;
      inFlight = Boolean(next);
      return { next };
    },
    reset() {
      inFlight = false;
      queued = null;
    },
  };
}
```

Run:

```bash
cd frontend
npm test -- --run src/features/trading-workspace/monitorRefreshState.test.ts
```

Expected:

```text
PASS.
```

- [ ] **Step 5: Refactor useMonitorData to call loader/state machine**

Modify `frontend/src/features/trading-workspace/useMonitorData.ts`:

- Replace direct `monitorRefreshRef` / `pendingMonitorRefreshRef` manipulation with `createMonitorRefreshState()`.
- Replace inline BFF first-screen logic in `fetchMonitorData` with `loadMonitorWorkspaceFirstScreen`.
- Keep existing public return shape unchanged.
- Keep lane-specific refresh behavior through `refreshActivePriorityLane`.
- Keep auth handling through `onAuthRequiredRef.current()`.
- Keep fallback to legacy only for explicit BFF disabled response.

Run:

```bash
cd frontend
npm test -- --run src/features/trading-workspace/useMonitorData.test.ts src/features/trading-workspace/useMonitorWorkspaceBff.test.ts src/features/trading-workspace/monitorWorkspaceLoaders.test.ts src/features/trading-workspace/monitorRefreshState.test.ts
```

Expected:

```text
PASS. Existing monitor route/lane tests still pass.
```

- [ ] **Step 6: Run smoke for request-count regression**

Run:

```bash
cd frontend
npm run build
npm run preview -- --host 127.0.0.1 > /tmp/gupiao-frontend-preview.log 2>&1 &
FRONTEND_SMOKE_URL=http://127.0.0.1:4173 node ./scripts/smoke-monitor-bff.mjs
```

Expected:

```text
dist/monitor-bff-smoke-report.json ok=true, bff_count=1, legacy_monitor_count=0.
```

- [ ] **Step 7: Full old frontend gate**

Run:

```bash
cd frontend
npm run typecheck
npm run lint
npm test -- --run
npm run build
```

Expected:

```text
All pass.
```

- [ ] **Step 8: Commit**

Run:

```bash
git add frontend/src/features/trading-workspace/useMonitorData.ts \
  frontend/src/features/trading-workspace/useMonitorData.test.ts \
  frontend/src/features/trading-workspace/useMonitorWorkspaceBff.ts \
  frontend/src/features/trading-workspace/useMonitorWorkspaceBff.test.ts \
  frontend/src/features/trading-workspace/monitorWorkspaceLoaders.ts \
  frontend/src/features/trading-workspace/monitorWorkspaceLoaders.test.ts \
  frontend/src/features/trading-workspace/monitorRefreshState.ts \
  frontend/src/features/trading-workspace/monitorRefreshState.test.ts
git commit -m "refactor: streamline legacy monitor workspace loading"
```

Expected:

```text
Commit contains only Batch 1 files.
```

---

### Batch 2: Unified Freshness And Degraded-State UI

**Purpose:** 统一旧前端推荐票、优先榜、选股宝典、最新数据状态的过期/降级/等待发布文案，避免不同页面给出不一致的交易风险暗示。

**Files:**
- Create: `frontend/src/features/workspace-shared/dataFreshnessViewModel.ts`
- Create: `frontend/src/features/workspace-shared/dataFreshnessViewModel.test.ts`
- Modify: `frontend/src/features/monitor/MonitorActionPage.tsx`
- Modify: `frontend/src/features/monitor/MonitorPage.helpers.ts`
- Modify: `frontend/src/features/playbook/PlaybookPage.tsx`
- Modify: `frontend/src/features/settings/LatestDataStatusCard.tsx`
- Modify: `frontend/src/features/workspace-shared/workspaceViewModels.ts`

- [ ] **Step 1: Write freshness view model tests**

Create `frontend/src/features/workspace-shared/dataFreshnessViewModel.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { buildDataFreshnessView } from "./dataFreshnessViewModel";

describe("buildDataFreshnessView", () => {
  it("marks stale recommendation snapshots as review-only", () => {
    expect(buildDataFreshnessView({
      stale: true,
      staleReason: "落后 2 个交易日",
      latestTradeDate: "2026-06-03",
      expectedTradeDate: "2026-06-05",
    })).toEqual({
      status: "stale",
      tone: "warn",
      title: "数据已过期，仅供复盘",
      detail: "落后 2 个交易日",
      tradeDateText: "2026-06-03 / 目标 2026-06-05",
      reviewOnly: true,
    });
  });

  it("keeps successful same-trade-date data usable", () => {
    expect(buildDataFreshnessView({
      status: "success",
      latestTradeDate: "2026-06-05",
      expectedTradeDate: "2026-06-05",
    }).reviewOnly).toBe(false);
  });

  it("uses waiting copy when data is not stale but not published yet", () => {
    const view = buildDataFreshnessView({
      status: "waiting",
      latestTradeDate: "2026-06-05",
      expectedTradeDate: "2026-06-05",
    });
    expect(view.status).toBe("waiting");
    expect(view.title).toBe("等待最新数据发布");
  });
});
```

Run:

```bash
cd frontend
npm test -- --run src/features/workspace-shared/dataFreshnessViewModel.test.ts
```

Expected:

```text
FAIL because dataFreshnessViewModel.ts does not exist yet.
```

- [ ] **Step 2: Implement freshness view model**

Create `frontend/src/features/workspace-shared/dataFreshnessViewModel.ts`:

```ts
export type DataFreshnessStatus = "ok" | "waiting" | "stale" | "degraded" | "blocked" | "no_data";
export type DataFreshnessTone = "up" | "warn" | "down" | "neutral";

export interface DataFreshnessInput {
  status?: string | null;
  stale?: boolean | null;
  staleReason?: string | null;
  dataQuality?: string | null;
  latestTradeDate?: string | null;
  expectedTradeDate?: string | null;
  detail?: string | null;
}

export interface DataFreshnessView {
  status: DataFreshnessStatus;
  tone: DataFreshnessTone;
  title: string;
  detail: string;
  tradeDateText: string;
  reviewOnly: boolean;
}

export function buildDataFreshnessView(input: DataFreshnessInput): DataFreshnessView {
  const tradeDateText = buildTradeDateText(input.latestTradeDate, input.expectedTradeDate);
  if (input.stale || input.dataQuality === "stale") {
    return {
      status: "stale",
      tone: "warn",
      title: "数据已过期，仅供复盘",
      detail: input.staleReason || input.detail || "当前展示最近可用快照，不作为今日观察依据。",
      tradeDateText,
      reviewOnly: true,
    };
  }
  if (input.status === "blocked" || input.dataQuality === "blocked") {
    return {
      status: "blocked",
      tone: "down",
      title: "数据暂不可用",
      detail: input.detail || "数据链路未满足生成条件。",
      tradeDateText,
      reviewOnly: true,
    };
  }
  if (input.status === "no_data" || input.dataQuality === "no_data") {
    return {
      status: "no_data",
      tone: "neutral",
      title: "暂无可用数据",
      detail: input.detail || "等待数据生成后再展示。",
      tradeDateText,
      reviewOnly: true,
    };
  }
  if (input.status === "degraded" || input.dataQuality === "degraded" || input.dataQuality === "partial") {
    return {
      status: "degraded",
      tone: "warn",
      title: "数据部分降级",
      detail: input.detail || "主链路可用，部分辅助数据暂缺。",
      tradeDateText,
      reviewOnly: false,
    };
  }
  if (input.status === "success" && sameDate(input.latestTradeDate, input.expectedTradeDate)) {
    return {
      status: "ok",
      tone: "up",
      title: "数据已更新",
      detail: input.detail || "当前数据可用于今日观察。",
      tradeDateText,
      reviewOnly: false,
    };
  }
  return {
    status: "waiting",
    tone: "neutral",
    title: "等待最新数据发布",
    detail: input.detail || "数据检查通过后会自动发布给前端使用。",
    tradeDateText,
    reviewOnly: false,
  };
}

function buildTradeDateText(latest?: string | null, expected?: string | null): string {
  if (latest && expected) return `${latest} / 目标 ${expected}`;
  return latest || expected || "--";
}

function sameDate(latest?: string | null, expected?: string | null): boolean {
  return Boolean(latest && expected && latest === expected);
}
```

Run:

```bash
cd frontend
npm test -- --run src/features/workspace-shared/dataFreshnessViewModel.test.ts
```

Expected:

```text
PASS.
```

- [ ] **Step 3: Apply view model to monitor priority board**

Modify `frontend/src/features/monitor/MonitorActionPage.tsx`:

- Use `buildDataFreshnessView` for `priorityBoard?.stale`, `priorityBoard?.stale_reason`, `priorityBoard?.latest_trade_date`, `priorityBoard?.data_quality`.
- Replace the inline stale callout title/detail with `view.title` and `view.detail`.
- Keep `StrategyLaneStatusCard`, `FamilyStrip`, and candidate list behavior unchanged.

Run:

```bash
cd frontend
npm test -- --run src/features/monitor/MonitorActionPage.test.tsx
```

Expected:

```text
PASS, including "surfaces stale priority board snapshots as review-only".
```

- [ ] **Step 4: Apply view model to playbook**

Modify `frontend/src/features/playbook/PlaybookPage.tsx`:

- Use `buildDataFreshnessView` when `playbook?.stale` or `playbook?.stale_reason` exists.
- Keep stale-date candidates visible in strategy lanes.
- Do not change candidate ranking or filtering.

Run:

```bash
cd frontend
npm test -- --run src/features/trading-workspace/PlaybookPage.test.tsx
```

Expected:

```text
PASS, including stale-date candidate visibility regression.
```

- [ ] **Step 5: Apply view model to latest data card**

Modify `frontend/src/features/settings/LatestDataStatusCard.tsx`:

- Replace local `latestDataView` logic with `buildDataFreshnessView`.
- Map `LatestLowBuyDataStatus` fields:
  - `status.status`
  - `status.local_staleness_trade_days > 0` -> stale
  - `status.local_latest_trade_date`
  - `status.calendar_expected_trade_date || status.expected_trade_date`
  - `status.staleness_trade_days`
- Preserve the existing management-token disabled behavior.

Run:

```bash
cd frontend
npm test -- --run src/features/settings/SettingsPage.test.tsx src/features/settings/LatestDataStatusCard.test.tsx
```

Expected:

```text
PASS if LatestDataStatusCard.test.tsx exists; otherwise run SettingsPage-related tests and add a focused test for latestData view behavior.
```

- [ ] **Step 6: Full gate**

Run:

```bash
cd frontend
npm run typecheck
npm run lint
npm test -- --run
```

Expected:

```text
All pass.
```

- [ ] **Step 7: Commit**

Run:

```bash
git add frontend/src/features/workspace-shared/dataFreshnessViewModel.ts \
  frontend/src/features/workspace-shared/dataFreshnessViewModel.test.ts \
  frontend/src/features/monitor/MonitorActionPage.tsx \
  frontend/src/features/monitor/MonitorPage.helpers.ts \
  frontend/src/features/playbook/PlaybookPage.tsx \
  frontend/src/features/settings/LatestDataStatusCard.tsx \
  frontend/src/features/workspace-shared/workspaceViewModels.ts
git commit -m "feat: unify legacy frontend data freshness states"
```

Expected:

```text
Commit contains only Batch 2 files.
```

---

### Batch 3: Route Bundle Budget And Lazy-Load Tightening

**Purpose:** 继续利用现有手动分包和预算脚本，防止旧前端首屏拉入回测、模拟盘、复杂设置页和重图表依赖。

**Files:**
- Modify: `frontend/scripts/bundle-report.mjs`
- Modify: `frontend/scripts/check-bundle-budget.mjs`
- Modify: `frontend/scripts/check-bundle-budget.test.mjs`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/.bundle-allowlist.json`
- Modify as needed: route/component files that accidentally pull heavy dependencies into `/monitor`

- [ ] **Step 1: Add route budget test coverage**

Modify `frontend/scripts/check-bundle-budget.test.mjs` to cover:

```js
import { describe, expect, it } from "vitest";
import { checkBundleBudget } from "./check-bundle-budget.mjs";

describe("checkBundleBudget route budgets", () => {
  it("fails when a lazy backtest chunk is classified as first-screen JS", () => {
    const violations = checkBundleBudget({
      first_screen_js_gzip_kb: 300,
      total_gzip_kb: 700,
      baseline_first_screen_js_gzip_kb: 400,
      assets: [
        { file: "BacktestPage-demo.js", gzip_kb: 30, kind: "first-screen-js" },
      ],
    }, { chunks: {} });

    expect(violations.some((item) => item.includes("BacktestPage"))).toBe(true);
  });
});
```

Run:

```bash
cd frontend
npm test -- --run scripts/check-bundle-budget.test.mjs
```

Expected:

```text
FAIL until check-bundle-budget understands route budget rules.
```

- [ ] **Step 2: Implement route budget guard**

Modify `frontend/scripts/check-bundle-budget.mjs`:

- Add forbidden first-screen prefixes:
  - `BacktestPage-`
  - `PaperTradingPage-`
  - `SettingsPage-`
  - `DataConsolePage-`
  - `StrategyTrackingPage-`
  - `echarts-`
- If any asset with those prefixes has `kind === "first-screen-js"`, fail with a clear message.
- Keep existing total/single-chunk/baseline checks.

Run:

```bash
cd frontend
npm test -- --run scripts/check-bundle-budget.test.mjs
```

Expected:

```text
PASS.
```

- [ ] **Step 3: Verify actual bundle classification**

Run:

```bash
cd frontend
npm run build
npm run analyze
node -e "const r=require('./dist/bundle-report.json'); console.log(r.assets.filter(a=>a.kind==='first-screen-js').map(a=>a.file).join('\n'))"
```

Expected:

```text
first-screen-js 不包含 BacktestPage/PaperTradingPage/SettingsPage/DataConsolePage/StrategyTrackingPage/echarts-*。
```

- [ ] **Step 4: Fix accidental heavy imports**

If Step 3 shows forbidden chunks in first screen:

- Move route-only imports behind existing lazy routes in `frontend/src/app/router/webRouteDefinitions.tsx` or `frontend/src/features/trading-workspace/TradingWorkspaceChrome.tsx`.
- Move chart imports behind existing `Lazy*Chart` or `MiniKlineChart` wrappers.
- Keep `WorkspaceRoute` shell light.

Run:

```bash
cd frontend
npm run build
npm run analyze
npm run lint
```

Expected:

```text
No forbidden first-screen route chunks. Bundle budget check passed.
```

- [ ] **Step 5: Update acceptance report**

Append to `docs/reports/legacy-frontend-optimization-acceptance-2026-06-06.md`:

```markdown
## Batch 3 Bundle Budget

- first_screen_js_gzip_kb before: `<value>`
- first_screen_js_gzip_kb after: `<value>`
- total_gzip_kb after: `<value>`
- forbidden lazy route chunks in first screen: `0`
- check-bundle-budget: `pass`
```

- [ ] **Step 6: Commit**

Run:

```bash
git add frontend/scripts/bundle-report.mjs \
  frontend/scripts/check-bundle-budget.mjs \
  frontend/scripts/check-bundle-budget.test.mjs \
  frontend/vite.config.ts \
  frontend/.bundle-allowlist.json \
  docs/reports/legacy-frontend-optimization-acceptance-2026-06-06.md
git add frontend/src/app/router/webRouteDefinitions.tsx frontend/src/features/trading-workspace/TradingWorkspaceChrome.tsx frontend/src/features || true
git commit -m "perf: tighten legacy frontend route bundle budgets"
```

Expected:

```text
Review staged diff before commit. Do not include unrelated files.
```

---

### Batch 4: Settings And Page Component Slimming

**Purpose:** 在不做大重构的前提下，把已接近阈值的旧前端页面拆成 view model + page shell，降低后续维护成本。

**Files:**
- Create: `frontend/src/features/settings/SettingsPage.viewModel.ts`
- Create: `frontend/src/features/settings/SettingsPage.viewModel.test.ts`
- Modify: `frontend/src/features/settings/SettingsPage.tsx`
- Modify if needed: `frontend/src/features/settings/SettingsPagePanels.tsx`
- Modify: `frontend/src/features/paper/PaperTradingPage.tsx`
- Modify if needed: `frontend/src/features/paper/paperTradingStatus.ts`

- [ ] **Step 1: Write Settings view model tests**

Create `frontend/src/features/settings/SettingsPage.viewModel.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { buildSettingsPageViewModel } from "./SettingsPage.viewModel";

describe("buildSettingsPageViewModel", () => {
  it("disables admin actions when the admin token is missing", () => {
    const view = buildSettingsPageViewModel({
      hasAdminToken: false,
      latestDataStatus: null,
      runtimeStatus: null,
    });

    expect(view.adminActionDisabled).toBe(true);
    expect(view.adminActionReason).toBe("需要填写管理令牌");
  });

  it("marks latest data refresh as available when token exists", () => {
    const view = buildSettingsPageViewModel({
      hasAdminToken: true,
      latestDataStatus: { status: "success", expected_trade_date: "2026-06-05", published_trade_date: "2026-06-05" } as any,
      runtimeStatus: null,
    });

    expect(view.adminActionDisabled).toBe(false);
  });
});
```

Run:

```bash
cd frontend
npm test -- --run src/features/settings/SettingsPage.viewModel.test.ts
```

Expected:

```text
FAIL because SettingsPage.viewModel.ts does not exist yet.
```

- [ ] **Step 2: Implement Settings view model**

Create `frontend/src/features/settings/SettingsPage.viewModel.ts`:

```ts
import type { LatestLowBuyDataStatus, RuntimeStatus } from "../../types";

export interface SettingsPageViewModelInput {
  hasAdminToken: boolean;
  latestDataStatus: LatestLowBuyDataStatus | null;
  runtimeStatus: RuntimeStatus | null;
}

export interface SettingsPageViewModel {
  adminActionDisabled: boolean;
  adminActionReason: string;
  latestDataReady: boolean;
  runtimeReadyChecks: number;
}

export function buildSettingsPageViewModel(input: SettingsPageViewModelInput): SettingsPageViewModel {
  const runtimeReadyChecks = input.runtimeStatus?.ready_checks?.filter((item) => item.ok).length ?? 0;
  const latestDataReady = Boolean(
    input.latestDataStatus?.status === "success" &&
    input.latestDataStatus?.published_trade_date &&
    input.latestDataStatus.published_trade_date === input.latestDataStatus.expected_trade_date,
  );
  return {
    adminActionDisabled: !input.hasAdminToken,
    adminActionReason: input.hasAdminToken ? "" : "需要填写管理令牌",
    latestDataReady,
    runtimeReadyChecks,
  };
}
```

Run:

```bash
cd frontend
npm test -- --run src/features/settings/SettingsPage.viewModel.test.ts
```

Expected:

```text
PASS.
```

- [ ] **Step 3: Slim SettingsPage.tsx**

Modify `frontend/src/features/settings/SettingsPage.tsx`:

- Move pure derived state to `buildSettingsPageViewModel`.
- Keep page layout and event handlers in `SettingsPage.tsx`.
- Do not move API calls into the view model.
- Target: reduce `SettingsPage.tsx` below 350 lines, or document why remaining lines are layout-only.

Run:

```bash
cd frontend
npm test -- --run src/features/settings/SettingsPage.viewModel.test.ts src/features/settings/DataQualityPanel.test.tsx
npm run typecheck
```

Expected:

```text
PASS.
```

- [ ] **Step 4: Apply the same pattern only where it reduces real complexity**

For `frontend/src/features/paper/PaperTradingPage.tsx`:

- Extract only pure status/action availability logic to `paperTradingStatus.ts` if not already present.
- Do not split presentational components solely to satisfy line counts.
- Keep action handlers and mutations in page/hook layer.

Run:

```bash
cd frontend
npm test -- --run src/features/paper
npm run typecheck
```

Expected:

```text
PASS.
```

- [ ] **Step 5: Full gate**

Run:

```bash
cd frontend
npm run lint
npm test -- --run
npm run build
```

Expected:

```text
All pass.
```

- [ ] **Step 6: Commit**

Run:

```bash
git add frontend/src/features/settings/SettingsPage.tsx \
  frontend/src/features/settings/SettingsPage.viewModel.ts \
  frontend/src/features/settings/SettingsPage.viewModel.test.ts \
  frontend/src/features/settings/SettingsPagePanels.tsx \
  frontend/src/features/paper/PaperTradingPage.tsx \
  frontend/src/features/paper/paperTradingStatus.ts
git commit -m "refactor: slim legacy settings and paper page view models"
```

Expected:

```text
Commit contains only page slimming changes.
```

---

### Batch 5: Core Workflow Browser Smoke

**Purpose:** 把旧前端核心链路从单测/类型检查提升到浏览器级验收，覆盖真实路由、懒加载、错误边界和关键文案。

**Files:**
- Create: `frontend/scripts/smoke-core-workflow.mjs`
- Modify: `frontend/package.json`
- Modify: `docs/reports/legacy-frontend-optimization-acceptance-2026-06-06.md`

- [ ] **Step 1: Add core workflow smoke script**

Create `frontend/scripts/smoke-core-workflow.mjs`:

```js
import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { mockStrategyMeta, mockUser, now } from "./smoke-responsive-fixtures.mjs";

const baseUrl = (process.env.FRONTEND_SMOKE_URL || "http://127.0.0.1:4173").replace(/\/$/, "");
const reportPath = resolve("dist", "core-workflow-smoke-report.json");
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1366, height: 900 }, serviceWorkers: "block" });
const page = await context.newPage();
const requests = [];
const errors = [];

page.on("request", (request) => {
  const url = new URL(request.url());
  if (url.pathname.startsWith("/api/")) requests.push(url.pathname);
});
page.on("pageerror", (error) => errors.push(String(error.message || error)));

await page.addInitScript(() => {
  localStorage.setItem("tquant:auth:persistence_mode", "session");
  sessionStorage.setItem("tquant:auth:access_token", "smoke-token");
});

await page.route("**/api/**", async (route) => {
  const url = new URL(route.request().url());
  const path = url.pathname.replace(/^\/api/, "");
  const json = (body, status = 200) => route.fulfill({
    status,
    contentType: "application/json; charset=utf-8",
    body: JSON.stringify(body),
  });

  if (path === "/auth/me") return json({ user: mockUser });
  if (path === "/auth/refresh") return json({ access_token: "smoke-token", refresh_token: "smoke-refresh", token_type: "bearer", expires_in: 3600, user: mockUser });
  if (path === "/strategies/meta") return json({ strategies: mockStrategyMeta });
  if (path === "/strategy/presets") return json({ presets: [] });
  if (path === "/bff/v1/workspace/monitor") return json(monitorWorkspacePayload());
  if (path.includes("playbook")) return json({ stale: false, candidates: [], lanes: [] });
  if (path.includes("backtest")) return json({ runs: [], summary: null });
  if (path.includes("paper")) return json({ account: null, positions: [], orders: [] });
  if (path.includes("settings") || path.includes("runtime") || path.includes("data")) return json({});
  return json({});
});

const checks = [];
for (const route of ["/monitor", "/playbook", "/backtest", "/paper", "/settings"]) {
  await page.goto(`${baseUrl}${route}`, { waitUntil: "networkidle", timeout: 20_000 });
  const text = await page.locator("body").innerText();
  checks.push({ route, ok: text.length > 20 && !text.includes("页面加载失败") && !text.includes("加载失败，正在重试") });
}

await context.close();
await browser.close();
await mkdir(resolve("dist"), { recursive: true });

const report = {
  ok: checks.every((item) => item.ok) && errors.length === 0,
  checks,
  requests,
  errors,
  generated_at: new Date().toISOString(),
};
await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(reportPath);
if (!report.ok) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}

function monitorWorkspacePayload() {
  return {
    api_version: "v1",
    schema_version: "smoke",
    generated_at: now,
    monitor_snapshot: {
      priority_board: {
        latest_trade_date: "2026-06-05",
        stale: false,
        data_quality: "ok",
        items: [],
      },
      watchlist_signals: [],
      sector_etf_t0: null,
    },
    market_breadth: null,
    market_pulse: null,
    review_reports: [],
    review_status: null,
    sector_relative_strength: null,
    paired_hedge: null,
    hourly_snapshot_history: [],
    partial_errors: [],
  };
}
```

Run:

```bash
cd frontend
npm run build
npm run preview -- --host 127.0.0.1 > /tmp/gupiao-frontend-preview.log 2>&1 &
FRONTEND_SMOKE_URL=http://127.0.0.1:4173 node ./scripts/smoke-core-workflow.mjs
```

Expected:

```text
dist/core-workflow-smoke-report.json ok=true.
```

- [ ] **Step 2: Add package script**

Modify `frontend/package.json`:

```json
"smoke:core-workflow": "node ./scripts/smoke-core-workflow.mjs"
```

Run:

```bash
cd frontend
npm run smoke:core-workflow
```

Expected:

```text
dist/core-workflow-smoke-report.json ok=true.
```

- [ ] **Step 3: Add stale snapshot smoke scenario**

Extend `frontend/scripts/smoke-core-workflow.mjs`:

- Read `CORE_WORKFLOW_SMOKE_SCENARIO`.
- If scenario is `stale`, return `priority_board.stale=true` and `stale_reason`.
- Verify `/monitor` body includes `仅供复盘` or `数据已过期`.

Run:

```bash
cd frontend
CORE_WORKFLOW_SMOKE_SCENARIO=stale FRONTEND_SMOKE_URL=http://127.0.0.1:4173 npm run smoke:core-workflow
```

Expected:

```text
Report ok=true and stale scenario verifies review-only copy.
```

- [ ] **Step 4: Full gate**

Run:

```bash
cd frontend
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run smoke:monitor-bff
npm run smoke:core-workflow
CORE_WORKFLOW_SMOKE_SCENARIO=stale npm run smoke:core-workflow
```

Expected:

```text
All pass.
```

- [ ] **Step 5: Update acceptance report**

Append:

```markdown
## Batch 5 Browser Smoke

- monitor BFF smoke: `pass`
- core workflow smoke: `pass`
- stale workflow smoke: `pass`
- routes covered: `/monitor`, `/playbook`, `/backtest`, `/paper`, `/settings`
```

- [ ] **Step 6: Commit**

Run:

```bash
git add frontend/scripts/smoke-core-workflow.mjs frontend/package.json docs/reports/legacy-frontend-optimization-acceptance-2026-06-06.md
git commit -m "test: add legacy frontend core workflow smoke"
```

Expected:

```text
Commit contains smoke script, package script, and report update.
```

---

## Final Verification

Run from repository root:

```bash
git status --short
cd frontend
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run analyze
npm run smoke:monitor-bff
npm run smoke:core-workflow
CORE_WORKFLOW_SMOKE_SCENARIO=stale npm run smoke:core-workflow
```

Expected final state:

```text
- Old frontend checks pass.
- /monitor normal smoke: BFF request count is 1, legacy monitor request count is 0.
- Core route smoke passes for /monitor, /playbook, /backtest, /paper, /settings.
- Stale recommendation smoke shows review-only copy.
- Bundle budget check passes and no forbidden lazy route chunk is first-screen-js.
- git status contains only intended tracked changes plus pre-existing unrelated files.
```

## Rollback

- Batch 1 rollback: revert `monitorWorkspaceLoaders.ts`, `monitorRefreshState.ts`, and `useMonitorData.ts` refactor; set `VITE_MONITOR_BFF_AGGREGATE_ENABLED=false` for runtime fallback.
- Batch 2 rollback: revert `dataFreshnessViewModel.ts` usage; page-local stale callouts return to prior behavior.
- Batch 3 rollback: revert bundle script/vite changes; keep report evidence explaining why.
- Batch 4 rollback: revert page view model extraction only; no API/schema change.
- Batch 5 rollback: remove smoke script and package script; production runtime unaffected.

## Execution Options

1. **Subagent-Driven (recommended):** one fresh subagent per batch, review and test after each commit.
2. **Inline Execution:** execute batches in this session with checkpoints after every batch.

