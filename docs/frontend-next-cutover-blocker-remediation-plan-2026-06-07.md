# Frontend Next Cutover Blocker Remediation Plan - 2026-06-07

状态：cutover 前阻断项核对与修复计划
范围：`frontend-next/`、契约文档、验收脚本和报告；旧 `frontend/` 只读参考
结论：本地 cutover readiness 脚本已通过；未部署、未切流，正式 cutover 仍需用户单独授权并在正式环境复跑。

## 2026-06-07 自用口径结论

用户最新目标调整为“满足自用即可，保证各功能都正常可用”。按该口径，本轮已完成自用可用性收尾：9 个 `/next/*` 页面、登录/权限、主要业务读取、模拟盘机甲、分析流、策略跟踪、回测、数据中心和设置页交互均通过本地 E2E；页面不再把 `blocked_contract_needed` / `shadow` 等工程态直接展示给用户。

自用结论：可以继续本地使用 `frontend-next/`。正式保存仍受写入 flag、权限守卫和 cutover 授权控制；本轮已补齐剩余 4 组安全写的本地后端 rollback、审计、403、读回一致证据。默认写入 flag 仍关闭，因此不影响生产策略语义、生产排序、`production_score` 或 `priority_board`。

正式 cutover 结论：本地 readiness 已通过，但仍未部署、未切流；需要用户单独授权，并在正式 admin token/environment 下复跑全套 gate。

## 2026-06-07 最新执行更新

本轮继续完成安全写契约整改，仍未部署、未切流。旧 `frontend/` 生产代码未修改，`strategy_policy.py` 未修改；后端仅做安全写契约最小改动（审计、review-only 记录、runtime task cancel、OpenAPI），不改变生产策略语义、生产排序、`production_score`、`priority_board` 口径。

| Gate | 最新状态 | 证据 |
|---|---|---|
| API cutover readiness | PASS（本地 admin token 环境） | `API_BASE=http://127.0.0.1:8011 ADMIN_API_TOKEN=test-admin-token FRONTEND_ADMIN_TOKEN=test-admin-token npm run api:cutover-readiness`：6 probes / 0 failed；`strategy-tracking/items`、`/api/settings`、`/api/settings/factor-weights`、3 个 BFF workspace 均 2xx。 |
| 安全写 readiness | PASS（本地证据齐全） | `npm run write:readiness`：13 contracts，12 production-ready，0 blocked，1 cutover-excluded，rollback evidence `ok`，`cutover_ready=true`。 |
| 完整隔离写回滚 | PASS | `API_BASE=http://127.0.0.1:8011 ADMIN_API_TOKEN=test-admin-token FRONTEND_ADMIN_TOKEN=test-admin-token FRONTEND_NEXT_LOCAL_ADMIN_PROMOTE=1 npm run write:rollback -- --all --isolated`：auth MFA、watchlist、trade journal、paper account、paper order、settings、feature flag、backtest run/validation/optimization、database check 全部 `ok=true`。 |
| 新前端基础质量 | PASS | `api:check`、`typecheck`、`lint`、`npm test -- --run`、`build` 均已通过；单测 19 files / 86 tests。 |
| CSS 预算/未引用报告 | PASS | `css:budget`：dist CSS gzip 47925 bytes、`!important` 51；`css:unused-report`：110 candidate unused selectors，仅报告不删除。 |

本轮已补齐剩余 4 组真实写入契约的本地证据：

1. `FNX-SW-PLAYBOOK-LIFECYCLE`：补 `lowBuyLifecycleUpdate` / `lowBuyStrategyUpdate` 的 audit_id、before_hash、after_hash、确定性 fixture、restore/readback、401/403 权限断言。
2. `FNX-SW-STRATEGY-REVIEW`：新增 review-only backend record CRUD，基于 `operation_audit_log` 记录，不写生产排序；补 create/list/delete/readback 和 refresh 审计。
3. `FNX-SW-DATA-TASK`：`dataJobSubmit` 映射到 `/api/runtime-tasks`，补 runtime task cancel endpoint、audit_id、cancel/readback、401/403 权限断言。
4. `FNX-SW-DATA-REPAIR`：补 repair 入队 audit_id、dry-run/cancel/readback、401/403 权限断言。
5. `FNX-SW-DATABASE-MAINTENANCE.databaseMigrate` 仍 cutover-excluded，需单独运维授权，不纳入前端默认 cutover。

结论：`frontend-next/` 当前可继续 `/next/*` 本地联调；本地 cutover readiness 脚本已通过，但正式 cutover 仍必须由用户单独授权，并在正式环境复跑。

## 2026-06-07 前序执行更新

本节为前序历史记录；最新状态以上方“最新执行更新”为准。当前已在本地补齐安全写 readiness 和 rollback 证据，未部署、未切流，旧 `frontend/` 生产代码和 `strategy_policy.py` 未修改。

| 范围 | 当前状态 | 证据 |
|---|---|---|
| 安全写契约自动审计 | 本地 PASS | `npm run write:readiness`：13 contracts，12 production-ready，0 blocked，1 cutover-excluded。 |
| 写入回滚 smoke | 本地 PASS | `npm run write:rollback -- --all --isolated` 覆盖准备开放的写操作，含剩余 4 组的 rollback/cancel/readback/403。 |
| API cutover readiness | 本地 PASS | `api:cutover-readiness` 6 probes / 0 failed；正式 cutover 前仍需正式 admin token/environment 复跑。 |
| `strategy-tracking` 422 | 已修复前端契约参数 | 新前端请求 `limit=50`，对齐 OpenAPI max 50；未改后端。 |
| `/next/settings` 503 噪音 | 已修复页面请求策略 | 设置页改为 BFF-first，只有存在 admin API token 才请求直连管理接口；`request:trace` 显示 `/next/settings` 仅 2 个请求且 0 SSE。 |
| 功能级 E2E | 已补充并通过 | `npm run e2e` 44 tests PASS，覆盖 monitor、analysis、playbook、paper、strategy review、backtest、data/settings 错误态、401/403 guard。 |
| 单测 | 已补充并通过 | `npm test -- --run` 19 files / 86 tests PASS，覆盖 safe write、mutations、worker/chart/UI/API 回归。 |
| CSS/视觉 gate | 已落地报告和视觉一致性检查 | `css:budget`、`css:unused-report` PASS；`visual:consistency` 9 页 x 4 视口 36 张截图 PASS，未做 PurgeCSS 删除。 |
| 两交易日 shadow | 已满足脚本 gate | `shadow:aggregate` PASS，样本日期 `2026-06-05`、`2026-06-06`、`2026-06-07`，API/request-SSE/screenshot gates 均 true。 |

当前正式 cutover 前仍需满足的事项：

1. 用户尚未单独授权 cutover；本轮默认保持 `/next/*` 本地/并行使用。
2. 正式 cutover 前必须用正式 admin token/environment 复验 `api:cutover-readiness`、`write:readiness`、`write:rollback -- --all --isolated`。
3. `databaseMigrate` 仍 cutover-excluded，需单独运维授权。
4. cutover 运行手册、回滚开关和监控告警需按授权级别再次确认。

## 0. 边界

本计划不授权部署、不授权切流、不要求修改旧 `frontend/`，也不修改 `strategy_policy.py`、生产策略语义、生产排序、`production_score` 或 `priority_board` 口径。所有 Worker/WASM 仍只允许做显示层 `filter / sort / derive / downsample` 和纯计算。

视觉验收口径更新：后续前端视觉不再以旧前端像素级复刻作为阻断标准。旧前端截图和历史相似度只作为迁移参考；正式验收以新前端当前样式体系的整洁度、一致性、可用性、信息密度、无错位、无大留白和稳定性为准。

本轮初始检查已执行：

```bash
cd /Users/j/Documents/gupiao
git status --short
```

当前工作树以未跟踪的 `frontend-next/` 和 `docs/frontend-next*`、`docs/reports/frontend-next*` 为主，未发现已跟踪旧前端、后端或策略文件被本轮修改。

## 1. 问题确认结论

| 编号 | 用户提出的问题 | 当前确认 |
|---|---|---|
| P0-1 | 写操作仍是 shadow / isolated-live-smoke，不是真实 live | 确认。`safeWriteContracts.ts` 的 `requiredMode` 只有 `shadow` / `isolated-live-smoke`，`mutations.ts` 只有 `ready` / `live-smoke` 且开启写 flag 时才会发送。多数写仍是 `blocked_contract_needed` 或 `shadow-only`。 |
| P0-2 | `strategy-tracking` 422、`settings` 503 | 历史报告确认出现过；后续联调报告显示 BFF 与截图采样已恢复为 0 failed API。结论应改为“必须正式环境复验并保留显式错误/空态”，不能直接按已修关闭。 |
| P0-3 | 逐页深度功能 parity 未 100% | 确认。矩阵已大量填充为 shadow ready，但功能级签收和真实写闭环仍未签完；`analysis` 历史视觉 0.7767 不再作为视觉阻断，只作为旧视觉对比记录。 |
| P0-4 | 功能级 E2E 与单元测试覆盖不足 | 确认。新前端单测约 83 个，旧前端约 299 个；这不是精简收益，而是覆盖缺口。现有 E2E 覆盖 shell、no-write、部分流程，但缺 live 写入、rollback、错误态和跨页业务闭环断言。 |
| P1-5 | 会话与权限端到端 | 部分已完成。启动 `me -> refresh`、401 登录、admin/can_paper_trade guard 已有代码和部分 E2E；仍需补过期 token、越权全路径和正式账号复验。 |
| P1-6 | 新前端视觉口径切换 | 已调整。前端视觉以后续新前端样式为准，不再要求旧前端像素 parity；仍需做新前端内部一致性、布局密度和稳定性检查。 |
| P1-7 | 兼容路由和全局能力 | 兼容路由、Command Palette、快捷键、用户菜单、移动抽屉已实现并有测试；AI 对话、股票详情弹窗、自动刷新仍需逐项审计签字。 |
| P1-8 | 两交易日 shadow + 全写回滚 | 两交易日 shadow 本地聚合已 PASS；全写回滚未完成，目前只有 `paperOrderCreate`、`featureFlagUpdate`、`backtestRunCreate` 完成本地 isolated smoke。 |
| P2-9 | 性能/可维护性 | 部分完成。JS 净减少明显，但 CSS 体积从约 85KB 增至约 233KB，主要来自去 AntD 后原生复刻 `legacy-workspace/*` 皮肤；仍需收敛 CSS、`!important` 51 处、确认 ECharts 非首屏预加载、观察 paper DOM，并建立新前端样式一致性 gate。 |
| P2-10 | Cutover 运维闭环 | runbook 存在，但仍需落实灰度开关、监控告警、回滚演练和放量节奏。 |
| P2-11 | 文档收敛 | 确认。`gap-audit`、feature parity matrix、open-items、visual signoff 需要统一状态，避免互相矛盾。 |

## 2. P0 修复包

### P0-A 安全写入从 shadow/live-smoke 升级到 production-ready

目标：所有准备 cutover 的写操作必须逐 operation 完成 request/response/rollback/audit/403 契约，且只有证据齐全后才能从 `blocked_contract_needed` / `shadow-only` / `live-smoke` 升为 `ready`。

不得只改字符串状态。每个 operation 必须同时满足：

1. OpenAPI request/response 使用 generated types，不手写重复 DTO。
2. 具备 `client_request_id` / idempotency key。
3. 后端返回 `audit_id` 或可追踪审计字段。
4. 403/权限不足 fixture 明确可复现。
5. rollback 方式可自动验证。
6. E2E 能证明页面刷新后读回一致。
7. 证明不影响 `priority_board`、`production_score` 和生产排序。

写操作分组：

| 分组 | 当前操作 | 当前状态 | 修复要求 |
|---|---|---|---|
| Monitor watchlist | `watchlistUpsert`、`watchlistRemove` | `blocked_contract_needed` | 补观察池 CRUD、rollback、审计、生产榜不变断言。 |
| Playbook lifecycle / governance | `lowBuyLifecycleUpdate`、`lowBuyStrategyUpdate` | `blocked_contract_needed` | 明确 research-only/near-entry 边界，补 restore previous governance snapshot。 |
| Strategy tracking | `strategyReviewRecord`、`strategyTrackingRefresh`、`tradeJournalCreate` | `shadow-only` / `blocked_contract_needed` | 补复盘记录 CRUD、交易日志 CRUD、refresh 审计、rollback。 |
| Paper | `paperOrderCreate`、`paperOrderCancel`、`paperAccountPause`、`paperAccountResume`、`paperAccountReconcile`、`paperPositionsRefresh` | create 已 isolated smoke，其余 blocked | 使用隔离模拟盘账号补下单、撤单、暂停、恢复、对账、刷新回滚。 |
| Backtest | `backtestRunCreate`、`backtestRunCancel`、`backtestValidationCreate`、`backtestOptimizationCreate` | create 已 isolated smoke，其余 blocked | 补 cancel/validate/optimize/compare/ETF T0 的任务状态真值表和取消/删除 rollback。 |
| Data | `dataJobSubmit`、`dataQualityBackfill`、`dataQualityRepair`、`runtimeTaskCreate`、ETF/股票池维护 | shadow/blocked | 补 dry-run/apply/cancel/rollback，限制任务范围，admin 403。 |
| Settings | `settingsUpdate`、`sectorExclusionsUpdate`、`factorWeightsUpdate`、`featureFlagUpdate` | feature flag 已 isolated smoke，其余 blocked | 补 section version、保存回显、恢复上一版本、分区权限。 |
| Auth/MFA | `authTotpSetup`、`authTotpEnable`、`authTotpDisable` | contract defined | 补隔离账号 MFA 开关、secret 不落 telemetry、恢复旧状态。 |
| Database maintenance | `databaseCheck`、`databaseMigrate` | blocked | cutover 阶段默认不开放 migrate；只允许 dry-run check，migrate 需单独运维授权。 |

新增验收脚本建议：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run write:readiness
npm run write:rollback -- --all --isolated
npm run e2e -- tests/e2e/write-live-readiness.spec.ts
```

准入条件：`write:readiness` 输出 0 个 `blocked_contract_needed`，除明确保留 shadow-only 的研究展示项外，所有 cutover 写操作均为 `ready` 且有 rollback evidence。

### P0-B 后端/API 环境与契约复验

目标：关闭历史 `422/503` 风险，并保证 cutover 后策略跟踪和设置页不会出现空白或假成功。

待核查端点：

```text
GET /api/strategy-tracking/items?range=60&board_filter=include_all&limit=120&offset=0
GET /api/settings
GET /api/settings/factor-weights
GET /api/bff/v1/workspace/strategy
GET /api/bff/v1/workspace/settings
```

修复步骤：

1. 增加 `npm run api:cutover-readiness`，用正式验收 token 跑上述端点。
2. 如果 `strategy-tracking/items` 仍 422，先对照 OpenAPI 参数；若 `board_filter` 或分页参数不被后端接受，前端改为兼容参数或后端补兼容别名，不能静默吞错。
3. 如果 `/api/settings` 或 `/api/settings/factor-weights` 仍 503，后端需明确是环境依赖、权限、数据库还是配置缺失；前端要显示可操作错误态。
4. `screenshot:parity` 必须继续阻断新前端 failed API、错误边界和未捕获 JS 异常。

准入条件：正式验收环境中上述端点全部 2xx，且前端有 422/503 fixture 的错误态 E2E。

### P0-C 逐页深度功能 parity 签收

目标：把 `docs/frontend-next-feature-parity-matrix-2026-06-05.md` 从“shadow ready”升级为“逐功能已签收”。

说明：这里的 parity 指功能和数据能力对齐，不再要求旧前端视觉像素对齐。视觉只检查新前端当前样式体系内是否整洁、一致、稳定、无错位、无大留白。

逐页 checklist：

| 页面 | 必签功能 |
|---|---|
| `/next/monitor` | 持仓录入抽屉、观察池 CRUD、AI 榜单解读、去分析、去选股、生产榜顺序不变。 |
| `/next/monitor/market` | 市场 gate、宽度、脉冲、板块/ETF、市场解释、白底视觉、低频图表口径。 |
| `/next/strategy-tracking` | 筛选抽屉、分页/排序、详情 tabs、复盘记录 CRUD、交易日志 CRUD、rollback。 |
| `/next/paper` | 自动交易状态、下单/撤单、暂停/恢复、风险事件、绩效、标签、对账详情、机甲 display/review 边界。 |
| `/next/analysis` | 单票分析、批量分析、K 线、关键位、异常、模拟下单草稿联动、错误/空态。 |
| `/next/playbook` | 策略切换、候选分层、生命周期、低吸榜、策略治理、去分析/回测联动。 |
| `/next/backtest` | create/cancel/validation/optimization/compare、ETF T0、权益曲线、成交明细、任务状态。 |
| `/next/data` | SLA、gate、source、coverage、repair、inspector、runtime tasks、ETF/股票池。 |
| `/next/settings` | 安全/MFA、行业排除、风控、LLM、因子、量化参数、治理、审计、权限态。 |

准入条件：矩阵每一行都包含“旧功能锚点、新实现锚点、API/状态、E2E 名称、截图路径、签收人/日期”。

### P0-D 功能级 E2E 扩展

目标：从 smoke/no-write E2E 升级到 cutover 功能断言。

新增用例：

| 用例文件 | 必测内容 |
|---|---|
| `tests/e2e/monitor-live-readiness.spec.ts` | 观察池新增/编辑/删除、AI 榜单解读、持仓录入、生产榜不变。 |
| `tests/e2e/analysis-live-flow.spec.ts` | 真实分析流、K 线加载、去 paper 草稿、分析失败态。 |
| `tests/e2e/playbook-governance.spec.ts` | 策略联动、生命周期 shadow/live-readiness、治理 403。 |
| `tests/e2e/paper-live-readiness.spec.ts` | 隔离账号下单、撤单、暂停、恢复、对账、rollback。 |
| `tests/e2e/strategy-review-live-readiness.spec.ts` | 复盘 CRUD、交易日志 CRUD、rollback、筛选分页排序。 |
| `tests/e2e/backtest-task-live-readiness.spec.ts` | create/cancel/validate/optimize/compare、任务状态回读。 |
| `tests/e2e/data-settings-error-states.spec.ts` | 422/503、admin 403、settings 分区保存/回滚。 |

准入条件：E2E 不只验证按钮存在，必须断言 API payload、状态回读、rollback 结果和错误态文案。

## 3. P1 修复包

### P1-A 会话、token 和权限闭环

当前已实现：启动时 `auth.me()`，失败后尝试 refresh；401 进入 `/login?redirect=...`；read 请求 401 会静默 refresh 一次；写请求 401 不自动重试；`AdminGuard` 和 `PaperGuard` 已有页面级拦截。

仍需补齐：

1. E2E：过期 access token -> refresh 成功 -> 留在原页面。
2. E2E：refresh 失败 -> 清 token -> 跳 login 并保留 redirect。
3. E2E：非 admin 访问 data/settings admin 分区全路径。
4. E2E：无 `can_paper_trade` 不能进入 paper，也不能触发写 mutation。
5. Telemetry：401/403 不泄露 token、cookie、password。

### P1-B 新前端视觉一致性签收

旧前端视觉 parity 不再作为 cutover 阻断项。`/next/analysis` 曾出现的 0.7767 相似度只保留为历史迁移参考，不再要求按旧前端修到固定阈值。

新的视觉签收目标：

1. 以新前端当前样式为准。
2. 页面整洁，组件尺寸合理，信息紧凑。
3. 不出现明显错位、重叠、截断、异常留白。
4. 左侧菜单、顶部栏、按钮、表格、卡片、徽标、空态、错误态风格一致。
5. 页面在 1440/1280/768/390 viewport 下可用。

修复步骤：

1. 新增或调整 `npm run visual:consistency`，检查新前端页面截图，不再和旧前端像素比对。
2. 每页输出当前新前端截图到 `docs/reports/frontend-next-visual-review-2026-06-05/` 或新日期目录。
3. 用户逐页按“通过 / 不通过 + 原因”签收。
4. 将 `docs/reports/frontend-next-visual-signoff-2026-06-05.md` 改为新前端视觉签收清单，移除旧视觉 similarity gate。
5. CI gate 保留“截图可捕获、无错误边界、无未捕获 JS、无 failed API、无严重布局异常”，不再阻断旧新相似度。

### P1-C 兼容路由和全局能力

已实现并有测试的能力：

```text
/next/emotion -> /next/monitor
/next/low-buy -> /next/playbook
/next/strategy -> /next/backtest
/next/performance -> /next/paper
Command Palette
Cmd/Ctrl+K
Cmd/Ctrl+1~8
用户菜单
移动抽屉
```

仍需审计签收：

1. 全局 AI 对话或 AI 决策入口是否与旧前端一致。
2. 股票详情弹窗是否所有旧入口都能打开。
3. 自动刷新策略是否与旧前端一致，且不会重复请求/SSE。
4. 旧书签带 query 时是否都保留上下文。

### P1-D 两交易日 shadow 与正式环境复跑

本地两交易日 shadow 已 PASS，交易日记录为 `2026-06-05`、`2026-06-06`。这关闭了“只跑 1/2 天”的历史问题。

cutover 前仍需：

```bash
cd /Users/j/Documents/gupiao/frontend-next
FRONTEND_AUTH_TOKEN=<正式验收token> npm run shadow:sample
npm run shadow:aggregate
START_LEGACY_FRONTEND=1 npm run request:trace
npm run screenshot:parity
npm run perf:compare
```

准入条件：正式验收账号/环境复跑通过，报告写入 acceptance/open-items，不能只使用本地 fixture 作为 cutover 依据。

## 4. P2 修复包

### P2-A 性能和可维护性

修复项：

1. 记录 bundle 总账：CSS 约 85KB -> 233KB，增量约 148KB / +174%；JS 约减少 1290KB，整体仍是净收益。
2. CSS 体积增加属于去 AntD runtime、用原生 CSS 复刻工作台皮肤的结构性代价，但需要治理，不允许继续无限增长。
3. 收敛剩余 `!important` 约 51 处，优先把页面级 override 下沉为 shared wrapper variant 或局部 class。
4. `paper` DOM 继续观察，持仓/日志列表达到阈值后切 `VirtualList`。
5. 确认 ECharts 只在低频图表 adapter 懒加载，K 线统一 `Lightweight Charts + worker downsample`。
6. 删除或合并未引用 CSS，登录相关 CSS 保持单入口。
7. 删除旧 `DataGrid` 别名，只保留 `DenseTable/DataTable` contract。
8. 徽标统一到 `StatusBadge`。
9. bundle budget、CSS guard、boundary guard 保持在 `npm run lint` 内执行。

准入条件：`npm run build` 输出 chunks 可解释，CSS/JS 总账在报告里说明，`npm run perf:compare` 不回归，新前端视觉一致性 gate 通过。

### P2-B CSS 无损优化方案

目标：降低 CSS 维护成本和首屏主包压力，但不改变当前新前端视觉。优化只允许围绕加载边界、重复规则、预算监控、未引用报告和 `!important` 收敛展开，不允许改色、改间距、改布局密度或重做视觉。

当前基线：

| 项 | 当前观察 | 说明 |
|---|---|---|
| 源码 CSS | 约 297KB / 15522 行 | 主要来自 `legacy-workspace/*` 和各页面 slice CSS。 |
| 构建后 CSS | 主包约 86KB，页面 CSS 分 chunk | 页面 chunk 已存在，但全局 legacy 仍偏重。 |
| gzip 总量 | 约 48KB | 网络传输压力可控，维护复杂度仍需治理。 |
| `!important` | 约 51 处 | `monitor-market.css`、`workspace-strategy-tracking.css`、`legacy-solid-adapter.css` 优先收敛。 |
| 体积变化 | CSS 约 85KB -> 233KB，JS 约 -1290KB | 去 AntD runtime 后的 CSS 体积增长可接受，但不能继续无预算增长。 |

无视觉风险优化：

1. 新增 CSS budget 报告脚本，输出 raw/gzip、主包/page chunk、`!important` 数量、最大 CSS 文件排行。
2. 新增 unused CSS / orphan selector 报告，只报告不自动删除。
3. 将 `!important` 分类为 `reduced-motion 必要项`、`响应式必要项`、`覆盖债`，先做清单。
4. 每次 CSS 优化后固定跑截图健康检查：无错误边界、无 failed API、无明显错位、无大留白。

低风险优化：

1. 拆 `legacy-workspace.css` 的导入边界：首屏只保留 tokens、shell、panel、button、input、tabs、table、toast、drawer、modal 等真正全局规则。
2. 将 `workspace-paper.css`、`workspace-paper-mecha.css`、`workspace-strategy-tracking.css`、`workspace-backtest.css`、login 相关 legacy CSS 移到对应页面懒加载入口。
3. 合并重复的按钮、表格、badge、panel、empty-state 规则到 `shared/ui` wrapper 样式，页面 CSS 只保留页面布局和特例。
4. 优先移除可用选择器优先级替代的 `!important`，保留 reduced-motion 内的必要 `!important`。

中风险优化，必须截图确认：

1. 删除旧 Ant 兼容选择器前，先用 DOM/class 扫描证明新前端运行时不再输出对应 `.ant-*`。
2. 合并跨页面重复色值、边框、阴影、字号、间距变量时，只允许替换为现有 token，不允许新建视觉风格。
3. 大 CSS 文件可拆为 `layout / components / states`，但导入顺序必须保持等价。

明确禁止：

1. 禁止直接使用 PurgeCSS 批量删除，避免误删动态 class、响应式 class 和错误态 class。
2. 禁止为了降体积改动当前页面视觉、密度、交互位置或文案层级。
3. 禁止把页面样式重新搬回第三方默认样式。
4. 禁止修改旧 `frontend/` 作为 CSS 优化手段。

验收命令建议：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run css:budget
npm run css:unused-report
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run screenshot:parity
npm run perf:compare
```

产出：

1. `docs/reports/frontend-next-css-optimization-2026-06-07.md`：记录 before/after raw/gzip、chunk、`!important`、未引用候选和保留原因。
2. `docs/reports/frontend-next-visual-review-2026-06-05/` 或新日期截图目录：保留优化后每页截图。
3. 更新本计划中的 CSS 基线和剩余债务。

### P2-D 测试覆盖补齐

当前新前端单元测试数量显著低于旧前端，不能解释为“代码更少所以无需补测”。cutover 前应按风险补齐，而不是追求数字完全相等。

补齐方向：

1. shared API：safe write、401 refresh、403 guard、retry、error body 单读流回归。
2. shared UI：Panel、DenseTable、StatusBadge、Toast、Drawer、Modal、VirtualList、StockCard contract。
3. charts/worker：KlineChart、ECharts island 懒加载、worker timeout/error/postMessage fallback。
4. pages model：monitor、market、analysis、playbook、strategy、paper、backtest、data、settings 的数据归一化。
5. pages interaction：每个页面至少覆盖加载态、空态、错误态、禁用态和核心按钮。
6. regression：422/503、Response body stream already read、502 error toast、no duplicate SSE。

准入条件：新增测试覆盖所有 P0/P1 风险场景；`npm test -- --run` 和 `npm run e2e` 全绿；acceptance 报告列出新旧测试数量差异和未覆盖风险。

### P2-B Cutover 运维闭环

`docs/frontend-next-cutover-runbook-2026-06-05.md` 需要补齐并演练：

1. 灰度入口和切流开关。
2. 新旧前端并行观察期。
3. 回滚步骤和负责人。
4. 监控告警：5xx、JS error、failed API、请求数、SSE、写 mutation、rollback failure。
5. 放量节奏：内部账号 -> 小流量 -> 全量。
6. 停止条件：任一 P0 失败立即回滚。

### P2-C 文档收敛

需要统一这些文档的状态：

| 文档 | 动作 |
|---|---|
| `docs/reports/frontend-next-gap-audit-2026-06-06.md` | 标记 superseded 或链接到本计划。 |
| `docs/frontend-next-feature-parity-matrix-2026-06-05.md` | 逐项补签收字段，移除过期“仍缺两交易日”说法。 |
| `docs/reports/frontend-next-open-items-2026-06-05.md` | 只保留当前未完成项，合并重复段落。 |
| `docs/reports/frontend-next-visual-signoff-2026-06-05.md` | 人工签收后更新结论。 |
| `docs/reports/frontend-next-acceptance-2026-06-05.md` | cutover 前作为最终验收入口更新。 |

## 5. 多 Agent 并行分工

| Agent | 负责人职责 | 输出 |
|---|---|---|
| A 契约/安全写 | 写 operation readiness、OpenAPI、safe write 状态推进、rollback smoke | `write:readiness`、扩展 `write:rollback`、契约证据报告 |
| B API/后端联调 | 422/503 复验、正式 token 读链路、错误态 fixture | `api:cutover-readiness`、API 复验报告 |
| C 页面 parity | 按页面补全功能矩阵和交互缺口 | 更新 feature parity matrix |
| D E2E | 功能级 E2E、错误态、权限、rollback 断言 | 新增 e2e spec 和报告 |
| E 视觉/性能 | 新前端视觉一致性、截图健康、bundle/perf、CSS 收敛 | visual consistency signoff、perf report |
| F 运维文档 | cutover runbook、回滚、监控、放量 | 更新 runbook 和 acceptance |

并行规则：A/B/D 可以并行，但任何 operation 升 `ready` 必须等待 A 的契约证据、B 的 API 复验和 D 的 E2E/rollback 同时通过。

## 6. 总体验收命令

新前端：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run e2e
npm run api:cutover-readiness
npm run write:readiness
npm run write:rollback -- --all --isolated
npm run shadow:sample
npm run shadow:aggregate
npm run request:trace
npm run screenshot:parity
npm run visual:consistency
npm run perf:compare
```

旧前端：

```bash
cd /Users/j/Documents/gupiao/frontend
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
```

仓库：

```bash
cd /Users/j/Documents/gupiao
git diff --check
git status --short
```

## 7. Cutover 准入标准

只有全部满足时才允许进入 cutover 讨论：

1. 所有 P0 写操作 readiness 为 `ready`，或明确从 cutover 范围排除并保持 UI 禁用/隐藏。
2. 所有写操作有 rollback、audit、403、idempotency 证据。
3. `strategy-tracking/items`、`settings`、`factor-weights` 正式环境复验 2xx。
4. 逐页功能 parity matrix 完成签收。
5. 功能级 E2E 全绿，且包含错误态和 rollback 断言。
6. 两交易日 shadow 在正式验收账号/环境复跑通过。
7. 新前端视觉一致性签收 9 页全部通过，不再要求旧前端像素 similarity。
8. 新旧前端验证命令全绿。
9. runbook 的灰度、监控、回滚演练完成。
10. 用户单独明确授权 cutover。

## 8. 当前不可 cutover 的剩余项

| 剩余项 | 阻断级别 | 当前状态 |
|---|---|---|
| 全写操作 production-ready | P0 | 未完成，只有 3 项本地 isolated smoke。 |
| 422/503 正式复验 | P0 | 历史失败已后续缓解，但未用正式环境关闭。 |
| 逐页深度功能签收 | P0 | shadow ready，不等于 1:1 功能签收。 |
| 功能级 live/rollback E2E | P0 | 未完成。 |
| 单元测试和功能级测试覆盖 | P0 | 新前端测试数量明显少于旧前端，需按 P0/P1 风险补齐。 |
| 新前端视觉一致性签收 | P1 | 不再按旧视觉 similarity 阻断，但仍需按新样式逐页确认无错位、无大留白、组件密度合理。 |
| 正式验收账号 shadow 复跑 | P1 | 未完成。 |
| AI 对话/股票详情/自动刷新逐项确认 | P1 | 需要审计签字。 |
| 性能与 CSS 收敛 | P2 | JS 净收益明确；CSS 增长和 `!important` 仍需治理。 |
| runbook 演练 | P2 | 未完成。 |
| 文档状态收敛 | P2 | 未完成。 |

## 9. 默认结论

当前新前端不应正式切流。可以继续在 `/next/*` 下 shadow 使用、本地联调、正式账号读链路复验和 isolated write smoke。除非用户后续单独授权 cutover，并且本计划的 P0/P1 gate 全部关闭，否则默认不部署、不切流。
