# 前端渲染性能 · 最终方案（端态，非过渡）

> 日期：2026-05-30　范围：Web 前端渲染性能　栈：React 18 + TS + Vite(rolldown) + AntD 6.4.3 + Zustand + TanStack Query + ECharts
> 性质：**只出方案，不改代码**。给出端态架构 + 精确改动点 + 验收，不分“先试一版再说”的过渡步骤。

## 0. 先说结论（基于实测，避免误导）

- **不换语言、不换框架、不引 WASM。** 你的构建层已优化到位（路由 lazy、echarts 手动分包、`react-vendor` 拆分、`npm run analyze` 已测 gzip），ECharts 已是教科书级（canvas renderer + 手动实例 + `setOption(opt,true,true)` + 全部 `Lazy*Chart`）。换栈只会丢掉 3.7 万行 + 移动端/Capacitor + 生成类型 + 测试，且**解决不了**真正的重量来源（AntD ~1MB + ECharts ~580K 是选型固有成本）。
- **当前并非“几百行未虚拟化导致卡死”**：你的表格已用分页（`StrategyTrackingTable` 服务端分页 pageSize 30）、`scroll={{y}}`、卡片用 `.slice(0,N)` 兜底。所以这是**把“临时的分页/截断兜底”升级成“一套统一虚拟化标准”**，收益是：去掉人为 `slice` 截断（用户看全量）、去掉翻页点击、数据增长时 DOM 恒定、并永久防回退。
- **最大杠杆是一个文件**：几乎所有表格都走共享 `src/ui/table/DataTable.tsx`。把它做成**虚拟化默认开**，全站表格一次性受益。

---

## 1. 最终渲染架构（端态，四根支柱）

> 一种布局只用一种工具，互不重叠，全部基于“已安装/已具备”的能力。

### 支柱 1 —— 表格统一走 AntD 原生虚拟化（经共享 `DataTable`）
- **决策**：大表统一用 **AntD `<Table virtual scroll={{ y }}>`**（AntD 6.4.3 原生支持），**不**用 `react-virtual` 做表格——因为 AntD 虚拟表原生保留列定义、排序、筛选、固定列，迁移成本最低、回归面最小。
- **落点（一个文件辐射全站）**：升级 `src/ui/table/DataTable.tsx`：
  - 默认 `virtual` 开、默认给一个有界 `scroll={{ y: <默认高度> }}`（调用方可覆盖 `x/y`）；
  - 新增 `paginated?: boolean` 显式开关：**扫描型大表默认虚拟滚动（不分页）**，仅“配置型小表/天然需要分页的服务端超大集”显式 `paginated`。
- **迁移清单（已查到的表格，按是否扫描型分流）**：
  - 转虚拟滚动（去客户端分页/铺全量）：`StrategyTrackingTable`(现 pageSize30)、`StrategyTrackingPerformanceTable`(现 `pagination=false` 直接铺)、`PaperDetailTabs` 成交/持仓表、`BacktestDashboard.panels` 成交/归因表、`EtfUniverseAdminCard`(ETF 全集可大)、`FactorMiningTab`、`MLCapacityPanel`、`EtfT0OosPanel`/`EtfT0BacktestPanel`。
  - 保持分页/小表不变：`StrategyTrackingHoldingAnalysisPanel`(pageSize10)、`StrategyTrackingDetailDrawer`(12)、`StrategyTrackingDiagnosticsPanel`(8) 等天然小数据集。
- **例外规则（必须在迁移时甄别）**：AntD 虚拟表要求**固定行高 + 必须设 `scroll.y`**，且与 `expandable` 展开行、`rowSpan` 合并单元格、行内可变高度**不兼容**。命中这些的表 → 保持分页或拆成“列表 + 详情抽屉”，不强转虚拟。

### 支柱 2 —— 卡片/自定义列表统一走 `@tanstack/react-virtual`（已安装、当前零使用）
- **决策**：非 `<Table>` 的卡片列、自定义行布局，用 `@tanstack/react-virtual` 建**一个** `src/ui/list/VirtualCardList.tsx`（支持动态测高 `measureElement`，适配卡片不等高）。
- **落点 + 同时去掉人为截断**（这是“非过渡”的关键：不再靠 `slice` 藏数据）：
  - `MonitorPage` 优先榜卡片（现 `priorityCards.slice(0,12)`）、自选卡片（`watchCards.map` 无界）、板块 ETF（`opportunities.slice(0,6)`）→ 用 `VirtualCardList` 铺全量；
  - `app-preview/portfolio.tsx`、`paper/PaperPositionDetailsPanel.tsx` 等卡片列同理。
  - 截断从“限制 DOM 的 workaround”改为“仅业务上确需 Top-N 时才保留”（如首屏摘要），其余放开。

### 支柱 3 —— 渲染隔离作为永久规则
- **现状（已半成）**：`MonitorPage` 已 `memo` + 用**窄单字段** store selector（`useWorkspaceMonitorStore(s => s.activeStrategyLane)`），方向正确。
- **端态规则**：
  - 每个卡片/行抽成 `memo` 叶子组件，**只吃自己那条 item**（按 `id` key），使一次 30s 轮询/价格 tick 只重渲染变化的那张卡，而非整页；
  - store 订阅一律窄字段 selector；确需多字段时用 `useShallow`（当前全站未用，但因多为单字段订阅，按需引入即可）；
  - 重派生（`MonitorPage` 里 `resolveTodayAction/buildPriorityNotice` 等 `useMemo` 链）下沉为 store 派生或 `select`，避免每次数据刷新整页重算。

### 支柱 4 —— 永久护栏（保证“端态不回退”）
- 约定 + lint：新大列表只能用 `DataTable`(virtual) 或 `VirtualCardList`；**禁止**用 `<Table pagination>` + `.slice()` 作为控制行数的手段。
- 写入 `frontend` 开发规范；可加一条自定义 ESLint 规则或 PR checklist 项。

---

## 2. 明确不做（最终取舍）
| 选项 | 裁决 | 原因 |
|---|---|---|
| 换 Solid/Svelte/Qwik 等框架 | ❌ | 丢掉现有栈与移动端/测试，解决不了 AntD/ECharts 重量 |
| Rust/WASM 做前端计算 | ❌ | 重计算已在后端 Rust(`tquant_rs`)，前端无 CPU 热点 |
| `react-virtual` 做表格 | ❌ | AntD 原生虚拟表已够且保留列/排序/筛选，避免两套虚拟系统 |
| 动 ECharts | ❌ | 已最优（canvas + 手动实例 + lazy），改动只会引入风险 |
| Web Worker | ⏸ 仅按需 | 仅当支柱 3 下沉后 Profiler 仍显示主线程大数组变换卡顿才上；非默认项 |

---

## 3. 落地改动点（一个变更集，一次到位）

1. `src/ui/table/DataTable.tsx`：加 `virtual` 默认、有界 `scroll.y` 默认、`paginated` 显式开关；导出不变（向后兼容）。
2. 新增 `src/ui/list/VirtualCardList.tsx`（`@tanstack/react-virtual`，动态测高）。
3. 迁移支柱 1 的扫描型表 → 走 `DataTable`（去客户端分页）；甄别 `expandable`/`rowSpan`/可变行高的表走例外。
4. 迁移支柱 2 的卡片列 → `VirtualCardList`，移除非业务性的 `slice(0,N)` 截断。
5. 抽卡片/行为 `memo` 叶子组件；重派生下沉 store/`select`。
6. 加护栏（规范 + lint/checklist）。

> 全部不涉及后端、不涉及路由结构、不涉及构建配置；ECharts 不动。

---

## 4. 验收（测得到、可回归）

- **量化**：用已有 `npm run analyze`（`scripts/bundle-report.mjs` 已出 gzip/首屏）确认 bundle 不退化（本方案基本不增包：`react-virtual` 已在 deps，AntD virtual 是 AntD 内置）。
- **渲染**：React DevTools Profiler 录“监控页一次 30s 刷新”“策略跟踪表滚动”“回测成交表滚动”：
  - 刷新时只重渲染变化的卡/行（提交数与变化项数量级一致），而非整页；
  - 大表滚动稳定 ~60fps；DOM 节点数随数据量**不再线性增长**（恒定可视行）。
- **功能不回归**：迁移后的表列定义、排序、筛选、固定列、空态与原一致；移除 `slice` 后列表展示全量且滚动流畅。
- **护栏生效**：新增一个违规用法（raw `<Table pagination>` + `.slice()` 大列表）能被 lint/checklist 拦下。

## 5. 风险与处置
| 风险 | 处置 |
|---|---|
| AntD 虚拟表需固定行高 + `scroll.y` | 统一行高；不规则高度的表走例外（保留分页或列表+抽屉） |
| `expandable`/`rowSpan` 与虚拟表冲突 | 迁移前甄别，命中者不转虚拟 |
| 卡片不等高导致跳动 | `VirtualCardList` 用 `measureElement` 动态测高 |
| 移除 `slice` 后一次性数据量增大 | 数据仍由后端分页/物化提供上限；虚拟化只渲染可视行，DOM 不随之增长 |
| 移动端（antd-mobile）单独栈 | 本方案聚焦 Web；移动端卡片如需同样处理，复用 `VirtualCardList`（与 antd-mobile 列表择一，不混用） |

---

## 6. 一句话总结
**把已存在的共享 `DataTable` 升级为 AntD 原生虚拟表（一个文件辐射全站）+ 用已安装的 `react-virtual` 建一个 `VirtualCardList` 去掉 `slice` 截断 + 卡片/行做 memo 叶子隔离 + 加一条护栏。** 这是端态：一套表格虚拟化标准、一套列表虚拟化标准、渲染隔离成规则、回退被 lint 拦住。投入约 1 周，不换语言、不换框架、不动 ECharts。
