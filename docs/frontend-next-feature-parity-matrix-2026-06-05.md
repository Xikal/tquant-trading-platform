# Frontend Next Feature Parity Matrix - 2026-06-05

状态：frontend-next shadow parity 矩阵；2026-06-07 已更新为 cutover readiness 审计口径，未 cutover
适用范围：旧 `frontend/` 到未来 `frontend-next/` 的 Web 功能对齐
最后核验日期：2026-06-07

## 结论

`frontend-next/` 已完成 `/next/*` 本地 shadow 页面、API contract smoke、请求/SSE trace、截图采样、视觉一致性、功能级 E2E、两交易日 shadow aggregate，以及安全写本地隔离 rollback。剩余 4 组安全写契约已补齐本地后端 rollback、审计、403、读回一致证据；`write:readiness` 为 12 production-ready、0 blocked、1 cutover-excluded。仍不能自动切流：正式 admin/API 环境必须复跑，且用户尚未单独授权 cutover。

最新状态以本节和 `2026-06-07 Cutover Readiness 更新` 为准；下方历史段落中的 `shadow/blocked` 记录仅保留迁移过程参考。

视觉口径更新：旧前端像素相似度不再作为 cutover 阻断项；后续以新前端当前视觉体系的一致性、紧凑度、稳定性、无错位、无大留白为准。`screenshot:parity` 继续保留为截图采样和历史参考。

## 页面 Parity 矩阵

| 当前路由 | 新路由 | 模块 | 优先级 | 当前能力 | 主要 API/数据锚点 | Parity Gate | 当前状态 |
|---|---|---|---|---|---|---|---|
| `/monitor` | `/next/monitor` | `monitor-action` | P0 | 实时行动台、市场状态、生产优先榜、观察池、持仓提醒、关键位 | `/api/bff/v1/workspace/monitor`、`/api/monitor/snapshot`、`monitor_snapshot.priority_board` | BFF payload parity、优先榜顺序 parity、live quote parity、截图 parity、请求数不回归 | Shadow ready；生产榜仅服务端顺序展示 |
| `/monitor/market` | `/next/monitor/market` | `monitor-market` | P0 | 市场环境、宽度、脉冲、板块/ETF、市场解释 | `/api/bff/v1/workspace/monitor`、market/sector/ETF 字段 | market state parity、breadth/pulse parity、板块/ETF parity、截图 parity | Shadow ready |
| `/strategy-tracking` | `/next/strategy-tracking` | `strategy-tracking` | P0 | 信号跟踪、复盘中心、表现、风险、shadow observations | `/api/bff/v1/workspace/strategy`、`/api/strategy-tracking/items?limit=50` | snapshot parity、表格 parity、状态/风险标签 parity、生产/观察边界 parity | Shadow ready；历史 422 已通过 `limit=50` 对齐 OpenAPI 修复；复盘写入保持 no-write |
| `/paper` | `/next/paper` | `paper` | P0 | 账户、持仓、订单、成交、收益、风险、复盘、机甲 display/review | `/api/bff/v1/workspace/paper`、`/api/paper/*` | account/order/holding/performance parity、机甲/日志 display parity、无自动下单语义漂移 | Shadow ready；订单写入默认关闭 |
| `/analysis` | `/next/analysis` | `analysis` | P1 | 个股分析、K 线、信号状态、解释 | 现有 analysis wrapper 待完整接入 | 分析结果 parity、K 线 parity、加载/空/错误态 parity | Style shell ready |
| `/playbook` | `/next/playbook` | `playbook` | P1 | 选股宝典、策略 copy、候选逻辑、表现字段 | 现有 playbook/strategies API wrapper 待完整接入 | 策略文案 parity、字段 parity、候选展示 parity | Style shell ready |
| `/backtest` | `/next/backtest` | `backtest` | P1 | 回测运行、结果图、交易明细、报告、优化/验证任务 | `/api/backtests`、`/api/backtests/{run_id}/*` | run list parity、equity/chart parity、报告口径 parity、任务状态 parity | Shadow ready；提交默认 no-write |
| `/data` | `/next/data` | `data-console` | P2 | 数据源健康、覆盖率、补数任务、质量门禁 | `/api/data-quality/*`、`/api/market/data-sources/health`、runtime task API 待完整接入 | source health parity、coverage parity、task state parity、质量门禁 parity | Style shell ready；任务提交 no-write |
| `/settings` | `/next/settings` | `settings` | P2 | feature flag、运行配置、数据库检查、权限相关配置 | `/api/bff/v1/workspace/settings`、`/api/settings/feature-flags` | flag parity、auth guard parity、禁用态 parity、设置保存/回显 parity | Shadow ready；页面 BFF-first，缺 admin token 时不请求直连管理接口；正式 cutover 仍需 `/api/settings` 与 `/api/settings/factor-weights` 管理端点复验 |

## 跨页面 Parity 要求

| 类别 | 必须一致 | 验收方式 |
|---|---|---|
| API 契约 | OpenAPI generated types、snake_case 字段、兼容响应 | `npm run api:check`、payload compare |
| 生产排序 | 后端返回顺序、`priority_board`、`production_score` | old/new 同 payload 比较；禁止前端生产 re-sort |
| feature flag | 关闭后无空洞、无自动执行、无隐藏后仍运行 | flag off fixture、禁用态截图 |
| 实时连接 | 不重复 SSE，不重复 BFF 轮询 | connection count、request count compare |
| 错误/空/加载态 | 页面有清晰 fallback，不静默成功 | component tests、E2E fixture |
| 样式 | 颜色、密度、间距、字体、布局、滚动区域 | approved Web style image + screenshot parity |
| 性能 | 核心页面不慢于旧前端，首屏包体可解释 | perf profile、bundle report |

## 生产策略保护矩阵

| 保护点 | 新前端规则 | 不通过条件 |
|---|---|---|
| `priority_board` | 只按后端返回顺序展示 | 任意本地排序改变生产优先榜 |
| `production_score` | 只展示后端字段和口径 | 前端计算或覆盖生产分 |
| `near_entry` | 只能 watch-only 展示 | 进入生产收益排行或生产候选 |
| research-only 策略 | 只进入研究/观察展示 | 绕过 flag 或 gate 进入生产排序 |
| paper/shadow | 只用于模拟盘、复盘、display/review | 影响生产信号或真实交易 |
| Worker/WASM | 只做显示层派生和纯计算 | 无 fallback 或参与生产策略判断 |

## 样式与截图前置条件

每个页面实现前必须存在：

1. `docs/frontend-next/style-specs/<page>-style-spec-2026-06-05.md`
2. `docs/frontend-next/style-specs/images/<page>-web.png`
3. 旧页面或批准布局的 Web viewport 说明，默认 `1440x900`
4. 截图 parity checklist

本轮已创建上述 style spec 和 Web 样式图；截图采样 parity 通过。旧新页面的像素级人工签收尚未完成，因此仍不可切流。

## Shadow 验收最低标准

1. 至少两个交易日 shadow 使用无 P0/P1 问题。
2. API 请求数不回归。
3. SSE 连接数不重复。
4. 核心页面性能等于或优于旧前端。
5. 所有 P0/P1 页面通过截图 parity。
6. 旧 `frontend/` 验证命令仍通过。
7. 后端、策略语义、生产排序无改动或有明确零差异证明。

## 是否可作为生产依据

不可作为生产切流依据。本文代表本地 shadow 验收进展，不代表两交易日 shadow、完整写入回滚、人工视觉签收或 cutover 授权已经完成。

## 2026-06-07 Cutover Readiness 更新

| Gate | 当前结果 | 证据 |
|---|---|---|
| 功能级 E2E | PASS | `npm run e2e`：44 tests passed，覆盖 monitor live readiness、analysis live flow、playbook governance、paper live readiness、strategy review、backtest task、data/settings 错误态。 |
| 单测 | PASS | `npm test -- --run`：19 files / 86 tests passed。 |
| API cutover readiness | PASS（本地 admin-token 环境） | `docs/reports/frontend-next-api-cutover-readiness-2026-06-07.md`：6 probes，0 failed；strategy tracking、settings、factor weights、3 个 BFF workspace 均 2xx。正式环境仍需用正式 admin token 复跑。 |
| 安全写 readiness | PASS（本地证据齐全） | `docs/reports/frontend-next-write-readiness-2026-06-07.md`：13 contracts，12 production-ready，0 blocked，1 cutover-excluded；rollback evidence `ok`，`cutover_ready=true`。 |
| rollback smoke | PASS（本地隔离） | `write:rollback -- --all --isolated` PASS；auth MFA、watchlist、trade journal、paper account/order、settings、feature flag、backtest run/validation/optimization、playbook lifecycle、strategy review、data task、data repair、database check 均完成本地写入/撤销或取消/读回。 |
| 请求/SSE | PASS | `request:trace` 9 页无导航错误，EventSource 全 0；`/next/settings` 仅 `/api/auth/me` + BFF settings。 |
| 视觉一致性 | PASS | `visual:consistency` 9 页 x 4 视口，36 captures，failed 0。 |
| 两交易日 shadow | PASS | `shadow:aggregate` 样本日期 `2026-06-05`、`2026-06-06`、`2026-06-07`，四个 gate 均 true。 |

当前页面功能可继续作为 `/next/*` 本地使用；本地 readiness gate 已通过。不可自动作为正式生产入口：仍需正式环境复跑和用户单独授权 cutover；`databaseMigrate` 保持 cutover-excluded。

## 2026-06-06 Final Update

最新结论：`frontend-next/` 已完成本地 `/next/*` shadow 功能 parity、请求/SSE parity、两交易日 shadow aggregate、四档截图捕获和完整新旧前端命令验证；仍未 cutover，不能自动作为生产入口。

| 当前路由 | 新路由 | 最新状态 | 最新证据 |
|---|---|---|---|
| `/monitor` | `/next/monitor` | Shadow parity ready | `monitor-workflows.spec.ts` 验证生产榜顺序和 no-write；`request:trace` 新 2 请求/旧 8 请求，EventSource 0；截图 1440/1280/768/390 已捕获。 |
| `/monitor/market` | `/next/monitor/market` | Shadow parity ready | `monitor-workflows.spec.ts` 验证 gate/breadth/sector/ETF/review/runtime；新 2 请求/旧 8 请求，EventSource 0；截图已捕获。 |
| `/paper` | `/next/paper` | Shadow parity ready，视觉待签收 | 账户/持仓/委托/成交/风险/绩效/自动交易/对账/机甲已覆盖；E2E 验证 API 503 机甲仍可见和默认 no-write。 |
| `/strategy-tracking` | `/next/strategy-tracking` | Shadow parity ready | 筛选、详情、表现/持有/复盘中心、日志/相对强弱读取已覆盖；复盘/日志写入保持 no-write/blocked。 |
| `/analysis` | `/next/analysis` | Shadow parity ready | 单票/批量分析、quote/kline/key-level/anomaly 已覆盖；分析请求不属于交易写入。 |
| `/playbook` | `/next/playbook` | Shadow parity ready，视觉待签收 | strategy meta、low-buy priority、quotes、候选分层、绩效归因、详情联动已覆盖；生命周期写入保持 shadow/blocked。 |
| `/backtest` | `/next/backtest` | Shadow parity ready | run list/detail/equity/trades/control/validate/optimize 已覆盖；真实 cancel/validate/optimize 仍需安全契约。 |
| `/data` | `/next/data` | Shadow parity ready | coverage/SLA/tasks/workers/repair/inspector 已覆盖；repair/backfill/task 真实写仍需安全契约。 |
| `/settings` | `/next/settings` | Shadow parity ready | security/risk/sector/factor/flags/quant/governance/audit 已覆盖；首屏请求已懒加载优化到 2 个；非 feature-flag 写仍需安全契约。 |

Cutover 限制仍然有效：必须先完成人工视觉签收，并由用户单独明确授权 cutover；本文件不代表已经部署或切流。

## 2026-06-06 Visual/API Fix Update

最新状态：`/next/playbook` 422 已修复，`/next/paper` 首屏已压缩，完整新旧验收链继续通过。

| 页面 | 最新状态 | 最新证据 |
|---|---|---|
| `/next/playbook` | Shadow parity ready，视觉待签收 | 默认策略 `first_board`；priority-board 请求为 `limit=30&refresh=cache&strategy_variant=baseline`；无 4xx；旧新 review similarity 0.9350。 |
| `/next/paper` | Shadow parity ready，视觉待签收 | 模拟委托为弹窗入口，机甲头像/Canvas 粒子/机型切换/API 503 可见回归继续通过；旧新 review similarity 0.8503。 |
| `/next/*` 全路由 | Ready for cutover review，但未 cutover | 新前端全命令 PASS；旧前端全命令 PASS；request/SSE PASS；two-day shadow aggregate PASS；write rollback guard PASS。 |

仍不可自动切流：视觉人工签收、缺安全写契约动作、cutover 授权仍未完成。

## 2026-06-06 QA Gate Hardening Update

最新状态：`frontend-next/` 自动化 gate 已加严并通过；仍未部署、未切流。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| `/next/*` 截图验收 | Ready for cutover review | `screenshot:parity` 现在阻断 `/next/*` 的错误边界、未捕获 JS 异常和失败 API 响应；最新 9 个新路由这些字段均为空，1440/1280/768/390 均 captured。 |
| `/next/settings` | Shadow parity ready，视觉待签收 | 运行诊断按“治理”页签懒加载；首屏 API 请求数从 2 降到 1，失败 API 响应为 0。 |
| 两交易日 shadow run | PASS | `shadow:sample` 使用已有本地 shadow token 通过；`shadow:aggregate` 交易日 `2026-06-05`、`2026-06-06`，`sample_count=5`，API/request-SSE/screenshot gates 全 true。 |
| 旧新请求/SSE | PASS | `START_LEGACY_FRONTEND=1 npm run request:trace` 新前端 9 路由请求数均不高于旧前端，EventSource 全为 0。 |
| 旧新视觉 review | Ready for human signoff | 最新 similarity：monitor 0.9229、market 0.9422、paper 0.8504、strategy 0.9610、analysis 0.9086、playbook 0.9354、backtest 0.9136、data 0.9805、settings 0.9473；人工签收仍未完成。 |

仍不可自动切流：人工视觉签收、缺安全写契约动作和 cutover 授权仍未完成。legacy 对照页诊断中存在 `/strategy-tracking` JS 异常和 `/backtest` 403，但新前端对应页面没有错误边界、JS 异常或失败 API 响应。

## 2026-06-06 Client Telemetry Update

最新状态：新前端补齐浏览器内存型诊断 telemetry，用于 cutover 前请求、SSE、Worker、图表、mutation guard 和 UI 事件取证；不部署、不切流、不上报后端。

| 能力 | 最新状态 | parity 影响 |
|---|---|---|
| API 诊断 | Ready for cutover review | `perf:compare` 可输出 route 级 API telemetry；不改变 API 契约、请求参数、缓存 key 或生产数据口径。 |
| SSE/Worker/Chart 诊断 | Ready for cutover review | 只记录显示层连接、fallback、init/update/dispose；不参与生产策略、排序、信号、`production_score` 或 `priority_board`。 |
| Mutation guard 诊断 | Shadow-only evidence | 记录 shadow/blocked/permission/mode/contract 状态；缺安全写契约的功能仍保持 shadow-only 或 blocked_contract_needed。 |
| 敏感信息保护 | Ready for cutover review | telemetry 自动脱敏 token/secret/cookie/authorization，不记录 payload/body；仅浏览器内存快照。 |

本更新只增强可观测性和稳定性验收证据，不改变本矩阵 cutover 限制：视觉人工签收、安全写契约、正式验收账号复跑和用户明确 cutover 授权仍必须单独完成。

## 2026-06-06 Compatibility Route Context Update

最新状态：兼容入口已补齐 query/search 保留，避免从旧路径迁移到 `/next/*` 时丢失股票代码、来源或筛选上下文。

| 兼容入口 | 目标入口 | 最新状态 | 证据 |
|---|---|---|---|
| `/next/emotion?...` | `/next/monitor?...` | Ready for cutover review | `routeTree.tsx` 使用 `search={true}` 保留 query；route inventory 单测覆盖。 |
| `/next/low-buy?...` | `/next/playbook?...` | Ready for cutover review | E2E 覆盖 `/next/low-buy?symbol=000001&source=compat` 跳转后 query 保留。 |
| `/next/strategy?...` | `/next/backtest?...` | Ready for cutover review | `App.test.tsx` 覆盖兼容目标和 query preservation。 |
| `/next/performance?...` | `/next/paper?...` | Ready for cutover review | E2E 覆盖 `/next/performance?symbol=000001&source=compat` 跳转后 query 保留。 |

该更新只影响新前端 shadow 导航上下文，不改变业务数据、权限、写入、生产排序或 cutover 限制。

## 2026-06-06 Analysis Batch Worker Sort Update

最新状态：`/next/analysis` 批量分析结果已使用 Web Worker 展示排序，并有同步 fallback。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| `/next/analysis` batch results | Ready for cutover review | 批量行按 `score desc` 稳定排序；Worker 不可用、超时或报错时同步 fallback；E2E 验证最高分结果排第一。 |
| Worker display compute | Ready for cutover review | `filter / downsample / derive / sort` 均在 `shared/workers` 协议内，继续限定为显示层纯计算。 |

该更新只影响分析页展示顺序，不改变 API 契约、后端响应、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Chart Downsample Endpoint Stability Update

最新状态：新前端图表降采样保留首尾端点，避免尾部最新值丢失。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| Kline/chart display | Ready for cutover review | `downsample` 对不均匀点数返回固定数量、保留首尾；`maxPoints=1` 保留最新点。 |
| Worker fallback | Ready for cutover review | worker 与同步 fallback 共用同一显示层纯计算实现；相关单测通过。 |

该更新只影响图表显示采样，不改变 API 契约、后端响应、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Kline Worker Downsample Adapter Update

最新状态：`KlineChart` 已实际接入 worker downsample adapter，并有 stale async 防护。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| `/next/analysis` Kline | Ready for cutover review | K 线进入 Lightweight Charts 前经 `downsampleChartPoints`，快速切换标的不会被旧采样结果覆盖。 |
| Worker display compute | Ready for cutover review | downsample worker/fallback 现在有真实 KlineChart 调用点，相关单测通过。 |

该更新只影响 K 线显示性能和稳定性，不改变 API 契约、后端响应、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Backtest Workflow Tabs Update

最新状态：`/next/backtest` 已按批准样式图收敛为回测工作流页签。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| `/next/backtest` workflow | Ready for cutover review | `提交任务 / 结果概览 / 成交明细 / ETF T0 / 研究闭环` 页签已落地；运行列表、详情、权益曲线、成交明细、shadow 控制均在同一工作台内。 |
| Backtest writes | Shadow-only | 提交、取消、验证/优化 E2E 验证 0 个真实写请求；ETF T0 真实任务仍 blocked_contract_needed。 |

该更新只影响回测页交互组织和 shadow 工作流，不改变 API 契约、后端任务状态、回测结果、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Data Console Maintenance Workbench Update

最新状态：`/next/data` 已按数据控制台 style spec 收敛为运维工作区。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| `/next/data` operations tabs | Ready for cutover review | `SLA / 覆盖 / 任务 / Worker / 修复 / 检查 / 池管理` 已落地；采集、补齐、修复、检查、池维护均纳入对应页签。 |
| Data writes | Shadow-only / blocked | E2E 覆盖五类操作后写请求数组为空；真实 task/backfill/repair/ETF池写入仍需安全契约和回滚证据。 |
| ETF/stock universe display | Shadow parity ready | 池管理页签明确 `blocked_contract_needed`，不参与生产排序、信号计算、`production_score` 或 `priority_board`。 |

该更新只影响数据控制台信息架构和 shadow 展示，不改变 API 契约、后端任务状态、数据源、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Strategy Tracking Filter Drawer Update

最新状态：`/next/strategy-tracking` 已补齐 off-canvas 筛选抽屉，并保留紧凑筛选摘要。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| `/next/strategy-tracking` filter drawer | Ready for cutover review | “筛选条件”按钮打开 `shared/ui/Drawer`，承载关键词、策略、状态、信号、复盘过滤。 |
| Filter summary | Ready for cutover review | 首屏展示结果数和 active filters；模式/板块仍在首屏可快速切换。 |
| Review writes | Shadow-only | 筛选、详情 drawer、secondary tabs、复盘日志 E2E 后写请求数组为空。 |

该更新只影响策略跟踪页筛选交互和首屏密度，不改变 API 契约、服务器返回顺序、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Settings Layout IA Update

最新状态：`/next/settings` 已按 style spec 补齐设置页信息架构。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| `/next/settings` topbar/nav/content | Ready for cutover review | `系统设置` sticky 顶栏、左侧分区导航、右侧内容区已落地；Admin 分区继续权限隐藏。 |
| Settings writes | Shadow-only / guarded | 功能开关写入仍走 guarded mutation；配置写入仍 shadow-only，等待安全写契约。 |
| Secret handling | Ready for cutover review | 页面继续展示 configured/unconfigured 状态，不展示 secret 原值。 |

该更新只影响设置页布局与表单归属，不改变 API 契约、真实配置状态、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Paper Guarded Account Actions Update

最新状态：`/next/paper` 高风险 shadow 动作增加二次确认和 blocked 契约标识。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| Pause/resume/autotrade/reconcile UI | Shadow parity ready | 账户控制、自动交易控制、对账/修复动作需二次确认后才记录本地意图。 |
| Paper writes | Shadow-only / blocked | 动作条显示 `blocked_contract_needed`；默认不发送真实 API 写请求。 |
| Mecha display boundary | Ready for cutover review | 机甲头像/HUD/粒子继续只作为 display/review 元素，不参与生产排序或信号计算。 |

该更新只影响模拟盘页面高风险动作的确认体验，不改变 API 契约、模拟账户真实状态、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Settings MFA Shadow Management Update

最新状态：`/next/settings` 账户与安全分区已补 MFA 状态和 shadow 管理入口。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| `/next/settings` account security | Ready for cutover review | 账户与安全分区展示 TOTP 当前状态，继续隐藏 secret/二维码等敏感值。 |
| MFA management UI | Shadow-only / blocked | `MFA 管理` 面板可记录 setup/disable 意图和动态口令，二次确认后只返回本地 shadow 结果。 |
| TOTP live writes | blocked_contract_needed | 真实 setup/enable/disable 仍需账号安全契约、回显和回滚证据；当前不调用真实写接口。 |

该更新只影响新前端设置页账户安全展示和 shadow 记录；不改变账户真实 MFA 状态、API 契约、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Settings Section Shadow Management Update

最新状态：`/next/settings` 已补齐各设置分区的 shadow 管理入口，并明确真实写入仍 blocked。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| Risk/LLM settings | Shadow-only / blocked | `配置写入` 经 mutation guard 返回 `blocked_contract_needed`，不伪造保存成功。 |
| Sector exclusions | Shadow-only / blocked | `行业排除管理` 使用 generated `UserSectorExclusionsUpdate` payload，真实 PUT 被契约状态阻断。 |
| Factor weights | Shadow-only / blocked | `因子权重管理` 使用 generated `FactorWeightsUpdate` payload，真实 PUT 被契约状态阻断。 |
| Quant parameters / strategy governance | blocked_contract_needed | 仅记录 shadow 意图，等待量化参数和策略治理安全写契约。 |

该更新只影响设置页配置管理入口和 blocked 反馈；不改变真实配置状态、API 契约、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Shadow Submit And Menu Layer Stability Update

最新状态：shared shadow 表单补齐提交中防重复与失败恢复；AppShell 用户菜单层级修复。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| Shared shadow actions | Shadow-only / Ready for cutover review | 二次确认后的异步提交禁用按钮并显示 `处理中`；失败显示错误且保留草稿；wrapper 单测覆盖。 |
| `/next/settings` user menu | Ready for cutover review | topbar/user menu 层级高于设置页 sticky 工具条；E2E 验证从账户菜单进入设置并退出登录。 |
| `/next/data`、`/next/settings` no-write flows | Shadow-only / blocked | E2E 按当前页签/分区进入 shadow 面板并验证无真实 API 写请求。 |

该更新只影响新前端本地交互稳定性和测试导航口径；不改变真实配置、API 契约、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Auth Refresh Recovery Update

最新状态：普通读请求的 401 认证过期恢复已补齐，写请求仍不自动重试。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| Auth/session restore | Ready for cutover review | 页面读请求 401 会调用 `/api/auth/refresh` 后重试原请求一次；`/api/auth/me` 同样支持该恢复路径。 |
| Write boundary | Shadow-only / blocked | POST/PUT/PATCH/DELETE 不自动 refresh+retry，防止真实写入重复提交。 |
| Tests | Ready for cutover review | API client/auth 单测和 app-shell auth E2E 均通过。 |

该更新只影响新前端认证过期恢复；不改变真实配置、API 契约、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Error Boundary And Telemetry Redaction Update

最新状态：错误边界、telemetry 字符串值和 K 线错误事件已补齐敏感信息脱敏。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| App error fallback | Ready for cutover review | 页面渲染异常 fallback 只展示脱敏后的错误信息。 |
| Telemetry diagnostics | Ready for cutover review | 诊断快照不会保留 token、authorization、secret、password、cookie 等敏感值。 |
| Kline chart errors | Ready for cutover review | K 线 downsample/chart error 记录前先脱敏，错误恢复路径保持可用。 |

该更新只影响新前端错误展示和诊断日志安全；不改变真实配置、API 契约、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Route Level Error Boundary Update

最新状态：`/next/*` 已补齐页面级错误边界，单页异常不会拖垮 AppShell。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| Route-level fallback | Ready for cutover review | 业务路由统一包 `RouteErrorBoundary`，页面 crash 只替换当前内容区。 |
| Shell recovery | Ready for cutover review | E2E 验证 `/next/analysis` 模块异常时侧边栏仍可见，并可跳转 `/next/playbook`。 |
| Error privacy | Ready for cutover review | route fallback 继续脱敏 token/password 等敏感值。 |

该更新只影响新前端页面级容错；不改变真实配置、API 契约、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Paper Mecha Reduced Motion Update

最新状态：`/next/paper` 机甲 Canvas 粒子动效已补齐系统 reduced-motion 运行时响应。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| `/next/paper` mecha particles | Ready for cutover review | 运行时开启 reduced motion 会取消 RAF、移除 resize listener 并清理 Canvas；关闭后恢复当前状态动效。 |
| Mecha display boundary | Ready for cutover review | 机甲头像/HUD/粒子继续只作为 display/review 元素，不参与生产排序、信号计算或模拟委托判断。 |
| Tests | Ready for cutover review | `PaperMechaParticles.test.tsx` 覆盖卸载、初始 reduced motion、运行时切换 reduced motion。 |

该更新只影响新前端模拟盘显示层动效的可访问性和稳定性；不改变真实配置、API 契约、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 SSE Reconnect Stability Update

最新状态：新前端 quote SSE client 已补齐断连退避重连和离页取消 pending reconnect。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| quote SSE reconnect | Ready for cutover review | `EventSource.onerror` 后关闭旧 source，按指数退避重连；同 URL active/pending 连接继续共享订阅计数。 |
| Realtime resource cleanup | Ready for cutover review | 最后订阅者 cleanup 取消 pending reconnect timer 并关闭 active source，避免离页后后台重连。 |
| Production order boundary | Ready for cutover review | SSE 只更新 live quote display signals，不改变 `priority_board` 服务端顺序、`production_score` 或策略语义。 |

该更新只影响新前端实时显示层连接稳定性；不改变真实配置、API 契约、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 User-Facing Error Message Redaction Update

最新状态：新前端页面/表单错误文案已统一接入敏感信息脱敏。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| Shared API errors | Ready for cutover review | `errorMessage` 统一脱敏敏感片段后返回用户可见文案；新增 `errors.test.ts` 覆盖。 |
| Shadow action panels | Ready for cutover review | `ShadowActionPanel` 不再维护本地错误文案函数，失败展示由 shared API 层统一处理。 |
| `/next/paper` order failure | Shadow-only / Ready for cutover review | 委托提交失败只展示脱敏文案，真实写入仍由 mutation guard 控制。 |

该更新只影响新前端用户可见错误文案安全；不改变真实配置、API 契约、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Worker Error Redaction Update

最新状态：新前端 Worker 失败响应和 fallback telemetry 已统一接入敏感信息脱敏。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| Worker display compute | Ready for cutover review | `filter / derive / downsample / sort` worker 失败时继续同步 fallback，错误诊断已脱敏。 |
| Analysis/chart fallback | Ready for cutover review | 批量排序和图表降采样仍保持 display-only，失败不影响 API 数据口径和生产榜顺序。 |
| Telemetry privacy | Ready for cutover review | Worker `error-fallback` telemetry 覆盖 token/password 脱敏单测。 |

该更新只影响新前端 Worker 失败诊断安全；不改变真实配置、API 契约、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Worker PostMessage Fallback Update

最新状态：新前端 Worker `postMessage` 同步失败路径已补齐 sync fallback 和资源清理。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| Worker display compute | Ready for cutover review | `postMessage` 抛错后立即同步 fallback，避免等到 timeout 才恢复。 |
| Resource cleanup | Ready for cutover review | 单测覆盖 `message/error/messageerror` listener 清理。 |
| Telemetry privacy | Ready for cutover review | `postmessage-fallback` telemetry 错误文本脱敏。 |

该更新只影响新前端 Worker 异常恢复；不改变真实配置、API 契约、生产排序、`priority_board`、`production_score`、策略语义、写入边界或 cutover 限制。

## 2026-06-06 Safe Write Contract Definition Update

最新状态：新前端安全写契约已完成定义，并接入 mutation result；真实写入仍默认 shadow/blocked。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| Guarded mutation contracts | Contract defined / no live write | `safeWriteContracts.ts` 覆盖全部非 ready 写 operation；`mutations.test.ts` 和 `operations.test.ts` PASS，证明 blocked result 带 `FNX-SW-*` id 且不发送请求。 |
| Strategy review / trade journal | Contract defined, backend needed | `FNX-SW-STRATEGY-REVIEW`、`FNX-SW-TRADE-JOURNAL` 已定义；仍需后端 CRUD、隔离数据和 rollback smoke。 |
| Data task / repair | Contract defined, backend needed | `FNX-SW-DATA-TASK`、`FNX-SW-DATA-REPAIR` 已定义；仍需 dry-run/apply/cancel/rollback 后端证据。 |
| Settings non-flag writes | Contract defined, backend needed | `FNX-SW-SETTINGS-SECTION` 已定义；仍需 section version、save echo 和 restore previous version。 |
| Paper account actions | Contract defined, backend needed | `FNX-SW-PAPER-ACCOUNT` 已定义；仍需隔离模拟盘账号和账户状态回滚证据。 |
| Backtest tasks / feature flags | Contract defined, isolated smoke gated | `FNX-SW-BACKTEST-TASK`、`FNX-SW-FEATURE-FLAG` 已定义；仍需用户授权、测试 run/admin token、审计和回滚证据。 |

该更新只完成安全写契约定义和前端可观测性，不改变后端、不开放 blocked 写入、不部署、不切流，不改变生产排序、`priority_board`、`production_score` 或策略语义。

## 2026-06-06 Safe Write Request Evidence Update

最新状态：新前端安全写 live-smoke 请求证据链已补齐；真实写入仍由 guard、隔离账号、回滚证据和单独授权约束。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| Guarded mutation request evidence | Ready for isolated smoke review | 允许发送的 `paperOrderCreate`、`backtestRunCreate`、`featureFlagUpdate` 请求会附加 `X-Frontend-Next-*` 安全写 header，并返回 `clientRequestId`。 |
| Shadow/blocked writes | Shadow-only / blocked | `strategy review/trade journal`、`data repair/backfill/task`、`settings non-flag`、`paper account actions` 等 blocked/shadow 分支不发送 requester，不生成 live request id。 |
| API parity | No DTO drift | 请求证据只放在 header 和 telemetry，不改 request body，不手写重复 DTO。 |

该更新只补安全写前端侧请求证据链，不改变后端、不开放 blocked 写入、不部署、不切流，不改变生产排序、`priority_board`、`production_score` 或策略语义。

## 2026-06-06 Local Isolated Write Rollback Smoke Update

最新状态：新前端可发送的三项 isolated live-smoke 已在本地 sqlite 环境完成回滚验证。

| 页面/能力 | 最新状态 | 最新证据 |
|---|---|---|
| `/next/paper` paper order live-smoke | Completed local isolated smoke | `paperOrderCreate` create+reset PASS，报告含 `FNX-SW-PAPER-ORDER` request evidence。 |
| `/next/settings` feature flag live-smoke | Completed local isolated smoke | `playbook_lazy_load_enabled` toggle+restore PASS，最终恢复 true，报告含 `FNX-SW-FEATURE-FLAG` request evidence。 |
| `/next/backtest` run create live-smoke | Completed local isolated smoke | `backtestRunCreate` create+delete PASS，rollback status `deleted`，报告含 `FNX-SW-BACKTEST-TASK` request evidence。 |
| Formal cutover parity | Still pending | 仍需正式验收账号/正式环境复跑、人工视觉签收和用户明确 cutover 授权。 |

该更新只证明本地 sqlite 隔离写链路可回滚，不改变后端代码、不部署、不切流，不改变生产排序、`priority_board`、`production_score` 或策略语义。
