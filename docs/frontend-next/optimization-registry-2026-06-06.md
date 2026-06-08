# Frontend Next Optimization Registry - 2026-06-06

状态：旧实现优化登记初版，未部署，未切流
适用范围：`frontend-next/` 在补齐旧 `frontend/` P0/P1 能力时允许采用的易用性、可用性、稳定性优化
最后核验日期：2026-06-06

## 结论

本登记表只记录允许优化的方向和验收证据要求，不授权改变生产口径。所有优化必须保持旧前端可完成的用户能力、API 字段口径、权限边界、feature flag、研究/生产/模拟盘边界不变。缺安全写 API 的优化只能停留在 `shadow-only` 或 `blocked_contract_needed`。

## 工作边界

1. 不为了优化修改旧 `frontend/` 生产代码。
2. 不为了优化修改后端；缺契约时形成后端契约需求。
3. 不改变 `priority_board`、`production_score`、策略语义、研究/生产边界。
4. Worker 只做显示层 sort/filter/derive/downsample，不参与生产策略判断。
5. 机甲、动效、日志只用于 `/next/paper` display/review，不影响信号或排序。

## 状态词典

| 状态 | 含义 |
|---|---|
| `planned` | 可按登记方向实现，尚无代码和验收证据 |
| `evidence_needed` | 方向合理，但必须补测试、截图、request trace 或 perf 证据 |
| `shadow-only` | 只能在 shadow/no-write 模式验证 |
| `blocked_contract_needed` | 缺安全写契约、隔离数据或回滚路径 |

## 优化登记矩阵

| ID | 范围 | 旧实现问题 | 新前端优化方案 | 易用性收益 | 可用性收益 | 稳定性收益 | 保持不变口径 | 验收证据 | 当前状态 |
|---|---|---|---|---|---|---|---|---|---|
| FNX-OPT-001 | Auth/工作台 | 登录、刷新、退出、MFA 和权限提示分散，刷新恢复链路不适合作为新前端复用壳 | 集中到 `features/auth`、`shared/api/auth`、route guard 和 UserMenu | 用户刷新页面不丢失会话，权限不足有明确下一步 | 401/403 可恢复，不白屏 | auth adapter 统一 token、refresh、脱敏 | 权限判定和后端身份字段不改 | auth E2E、401 refresh、403 fallback、MFA fixture | `planned` |
| FNX-OPT-002 | AppShell/导航 | 高频页面跳转和股票分析入口分散 | Command Palette、快捷键、移动抽屉和兼容跳转统一 | 降低跳转和查找成本 | 移动端不依赖桌面侧边栏 | route-level error boundary 防止壳体被单页拖垮 | 路由目标和 query 语义不改 | Command Palette E2E、redirect query test、390x844 截图 | `planned` |
| FNX-OPT-003 | API/Query | 页面直接依赖零散 URL 或临时字段会扩大漂移风险 | OpenAPI generated types + operation adapters + feature query keys | 页面开发不重复猜字段 | stale time 和 invalidate 按 feature 管理 | 请求取消、超时和 schema mismatch 可定位 | 后端字段、snake_case、收益/评分口径不改 | `api:check`、operation tests、payload hash | `planned` |
| FNX-OPT-004 | Mutation | 旧写入流确认、提交、失败、回滚分散 | 统一状态机：validating、confirming、submitting、success、failed、rollback | 用户能看懂提交状态和失败恢复 | 防重复提交，危险操作统一确认 | live-smoke 可进入 rollback_needed，不伪造成功 | 写入权限、审计、feature flag 边界不改 | mutation lifecycle tests、no-write trace、rollback smoke | `shadow-only` |
| FNX-OPT-005 | Shared UI | 表格、抽屉、确认、空态在页面内重复实现 | `DataTable`、`VirtualCardList`、`Modal`、`Drawer`、`ConfirmAction` wrapper | 交互一致，学习成本低 | 长列表和大表不拖慢页面 | focus trap、Esc、焦点回归、禁用态统一 | 展示字段和业务动作不改 | component tests、a11y checks、截图 parity | `planned` |
| FNX-OPT-006 | Monitor | 生产优先榜和行情更新容易被前端派生逻辑误改 | 生产榜只按后端顺序展示，行情只更新 leaf cell | 用户看到的行动顺序稳定可信 | 新入榜/价格变化可读但不重排 | 防止 tick 导致整页刷新或重复 SSE | `priority_board`、`production_score` 完全不改 | order hash、request/SSE trace、leaf update trace | `evidence_needed` |
| FNX-OPT-007 | Monitor actions | 持仓、自选、观察池编辑入口散落，状态反馈不统一 | drawer + ConfirmAction + shadow/live-smoke mode gate | 在当前上下文完成编辑 | 禁用态、错误态、失败保留输入 | 写入不安全时停在 shadow/blocked | 自选/观察/生产边界不改 | no-write trace、shadow record、live-smoke rollback | `shadow-only` |
| FNX-OPT-008 | Market | 市场图表和运行态面板容易在切页后残留资源 | 可见时初始化图表，切页 dispose；runtime/data quality 独立降级 | 市场状态更易扫读 | 避免不可见图表继续耗资源 | dispose telemetry 证明释放 | 市场总闸、宽度、ETF 口径不改 | chart init/update/dispose timing、market payload hash | `evidence_needed` |
| FNX-OPT-009 | Analysis | 单票、批量、关键位、异常、K 线和模拟委托联动路径割裂 | 单页 screen model + Kline adapter + 批量 Worker fallback + paper handoff | 分析后可直接进入下一步操作 | 非法输入、API 错误、空态明确 | K 线输入变化不重建整页，Worker crash 有 sync fallback | 分析结论、关键位、排序规则不改 | invalid/error fixtures、worker hash、Kline dispose、截图 parity | `planned` |
| FNX-OPT-010 | Playbook | 候选展示与实时报价刷新容易造成整页重渲染，`near_entry` 容易被误读 | 候选分层、leaf quote refresh、`near_entry` watch-only guard | 候选状态更清楚 | 刷新只更新叶子字段 | research-only/near-entry guard 防止越界 | 生产/观察策略和收益口径不改 | research-only guard、near-entry guard、render trace | `planned` |
| FNX-OPT-011 | Paper order | 委托、数量快捷、费用估算、权限、确认和失败恢复复杂 | 统一委托弹窗和表单 validator，默认 shadow，live-smoke 隔离 | 下单模拟路径更少跳转 | can_paper_trade、提交中禁用、失败保留输入 | 缺 reset/rollback API 时不进 live-smoke | 真实交易仍禁止，模拟盘不影响生产信号 | guard E2E、no-write trace、rollback evidence | `blocked_contract_needed` |
| FNX-OPT-012 | Paper display/review | 机甲 display/review 容易被误解为策略信号 | 机甲仅挂在 paper HUD 和日志 review 区，标记 display-only | 提升复盘可读性 | reduced motion 保证不干扰读数 | Canvas/粒子切页释放 | 不参与生产排序、信号、委托判断 | display-only guard、reduced-motion screenshot、resource dispose | `evidence_needed` |
| FNX-OPT-013 | Strategy tracking | 筛选、详情、复盘中心、日志 CRUD 复杂且页面状态易丢 | 虚拟表格 + 筛选抽屉 + 详情抽屉 + review center screen model | 筛选和详情不打断列表上下文 | 分页/筛选可回退，空态清楚 | 复盘写入缺安全 API 时显示真实阻塞 | 策略状态、表现、复盘口径不改 | filter query hash、detail fixture、review no-write trace | `blocked_contract_needed` |
| FNX-OPT-014 | Backtest | 大图表、任务状态、提交/取消容易出现假成功或卡顿 | downsample adapter、任务状态 truth table、submit/cancel guarded mutation | 研究结果更清楚 | 长序列不卡顿，任务失败可见 | 图表释放、状态不伪造成功 | 回测指标、OOS、收益口径不改 | downsample endpoint check、task state fixture、E2E | `shadow-only` |
| FNX-OPT-015 | Data console | 管理任务、repair apply、token 操作风险高 | admin guard + dry-run 前置 + ConfirmAction + audit echo | 运维操作影响范围可见 | 非 admin 只读替代路径 | 危险操作不能绕过 dry-run/确认 | 数据门禁、覆盖率、任务状态不改 | admin 403 fixture、dry-run/apply trace、audit echo | `blocked_contract_needed` |
| FNX-OPT-016 | Settings | 设置项多且保存回显、审计和权限边界容易混乱 | 按 section 管理 validator、save、echo、audit；admin tabs guard | 用户只看到可操作项 | 保存失败保留输入，成功回显真实后端 | feature flag live-smoke 可回滚 | 风控、行业、因子、量化参数口径不改 | validation tests、save echo、feature flag rollback | `blocked_contract_needed` |
| FNX-OPT-017 | 异常恢复 | 错误态散落，网络断开、429、Worker crash、SSE 断连不统一 | 异常矩阵 + route error boundary + offline banner + backoff + fallback | 用户知道失败原因和下一步 | 热数据保留旧缓存，可重试 | 不重复 EventSource，Worker crash 不拖垮页面 | 数据口径和缓存真源不改 | exception fixtures、request trace、telemetry | `planned` |
| FNX-OPT-018 | 响应式/a11y | 大表和图表在移动端、键盘、红绿状态上易不可用 | 四档截图、移动卡片降级、focus trap、非颜色状态标识、reduced motion | 移动端和键盘用户可完成核心任务 | 关键字段不被横向滚动遮挡 | 动效不造成 CPU 持续占用 | 视觉风格、密度、中文文案语气不改 | 1440/1280/768/390 截图、component a11y checks | `planned` |

## 优化项完成定义

每个优化项进入完成状态前必须同时满足：

1. 能反查到旧实现问题。
2. 写明新前端优化方案和用户收益。
3. 写明保持不变的业务口径。
4. 提供至少一种功能证据和一种非功能证据：测试、截图、request trace、error recovery 或 perf compare。
5. 写入能力若缺安全契约，状态只能是 `shadow-only` 或 `blocked_contract_needed`。

## 当前阻塞摘要

| 阻塞 | 影响范围 | 当前处理 |
|---|---|---|
| 缺 strategy review/trade journal 安全写 API | `/next/strategy-tracking` 复盘中心、交易日志 | `blocked_contract_needed`，只允许 shadow 记录 |
| 缺 data job/repair 可回滚测试路径 | `/next/data` 数据任务和 repair apply | `blocked_contract_needed`，必须 dry-run + contract request |
| 缺 feature flag live-smoke 隔离审计路径 | `/next/settings` feature flags | `blocked_contract_needed`，默认 shadow |
| 缺 paper order live-smoke 隔离账户 reset/rollback 证明 | `/next/paper` 委托 | `blocked_contract_needed`，当前只允许 no-write/shadow |
| 缺完整字段级 parity 证据 | 所有 P0/P1 页面 | `evidence_needed`，不能进入 cutover |

## 使用限制

本文不是重设计授权，也不是 cutover 授权。优化只能服务于易用性、可用性和稳定性；任何会改变生产排序、策略判断、收益口径、权限边界或写入安全边界的改动，必须另起计划并经过用户明确授权。

## 2026-06-06 最新优化收敛证据

说明：上方优化登记矩阵保留初版状态；本节为当前最新状态和证据，覆盖已过期的 `planned/evidence_needed` 判断。

| ID | 最新状态 | 证据 |
|---|---|---|
| FNX-OPT-001 Auth/工作台 | `ready_for_cutover_review` | route guard、session restore、login/logout、MFA model、paper/admin guard 已实现；`app-shell-auth.spec.ts` PASS。正式验收账号复跑仍 open。 |
| FNX-OPT-002 AppShell/导航 | `ready_for_cutover_review` | Command Palette、快捷键、移动导航、兼容跳转 E2E PASS；离线状态条仅在断网显示。 |
| FNX-OPT-003 API/Query | `ready_for_cutover_review` | OpenAPI types、operation adapters、query keys、`api:check` PASS；API timeout/offline/429/5xx retry 和 Query retry 收敛已测。 |
| FNX-OPT-004 Mutation | `shadow-only` | mutation 状态机新增 writeMode/requiresAdmin 硬阻断；默认 shadow；live-smoke 仍需授权和回滚证据。 |
| FNX-OPT-005 Shared UI | `ready_for_cutover_review` | Button/DataGrid/VirtualList/Modal/Drawer/ShadowActionPanel 等 wrapper 使用，component tests/lint/typecheck/build PASS。 |
| FNX-OPT-006 Monitor | `ready_for_cutover_review` | `/next/monitor` shadow parity、服务端顺序展示、request trace、新旧截图和 E2E PASS；未改变 `priority_board`/`production_score`。 |
| FNX-OPT-007 Monitor actions | `shadow-only` | 观察池/持仓动作仍 no-write/shadow，E2E 证明不发真实写。 |
| FNX-OPT-008 Market | `ready_for_cutover_review` | `/next/monitor/market` shadow parity、request trace 和截图 PASS；SSE 当前未接入，EventSource 为 0。 |
| FNX-OPT-009 Analysis | `ready_for_cutover_review` | 单票/批量/K 线/关键位/异常/worker fallback 已实现，E2E 和截图 PASS。 |
| FNX-OPT-010 Playbook | `ready_for_cutover_review` | low-buy screener/priority-board/quotes/strategies/meta 已接入，422 修复后截图和 request trace PASS。 |
| FNX-OPT-011 Paper order | `shadow-only` | 模拟委托弹窗、二次确认、`can_paper_trade` guard、no-write E2E PASS；真实/isolated live-smoke 仍需隔离账号和 rollback。 |
| FNX-OPT-012 Paper display/review | `ready_for_cutover_review` | 机甲头像、Canvas 粒子、机型切换、日志在 API 503 下仍可见；只作为 paper display/review。 |
| FNX-OPT-013 Strategy tracking | `blocked_contract_needed` | 读链路 shadow parity 完成；review/trade journal 写入仍缺安全契约。 |
| FNX-OPT-014 Backtest | `shadow-only` | runs/detail/equity/trades 图表和 shadow submit E2E PASS；cancel/validate/optimize 真实写仍 blocked。 |
| FNX-OPT-015 Data console | `blocked_contract_needed` | admin guard、coverage/SLA/runtime/admin 读链路完成；repair/backfill/task 真实写仍缺契约。 |
| FNX-OPT-016 Settings | `blocked_contract_needed` | settings 读链路、admin-only tabs、feature flag guard 完成；非 feature-flag 写入仍缺契约。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | route error boundary、QueryState、offline/timeout/network/aborted 分类、Worker timeout fallback 已实现；SSE 重连仍不是 cutover blocker，因为当前 EventSource 为 0。 |
| FNX-OPT-018 响应式/a11y | `ready_for_cutover_review` | 1440x900、1280x800、768x1024、390x844 截图均 captured；E2E 27/27 PASS。 |

仍需外部确认或后端契约的优化项：视觉人工签收、正式验收账号复跑、所有 `blocked_contract_needed` 写入、cutover/部署授权、飞书通知目标。

## 2026-06-06 Query Cancellation / Resource Cleanup 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-003 API/Query | `ready_for_cutover_review` | `requestOperation` 和常用 wrapper 支持 `AbortSignal` 透传；strategy-tracking 与 playbook 均进入可取消 Query 链路；`client.test.ts` 覆盖 abort 和 wrapper signal。 |
| FNX-OPT-008 Market | `ready_for_cutover_review` | SSE client 已补 ref-count/cleanup 单测；当前页面未默认启动 SSE，最新 request trace EventSource 全为 0。 |
| FNX-OPT-009 Analysis | `ready_for_cutover_review` | 单票/批量手动请求增加 `AbortController`，重复触发或切页取消旧请求；Kline 空数据清图并有图表 cleanup 单测。 |
| FNX-OPT-010 Playbook | `ready_for_cutover_review` | Playbook 从 `createResource` 迁入 TanStack Query，low-buy 读链路均接 `signal`；最新 request trace 新前端 6 请求，旧前端 9 请求。 |
| FNX-OPT-012 Paper display/review | `ready_for_cutover_review` | PaperMechaParticles 单测覆盖 RAF/resize cleanup 和 reduced-motion no-animation；机甲仍只用于 `/next/paper` display/review。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | Toast 同 id timer 替换、Dialog 延迟 focus timer 清理、SSE 坏 JSON error、API aborted/timeout 分类均有代码或单测证据。 |
| FNX-OPT-018 响应式/a11y | `ready_for_cutover_review` | `npm run screenshot:parity` 9 页四档截图 PASS；shared wrapper tests 覆盖 focus trap、listener cleanup、toast timer。 |

最新验证：新前端 `api:check/typecheck/lint/test/build/e2e/perf:compare/screenshot:parity` 全 PASS；旧前端 `api:check/typecheck/lint/test/build` 全 PASS。仍未授权部署或 cutover。

## 2026-06-06 Client Telemetry 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-003 API/Query | `ready_for_cutover_review` | `requestJson` 记录 method、脱敏 path、status code、attempts、duration、ok/http_error/network/offline/timeout/aborted；HTTP 错误不重复计数，便于和 `request:trace` 对照。 |
| FNX-OPT-004 Mutation | `shadow-only` | mutation guard 记录 shadow/blocked/mode/permission/contract 结果，不记录 payload；缺安全写契约项仍不发真实写。 |
| FNX-OPT-008 Market | `ready_for_cutover_review` | SSE client 记录 connecting/open/error/message/parse-error/closed/shared/replace，配合 ref-count 证明同 URL 不重复连接；当前 request trace EventSource 仍为 0。 |
| FNX-OPT-009 Analysis | `ready_for_cutover_review` | Worker 和 Kline telemetry 记录 fallback、timeout、set-data、dispose 等显示层/纯计算状态；不改变分析口径。 |
| FNX-OPT-012 Paper display/review | `ready_for_cutover_review` | Chart/Canvas 相关诊断只服务资源释放和 display/review 观察；机甲仍只在 `/next/paper` 展示。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | 前端内存 telemetry 现在覆盖 API、SSE、Worker、Chart、Mutation、UI 六类，`perf:compare` 可直接导出 route 快照。 |
| FNX-OPT-018 响应式/a11y | `ready_for_cutover_review` | telemetry 不增加可见文案和页面描述，不影响四档截图 parity；只通过诊断函数读取。 |

使用限制不变：telemetry 不上报后端、不持久化、不记录敏感信息或业务 payload，不能替代人工视觉签收、正式验收账号复跑、安全写契约和 cutover 授权。

## 2026-06-06 No Fake Data / Copy Clarity 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-009 Analysis | `ready_for_cutover_review` | K 线无真实后端 bars 时返回空点集，不再使用测试样例曲线填充；新增 `analysisModel.test.ts` 覆盖有 bars/无 bars 两种路径。 |
| FNX-OPT-012 Paper display/review | `ready_for_cutover_review` | 逐股盈亏与绩效摘要中的 `unrealized_pnl` 文案由“未实现”改为“浮动盈亏”，降低和“功能未实现”的误读风险；收益字段、计算口径和排序不变。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | 空 K 线走空数据清图和页面空态，不伪造曲线；符合缺数据显式展示、不能静默成功的稳定性要求。 |

本节不改变分析结论、模拟盘收益口径或任何生产字段，仅移除测试样例数据在业务页的显示风险，并优化可见文案清晰度。

## 2026-06-06 Auth Contract Consolidation 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-001 Auth/工作台 | `ready_for_cutover_review` | Auth model 改为通过 `shared/api/auth.ts` 的 `authApi` 执行 me/login/register/refresh/logout/TOTP，feature 层不再拼 `/api/auth/*` URL。 |
| FNX-OPT-003 API/Query | `ready_for_cutover_review` | AuthUser/AuthToken/MFA 类型从 `shared/api/types.ts` 导出，继续以 OpenAPI generated types 为事实源；`typecheck` 和 auth targeted tests PASS。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | 删除未使用的 `shared/testing/fixtures.ts`，减少接口不可用时测试样例数据被误用为业务 fallback 的风险。 |

本节只收敛契约和可维护性，不改变登录、刷新、登出、MFA、paper/admin guard 的用户语义。

## 2026-06-06 Compatibility Navigation 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-002 AppShell/导航 | `ready_for_cutover_review` | 兼容入口 `/next/emotion`、`/next/low-buy`、`/next/strategy`、`/next/performance` 现在保留 query/search 后再跳转目标页，股票代码、来源、筛选等上下文不会在迁移入口丢失；`App.test.tsx`、`keyboardShortcuts.test.ts` 与 `app-shell-auth.spec.ts` 已覆盖页面跳转、快捷键和移动导航。 |

本优化提升旧入口迁移到新前端时的易用性和稳定性；业务目标路由、权限、API、生产排序和写入模式不变。

## 2026-06-06 Command Palette Strategy Navigation 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-002 AppShell/导航 | `ready_for_cutover_review` | Command Palette 已补策略命令索引和 E2E：用户可输入 `首板` 进入 `/next/playbook?strategy=first_board`，输入 `N形` 进入 `/next/strategy-tracking?strategy_key=n_pattern_long_wash`；同时保留页面跳转和 6 位股票代码进入分析。 |
| FNX-OPT-010 Playbook | `ready_for_cutover_review` | Playbook 响应 `strategy` query 并同步策略页签，非法格式回落默认策略，避免无效 key 触发错误请求。 |
| FNX-OPT-013 Strategy tracking | `ready_for_cutover_review` | Strategy Tracking 响应 `strategy_key` query 并同步筛选，不打开任何复盘/日志写入能力。 |

该优化只提升查找和跳转效率；策略 registry 不保存生产排序、评分或交易判断，不能替代后端策略元数据，也不改变 `priority_board`、`production_score` 或写入边界。

## 2026-06-06 AppShell Auth/Navigation Usability 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-001 Auth/工作台 | `ready_for_cutover_review` | 登录/注册成功后恢复 `/login?redirect=` 中的安全 `/next/*` 深链路；外链和非 next 路径回落默认行动台，避免开放跳转。 |
| FNX-OPT-002 AppShell/导航 | `ready_for_cutover_review` | 顶栏用户菜单补齐“系统设置/退出登录”；全局快捷键在 input、textarea、select、contenteditable 内不触发，避免表单输入时误跳页。 |

该优化提升易用性和稳定性，不新增业务能力或权限；退出登录仍走既有 auth adapter，页面快捷键和菜单只影响新前端 shadow 导航。

## 2026-06-06 Command Palette Focus Trap 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-002 AppShell/导航 | `ready_for_cutover_review` | Command Palette 打开后焦点自动进入搜索框，Esc 关闭后回到触发按钮；不会破坏页面/策略/股票代码命令。 |
| FNX-OPT-005 Shared UI | `ready_for_cutover_review` | Command Palette 复用 `shared/ui/dialogFocus` 的 focus trap、Esc 和焦点恢复能力，减少弹层行为重复实现。 |
| FNX-OPT-018 响应式/a11y | `ready_for_cutover_review` | `app-shell-auth.spec.ts` 新增 Tab/Shift+Tab 焦点循环验证；不增加可见说明文案，不改变页面密度。 |

该优化只提升键盘可用性和弹层稳定性；业务路由、权限、API、策略排序和写入边界不变。

## 2026-06-06 Command Palette Shared UI Wrapper 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-002 AppShell/导航 | `ready_for_cutover_review` | Command Palette 的业务命令仍由 feature 层按页面/策略/股票代码生成，UI 抽象不改变用户跳转路径或 query 语义；E2E 继续覆盖页面、策略、股票代码入口。 |
| FNX-OPT-005 Shared UI | `ready_for_cutover_review` | 新增 `shared/ui/CommandPalette.tsx` wrapper，统一弹层结构、旧兼容样式、搜索输入、列表、footer 和 focus 生命周期；`wrappers.test.tsx` 覆盖 Command Palette wrapper 行为。 |
| FNX-OPT-018 响应式/a11y | `ready_for_cutover_review` | wrapper 延续 `.tq-command*` 视觉和现有文案，不新增说明信息；键盘焦点行为继续由 shared `dialogFocus` 管理。 |

该优化提升可维护性和稳定性，不改变业务路由、权限、API、策略排序、生产口径、写入边界或旧前端。

## 2026-06-06 Paper Order Form Usability 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-011 Paper order | `shadow-only` | 委托表单补齐推荐导入、持仓导入、数量快捷、费用估算和二次确认摘要；默认继续由 mutation guard 返回 shadow 结果，E2E 证明 0 个真实写请求。 |
| FNX-OPT-005 Shared UI | `ready_for_cutover_review` | 买卖方向和委托类型使用 `shared/ui/Segmented`，按钮和状态使用 shared wrapper；不引入第三方默认样式。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | 表单校验要求 6 位代码、正数量和有效价格；失败保留输入，提交中禁用按钮。 |

该优化提升模拟委托易用性和提交前可核对性；不改变真实交易、模拟账户状态、生产排序、收益口径或后端契约。

## 2026-06-06 Analysis To Paper Shadow Handoff 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-009 Analysis | `ready_for_cutover_review` | 分析结果页可直接打开模拟委托草稿，减少分析后手工复制代码/价格/理由的步骤；没有分析结果时按钮禁用。 |
| FNX-OPT-011 Paper order | `shadow-only` | 模拟盘只接收 `source=analysis` 的草稿 search，并复用现有 shadow 表单、二次确认、费用估算和 mutation guard。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | search 解析会过滤非 analysis 来源、无代码或非法数量/价格；草稿变更有 dedupe key，避免重复弹窗。 |

该优化提升分析到模拟复盘的连续性和稳定性；不改变分析结论、生产策略判断、真实写入、模拟账户状态、后端契约或旧前端。

## 2026-06-06 Symbol Analysis Navigation 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-002 AppShell/导航 | `ready_for_cutover_review` | Router search 使用普通 URL query；Command Palette 股票代码入口不再产生 JSON 引号编码，分析页能直接预填代码。 |
| FNX-OPT-007 Monitor actions | `ready_for_cutover_review` | Monitor 选中生产优先榜标的后可进入分析页；选中态写入 query，返回后不丢上下文。 |
| FNX-OPT-009 Analysis | `ready_for_cutover_review` | Analysis 响应 `symbol` query，并在 query 变化时取消旧请求、清空旧结果，降低跨标的旧数据误读风险。 |
| FNX-OPT-010 Playbook | `ready_for_cutover_review` | Playbook 候选详情支持进入分析页，`strategy + symbol` query 保留候选上下文。 |

该优化提升跨页任务连续性和 URL 稳定性；不改变生产榜排序、`priority_board`、`production_score`、策略语义、写入边界或后端契约。

## 2026-06-06 Shadow Action Draft Refresh 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-004 Mutation | `shadow-only` | ShadowActionPanel 字段快照变化时会重置草稿和二次确认，降低用户在切换标的后提交旧上下文 shadow 草稿的风险。 |
| FNX-OPT-005 Shared UI | `ready_for_cutover_review` | shared wrapper 单测覆盖 draft refresh；该能力由所有复用 `ShadowActionPanel` 的页面共享。 |
| FNX-OPT-007 Monitor actions | `shadow-only` | Monitor 观察池/持仓 shadow 表单随选中标的更新，E2E 继续证明不发真实写请求。 |

该优化提升 shadow 表单稳定性和可用性；不改变写入权限、后端契约、生产排序、策略语义或旧前端。

## 2026-06-06 Analysis Batch Worker Sort 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-009 Analysis | `ready_for_cutover_review` | 批量分析结果排序迁入 worker `sort`，主线程只负责渲染已排序展示行；worker 失败时同步 fallback。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | worker 返回错误也会回退同步排序；同分稳定、缺失分数靠后，避免结果表异常跳动或空白。 |
| FNX-OPT-003 API/Query | `ready_for_cutover_review` | 排序发生在 API 响应之后，不改变请求体、请求数量、缓存 key 或后端契约。 |

该优化提升分析页大批量展示的性能余量和稳定性；不改变分析结论、生产排序、`priority_board`、`production_score`、策略语义、写入边界或旧前端。

## 2026-06-06 Chart Downsample Endpoint Stability 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-009 Analysis | `ready_for_cutover_review` | 图表降采样改为首尾保留，保障 K 线最新点可见。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | `maxPoints=1` 返回最新点；不均匀点数仍返回目标数量并保持顺序。 |
| FNX-OPT-012 Paper display/review | `ready_for_cutover_review` | 共享 worker downsample fallback 稳定性提升，仍仅作为显示层纯计算。 |

该优化提升图表可读性和稳定性；不改变 API、后端计算、回测结果、生产排序、策略语义或写入边界。

## 2026-06-06 Kline Worker Downsample Adapter 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-009 Analysis | `ready_for_cutover_review` | KlineChart 写入 Lightweight Charts 前会经 worker downsample adapter；快速切换标的时旧异步结果被丢弃。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | worker unavailable/error/timeout 仍 fallback 到 sync downsample，卸载后不会再写图表。 |
| FNX-OPT-018 响应式/a11y | `ready_for_cutover_review` | KlineChart 不新增可见说明文案或布局变化，仍保持现有 chart-frame 尺寸。 |

该优化提升大 K 线点集的性能和稳定性；不改变 API 请求、分析结论、生产排序、策略语义、写入边界或旧前端。

## 2026-06-06 Backtest Workflow Tabs 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-014 Backtest | `shadow-only` | 回测页按 `提交任务 / 结果概览 / 成交明细 / ETF T0 / 研究闭环` 组织，减少详情和曲线来回切换；提交/取消/验证/优化仍 no-write。 |
| FNX-OPT-005 Shared UI | `ready_for_cutover_review` | 页签、运行列表、详情表、shadow 表单均复用 shared wrapper；运行列表补名称列提高可扫读性。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | ETF T0 明确显示 blocked_contract_needed，不伪造 minute backtest/validate 成功。 |

该优化提升回测研究路径的易用性和稳定性；不改变后端任务、回测结果、生产排序、策略语义或写入边界。

## 2026-06-06 Settings MFA Shadow Management 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-016 Settings | `shadow-only` | 账户与安全分区补齐 MFA 状态和 `MFA 管理` shadow 面板，减少用户不知道 MFA 是否可管理的盲区。 |
| FNX-OPT-005 Shared UI | `ready_for_cutover_review` | MFA 管理复用 `ShadowActionPanel`、二次确认和状态 pill，保持现有设置页密度和风格。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | 缺账号安全写契约时明确显示 `blocked_contract_needed`，不伪造 TOTP setup/disable 成功。 |

该优化提升设置页账户安全可用性和稳定性；不改变账户真实 MFA 状态、后端契约、权限、生产排序、策略语义或写入边界。

## 2026-06-06 Settings Section Shadow Management 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-004 Mutation | `shadow-only` / `blocked_contract_needed` | settings section 写入现在走统一 mutation guard，缺契约时明确 blocked，不再给出“保存成功”式结果。 |
| FNX-OPT-016 Settings | `blocked_contract_needed` | 风控、行业排除、因子权重、量化参数、策略治理均补可见管理入口，提升配置工作流可发现性。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | 缺安全写契约时保留输入、二次确认和 blocked 结果，用户可知道下一步是补契约而不是误以为已生效。 |

该优化提升设置页易用性、可用性和稳定性；不改变真实配置、权限、后端契约、生产排序、策略语义或写入边界。

## 2026-06-06 Shadow Submit And Menu Layer Stability 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-004 Mutation | `shadow-only` / `blocked_contract_needed` | Shadow 表单二次确认后进入提交中状态，防止重复提交 intent；失败时不清空草稿，便于修正重试。 |
| FNX-OPT-005 Shared UI | `ready_for_cutover_review` | `ShadowActionPanel` 的防重复、失败恢复和字段刷新均有 wrapper 单测，复用页面无需各自重写。 |
| FNX-OPT-002 AppShell/导航 | `ready_for_cutover_review` | topbar/user menu 层级修复后，设置页 sticky 工具条不再截获账户菜单点击。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | 异步提交失败显示具体错误或默认重试文案，避免伪造成成功状态。 |

该优化提升 shadow 写入交互的易用性、可用性和稳定性；不改变真实写入权限、后端契约、生产排序、策略语义或旧前端。

## 2026-06-06 Auth Refresh Recovery 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-001 Auth/工作台 | `ready_for_cutover_review` | 普通读请求 401 可自动续期并重试一次，刷新页面后的 session restore 之外也有认证过期恢复路径。 |
| FNX-OPT-003 API/Query | `ready_for_cutover_review` | refresh retry 在 `shared/api/client.ts` 统一处理，页面和 feature query 不需要各自拼 URL 或手写恢复逻辑。 |
| FNX-OPT-004 Mutation | `shadow-only` / `blocked_contract_needed` | 写请求 401 不自动重试，继续由 mutation 状态机和二次确认保护。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | refresh 失败会回到原 401 错误路径，成功/失败均有脱敏 telemetry，避免静默白屏。 |

该优化提升认证过期场景的可用性和稳定性；不改变真实写入权限、后端契约、生产排序、策略语义或旧前端。

## 2026-06-06 Error Boundary And Telemetry Redaction 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | 页面 crash fallback 展示前统一脱敏错误 message，避免异常恢复界面泄露敏感值。 |
| FNX-OPT-003 API/Query | `ready_for_cutover_review` | telemetry 字符串值脱敏覆盖 authorization/token/secret/password/cookie 片段，不改变请求、缓存 key 或 API 契约。 |
| FNX-OPT-009 Analysis | `ready_for_cutover_review` | K 线错误 telemetry 脱敏后仍保留 chart error 状态，便于排障但不暴露凭据。 |

该优化提升新前端错误恢复和诊断稳定性；不改变 API、真实写入权限、生产排序、`priority_board`、`production_score`、策略语义或旧前端。

## 2026-06-06 Route Level Error Boundary 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | 单个 `/next/*` 页面 crash 不拖垮 AppShell；用户仍可通过侧边栏或 fallback 按钮离开失败页面。 |
| FNX-OPT-002 AppShell/导航 | `ready_for_cutover_review` | 路由级 fallback 保留 topbar、sidebar、账户菜单和 Command Palette 上下文。 |
| FNX-OPT-005 Shared UI | `ready_for_cutover_review` | route fallback 复用 `Panel`、`Button` 和 redaction 工具，不新增页面私有错误样式。 |

该优化提升新前端页面级可用性和稳定性；不改变 API、真实写入权限、生产排序、`priority_board`、`production_score`、策略语义或旧前端。

## 2026-06-06 Paper Mecha Reduced Motion 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-012 Paper display/review | `ready_for_cutover_review` | 机甲 Canvas 粒子响应 reduced motion 运行时切换，开启后立即停止动画并释放 resize listener；关闭后按当前状态恢复。 |
| FNX-OPT-018 响应式/a11y | `ready_for_cutover_review` | 动效遵循系统 reduced-motion 偏好，不要求刷新页面，也不新增可见说明文案或改变页面密度。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | 单测覆盖 RAF/resize cleanup，降低隐藏页或辅助功能切换后持续占用 CPU 的风险。 |

该优化提升模拟盘显示层动效的易用性、可用性和稳定性；不改变 API、真实写入权限、生产排序、`priority_board`、`production_score`、策略语义或旧前端。

## 2026-06-06 SSE Reconnect Stability 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-006 Monitor/realtime | `ready_for_cutover_review` | quote SSE 断连后关闭旧连接并按 1s 起步、最大 15s 的指数退避重连，避免一直停留在错误状态。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | 最后订阅者 cleanup 会取消 pending reconnect timer，切页后不会后台重连或保留僵尸 EventSource。 |
| FNX-OPT-003 API/Query | `ready_for_cutover_review` | SSE telemetry 只记录连接状态、attempt 和 delay，不记录 quote payload、token、账号或策略字段。 |

该优化提升实时行情显示层的可用性和稳定性；不改变 API、真实写入权限、生产排序、`priority_board`、`production_score`、策略语义或旧前端。

## 2026-06-06 User-Facing Error Message Redaction 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | 通用 `errorMessage` 返回页面文案前会脱敏 token、authorization、secret、password、cookie 等敏感片段。 |
| FNX-OPT-004 Mutation | `shadow-only` / `blocked_contract_needed` | Shadow 表单和模拟委托提交失败时保留草稿/确认状态，但只展示脱敏后的失败原因。 |
| FNX-OPT-005 Shared UI | `ready_for_cutover_review` | `ShadowActionPanel` 删除本地重复错误文案函数，复用 shared API 错误文案，降低后续页面复制泄露风险。 |

该优化提升新前端错误恢复的易用性、可用性和稳定性；不改变 API、真实写入权限、生产排序、`priority_board`、`production_score`、策略语义或旧前端。

## 2026-06-06 Worker Error Redaction 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | Worker crash/failure 的错误文本在响应和 telemetry 进入诊断前统一脱敏。 |
| FNX-OPT-003 API/Query | `ready_for_cutover_review` | Worker fallback 诊断只记录显示层任务名、状态、耗时和脱敏错误，不记录 payload/body/token。 |
| FNX-OPT-009 Analysis | `ready_for_cutover_review` | Worker sort/downsample 失败继续同步 fallback，避免页面空白或排序结果丢失。 |

该优化提升新前端 Worker 失败恢复的可用性和稳定性；不改变 API、真实写入权限、生产排序、`priority_board`、`production_score`、策略语义或旧前端。

## 2026-06-06 Worker PostMessage Fallback 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | Worker `postMessage` 同步抛错后不再等待 timeout，立即走 sync fallback。 |
| FNX-OPT-003 API/Query | `ready_for_cutover_review` | fallback telemetry 只记录任务名、状态、耗时和脱敏错误，不记录 payload/body/token。 |
| FNX-OPT-009 Analysis | `ready_for_cutover_review` | 批量排序和图表降采样 Worker payload 异常时仍可恢复为同步显示层计算。 |

该优化提升新前端 Worker 异常路径的可用性和稳定性；不改变 API、真实写入权限、生产排序、`priority_board`、`production_score`、策略语义或旧前端。

## 2026-06-06 Safe Write Contract Registry 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-004 Mutation | `shadow-only` / `blocked_contract_needed` | 新增 `safeWriteContracts.ts`，blocked mutation 结果带 `safeWriteContract.id`、required mode、required role 和 evidence 摘要，避免“只知道被拦截但不知道缺什么”。 |
| FNX-OPT-011 Paper order | `defined_isolated_live_smoke` | `FNX-SW-PAPER-ORDER` 明确隔离模拟盘账号、幂等、cancel/reset rollback、audit echo 要求；默认仍 shadow。 |
| FNX-OPT-013 Strategy tracking | `defined_backend_needed` | `FNX-SW-STRATEGY-REVIEW`、`FNX-SW-TRADE-JOURNAL` 明确 review/journal CRUD、审计和回滚要求；真实写仍 blocked。 |
| FNX-OPT-014 Backtest | `defined_isolated_live_smoke` / `defined_backend_needed` | `FNX-SW-BACKTEST-TASK` 明确 test run marker、cancel/delete 回滚和任务状态 truth table。 |
| FNX-OPT-015 Data console | `defined_backend_needed` | `FNX-SW-DATA-TASK`、`FNX-SW-DATA-REPAIR` 明确 bounded scope、dry-run/apply、cancel/rollback 和 audit echo。 |
| FNX-OPT-016 Settings | `defined_backend_needed` / `defined_isolated_live_smoke` | `FNX-SW-SETTINGS-SECTION` 和 `FNX-SW-FEATURE-FLAG` 明确 section version、save echo、restore previous value 和 audit echo。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | blocked message 从泛化“缺契约”变为具体 contract id 和下一步证据要求，降低后续联调误判和重复返工风险。 |

该优化提升危险写入工作流的易用性、可用性和稳定性；不开放真实写入，不改变后端 API、生产排序、`priority_board`、`production_score`、策略语义或旧前端。

## 2026-06-06 Safe Write Request Evidence 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-004 Mutation | `defined_isolated_live_smoke` evidence ready | live-smoke mutation 发送前附加安全写 header，并在 `MutationResult.clientRequestId` 返回前端请求追踪 ID。 |
| FNX-OPT-003 API/Query | `ready_for_cutover_review` | 请求证据不改变 body 和 OpenAPI DTO，避免为审计字段破坏现有后端契约。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | telemetry 增加 contract id 和 client request id，联调失败时可定位是哪次 guarded mutation，但不记录 payload 或敏感凭据。 |

该优化提升安全写联调、回滚冒烟和问题定位的稳定性；不开放真实写入，不改变后端 API、生产排序、`priority_board`、`production_score`、策略语义或旧前端。

## 2026-06-06 Local Isolated Write Rollback Smoke 最新证据

| ID | 最新状态 | 补充证据 |
|---|---|---|
| FNX-OPT-004 Mutation | `completed_local_isolated_smoke` | `write:rollback` 三项 live-smoke 均 `ok=true`，报告包含 contract id、client request id 和 rollback shape。 |
| FNX-OPT-011 Paper order | `completed_local_isolated_smoke` | 模拟委托 create 后 reset 临时账号，未改变生产模拟盘账号。 |
| FNX-OPT-014 Backtest | `completed_local_isolated_smoke` | 回测 run create 后 delete，rollback status 为 `deleted`。 |
| FNX-OPT-016 Settings | `completed_local_isolated_smoke` | 低风险 UI feature flag toggle 后 restore，最终 `ff_playbook_lazy_load_enabled=true`。 |
| FNX-OPT-017 异常恢复 | `ready_for_cutover_review` | 脚本运行时选择当前后端实际支持的 feature flag，避免因旧 key 漂移造成 false negative。 |

该优化提升本地验收可重复性和稳定性；不开放正式环境真实写入，不改变后端 API、生产排序、`priority_board`、`production_score`、策略语义或旧前端。
