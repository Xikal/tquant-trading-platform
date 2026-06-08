# frontend-next 优化完整方案（2026-06-07）

> 状态：方案（待执行）。**本文只出方案，不改代码、不部署、不切流。**
> 适用范围：`frontend-next/`（新前端）；旧 `frontend/`、后端、`strategy_policy.py` 一律不动。
> 证据来源：本会话实测 —— `frontend-next-full-audit-2026-06-07.md`、新旧 dist 构建对比、`g1-g7-refactor-report-2026-06-07.md` 的 perf:compare / screenshot:parity。
> 方法学说明：部分 file:行号锚点来自本会话早前对 `frontend-next/src` 的读取；执行时如遇文件访问问题（本轮 shell 对 `src/` 出现 EPERM）需先恢复读权限再按锚点定位。标注「待复测」的项需执行者现场确认数值。

---

## 0. 定位

新前端在体积/框架上已大幅领先旧前端（JS gzip −52%、框架运行时 −97%、监控页请求 13→2）。本方案是**下一轮工程优化**：把 monitor 已验证的"BFF 合包 + 虚拟化"模式复制到其余重页面、补回唯一劣化项（CSS +174%）、收敛 echarts 与首屏块。**不是重设计、不是换栈、不扩功能。**

---

## 1. 现状基线（本会话实测，作为每个工作包的 M0）

**Bundle（dist 实测，Jun 7 构建）**

| 项 | 数值 |
|---|---|
| JS 总体积 | 1162 KB raw / 380 KB gzip |
| CSS 总体积 | 233 KB（旧前端 85 KB，本轮唯一劣化项 +174%） |
| chunk 数 | 29（bundle budget 1.25MB，现 1,189,691 bytes） |
| 首屏关键块 | index 68.6 + solid-vendor 33 + vendor 160 + tanstack 159 ≈ **412 KB raw** |
| echarts | `echarts-charts` 284 + `echarts-components` 160 = **447 KB**（独立 chunk = lazy） |
| 最大页面块 | `PaperPage` 56.7KB、`StrategyTracking` 39.6、`Backtest` 38.5、`Settings` 25.7、`MonitorAction` 22.2、`DataConsole` 21.1 |

**运行时（perf:compare，冷启本地 shadow）**

| 页面 | 时长 | DOM | API 请求 |
|---|---:|---:|---:|
| /next/monitor | 1718ms | 230 | **2**（BFF 合包，标杆） |
| /next/monitor/market | 732ms | 271 | 2 |
| /next/paper | 1967ms | **403** | 2 |
| /next/strategy-tracking | 1906ms | 226 | **9**（含 items 422） |

**CSS 健康**：15.5k 行；`!important`×51（monitor-market 8 最多）；`:has(`×1（合法）；paper 三源（`paper-page.css`+`workspace-paper.css`+`workspace-paper-mecha.css`）；login 5 文件 ~1.3k；primitives 拆 4 文件。

**视觉**：screenshot:parity 8/9 ≥0.85，analysis 0.7767 唯一不达标。
**测试**：unit 83 / e2e 35（旧前端 unit 299）。

---

## 2. 硬边界（实施期必须始终成立）

1. **只动 `frontend-next/`**；旧 `frontend/`、后端、`strategy_policy.py` 0 改动。
2. **不换栈**：SolidJS + TanStack + lightweight-charts（K 线）+ echarts（仅低频 adapter）+ Worker；零新增框架级依赖。
3. **不破坏既有 guard**：`check-boundary-guard`（K 线不引 echarts / 不依赖 strategy_policy / Worker 不改生产排序）、`check-css-guard`、`check-refactor-guard`、`check-bundle-budget`（<1.25MB）全程绿。
4. **不改业务语义/生产口径**：production_score / priority_board / 生产排序 / lane 语义不变；Worker 仍只 display sort/filter/derive/downsample。
5. **契约优先**：DTO 继续从 `generated/api-types` 派生（`ApiGet<>`），不新增手写 DTO。
6. **不退视觉/功能 parity**：parity ≥0.85 的 8 页不得回退；不引入新空态/假数据。
7. **机甲仅 display/review**，优化（虚拟化/资源）不得改其展示边界。
8. **每个工作包独立可回退**，无 schema/迁移。
9. **不部署、不切流**（本方案产出后另行授权执行）。

---

## 3. 工作包（O1–O10，按 ROI 排序）

### P1 — 高收益

#### O1 strategy-tracking 请求合包（9 → ≤2）
- **目标**：把 strategy-tracking 的 9 个 API 收敛为 BFF 合包，对齐 monitor 的 2。
- **为什么**：perf 实测 strategy-tracking 9 请求（含 items 422）/1906ms；`types.ts` 已有 `StrategyWorkspaceResponse = ApiGet<"/api/bff/v1/workspace/strategy">` → **后端合包已就绪，前端未接**。
- **涉及文件**：`src/features/strategy-tracking/StrategyTrackingPage.tsx`、`src/shared/api/operations.ts`、`queryKeys.ts`（新增 strategy workspace query）。
- **不允许**：改后端；改策略排序/口径；把 items 422 用假数据掩盖（须真实修参数契约或显式错误态）。
- **做法**：新增 `useStrategyWorkspace` 走 `/api/bff/v1/workspace/strategy` 单请求 → 字段切片；保留旧多请求为 fallback；修 items 422 参数（与后端确认 range/board_filter/limit/offset 契约）。
- **验收 / 量化门**：DevTools 该页请求数 9→≤2；页面延迟较 1906ms 下降；items 不再 422；关键字段 sha256 合包前后一致。
- **回退**：flag 关闭回多请求。

#### O2 paper 列表虚拟化（DOM 403 → <150）
- **目标**：降 paper DOM 数与渲染时长。
- **为什么**：perf paper DOM **403（9 页最高）**、1967ms（最慢）；`shared/ui/VirtualList` 已存在但 paper 未用。
- **涉及文件**：`src/features/paper/PaperPage.tsx` 及持仓/委托/成交/绩效列表子组件；`src/shared/ui/VirtualList.tsx`。
- **不允许**：改机甲展示边界；虚拟化导致截图 parity（paper 0.8826）回退。
- **做法**：持仓/委托/成交/绩效长列表接 `VirtualList`（仅渲染视口行）；机甲 HUD 不动。
- **验收 / 量化门**：paper DOM <150；paper 延迟较 1967ms 下降；paper parity ≥0.8826 不回退。
- **回退**：列表回退非虚拟渲染。

#### O3 CSS 瘦身（233KB → 目标显著下降；补回唯一劣化项）
- **目标**：去死规则 + 合并多源，压低 233KB。
- **为什么**：benchmark 显示 CSS 是新前端唯一劣化（+174% vs 旧 85KB）；15.5k 行 legacy 皮肤复刻大概率带入死规则。
- **涉及文件**：`src/shared/styles/legacy-workspace/*`（16 文件）、各 feature slice css、`scripts/check-css-guard.mjs`。
- **不允许**：改视觉风格/密度（parity 不退）；删未确认无引用的规则（须扫描证据）。
- **做法**：① PurgeCSS/未用选择器扫描 legacy 皮肤（以 9 页 + 组件为白名单）；② paper 三源、strategy-tracking、backtest 的 feature-slice 与 legacy-workspace 双源**合并去重**；③ login 5 文件→2、primitives 4→收敛；④ `!important` 51→≤25（先 monitor-market 8）。
- **验收 / 量化门**：CSS 总体积下降（目标 ≤180KB，**待 purge 后定**）；`!important` ≤25；9 页 parity 不回退；`check-css-guard` 绿。
- **回退**：分文件回退；purge 结果可逐条 review。

### P2 — 中收益

#### O4 echarts 收敛（447KB）
- **目标**：确认 echarts 完全 lazy + 更细 tree-shake，潜在再省 ~100KB+。
- **为什么**：echarts 是最重依赖；K 线已走 lightweight-charts，echarts 仅低频 adapter。
- **涉及文件**：`src/shared/charts/EchartsIsland.tsx`、引用 EchartsIsland 的页面（backtest/analysis）、vite manualChunks（待复测）。
- **不允许**：把 K 线改回 echarts（破坏 boundary guard）；任何页首屏 eager echarts。
- **做法**：核对 echarts 仅按需 import 用到的 chart/component（`echarts/core` + 具体 series 注册，而非全量）；确认 9 页首屏均不预载 echarts chunk；评估剩余低频图换 lightweight-charts/轻量库。
- **验收 / 量化门**：echarts chunk 体积下降；首屏 network 无 echarts；boundary guard 绿。

#### O5 首屏块体检（vendor 160 + tanstack 159 ≈ 319KB）
- **目标**：首屏 412KB → ≤350KB。
- **为什么**：vendor/tanstack 是首屏最大块；tanstack 159KB 对 solid-query+router 偏大，疑有可 lazy 部分。
- **涉及文件**：`vite.config.ts` manualChunks（**待复测**）、`src/shared/ui/VirtualList.tsx`（solid-virtual 用点）。
- **不允许**：拆分制造无意义薄包装；破坏 bundle budget。
- **做法**：`vite-bundle-visualizer` 看 vendor/tanstack 组成；`solid-virtual` 仅在用虚拟化的页 lazy；vendor 内 dayjs/decimal/lightweight-charts 等按需引入/code-split。
- **验收 / 量化门**：首屏 raw ≤350KB；总 JS 仍 <1.25MB；parity/e2e 不退。

#### O6 shared/ui 去重
- **目标**：删冗余 wrapper，降维护面。
- **为什么**：`DataGrid.tsx` 是 `DataTable` 纯别名；`StatusBadge`/`StatusPill`/`Tag` tone API 重叠。
- **涉及文件**：`src/shared/ui/{DataGrid,StatusBadge,StatusPill,Tag}.tsx` 及调用方。
- **做法**：删 `DataGrid`，调用方改 `DataTable`；徽标合并统一 tone（保留 StatusPill 的 label+value 结构）。
- **验收**：typecheck/lint/test 绿；无视觉回退。

### P3 — 质量 / 量化（非体积）

#### O7 TanStack Query 请求治理
- 统一热查询 `staleTime`/`placeholderData`/key 粒度，消重复请求（配合 O1）。验收：无重复 in-flight 请求；抖动不闪空。

#### O8 测试覆盖补齐
- unit 83（旧 299）→ 补功能级断言（analysis 真实分析流、playbook 联动、paper 下单+撤单、strategy review CRUD+rollback）+ 422/503 错误态测试 + parity 阈值纳入 CI gate。质量缺口，cutover 前必须。

#### O9 新旧渲染 A/B 量化
- 同机同数据对新旧各跑 Lighthouse/perf，量化 LCP/TTI/重渲染次数（当前只有体积是硬数，渲染速度无 A/B）。产出 `frontend-next-vs-legacy-benchmark` 渲染章节。

#### O10 资源 / 动效核查（待复测）
- 核查 `src/assets` 体积、机甲粒子 + 登录 canvas 的资源大小与帧开销（`onCleanup` 已均衡，但 canvas 帧循环需抽样低端机不掉帧）。

---

## 4. 并行 / 串行

```
P1（可并行启动）：O1 strategy 合包 │ O2 paper 虚拟化 │ O3 CSS 瘦身
                        │
P2（P1 后）：O4 echarts │ O5 首屏块 │ O6 shared/ui 去重（O5/O6 可与 O4 并行）
                        │
P3（收尾/质量）：O7 请求治理（依赖 O1）→ O8 测试 → O9 A/B → O10 资源
```
- O1/O2/O3 互不依赖，P1 三件可同时做。
- O7 依赖 O1（合包后再统一 query 策略）。
- O8/O9/O10 收尾。

---

## 5. 量化验收门（M0 → 目标）

| 指标 | M0（实测） | 目标 | 工作包 |
|---|---:|---:|---|
| strategy-tracking API 请求 | 9 | ≤2 | O1 |
| strategy-tracking items 422 | 有 | 0 | O1 |
| paper DOM | 403 | <150 | O2 |
| paper 延迟 | 1967ms | 显著↓ | O2 |
| CSS 总体积 | 233 KB | ≤180 KB（purge 后定） | O3 |
| `!important` | 51 | ≤25 | O3 |
| echarts chunk | 447 KB | ↓（首屏不预载） | O4 |
| 首屏 raw | 412 KB | ≤350 KB | O5 |
| 总 JS | 1162 KB / <1.25MB budget | 维持 budget 绿 | 全程 |
| screenshot:parity | 8/9 ≥0.85 | 8 页不退；analysis 另案修 | 全程 |
| unit 测试 | 83 | 补功能级 | O8 |

---

## 6. 验收命令（每个工作包完成必跑）

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run typecheck
npm run lint            # 含 boundary/css/refactor/bundle-budget guard
npm test -- --run
npm run build           # 看 chunk 体积变化
npm run e2e
npm run screenshot:parity   # 确认 8 页 parity 不回退
npm run perf:compare        # 确认请求数/DOM/延迟改善
cd /Users/j/Documents/gupiao && git diff --check && git status --short
```

---

## 7. 回退

- 每个工作包独立 commit + 独立 flag/可逆：O1 合包 flag、O2 列表渲染开关、O3 分文件回退、O4/O5 vite 配置回退、O6 wrapper 还原。
- 无 schema、无数据迁移、无后端改动 → 回退零数据风险。

---

## 8. 明确不做

- 不换 React/Solid/Vite/图表库；不上 SSR/WASM/微前端；零新增框架依赖。
- 不改后端、`strategy_policy.py`、生产排序、production_score、priority_board 口径。
- 不动旧 `frontend/`。
- 不把 K 线改回 echarts；不让 Worker 碰生产排序；不绕 mutation guard。
- 不为降体积制造无意义薄包装文件或删未经扫描确认的 CSS。
- 不部署、不切流（另行授权）。

---

## 9. Definition Of Done

- O1：strategy-tracking 请求 ≤2、items 不 422、字段 parity 一致。
- O2：paper DOM <150、延迟下降、paper parity 不退。
- O3：CSS 体积下降、`!important` ≤25、9 页 parity 不退。
- O4/O5：echarts 首屏不预载且更小、首屏 raw ≤350KB、budget 绿。
- O6：冗余 wrapper 去除、无视觉/类型回退。
- 全程：`api:check/typecheck/lint/test/build/e2e/screenshot:parity/perf:compare` 全绿；boundary/css/refactor/bundle guard 绿；旧前端/后端/strategy_policy 0 改动；`git diff --check` 通过。
- 每项独立可回退。

---

## 10. 一句话

**最高 ROI 是把 monitor 验证过的「BFF 合包 + 虚拟化」复制到 strategy-tracking（请求 9→2）和 paper（DOM 403→<150），并补回 CSS 这块唯一劣化（233KB purge+合并）；echarts 与首屏块是中等收益的体积项。** O1/O2/O3 不依赖受限的文件读取，可直接落地；全程不换栈、不改业务、不动旧前端/后端，逐项可回退。
