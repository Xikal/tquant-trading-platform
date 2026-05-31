# Frontend Architecture Hardening Implementation Plan (2026-05-30)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 或 superpowers:executing-plans，按 Task 逐步实现。Steps 用 `- [ ]` 跟踪。
>
> **定位：** 把现有前端栈收口到“数据密集型内部交易看板”的理想端态——**强化、非重写、非过渡、非过度**。**不换** React 18 / TypeScript / Vite / AntD / ECharts；**不上** SSR/Next、**不引** WASM、**不做**微前端。只做三件结构性强化：① 服务端/客户端状态硬分离；② 实时热路径信号化 + SSE；③ 单一虚拟化网格 + 响应式单代码库。
>
> **依据：** 本项目是登录后访问、用户量小、组件密集（企业表格/表单 + ECharts）、重计算在后端（Rust/Python）的实时决策看板。架构由“组件生态 + 数据网格/图表渲染 + 服务端状态缓存”主导，而非渲染内核微观性能或 SSR。换框架/SSR/WASM 即便免费也不解决真实瓶颈，故明确排除。

**Goal:** 在不换技术栈的前提下，消除看板的两个真实瓶颈——**轮询/tick 触发的整页重渲染**与**服务端状态被复制进多个 store 的漂移**——并把表格/图表/移动端收敛为单一标准，使前端达到“可扩展不返工”的端态。

**Tech Stack（保持，唯一新增见 F2）：** React 18 + TypeScript + Vite(rolldown) + Ant Design 6 + Zustand + TanStack Query + ECharts(canvas) + @tanstack/react-virtual + Vitest。**唯一新增依赖：`@preact/signals-react`**（在 React 内部做细粒度更新，非框架替换）。

---

## Scope And Non-Goals

**In scope**
- F1：TanStack Query 独占服务端状态；Zustand 仅 UI 临时态；渲染隔离（窄 selector + memo 叶子）；lint 护栏扩展。
- F2：实时高频字段（行情价/涨跌/买点状态）信号化（单元格级更新）；真实时数据改 SSE 推送；ECharts 命令式岛规则固化。
- F3：收敛单一虚拟化网格原语；退役 antd-mobile/桌面双栈为**响应式单代码库**（Capacitor 仅作可选壳）。

**Out of scope / 明确排除（即便不计成本也不做）**
- 不换 React/AntD/Vite/ECharts；不引 SolidJS/Svelte/Qwik。
- 不上 SSR/RSC（Next/Remix）：登录后内部 SPA，无 SEO、无规模首屏压力。
- 不引 WASM 前端：重计算在后端。
- 不做微前端 / module federation。
- 不改后端 API 与契约（纯前端架构收口；类型仍来自 `generated/api-types`）。
- signals 不替代 TanStack Query，不“全站信号化”，只用于实时热路径。

---

## 硬边界（不可跑偏 · 实现期必须始终成立）

1. **技术栈冻结**：React 18 + TS + Vite + AntD 6 + ECharts 不变；不上 SSR、不引 WASM、不做微前端。唯一新增依赖 `@preact/signals-react`。
2. **服务端状态唯一真源 = TanStack Query**：禁止把服务端响应数据复制进 Zustand store；store 只放 UI 临时态（选中/展开/tab/筛选草稿/lane 切换）。
3. **零 `useState`/`useReducer` 维持**（`check-refactor-guard.mjs` 现有规则不回退）；新增护栏：禁止 store 字段命名/类型暗示服务端数据（评审 + 约定）。
4. **signals 仅用于实时热路径**（行情价、涨跌幅、买点状态等高频字段），单元格/叶子级订阅；不得污染普通组件、不得替代 Query 缓存。
5. **表格唯一走虚拟化网格原语，长列表走 `VirtualCardList`**；新增/扩展面板默认懒加载、不进首屏关键路径。
6. **ECharts 命令式岛**：保持 canvas renderer + 手动 `init`/`setOption(opt,true,true)`/`dispose`；图表不随 React 重渲染重建实例。
7. **契约类型唯一来源 = `frontend/src/generated/api-types.ts`**；手写类型只能是 UI ViewModel。
8. **性能预算门**：`npm run analyze` 首屏 gzip 不得因本计划上升；关键页 Profiler 提交数随“变化项数量级”而非“整页”。

---

## Existing Code Anchors（复用/收口，勿重写）

- 服务端状态：`@tanstack/react-query`（已装）、`frontend/src/features/strategy-tracking/queries.ts`（已有 query 封装样例）、`frontend/src/api/{base.ts,client.ts}`
- 客户端 store（18 个）：`frontend/src/stores/*`（`workspaceMonitorStore.ts`、`paperTradingStore.ts`、`strategyTrackingStore.ts`、`workspaceStore.ts` 等）
- 虚拟化原语：`frontend/src/ui/table/DataTable.tsx`（默认 AntD virtual + scroll.y）、`frontend/src/ui/list/VirtualCardList.tsx`（`@tanstack/react-virtual`，动态测高）
- 渲染护栏：`frontend/scripts/check-refactor-guard.mjs`（禁 useState/useReducer/raw Table/slice 截断/native form）
- ECharts 岛：`frontend/src/ui/charts/LazyKlineChart.tsx`、`frontend/src/features/backtest/Lazy*Chart.tsx`（canvas + 手动实例，端态范本）
- 实时通道：后端 `backend/app/api/routes/strategy_stream.py`（ws/SSE router）；前端实时消费入口（EventSource/WS）
- 行情热字段来源：`frontend/src/features/monitor/MonitorPage.tsx`（memo + 窄 selector，30s 轮询）、`useMonitorData.ts`、`features/trading-workspace/useMonitorData.ts`
- 移动端双栈：`frontend/src/mobile/*`（`MobileApp.tsx`、`MobileTabSections.tsx`、`MobileDesignCards.tsx`）、`antd-mobile` 依赖、`main-native.tsx`、`index.native.html`、`capacitor.config.ts`、`android/`、`ios/`、`dist-native`
- 构建/预算：`frontend/vite.config.ts`（splitVendorChunks）、`frontend/scripts/bundle-report.mjs`（gzip + first_screen）、`package.json` scripts（`api:check`/`lint`/`build`/`test`/`analyze`）
- 契约类型：`frontend/src/generated/api-types.ts`

## File Structure Plan

**Create**
- `frontend/src/state/queryClient.ts`（统一 QueryClient + 默认 staleTime/gcTime/refetchOnWindowFocus=false/structuralSharing）
- `frontend/src/state/serverQueries/*.ts`（按域归并的 query hooks：monitor/paper/strategyTracking/backtest/settings）
- `frontend/src/state/realtime/liveQuoteSignals.ts`（signals store：symbol→价格/涨跌/买点状态）
- `frontend/src/state/realtime/useQuoteStream.ts`（SSE 订阅 → 写 signals）
- `frontend/src/ui/grid/VirtualGrid.tsx`（唯一虚拟化网格原语，吸收 DataTable virtual 能力）
- `frontend/src/ui/realtime/LiveCell.tsx`（信号驱动的单元格组件）
- `frontend/scripts/check-state-separation.mjs`（护栏：扫 store 里疑似服务端数据 + 实时字段未走 signals）
- 测试：`*.test.tsx`（见各 Task）

**Modify**
- `frontend/src/main.tsx`（挂统一 QueryClient + signals runtime）
- `frontend/src/stores/*`（剥离其中的服务端数据，只留 UI 态）
- `frontend/src/features/monitor/MonitorPage.tsx`、`useMonitorData.ts`、`features/trading-workspace/*`（行情热字段改 signals + LiveCell；服务端数据改 query hooks）
- `frontend/src/features/{paper,strategy-tracking,backtest}/*`（表格统一走 `VirtualGrid`；服务端数据走 query hooks）
- `frontend/src/ui/table/DataTable.tsx`（保留为 `VirtualGrid` 的 AntD 适配壳或收敛）
- `frontend/scripts/check-refactor-guard.mjs`（接入 state-separation 检查）
- `frontend/package.json`（新增 `@preact/signals-react`；`lint` 串联新护栏）
- `frontend/vite.config.ts`（如需为 signals 配 babel 插件）
- F3：`frontend/src/mobile/*`、`main-native.tsx`、`index.native.html`、`capacitor.config.ts`、`package.json`（退役双栈，见 F3）

## Milestones（3 批，独立可合入/回滚，按结构价值/风险排序）

### M0 基线（0.5d）
- `npm run analyze` 记录首屏 gzip 基线；`npm test -- --run` 全绿；React Profiler 录“监控页一次 30s 刷新”“大表滚动”作为对照基线。

### Batch F1｜服务端/客户端状态硬分离 + 渲染隔离（地基，先做）
结构最高价值、用户可见风险最低。出口：服务端数据只在 TanStack Query；store 仅 UI 态；护栏拦截违规；轮询不再触发整页重渲染。

### Batch F2｜实时热路径信号化 + SSE
出口：行情高频字段经 SSE→signals→`LiveCell` 单元格级更新；一次 tick 只更新对应单元格；ECharts 岛规则固化。

### Batch F3｜单一虚拟化网格 + 响应式单代码库
出口：全站表格走 `VirtualGrid`；antd-mobile/桌面双栈合一为响应式单代码库，Capacitor 仅可选壳。**（效率最大、可作为最后批；若产品确需原生再保留壳）**

---

## Batch F1 Tasks

### Task F1-1: 统一 QueryClient 与服务端 query 层
- [ ] 失败测试：`queryClient.test.ts` 断言默认 `refetchOnWindowFocus=false`、合理 `staleTime/gcTime`、`structuralSharing=true`。
- [ ] `state/queryClient.ts` 集中配置；`main.tsx` 挂载（替换分散配置）。
- [ ] 按域建 `state/serverQueries/*`：把现有散落 fetch（`api/client.ts` 调用）收敛为 typed query hooks，类型取自 `generated/api-types`，`select` 取片、`enabled` 控依赖。
- [ ] 测试：query hook 命中缓存、`select` 只返回所需片。

### Task F1-2: store 去服务端化（只留 UI 态）
- [ ] 失败测试：`check-state-separation` 对“store 里存在服务端数据形状”的样例报错。
- [ ] 逐个 `stores/*`：移除被复制进来的服务端数据字段（候选榜、持仓、回测结果等），改由组件用 query hooks 读；store 只保留选中/展开/tab/筛选草稿/lane 等 UI 态。
- [ ] 新增 `scripts/check-state-separation.mjs`：静态扫描 store 字段命名/类型是否疑似服务端 DTO（与 `generated/api-types` 形状比对，命中则报错），并接入 `npm run lint`。
- [ ] 测试：关键页（监控/纸面/策略追踪）数据仍正确渲染（vitest 渲染测试），store 不再持有服务端数据。

### Task F1-3: 渲染隔离（窄 selector + memo 叶子）
- [ ] 失败测试：用 Profiler/渲染计数断言——模拟一次服务端刷新，仅变化的卡/行重渲染，非整页。
- [ ] 把列表项/卡片抽成 `memo` 叶子组件，只吃自己那条 item（按 id key）；多字段 store 订阅改 `useShallow`；重派生下沉为 query `select` 或 store 派生。
- [ ] 测试：监控页一次刷新提交数与变化项数量级一致。

---

## Batch F2 Tasks

### Task F2-1: 行情热字段信号化
- [ ] 新增 `@preact/signals-react`（+ 必要 babel 插件）；`liveQuoteSignals.ts`：`Map<symbol, {price, changePct, signalState}>` 的 signals。
- [ ] 失败测试：更新单个 symbol 的 price signal，仅对应 `LiveCell` 重渲染，父表/兄弟单元格不重渲染。
- [ ] `LiveCell.tsx`：读取 signal 渲染价格/涨跌/买点状态，用于表格热列与监控卡热字段。
- [ ] 边界：signals 只承载高频字段；其余仍走 query。测试覆盖“信号更新不触发表格整体重渲染”。

### Task F2-2: SSE 实时传输
- [ ] `useQuoteStream.ts`：EventSource 订阅后端实时通道（复用 `strategy_stream` 或新增报价 SSE 端点——若后端无则本 Task 仅接已有流，缺端点列入“需后端配合”，不自造假数据）。
- [ ] 失败测试：SSE 推送 → 写入 `liveQuoteSignals` → `LiveCell` 更新；断线重连与降级回轮询。
- [ ] 把监控页价格刷新从“30s 轮询整表”切到“SSE 改热字段 + 低频轮询非实时数据”。
- [ ] 测试：断线回退轮询；无 SSE 时不阻塞页面。

### Task F2-3: ECharts 命令式岛规则固化
- [ ] 失败测试：图表组件 props 变化只触发 `setOption`，不重建实例；卸载 `dispose`。
- [ ] 把现有 `Lazy*Chart` 模式收敛为统一 `ChartIsland` 约定（canvas + 手动 init + `setOption(opt,true,true)` + resize 节流 + dispose）；新增图表必须走该约定。
- [ ] 护栏：`check-refactor-guard` 增“图表不得用 echarts-for-react 全量重渲染模式”检查（可选）。

---

## Batch F3 Tasks

### Task F3-1: 单一虚拟化网格原语
- [ ] `ui/grid/VirtualGrid.tsx`：吸收 `DataTable` 的 AntD virtual + scroll.y + 列/排序/筛选能力，作为全站唯一表格入口；`DataTable` 收敛为其薄壳或别名。
- [ ] 失败测试：500 行只渲染可视行；排序/筛选/固定列保持；`expandable`/可变行高场景明确走非虚拟分支。
- [ ] 迁移 `paper/strategy-tracking/backtest` 表格到 `VirtualGrid`；`check-refactor-guard` allowlist 收敛到 `VirtualGrid`。

### Task F3-2: 响应式单代码库（退役 antd-mobile/桌面双栈）
- [ ] 失败测试：关键页在窄视口（移动断点）渲染正确（vitest + 视口模拟），不再依赖 `src/mobile/*` 分叉。
- [ ] 用 AntD 响应式（Grid/断点）+ 既有 `VirtualGrid`/`VirtualCardList` 把桌面页做成响应式；逐页替换 `mobile/MobileApp.tsx`/`MobileTabSections.tsx`/`MobileDesignCards.tsx` 的并行实现。
- [ ] 退役 `antd-mobile` 依赖、`main-native.tsx`/`index.native.html`/`dist-native` 分叉；**Capacitor 保留为可选壳**（包响应式 Web），`android/ios` 工程保留但不再维护并行 UI。
- [ ] 测试：桌面/移动断点同一代码路径；`npm run analyze` 移除 antd-mobile 后首屏 gzip 下降。
- [ ] 说明：F3-2 是“不计成本”的端态目标；若产品确需原生独立体验，可只做 F3-1 并保留双栈，本 Task 单独决策。

---

## Acceptance Matrix

| 能力 | 端态行为 | 必测/护栏 |
|---|---|---|
| 服务端状态 | 只在 TanStack Query；store 无服务端数据 | `check-state-separation.mjs` + query hook 测试 |
| 渲染隔离 | 一次刷新仅变化项重渲染 | Profiler/渲染计数测试 |
| 实时热路径 | tick 单元格级更新，不重渲染表 | `LiveCell` 信号测试 |
| SSE | 推送更新热字段，断线回退轮询 | `useQuoteStream` 测试 |
| 图表岛 | props 变化只 setOption、卸载 dispose | ChartIsland 测试 |
| 虚拟化网格 | 全站表格走 VirtualGrid，大表恒定 DOM | VirtualGrid 测试 + guard |
| 响应式单栈 | 桌面/移动同一代码路径 | 视口渲染测试 + analyze 下降 |

## Verification Commands（每批结尾）
```bash
cd frontend
npm run api:check          # 契约类型不漂移
npm run lint               # 含 check-refactor-guard + check-state-separation
npm test -- --run          # vitest 全绿（含新增渲染隔离/信号/网格用例）
npm run build
npm run analyze            # 首屏 gzip 不上升（F3 后应下降）
```
- 性能预算门：`analyze` 首屏 gzip ≤ M0 基线；F1/F2 后用 Profiler 复测“监控页一次刷新”提交数显著下降；F3 后 antd-mobile 移除使首屏下降。

## Rollback
- 三批独立可回退（互不依赖生产生效）。
- F1：query 层与 store 改动可按域分 PR；护栏 `check-state-separation` 可先 warn 后 error。
- F2：signals/SSE 用运行时开关（如 `VITE_LIVE_QUOTE_SIGNALS=false`）回退到轮询路径；`@preact/signals-react` 仅热路径引用，移除影响面小。
- F3：`VirtualGrid` 回退为 `DataTable`；响应式单栈未完成前**保留 mobile 双栈**，按页灰度替换，不一刀切。

## Definition Of Done
- 服务端数据仅在 TanStack Query；`stores/*` 仅 UI 态；`check-state-separation` 纳入 `lint` 并通过。
- 行情高频字段经 signals 单元格级更新；监控页一次刷新不再整页重渲染（Profiler 证据）。
- 真实时数据走 SSE，断线回退轮询；ECharts 岛规则固化（canvas+手动实例+dispose）。
- 全站表格走单一 `VirtualGrid`；（F3-2 若执行）antd-mobile 双栈退役为响应式单代码库，Capacitor 仅可选壳，首屏 gzip 下降。
- 零 `useState/useReducer` 维持；契约类型唯一来源不变；未换 React/AntD/Vite/ECharts、未引 SSR/WASM/微前端。
- `api:check`/`lint`/`build`/`vitest`/`analyze` 全绿，首屏 gzip ≤ 基线。
```
