# frontend-next 全量审查报告（2026-06-07）

> 性质：**只读审查，未修改任何代码，未部署，未切流**。旧 `frontend/` 仅作只读参考。
> 审查对象：`frontend-next/`（当前 157 个源文件 / ~61.9k LOC，全部 untracked）。
> 必读文档已阅：`AGENTS.md`、`docs/engineering-conventions.md`、`frontend-next-solid-parallel-development-plan-2026-06-05.md`、`frontend-next-legacy-ui-architecture-migration-development-doc-2026-06-06.md`、`reports/frontend-next-g1-g7-refactor-report-2026-06-07.md`、`reports/frontend-next-gap-audit-2026-06-06.md`、`docs/frontend-next/style-specs/*.md`（9 份）。

---

## 0. 总体结论

**Approve（作为 `/next/*` shadow 预览）** —— 无 Critical 缺陷；10 个硬边界全部成立；工程门禁全绿。

但**这不是 cutover 签收**。仍有 1 个视觉 Required（analysis 相似度 0.7767 < 0.85 门）、2 类环境 API 错误（strategy-tracking 422 / settings 503）需后端确认，以及若干 Optional 清理项。

**关键校正**：`frontend-next-gap-audit-2026-06-06.md`（"16 文件 / 多为 shell"）**已被 06-06 的 legacy-ui 迁移 + 06-07 的 G1-G7 重构大幅推翻**。当前实测：LoginPage/鉴权、analysis 真实 `/analyze`、playbook 真实 screener、monitor lane 切换、paper 带确认的下单表单**均已落地**。本报告以**当前代码**为准，建议把旧 gap-audit 标记为 superseded。

---

## 1. 审查范围与命令结果（本轮均为新跑，除 perf 外）

| 命令 | 结果 | 证据 |
|---|---|---|
| `npm run api:check` | ✅ 通过 | OpenAPI → `generated/api-types.ts` 重生成 + `tsc -b` 无错 |
| `npm run typecheck` | ✅ 通过 | `tsc -b` 零错误 |
| `npm run lint` | ✅ 通过 | 含 refactor / css / **boundary guard** / bundle budget（29 chunks / 1,189,691 bytes < 1.25MB） |
| `npm test -- --run` | ✅ **19 files / 83 passed** | vitest |
| `npm run build` | ✅ 通过（698ms） | 见 §9 bundle |
| `npm run e2e` | ✅ **35 passed**（8.3s） | 含鉴权/权限/移动导航/no-write guard |
| `npm run screenshot:parity` | ⚠️ **8/9 ≥ 0.85**（analysis 0.7767） | 见 §3 |
| `npm run perf:compare` | ✅（引用今日 G1-G7 报告同日同树） | 见 §9 |
| `git diff --check` | ✅ clean | 仓库根 |
| `git status --short` | ✅ 全部 `??` untracked | 无 tracked 业务改动 |

> 诚实说明：api:check / typecheck / lint / test / build / e2e / screenshot:parity 为本轮**新跑**；perf:compare 数值**引用** `frontend-next-g1-g7-refactor-report-2026-06-07.md`（同日、同树），未重复跑。

---

## 2. 按严重级别列问题

> 字段：文件:行号 / 问题 / 影响 / 修复建议 / 可否自动修复。

### Critical（阻断，必须先修）
**无。** 未发现破坏构建、违反硬边界、污染策略语义、泄漏密钥或导致页面崩溃的问题。

### Required（cutover 前应修，不阻断当前 shadow 构建）

**RQ-1 `/next/analysis` 视觉相似度 0.7767，低于 0.85 门（9 页中唯一不达标）**
- 文件：`frontend-next/src/features/analysis/AnalysisPage.tsx`、`frontend-next/src/features/analysis/analysisSlice.css`
- 证据：`screenshot:parity` analysis 0.7767（其余 8 页 0.8826–0.9568）。功能**已接真实 API**（`analysisModel.ts:77 apiClient.analyzeSymbol`、`:98 analyzeBatch`），故这是**视觉/信息密度差异，非功能缺失**。
- 影响：视觉验收不达标；不影响功能与数据正确性。
- 修复建议：对照 `analysis-style-spec-2026-06-05.md` 调密度/间距/字号层级/首屏信息组织（属上轮"视觉微调"未覆盖项）。
- 可自动修复：部分（CSS 密度可调；布局结构需人工对照 spec）。

**RQ-2 环境 API 错误在 parity/perf 中持续出现**
- 证据：`/api/strategy-tracking/items?range=60&board_filter=include_all&limit=120&offset=0` → **422**；`/api/settings`、`/api/settings/factor-weights` → **503×4**（settings 页）。
- 影响：本地/截图环境下相关分区取不到数据；e2e 显示**页面壳与错误态仍可用、不崩溃**（`app-shell-auth` 35 passed），但真实数据缺失。
- 修复建议：后端/契约侧确认 422 参数契约与 503 是否为本地依赖未启动；前端侧需确认这些路径有**显式空态/错误态**（非静默空白）。
- 可自动修复：否（需后端确认 + 前端错误态核对）。

### Optional（清理 / 合并，提升可维护性）

**OP-1 `DataGrid.tsx` 是 `DataTable` 的纯别名（冗余 wrapper）**
- 文件：`frontend-next/src/shared/ui/DataGrid.tsx:1-5`（`return <DataTable {...props} />`）。
- 影响：两个名字一份实现，增加心智负担。
- 修复建议：删除 `DataGrid`，调用方改用 `DataTable`；或保留并在文件头注明"别名，勿新增逻辑"。
- 可自动修复：是（若无外部依赖该名）。

**OP-2 三个徽标 wrapper 语义重叠**
- 文件：`StatusBadge.tsx`(5L) / `StatusPill.tsx`(21L) / `Tag.tsx`(9L)。
- 影响：三种 span 徽标 tone API 不统一（`tq-status-badge` / status-pill / `tq-tag`）。
- 修复建议：保留 `StatusPill`（含 label+value 结构）与 `Tag`（纯 tone 标签），评估把 `StatusBadge` 合入 `Tag`；统一 tone 取值。
- 可自动修复：部分。

**OP-3 `!important` 共 51 处（migration 皮肤债）**
- 文件：`monitor-market.css`(8)、`workspace-strategy-tracking.css`(6)、`legacy-solid-adapter.css`(5)、`playbookSlice.css`(5)、`monitor-action.css`(4)、`LoginPage.css`(4)、`analysisSlice.css`(4)…
- 影响：覆盖优先级脆弱，后续微调易打架。
- 修复建议：用更高特异性选择器或 token 替代覆盖式 `!important`；优先收敛 monitor-market 的 8 处。
- 可自动修复：部分。

**OP-4 feature-slice CSS 与 legacy-workspace/*.css 双源**
- 文件：`features/paper/paper-page.css` + `legacy-workspace/workspace-paper.css`(+`workspace-paper-mecha.css`)；strategy-tracking、backtest 同形。
- 影响：同页两份 CSS 来源，存在合并空间（未发现规则冲突，但维护点分散）。
- 修复建议：核对重复选择器后，按页合并到单一 slice 或单一 legacy 皮肤文件。
- 可自动修复：否（需人工核对规则交叠）。

**OP-5 登录页 5 个 CSS 文件 ~1.3k 行**
- 文件：`workspace-login.css`+`-card`(365)+`-motion`(321)+`-scene`(486)+`-shell`(101)。
- 影响：登录视觉场景拆得过细。
- 修复建议：评估把 login-* 合并为 2 个（结构 + 动效）。属低优先美化债。
- 可自动修复：否。

### FYI（提示，非问题）

**FY-1 admin token 客户端持有**：`data-console/DataConsolePage.tsx:39` `createSignal("")`，`:168` 作为 `token={adminToken()}` 传子组件。未见明文 `console.log`/渲染；e2e `route-level errors ... redact sensitive details` 通过。建议确认该输入为掩码（password）且不持久化到 localStorage/日志。

**FY-2 gap-audit 已过期**：`frontend-next-gap-audit-2026-06-06.md` 多条 P0（认证、analysis、playbook、monitor lane、paper 下单）在当前树已落地，建议标注 superseded，避免误导。

---

## 3. screenshot:parity 结果（本轮新跑，1440×900 sample_similarity）

| 路由 | similarity | 达标(≥0.85) | 失败 API |
|---|---:|:--:|---|
| /next/monitor | 0.9432 | ✅ | - |
| /next/monitor/market | 0.9561 | ✅ | - |
| /next/paper | 0.8826 | ✅ | - |
| /next/strategy-tracking | 0.9504 | ✅ | items **422** |
| /next/analysis | **0.7767** | ❌ | - |
| /next/playbook | 0.9158 | ✅ | - |
| /next/backtest | 0.9154 | ✅ | - |
| /next/data | 0.9568 | ✅ | - |
| /next/settings | 0.9357 | ✅ | settings **503×4** |

**8/9 达标**；analysis 为唯一不达标（RQ-1）。截图输出目录：`docs/reports/frontend-next-screenshots-2026-06-05/`。

---

## 4. 功能完整性清单（逐页，当前实测）

| 页面 | 当前实测能力 | 仍缺/待确认 | 阻断等级 |
|---|---|---|---|
| /next/monitor | BFF 读取 + 优先榜 + **lane 切换**（`MonitorActionPage.tsx:184-186` 原低吸/前排加权/前排极精选，按 `item.lane` 客户端过滤、不重排） | 与旧前端 AI 榜单解读、持仓录入抽屉等深度交互对齐度待人工确认 | 非阻断 |
| /next/monitor/market | BFF 市场总闸/宽度/ETF/复盘 | 大盘关键位、板块龙头确认完整度待确认 | 非阻断 |
| /next/paper | 账户/持仓 + 机甲 HUD（仅 display/review）+ **确认门下单表单**（`PaperOrderForm.tsx:90,185` 待确认→已确认两段）+ workflow tabs | 自动交易/风险事件/对账详情完整度待确认 | 非阻断 |
| /next/strategy-tracking | BFF 表格 + 概览指标 | items 422 导致筛选/分页数据缺；详情/复盘闭环完整度待确认 | RQ-2 |
| /next/analysis | **真实** `/analyze`+`/analyze/batch`（`analysisModel.ts:77,98`）；`analysisModel.test.ts:49` 守"不臆造策略字段" | 视觉密度（RQ-1）；批量排序/关键位/盘中异常完整度待确认 | RQ-1 |
| /next/playbook | **真实** screener（`PlaybookPage.tsx:39 queryKeys.lowBuyScreener`）+ 策略 tabs | 绩效归因/仪式 UI 完整度待确认 | 非阻断 |
| /next/backtest | run list + ECharts 曲线 + shadow 提交 | submit 全参数/cancel/validation/optimization/compare 完整度待确认 | 非阻断 |
| /next/data | admin token 输入 + 采集任务 + 运维分区 | SLA/gate/source/coverage/repair 全链路完整度待确认 | 非阻断 |
| /next/settings | 运行状态 + feature flag；settings 503 | 安全/风控/LLM/因子/治理/审计完整度待确认（且 503 取不到） | RQ-2 |
| 登录页 | LoginPage + 鉴权 guard（e2e：非 admin 拦截 data console、无 paper 权限拦截 paper） | MFA/注册/会话恢复完整度待确认 | 非阻断 |

> 说明：gap-audit 列为 P0 的"认证/analysis/playbook/lane/paper 下单"已落地；剩余多为"深度交互完整度待人工逐项核对"，非"页面存在但功能不存在"。

---

## 5. 视觉/布局问题清单（按页面）

- **/next/analysis（RQ-1）**：相似度 0.7767，密度/信息组织与 spec 差距最大 —— 本轮最该处理的视觉项。
- /next/paper：0.8826，9 页中次低；机甲 HUD 已保留为 display/review。可继续对齐持仓卡/结论条密度（上轮已 +0.0076）。
- /next/backtest：0.9154；playbook 0.9158 —— 可作下一轮微调，但已达标。
- 其余 5 页 ≥ 0.93，视觉风险低。
- 全局：`!important`×51（OP-3）是后续微调的隐患，建议同步收敛。

---

## 6. CSS 可合并/可删除清单

- **可删/可注释别名**：`DataGrid.tsx`（OP-1，TS 别名，非 CSS）。
- **可合并 CSS**：
  - feature-slice 与 legacy-workspace 双源（paper / strategy-tracking / backtest）（OP-4）。
  - login-* 5 文件 → 2 文件（OP-5）。
- **未发现 orphan CSS**：`legacy-workspace.css` → `workspace.css`（8 个 `@import`）→ 嵌套子 barrel（login/primitives），每个 `legacy-workspace/*.css` 均被引用恰好 1 次（G2 清理成立）。
- **`:has()` 外壳覆盖**：仅剩 1 处合法局部用法 `backtest-slice.css:407 .backtest-strategy-tile:has(input:checked)`（G3 移除页面级 `:has` 外壳成立）。
- CSS 入口干净：`index.tsx` 3 个全局（tokens / legacy-workspace barrel / legacy-solid-adapter）+ 每页 1 个 slice。

---

## 7. shared UI 可抽象/已抽象清单

- **已抽象并复用**（G4/G6 成立）：`Icon`、`PagePanel`、`Panel`（复用 PagePanel）、`DenseTable`、`StatusBadge`、`DataTable`、`MetricGrid` 等 24 个 wrapper 在 `shared/ui/`。
- **可进一步收敛**：
  - `DataGrid` = `DataTable` 别名（OP-1）。
  - `StatusBadge`/`StatusPill`/`Tag` tone API 统一（OP-2）。
- **契约层抽象优秀**：`shared/api/types.ts` 用 `ApiGet<"/api/...">` 从 `generated/api-types` 的 `paths`/`components` **类型级派生**所有响应 DTO，零手写 DTO；feature 页经 `operations.ts` 消费 —— contract-first 链路标准实现，**非问题**。

---

## 8. API / 请求 / 错误处理

- **OpenAPI generated types**：被 `shared/api/types.ts` + `operations.ts` 集中消费并派生（§7）；`api:check` 通过 —— 契约事实源成立，无手写 DTO 旁路。
- **typed client / queryKeys**：`shared/api/{client,operations,queryKeys,mutations,errors,safeWriteContracts}.ts` 分层清晰；`queryKeys.ts`(77L) 统一 key。
- **写操作 guard**：paper 下单为确认门两段提交（`PaperOrderForm.tsx:90`）；e2e `interaction-parity` / `no-write` 通过；mutation 默认不发真实写。
- **错误处理缺口（RQ-2）**：strategy-tracking 422、settings 503×4 在采样环境出现；需确认前端对这些路径有显式空态/错误态而非静默空白（e2e 证明页面壳不崩，但数据态需核对）。

---

## 9. K 线 / Worker / 生产策略边界核查结论

**全部合规。**
- **K 线**：`lightweight-charts` 仅出现在 `shared/charts/KlineChart.tsx`；`echarts` 仅出现在 `shared/charts/EchartsIsland.tsx`（低频 adapter）。`check-boundary-guard.mjs` 在 lint 中强制（阻止 feature K 线直引 ECharts）。
- **Worker**：`shared/workers/computeSync.ts` 仅 `filterItems`（关键词过滤）/`downsample`（图表降采样）/`sortItems`（按调用方 key 的通用显示排序）/`deriveSummary`（仅 `count total` + `count with finite score`）。**不重算 production_score、不重排生产榜、不做策略判断**。`:35` 只读 `production_score` 做计数。
- **生产策略边界**：`monitor-action` lane 切换是按服务端 `item.lane` 的**客户端过滤**（`MonitorActionPage.tsx:541 items.filter(item.lane===lane)`），不重排、不重打分；`analysisModel.test.ts:49` 守"不臆造策略字段"。
- **机甲**：仅在 `/next/paper` display/review（`workspace-paper-mecha.css`），不参与排序/信号/交易判断。

## 9b. 性能与 bundle 风险

- 总 JS ~1.19MB < 1.25MB 预算门（lint 通过）。
- 最大块：`echarts-charts` 284KB/gzip 95KB、`echarts-components` 160KB/54KB、`vendor` 160KB/52KB、`tanstack` 159KB/46KB —— 均**独立 code-split chunk**（非首屏 index）。页面块 20–57KB（PaperPage 56KB 最大）。
- **风险点（Optional）**：echarts 两块共 ~444KB raw，虽 lazy，但凡引入 `EchartsIsland` 的页面（如 backtest）会拉入；KlineChart 走 lightweight-charts 已规避主路径。建议确认 9 页首屏均不**预加载** echarts。
- perf（引用今日 G1-G7）：monitor 1718ms/DOM230/API2、market 732ms/DOM271/API2、paper 1967ms/DOM403/API2、strategy-tracking 1906ms/DOM226/API9（items 422）。paper DOM 403 偏高，可作虚拟化/降 DOM 观察项。

---

## 10. 测试缺口

- **现状**：unit 83、e2e 35（含鉴权/权限/移动导航/no-write/机甲可见/worker sync/mutation guard）。
- **缺口**：
  1. **功能级 E2E 不足**：多数仍偏 smoke/shell + no-write；analysis 真实 `/analyze` 流程、playbook screener 联动、paper 确认门下单的**断言深度**待加强（gap-audit §5 已指出"只测 shell 不测功能"）。
  2. **错误态测试缺**：strategy-tracking 422 / settings 503 的前端降级态无专门断言。
  3. **视觉回归**：analysis 0.7767 无阈值守卫（建议把 parity 阈值纳入 CI gate）。
- 未发现"过度宽松断言"明显反例，但功能深度断言不足是 cutover 前的真实缺口。

---

## 11. 不应修改项确认（回归风险）

| 项 | 结论 | 证据 |
|---|---|---|
| 旧 `frontend/` | **未改动** | `git diff -- frontend` = 0 行；`git status` 无 tracked `M` |
| 后端 | **未改动** | `git diff -- backend` = 0 行 |
| `strategy_policy.py` | **未改动** | 同上；`check-boundary-guard.mjs` 阻止依赖 |
| 生产排序 / production_score / priority_board | **未改动语义** | Worker 只读计数、lane 仅客户端过滤、无重排（§9） |
| `git diff --check` | clean | 仓库根 |

全部 dirty 项均为 `??` untracked（`frontend-next/` + `docs/`）。

---

## 12. 是否影响平台功能

**不影响。**
- 本轮仅审查 + 新增本报告，未改任何 tracked 业务代码。
- 旧 `frontend/`、后端、`strategy_policy.py` 0 改动（§11）。
- 新前端仍挂 `/next/*`，写入默认关闭、走 mutation guard；未部署、未切流。
- Worker / K 线 / 机甲 / lane 均在显示层，不触碰生产策略口径（§9）。

---

## 13. 下一步修复优先级

**P0（cutover 前必须）**
1. RQ-2：后端确认 `/api/strategy-tracking/items` 422 参数契约 + `/api/settings*` 503 环境依赖；前端核对这两类路径的显式错误/空态。
2. 功能级 E2E 补齐（analysis/playbook/paper 下单的真实流程断言）—— cutover 不能只靠 smoke。

**P1（cutover 前应做）**
3. RQ-1：`/next/analysis` 视觉对齐 spec（密度/布局），把 parity 0.7767 拉到 ≥0.85，并把 parity 阈值纳入 CI gate。
4. 把 gap-audit-2026-06-06 标记 superseded（FY-2）。
5. 逐页深度交互完整度人工核对（§4 "待确认"列）。

**P2（可维护性，非阻断）**
6. OP-1 删 `DataGrid` 别名；OP-2 徽标 tone 统一；OP-3 收敛 `!important`（先 monitor-market 8 处）；OP-4/OP-5 CSS 合并；FY-1 admin token 掩码/不持久化核对；echarts 首屏预加载核对。

---

## 14. 审查方法说明

- 命令证据为本轮新跑（perf 引用同日 G1-G7）。
- 代码定位均给文件:行号；未实跑到的"深度交互完整度"统一标注"待确认"，不写成确定缺失结论。
- 本报告不修改任何代码；如需我按 P0/P1/P2 落地修复，请明确授权。
