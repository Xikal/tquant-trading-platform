# Frontend Next Permissions Matrix - 2026-06-06

状态：权限与写入模式验收矩阵初版，未部署，未切流
适用范围：`frontend-next/` P0/P1 页面、危险操作、写入模式、403 降级与证据字段
最后核验日期：2026-06-06

## 结论

`frontend-next/` 不能只靠隐藏按钮表达权限。所有 P0/P1 页面必须同时具备 route guard、action guard、mutation mode guard 和 403 fallback。当前认证、paper/admin guard、live-smoke、数据修复、复盘写入和 feature flag 隔离回滚证据均未完整，因此相关能力保持 `gap_open`、`shadow-only` 或 `blocked_contract_needed`。

## 角色与模式

| 角色/模式 | 可见范围 | 可写范围 | 明确禁止 |
|---|---|---|---|
| `anonymous` | 登录页、公开错误页 | 无 | 访问 `/next/*` 业务页 |
| `authenticated_observer` | monitor、market、analysis、playbook、strategy-tracking 只读 | 自选/观察类 shadow 写入，按后端权限决定 | paper 委托、admin 数据修复、feature flag 写入 |
| `can_paper_trade` | paper 页面、模拟盘 display/review | paper shadow 写入；live-smoke 需额外模式 | 真实交易、生产排序、admin 操作 |
| `admin` | data、settings admin tabs、审计、数据任务 | data/settings 安全写入；默认 shadow | 未确认危险操作、绕过 dry-run |
| `live_smoke_operator` | 隔离账号或隔离标记下的 live-smoke | 可回滚测试写入 | 影响真实生产数据、绕过审计 |

## 写入模式

| 模式 | 含义 | 允许条件 | 验收证据 |
|---|---|---|---|
| `shadow` | 不发真实写请求，只记录 shadow/no-write 结果 | 默认模式 | no-write request trace、shadow record |
| `isolated-live-smoke` | 使用隔离账号、隔离标记或测试 run，允许回滚 | 用户明确允许对应 smoke，且存在回滚路径 | create/apply/cancel/rollback trace、audit echo |
| `live` | 真实生产写入 | 本阶段禁止 | 不适用 |

## 页面权限矩阵

| ID | 路由 | 最低可见角色 | 可读范围 | 可写/危险操作 | 必须 guard | 禁止 | 当前状态 |
|---|---|---|---|---|---|---|---|
| FNX-PERM-000 | `/next/*` | authenticated | 对应业务页读取 | 由各页 action 决定 | route guard、401 refresh、403 fallback | anonymous 直接进入业务页 | `gap_open` |
| FNX-PERM-010 | `/next/monitor` | authenticated_observer | 市场状态、生产优先榜、持仓/观察、关键位 | 持仓/观察池 add/edit/delete 默认 shadow | action guard、write mode guard | 前端重排生产榜、前端计算生产分 | `gap_open` |
| FNX-PERM-020 | `/next/monitor/market` | authenticated_observer | 市场总闸、宽度、脉冲、板块/ETF、复盘摘要 | instrument sync 或 runtime 任务需 admin/contract | admin guard for task actions | 非 admin 执行运行时任务 | `gap_open` |
| FNX-PERM-030 | `/next/analysis` | authenticated_observer | 单票/批量分析、关键位、异常、K 线 | 打开 paper 委托需 `can_paper_trade` | form validator、paper action guard | 未授权打开委托表单 | `gap_open` |
| FNX-PERM-040 | `/next/playbook` | authenticated_observer | 策略 meta、候选、绩效、板块 | 选择/观察类动作默认 shadow | research-only guard、near-entry guard | `near_entry` 进入生产榜 | `gap_open` |
| FNX-PERM-050 | `/next/paper` | `can_paper_trade` | 账户、持仓、订单、成交、绩效、风险、机甲 display/review | 委托、暂停/恢复、标签默认 shadow；对账 apply 需 admin | route/action guard、write mode guard、ConfirmAction | 真实交易、机甲影响信号 | `shadow-only` |
| FNX-PERM-060 | `/next/strategy-tracking` | authenticated_observer | snapshot、items、详情、报告、relative strength | 复盘和交易日志写入默认 shadow | action guard、contract guard | 缺安全 API 时伪造成功 | `blocked_contract_needed` |
| FNX-PERM-070 | `/next/backtest` | authenticated_observer | runs、detail、equity、trades、validation、optimization | submit/cancel 默认 shadow；live-smoke 需测试 run 标记 | ConfirmAction、task state guard | 任务状态假成功 | `shadow-only` |
| FNX-PERM-080 | `/next/data` | admin | SLA、gate、source health、coverage、workers | sync、refresh、backfill、repair、ETF universe | admin route guard、dry-run 前置、ConfirmAction | 非 admin 访问管理操作、绕过 dry-run | `blocked_contract_needed` |
| FNX-PERM-090 | `/next/settings` | authenticated by tab; admin for admin tabs | 账户安全、风控、行业、LLM、因子、量化参数、审计 | section save、feature flags、latest data refresh 默认 shadow | tab guard、validator、ConfirmAction | 非 admin 保存 admin 设置 | `blocked_contract_needed` |
| FNX-PERM-100 | `/next/emotion`、`/next/low-buy`、`/next/strategy`、`/next/performance` | authenticated_observer | 兼容跳转 | 无 | redirect guard | 丢失 query 或绕过权限 | `gap_open` |

## Action 权限矩阵

| ID | 操作 | 入口 | 需要角色/模式 | API operation | 数据口径 | 必须证据 | 当前状态 |
|---|---|---|---|---|---|---|---|
| FNX-ACT-001 | login/register/refresh/logout/me | `/next/login`、AppShell | anonymous/authenticated | `auth.*` | exact | auth E2E、401 refresh、session restore | `gap_open` |
| FNX-ACT-002 | MFA/TOTP enable/disable | settings/account | authenticated | `auth.totp.*` | exact | form validation、403/422 fixture、save echo | `gap_open` |
| FNX-ACT-003 | Command Palette 页面跳转 | AppShell | authenticated | `workspace.navigation` | format-only | keyboard E2E、Esc/Enter、query preservation | `gap_open` |
| FNX-ACT-004 | 6 位股票代码进入分析 | Command Palette | authenticated | `workspace.navigation.toAnalysis` | format-only | command E2E、非法代码 fallback | `gap_open` |
| FNX-ACT-005 | 生产优先榜读取 | `/next/monitor` | authenticated | `monitor.getWorkspace` | exact | payload hash、order hash、no local sort guard | `ready_for_shadow_check` |
| FNX-ACT-006 | 持仓/观察池 add/edit/delete | `/next/monitor` | authenticated + `shadow` | `monitor.watchlist.*`、`monitor.holding.*` | shadow-only | no-write trace、shadow record、ConfirmAction | `gap_open` |
| FNX-ACT-007 | AI 榜单解读 | `/next/monitor` | authenticated | `monitor.getAiDecisionSupport` | format-only | dialog screenshot、no production effect guard | `gap_open` |
| FNX-ACT-008 | 市场复盘/runtime 读取 | `/next/monitor/market` | authenticated | `monitor.getReview`、`monitor.getRuntime` | exact/tolerance | payload hash、chart dispose telemetry | `gap_open` |
| FNX-ACT-009 | instrument sync | `/next/monitor/market` | admin + `shadow` or contract | `monitor.instrumentSync` | shadow-only | 403 fixture、task trace、contract requirement | `blocked_contract_needed` |
| FNX-ACT-010 | 单票分析 | `/next/analysis` | authenticated | `analysis.analyze` | exact/tolerance | invalid/empty/error fixtures、result hash | `gap_open` |
| FNX-ACT-011 | 批量分析排序 | `/next/analysis` | authenticated | `analysis.analyzeBatch` | exact | worker vs sync hash、fallback telemetry | `gap_open` |
| FNX-ACT-012 | 从分析打开模拟委托 | `/next/analysis` -> `/next/paper` | `can_paper_trade` + `shadow` | `paper.prepareOrderDraft` | shadow-only | guard E2E、no-write trace | `shadow-only` |
| FNX-ACT-013 | 候选分层读取 | `/next/playbook` | authenticated | `playbook.getLowBuyCandidates` | exact/format-only | research-only guard、near-entry watch-only guard | `gap_open` |
| FNX-ACT-014 | 交易时段报价刷新 | `/next/playbook` | authenticated | `playbook.refreshQuotes` | exact | leaf update trace、request count | `gap_open` |
| FNX-ACT-015 | paper 委托创建 | `/next/paper` | `can_paper_trade` + `shadow` | `paper.createOrder` | shadow-only | no-write trace、form validation、duplicate submit guard | `shadow-only` |
| FNX-ACT-016 | paper live-smoke 委托 | `/next/paper` | `can_paper_trade` + `live_smoke_operator` | `paper.createOrder`、`paper.rollbackOrder` | exact/shadow-only | isolated account、create/rollback/audit trace | `blocked_contract_needed` |
| FNX-ACT-017 | paper 暂停/恢复、标签 | `/next/paper` | `can_paper_trade` + `shadow` | `paper.pause/resume`、`paper.tags.*` | shadow-only | ConfirmAction、no-write trace | `blocked_contract_needed` |
| FNX-ACT-018 | paper 对账 dry-run/apply | `/next/paper` | admin + `shadow` or isolated smoke | `paper.ledgerRepair.*` | shadow-only | dry-run before apply、admin 403、rollback trace | `blocked_contract_needed` |
| FNX-ACT-019 | strategy tracking 筛选/详情 | `/next/strategy-tracking` | authenticated | `strategyTracking.getItems`、`getDetail` | exact/format-only | query param hash、detail fixture | `gap_open` |
| FNX-ACT-020 | strategy review 写入 | `/next/strategy-tracking` | authenticated + `shadow` | `strategyTracking.review.*` | shadow-only | no-write trace、safe write contract | `blocked_contract_needed` |
| FNX-ACT-021 | trade journal CRUD | `/next/strategy-tracking` | authenticated + `shadow` | `strategyTracking.tradeJournal.*` | shadow-only | no-write trace、rollback contract | `blocked_contract_needed` |
| FNX-ACT-022 | backtest create/cancel | `/next/backtest` | authenticated + `shadow` | `backtest.createRun`、`backtest.cancelRun` | shadow-only | task state fixture、test run marker、no fake success | `shadow-only` |
| FNX-ACT-023 | backtest detail/equity/trades | `/next/backtest` | authenticated | `backtest.getRunDetail/equity/trades` | exact/tolerance | run hash、downsample endpoint check | `gap_open` |
| FNX-ACT-024 | data health/coverage/worker 读取 | `/next/data` | admin | `dataConsole.get*` | exact | admin guard、payload hash、403 fallback | `gap_open` |
| FNX-ACT-025 | data tasks submit/cancel | `/next/data` | admin + `shadow` or isolated smoke | `dataConsole.tasks.*` | shadow-only | ConfirmAction、task trace、rollback contract | `blocked_contract_needed` |
| FNX-ACT-026 | data repair dry-run/apply | `/next/data` | admin + `shadow` or isolated smoke | `dataConsole.repair.*` | shadow-only | dry-run before apply、audit echo、rollback contract | `blocked_contract_needed` |
| FNX-ACT-027 | settings section save | `/next/settings` | authenticated/admin by section + `shadow` | `settings.saveSection` | shadow-only/exact echo | validation、save echo、403 fixture | `gap_open` |
| FNX-ACT-028 | feature flag update | `/next/settings` | admin + `shadow` or `live_smoke_operator` | `settings.featureFlags.*` | shadow-only | no-write trace、audit echo、rollback trace | `blocked_contract_needed` |
| FNX-ACT-029 | operation audit/latest refresh | `/next/settings` | admin | `settings.getAudit`、`settings.refreshLatestData` | exact/shadow-only | admin guard、audit payload hash | `blocked_contract_needed` |

## 403 与降级要求

| 场景 | 展示要求 | 可用替代路径 | 验收证据 |
|---|---|---|---|
| anonymous 打开 `/next/*` | 会话要求和登录入口 | 登录页 | route guard E2E |
| 无 `can_paper_trade` 打开委托 | 模拟盘白名单提示 | 只读账户/持仓或返回 monitor | paper guard E2E |
| 非 admin 打开 `/next/data` | 权限不足说明 | 返回 monitor/market 只读状态 | data admin 403 fixture |
| 非 admin 打开 settings admin tab | 隐藏 admin 操作并说明原因 | 普通 settings tabs | settings 403 fixture |
| 缺安全写 API | 显示 `blocked_contract_needed` 或 shadow-only 状态 | shadow 记录、契约需求 | no-write trace、blocked reason |
| live-smoke 未授权 | 显示写入模式不足 | shadow 模式 | mode guard E2E |

## 权限证据字段

每个危险操作进入完成状态前必须记录：

| 字段 | 说明 |
|---|---|
| `role_fixture` | anonymous、authenticated_observer、`can_paper_trade`、admin、live_smoke_operator |
| `write_mode` | `shadow`、`isolated-live-smoke` 或 `live`；本阶段不得使用真实 live |
| `request_trace` | 是否发出真实写请求；shadow 下必须证明未发 live 写 |
| `audit_echo` | admin 或 live-smoke 操作的审计回显 |
| `rollback_trace` | live-smoke create/apply 后的 cancel/rollback/reset 证明 |
| `blocked_reason` | 缺契约时写明缺哪一个 API、隔离数据或回滚路径 |
| `fallback_ui` | 403、blocked、shadow-only 的实际 UI 截图 |

## 当前不可越过的权限边界

1. `anonymous` 不得进入 `/next/*` 业务页。
2. 未具备 `can_paper_trade` 不得打开或提交模拟委托。
3. 非 admin 不得执行数据任务、repair apply、feature flag 更新或 admin settings。
4. `near_entry`、research-only、paper/shadow、机甲 display/review 不得进入生产排序或生产收益排行。
5. 缺安全写 API、隔离账号、测试 run 标记或回滚路径时，状态必须保持 `blocked_contract_needed`。
6. 本阶段不允许真实 live 写入、部署或切流。

## 2026-06-06 最新权限硬化证据

说明：上方主矩阵保留初版审计行；本节为当前最新状态，覆盖初版中已过期的 `gap_open` 判断。

| 范围 | 最新状态 | 证据 |
|---|---|---|
| `/next/*` route guard | `ready_for_cutover_review` | anonymous 访问业务页跳转登录；`app-shell-auth.spec.ts` PASS。 |
| `/next/data` admin guard | `ready_for_cutover_review` | 路由级 `AuthGuard + AdminGuard`；非 admin E2E 显示“管理员权限不足”；admin fixture 业务页 E2E PASS。 |
| `/next/paper` paper guard | `ready_for_cutover_review` | 路由级 `PaperGuard` 检查 `can_paper_trade`；无权限 E2E 显示“模拟盘权限不足”。 |
| `/next/settings` admin-only tabs | `ready_for_cutover_review` | 非 admin 隐藏 `开关/治理/Audit` 和“功能开关写入”；相关 query enabled 受 `auth.isAdmin()` 限制。 |
| mutation write mode guard | `ready_for_cutover_review` | `createMutationClient` 硬检查 `writeEnabled`、`writeMode`、contract status、`requiresAdmin`；`mutations.test.ts` 6 tests PASS。 |
| shadow-only / blocked writes | `shadow-only` / `blocked_contract_needed` | 默认 `shadow` 不发 live-smoke；缺契约操作继续返回 shadow/blocked message；E2E no-write trace 仍 PASS。 |
| request/SSE permission side effect | `ready_for_cutover_review` | `START_LEGACY_FRONTEND=1 npm run request:trace` PASS；9 个新路由请求数低于旧前端，EventSource 全为 0。 |

仍需保持 open 的权限/写入项：

| 项 | 状态 | 原因 |
|---|---|---|
| strategy review/trade journal 真实写 | `blocked_contract_needed` | 缺安全写契约、隔离数据和回滚路径。 |
| data repair/backfill/task 真实写 | `blocked_contract_needed` | 缺 dry-run/apply/cancel 契约和回滚证据。 |
| settings 非 feature-flag 写入 | `blocked_contract_needed` | 缺分区保存、回显、回滚契约。 |
| paper pause/resume/reconcile | `blocked_contract_needed` | 会影响模拟账户状态，需隔离账号和 rollback。 |
| backtest cancel/validate/optimize | `blocked_contract_needed` | 会影响任务状态，需测试 run 标记和回滚/取消证明。 |
| feature flag live-smoke | `shadow-only` until authorized | 需要用户单独授权、admin token、审计回显和回滚证明。 |

## 2026-06-06 Client Telemetry 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| mutation 权限诊断 | `ready_for_cutover_review` | 前端内存 telemetry 记录 `shadow-only`、`blocked_contract_needed`、`write-disabled`、`mode-blocked`、`permission-blocked`、`sent`，只包含 action、mode、contract status、requiresAdmin 等 guard 结果。 |
| 敏感信息保护 | `ready_for_cutover_review` | telemetry meta 自动脱敏 token、secret、password、authorization、cookie、credential 等 key；不记录 mutation payload、请求 body、auth token。 |
| 写入边界 | `shadow-only` / `blocked_contract_needed` | telemetry 只证明前端 guard 结果，不改变请求发送规则；缺契约动作仍保持 shadow/blocked，live-smoke 仍需单独授权和 rollback 证据。 |
| 运行时可见性 | `ready_for_cutover_review` | `window.__FRONTEND_NEXT_TELEMETRY__()` 仅暴露浏览器内存快照，`perf:compare` 读取后写入本地报告；不发送后端、不创建生产审计记录。 |

本节不新增任何角色、权限或写入能力；仅用于 cutover 前本地诊断和验收证据采集。

## 2026-06-06 兼容跳转权限与上下文证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| `/next/*` compatibility routes | `ready_for_cutover_review` | `/next/emotion`、`/next/low-buy`、`/next/strategy`、`/next/performance` 仍运行在 AppShell/AuthGuard 下，并在跳转时保留 query/search；`app-shell-auth.spec.ts` 覆盖带 `symbol/source` 的兼容跳转。 |

该补充不新增任何匿名访问、paper、admin 或 live-smoke 权限；只是确保已授权用户从兼容入口进入目标页时不会丢失上下文参数。

## 2026-06-06 策略命令跳转权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| Command Palette strategy navigation | `ready_for_cutover_review` | 策略命令仍要求 `/next/*` authenticated shell；`首板` 只跳转 `/next/playbook?strategy=first_board`，`N形` 只跳转 `/next/strategy-tracking?strategy_key=n_pattern_long_wash`；`app-shell-auth.spec.ts` 覆盖两类策略跳转。 |
| Strategy query normalization | `ready_for_cutover_review` | `strategy` 和 `strategy_key` 只接受有限 ASCII route key，中文标签或空值回落，不作为写入 payload 或生产策略判断输入。 |

该补充不新增匿名、paper、admin、live-smoke 或任何写权限；策略跳转只改变前端路由 search，用于展示筛选和页面上下文。

## 2026-06-06 AppShell 登录与用户菜单权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| Login redirect restore | `ready_for_cutover_review` | 匿名用户访问业务深链路仍先进入 `/login`；登录成功后仅允许回到白名单 `/next/*`，外链和非业务路径回落 `/next/monitor`。 |
| User menu | `ready_for_cutover_review` | 账户菜单只在 authenticated 状态显示，支持进入 `/next/settings` 和退出登录；不暴露 admin/paper/live-smoke 权限。 |
| Editable shortcut guard | `ready_for_cutover_review` | input/textarea/select/contenteditable 内的 `Cmd/Ctrl+K` 与 `Cmd/Ctrl+1~8` 不触发全局路由动作，避免表单编辑时绕过当前页面上下文。 |

该补充不新增任何写权限、角色权限或后端契约；仅收紧新前端登录态导航和输入态误触边界。

## 2026-06-06 Command Palette 焦点权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| Command Palette focus trap | `ready_for_cutover_review` | Command Palette 仍只在 authenticated AppShell 内打开；焦点限制在弹层内部，Esc 关闭后回到触发按钮；E2E 覆盖焦点循环和恢复。 |

该补充不新增任何匿名访问、paper、admin、live-smoke 或写权限；只收敛已授权用户的键盘操作边界。

## 2026-06-06 Command Palette Shared UI Wrapper 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| Command Palette wrapper | `ready_for_cutover_review` | `shared/ui/CommandPalette.tsx` 只负责弹层 UI 和键盘焦点，业务命令仍在 authenticated AppShell feature 内生成；`app-shell-auth.spec.ts` 继续覆盖匿名 guard、策略跳转、股票代码跳转和权限负例。 |

该补充不新增任何匿名访问、paper、admin、live-smoke 或写权限；只把已授权用户可见的 Command Palette UI 收敛到 shared wrapper。

## 2026-06-06 Paper 委托表单权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| `/next/paper` order form | `shadow-only` | 委托表单新增导入推荐、持仓导入、数量快捷和费用估算，但仍运行在 `PaperGuard` 后；提交继续走 `mutationClient.createPaperOrder`，默认 `shadow` 下不发真实写请求。 |

该补充不新增匿名、admin、live-smoke 或真实写权限；只提升已有 `can_paper_trade` 用户在 shadow 模式下的草稿编辑体验。

## 2026-06-06 Analysis To Paper Handoff 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| `/next/analysis` 打开模拟委托 | `ready_for_cutover_review` | 分析页只生成 `/next/paper?source=analysis...` 前端草稿参数；目标页仍经过 `AuthGuard + PaperGuard`，没有 `can_paper_trade` 时不会进入委托表单。 |
| `/next/paper` 接收分析草稿 | `shadow-only` | 仅 `source=analysis` search 自动打开一次 shadow 委托弹窗；提交仍由 mutation write mode guard 控制，默认不发真实请求。 |

该补充不新增匿名、admin、live-smoke、真实写入或绕过 `can_paper_trade` 的能力；只允许已授权用户把分析结果带入模拟盘 shadow 草稿。

## 2026-06-06 Symbol Analysis Navigation 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| 股票代码进入分析 | `ready_for_cutover_review` | Command Palette、Monitor、Playbook 都只在 authenticated shell 内跳转 `/next/analysis?symbol=...`；Analysis 只把 symbol 填入表单，不自动提交。 |
| Monitor/Playbook 返回上下文 | `ready_for_cutover_review` | 选中 symbol 只写入当前页 search，用于浏览器返回和页面上下文恢复，不作为写入 payload 或生产排序输入。 |

该补充不新增匿名访问、paper、admin、live-smoke 或写权限；只改善已授权用户的只读页面跳转和表单预填。

## 2026-06-06 Shadow Action Draft Refresh 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| ShadowActionPanel 草稿同步 | `ready_for_cutover_review` | 父级字段变化会清除旧二次确认并重置草稿；用户必须在当前上下文重新确认。 |
| 写入边界 | `shadow-only` / `blocked_contract_needed` | 修复不改变任何 mutation mode guard；缺安全契约的动作仍不发真实请求。 |

该补充不新增任何角色、权限、admin/live-smoke 能力或真实写入；只降低 shadow 表单旧上下文误提交风险。

## 2026-06-06 Analysis Batch Worker Sort 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| `/next/analysis` batch display sort | `ready_for_cutover_review` | worker `sort` 只处理已返回的展示行数组，不接收 auth token、请求 body、生产榜 payload 或 mutation payload。 |
| 写入边界 | `shadow-only` / no-write | 批量排序不会触发任何 POST/PUT/PATCH/DELETE；`analysis-playbook.spec.ts` 仍只观察到 `POST /api/analyze` 和 `POST /api/analyze/batch` 两个分析接口。 |

该补充不新增匿名、paper、admin、live-smoke 或真实写权限；只提升已授权用户在分析页的本地展示排序能力。

## 2026-06-06 Backtest Workflow Tabs 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| `/next/backtest` submit/research tabs | `shadow-only` | `回测提交`、`回测任务控制`、`验证与优化` 都继续走 `ShadowActionPanel` 二次确认；默认 mutation guard 不发真实写请求。 |
| ETF T0 research | `blocked_contract_needed` | ETF T0 页签只展示研究入口和边界说明，不调用 minute backtest、validate、optimize 或 promote 写接口。 |

该补充不新增匿名、admin、live-smoke 或真实写权限；只把已有回测 shadow 操作收敛到批准的页签工作流。

## 2026-06-06 Settings MFA Shadow Management 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| `/next/settings` MFA 状态 | `ready_for_cutover_review` | 账户与安全分区只展示当前用户 TOTP 状态和安全边界，不展示 secret、二维码或恢复码。 |
| MFA setup/disable UI | `shadow-only` / `blocked_contract_needed` | `MFA 管理` 只允许已认证用户记录本地 shadow 意图；真实 setup/enable/disable 仍被安全契约阻断。 |
| 写入权限 | no live write | E2E 仅验证二次确认和本地 shadow 结果，未新增匿名、admin、paper、live-smoke 或真实账号写权限。 |

该补充不新增任何角色、权限、admin/live-smoke 能力或真实写入；只提升已授权用户对账户安全状态的可见性。

## 2026-06-06 Settings Section Shadow Management 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| 风控/LLM 配置写入 | `blocked_contract_needed` | `配置写入` 走 mutation guard，缺安全契约时只显示 blocked 结果，不发送 PUT `/api/settings`。 |
| 行业排除/因子权重写入 | `blocked_contract_needed` | `行业排除管理`、`因子权重管理` 使用 generated typed payload，但真实写入被 contract status 阻断。 |
| 量化参数/策略治理写入 | `blocked_contract_needed` | 当前仅记录 shadow 意图，等待安全契约、权限 gate、审计回显和回滚证据。 |
| 写入权限 | no live write | E2E 覆盖新增管理入口后 `POST/PUT/PATCH/DELETE /api/*` 写请求数组仍为空。 |

该补充不新增任何 admin/live-smoke 能力或真实写入；只让已授权用户看见设置项可管理入口和当前阻断原因。

## 2026-06-06 Shadow Submit And Menu Layer Stability 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| ShadowActionPanel 提交 | `shadow-only` / `blocked_contract_needed` | 提交中防重复和失败恢复只约束本地 intent 状态；真实写入仍由 mutation client 的 `writeEnabled`、`writeMode`、contract status 和 admin gate 决定。 |
| AppShell 用户菜单 | `ready_for_cutover_review` | 层级修复只影响已认证用户菜单可点击性；不新增匿名访问、admin、paper、live-smoke 或真实写权限。 |
| `/next/data`、`/next/settings` no-write E2E | no live write | 最新 interaction parity 覆盖当前分区导航后，`POST/PUT/PATCH/DELETE /api/*` 写请求数组仍为空。 |

该补充不新增任何角色、权限、admin/live-smoke 能力或真实写入；只降低 shadow intent 重复提交和菜单遮挡风险。

## 2026-06-06 Auth Refresh Recovery 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| authenticated read requests | `ready_for_cutover_review` | 读请求 401 只使用本地 refresh token 恢复同一用户会话，不提升角色或绕过 route guard。 |
| writes/mutations | no automatic replay | 写请求 401 不自动 refresh+retry；真实写入仍需显式用户动作、mutation guard、权限 gate、契约状态和二次确认。 |
| token handling | no secret exposure | telemetry 只记录 `/api/auth/refresh` 脱敏路径和状态，不记录 token、cookie、body、secret。 |

该补充不新增任何角色、权限、admin/live-smoke 能力或真实写入；只提升已认证读链路的过期恢复能力。

## 2026-06-06 Error Boundary And Telemetry Redaction 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| 页面错误 fallback | no secret exposure | `AppErrorBoundary` 只展示脱敏后的错误 message；不会把 token、authorization、secret、password、cookie 原样渲染。 |
| telemetry diagnostic snapshot | no secret exposure | 敏感 meta key 直接 redacted；普通字符串值也会扫描并替换敏感片段。 |
| chart error telemetry | no secret exposure | K 线错误事件只记录脱敏后的 error 字符串。 |

该补充不新增任何角色、权限、admin/live-smoke 能力或真实写入；只降低新前端本地错误展示和诊断日志的信息泄露风险。

## 2026-06-06 Route Level Error Boundary 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| `/next/*` route fallback | no permission escalation | 页面异常 fallback 不绕过 `AuthGuard`、`PaperGuard` 或 `AdminGuard`；只在已允许进入的页面内容区生效。 |
| shell navigation | no new write access | 页面异常后用户只能使用既有导航离开失败页，不新增 admin、paper、live-smoke 或真实写权限。 |
| sensitive details | no secret exposure | route fallback 错误 message 复用 shared redaction，不显示 token、authorization、password 原值。 |

该补充不新增任何角色、权限、admin/live-smoke 能力或真实写入；只提升新前端 route-level 失败恢复能力。

## 2026-06-06 Paper Mecha Reduced Motion 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| `/next/paper` mecha particles | no permission escalation | reduced-motion 监听只控制本地 Canvas 粒子是否运行；不读取 token、不调用 API、不触发 mutation。 |
| paper display/review | no production impact | 机甲头像、HUD、粒子和日志仍只作为模拟盘 display/review，不参与生产排序、信号计算、模拟委托判断。 |
| resource lifecycle | ready_for_cutover_review | 运行时开启 reduced motion 会取消 RAF、移除 resize listener；组件卸载路径继续清理资源。 |

该补充不新增任何角色、权限、admin/live-smoke 能力或真实写入；只提升 `/next/paper` display/review 动效的可访问性和资源释放能力。

## 2026-06-06 SSE Reconnect Stability 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| quote SSE reconnect | no permission escalation | 重连复用同一 URL 和 `withCredentials` 连接参数；不新增 token 读取、不绕过 AuthGuard、不创建写请求。 |
| live quote signals | no production impact | SSE 只更新 `liveQuoteSignals` 展示层字段，不改变生产优先榜顺序、`production_score` 或策略判断。 |
| resource lifecycle | ready_for_cutover_review | cleanup 会取消 pending reconnect timer，防止离页后后台重连或重复 EventSource。 |

该补充不新增任何角色、权限、admin/live-smoke 能力或真实写入；只提升新前端实时展示连接的恢复与释放能力。

## 2026-06-06 User-Facing Error Message Redaction 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| 页面错误文案 | no secret exposure | `shared/api/errorMessage` 在返回给 Login、QueryState、Analysis、Playbook、ShadowActionPanel 和 Paper order 前统一脱敏敏感片段。 |
| Shadow/action errors | no permission escalation | 错误脱敏只影响本地结果文案，不改变 mutation guard、admin gate、paper guard、live-smoke gate 或 contract status。 |
| Token handling | no secret exposure | 单测覆盖 Authorization/Bearer、access_token、refresh_token、password、cookie 原值不会进入用户可见文本。 |

该补充不新增任何角色、权限、admin/live-smoke 能力或真实写入；只降低新前端页面错误文案泄露凭据的风险。

## 2026-06-06 Worker Error Redaction 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| Worker failure response | no secret exposure | `compute.worker.ts` 异常响应通过 shared redaction 处理，不返回原始 token/password。 |
| Worker telemetry | no secret exposure | `workerClient.ts` 只记录脱敏后的 `meta.error`，不记录 worker payload、请求 body 或账号凭据。 |
| Worker permissions | no permission escalation | Worker 仍只做显示层纯计算，不能绕过 AuthGuard、PaperGuard、AdminGuard 或 mutation guard。 |

该补充不新增任何角色、权限、admin/live-smoke 能力或真实写入；只降低 Worker crash/fallback 诊断泄露凭据的风险。

## 2026-06-06 Worker PostMessage Fallback 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| Worker postMessage fallback | no permission escalation | `postMessage` 抛错后只回退同步显示层计算，不触发 API、mutation 或权限绕过。 |
| Worker telemetry | no secret exposure | `postmessage-fallback` 只记录脱敏错误，不记录 payload、请求 body 或账号凭据。 |
| Resource cleanup | ready_for_cutover_review | listener/timeout 在 `postMessage` 抛错路径被清理，不保留跨路由监听器。 |

该补充不新增任何角色、权限、admin/live-smoke 能力或真实写入；只降低 Worker postMessage 失败后的挂起、泄露和诊断暴露风险。

## 2026-06-06 Safe Write Contract 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| 安全写契约 registry | `ready_for_cutover_review` for contract definition | `safeWriteContracts.ts` 为所有 guarded non-ready writes 提供稳定 `FNX-SW-*` id、角色、模式、guard、request/response、audit、rollback 和 evidence 要求。 |
| Mutation guard 输出 | `shadow-only` / `blocked_contract_needed` | `MutationResult.safeWriteContract` 返回契约摘要；blocked message 带 contract id，用户不会误解为写入成功。 |
| 非 ready 写操作覆盖 | `ready_for_cutover_review` for coverage | `operations.test.ts` 验证每个非 ready 写 operation 都映射到安全写契约，避免后续新增危险写漏登记。 |
| 真实写权限 | no new live access | 本补充没有把任何 `blocked_contract_needed` operation 改为可发送；`shadow`、`blocked_contract_needed`、`requiresAdmin`、`isolated-live-smoke` guard 仍按原逻辑阻断。 |

当前安全写 open 项状态更新：

| 项 | 最新状态 | 原因 |
|---|---|---|
| strategy review/trade journal 真实写 | `contract_defined_backend_needed` | 已有 `FNX-SW-STRATEGY-REVIEW`、`FNX-SW-TRADE-JOURNAL`；仍缺后端 CRUD、隔离数据和 rollback smoke。 |
| data repair/backfill/task 真实写 | `contract_defined_backend_needed` | 已有 `FNX-SW-DATA-TASK`、`FNX-SW-DATA-REPAIR`；仍缺 dry-run/apply/cancel/rollback 后端证据。 |
| settings 非 feature-flag 写入 | `contract_defined_backend_needed` | 已有 `FNX-SW-SETTINGS-SECTION`；仍缺 section version、save echo 和 restore previous version。 |
| paper pause/resume/reconcile | `contract_defined_backend_needed` | 已有 `FNX-SW-PAPER-ACCOUNT`；仍缺隔离模拟盘账号和账户状态回滚证据。 |
| backtest cancel/validate/optimize | `contract_defined_backend_needed` | 已有 `FNX-SW-BACKTEST-TASK`；仍缺测试 run/task 标记和 cancel/delete 证据。 |
| feature flag live-smoke | `contract_defined_isolated_live_smoke` | 已有 `FNX-SW-FEATURE-FLAG`；仍需用户单独授权、admin token、审计回显和 restore 证据。 |

该补充只定义权限与写入契约，不新增匿名、paper、admin、live-smoke 或真实写权限，不改变后端、旧前端、生产排序、策略语义、`priority_board` 或 `production_score`。

## 2026-06-06 Safe Write Request Evidence 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| Live-smoke 请求证据 | `ready_for_cutover_review` for frontend evidence | 允许发送的 live-smoke mutation 会附加 `X-Frontend-Next-Client-Request-Id`、`X-Frontend-Next-Contract-Id`、`X-Frontend-Next-Operation`、`X-Frontend-Next-Write-Mode` 等 header。 |
| Guarded blocked writes | no permission escalation | `shadow-only`、`blocked_contract_needed`、`write-disabled`、`mode-blocked`、`permission-blocked` 分支不生成 live request id，不调用 requester，不附加写请求 header。 |
| Admin/live-smoke 权限 | no new live access | header 生成发生在权限 gate 之后；没有把任何非 admin、非 isolated-live-smoke、非可发送 operation 提升为真实写。 |
| 诊断隐私 | no secret exposure | header 和 telemetry 只含 contract id、operation、write mode、client request id，不含 token、password、secret、cookie 或 payload。 |

该补充只提升前端侧 isolated live-smoke 审计可追踪性，不新增角色、权限、admin/live-smoke 能力或真实写入，不改变后端、旧前端、生产排序、策略语义、`priority_board` 或 `production_score`。

## 2026-06-06 Local Isolated Write Rollback Smoke 权限证据补充

| 范围 | 最新状态 | 证据 |
|---|---|---|
| 本地临时账号 | isolated local only | `write:rollback` 只在本地 sqlite 下创建 `frontend_next_smoke_*` 临时用户；脚本 cleanup 删除本次用户、session、paper account 和本次 backtest run。 |
| Paper live-smoke | completed local isolated smoke | `FNX-SW-PAPER-ORDER` 通过 create+reset，写请求带 `X-Frontend-Next-*` header 和 `client_request_id`。 |
| Feature flag live-smoke | completed local isolated smoke | `FNX-SW-FEATURE-FLAG` 选择低风险 UI 开关 `playbook_lazy_load_enabled`，toggle 后 restore，最终值恢复为 true。 |
| Backtest live-smoke | completed local isolated smoke | `FNX-SW-BACKTEST-TASK` 通过 create+delete，run rollback 状态为 `deleted`。 |
| 正式权限边界 | still gated | 该 smoke 不授权正式环境写入、不授权 cutover；正式验收账号仍需单独复跑。 |

该补充只证明本地 sqlite 隔离环境的可回滚写链路，不新增生产角色、权限或自动写入，不改变后端代码、旧前端、生产排序、策略语义、`priority_board` 或 `production_score`。
