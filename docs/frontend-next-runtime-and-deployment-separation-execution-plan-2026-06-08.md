# frontend-next 运行时修复与前后端数据库分离部署完整开发计划

日期：2026-06-08
项目：`/Users/j/Documents/gupiao`
状态：待实施开发计划
范围：`frontend-next/` 性能与运行时 blocker 修复、必要报告更新、前端/后端/数据库独立部署拓扑设计与落地

## 1. 一句话结论

本计划分两条主线串行落地：

1. 先修 `frontend-next/` 当前再审查报告中的 O1/O2 运行时证据缺口、O3 CSS 体积、O4 ECharts 体积、O5 TanStack/首屏块问题，确保 `/next/*` 本地验收具备真实数据和稳定门禁。
2. 再推进部署拓扑分离，把当前“FastAPI 同时托管 API 与前端静态资源”的形态演进为“frontend 静态服务 + backend API 服务 + worker + MySQL/Redis 数据层”可独立部署形态。

本轮默认不部署、不切流、不改旧 `frontend/`、不改后端业务、不改 `strategy_policy.py`。若后续进入部署阶段，必须由用户单独授权。

## 2. 当前事实基线

### 2.1 当前工作区保护

实施前必须执行：

```bash
cd /Users/j/Documents/gupiao
git status --short
```

当前已知存在未提交或未跟踪改动，必须保护，不得覆盖：

```text
backend/tests/test_low_buy_read_paths.py
frontend-next/src/features/monitor-market/MonitorMarketPage.tsx
frontend-next/src/features/monitor-market/monitorMarketModel.ts
frontend-next/src/features/playbook/PlaybookPage.tsx
frontend-next/src/features/playbook/playbookModel.test.ts
frontend-next/src/features/playbook/playbookModel.ts
frontend-next/tests/e2e/monitor-workflows.spec.ts
frontend/src/features/workspace-shared/todayRecommendations.test.ts
frontend/src/features/workspace-shared/todayRecommendations.ts
frontend/src/workers/__tests__/computeSync.test.ts
frontend/src/workers/computeSync.ts
go-services/bff-gateway/cmd/bff-gateway/main_test.go
go-services/bff-gateway/cmd/bff-gateway/workspace_aggregate.go
docs/reports/frontend-next-reaudit-2026-06-07.md
docs/reports/strategy-frontend-display-correctness-audit-2026-06-08.md
frontend-next/src/features/monitor-market/monitorMarketModel.test.ts
frontend-next/tests/e2e/page-function-matrix.spec.ts
```

规则：

1. 不回退上述改动。
2. 如必须编辑同一文件，先读 diff，确认不会覆盖用户或其他线程改动。
3. 本计划产出阶段只允许新增/更新本计划文档；执行阶段按任务最小范围改动。

### 2.2 frontend-next 再审查结论

`docs/reports/frontend-next-reaudit-2026-06-07.md` 的关键结论：

| 项 | 状态 | 需要补做 |
| --- | --- | --- |
| O1 strategy-tracking 合包 | 源码已接，运行时待测 | 启动后端后跑 `perf:compare`，验证 API 请求数 <=2 |
| O2 paper 虚拟化 | 源码已接，运行时待测 | 验证 DOM 节点下降；若不达标修 `VirtualList` fallback |
| O3-a `!important` | 已从 51 降至 23 | 保持 <=25 |
| O3-b CSS 体积 | 未达标，约 235KB | 目标 raw <=180KB |
| O4 ECharts | 未达标，约 447KB | 移除运行时 ECharts 或确保非首屏且显著瘦身 |
| O5 TanStack/首屏块 | 未达标，tanstack 反增 | 拆 manual chunks，首屏 raw <=350KB |

### 2.3 当前部署拓扑结论

当前生产拓扑是“部分分离”：

1. MySQL、Redis 已独立容器运行。
2. Web/API、runtime worker、scheduler、analytics worker、backtest worker、Go BFF/market-read/scan worker 已按进程角色分离。
3. `frontend/` 和 `frontend-next/` 虽独立构建，但最终 `dist` 被复制进 Python `app` 镜像，由 FastAPI 托管静态资源。
4. nginx 当前将 `/api/` 和 `/` 都 proxy 到同一个 backend app 端口。

目标是新增真正独立的 `frontend-web` 静态服务，使前端、后端 API、worker、数据库可以分别部署、重启和回滚。

### 2.4 frontend-next 策略展示正确性审计结论

来源：`docs/reports/frontend-next-strategy-display-correctness-audit-2026-06-08.md`。

该审计覆盖 `/next/monitor`、`/next/monitor/market`、`/next/strategy-tracking`、`/next/backtest`、`/next/paper`、`/next/playbook` 的策略展示链路，对照后端真实策略数据、API 契约和旧前端已验证行为。

已确认正确的能力：

1. priority board 嵌套路径读取正确，优先读取 `monitor_snapshot.priority_board`。
2. frontend-next 展示层没有重排 `priority_score`、`production_score` 或后端生产榜顺序。
3. lane/tab 只做展示过滤，不改变后端排序语义。
4. stale、fallback、empty、data_quality 有显式展示。
5. `strategy_engine` 仅作为 shadow/parity 文案展示，不参与生产排序或打分。
6. API 类型以 `generated/api-types` 派生，优于手写 DTO。
7. 在途 `monitor-market` 的 `toPercentValue` 修复方向正确：缺数据返回 `NaN`，不再假报 75%。
8. 在途 `playbookCandidates` 修复方向正确：优先真实 screener，空时回退 priority board，lane 只过滤不重排。

审计中需要纳入本计划的问题：

| 编号 | 状态 | 处理结论 |
| --- | --- | --- |
| F1 strategy-tracking 影子一致性假报 `99.2%` | 审计称已最小修复；当前文件已见 fallback 为 `"--"` | 加回归守卫，防止假分回流 |
| F2 strategy-tracking 编造策略叙述兜底 | 审计称已最小修复 | 加 grep/单测守卫，缺数据必须显示占位 |
| F3 backtest 执行假设口径不一致 | 需修复/需量化确认；当前文件似已改为读取 run 字段，但仍需验证 label 与字段语义 | 加专项任务，接真实 `execution_assumptions` 或改成明确版本/模型展示 |
| F4 paper 机甲 HUD 同步率硬编码 | 装饰项，可接受 | 不作为 blocker；可选加“示意”标注 |
| F5 strategy-tracking 漂移面板硬编码兜底和健康状态 | 仍需系统性 sweep | 加专项修复，禁止缺数据时断言“可接受/高速级/无异动” |
| E2E 失败：移动导航到 playbook | 在途改动面 | 作为最终门禁 blocker 处理 |
| E2E 失败：monitor-market 闸门模式 | 在途改动面 | 作为最终门禁 blocker 处理 |

原则：F3/F5 属展示映射、契约、兜底文案问题，可在 `frontend-next/` 内直接修；若发现后端缺少必要 `execution_assumptions` 字段，只记录最小后端契约建议，不在本轮擅自改后端。

## 3. 硬边界

1. 不改旧 `frontend/` 生产代码，除非用户单独授权。
2. 不改 `strategy_policy.py`。
3. 不改变生产策略语义、`production_score`、`priority_board` 排序和口径。
4. 不改后端业务逻辑；部署分离阶段如需后端 API-only 开关，只做最小配置和静态托管边界改造。
5. 不部署、不切流；部署必须再次得到用户明确授权。
6. 不留下测试脏数据。
7. 真实写操作必须隔离写入、rollback、读回一致、403 权限断言。
8. `frontend-next/` 不换栈，继续 SolidJS + TanStack + Lightweight Charts + Worker。
9. K 线继续使用 Lightweight Charts，不改回 ECharts。
10. Worker 只做展示层 filter/sort/derive/downsample，不做生产策略判断。
11. DuckDB/Parquet 只作为分析层和报告层，不作为生产交易事实源。
12. CSS 优化不得盲目 PurgeCSS；必须结合 unused report、DOM class 检查和截图验证。

## 4. 多 Agent 协作执行编排

本计划执行时默认遵循 `/Users/j/Documents/gupiao/AGENTS.md` 的角色顺序和工程边界。`trading-platform-supervisor` 负责总控、风险升级、跨阶段验收和是否进入部署授权申请；任何角色都不得绕过第 3 节硬边界。

### 4.1 执行顺序

1. `trading-quant-lead`
2. `stock-analysis-specialist`
3. `product-strategist`
4. `ui-designer`
5. `fullstack-builder`
6. `qa-tester`
7. `devops-operator`

### 4.2 角色职责映射

| 角色 | 本计划职责 | 输出物 |
| --- | --- | --- |
| `trading-quant-lead` | 确认 P6 中 F3/F5 不改变策略公式、生产排序、风控阈值；确认 backtest 执行假设只做展示口径修正 | 策略边界确认、量化口径待确认清单 |
| `stock-analysis-specialist` | 核对 `/next/monitor`、`/next/playbook`、`/next/strategy-tracking` 的策略 key/title/family/lane、状态、标签、失效条件展示是否与真实数据一致 | 策略展示字段核对清单 |
| `product-strategist` | 将 O1-O5、F1-F5、分离部署目标转成页面能力、空态、错误态、权限态和验收标准 | 页面验收矩阵、blocker 优先级 |
| `ui-designer` | 确认 CSS 拆分、ECharts 替换、移动导航修复后，桌面/移动不遮挡、不堆叠、不横向溢出 | screenshot parity 和视觉风险记录 |
| `fullstack-builder` | 实施 `frontend-next/` 修复、轻量图表、chunk/CSS 优化、API-only 静态托管开关、frontend-web 独立服务、本地 compose | 代码、测试、分离部署工件 |
| `qa-tester` | 执行 P7/P9 全量门禁、Playwright、perf、screenshot、策略展示专项测试、边界检查 | 验证命令结果、失败根因、残留风险 |
| `devops-operator` | 准备但不执行云端部署：nginx 模板、scope、rollback、runbook、资源/健康检查清单 | 分离部署 runbook、rollback 清单、授权前检查 |

### 4.3 交接规则

1. `trading-quant-lead` 和 `stock-analysis-specialist` 先于产品和工程确认策略展示边界；如果发现疑似策略逻辑问题，只记录证据和量化待确认，不直接改公式。
2. `product-strategist` 必须把缺数据、stale、fallback、权限不足、超时态写入验收矩阵，避免 UI 把缺数据展示成正常结论。
3. `fullstack-builder` 只按已确认的展示契约和性能目标实现；如必须碰后端，仅限 API-only 静态托管开关或契约缺口报告。
4. `qa-tester` 的结论以命令和截图证据为准；不能用脏 worktree 假绿。
5. `devops-operator` 只准备部署和回滚材料，不执行云端部署、不切流。

## 5. 端态目标

### 5.1 frontend-next 端态

| 指标 | 目标 |
| --- | ---: |
| `/next/strategy-tracking` API 请求数 | <=2 |
| `/next/strategy-tracking` fallback 到 `/api/strategy-tracking/items` | 无无故 fallback |
| `/next/paper` DOM 节点 | 达到 perf 目标，虚拟列表真实生效 |
| CSS raw | <=180KB |
| `!important` | <=25 |
| ECharts 初始 assets | 0 |
| ECharts lazy assets | 0，优先移除；若保留则显著低于当前约 457KB |
| initial JS raw | <=350KB |
| `tanstack-virtual` | 不进入初始 HTML modulepreload/script |
| strategy-tracking 影子一致性/策略叙述兜底 | 缺数据显示 `"--"`，不显示假分或编造结论 |
| strategy-tracking 漂移面板 | 缺真实数据时不显示“可接受/高速级/无异动”等断言状态 |
| backtest 执行假设展示 | 与后端 `execution_assumptions` 或 run 字段语义一致 |
| frontend-next 策略展示 E2E | playbook 移动导航、monitor-market 闸门模式不失败 |
| screenshot parity | 不回退 |
| API/type/lint/test/build/e2e | 全绿 |

### 5.2 独立部署端态

```text
公网 HTTPS / IP
  ↓
Nginx Gateway
  ├─ /              -> frontend-web 静态服务，旧 frontend/dist
  ├─ /next/*        -> frontend-web 静态服务，frontend-next/dist
  ├─ /assets/*      -> frontend-web 静态资源
  ├─ /next/assets/* -> frontend-web 静态资源
  ├─ /api/*         -> backend-api FastAPI
  ├─ /readyz        -> backend-api
  └─ /ws/*          -> backend-api，如后续存在 WebSocket

backend-api
  ├─ auth / permission / settings
  ├─ API routes
  ├─ BFF workspace read
  ├─ light query
  └─ task submit/status

workers
  ├─ runtime-worker
  ├─ runtime-scheduler
  ├─ analytics-worker
  └─ backtest-worker

data
  ├─ mysql
  ├─ redis
  └─ app_runtime_data / analytics artifacts
```

验收：

1. frontend-web 可单独部署、重启、回滚。
2. backend-api 可单独部署、重启、回滚。
3. worker 可单独部署、重启、回滚。
4. MySQL/Redis 独立健康检查、备份、恢复。
5. backend-api 重启不造成前端动态 chunk 缺失。
6. frontend-web 重启不影响 `/api/readyz`。

## 6. 执行阶段总览

| 阶段 | 名称 | 范围 | 是否可并行 |
| --- | --- | --- | --- |
| P0 | 隔离与基线 | git/status、build、chunk/css/perf 基线 | 必须最先 |
| P1 | O1/O2 运行时证据 | 本地后端 + `perf:compare` + `screenshot:parity` | P0 后 |
| P2 | O2 虚拟化兜底修复 | `VirtualList.tsx` fallback | 仅 O2 不达标时 |
| P3 | O3 CSS 体积修复 | global CSS 拆分、路由样式收敛 | P1 后 |
| P4 | O4 ECharts 体积修复 | 替换为轻量 SVG/Canvas chart | P1 后 |
| P5 | O5 TanStack/首屏块修复 | `vite.config.ts` manualChunks | P3/P4 后 |
| P6 | 策略展示正确性专项 | F1/F2 回归守卫、F3 backtest 执行假设、F5 漂移面板、在途 E2E blocker | P1 后，可与 P3-P5 并行但必须在最终门禁前完成 |
| P7 | frontend-next 最终门禁 | API/type/lint/test/build/e2e/perf/visual | P2-P6 后 |
| P8 | 分离部署设计落地 | frontend-web、API-only、nginx、deploy scopes | P7 后 |
| P9 | 分离部署本地验收 | separated compose 本地验证 | P8 后 |
| P10 | 云端部署准备文档 | runbook、rollback、授权清单 | P9 后，不自动部署 |

## 7. P0：隔离与基线

### 6.1 工作区保护

```bash
cd /Users/j/Documents/gupiao
git status --short
git diff --stat
```

产出：

1. 在实施报告中记录脏文件清单。
2. 明确哪些文件是本轮新增/修改。
3. 若发现同一文件存在他人改动，必须先读 diff 再改。

### 6.2 frontend-next 静态基线

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run build
npm run chunk:profile
npm run css:budget
npm run css:unused-report
```

产出：

1. 更新或新增 `docs/reports/frontend-next-runtime-and-bundle-fix-2026-06-08.md`。
2. 写入新数字：JS raw/gzip、initial JS raw、CSS raw、ECharts assets、TanStack assets、`!important` 数。
3. 若 build 失败，先定位，不进入 P1。

## 8. P1：补 O1/O2 运行时证据

### 7.1 启动本地后端

建议使用现有本地启动方式，确保 API 在 `127.0.0.1:8000`：

```bash
cd /Users/j/Documents/gupiao
# 按当前项目 runbook 启动 backend app，确保 /readyz 可访问
curl -fsS http://127.0.0.1:8000/readyz
```

不得绕过鉴权或写入生产数据。

### 7.2 运行 perf 与截图

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run perf:compare
npm run screenshot:parity
```

验收：

1. `/next/strategy-tracking` API 请求数 <=2。
2. `/next/strategy-tracking` 没有无故 fallback 到 `/api/strategy-tracking/items`。
3. `/next/paper` DOM 节点或非机甲区节点降到目标范围。
4. 虚拟列表实际生效，不是源码接入但运行时全量渲染。
5. screenshot parity 不回退。

若后端无法启动，记录 blocker，不把 O1/O2 写成已完成。

## 9. P2：修 O2 VirtualList 初始 fallback

触发条件：P1 显示 `/next/paper` DOM 未达标，或虚拟列表在 `scrollReady=false` 初始状态渲染全部 items。

### 8.1 根因

当前 `frontend-next/src/shared/ui/VirtualList.tsx` 在 virtualizer 尚未 ready 时，fallback 会将 `props.items` 全量 map 成虚拟项。长列表初始帧仍可能渲染全部 items，导致 DOM 未真正下降。

### 8.2 修复方案

修改 `VirtualList.tsx`：

1. 增加 `initialItemLimit` 或内部首屏估算数量。
2. `scrollReady=false` 时只渲染首屏有限数量，例如：
   - `Math.ceil((maxHeight / estimateSize) + overscan * 2)`
   - 至少 1，最多不超过 20 或可配置上限。
3. 容器总高度仍使用 `items.length * estimateSize()` 保持滚动条语义。
4. virtualizer ready 后切回真实 `getVirtualItems()`。
5. 空态、loading、aria、键盘滚动不回退。

### 8.3 测试

新增或更新：

1. `frontend-next/src/shared/ui/__tests__/VirtualList.test.tsx`
2. `frontend-next/src/features/paper/PaperPage.test.tsx` 或现有 paper model/page 测试
3. E2E perf 断言：长列表不全量渲染

命令：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm test -- --run src/shared/ui
npm run perf:compare
```

## 10. P3：修 O3-b CSS 体积

### 9.1 根因

当前 `frontend-next/src/index.tsx` 全局引入：

```ts
import "./shared/styles/tokens.css";
import "./shared/styles/legacy-workspace.css";
import "./shared/styles/legacy-solid-adapter.css";
```

其中 `legacy-workspace.css` 继续把 login、paper、strategy、backtest、monitor、settings 等旧样式打进首屏 CSS，导致全局 CSS raw 约 235KB，目标 <=180KB 未达。

### 9.2 拆分原则

1. 全局只保留：
   - `tokens.css`
   - 必要 reset/base
   - 必要 shell adapter 基础样式
2. 页面样式改为路由内 import。
3. 不盲目 PurgeCSS 删除。
4. 先用 `css-unused-report` 得候选，再用截图和 DOM class 检查确认。
5. 每次删样式必须能解释“该选择器在哪个页面不再使用”。

### 9.3 具体拆分

| 样式组 | 目标落点 |
| --- | --- |
| `workspace-login*` | `LoginPage` 路由样式 |
| `workspace-paper*` | paper 路由样式，和 `paper-page.css` 去重合并 |
| `paper-page.css` | 保留 paper 专属，删除和 workspace-paper 重复规则 |
| `workspace-strategy-tracking.css` | strategy-tracking 路由样式 |
| `strategy-tracking.css` | 与 workspace strategy 样式去重 |
| backtest 样式 | backtest 路由内加载 |
| monitor 样式 | monitor/market 路由内加载 |
| settings 样式 | settings 路由内加载 |
| shared primitive | 只保留跨页面真实复用的 selector |

### 9.4 验收

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run build
npm run css:budget
npm run css:unused-report
npm run screenshot:parity
```

目标：

1. `dist` CSS raw <=180KB。
2. `!important` <=25。
3. screenshot parity 不回退。
4. login、paper、strategy-tracking、backtest、monitor、settings 页面无遮挡、无样式丢失。

若 <=180KB 不可达，必须在报告中列出不可删样式组、对应页面和保留原因。

## 11. P4：修 O4 ECharts 体积

### 10.1 优先方案：移除 frontend-next ECharts 运行时

当前 `frontend-next` 只在 backtest 简单权益曲线使用 `EchartsIsland`。优先将其替换为轻量 SVG 或 Canvas chart。

要求：

1. 新增轻量 chart 组件，例如 `frontend-next/src/shared/charts/EquitySparklineChart.tsx` 或 backtest 内部 chart 组件。
2. 保留：
   - 非空渲染
   - 空态
   - hover tooltip 或等价读数反馈
   - 可访问 label
   - 截图稳定性
3. `BacktestPage.tsx` 从 `EchartsIsland` 改用轻量组件。
4. 若 `EchartsIsland` 无其他引用，删除运行时入口。
5. 若 `echarts` 无其他引用，从 `frontend-next/package.json` 和 lockfile 移除。

### 10.2 备选方案：保留但动态隔离

仅当产品明确要求 ECharts 交互时采用：

1. 把 chart island 移入 backtest 页面内部动态导入。
2. 拆更细 manualChunks。
3. 保证 initial ECharts assets = 0。

但该方案收益不如直接替换，不作为默认。

### 10.3 验收

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm test -- --run src/shared/charts src/features/backtest
npm run build
npm run chunk:profile
npm run e2e -- tests/e2e/backtest*.spec.ts
```

目标：

1. `dist/assets/echarts-*.js` 为 0；或如保留则显著低于当前约 457KB。
2. initial ECharts assets = 0。
3. backtest 图表非空渲染。
4. backtest 页面 smoke 通过。

## 12. P5：修 O5 TanStack/首屏块

### 11.1 根因

当前 `frontend-next/vite.config.ts` 将所有 `@tanstack/*` 合成一个 `tanstack` chunk。`@tanstack/solid-virtual` 被 `/next/paper` 虚拟列表引入后，可能抬高首屏块。

### 11.2 修复方案

修改 `splitVendorChunks`：

```text
@tanstack/solid-router -> tanstack-router
@tanstack/solid-query  -> tanstack-query
@tanstack/solid-table  -> tanstack-table
@tanstack/solid-virtual -> tanstack-virtual
其他 @tanstack/*       -> tanstack-misc
```

要求：

1. `tanstack-virtual` 只随 `/next/paper` 或使用虚拟化的懒加载页加载。
2. 不进入首屏初始 HTML 的 modulepreload/script。
3. 不破坏 router/query/table 的缓存和懒加载。

### 11.3 验收

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run build
npm run chunk:profile
```

目标：

1. initial JS raw <=350KB。
2. initial ECharts assets = 0。
3. `tanstack-virtual` 不在初始 HTML modulepreload/script 中。
4. bundle budget guard 通过。

## 13. P6：策略展示正确性专项

本阶段来自 `docs/reports/frontend-next-strategy-display-correctness-audit-2026-06-08.md`。目标是消除 `/next/*` 策略相关页面里的展示造假、硬编码健康状态、执行假设口径不一致和在途 E2E blocker。

### 12.1 P6-a：F1/F2 回归守卫

F1/F2 在审计报告中已标记为最小修复；当前代码也应保持缺数据时显示 `"--"`，不得恢复假分或编造结论。

守卫对象：

1. `StrategyTrackingPage.tsx` 不得出现 `"99.2% (影子校验)"`。
2. `StrategyTrackingPage.tsx` 不得出现 `"冲高未止盈 · 原低吸策略 · 影子校验一致"` 这类无数据时的具体策略结论。
3. 影子一致性字段缺失时显示 `"--"`。
4. summary/reason 字段缺失时显示 `"--"` 或明确空态，不编造策略判断。

建议补测试：

1. `frontend-next/src/features/strategy-tracking/strategyTrackingDisplay.test.ts`
2. 或扩展现有 `StrategyTrackingPage` 测试，构造缺失 `shadow_consistency`、缺失 summary 的 payload。

命令：

```bash
cd /Users/j/Documents/gupiao/frontend-next
rg -n "99\\.2%|冲高未止盈|影子校验一致" src/features/strategy-tracking
npm test -- --run src/features/strategy-tracking
```

验收：

1. grep 无旧造假串。
2. 缺数据测试断言显示占位。
3. 不改变 strategy_engine shadow-only 边界。

### 12.2 P6-b：F3 backtest 执行假设口径修复

问题：审计报告指出 backtest 专家提交面板曾硬编码：

1. `单笔最大仓位 10%`
2. `双向滑点 1.5bp`
3. `综合手续费率 0.03%`

后端真实口径来自 `backend/app/services/backtest/engine_helpers.py` 的 `execution_assumptions()`，其中手续费模型为：

1. 股票买卖双边按成交额 `0.0085%` 估算，单笔最低 5 元。
2. ETF/基金类按成交额 `0.005%` 估算。
3. 股票卖出印花税 `0.05%`。
4. 股票过户费 `0.001%`。
5. source 为 `app.services.paper.fees.calculate_fee`。

当前 `BacktestPage.tsx` 看起来已改为读取 `latestRun().params.max_position_pct`、`latestRun().slippage_bps`、`latestRun().fee_model_version`，但仍需确认：

1. label `综合手续费率` 与值 `fee_model_version` 语义不一致，可能把“模型版本”展示成“费率”。
2. 若 API response 已包含 `execution_assumptions`，应直接展示真实 commission/stamp_tax/transfer_fee/slippage_model 文案。
3. 若 API response 未包含该字段，前端不得硬编码费率数字；应显示 `fee_model_version` 并把 label 改为 `费率模型`，或显示 `"后端未返回执行假设"`。

优先修复方案：

1. 在 `backtestModel.ts` 增加 `executionAssumptionRows(detailOrRun)` normalizer。
2. 优先读取：
   - `execution_assumptions.fee_model.version`
   - `execution_assumptions.fee_model.commission`
   - `execution_assumptions.fee_model.stamp_tax`
   - `execution_assumptions.fee_model.transfer_fee`
   - `execution_assumptions.slippage_model.*`
3. 若无 `execution_assumptions`：
   - `单笔最大仓位` 读取 `params.max_position_pct`，无值显示 `"--"`。
   - `双向滑点 (bp)` 读取 `slippage_bps`，无值显示 `"--"`。
   - 将 `综合手续费率` 改为 `费率模型`，值读取 `fee_model_version`，无值显示 `"--"`。
4. 不在前端写死 `0.03%`、`0.0085%`、`0.005%` 等费率，除非这些数字来自后端 payload。
5. 如后端契约确实缺 `execution_assumptions`，本轮只记录最小后端契约建议，不擅自改后端。

测试：

1. `backtestModel.test.ts` 覆盖有 `execution_assumptions`、只有 run 字段、字段缺失三类。
2. `BacktestPage` 页面测试覆盖 label 不误导。
3. grep 确认 frontend-next 无硬编码旧费率。

命令：

```bash
cd /Users/j/Documents/gupiao/frontend-next
rg -n "综合手续费率|0\\.03%|0\\.0085|0\\.005|单笔最大仓位 10|1\\.5bp" src/features/backtest
npm test -- --run src/features/backtest
```

验收：

1. 前端不再把模型版本展示成费率。
2. 执行假设展示来自后端字段或明确缺失。
3. 不改变回测提交参数和后端回测逻辑。

### 12.3 P6-c：F5 strategy-tracking 漂移面板 sweep

问题：`StrategyTrackingPage.tsx` 的漂移面板仍存在硬编码兜底和健康状态：

1. `均化滑点损失` fallback `"-0.12% / 交易"`。
2. `实盘信号响应延时` fallback `"平均 0.85 秒"`。
3. `status="可接受"`。
4. `status="高速级"`。
5. `status="无异动"`。
6. `PanelHead badge="轻微滑点"` 在无真实数据时也会断言状态。

修复原则：

1. 缺真实数据时显示 `"--"`，不展示假滑点、假延时。
2. status 必须来自后端字段或由明确阈值函数根据真实数值派生。
3. 如果没有真实数值，status 显示 `待确认`、`暂无数据` 或不显示。
4. 面板 badge 不得在缺数据时固定为 `轻微滑点`；可改成 `数据待确认` 或根据状态派生。
5. 任何派生状态必须集中到 model/helper，避免页面散落硬编码。
6. 不使用 strategy_engine shadow 字段替代生产排序或生产分。

建议实现：

1. 在 `strategyTrackingModel.ts` 或本页 helper 中新增：
   - `formatDriftMetric(value, suffix?)`
   - `deriveDriftStatus(metric)`
   - `buildDriftRows(reviewPayload, fallbackItems)`
2. 每行结构：
   - `label`
   - `value`
   - `status`
   - `hasData`
   - `source`
3. `hasData=false` 时 value/status 都为占位或空态。
4. 对 `slippage_pct`、`latency_ms`、`order_consistency` 分别定义展示规则。
5. 若后端字段缺失，显示 `暂无实盘漂移数据`，而不是回退到当前筛选结果并断言健康。

测试：

1. 缺漂移 payload：三行都显示 `"--"` 或 `暂无数据`。
2. 有真实滑点/延时/一致性：正确格式化。
3. status 来自字段或阈值，非固定常量。
4. grep 确认旧硬编码串消失。

命令：

```bash
cd /Users/j/Documents/gupiao/frontend-next
rg -n "均化滑点损失|平均 0\\.85|可接受|高速级|无异动|轻微滑点|-0\\.12% / 交易" src/features/strategy-tracking
npm test -- --run src/features/strategy-tracking
```

验收：

1. 缺数据不再显示“可接受/高速级/无异动”。
2. 无真实字段不再假报滑点和延时。
3. 视觉上仍有明确空态反馈。

### 12.4 P6-d：F4 paper 机甲 HUD 装饰确认

F4 审计结论为 FYI：机甲 HUD `syncRate` 是 display/review 装饰，非策略、绩效、排序或交易判断数据。

默认处理：

1. 不作为 blocker。
2. 不强制修改。
3. 若后续视觉审查担心误读，可把 label 从 `同步` 调整为 `状态动画` 或加 `示意`，但不得引入假策略指标。

验收：

1. paper 机甲 HUD 不参与任何排序、信号、交易判断。
2. 页面文案不暗示 `syncRate` 是真实绩效或行情同步率。

### 12.5 P6-e：在途 E2E blocker 收敛

审计报告记录 `npm run e2e` 两个失败：

1. `app-shell-auth.spec.ts:195`：移动导航 monitor -> playbook。
2. `page-function-matrix.spec.ts:61`：`/next/monitor/market` 闸门模式。

处理原则：

1. 两个失败虽然来自在途改动面，但最终门禁必须收敛。
2. 先确认失败是否仍可复现；若已被并行改动修复，只记录验证结果。
3. 若仍失败，只修 `frontend-next/` 对应页面/测试契约，不改旧 `frontend/`、不改后端策略。
4. 移动导航只做基本可用和无阻塞，不扩大为完整移动端改造。
5. monitor-market 闸门模式必须确认真实数据缺失、stale、fallback、权限态有明确文案，不允许假默认。

命令：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npx playwright test tests/e2e/app-shell-auth.spec.ts tests/e2e/page-function-matrix.spec.ts --project=chromium
```

验收：

1. 两个专项 E2E 通过。
2. 全量 `npm run e2e` 通过。
3. 若因后端缺数据导致无法通过，记录 blocker，不伪造数据。

### 12.6 P6 验证命令

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run typecheck
npm run lint
npm test -- --run src/features/strategy-tracking src/features/backtest src/features/paper
npx playwright test tests/e2e/app-shell-auth.spec.ts tests/e2e/page-function-matrix.spec.ts --project=chromium
```

边界确认：

```bash
cd /Users/j/Documents/gupiao
git diff -- frontend backend strategy_policy.py
```

验收：

1. F1/F2 无假分和编造结论回流。
2. F3 backtest 执行假设展示与后端契约一致。
3. F5 漂移面板无硬编码健康状态和假指标。
4. F4 装饰项不被误标为真实策略数据。
5. 两个 E2E blocker 关闭或明确记录外部 blocker。

## 14. P7：frontend-next 最终验证门禁

必须全部执行：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run e2e
npm run chunk:profile
npm run css:budget
```

后端启动后执行：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run perf:compare
npm run screenshot:parity
```

边界检查：

```bash
cd /Users/j/Documents/gupiao/frontend-next
node scripts/check-boundary-guard.mjs

cd /Users/j/Documents/gupiao
git diff -- frontend backend strategy_policy.py
```

验收：

1. 上述命令全绿。
2. `git diff -- frontend backend strategy_policy.py` 为空；如因后续分离部署阶段需要改后端静态托管开关，则必须单独说明并获得授权。
3. 新报告写入所有 before/after 数字。
4. 无旧前端、后端业务、策略口径改动。

## 15. P8：前端/后端/数据库分离部署落地

P8 仅在 P7 通过后开始。该阶段可本地实现和验证，但不部署到云服务器，除非用户单独授权。

### 14.1 新增 frontend-web 静态服务

新增建议文件：

```text
deploy/frontend/Dockerfile
deploy/frontend/nginx.conf
```

职责：

1. 构建旧 `frontend/` 到 `/usr/share/nginx/html/`。
2. 构建 `frontend-next/` 到 `/usr/share/nginx/html/next/`。
3. 静态服务处理 SPA fallback：
   - `/` fallback 到旧前端 `index.html`
   - `/next/*` fallback 到 frontend-next `index.html`
4. 静态资源长期 cache：
   - hashed assets: long cache
   - index.html: no-cache
5. 不代理 API，不做业务鉴权。

### 14.2 backend-api API-only 模式

当前 FastAPI 会托管 `frontend/dist` 和 `frontend-next/dist`。目标是增加可回滚开关：

```env
SERVE_FRONTEND_STATIC=true|false
```

规则：

1. 默认保持 `true`，兼容旧部署。
2. 分离部署 compose 中设为 `false`。
3. `false` 时：
   - `/api/*` 正常。
   - `/readyz`、`/metrics` 正常。
   - 非 API SPA 路径不再由 backend 托管。
4. 不改变任何后端业务 API、策略、排序、鉴权语义。

### 14.3 Compose 拆分

方案 A：新增 `docker-compose.separated.yml`，先本地/灰度验证。

服务：

```text
frontend-web
backend-api
runtime-worker
runtime-scheduler
analytics-worker
backtest-worker
mysql
redis
go-bff-gateway
go-market-read-service
go-scan-worker
```

端口建议：

```text
frontend-web: 18080 -> 80
backend-api: 18090 -> 8000
go-bff:      internal 8091
market-read: internal 8092
scan-worker: internal 8093
```

方案 B：在现有 `docker-compose.mysql.yml` 增加 `frontend-web` 和 profile。

推荐先用方案 A，降低对当前生产 compose 的扰动。

### 14.4 Nginx Gateway 路由

目标模板：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:18090;
}

location /readyz {
    proxy_pass http://127.0.0.1:18090;
}

location /metrics {
    proxy_pass http://127.0.0.1:18090;
}

location /next/ {
    proxy_pass http://127.0.0.1:18080;
}

location /assets/ {
    proxy_pass http://127.0.0.1:18080;
}

location /next/assets/ {
    proxy_pass http://127.0.0.1:18080;
}

location / {
    proxy_pass http://127.0.0.1:18080;
}
```

注意：

1. `/api/auth/*` 限流策略保留。
2. HTTPS、CSP、cookie secure、SameSite 继续按现有生产策略。
3. 使用 IP 验收时必须确认 cookie 和 CORS 行为。
4. 前端 API base 保持 same-origin `/api`，不引入跨域。

### 14.5 部署脚本 scope

新增或改造 deploy scope：

| Scope | 行为 |
| --- | --- |
| `frontend` | 只构建/发布/重启 `frontend-web` |
| `api` | 只构建/发布/重启 `backend-api` |
| `worker` | 只重启 runtime/scheduler/analytics/backtest worker |
| `go` | 只发布 Go BFF/market-read/scan |
| `db-migration` | 只跑 migration，需备份和授权 |
| `all` | 完整发布 |

要求：

1. 每个 scope 有 before/after health check。
2. 每个 scope 有 rollback 命令。
3. `frontend` scope 不重启 backend-api。
4. `api` scope 不重启 frontend-web。
5. `worker` scope 不影响页面静态资源和 API。

### 14.6 回滚策略

| 失败点 | 回滚 |
| --- | --- |
| frontend-web 新版本失败 | 回滚到上一版 frontend image 或静态目录 |
| backend-api 新版本失败 | 回滚 backend-api image，不动 frontend-web |
| nginx route 失败 | 恢复旧 nginx 模板，全部 proxy 到 backend app |
| API-only 模式失败 | `SERVE_FRONTEND_STATIC=true` 并重启 backend-api |
| worker 失败 | 单独回滚对应 worker image |
| migration 失败 | 停 worker，按备份恢复，重跑 readyz |

## 16. P9：分离部署本地验收

### 15.1 本地 compose 验收

```bash
cd /Users/j/Documents/gupiao
docker compose -f docker-compose.separated.yml build frontend-web backend-api
docker compose -f docker-compose.separated.yml up -d frontend-web backend-api mysql redis
curl -fsS http://127.0.0.1:18090/readyz
curl -fsS http://127.0.0.1:18080/
curl -fsS http://127.0.0.1:18080/next/
```

### 15.2 Playwright 验收

```bash
cd /Users/j/Documents/gupiao/frontend-next
PLAYWRIGHT_BASE_URL=http://127.0.0.1:18080/next npm run e2e
```

补充验证：

1. `/` 旧前端可打开。
2. `/next/login` 可打开。
3. `/next/assets/*` 返回 200。
4. backend-api 重启期间，frontend static assets 仍可访问。
5. frontend-web 重启期间，backend `/readyz` 仍可访问。

## 17. P10：云端部署准备，不自动部署

云端只准备文档和脚本，不执行部署，除非用户单独授权。

准备产物：

1. `docs/operations/frontend-backend-separated-deployment-runbook.md`
2. `docs/reports/frontend-next-runtime-and-bundle-fix-2026-06-08.md`
3. `docs/reports/deployment-separation-readiness-2026-06-08.md`
4. 新 nginx 模板或 diff 说明。
5. 新 compose 或 profile 说明。
6. rollback 命令清单。

授权后部署前必须执行：

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97
cd /home/ubuntu/gupiao-upload
sudo docker compose -f docker-compose.mysql.yml ps
curl -fsS http://127.0.0.1:18090/readyz
df -h /
free -m
sudo docker system df
```

## 18. 最低测试矩阵

### 17.1 frontend-next 修复矩阵

| 模块 | 测试 |
| --- | --- |
| API 契约 | `npm run api:check` |
| 类型 | `npm run typecheck` |
| lint/boundary | `npm run lint` |
| 单测 | `npm test -- --run` |
| 构建 | `npm run build` |
| E2E | `npm run e2e` |
| chunk | `npm run chunk:profile` |
| CSS | `npm run css:budget && npm run css:unused-report` |
| 策略展示正确性 | `npm test -- --run src/features/strategy-tracking src/features/backtest src/features/paper` |
| 策略展示 E2E blocker | `npx playwright test tests/e2e/app-shell-auth.spec.ts tests/e2e/page-function-matrix.spec.ts --project=chromium` |
| perf | 后端启动后 `npm run perf:compare` |
| 视觉 | 后端启动后 `npm run screenshot:parity` |
| 边界 | `node scripts/check-boundary-guard.mjs` |

### 17.2 分离部署矩阵

| 模块 | 测试 |
| --- | --- |
| frontend-web build | Docker build + static HTML/assets 200 |
| backend-api API-only | `/readyz`、`/api/*`、非 API 路径行为符合开关 |
| nginx route | `/`、`/next/`、`/api/`、`/readyz` 正确路由 |
| independent restart | frontend/backend/worker 分别重启互不阻断 |
| auth | IP HTTPS 登录 cookie 正常 |
| dynamic chunk | `/next/assets/*` 不缺失 |
| rollback | 每个 scope 回滚命令可执行 |

## 19. 报告要求

执行完成后必须输出：

1. `docs/reports/frontend-next-runtime-and-bundle-fix-2026-06-08.md`
   - before/after 指标
   - O1/O2 运行时证据
   - O3/O4/O5 修复说明
   - F1/F2/F3/F5 策略展示正确性修复状态
   - 两个 E2E blocker 的复测结果
   - 命令结果
   - 截图/性能证据路径
2. `docs/reports/deployment-separation-readiness-2026-06-08.md`
   - 当前拓扑
   - 目标拓扑
   - 本地验收结果
   - 云端部署前置条件
   - 回滚计划
3. 若存在未达标项：
   - 标记 blocker / non-blocker
   - 写明根因
   - 写明是否阻塞自用、正式验收或 cutover

## 20. 任务拆解清单

### Task A：隔离与基线

1. 执行 `git status --short`。
2. 执行 frontend-next build/chunk/css 基线。
3. 新建修复报告草稿。
4. 不改代码。

验收：基线数字完整。

### Task B：O1/O2 运行时复测

1. 启动本地后端到 `127.0.0.1:8000`。
2. 执行 `perf:compare`。
3. 执行 `screenshot:parity`。
4. 记录 `/next/strategy-tracking` 请求数、fallback、`/next/paper` DOM。

验收：O1/O2 有运行时证据。

### Task C：VirtualList 修复

仅 O2 不达标时执行。

1. 修改 `VirtualList.tsx` 初始 fallback。
2. 补单测。
3. 复跑 paper perf。

验收：初始状态不全量渲染。

### Task D：CSS 拆分和瘦身

1. 全局 CSS 只保留 tokens/base/adapter。
2. 页面 CSS 路由内加载。
3. 合并 paper/login/strategy/backtest 重复样式。
4. 复跑 css budget 和截图。

验收：CSS raw <=180KB，视觉不回退。

### Task E：ECharts 替换

1. 用轻量 SVG/Canvas 替代 backtest `EchartsIsland`。
2. 删除无引用 ECharts 入口。
3. 移除 `echarts` 依赖。
4. 补图表测试。

验收：ECharts assets 为 0 或显著下降，backtest 图表非空。

### Task F：TanStack chunk 拆分

1. 修改 `vite.config.ts` manualChunks。
2. 拆 `tanstack-router/query/table/virtual`。
3. 验证 `tanstack-virtual` 不在首屏。

验收：initial JS raw <=350KB。

### Task G：策略展示正确性专项

1. 为 F1/F2 补回归守卫。
2. 修 F3 backtest 执行假设展示口径。
3. 修 F5 strategy-tracking 漂移面板硬编码兜底和状态。
4. 确认 F4 机甲 HUD 装饰不误导。
5. 复测 playbook 移动导航和 monitor-market 闸门 E2E。

验收：策略展示正确性测试和专项 E2E 通过；无假分、假指标、编造策略叙述。

### Task H：最终 frontend-next 门禁

执行第 14 节全部命令。

验收：全部通过，报告完整。

### Task I：frontend-web 独立服务

1. 新增 frontend static Dockerfile。
2. 新增 frontend nginx conf。
3. 本地 build。

验收：`/`、`/next/`、assets 200。

### Task J：backend API-only 开关

1. 增加 `SERVE_FRONTEND_STATIC`。
2. 保持默认兼容旧部署。
3. API-only 模式本地验证。

验收：API 正常，非 API 静态托管按开关控制。

### Task K：separated compose 与 nginx gateway

1. 新增 separated compose 或 profile。
2. 新增 nginx route 模板。
3. 本地路由验收。

验收：frontend/backend/db/worker 可独立启动。

### Task L：部署脚本 scope 与 runbook

1. 补 `frontend/api/worker/go/db-migration/all` scope。
2. 每个 scope 补 health check 和 rollback。
3. 写 runbook。

验收：只准备，不部署。

## 21. 最终验收结论模板

执行完成后按以下格式给结论：

```text
本轮完成：
- frontend-next O1/O2/O3/O4/O5 修复状态：
- 策略展示正确性 F1/F2/F3/F5 修复状态：
- playbook/monitor-market E2E blocker 状态：
- 分离部署本地 readiness：
- 新增/修改文件：
- 未改旧 frontend：
- 未改后端业务：
- 未改 strategy_policy.py：
- 未部署、未切流：

关键指标：
- /next/strategy-tracking API 请求数：
- /next/paper DOM：
- CSS raw：
- initial JS raw：
- ECharts assets：
- tanstack-virtual 初始加载：
- strategy-tracking 假分/假指标 grep：
- backtest 执行假设口径：
- screenshot parity：

验证命令：
- npm run api:check：
- npm run typecheck：
- npm run lint：
- npm test -- --run：
- npm run build：
- npm run e2e：
- npm run chunk:profile：
- npm run css:budget：
- 策略展示正确性单测：
- playbook/monitor-market 专项 E2E：
- npm run perf:compare：
- npm run screenshot:parity：
- node scripts/check-boundary-guard.mjs：
- git diff -- frontend backend strategy_policy.py：

结论：
- 是否可进入部署授权申请：
- 是否阻塞正式 frontend-next 验收：
- 是否阻塞 cutover：
```

## 22. 不做事项

1. 不在本计划执行中直接部署云服务器。
2. 不切换生产入口。
3. 不重写后端领域服务。
4. 不拆数据库为多个领域库。
5. 不让 frontend-next 取代旧前端生产入口，除非用户另行授权。
6. 不通过删除数据、删除 Docker volume、删除 binlog 来伪造资源优化结果。
7. 不用 ECharts 替代 Lightweight Charts K 线。
8. 不通过前端重算改变生产策略排序。

## 23. 完整执行提示词

把下面提示词复制到新线程即可执行本计划。执行前仍必须重新确认当前工作树，因为本仓库存在并行改动。

```text
你在 /Users/j/Documents/gupiao 项目中工作。请完整实施 docs/frontend-next-runtime-and-deployment-separation-execution-plan-2026-06-08.md 的所有需求，目标是完成 frontend-next 运行时/性能/策略展示正确性修复，并落地前端、后端、数据库可单独部署的本地 readiness 工件；本轮只做本地开发和验证，不部署、不切流。

必须先读并遵守：
1. /Users/j/Documents/gupiao/AGENTS.md
2. docs/engineering-conventions.md
3. docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md
4. docs/frontend-next-runtime-and-deployment-separation-execution-plan-2026-06-08.md
5. docs/reports/frontend-next-reaudit-2026-06-07.md
6. docs/reports/frontend-next-strategy-display-correctness-audit-2026-06-08.md

开始前必须执行：
cd /Users/j/Documents/gupiao && git status --short

硬边界：
1. 保护现有未提交/未跟踪改动；如需编辑同一文件，先读 diff，不得覆盖其他线程改动。
2. 优先只改 frontend-next/、docs/reports/、docs/operations/、deploy/ 和必要部署工件。
3. 不改旧 frontend/ 生产源码；除非只是分离部署静态服务构建入口引用，不得编辑旧前端业务代码。
4. 不改 strategy_policy.py。
5. 不改变生产策略语义、production_score、priority_board 排序和口径。
6. 不让 strategy_engine 替代 low-buy、priority board 或 production scoring；它仍是 shadow-only。
7. 后端尽量不动；若 API-only 静态托管开关必须改 backend，只做最小配置改动，保持默认兼容旧部署，并在报告中说明。
8. 不部署、不切流；任何云端部署或生产入口切换必须停止并等待用户单独授权。
9. 不留下测试脏数据；真实写操作必须隔离写入、rollback、读回一致、403 权限断言。
10. CSS 不做盲目 PurgeCSS；必须结合 css-unused-report、DOM class 检查和 screenshot parity。
11. K 线继续使用 Lightweight Charts；不得用 ECharts 替代 K 线。

按 AGENTS.md 的执行顺序组织判断：trading-quant-lead、stock-analysis-specialist 先确认策略边界和展示口径；product-strategist 明确页面/状态验收；ui-designer 负责视觉和移动可用；fullstack-builder 实施；qa-tester 跑全量验证；devops-operator 只准备分离部署和回滚材料，不执行部署。

实施步骤：
1. P0 隔离与基线：运行 frontend-next 的 npm run build、npm run chunk:profile、npm run css:budget、npm run css:unused-report，并把 before 数字写入 docs/reports/frontend-next-runtime-and-bundle-fix-2026-06-08.md。
2. P1 运行时证据：启动本地后端到 127.0.0.1:8000，跑 npm run perf:compare 和 npm run screenshot:parity；验证 /next/strategy-tracking API 请求数 <=2、无无故 fallback 到 /api/strategy-tracking/items、/next/paper 虚拟列表真实生效。若后端无法启动，记录 blocker，不伪造通过。
3. P2 如 O2 不达标，修 frontend-next/src/shared/ui/VirtualList.tsx：scrollReady=false 时只渲染首屏有限数量，不再 fallback 全量 items；补单测和 perf 断言。
4. P3 修 CSS 体积：移除/拆分全局 legacy-workspace.css 的首屏负担，将 login/paper/strategy-tracking/backtest/monitor/settings 样式收敛到路由内或真实 shared primitive；验收 dist CSS raw <=180KB、!important <=25、screenshot parity 不回退。
5. P4 修 ECharts 体积：用轻量 SVG/Canvas chart 替换 backtest 的 EchartsIsland，保留空态、非空渲染、tooltip/读数反馈；无其他引用时删除 EchartsIsland 并移除 echarts 依赖；验收 echarts assets 为 0 或显著下降。
6. P5 修 TanStack chunk：修改 frontend-next/vite.config.ts manualChunks，把 tanstack-router/query/table/virtual 拆开，确保 tanstack-virtual 不进初始 HTML modulepreload/script，initial JS raw <=350KB。
7. P6 策略展示正确性专项：为 F1/F2 补回归守卫；修 F3 backtest 执行假设展示，优先读取 execution_assumptions，缺字段时明确显示模型/缺失而不是硬编码费率；修 F5 strategy-tracking 漂移面板，不再用 -0.12%、平均 0.85 秒、可接受、高速级、无异动、轻微滑点等缺数据假状态；确认 F4 paper 机甲 HUD 不被误标为真实策略指标；复测 playbook 移动导航和 monitor-market 闸门 E2E。
8. P7 跑最终 frontend-next 门禁：npm run api:check、npm run typecheck、npm run lint、npm test -- --run、npm run build、npm run e2e、npm run chunk:profile、npm run css:budget；后端启动后跑 npm run perf:compare、npm run screenshot:parity；再跑 node scripts/check-boundary-guard.mjs 和 git diff -- frontend backend strategy_policy.py。
9. P8/P9 落地本地分离部署 readiness：新增 frontend-web 静态服务 Dockerfile/nginx.conf、backend API-only 开关（如必要）、docker-compose.separated.yml 或等价 profile、nginx gateway 路由模板；本地验证 /、/next/、/next/assets/*、/api/*、/readyz、frontend/backend/worker 独立启动和重启。
10. P10 只准备云端部署文档，不执行部署：写 docs/operations/frontend-backend-separated-deployment-runbook.md 和 docs/reports/deployment-separation-readiness-2026-06-08.md，包含 frontend/api/worker/go/db-migration/all scopes、health check、rollback、授权前检查命令。

最低验证命令必须覆盖：
cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run e2e
npm run chunk:profile
npm run css:budget
npm run css:unused-report
npm run perf:compare
npm run screenshot:parity
npx playwright test tests/e2e/app-shell-auth.spec.ts tests/e2e/page-function-matrix.spec.ts --project=chromium
node scripts/check-boundary-guard.mjs
cd /Users/j/Documents/gupiao && git diff -- frontend backend strategy_policy.py

最终必须交付：
1. 修复后的代码和测试。
2. docs/reports/frontend-next-runtime-and-bundle-fix-2026-06-08.md，记录 before/after、O1/O2/O3/O4/O5、F1/F2/F3/F5、E2E blocker、命令结果、截图/性能证据。
3. docs/reports/deployment-separation-readiness-2026-06-08.md。
4. docs/operations/frontend-backend-separated-deployment-runbook.md。
5. 分离部署本地 readiness 工件：frontend-web、API-only、nginx route、compose/profile、rollback/scope。
6. 最终结论：哪些通过、哪些 blocker、是否可申请部署授权、是否阻塞正式 frontend-next 验收、是否阻塞 cutover；明确说明未部署、未切流、未改旧 frontend、未改 strategy_policy.py、是否有最小后端改动。
```
