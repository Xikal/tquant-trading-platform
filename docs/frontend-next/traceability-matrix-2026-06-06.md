# Frontend Next Traceability Matrix - 2026-06-06

状态：QA/验收矩阵初版，未部署，未切流
适用范围：旧 `frontend/` 到 `frontend-next/` 的 P0/P1 用户能力、权限、数据口径与证据追踪
最后核验日期：2026-06-06

## 结论

`frontend-next/` 当前仍只能作为 `/next/*` shadow 预览使用。本矩阵把 P0/P1 能力拆成可验收行，但不代表功能已完成；当前无 P0/P1 能力可标记为 `parity_ready`。涉及安全写入、真实复盘、数据任务、feature flag live-smoke、paper live-smoke 的能力，必须明确保持 `shadow-only` 或 `blocked_contract_needed`。

## 工作边界

1. 本文只覆盖 QA/验收矩阵，不部署、不切流。
2. 本轮不修改旧 `frontend/`、不修改后端、不修改 `frontend-next/` 代码。
3. 初版要求不修改 acceptance/open-items；后续稳定性与权限硬化已在对应报告末尾追加最新证据，历史段落不作为当前状态判断依据。
4. API operation 名称为验收锚点建议，最终以 `frontend-next/src/shared/api/operations.ts` 和 OpenAPI 生成类型为准。

## 状态词典

| 状态 | 含义 | 不允许误判为完成的条件 |
|---|---|---|
| `gap_open` | 功能、权限、数据或证据仍缺失 | 只有页面壳、样式图或 smoke 通过 |
| `shadow-only` | 只允许 no-write 或 shadow 记录验证 | 未经隔离 live-smoke 和回滚证明 |
| `blocked_contract_needed` | 缺安全后端契约、隔离测试数据或回滚接口 | 前端伪造成功或直接打 live 写接口 |
| `ready_for_shadow_check` | 已有 shadow 读取或壳体，可补字段级证据 | 未完成 payload/order/request/screenshot 对比 |
| `ready_for_cutover_review` | 本地 shadow 功能、权限、请求、截图和测试证据已满足进入 cutover 评审 | 不等于已 cutover；人工视觉签收、正式账号复跑、危险写契约和用户授权仍可阻断 |
| `parity_ready` | 功能、权限、数据、截图、请求、测试证据齐全 | P0/P1 不得存在未解释阻塞 |

## 数据 Parity 口径

| 口径 | 判定规则 | 适用字段 |
|---|---|---|
| `exact` | 字段值、排序、数量、状态完全一致 | `priority_board`、`production_score`、权限状态、策略状态、任务状态 |
| `tolerance` | 数值允许约定误差，必须记录精度 | 收益率、PnL、图表 downsample 后端点和关键指标 |
| `format-only` | 展示格式可不同，原始字段必须一致 | 时间、金额、百分比、标签文案、颜色映射 |
| `shadow-only` | 不发 live 写请求，只验证 shadow 记录或未发请求 | 委托、复盘、数据任务、设置保存、feature flag |

## 跨页面 Gate

| ID | 优先级 | 旧入口 | 新入口 | 用户能力 | API operation | 权限 | 数据口径 | UI 证据 | 测试/验收证据 | 当前状态 |
|---|---|---|---|---|---|---|---|---|---|---|
| FNX-TM-000 | P0 | 登录态工作台 | `/next/*` guard | 登录、注册、刷新会话、退出、MFA、会话恢复 | `auth.login/register/refresh/logout/me/totp` | anonymous/authenticated | exact | route guard 截图待补 | auth E2E、401 refresh、403 fallback | `gap_open` |
| FNX-TM-001 | P0 | 全局工作台 | `AppShell`、Command Palette、移动抽屉 | 页面跳转、策略跳转、股票代码进入分析、快捷键 | `workspace.navigation` | authenticated | format-only | responsive 截图待补 | Command Palette E2E、390x844 截图 | `gap_open` |
| FNX-TM-002 | P0 | `frontend/src/api/*` | `shared/api/*` | 统一 typed operation、query key、请求取消 | `operations.*`、`queryKeys.*` | authenticated | exact | 不适用 | `api:check`、operation tests、request trace | `gap_open` |
| FNX-TM-003 | P0 | 各页写入流 | `shared/api/mutations` | shadow/live-smoke/live 状态机、确认、失败恢复、回滚 | `mutations.*` | role + mode gate | shadow-only | ConfirmAction 截图待补 | mutation lifecycle tests、no-write trace | `shadow-only` |
| FNX-TM-004 | P0 | 实时行情/请求 | realtime adapters | 不重复 SSE、不重复 BFF 轮询、离页释放资源 | `realtime.*` | authenticated | exact | 连接状态截图待补 | request count、EventSource count、dispose telemetry | `gap_open` |
| FNX-TM-005 | P1 | 桌面/移动页面 | shared UI wrappers | 响应式、键盘、focus trap、reduced motion | `ui.*` | all roles | format-only | 1440/1280/768/390 截图待补 | component tests、a11y checks | `gap_open` |

## 页面能力矩阵

| ID | 优先级 | 旧入口 | 新入口 | 用户能力 | API operation | 权限 | 数据口径 | UI 证据 | 测试/验收证据 | 当前状态 |
|---|---|---|---|---|---|---|---|---|---|---|
| FNX-TM-010 | P0 | `/monitor` | `/next/monitor` | 实时行动台、生产优先榜、市场状态、持仓风险摘要 | `monitor.getWorkspace` | authenticated | exact | `docs/frontend-next/style-specs/monitor-action-style-spec-2026-06-05.md`、`images/monitor-action-web.png` | BFF payload hash、`priority_board` order hash、request/SSE trace、截图 parity | `ready_for_shadow_check` |
| FNX-TM-011 | P0 | `/monitor` watchlist/holding actions | `/next/monitor` drawer/actions | 持仓录入/编辑、观察池 add/edit/delete、卡片详情、去分析 | `monitor.updateHolding`、`monitor.watchlist.*` | authenticated observer | shadow-only | 同 FNX-TM-010 | shadow no-write trace、live-smoke 隔离回滚证据待补 | `gap_open` |
| FNX-TM-012 | P0 | `/monitor` key levels/AI | `/next/monitor` panels/dialog | 关键位、量价标签、AI 榜单解读入口 | `monitor.getKeyLevels`、`monitor.getAiDecisionSupport` | authenticated | exact/format-only | 同 FNX-TM-010 | 字段级对比、弹窗截图、错误态 fixture | `gap_open` |
| FNX-TM-020 | P1 | `/monitor/market` | `/next/monitor/market` | 市场总闸、宽度、脉冲、板块/ETF、复盘摘要 | `monitor.getWorkspace(view=market)` | authenticated | exact/tolerance | `docs/frontend-next/style-specs/monitor-market-style-spec-2026-06-05.md`、`images/monitor-market-web.png` | market payload hash、图表资源释放、截图 parity | `ready_for_shadow_check` |
| FNX-TM-021 | P1 | `/monitor/market` runtime actions | `/next/monitor/market` runtime panels | instrument sync、data quality、MarketReviewPanel 完整交互 | `monitor.instrumentSync`、`monitor.getReview` | authenticated/admin for task actions | exact/shadow-only | 同 FNX-TM-020 | task state trace、403/admin fixture、dispose telemetry | `gap_open` |
| FNX-TM-030 | P0 | `/analysis` | `/next/analysis` | 单票分析、关键位、盘中异常、执行计划、失效条件、K 线 | `analysis.analyze`、`analysis.getIntradayAnomaly`、`analysis.getKeyLevels` | authenticated | exact/tolerance | `docs/frontend-next/style-specs/analysis-style-spec-2026-06-05.md`、`images/analysis-web.png` | API error/empty/invalid fixtures、Kline update/dispose、截图 parity | `gap_open` |
| FNX-TM-031 | P0 | `/analysis` batch | `/next/analysis` batch panel | 2-8 个代码批量分析、Worker 排序、sync fallback | `analysis.analyzeBatch` | authenticated | exact | 同 FNX-TM-030 | worker vs sync output hash、fallback telemetry | `gap_open` |
| FNX-TM-032 | P0 | `/analysis` paper action | `/next/analysis` order handoff | 从分析结果打开模拟委托 | `paper.prepareOrderDraft` | `can_paper_trade` | shadow-only | analysis + paper 截图待补 | guard E2E、no-write trace | `shadow-only` |
| FNX-TM-040 | P0 | `/playbook` | `/next/playbook` | 生产/观察策略 tabs、真实候选、候选分层、绩效归因 | `playbook.getStrategyMeta`、`playbook.getLowBuyCandidates` | authenticated | exact/format-only | `docs/frontend-next/style-specs/playbook-style-spec-2026-06-05.md`、`images/playbook-web.png` | research-only guard、`near_entry` watch-only guard、截图 parity | `gap_open` |
| FNX-TM-041 | P0 | `/playbook` quote/actions | `/next/playbook` candidate cards | 交易时段报价刷新、详情、分析、选择联动 | `playbook.refreshQuotes`、`playbook.selectCandidate` | authenticated | exact/shadow-only | 同 FNX-TM-040 | leaf update trace、no full-page rerender evidence | `gap_open` |
| FNX-TM-050 | P0 | `/paper` | `/next/paper` | 账户、持仓、订单、成交、绩效、风险、机甲 display/review | `paper.getWorkspace`、`paper.getPerformance`、`paper.getRisk` | `can_paper_trade` for paper page | exact/tolerance | `docs/frontend-next/style-specs/paper-style-spec-2026-06-05.md`、`images/paper-web.png` | payload hash、机甲 display-only guard、截图 parity | `ready_for_shadow_check` |
| FNX-TM-051 | P0 | `/paper` order modal | `/next/paper` order modal | 推荐导入、搜索、买/卖、数量快捷、费用估算、提交 | `paper.createOrder` | `can_paper_trade` + write mode | shadow-only | 同 FNX-TM-050 | no-write trace、live-smoke 创建/回滚证据 | `shadow-only` |
| FNX-TM-052 | P0 | `/paper` admin/repair/tags | `/next/paper` tabs/actions | 暂停/恢复、自动交易、标签、对账 dry-run/apply | `paper.pause/resume`、`paper.tags.*`、`paper.ledgerRepair.*` | `can_paper_trade`、admin for repair apply | shadow-only | 同 FNX-TM-050 | dry-run 前置、ConfirmAction、admin 403 fixture | `blocked_contract_needed` |
| FNX-TM-060 | P0 | `/strategy-tracking` | `/next/strategy-tracking` | snapshot/items、分页、排序、虚拟表格、模式切换 | `strategyTracking.getSnapshot`、`strategyTracking.getItems` | authenticated | exact | `docs/frontend-next/style-specs/strategy-tracking-style-spec-2026-06-05.md`、`images/strategy-tracking-web.png` | query param parity、virtual table state、截图 parity | `ready_for_shadow_check` |
| FNX-TM-061 | P0 | `/strategy-tracking` detail/filter | `/next/strategy-tracking` drawers | 筛选抽屉、详情抽屉、表现、持有、漂移、诊断、relative strength | `strategyTracking.getDetail`、`strategyTracking.getReports` | authenticated | exact/format-only | 同 FNX-TM-060 | filter query hash、detail fixture、分页回退 | `gap_open` |
| FNX-TM-062 | P0 | `/strategy-tracking` review/journal | `/next/strategy-tracking` review center | 复盘中心、weekly report、promotion review、交易日志 CRUD | `strategyTracking.review.*`、`strategyTracking.tradeJournal.*` | authenticated + write mode | shadow-only | 同 FNX-TM-060 | no-write trace、safe write contract、rollback evidence | `blocked_contract_needed` |
| FNX-TM-070 | P1 | `/backtest` | `/next/backtest` | run list、run detail、metrics、equity、trades、图表 | `backtest.getRuns`、`backtest.getRunDetail`、`backtest.getEquity`、`backtest.getTrades` | authenticated | exact/tolerance | `docs/frontend-next/style-specs/backtest-style-spec-2026-06-05.md`、`images/backtest-web.png` | run payload hash、downsample endpoint check、截图 parity | `ready_for_shadow_check` |
| FNX-TM-071 | P1 | `/backtest` submit/cancel/research | `/next/backtest` forms/tabs | 提交、取消、ETF T0、OOS、validation、optimization、compare | `backtest.createRun`、`backtest.cancelRun`、`backtest.getValidation`、`backtest.getOptimization` | authenticated + write mode | shadow-only | 同 FNX-TM-070 | submit/cancel E2E、task status truth、test run marker | `shadow-only` |
| FNX-TM-080 | P1 | `/data` | `/next/data` | 今日数据状态、门禁、源健康、覆盖率、Worker 观测 | `dataConsole.getSla`、`dataConsole.getGate`、`dataConsole.getCoverage`、`dataConsole.getWorkers` | admin | exact | `docs/frontend-next/style-specs/data-console-style-spec-2026-06-05.md`、`images/data-console-web.png` | admin guard E2E、coverage payload hash、403 fixture | `gap_open` |
| FNX-TM-081 | P1 | `/data` tasks/repair | `/next/data` task/repair panels | sync、refresh、backfill、repair dry-run/apply/cancel、inspector、ETF universe | `dataConsole.tasks.*`、`dataConsole.repair.*` | admin + write mode | shadow-only | 同 FNX-TM-080 | ConfirmAction、dry-run 前置、rollback/contract evidence | `blocked_contract_needed` |
| FNX-TM-090 | P1 | `/settings` | `/next/settings` | 账户安全、MFA、风控、行业排除、LLM、因子、量化参数 | `settings.getWorkspace`、`settings.saveSection` | authenticated/admin by section | exact/shadow-only | `docs/frontend-next/style-specs/settings-style-spec-2026-06-05.md`、`images/settings-web.png` | section save echo、field validation、403 fixture | `gap_open` |
| FNX-TM-091 | P1 | `/settings` flags/audit | `/next/settings` feature flag/audit | feature flags、feature flag audit、operation audit、latest data refresh | `settings.featureFlags.*`、`settings.getAudit`、`settings.refreshLatestData` | admin/live-smoke operator | exact/shadow-only | 同 FNX-TM-090 | no-write trace、live-smoke rollback、audit echo | `blocked_contract_needed` |
| FNX-TM-100 | P1 | `/emotion`、`/low-buy`、`/strategy`、`/performance` | `/next/emotion`、`/next/low-buy`、`/next/strategy`、`/next/performance` | 兼容跳转且不丢 query | `router.redirects` | authenticated | format-only | route 截图待补 | redirect E2E、query preservation | `gap_open` |

## 证据字段模板

后续每行进入 `parity_ready` 前必须补齐以下字段，至少写入 acceptance 或对应阶段报告：

| 字段 | 说明 |
|---|---|
| `payload_hash` | 旧/新同源 API 原始 payload hash |
| `order_hash` | 生产榜、策略表、任务列表等排序 hash |
| `request_count` | 单页首屏和核心交互请求数 |
| `eventsource_count` | 同一路由 SSE/EventSource 数量，必须为 0 或 1 |
| `screenshot_path` | 1440x900、1280x800、768x1024、390x844 截图路径 |
| `test_command` | unit/component/E2E/parity/perf 命令 |
| `permission_fixture` | anonymous、authenticated、`can_paper_trade`、admin、live-smoke operator |
| `write_mode` | `shadow`、`isolated-live-smoke` 或 `live`；本阶段不得使用真实 live |
| `blocked_reason` | 若为 `blocked_contract_needed`，必须写明缺失契约、隔离数据或回滚路径 |

## Cutover 使用限制

本文不可作为 cutover 授权依据。只有当 P0/P1 行全部具备功能、权限、数据、截图、请求/SSE、测试和 shadow 证据，且两交易日 shadow、write rollback smoke、人工视觉签收均通过后，才能进入 cutover 评审。

## 2026-06-06 Final Evidence Update

本节覆盖前文初版矩阵中的过期状态。当前 P0/P1 页面功能已达到本地 shadow parity，仍未 cutover。

| ID | 最新状态 | 证据 |
|---|---|---|
| FNX-TM-000 | `ready_for_cutover_review` | Auth guard、login、session restore、Command Palette、兼容跳转 E2E 通过；正式 cutover 前仍建议用正式账号复跑。 |
| FNX-TM-001 | `ready_for_cutover_review` | 移动导航、快捷键、兼容 route E2E 通过；四档截图已捕获。 |
| FNX-TM-002 | `ready_for_cutover_review` | `api:check`、typecheck、operation tests 通过；OpenAPI generated types 使用中。 |
| FNX-TM-003 | `shadow-only` | mutation guard 和 no-write E2E 通过；缺安全写契约的动作仍不发真实写。 |
| FNX-TM-004 | `ready_for_cutover_review` | request trace 9 路由无导航错误，EventSource 全为 0，新前端请求数不高于旧前端。 |
| FNX-TM-005 | `ready_for_cutover_review` | shared/ui wrapper tests 通过，四档截图已捕获；人工视觉签收仍未完成。 |
| FNX-TM-010 | `ready_for_cutover_review` | `/next/monitor` deep parity 完成；生产优先榜顺序 E2E 验证，`priority_board` 只按服务端顺序展示。 |
| FNX-TM-011 | `shadow-only` | 观察池/持仓录入有二次确认和 no-write E2E；真实写需安全契约。 |
| FNX-TM-012 | `ready_for_cutover_review` | 关键位、量价标签、AI 榜单解读展示已接入。 |
| FNX-TM-020 | `ready_for_cutover_review` | 市场总闸、breadth、pulse、sector、ETF、review、runtime E2E 通过。 |
| FNX-TM-021 | `ready_for_cutover_review` | runtime/sync/data quality 展示已完成；任务写入仍按 data-console 安全契约处理。 |
| FNX-TM-030 | `ready_for_cutover_review` | 单票分析、关键位、异常、报价、K 线 fallback E2E 通过。 |
| FNX-TM-031 | `ready_for_cutover_review` | 批量分析 E2E 通过；Worker/sync fallback 单测通过。 |
| FNX-TM-032 | `shadow-only` | 分析到模拟委托保持 paper write guard。 |
| FNX-TM-040 | `ready_for_cutover_review` | playbook 策略 meta、候选、绩效、详情联动 E2E 通过。 |
| FNX-TM-041 | `ready_for_cutover_review` | 报价刷新和记录状态 no-write E2E 通过。 |
| FNX-TM-050 | `ready_for_cutover_review` | paper 账户/持仓/订单/成交/绩效/风险/机甲 E2E 通过。 |
| FNX-TM-051 | `shadow-only` | 模拟委托二次确认 no-write E2E 通过；默认不发真实订单。 |
| FNX-TM-052 | `blocked_contract_needed` | pause/resume/reconcile 等仍需隔离账号和回滚契约。 |
| FNX-TM-060 | `ready_for_cutover_review` | strategy-tracking 表格、筛选、详情、tabs E2E 通过。 |
| FNX-TM-061 | `ready_for_cutover_review` | 表现、持有、漂移、诊断、relative strength 读取已覆盖。 |
| FNX-TM-062 | `blocked_contract_needed` | review/journal 写入仍 blocked/no-write。 |
| FNX-TM-070 | `ready_for_cutover_review` | backtest run/detail/equity/trades E2E 通过。 |
| FNX-TM-071 | `shadow-only` | submit 默认 guard；cancel/validate/optimize 真实写需安全契约。 |
| FNX-TM-080 | `ready_for_cutover_review` | data coverage/SLA/tasks/workers/repair/inspector E2E 通过。 |
| FNX-TM-081 | `blocked_contract_needed` | data repair/backfill/task 真实写需契约和回滚。 |
| FNX-TM-090 | `ready_for_cutover_review` | settings security/risk/sector/factor/flags/quant/governance/audit E2E 通过。 |
| FNX-TM-091 | `blocked_contract_needed` | feature flag guard 已有；非 feature-flag 写和正式 admin live-smoke 待契约/授权。 |
| FNX-TM-100 | `ready_for_cutover_review` | compatibility routes E2E 通过。 |

`ready_for_cutover_review` 只表示本地 shadow 功能、请求、截图和测试证据已满足进入评审；不表示已经 cutover。最终 cutover 仍需用户明确授权。

## 2026-06-06 Visual/API Fix Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-040 | `ready_for_cutover_review` | `/next/playbook` 422 已修复；priority-board 不再接收研究策略 key 或超限 limit；旧新 review similarity 0.9350。 |
| FNX-TM-041 | `ready_for_cutover_review` | 报价/候选/策略 tabs 在正常业务页渲染，无 4xx；生命周期动作仍 no-write。 |
| FNX-TM-050 | `ready_for_cutover_review` | `/next/paper` 首屏去除多余说明，委托弹窗化，机甲/粒子/API 失败可见 E2E 继续通过；旧新 review similarity 0.8503。 |
| FNX-TM-051 | `shadow-only` | 模拟委托二次确认仍默认不发写请求；表单入口改弹窗后 E2E 通过。 |
| FNX-TM-004 | `ready_for_cutover_review` | 最新 request trace 9 路由全部无导航错误，新前端请求数不高于旧前端，EventSource 全为 0。 |
| FNX-TM-005 | `ready_for_cutover_review` | 最新 screenshot parity 1440/1280/768/390 全捕获；人工签收仍单独待用户确认。 |

## 2026-06-06 QA Gate Hardening Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-004 | `ready_for_cutover_review` | `START_LEGACY_FRONTEND=1 npm run request:trace` PASS；新前端请求数分别为 monitor 2、market 2、paper 2、strategy 9、analysis 1、playbook 6、backtest 2、data 1、settings 1，均不高于旧前端；EventSource 全为 0。 |
| FNX-TM-005 | `ready_for_cutover_review` | `screenshot:parity` 已加严：`/next/*` 出现错误边界、未捕获 JS 异常或失败 API 响应时会失败；最新 9 个新路由这些字段均为空，四档截图均已捕获。 |
| FNX-TM-090 | `ready_for_cutover_review` | `/next/settings` 运行诊断改为“治理”页签懒加载；首屏 API 请求数为 1，失败 API 响应为 0；治理页签仍保留运行配置读取能力。 |
| FNX-TM-091 | `blocked_contract_needed` | feature flag guard 仍通过；非 feature-flag 写入继续 shadow/blocked，未做真实 live 写。 |

本节不改变 cutover 限制：人工视觉签收、缺安全写契约动作和用户明确 cutover 授权仍为最终前置条件。

## 2026-06-06 Stability And Permission Hardening Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-000 | `ready_for_cutover_review` | 新增非 admin、无 `can_paper_trade` 权限负例 E2E；anonymous 仍进入 login guard。 |
| FNX-TM-003 | `shadow-only` | mutation client 已硬检查 `writeEnabled`、`writeMode`、contract status 和 `requiresAdmin`；默认 `shadow` 不发 live-smoke，admin operation 非 admin 不发请求。 |
| FNX-TM-004 | `ready_for_cutover_review` | API client 增加 timeout/offline/network/aborted 分类、只读 429/5xx 单次重试、Query retry 收敛；最新 request trace 仍无重复 SSE/请求放大。 |
| FNX-TM-005 | `ready_for_cutover_review` | AppShell 离线状态只在断网时显示；不增加页面默认描述信息。 |
| FNX-TM-050 | `ready_for_cutover_review` | `/next/paper` 无 `can_paper_trade` 被 route guard 阻断；机甲 display/review 仍只在 paper 页展示，不参与生产信号。 |
| FNX-TM-080 | `ready_for_cutover_review` | `/next/data` 非 admin route guard E2E PASS；admin 读链路 E2E PASS。 |
| FNX-TM-090 | `ready_for_cutover_review` | `/next/settings` admin-only tabs 和“功能开关写入”仅 admin 可见；feature flag mutation 绑定 `auth.isAdmin`。 |
| FNX-TM-091 | `blocked_contract_needed` | 非 feature-flag 写入继续 blocked；feature flag live-smoke 仍需单独授权、admin token、审计回显和 rollback。 |

## 2026-06-06 Query Cancellation And Resource Cleanup Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-003 | `shadow-only` | API wrapper 可取消能力补齐后，缺契约写入仍由 mutation guard 保持 shadow/blocked；本轮未开放真实写。 |
| FNX-TM-004 | `ready_for_cutover_review` | `/next/strategy-tracking`、`/next/playbook` TanStack Query 均传递 abort `signal`；`START_LEGACY_FRONTEND=1 npm run request:trace` PASS，9 路由 EventSource 全为 0，新前端请求数不高于旧前端。 |
| FNX-TM-005 | `ready_for_cutover_review` | Toast timer、Dialog focus timer、Kline empty data、Lightweight Charts remove、ECharts dispose、PaperMechaParticles RAF/resize cleanup 均有单测；`npm test -- --run` PASS，11 files / 40 tests。 |
| FNX-TM-030 | `ready_for_cutover_review` | `/next/analysis` 手动单票/批量请求增加 `AbortController`，重复触发或切页不会让旧响应回写；Kline 空数据清图。 |
| FNX-TM-040 | `ready_for_cutover_review` | `/next/playbook` 已迁入 TanStack Query，low-buy screener、priority-board、strategies、meta、quotes 均可随 route/query 取消。 |
| FNX-TM-060 | `ready_for_cutover_review` | `/next/strategy-tracking` 通用 `operationQuery` 已统一把 TanStack `signal` 传到 `requestOperation`。 |
| FNX-TM-050 | `ready_for_cutover_review` | 机甲 Canvas 特效单测证明 unmount 取消 RAF、移除 resize listener；reduced-motion 下不启动动画，仍仅用于 paper display/review。 |

本节不改变 cutover 限制：人工视觉签收、正式验收账号复跑、缺安全写契约动作和用户明确 cutover 授权仍为最终前置条件。

## 2026-06-06 Client Telemetry Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-003 | `shadow-only` | mutation guard 现在记录 shadow-only、blocked_contract_needed、write-disabled、mode-blocked、permission-blocked、sent 等前端内存事件；不记录 payload，也不改变缺契约写入的 blocked 状态。 |
| FNX-TM-004 | `ready_for_cutover_review` | `npm run perf:compare` 输出 `window.__FRONTEND_NEXT_TELEMETRY__()` 快照，可按 route 查看 API/SSE/Worker/Chart/Mutation/UI 事件计数；API 错误去重后同一次 HTTP 响应只记录一次。 |
| FNX-TM-005 | `ready_for_cutover_review` | 新增 `shared/telemetry` 单测，脱敏 token/secret/cookie/authorization 等敏感字段，内存环形缓冲上限 200 条；最新 `npm test -- --run` PASS，12 files / 42 tests。 |
| FNX-TM-030 | `ready_for_cutover_review` | Analysis Kline/Worker 相关路径具备 chart/worker telemetry 证据入口；只记录显示层 init、set-data、fallback、dispose，不参与分析结论或交易信号计算。 |
| FNX-TM-040 | `ready_for_cutover_review` | Playbook Query 取消和只读请求可通过 API telemetry 与 request trace 交叉核对；不改变 research-only/near-entry 边界。 |
| FNX-TM-050 | `ready_for_cutover_review` | Paper 机甲/图表 telemetry 仅作为 display/review 资源释放诊断，不参与生产排序、生产信号、模拟委托判断。 |
| FNX-TM-060 | `ready_for_cutover_review` | Strategy Tracking 只读 operation query 可通过 API telemetry 验证请求状态；review/journal 写入仍 blocked_contract_needed。 |

本节不代表上线观测系统接入：telemetry 仅浏览器内存可读，不持久化、不发送后端、不改变 API 契约、生产策略语义或 cutover 前置条件。

## 2026-06-06 No Fake Chart Data Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-030 | `ready_for_cutover_review` | `/next/analysis` 不再在无真实 K 线 bars 时回退测试样例曲线；`chartPoints(null)` 和无 bars 快照返回空数组，`KlineChart` 已有空数据清图测试。 |
| FNX-TM-050 | `ready_for_cutover_review` | `/next/paper` 逐股盈亏表和绩效指标将 `unrealized_pnl` 显示为“浮动盈亏”，避免被误读为“功能未实现”；只改展示文案，不改收益口径。 |

本节强化“不伪造成功/不展示假数据”边界：缺数据时显示空图或空态，由页面错误/空态承担解释，不用测试样例替代后端业务数据。

## 2026-06-06 Auth Operation Adapter Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-000 | `ready_for_cutover_review` | `features/auth/authModel.tsx` 已改为调用 `shared/api/auth.ts` 的 `authApi.me/login/register/refresh/logout/totp`，由 `apiOperations` 统一生成路径，不再在 feature 层拼 auth URL。 |
| FNX-TM-002 | `ready_for_cutover_review` | auth user/token/MFA 类型收敛到 `shared/api/types.ts` 的 OpenAPI generated aliases；`npm run typecheck` 和 auth adapter 单测通过。 |
| FNX-TM-030 | `ready_for_cutover_review` | 未被生产代码引用的 `shared/testing/fixtures.ts` 已移除，避免测试样例优先榜/K 线数据未来误入业务页。 |

本节只收敛前端契约边界和测试样例隔离，不改变认证接口、token 存储语义、权限守卫或后端契约。

## 2026-06-06 Compatibility Route Query Preservation Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-001 | `ready_for_cutover_review` | `/next/emotion`、`/next/low-buy`、`/next/strategy`、`/next/performance` 兼容跳转已显式保留当前 query/search，避免从旧入口带入的 `symbol`、`source` 等上下文丢失；`keyboardShortcuts.test.ts` 覆盖 Cmd/Ctrl+K 和 Cmd/Ctrl+1~8。 |
| FNX-TM-100 | `ready_for_cutover_review` | `routeTree.tsx` 兼容 `Navigate` 使用 `search={true}`；`App.test.tsx` 覆盖 route inventory 和 query preservation；`app-shell-auth.spec.ts` 覆盖 4 个兼容入口 query preservation、Command Palette 页面跳转和 390x844 移动导航打开/跳转/遮罩关闭。 |

本节只影响 `/next/*` shadow 兼容跳转的前端导航上下文保留，不改变目标页面、权限 guard、API 请求、生产排序、策略语义或写入模式。

## 2026-06-06 Command Palette Strategy Navigation Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-001 | `ready_for_cutover_review` | Command Palette 已补策略跳转：`首板` 跳转 `/next/playbook?strategy=first_board`，`N形` 跳转 `/next/strategy-tracking?strategy_key=n_pattern_long_wash`；`app-shell-auth.spec.ts` 已覆盖页面、股票代码、策略三类入口。 |
| FNX-TM-040 | `ready_for_cutover_review` | `/next/playbook` 可读取 `strategy` query 并切换策略 tab；非法或非白名单格式 query 会回落到默认策略，不把中文标签当策略 key。 |
| FNX-TM-060 | `ready_for_cutover_review` | `/next/strategy-tracking` 可读取 `strategy_key` query 并同步筛选状态；仅用于表格筛选和页面上下文，不触发 review/journal 写入。 |

策略命令 registry 只是导航索引，策略真值、生产资格、排序和 `production_score` 仍由后端与既有 API 决定；本节不改变生产策略语义、`priority_board` 或任何写入模式。

## 2026-06-06 AppShell Auth/Navigation Usability Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-000 | `ready_for_cutover_review` | 登录后可恢复 `AuthGuard` 写入的 `/next/*` 深链路 redirect；`safeRedirectPath` 单测覆盖外链/非 next 路径回落。 |
| FNX-TM-001 | `ready_for_cutover_review` | 顶栏新增用户菜单，支持进入系统设置和退出登录；全局快捷键在可编辑字段内不再误触页面跳转或命令面板；`app-shell-auth.spec.ts` 覆盖用户菜单，`keyboardShortcuts.test.ts` 覆盖输入态 guard。 |

本节只影响新前端 AppShell 的导航可用性和误触防护；不改变权限模型、API 契约、写入模式、生产排序或策略语义。

## 2026-06-06 Command Palette Focus Trap Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-001 | `ready_for_cutover_review` | Command Palette 继续覆盖页面、策略、股票代码三类命令，同时补焦点进入、Tab trap、Esc 关闭和触发按钮焦点恢复 E2E。 |
| FNX-TM-005 | `ready_for_cutover_review` | Command Palette 复用 `shared/ui/dialogFocus`，与 Modal/Drawer 共用 focus 生命周期能力，不再单独手写 Escape/focus 行为。 |

本节只影响弹层键盘可访问性，不改变命令目标、路由 query、API 请求、权限或写入模式。

## 2026-06-06 Command Palette Shared UI Wrapper Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-001 | `ready_for_cutover_review` | Command Palette 的页面、策略、股票代码三类命令继续由 feature 层生成和执行；UI shell 下沉到 `shared/ui/CommandPalette.tsx` 后，`app-shell-auth.spec.ts` 仍覆盖三类入口和 focus trap。 |
| FNX-TM-005 | `ready_for_cutover_review` | `shared/ui/CommandPalette.tsx` 复用 `shared/ui/dialogFocus`，并由 `shared/ui/__tests__/wrappers.test.tsx` 覆盖打开聚焦、Enter 执行、Esc 关闭和焦点恢复；wrapper 不引入第三方默认样式。 |

本节只收敛新前端 UI wrapper 分层；不改变命令目标、路由 query、API 请求、权限、写入模式、生产排序或策略语义。

## 2026-06-06 Paper Order Form Usability Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-050 | `ready_for_cutover_review` | `/next/paper` 账户/持仓/订单/成交/风险/绩效/机甲 display/review 仍由只读 BFF 数据驱动；表单增强不改变展示字段口径。 |
| FNX-TM-051 | `shadow-only` | 模拟委托表单补导入推荐、持仓导入、数量快捷和费用估算；`paper-mecha.spec.ts` 验证二次确认、提交 shadow 记录和 0 个真实写请求。 |

本节只补 `/next/paper` shadow 委托草稿体验；不开放 live 写入，不改变模拟账户真实状态、生产排序、策略信号或后端契约。

## 2026-06-06 Analysis To Paper Shadow Handoff Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-030 | `ready_for_cutover_review` | `/next/analysis` 单票分析结果页新增“模拟下单”动作，必须先有分析响应才可点击；仍只读取 analyze/quote/kline/key-level/anomaly 数据。 |
| FNX-TM-032 | `ready_for_cutover_review` | `paperOrderDraftSearch` 将分析结果转成 `/next/paper?source=analysis...` 草稿；`paperOrderDraftFromSearch` 只接受 analysis 来源并自动打开一次 shadow 委托弹窗。`analysis-playbook.spec.ts` 验证跳转、草稿字段和 no-write trace。 |
| FNX-TM-051 | `shadow-only` | 委托草稿最终仍进入 `/next/paper` shadow 表单和二次确认；E2E 只观察到 `POST /api/analyze`，未触发 paper order 写请求。 |

本节只补分析到模拟盘的前端草稿联动；不新增后端 API，不开放 live 写入，不改变生产排序、`priority_board`、`production_score`、策略语义或模拟账户真实状态。

## 2026-06-06 Symbol Analysis Navigation Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-001 | `ready_for_cutover_review` | Router search 改为普通 query 序列化；Command Palette 输入 6 位股票代码跳转 `/next/analysis?symbol=...` 后，分析输入框填入目标代码。 |
| FNX-TM-010 | `ready_for_cutover_review` | `/next/monitor` 选中生产优先榜标的后可从关键位面板进入分析页；选中 symbol 写入当前页 query，浏览器返回后保留上下文。 |
| FNX-TM-030 | `ready_for_cutover_review` | `/next/analysis` 读取 `symbol` query，query 变化会取消旧请求并清空旧结果，避免旧响应覆盖新标的。 |
| FNX-TM-041 | `ready_for_cutover_review` | `/next/playbook` 候选详情新增“分析”动作，带 `strategy + symbol` query 保留候选上下文；E2E 覆盖进入分析和返回。 |

本节只补股票代码进入分析和返回上下文保持；不改变生产优先榜顺序、不触发写请求、不改变策略判断、后端契约或旧前端。

## 2026-06-06 Shadow Action Draft Refresh Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-003 | `shadow-only` | `ShadowActionPanel` 会在父级字段变化时重置草稿和二次确认状态，避免旧上下文草稿被提交到 shadow/mutation guard。 |
| FNX-TM-005 | `ready_for_cutover_review` | `shared/ui/__tests__/wrappers.test.tsx` 覆盖 shadow action draft refresh；所有 shadow 表单继续走 shared UI wrapper。 |
| FNX-TM-011 | `shadow-only` | `/next/monitor` 选中不同标的后，观察池维护/持仓录入表单会同步当前标的；monitor E2E 仍验证 0 个真实写请求。 |

本节只修复新前端 shadow 表单本地状态；不开放真实写入，不改变后端契约、生产排序、策略语义或旧前端。

## 2026-06-06 Analysis Batch Worker Sort Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-004 | `ready_for_cutover_review` | `shared/workers` 增加 `sort` 任务，worker timeout、messageerror、`ok=false` 都回退同步排序；telemetry 继续记录 worker/fallback 状态。 |
| FNX-TM-030 | `ready_for_cutover_review` | `/next/analysis` 批量分析结果通过 `sortDisplayItems` 按展示分 `score desc` 稳定排序；E2E 验证最高分 `600000` 位于批量结果第一行。 |
| FNX-TM-003 | `shadow-only` | 该排序只影响分析页展示表格，不参与 mutation、写请求、生产优先榜、`priority_board` 或 `production_score`。 |

本节只补 display-only Worker 计算能力；不改变 API 契约、后端响应、生产排序、策略判断、写入边界或旧前端。

## 2026-06-06 Chart Downsample Endpoint Stability Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-004 | `ready_for_cutover_review` | `downsample` 保留首尾端点，不均匀点数也不会丢失最新尾点；worker/sync fallback 共用同一纯计算实现。 |
| FNX-TM-030 | `ready_for_cutover_review` | `/next/analysis` K 线显示层降采样不会把最新点裁掉；空 bars 仍显示空态，不伪造图表数据。 |
| FNX-TM-005 | `ready_for_cutover_review` | 图表端点稳定性由 worker/chart/analysis 单测覆盖，不新增可见说明文案或第三方默认样式。 |

本节只修复图表显示层采样稳定性；不改变原始数据、分析结论、生产排序、策略语义、写入边界或旧前端。

## 2026-06-06 Kline Worker Downsample Adapter Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-004 | `ready_for_cutover_review` | `KlineChart` 通过 `downsampleChartPoints` 进入 worker downsample；worker 失败/不可用时继续 sync fallback。 |
| FNX-TM-030 | `ready_for_cutover_review` | `/next/analysis` K 线写入 Lightweight Charts 前完成显示层采样，sequence guard 防止旧标的采样结果覆盖新标的。 |
| FNX-TM-005 | `ready_for_cutover_review` | chart 单测覆盖空数据清图、downsample adapter、stale async guard 和 cleanup。 |

本节只把 K 线显示层降采样接入 worker/fallback；不改变业务数据、分析结论、生产排序、策略语义、写入边界或旧前端。

## 2026-06-06 Backtest Workflow Tabs Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-070 | `ready_for_cutover_review` | `/next/backtest` 结果概览页签集中展示 run metrics、详情字段和权益曲线；运行列表补名称列并可点击进入结果概览。 |
| FNX-TM-071 | `shadow-only` | 提交、取消、验证/优化进入 `提交任务` 和 `研究闭环` 页签，继续走 `ShadowActionPanel`、二次确认和 mutation guard；E2E 证明无真实写请求。 |
| FNX-TM-005 | `ready_for_cutover_review` | 页签结构对齐 `backtest-style-spec-2026-06-05.md`，使用 shared `Tabs`、`Panel`、`DataGrid`、`ShadowActionPanel` wrapper。 |

本节只改善新前端回测页工作流组织和可用性；不改变回测真实任务状态、后端契约、生产排序、策略语义、写入边界或旧前端。

## 2026-06-06 Settings MFA Shadow Management Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-003 | `shadow-only` / `blocked_contract_needed` | `/next/settings` MFA 管理只记录 setup/disable 本地意图；真实 TOTP setup/enable/disable 仍需安全写契约和回滚证据。 |
| FNX-TM-005 | `ready_for_cutover_review` | `MFA 管理` 复用 `ShadowActionPanel` wrapper、二次确认、状态 pill 和设置页分区布局，不直接使用第三方默认样式。 |
| FNX-TM-090 | `ready_for_cutover_review` | 账户与安全分区展示 MFA 当前状态、用户信息和安全写入边界；不展示 secret 或二维码。 |

本节只补设置页 MFA 可见管理入口；不开放真实账号安全写入，不改变后端契约、账户真实 MFA 状态、生产排序、策略语义或旧前端。

## 2026-06-06 Settings Section Shadow Management Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-003 | `shadow-only` / `blocked_contract_needed` | `配置写入`、`行业排除管理`、`因子权重管理` 进入 guarded mutation；缺安全写契约时返回 blocked 且不发送真实请求。 |
| FNX-TM-090 | `ready_for_cutover_review` | `/next/settings` 风控、行业排除、因子、量化参数、策略治理均有可见管理入口和 no-write E2E 证据。 |
| FNX-TM-091 | `blocked_contract_needed` | 非 feature-flag 设置写入仍缺保存、回显、审计和回滚契约；当前只进入 shadow/blocked 状态。 |

本节只补设置页各分区配置管理入口；不开放真实设置写入，不改变后端契约、生产排序、策略语义或旧前端。

## 2026-06-06 Shadow Submit And Menu Layer Stability Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-003 | `shadow-only` / `blocked_contract_needed` | `ShadowActionPanel` 提交中禁用按钮，防止二次确认后重复触发 shadow/mutation intent；失败时保留草稿并显示错误。 |
| FNX-TM-005 | `ready_for_cutover_review` | shared wrapper 单测覆盖提交中防重复、失败恢复、父字段变化重置状态；所有 shadow 表单继续通过 shared UI wrapper。 |
| FNX-TM-001 | `ready_for_cutover_review` | AppShell topbar/user menu 层级高于页面 sticky 工具条；设置页内用户菜单可正常点击退出登录。 |
| FNX-TM-004 | `ready_for_cutover_review` | 最新 `e2e`、`perf:compare`、`screenshot:parity` 均通过；核心路由未发现重复 SSE 或请求放大。 |

本节只修复新前端本地交互稳定性和菜单层级；不开放真实写入，不改变后端契约、生产排序、策略语义、旧前端或 cutover 限制。

## 2026-06-06 Auth Refresh Recovery Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-000 | `ready_for_cutover_review` | `requestJson` 对读请求和 `/api/auth/me` 的 401 执行 refresh token 续期，并重试原请求一次；auth E2E 继续通过。 |
| FNX-TM-002 | `ready_for_cutover_review` | refresh 调用走 OpenAPI operation path `/api/auth/refresh`，token response 使用 generated `AuthTokenResponse` 类型。 |
| FNX-TM-003 | `shadow-only` / `blocked_contract_needed` | 写请求 401 不自动 refresh+retry，避免真实写入或 live-smoke 动作重复提交。 |
| FNX-TM-004 | `ready_for_cutover_review` | API telemetry 记录脱敏 `auth-refresh` 成功/失败事件，不记录 token、secret、body 或 cookie。 |

本节只补认证过期恢复稳定性；不改变后端契约、真实写入、生产排序、策略语义、旧前端或 cutover 限制。

## 2026-06-06 Error Boundary And Telemetry Redaction Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-004 | `ready_for_cutover_review` | telemetry 字符串值新增通用 redaction；`auth-refresh`、chart error、API request 诊断均不记录 token、secret、password、cookie 原值。 |
| FNX-TM-005 | `ready_for_cutover_review` | `AppErrorBoundary` 通过 shared redaction 后再展示错误 message，不新增可见说明文案或第三方默认样式。 |
| FNX-TM-030 | `ready_for_cutover_review` | `KlineChart` downsample/chart error 记录前先脱敏，错误恢复仍清空图表数据并保留页面可用。 |

本节只增强新前端错误展示和诊断日志的敏感信息保护；不改变后端契约、真实写入、生产排序、策略语义、旧前端或 cutover 限制。

## 2026-06-06 Route Level Error Boundary Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-001 | `ready_for_cutover_review` | `/next/*` 页面渲染异常时 AppShell、导航和账户菜单仍保留；E2E 验证可从失败的 `/next/analysis` 跳转到 `/next/playbook`。 |
| FNX-TM-005 | `ready_for_cutover_review` | 所有业务路由统一包 `RouteErrorBoundary`，fallback 复用 shared UI `Panel`/`Button` 和 shared redaction。 |
| FNX-TM-004 | `ready_for_cutover_review` | 页面级异常不新增请求、SSE、Worker 或真实写入；只影响当前路由内容区渲染恢复。 |

本节只增强新前端页面级容错；不改变后端契约、真实写入、生产排序、策略语义、旧前端或 cutover 限制。

## 2026-06-06 Paper Mecha Reduced Motion Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-005 | `ready_for_cutover_review` | `PaperMechaParticles` 复用 shared `createReducedMotionSignal()`，系统 reduced motion 运行时切换会触发 effect cleanup 和重建。 |
| FNX-TM-050 | `ready_for_cutover_review` | 机甲 Canvas 粒子单测覆盖卸载、初始 reduced motion、运行时开启 reduced motion 三种路径；开启后取消 RAF、移除 resize listener 并清理 Canvas。 |
| FNX-TM-004 | `ready_for_cutover_review` | 动效切换不新增 API、SSE、Worker、Chart 或 Mutation 事件；只影响 `/next/paper` 本地 Canvas display/review。 |

本节只增强模拟盘机甲 display/review 动效的可访问性和资源释放；不改变后端契约、真实写入、生产排序、策略语义、旧前端或 cutover 限制。

## 2026-06-06 SSE Reconnect Stability Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-004 | `ready_for_cutover_review` | `startQuoteSse` 在 stream error 后关闭旧 EventSource，按指数退避重连，并在最后订阅者 cleanup 时取消 pending reconnect。 |
| FNX-TM-001 | `ready_for_cutover_review` | AppShell 的实时流状态继续显示 `connecting/open/error/closed`；SSE 异常不会拖垮 shell 或页面内容区。 |
| FNX-TM-005 | `ready_for_cutover_review` | `sseClient.test.ts` 覆盖同 URL 共享、错误重连、无效 payload 降级、cleanup 取消 pending reconnect。 |

本节只增强新前端实时流连接恢复和资源释放；不改变后端契约、真实写入、生产排序、策略语义、旧前端或 cutover 限制。

## 2026-06-06 User-Facing Error Message Redaction Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-003 | `shadow-only` / `blocked_contract_needed` | Shadow 表单失败结果复用 `shared/api/errorMessage`，保留草稿与二次确认状态，但不渲染原始 token/password。 |
| FNX-TM-004 | `ready_for_cutover_review` | 用户可见错误文案、error boundary 和 telemetry 均复用同一 redaction 工具覆盖敏感片段。 |
| FNX-TM-005 | `ready_for_cutover_review` | `ShadowActionPanel` 继续作为 shared UI wrapper 承载错误展示，不在页面内复制私有错误文案实现。 |
| FNX-TM-050 | `shadow-only` | `PaperOrderForm` 提交失败只更新本地委托状态文案，真实模拟盘写入仍由 mutation guard 控制。 |

本节只增强新前端用户可见错误文案的敏感信息保护；不改变后端契约、真实写入、生产排序、策略语义、旧前端或 cutover 限制。

## 2026-06-06 Worker Error Redaction Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-004 | `ready_for_cutover_review` | Worker `ok=false` 响应和 worker fallback telemetry 均脱敏 error 字符串；`workerClient.test.ts` 覆盖 token/password 不进入 telemetry。 |
| FNX-TM-005 | `ready_for_cutover_review` | Worker crash 后仍返回同步 fallback 结果，页面无需新增私有错误 UI 或第三方默认样式。 |
| FNX-TM-030 | `ready_for_cutover_review` | Analysis batch sort/Kline downsample 等 Worker 调用失败时保持 display-only fallback，不影响分析 API 结果或生产榜顺序。 |

本节只增强新前端 Worker 失败诊断的敏感信息保护和 fallback 可观测性；不改变后端契约、真实写入、生产排序、策略语义、旧前端或 cutover 限制。

## 2026-06-06 Worker PostMessage Fallback Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-004 | `ready_for_cutover_review` | `workerClient` 捕获 `postMessage` 同步异常并记录 `postmessage-fallback` telemetry，错误文本脱敏。 |
| FNX-TM-005 | `ready_for_cutover_review` | 单测覆盖 `postMessage` 抛错后的 listener 清理和 sync fallback，避免页面挂起或泄露监听器。 |
| FNX-TM-030 | `ready_for_cutover_review` | Analysis batch sort/Kline downsample 等 Worker 任务在不可克隆 payload 等异常下仍回退同步显示层计算。 |

本节只增强新前端 Worker postMessage 失败恢复和资源释放；不改变后端契约、真实写入、生产排序、策略语义、旧前端或 cutover 限制。

## 2026-06-06 Safe Write Contract Definition Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-003 | `shadow-only` / `blocked_contract_needed` | 新增 `docs/frontend-next/safe-write-contracts-2026-06-06.md` 和 `frontend-next/src/shared/api/safeWriteContracts.ts`，每个 guarded write 均有 `FNX-SW-*` contract id、权限、幂等、审计、回滚和验收要求。 |
| FNX-TM-011 | `defined_backend_needed` | 观察池写入映射 `FNX-SW-WATCHLIST`；真实写仍需后端隔离数据和 create/delete rollback 证据。 |
| FNX-TM-041 | `defined_backend_needed` | Playbook lifecycle/governance 映射 `FNX-SW-PLAYBOOK-LIFECYCLE`；`near_entry` 仍 watch-only，不进入生产排序。 |
| FNX-TM-051 | `defined_isolated_live_smoke` | 模拟委托映射 `FNX-SW-PAPER-ORDER`；当前默认 shadow，只有隔离账号、回滚证据和单独授权后才允许 smoke。 |
| FNX-TM-052 | `defined_backend_needed` | pause/resume/reconcile/refresh 映射 `FNX-SW-PAPER-ACCOUNT`；仍缺隔离模拟盘账号状态恢复证据。 |
| FNX-TM-062 | `defined_backend_needed` | 复盘与交易日志映射 `FNX-SW-STRATEGY-REVIEW`、`FNX-SW-TRADE-JOURNAL`；当前不发送真实写。 |
| FNX-TM-071 | `defined_isolated_live_smoke` / `defined_backend_needed` | create run 映射 `FNX-SW-BACKTEST-TASK` 可按隔离 smoke 验收；cancel/validate/optimize 仍需测试 run/task 标记和回滚证据。 |
| FNX-TM-081 | `defined_backend_needed` | data task/backfill/repair 映射 `FNX-SW-DATA-TASK`、`FNX-SW-DATA-REPAIR`；仍需 dry-run/apply/cancel/rollback 后端证据。 |
| FNX-TM-090 | `defined_backend_needed` | settings section save、行业排除、因子权重映射 `FNX-SW-SETTINGS-SECTION`；仍需 section version、echo 和 restore previous version。 |
| FNX-TM-091 | `defined_isolated_live_smoke` / `defined_backend_needed` | feature flag 映射 `FNX-SW-FEATURE-FLAG`；database maintenance 映射 `FNX-SW-DATABASE-MAINTENANCE`，本阶段仍不执行生产 live。 |

本节只完成安全写契约定义和前端 registry 对齐；不修改后端、不开放 blocked 写入、不部署、不切流。`defined_*` 不等于 `parity_ready`，真实写入仍必须补后端实现、隔离数据、审计回显、回滚证据和用户授权。

## 2026-06-06 Safe Write Request Evidence Update

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-TM-003 | `shadow-only` / `blocked_contract_needed` / `defined_isolated_live_smoke` | `createMutationClient` 只有在写开关、写模式、权限和 contract status 全部通过后才会生成 `clientRequestId` 并调用 requester；shadow/blocked 分支仍不发送。 |
| FNX-TM-004 | `ready_for_cutover_review` | mutation telemetry 增加 `safe_write_contract_id` 和 `client_request_id`，仍不记录 payload、token、secret、password 或 cookie。 |
| FNX-TM-051 | `defined_isolated_live_smoke` | `paperOrderCreate` live-smoke 请求会附加 `X-Frontend-Next-Contract-Id: FNX-SW-PAPER-ORDER` 等证据 header；仍需隔离账号和 rollback smoke。 |
| FNX-TM-071 | `defined_isolated_live_smoke` | `backtestRunCreate` live-smoke 请求会附加安全写 header；仍需测试 run 标记、cancel/delete 和审计回显。 |
| FNX-TM-091 | `defined_isolated_live_smoke` | `featureFlagUpdate` live-smoke 请求会附加安全写 header；仍需 admin token、toggle/restore 和 audit echo。 |

本节只补前端侧请求证据链，不修改后端、不开放 `blocked_contract_needed` 写入、不部署、不切流。请求 header 不能替代后端幂等、审计和回滚验收。
