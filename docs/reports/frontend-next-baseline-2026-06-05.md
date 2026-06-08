# Frontend Next Baseline - 2026-06-05

状态：Phase 0 文档基线
适用范围：并行 `frontend-next/` 方案的现状盘点、硬边界和后续验收入口
最后核验日期：2026-06-05

## 结论

本轮只创建文档基线，不实现 `frontend-next/`，不修改 `frontend/`、`backend/`、`frontend-next/`，不部署，不切流，不改变任何生产策略语义。

并行新前端的默认策略是：

1. 旧 `frontend/` 保持生产可用和可回滚。
2. 新 `frontend-next/` 未来只挂载到 `/next/*` shadow 路由。
3. OpenAPI/generated types 是前后端契约事实源。
4. `priority_board`、`production_score`、生产排序和策略门控仍由后端控制。
5. cutover 默认禁止，必须另行获得用户明确授权。

## 初始 Git Status

本轮开始前执行：

```bash
cd /Users/j/Documents/gupiao
git status --short
```

输出：

```text

```

记录口径：命令输出为空。若后续其他 agent 在同一工作区新增文件，以主代理记录的本轮开始状态为空为准；本文中的状态仅作为写文档时快照。

## 权威输入

本基线依据以下文件整理：

| 文件 | 用途 |
|---|---|
| `AGENTS.md` | 多 Agent 顺序、生产/研究边界、默认架构基线 |
| `docs/engineering-conventions.md` | 文档、feature flag、API、测试和生产边界规则 |
| `docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md` | 模块化单体、Worker 化、OpenAPI 契约、前端信息降噪基线 |
| `docs/frontend-next-solid-parallel-development-plan-2026-06-05.md` | 并行 SolidJS 前端目标方案 |
| `docs/reports/frontend-performance-baseline-2026-06-05.md` | 旧前端性能基线引用 |
| `frontend/src/app/router/webRouteDefinitions.tsx` | 当前 Web 路由事实源 |
| `frontend/src/features/trading-workspace/navConfig.tsx` | 当前导航与页面名称 |
| `docs/contracts/openapi.json`、`frontend/src/generated/api-types.ts` | 当前 API 契约与生成类型 |

## 当前页面与功能盘点

| 当前路由 | 当前页面职责 | 后续新路由 |
|---|---|---|
| `/monitor` | 实时行动台：市场状态、优先榜、持仓提醒、关键位 | `/next/monitor` |
| `/monitor/market` | 市场环境台：市场状态、宽度、脉冲、板块/ETF | `/next/monitor/market` |
| `/analysis` | 量化分析：个股分析、K 线、状态解释 | `/next/analysis` |
| `/playbook` | 选股宝典：策略说明、候选逻辑、表现字段 | `/next/playbook` |
| `/strategy-tracking` | 策略跟踪：信号状态、复盘、表现与风险 | `/next/strategy-tracking` |
| `/backtest` | 回测页：运行列表、结果图、报告和验证 | `/next/backtest` |
| `/paper` | 模拟盘：账户、持仓、订单、成交、收益、复盘 | `/next/paper` |
| `/data` | 数据中心：数据源、覆盖率、补数任务、质量门禁 | `/next/data` |
| `/settings` | 系统配置：feature flag、运行配置、权限/数据库检查 | `/next/settings` |

历史重定向保留为旧前端职责：`/emotion -> /monitor`、`/low-buy -> /playbook`、`/strategy -> /backtest`、`/performance -> /paper`。

## 当前样式源

后续 `frontend-next/` 不允许重做视觉主题，必须从旧前端提取并截图校验：

| 样式/组件源 | 用途 |
|---|---|
| `frontend/src/styles/foundation/tokens.css` | 色彩、间距、字体、基础 token |
| `frontend/src/styles/workspace/workspace.css` | 工作台布局和密度 |
| `frontend/src/features/workspace-shared/WorkspaceComponents.tsx` | 工作台共享面板、状态、弹窗 |
| `frontend/src/features/workspace-shared/StockCard.tsx` | 股票卡片密度和信息层级 |
| `frontend/src/ui/table/DataTable.tsx` | 长表格标准组件 |
| `frontend/src/ui/list/VirtualCardList.tsx` | 长列表标准组件 |

## 性能基线引用

旧前端性能基线见 `docs/reports/frontend-performance-baseline-2026-06-05.md`：

| 指标 | 当前基线 |
|---|---:|
| first_screen_js_gzip_kb | 319.76 |
| total_gzip_kb | 807.12 |
| `/monitor` 最大滚动帧 | 33.10ms |
| `/strategy-tracking` 最大滚动帧 | 34.10ms |
| `/paper` 最大滚动帧 | 32.50ms |
| long tasks | 0 |

后续 `frontend-next/` 验收必须补齐 `/backtest`、`/analysis`、二次进入、图表刷新、SSE 数量、请求数量和截图 parity。

## 本轮文件白名单

用户要求本轮只创建/编辑以下文件：

1. `docs/reports/frontend-next-baseline-2026-06-05.md`
2. `docs/frontend-next-architecture-design-2026-06-05.md`
3. `docs/frontend-next-feature-parity-matrix-2026-06-05.md`
4. `docs/frontend-next-cutover-runbook-2026-06-05.md`

因此，计划中 Phase 0 提到的 `docs/frontend-next/style-specs/*.md` 与 `docs/frontend-next/style-specs/images/*.png` 本轮不创建；它们是后续页面实现前的强制前置产物。

## 是否可作为生产依据

本文可作为 `frontend-next/` Phase 0 文档依据，不可作为生产切流依据。生产切流必须以后续 shadow 验证、parity 报告、性能报告、旧前端回归结果和用户显式授权为准。
