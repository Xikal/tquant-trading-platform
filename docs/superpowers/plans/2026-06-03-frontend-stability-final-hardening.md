# Frontend Stability Final Hardening Implementation Plan (2026-06-03)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 或 superpowers:executing-plans，按 Task 逐步实现。Steps 用 `- [ ]` 跟踪。
>
> **定位（基于实测的最终结论）：** 当前前端"加载慢、不稳定"**不是架构问题**——架构强化（queryClient/signals/VirtualGrid/LiveCell/ECharts 命令式岛/lazy 路由/refactor guard/state-separation guard）**已经全部落地**。剩下的真实问题集中在三件具体的事：① 首屏关键路径上 AntD 一体包仍 ~483K（gz ~155K）占首屏 60%+；② `Topbar.tsx:49` 每秒 `setInterval` 写 Zustand store 触发跨页重渲染；③ 后端尾延迟（market-read Redis 命中 ~20% + BFF partial timeout）传成前端"卡顿"。本计划是**收尾性最终方案**，不换 React/AntD/Vite、不上 SSR/WASM/微前端、不再做框架级升级。
>
> **关联**：`docs/superpowers/plans/2026-05-30-frontend-architecture-hardening.md`（架构强化，已落地 F1/F2/F3 主体）；`docs/superpowers/plans/2026-05-30-backend-performance-hardening.md`（G1/G2/G3 后端性能强化）；`frontend/scripts/check-refactor-guard.mjs`、`frontend/scripts/check-state-separation.mjs`、`frontend/scripts/bundle-report.mjs`。

**Goal:** 把用户感知到的"前端慢/不稳定"在不换栈、不返工的前提下收口到端态：**首屏 gz 显著下降**、**1 秒级心跳不再触发全局重渲染**、**热接口尾延迟与抖动可控**、**性能预算门防止再回退**。

**Tech Stack（保持）：** React 18 + TypeScript + Vite(rolldown) + AntD 6.4.3 + Zustand + TanStack Query + ECharts(canvas) + `@tanstack/react-virtual` + `@preact/signals-react`（已装）+ Vitest。**无新增依赖。**

---

## Scope And Non-Goals

**In scope**
- H1：首屏 AntD 切片化（shell vs detail）+ 图标按需 + 性能预算门
- H2：杀掉 Topbar 1s 心跳触发的全局重渲染（迁 signals 或外置）+ MonitorPage memo 叶子收尾
- H3：热接口 stale-while-revalidate + 与后端 G1/G2/G3 协同的前端配套
- H4：治理纪律（性能预算门 + refactor guard 黑名单扩展）

**Out of scope（明确不做，即便不计成本）**
- 不换 React/AntD/Vite；不引 SSR/RSC（Next/Remix）；不引 WASM；不做微前端。
- 不替换 ECharts 或引新图表库。
- 不再做"全栈架构层级"的改造——架构强化已完成，不重复。
- 不为降包做"无意义的薄包装文件拆分"（规范 §4.2）。
- 不破坏既有 `@preact/signals-react` 的"仅热路径"原则——signals 不外溢到普通组件。
- 不重建组合执行/选股引擎/contract 等业务能力——本文件只处理"稳定性收尾"。

---

## 硬边界（不可跑偏 · 实现期必须始终成立）

1. **栈冻结**：React 18 + TS + Vite + AntD 6 + ECharts 不变；本计划**零新增 npm 依赖**。
2. **零 `useState`/`useReducer` 维持**（`check-refactor-guard.mjs` 现有规则不回退）。
3. **服务端状态唯一真源 = TanStack Query**（不复制进 store；state-separation guard 不回退）。
4. **signals 仅热路径**：仅承载真实高频字段（行情 tick、Topbar 心跳），不外溢到普通组件、不替代 Query 缓存。
5. **首屏性能预算硬门**：`first_screen_js_gzip_kb` ≤ 350KB（首期阈值）；单 chunk gz > 150KB 必须显式 allowlist 并附理由；CI 红即不合入。
6. **禁 1 秒级写全局 store**（新增 guard 规则）：任何 `setInterval(..., <=1000ms)` 写 Zustand/global store 即 lint 失败。
7. **不接实盘 / 不承诺收益 / 不喊买卖**：与既有平台业务边界一致；UI 文案不受本计划影响。
8. **重计算不上 Web 后台 loop**：与后端 `WEB_RUNTIME_BACKGROUND_JOBS_ENABLED=false` 一致；前端不新增后台 loop。

---

## 真实瓶颈诊断（实测数据，2026-06-03）

| 现象 | 证据 | 根因 |
|---|---|---|
| 首屏 JS 包重 | `dist/assets/antd-BR64pej6.js` 483K（gz ~155K）；`echarts-charts` 300K、`echarts-components` 279K、`antd-display` 282K | AntD 主包未做"首屏 vs 详情态"切分；Detail 类组件（Drawer/Modal/Tabs/Collapse 等）随首屏 |
| 跨页持续重渲染 | `frontend/src/features/trading-workspace/Topbar.tsx:49`：`setInterval(() => setTopbarPulse(realTimePulse()), 1000)`，写入 `useWorkspaceStore` | 每秒触发 Zustand 订阅广播；任何含 `topbarPulse` 的 selector 重渲染；memo 叶子也被打断调度 |
| MonitorPage 仍有部分整页刷新 | `src/features/monitor/MonitorPage.tsx`（284 行，仅 1 处 `memo`） | F1-3 memo 叶子收尾未做透 |
| 接口尾延迟传成前端"卡" | `gupiao-cloud-performance-2026-05-30-153724.json`：Redis 命中 643/MySQL 回退 2494/unresolved 4；BFF partial timeout 2 | 后端 G1（缓存覆盖）/G2（PyMySQL→C 驱动）/G3（请求隔离）未完全到位 |
| api 客户端无 SWR 行为 | `api/base.ts` 已有 timeout + offlineCache，但热接口未设 `placeholderData/keepPreviousData` | 接口慢/抖时 UI 闪空白 |

**结论：架构层已不缺，剩下是 4 项具体收尾。**

---

## Existing Code Anchors（复用，勿重写）

- 构建/分包：`frontend/vite.config.ts`（已有 `splitVendorChunks`：react-vendor、antd-* 5 个、echarts-* 多个）
- 预算扫描：`frontend/scripts/bundle-report.mjs`（已能输出 `first_screen_js_gzip_kb`/`total_gzip_kb`）
- 守卫：`frontend/scripts/check-refactor-guard.mjs`、`frontend/scripts/check-state-separation.mjs`、`frontend/scripts/check-css-guard.mjs`
- 状态层：`src/state/queryClient.ts`（staleTime 15s / refetchOnWindowFocus=false / retry=false）、`src/state/realtime/{liveQuoteSignals.ts,useQuoteStream.ts}`（已具备 signals + SSE 基础）
- 渲染原语：`src/ui/grid/VirtualGrid.tsx`、`src/ui/list/VirtualCardList.tsx`、`src/ui/realtime/LiveCell.tsx`、`src/ui/table/DataTable.tsx`
- 接口层：`src/api/base.ts`（timeout + offlineCache + retryRequest）
- 受影响页面：`src/features/trading-workspace/Topbar.tsx`、`src/features/monitor/MonitorPage.tsx`、各 `features/*/queries.ts`（已有 30s `refetchInterval`）

---

## Milestones（4 批，按 ROI 排序，独立可合入/回滚）

### M0 基线测量（0.5d）
- 记录基线：`npm run analyze`（首屏 gz、total gz、Top chunks）；React DevTools Profiler 录"监控页一次 30s 刷新"与"切换 lane"提交数；浏览器 Performance 录首屏 FCP/LCP/TBT。
- 数据写入交付报告，后续每批前后必跑同套对比。

### H1 首屏 AntD 切片化 + 图标按需 + 性能预算门（最大单点收益，先做）
出口：`first_screen_js_gzip_kb` 较 M0 下降 30–40%、单 chunk ≤ 350K（gz ≤ 150K）。

### H2 杀掉 1s 心跳全局重渲染 + MonitorPage memo 叶子（最大稳定性收益）
出口：监控页一次刷新 React 提交数与"变化项数量级"一致；Topbar 心跳不再触发 Zustand 订阅广播。

### H3 热接口 stale-while-revalidate + 后端协同（前端配套）
出口：接口抖动时 UI 不闪空白、不显示"重新加载"；与后端 G1/G2/G3 一同把热端点 p95 拉下来。

### H4 治理纪律（性能预算门 + 1s 写 store 禁令）
出口：违规 PR 在 CI 红；预算回退即报错。

---

## H1 Tasks｜首屏 AntD 切片化 + 图标按需 + 预算门

### H1-1 vite.config.ts 切分 AntD 为 shell vs detail
- [ ] 失败用例：基线下 `antd-*` 单 chunk gz 仍 ~155K，CI 预算门（H4-1）红。
- [ ] `frontend/vite.config.ts` `splitVendorChunks` 调整：
  - `antd-shell`：随首屏的 `Button`/`Typography`/`Layout`/`Grid`/`Space`/`Tag`/`Alert`/`Spin`/`Result`/`Empty`/`ConfigProvider` 等。
  - `antd-detail`：**禁止进首屏**——`Drawer`/`Modal`/`Tabs`/`Collapse`/`Tree`/`TreeSelect`/`Tour`/`QRCode`/`Mentions`/`Upload`/`DatePicker`/`TimePicker`/`ColorPicker`/`AutoComplete`/`Cascader`/`Calendar`/`Transfer`/`Statistic`/`Steps`/`Anchor`/`Watermark`/`FloatButton`/`Carousel`/`Image`。
  - `antd-form` / `antd-feedback` / `antd-display` / `antd-core` 已有分包保留并复核归属，把上述 Detail 项从原 chunk 移出。
- [ ] 复核 Detail 类组件的引用站点是否在 lazy 路由内（不在则补 `lazy()`/动态 import）。
- [ ] 测试：vitest 全绿；`npm run build && npm run analyze` 显示 `antd-detail-*` chunk 仅出现在非首屏入口图中。

### H1-2 图标按需 / 集中索引
- [ ] 失败用例：`rg "from \"@ant-design/icons\"$" src` 命中数 > 0（全量桶导入）。
- [ ] 新建 `src/ui/icons/index.ts`，把全站用到的图标按 `import XxxOutlined from "@ant-design/icons/es/icons/XxxOutlined"` 显式列出再 re-export；全站统一从 `@/ui/icons` 取。
- [ ] 测试：`@ant-design/icons` 直接桶导入 = 0；icons chunk 大小可控。

### H1-3 性能预算脚本与 CI 接入
- [ ] 新建 `frontend/scripts/check-bundle-budget.mjs`，调用既有 `bundle-report.mjs` 输出，对 `first_screen_js_gzip_kb`/单 chunk gz/total gz 做阈值校验：
  - `first_screen_js_gzip_kb ≤ 350` （初期门，后续逐步下调到基线）
  - 单 chunk gz > 150 必须在 `frontend/.bundle-allowlist.json` 显式列出并附理由，否则失败
  - `total_gzip_kb` 不连续两次上升
- [ ] `package.json` 加 `"check:bundle-budget": "node ./scripts/check-bundle-budget.mjs"`；接入 `npm run lint`（与 refactor/state-separation/css guard 并列）。
- [ ] 测试：故意把一个 Detail 组件挪回首屏 → CI 红；恢复 → 绿。

**H1 验收**：`npm run analyze` 首屏 gz 较 M0 下降 ≥30%；`npm run lint` 含预算门通过；CI 能拦截预算回退。

---

## H2 Tasks｜杀掉 1s 心跳全局重渲染 + MonitorPage memo 叶子

### H2-1 Topbar pulse 迁出 Zustand 改 signals
- [ ] 失败用例：使用 React DevTools Profiler 录"停留 Topbar 5 秒"，断言**任何含 `useWorkspaceStore` selector** 的非 Topbar 组件被多次提交。
- [ ] 在 `src/state/realtime/` 新增 `topbarClockSignal.ts`，导出一个 `topbarPulseSignal: Signal<string>`；Topbar 内部用 `signal.value` 渲染；`setInterval(() => topbarPulseSignal.value = realTimePulse(), 1000)` 直接写信号，**不进 Zustand**。
- [ ] `useWorkspaceStore` 中删除 `topbarPulse` / `setTopbarPulse` 字段与方法；全局搜索更新所有引用。
- [ ] 文档/注释：标注"signals 仅热路径"，并补 README 一句说明。
- [ ] 测试：新增 `Topbar.signal.test.tsx`——断言 pulse 更新只影响 Topbar 单元、不触发外部 store 订阅广播（用 spy 验证 selector 调用次数）。

### H2-2 MonitorPage memo 叶子收尾
- [ ] 失败用例：Profiler 录"监控页 30s 一次刷新"，断言提交数 > 变化项数量级。
- [ ] 把 `MonitorPage.tsx` 中卡片/行抽 `memo` 叶子组件，每个叶子按 `id` key 只接收自己那条 item；多字段订阅用 `useShallow`。
- [ ] 重派生（`useMemo` 链）下沉为 query `select` 或 store 派生，避免每次刷新整页重算。
- [ ] 测试：渲染计数测试——模拟一次刷新仅变化项重渲染。

### H2-3 顺手清理其他 ≤1s 计时器
- [ ] `rg "setInterval\([^,]+, *[0-9]{1,3}\b" src` 列出所有 ≤1000ms 的计时器，逐个评估：是否真有必要 1s 级？能否合并为单一全局 RAF/signal？
- [ ] 测试：保留下来的 1s 级计时器必须写信号或写组件本地态，不得写全局 store（被 H4-2 guard 拦下）。

**H2 验收**：Profiler 监控页一次刷新提交数显著下降至"变化项数量级"；Topbar 心跳不再触发跨组件订阅广播；`useWorkspaceStore` 无 `topbarPulse` 字段。

---

## H3 Tasks｜热接口 stale-while-revalidate + 后端协同

### H3-1 TanStack Query 热接口 SWR 配置
- [ ] 失败用例：构造慢接口（mock 800ms），切换 lane/页面时观察空白闪烁。
- [ ] 在 `features/monitor/queries.ts`、`features/paper/queries.ts`、`features/playbook/queries.ts`、`features/strategy-tracking/queries.ts` 等热查询统一：
  - `placeholderData: (prev) => prev`（或 `keepPreviousData: true`）
  - `staleTime`：行情/价格类 5s；榜单/快照类 30s；详情类 60s
  - `refetchOnReconnect: true`、`refetchOnMount: false`
- [ ] 在 `src/state/queryClient.ts` 把上述补全到 `defaultOptions.queries`（非热接口不会变差）。
- [ ] 测试：模拟接口 800ms 抖动 → UI 保留上次数据、无闪空白；接口失败 → 显示既有 stale 提示而非全屏重载。

### H3-2 错误/慢源前端降级一致化
- [ ] `api/base.ts` 现有 `timeoutMs` 与 `retryRequest`；新增对 BFF partial（响应含 `partial_errors`）的统一降级处理：UI 显式标注"部分降级源"，不阻塞主链路。
- [ ] 测试：mock 含 `partial_errors` 响应 → 页面仍渲染主数据 + 显式降级标记。

### H3-3 与后端 G1/G2/G3 协同（引用既有计划，不重复实现）
- [ ] 引用 `docs/superpowers/plans/2026-05-30-backend-performance-hardening.md`：G1 行情缓存按需扩展、G2 PyMySQL→mysqlclient(C)、G3 热端点请求隔离。
- [ ] 本计划只在前端验收里加：监控页/优先榜 p95 较基线显著下降、`bff_partial_timeout=0`、Redis 命中率 ≥90% 后回测前端体感。
- [ ] **不在本文件实施后端改动**，避免与既有方案重复。

**H3 验收**：接口抖动 UI 不闪不空；与后端 G1/G2/G3 闭环后，监控/榜单 p95 显著下降、BFF timeout 归零。

---

## H4 Tasks｜治理纪律（防回退）

### H4-1 性能预算门接入 CI
- [ ] `package.json` 的 `lint`/`check:*` 链路接入 H1-3 的 `check:bundle-budget`。
- [ ] `.github/workflows/ci.yml` 前端 job 在 `build` 之后跑 `check:bundle-budget`（基线 350KB gz）。
- [ ] 测试：故意上升包大小 → CI 红。

### H4-2 refactor-guard 黑名单扩展
- [ ] `frontend/scripts/check-refactor-guard.mjs` 新增模式：
  - 禁止 `setInterval\([^,]+,\s*(\d{1,3})(?!\d)\s*\)`（≤999ms）出现在写 Zustand store 的同一函数里（用启发式扫"setInterval"附近是否调用 `useXxxStore.setState`/store action）。
  - 已有 `priorityCards/opportunities slice 截断` 等保持。
- [ ] 测试：写一个违规样例 → guard 报错；移除后通过。

### H4-3 README/规范文档同步
- [ ] 在 `docs/engineering-conventions.md` 补一段"性能预算门 + 1s 写 store 禁令"的规范条目（指向本文件）。
- [ ] 不新增重复规范页。

**H4 验收**：CI 有预算门、guard 含 1s 写 store 禁令；规范文档已同步。

---

## Verification Commands（每批 + 总验收）

```bash
# 每批前后必跑（与 M0 对比）
cd frontend
npm run build
npm run analyze                       # 记录 first_screen_js_gzip_kb / total / Top chunks
npm test -- --run                     # vitest 全绿（含 H2-1/H2-2 新增渲染计数测试）
npm run lint                          # 含 refactor / state-separation / css / bundle-budget
npm run api:check                     # 契约不漂移

# 总验收（最后跑）
npm run lint && npm test -- --run && npm run build && npm run analyze
# H1: first_screen_js_gzip_kb 较 M0 ↓≥30%
# H2: Profiler 提交数与变化项数量级一致
# H3: 接口抖动 UI 不闪空白
# H4: 故意违规 → CI 红
```

---

## 量化验收门

| 指标 | M0 基线 | 目标 | 工具 |
|---|---|---|---|
| `first_screen_js_gzip_kb` | 待测（当前估 ~250–280KB） | ≤ 350KB（首期门）且较基线 ↓≥30% | `npm run analyze` |
| 单 chunk gz 上限 | `antd-*` 最大 ~155KB | 任何首屏 chunk ≤ 150KB（超须 allowlist+理由） | `check-bundle-budget` |
| 监控页 React 提交数（一次 30s 刷新） | 整页量级 | 与变化项数量级一致 | React DevTools Profiler |
| Topbar 1s 心跳影响范围 | 跨页订阅广播 | 仅 Topbar 自身重渲染 | spy + signal 测试 |
| 接口抖动 UI | 闪空白 | 保留上次数据 + 显式降级标 | mock 800ms 抖动 |
| 监控/榜单 p95（联动后端 G1/G2/G3） | 当前云报告 | 显著下降；`bff_partial_timeout=0` | 云性能脚本 |

---

## Rollback

- **H1**：vite chunk 调整可单独回退到当前 `splitVendorChunks`；图标桶导入回退兼容；预算门可临时调阈值或暂停 CI 步骤（不删除）。
- **H2**：signal 迁移可保留 Zustand 字段过渡（双写 → 切读 → 删字段），任一环节回退；memo 叶子是渐进抽离。
- **H3**：SWR 配置降级到当前 staleTime；`partial_errors` 处理回退到现状。
- **H4**：guard 规则可单条禁用（环境变量或 allowlist），但默认保持启用。
- 每批改动独立可回退；无业务语义/数据契约变更；无 schema/迁移。

---

## Definition Of Done

- `first_screen_js_gzip_kb` 较 M0 ↓≥30% 且 ≤ 350KB；单 chunk ≤ 150KB gz（除显式 allowlist）。
- Topbar 1s pulse 经 signals 承载，不再写 Zustand 全局 store；Profiler 验证仅 Topbar 自身更新。
- MonitorPage 卡片/行为 memo 叶子；一次刷新提交数与变化项数量级一致。
- 热接口配置 SWR；接口抖动 UI 不闪空白；BFF partial 降级一致化。
- CI 含 `check:bundle-budget` + `check-refactor-guard`（已扩 1s 写 store 禁令）；故意回退即红。
- 全程未换 React/AntD/Vite/ECharts、未引 SSR/WASM/微前端、未新增 npm 依赖。
- `npm run api:check && npm run lint && npm test -- --run && npm run build && npm run analyze` 全绿。
- 与后端 G1/G2/G3 联动后，监控/优先榜 p95 显著下降、`bff_partial_timeout=0`。

---

## 不做清单（避免范围漂移）

- 不换 React/AntD/Vite/ECharts；不上 SSR/WASM/微前端。
- 不新增 npm 依赖（signals 已装）。
- 不外溢 signals 到普通组件，不让 signals 替代 TanStack Query。
- 不为降包做"无意义薄包装文件"。
- 不在本文件做后端 G1/G2/G3 的具体实施（指向既有方案）。
- 不重建组合执行/契约/选股引擎；不动业务逻辑。

---

## 风险与处置

| 风险 | 处置 |
|---|---|
| AntD 切片误把首屏组件挪入 detail → 报错 | 切片前先 `rg` 引用站点；vitest 关键页面覆盖；analyze 显式核对 |
| signals 滥用（外溢） | refactor-guard 增"signal 导出限定目录 `src/state/realtime/`"规则（H4-2 顺手加） |
| 预算门阈值偏紧导致开发受阻 | 首期 350KB，后续逐步下调；超阈值可显式 allowlist + 理由 |
| 后端 G1/G2/G3 未及时跟进 | 前端 H3-3 仅验收联动，不阻塞 H1/H2/H4 合入 |
| 1s 心跳被业务真需要 | 改用 signals 后心跳成本几乎为零；不影响业务 |
| guard 误伤 | 提供 `.bundle-allowlist.json`/per-file `eslint-disable` 等正规出口 |

---

## 优先级与执行节奏

- **第 1 天**：M0 基线测量 + H4-1/H4-2 先把预算门和 guard 装上（保证后续改动可量化、防回退）。
- **第 2 天**：H2 一次性做完（Topbar signal + MonitorPage memo 叶子）——单点稳定性收益最大、改动可控。
- **第 3–4 天**：H1 AntD 切片 + 图标按需，反复跑 analyze 直到达标。
- **持续**：H3 SWR 落到所有热查询；与后端 G1/G2/G3 联动验收。
- **最后**：交付报告对比 M0 与最终指标，提交 PR。

**一句话**：把这四件做完，"前端慢、不稳定"的体感问题就在不换栈的前提下收口；预算门和 guard 保证未来不会再悄悄回退。
