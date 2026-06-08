# Frontend Next 未完成项

日期：2026-06-05
范围：`frontend-next/` shadow 前端，不包含 cutover。

## 2026-06-07 自用口径剩余项

用户最新口径为“满足自用即可，保证各功能都正常可用”。按该口径，`frontend-next/` 当前可作为本地自用工作台继续使用；正式 cutover 仍不应执行。

最新状态说明：本节覆盖下方历史段落中的旧 `blocked` 描述。剩余 4 组安全写契约已补齐本地后端 rollback、审计、403、读回一致证据；`write:readiness` 当前为 12 production-ready、0 blocked、1 cutover-excluded。仍未部署、未切流，正式 cutover 需要用户单独授权，并在正式 admin token/environment 下复跑。

已满足自用：

| 项 | 状态 | 证据 |
|---|---|---|
| 9 个 `/next/*` 页面可打开和交互 | 已满足 | `npm run e2e` 44/44 passed。 |
| 登录、会话恢复、权限守卫 | 已满足 | E2E 覆盖匿名跳登录、token refresh、401 清理、admin/paper guard。 |
| 模拟盘机甲和操作流 | 已满足 | API 503 下机甲仍显示；委托、暂停/恢复、对账入口默认不发真实写请求。 |
| 分析、选股、策略跟踪、回测、数据、设置主要交互 | 已满足 | 相关 E2E 全通过；请求跟踪无导航错误。 |
| 页面工程态文案 | 已收敛 | 用户可见 `blocked_contract_needed`、`shadow` 等工程态已替换为本地记录/保护模式表达；API payload source 字段保留。 |
| 性能和请求稳定性 | 已满足本地自用 | `perf:compare` 核心页面 576-832ms（strategy 693ms），DOM 230-398；`request:trace` EventSource 全 0。 |

自用仍需注意：

| 项 | 影响 | 当前处理 |
|---|---|---|
| `playbook lifecycle`、`strategy review record`、`data task`、`data repair` 正式环境尚未复跑 | 不影响读取和本地复盘；影响正式切流授权前的验收材料 | 本地后端 rollback、审计、403、读回一致证据已补齐；cutover 前用正式 admin token 复跑。 |
| 正式 admin token/environment 未复验 | 不影响本地普通使用；影响正式管理写入切流 | 本地 admin-token 已通过，正式环境 cutover 前再复验。 |
| cutover 未授权 | 不影响 `/next/*` 自用 | 保持本地/并行使用，不部署、不切流。 |

## 2026-06-07 当前未完成项

本轮已继续完成安全写契约可验证部分、admin-token 本地联调和完整隔离 rollback smoke；以下项仍限制正式 cutover 执行。

| 项 | 状态 | 阻断/原因 | 下一步 |
|---|---|---|---|
| 安全写 production-ready | 本地 PASS | `write:readiness`：13 contracts，12 production-ready，0 blocked，1 cutover-excluded；rollback evidence `ok`，`cutover_ready=true`。 | cutover 前用正式 admin token/environment 复跑并归档。 |
| 正式管理 API 复验 | 本地 admin-token PASS；正式环境仍需复跑 | 本地 8011 独立后端注入 `ADMIN_API_TOKEN=test-admin-token` 后，`api:cutover-readiness` 6/6 probes 通过，包括 `/api/settings`、`/api/settings/factor-weights`。 | cutover 前用正式 admin token/environment 复跑；若生产缺管理 token，需运维补配置或确认切流降级策略。 |
| feature flag live rollback | 已完成本地隔离 PASS；正式环境仍需复跑 | 完整 `write:rollback -- --all --isolated` 已完成 feature flag toggle + restore，`frontend_solid_island_enabled` 恢复原值。 | cutover 前用正式 admin token 和隔离 flag 复跑并归档审计证据。 |
| 真实写入深度 parity | 本地 PASS | auth MFA、watchlist、trade journal、paper account/order、settings、feature flag、backtest run/validation/optimization、playbook lifecycle、strategy review、data task、data repair 已有本地隔离写入/撤销或取消/读回/403 证据。 | 正式环境复跑后再进入 cutover 授权流程。 |
| cutover 用户授权 | 未完成，P0 阻断 | 本轮明确不部署、不切流。 | 所有 gate 达标后，由用户单独授权 cutover。 |

本轮已关闭或降级为非阻断：

| 项 | 当前结果 | 证据 |
|---|---|---|
| 两交易日 shadow run | 已完成 | `shadow:aggregate` 样本日期 `2026-06-05`、`2026-06-06`、`2026-06-07`，API/request-SSE/screenshot gates 均 true。 |
| strategy-tracking 422 | 已修复 | 新前端请求 `limit=50`，`api:cutover-readiness` 中 `strategy-tracking-items` 200。 |
| 设置页普通环境 503 噪音 | 已修复页面侧 | `/next/settings` 仅请求 `/api/auth/me` 和 `/api/bff/v1/workspace/settings`；直连管理接口只在 admin API token 存在时启用。 |
| 新前端视觉一致性 | 已通过 | `visual:consistency` 36 captures，failed 0；旧像素 parity 不再作为 cutover 阻断项。 |
| CSS 预算/未引用报告 | 已完成报告 | `css:budget` 通过，source CSS 297152 bytes、dist CSS gzip 47925 bytes、`!important` 51；`css:unused-report` 仅列候选，不删除。 |
| 新前端质量命令 | 已完成 | `api:check`、`typecheck`、`lint`、`npm test -- --run`、`build` 均 PASS；单测 19 files / 86 tests。 |

## 本轮已补齐

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 认证态 API payload parity | 已完成本地 smoke | 已生成本地测试 token，`FRONTEND_AUTH_TOKEN=<token> npm run api:parity` 返回 6/6 个受保护端点 200，并输出 hash/shape | cutover 前仍需用正式验收账号复跑 |
| 真实旧页面截图 parity | 已完成认证态捕获，未达 cutover 签收 | `START_LEGACY_FRONTEND=1 FRONTEND_AUTH_TOKEN=<token> npm run screenshot:parity` 已捕获旧新截图；最新旧新 sample_similarity 为 0.8968-0.9629，8/9 页大于等于 0.90；`/paper` 迁移旧机甲后已达 0.9017/0.9018，`/analysis` 最新采样 0.8968 | cutover 前需要人工逐页视觉签收；`/analysis` 需重点查看 review PNG |
| 旧新请求数/SSE 对比 | 已完成认证态 trace | `START_LEGACY_FRONTEND=1 FRONTEND_AUTH_TOKEN=<token> npm run request:trace` 9 个路由均无导航错误，旧新 EventSource 均为 0；新前端每页 0-1 个业务请求 | 后续两交易日 shadow run 继续观测 |
| 交互级 shadow parity | 已完成 no-write 验收 | `/next/paper`、`/next/strategy-tracking`、`/next/backtest`、`/next/data`、`/next/settings` 已补输入、预览、二次确认和结果日志；e2e 拦截 POST/PUT/PATCH/DELETE，验证 0 个写请求 | cutover 前再接真实写接口和隔离测试数据 |
| 真实写入 adapter | 已完成 flag-guarded 准备 | `frontend-next/src/shared/api/mutations.ts` 已用 generated types 接入 paper order、backtest create、feature flag PUT；默认 `VITE_FRONTEND_NEXT_WRITE_ENABLED` 关闭时不发请求，单测验证开启时 endpoint/method/body 正确 | 只允许在隔离账号/数据集下开启 flag 做回滚验收 |
| Shadow 样本汇总脚本 | 已完成本地 smoke | `FRONTEND_AUTH_TOKEN=<token> npm run shadow:sample` 会串行执行 API parity、旧新请求/SSE trace、截图 parity，并把结果写入 `docs/reports/frontend-next-shadow-sample-2026-06-05.json`；最新样本 PASS | 两交易日窗口内重复执行 |
| 两交易日聚合脚本 | 已完成第一日采样和聚合报告 | `npm run shadow:sample` 已落盘 `docs/reports/frontend-next-shadow-samples/2026-06-05-*.json`；`npm run shadow:aggregate` 生成 `docs/reports/frontend-next-two-day-shadow-run-2026-06-05.json`，API/request/SSE/screenshot gates 均通过，但只有 1 个交易日 | 等第二个真实交易日再重复采样并聚合 |
| 写入回滚冒烟脚本 | 已完成本地完整隔离回滚 | `npm run write:rollback` 验证默认写入关闭；本地当前代码 8001 临时后端下，`FRONTEND_NEXT_LOCAL_ADMIN_PROMOTE=1 FRONTEND_NEXT_LIVE_WRITE_SMOKE=1 FRONTEND_NEXT_LIVE_ADMIN_WRITE_SMOKE=1 FRONTEND_NEXT_LIVE_BACKTEST_SMOKE=1 npm run write:rollback` 完成 paper order create+reset、feature flag toggle+restore、backtest create+delete，最新 `docs/reports/frontend-next-write-rollback-smoke-2026-06-05.json` 为 `ok=true` | strategy review/data job 仍需明确安全写 API；生产或正式验收账号不在本轮执行 |
| 页面可见英文/技术描述 | 已基本完成 | 页面标题、导航、说明、状态、操作反馈已改中文；`/next/paper` 自动交易状态增加对象保护，避免显示 `object Object` | 继续通过截图人工复查，API 契约字段不视为页面可见文案 |
| `/next/paper` 机甲头像和特效 | 已完成并加回归测试 | 初版新前端曾使用简化占位，且后续一度受 API 成功态门控影响；当前 `PaperMechaHud` 已独立渲染旧前端机甲头像、HUD、Canvas 粒子、机型切换和实时日志 | `npm run e2e` 中新增 API 503 下机甲仍可见的回归用例 |
| 视觉签收证据包 | 已生成，人工结论待签收 | `npm run visual:review` 生成 `docs/reports/frontend-next-visual-review-2026-06-05/*.png` 和 `docs/reports/frontend-next-visual-signoff-2026-06-05.md` | 逐页人工查看 review PNG，将结论从 `待签收` 改为 `通过` |
| 旧前端测试失败 | 已修复 | 仅修改旧前端测试文件 `frontend/src/features/trading-workspace/TradingWorkspaceChrome.test.ts`，对齐当前旧实现；旧前端 `api:check`、`typecheck`、`lint`、`test`、`build` 均已 PASS | 无 |
| `/next/analysis` 深功能 | 已完成 shadow parity | 接入 analyze/batch、quote、kline、关键位、盘中异常；支持单票/批量分析和 K 线 fallback；`analysis-playbook.spec.ts` 通过 | cutover 前补真实账号 API parity、截图 parity、性能采样 |
| `/next/playbook` 深功能 | 已完成 shadow parity | 接入 low-buy screener、priority-board、quotes、strategies、meta；支持策略 tabs、候选分层、绩效归因、详情联动；生命周期更新保持记录/阻断 | cutover 前补正式数据样本和视觉签收 |
| `/next/paper` 完整业务流 | 已完成 shadow parity | 补账户结论、持仓、订单/成交/风险/绩效/自动交易/对账 tabs、模拟委托表单、API 失败机甲可见回归；真实写默认关闭 | pause/resume/reconcile/自动交易控制仍需安全写契约；live-smoke 需隔离账号复跑 |
| `/next/strategy-tracking` 深功能 | 已完成 shadow parity | 补筛选、模式切换、表格、详情、表现/持有/漂移/诊断/复盘中心、交易日志和相对强弱读取；复盘/日志写入保持记录/阻断 | trade journal/review 真实写需安全契约和回滚证据 |
| `/next/backtest` 深功能 | 已完成 shadow parity | 补 run detail、equity、trades、任务控制、验证/优化记录和低频图表；`backtest-data-settings.spec.ts` 通过 | cancel/validate/optimize 真实写需安全契约和回滚证据 |
| `/next/data` 深功能 | 已完成 shadow parity | 接入 coverage/SLA/runtimeTasks/adminMetrics/adminTasks；补 SLA、coverage、tasks、workers、repair、inspector | repair/backfill/task 真实写需安全契约和回滚证据 |
| `/next/settings` 深功能 | 已完成 shadow parity | 接入 authMe、settings/runtime、sector/factor/flags/audit/quant/governance；feature flag 保持 mutation guard | 正式 admin 账号复测、MFA 真实写入和非 feature-flag 写契约仍待确认 |

## 当前未完成

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| Auth/Guard/AppShell 基础设施 | 已完成基础 pass，仍需正式验收账号复测 | 已新增登录/注册/session restore/logout/MFA model、route guard、paper/admin guard、Command Palette、快捷键、移动导航、兼容跳转；E2E 通过受控测试用户验证 | 用正式验收账号复跑 auth E2E、401 refresh、403 fallback；补 390x844 响应式截图 |
| API operation/query 基础 | 已完成页面主链路接入 | `shared/api/operations.ts` 覆盖主要 feature operation，页面主读链路已接入 operation/queryKeys，`api:check` 通过 | cutover 前补 payload hash、order hash 和正式账号 API parity |
| Shared UI wrapper 基础 | 已完成基础 pass | Button、DataTable、VirtualList/VirtualCardList、Modal、Drawer、ConfirmAction、Toast、FormField 等已补，wrapper tests/typecheck/lint/build 通过 | 页面实现时禁止复制临时弹窗/表格，继续补业务场景组件测试 |
| QA/权限/优化矩阵 | 已完成初版 | 已新增 traceability、optimization、permissions 三份矩阵，当前大量状态仍为 `gap_open`/`shadow-only`/`blocked_contract_needed` | 随功能完成逐行补 payload/order/request/SSE/screenshot/test 证据 |
| 页面深功能正式数据验收 | 未完成 | 页面已具备 shadow parity，但本批未使用正式验收账号重跑 API parity、request/SSE、截图 parity 和两交易日样本 | 用正式验收 token 执行 `api:parity`、`request:trace`、`screenshot:parity`、`shadow:sample` |
| 两交易日 shadow run | 部分完成，1/2 交易日 | 当前北京时间 2026-06-05 23:19 已非交易时段；已采集 2026-06-05 样本并通过 API/request/SSE/screenshot gates；`at_least_two_trading_days=false` | 第二个真实交易日执行 `FRONTEND_AUTH_TOKEN=<token> npm run shadow:sample && npm run shadow:aggregate` |
| strategy review/data job 安全写 API | 未完成 | 当前后端没有明确可回滚的安全写接口；新前端对应动作继续保持 shadow-only，不伪造写入 | 明确 API 契约、隔离数据和回滚方式后再接入 |
| 旧新视觉人工签收 | 证据已生成，未人工通过 | 并排 review PNG 与签收清单已生成，但人工结论仍为 `待签收`；`/paper` 迁移旧机甲后已达 0.9018，`/analysis` 最新截图采样略低于 0.90 | 打开 `docs/reports/frontend-next-visual-signoff-2026-06-05.md` 中 9 张 review PNG，逐页确认后改为 `通过` |
| cutover/部署 | 未执行 | 初始硬边界为“不部署”；且两交易日 shadow、人工视觉签收未完成 | 保持 `/next/*` shadow；满足验收后再单独执行 cutover runbook |

## 本轮可继续验证命令

```bash
cd /Users/j/Documents/gupiao/frontend-next
FRONTEND_AUTH_TOKEN=<token> npm run api:parity
START_LEGACY_FRONTEND=1 FRONTEND_AUTH_TOKEN=<token> npm run request:trace
START_LEGACY_FRONTEND=1 FRONTEND_AUTH_TOKEN=<token> npm run screenshot:parity
FRONTEND_AUTH_TOKEN=<token> npm run shadow:sample
npm run shadow:aggregate
npm run visual:review
npm run write:rollback
FRONTEND_NEXT_LIVE_WRITE_SMOKE=1 npm run write:rollback
FRONTEND_NEXT_LIVE_BACKTEST_SMOKE=1 npm run write:rollback
API_BASE=http://127.0.0.1:8001 FRONTEND_NEXT_LOCAL_ADMIN_PROMOTE=1 FRONTEND_NEXT_LIVE_WRITE_SMOKE=1 FRONTEND_NEXT_LIVE_ADMIN_WRITE_SMOKE=1 FRONTEND_NEXT_LIVE_BACKTEST_SMOKE=1 npm run write:rollback
```

以上命令不部署、不切流、不修改后端。

## 2026-06-06 最终未完成项更新

已完成更新：

| 项 | 最新状态 | 证据 |
|---|---|---|
| `/next/monitor` 深功能 | 已完成 shadow parity | 生产榜服务端顺序、分层 tabs、风险 badges、持仓/自选、观察池/持仓 shadow action、关键位、AI 解读、运行时/数据质量；`monitor-workflows.spec.ts` 通过。 |
| `/next/monitor/market` 深功能 | 已完成 shadow parity | 市场总闸、breadth、pulse、sector leader、ETF T0、review、runtime/sync/data quality；`monitor-workflows.spec.ts` 通过。 |
| 四档响应式截图 | 已完成自动捕获 | `npm run screenshot:parity` 生成 1440x900 compare，并捕获 1280x800、768x1024、390x844。 |
| 请求/SSE gate | 已完成 | `/next/settings` 已按 tab 懒加载，最新 `request:trace` 9 路由无导航错误，EventSource 全为 0，新前端请求数不高于旧前端。 |
| 两交易日 shadow run | 已完成脚本 gate | `npm run shadow:aggregate` PASS；交易日样本 `2026-06-05`、`2026-06-06`，API/request-SSE/screenshot gates 均 true。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，但 `docs/reports/frontend-next-visual-signoff-2026-06-05.md` 仍为 `待签收`；`/paper` 0.8327、`/playbook` 0.8301 需人工判断深功能布局变化是否可接受 | 打开 9 张 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png`，逐页签收或列出要改的视觉项 |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据、回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 用户本轮硬边界为不部署不切流；需要单独授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且 bot 搜不到目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 视觉/API 修复后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| `/next/playbook` 422 错误态 | 已完成 | 默认策略恢复 `first_board`；`priority-board` 使用 `strategy_variant=baseline` 且 `limit<=30`；只读网络检查无 4xx；`screenshot:parity` 正常渲染业务页。 |
| `/next/playbook` 视觉相似度 | 已改善 | 最新旧新 review similarity 0.9350，较错误态 0.8303 明显提升。 |
| `/next/paper` 首屏多余描述 | 已收敛 | 模拟委托改弹窗入口，移除多余说明块，机甲头像/特效/日志保留；最新旧新 review similarity 0.8503。 |
| 新前端完整验收链 | 已完成 | `api:check`、`typecheck`、`lint`、`test`、`build`、`e2e`、`perf:compare`、`screenshot:parity` 全 PASS。 |
| 旧前端完整验收链 | 已完成 | `api:check`、`typecheck`、`lint`、`test`、`build` 全 PASS。 |
| request/SSE | 已完成 | 9 个新路由请求数均不高于旧路由，EventSource 全为 0。 |
| 两交易日 shadow run | 已完成 | `shadow:aggregate` PASS，交易日 `2026-06-05`、`2026-06-06`。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` 因机甲 display/review 和完整 tab 入口相似度 0.8503，需要用户确认是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 后签收或指定需继续调整页面 |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮不部署不切流；需要单独授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Safe Write Contract Definition 后最新状态

本轮已完成：

| 项 | 最新状态 | 证据 |
|---|---|---|
| 安全写契约文档 | 已完成定义 | `docs/frontend-next/safe-write-contracts-2026-06-06.md` 定义 13 个 `FNX-SW-*` 契约。 |
| 前端契约 registry | 已完成 | `frontend-next/src/shared/api/safeWriteContracts.ts` 把全部 guarded non-ready writes 映射到 contract id。 |
| Mutation blocked 可见性 | 已完成 | `MutationResult.safeWriteContract` 返回 contract 摘要；blocked/shadow-only message 带 contract id。 |
| 覆盖测试 | 已完成 | `mutations.test.ts`、`operations.test.ts` PASS，证明非 ready 写 operation 不会漏登记。 |
| no-write 边界 | 已保持 | 没有把 `blocked_contract_needed` 改成可发送；默认 shadow 下仍不发真实写。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8505，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 后端安全写实现 | 未完成 | 契约已定义：`FNX-SW-STRATEGY-REVIEW`、`FNX-SW-TRADE-JOURNAL`；仍缺后端 CRUD、隔离数据和 rollback smoke | 实现 OpenAPI 契约、审计、rollback 后再接入 isolated live-smoke |
| data repair/backfill/task/ETF池 后端安全写实现 | 未完成 | 契约已定义：`FNX-SW-DATA-TASK`、`FNX-SW-DATA-REPAIR`；仍缺 dry-run/apply/cancel/rollback 后端证据 | 补后端安全契约、隔离环境、回滚证据 |
| settings 非 feature-flag 后端安全写实现 | 未完成 | 契约已定义：`FNX-SW-SETTINGS-SECTION`；仍缺 section version、save echo、restore previous version | 补分区保存 API、回显、回滚策略、权限 gate |
| paper pause/resume/reconcile 后端安全写实现 | 未完成真实写 | 契约已定义：`FNX-SW-PAPER-ACCOUNT`；仍缺隔离模拟盘账号和账户状态回滚证据 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize 隔离验证 | 未完成真实写 | 契约已定义：`FNX-SW-BACKTEST-TASK`；仍缺测试 run/task 标记、cancel/delete 证据 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Backend Integration 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| 本地后端联调 | 已完成 | `127.0.0.1:8000` 在线；未带 token `/api/auth/me` 返回 401；临时 shadow auth 下 `api:parity` 6/6 受保护端点 200。 |
| 两交易日 shadow aggregate | 已完成 | `npm run shadow:aggregate` PASS；交易日 `2026-06-05`、`2026-06-06`，`sample_count=6`，API/request-SSE/screenshot gates 均 true。 |
| 请求/SSE 对比 | 已完成 | `START_LEGACY_FRONTEND=1 npm run request:trace` PASS；9 个旧新路由无导航错误，旧新 EventSource 均为 0，新前端请求数均不高于旧前端。 |
| authenticated perf profile | 已完成 | `perf-profile.mjs` 已注入临时 auth；`npm run perf:compare` 复跑后核心路由 API 均 200，SSE 为 0。 |
| 联调报告 | 已完成 | `docs/reports/frontend-next-backend-integration-2026-06-06.md`。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收` | 用户逐页查看最新 review PNG 和截图，签收或指定继续调整项 |
| 正式验收账号/正式环境复跑 | 未完成 | 本轮联调证据来自本地 shadow token 和本地后端 | 提供正式验收账号/token 后复跑 `api:parity`、`request:trace`、`screenshot:parity`、`shadow:sample`、`shadow:aggregate` |
| strategy review/trade journal 真实写闭环 | 未完成 | 缺后端幂等、审计、隔离数据和回滚 live-smoke | 明确契约并补后端回滚证据后接入 |
| data repair/backfill/task/ETF池 真实写闭环 | 未完成 | 缺 dry-run/apply/cancel/rollback 后端证据 | 明确安全契约、隔离环境和回滚证据后接入 |
| settings 非 feature-flag 写入 | 未完成 | 缺分区保存、回显、审计和回滚契约 | 明确保存 API、回滚策略和权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消、验证、优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮不部署不切流；仍需要用户单独授权 | 获得明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Worker PostMessage Fallback 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| Worker postMessage 同步失败恢复 | 已完成稳定性补强 | `workerClient.ts` 捕获 `postMessage` 抛错并立即 sync fallback。 |
| listener/timeout 清理 | 已完成 | 单测验证 `message/error/messageerror` listener 在 `postMessage` 抛错后清空。 |
| 诊断脱敏 | 已完成 | `postmessage-fallback` telemetry 不保留 refresh token/password 原值。 |
| 针对性验证 | 已完成 | `workerClient.test.ts` PASS，1 file / 4 tests；`typecheck` PASS；`lint` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8504，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task/ETF池 安全写 | 未完成 | 缺明确 dry-run/apply/cancel/rollback 契约；当前仅 shadow/blocked | 明确安全契约、隔离环境和回滚证据后接入 live-smoke |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约；当前配置写入仍只做 shadow 记录 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前 shadow 交互已二次确认，但仍缺隔离模拟盘账号和回滚证据 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Safe Write Request Evidence 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| 安全写契约 registry | 已完成前端定义 | `safeWriteContracts.ts` 覆盖全部 guarded non-ready write operation，并提供 `FNX-SW-*` id、角色、模式、guard、request/response、audit、rollback 和 evidence 要求。 |
| live-smoke 请求证据 | 已完成前端证据链 | 允许发送的 live-smoke mutation 会附加 `X-Frontend-Next-Client-Request-Id`、`X-Frontend-Next-Contract-Id`、`X-Frontend-Next-Operation`、`X-Frontend-Next-Write-Mode` 等 header，并返回 `MutationResult.clientRequestId`。 |
| blocked/shadow 写保护 | 已完成 | `shadow-only`、`blocked_contract_needed`、`write-disabled`、`mode-blocked`、`permission-blocked` 分支不生成 live request id，不调用 requester。 |
| 本地 isolated write rollback smoke | 已完成 | 本地 sqlite 环境下 `paperOrderCreate` create+reset、`featureFlagUpdate` toggle+restore、`backtestRunCreate` create+delete 均 PASS，报告 `docs/reports/frontend-next-write-rollback-smoke-2026-06-05.json` 为 `ok=true`。 |
| 针对性验证 | 已完成 | `mutations.test.ts` + `operations.test.ts` PASS，2 files / 14 tests；`typecheck` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8505，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| 正式环境安全写 isolated live-smoke | 未完成 | 本地 sqlite 三项 smoke 已通过，但未在正式验收账号/正式环境复跑 | 使用正式验收账号和隔离数据复跑 `npm run write:rollback`，并归档审计/回滚证据 |
| strategy review/trade journal 安全写 | 未完成后端闭环 | 已有 `FNX-SW-STRATEGY-REVIEW`、`FNX-SW-TRADE-JOURNAL`；仍缺 review/journal CRUD 的后端回滚 smoke | 补 review/journal 后端安全写测试与回滚验证 |
| data repair/backfill/task/ETF池 安全写 | 未完成后端闭环 | 已有 `FNX-SW-DATA-TASK`、`FNX-SW-DATA-REPAIR`；仍缺 dry-run/apply/cancel/rollback 后端证据 | 明确 bounded dataset 和 cancel/rollback 后接入 live-smoke |
| settings 非 feature-flag 写入 | 未完成后端闭环 | 已有 `FNX-SW-SETTINGS-SECTION`；仍缺 section version、save echo 和 restore previous version | 补分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成后端闭环 | 已有 `FNX-SW-PAPER-ACCOUNT`；当前 shadow 交互已二次确认，但仍缺隔离模拟盘账号和回滚证据 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成后端闭环 | 已有 `FNX-SW-BACKTEST-TASK`；当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Worker Error Redaction 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| Worker 失败响应脱敏 | 已完成稳定性补强 | `compute.worker.ts` 捕获异常后返回脱敏 `error` 字段，避免 Worker crash 泄露 token/password。 |
| Worker fallback telemetry | 已完成 | `workerClient.ts` 在 `error-fallback` 事件中记录脱敏 `meta.error`，并继续同步 fallback。 |
| 针对性验证 | 已完成 | `workerClient.test.ts` + `clientTelemetry.test.ts` PASS，2 files / 5 tests；`typecheck` PASS；`lint` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8505，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task/ETF池 安全写 | 未完成 | 缺明确 dry-run/apply/cancel/rollback 契约；当前仅 shadow/blocked | 明确安全契约、隔离环境和回滚证据后接入 live-smoke |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约；当前配置写入仍只做 shadow 记录 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前 shadow 交互已二次确认，但仍缺隔离模拟盘账号和回滚证据 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 User-Facing Error Message Redaction 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| 页面错误文案脱敏 | 已完成稳定性补强 | `shared/api/errorMessage` 统一脱敏 token、authorization、secret、password、cookie 等敏感片段后再返回给页面。 |
| Shadow 表单错误 | 已完成 | `ShadowActionPanel` 复用通用错误文案；组件测试验证失败结果不渲染原始 token/password。 |
| 模拟委托错误 | 已完成 | `PaperOrderForm` 提交失败不再直接展示原始 `error.message`，统一走脱敏错误文案。 |
| 针对性验证 | 已完成 | `errors.test.ts` + `wrappers.test.tsx` PASS，2 files / 13 tests；`typecheck` PASS；`lint` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8505，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task/ETF池 安全写 | 未完成 | 缺明确 dry-run/apply/cancel/rollback 契约；当前仅 shadow/blocked | 明确安全契约、隔离环境和回滚证据后接入 live-smoke |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约；当前配置写入仍只做 shadow 记录 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前 shadow 交互已二次确认，但仍缺隔离模拟盘账号和回滚证据 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Route Level Error Boundary 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| `/next/*` 页面级错误边界 | 已完成 | 业务路由统一包 `RouteErrorBoundary`；页面异常只替换当前内容区，不替换整个 AppShell。 |
| Shell 保留与可恢复 | 已完成 | E2E 通过模块拦截让 `/next/analysis` 抛错，验证侧边栏仍可见，并可点击跳转 `/next/playbook`。 |
| 错误脱敏 | 已完成 | route fallback 复用 shared redaction，E2E 验证 token/password 不出现在页面文本。 |
| 针对性验证 | 已完成 | `ErrorBoundary.test.tsx`、`App.test.tsx` PASS；`app-shell-auth.spec.ts` PASS，12 tests；全量单测 PASS，18 files / 71 tests。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；部分页面 similarity 低于切流签收阈值时需人工判断业务布局差异是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 或最新 review PNG，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task/ETF池 安全写 | 未完成 | 缺明确 dry-run/apply/cancel/rollback 契约；当前仅 shadow/blocked | 明确安全契约、隔离环境和回滚证据后接入 live-smoke |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约；当前配置写入仍只做 shadow 记录 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前 shadow 交互已二次确认，但仍缺隔离模拟盘账号和回滚证据 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Error Boundary And Telemetry Redaction 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| 页面错误敏感信息脱敏 | 已完成 | `AppErrorBoundary` 渲染错误 message 前统一 redaction；单测验证 bearer token、access token、password 不出现在 fallback 文本。 |
| telemetry 字符串脱敏 | 已完成 | `recordTelemetry` 除敏感 key 外，还会扫描普通字符串值里的 authorization/token/secret/password/cookie 片段并替换为 `[redacted]`。 |
| K 线错误 telemetry | 已完成 | `KlineChart` downsample/chart error 记录前先脱敏，不把异常消息里的 token/secret 原样写入诊断快照。 |
| 针对性验证 | 已完成 | `ErrorBoundary.test.tsx`、`clientTelemetry.test.ts`、`charts.test.tsx` PASS；`typecheck` PASS；`lint` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；部分页面 similarity 低于切流签收阈值时需人工判断业务布局差异是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task/ETF池 安全写 | 未完成 | 缺明确 dry-run/apply/cancel/rollback 契约；当前仅 shadow/blocked | 明确安全契约、隔离环境和回滚证据后接入 live-smoke |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约；当前配置写入仍只做 shadow 记录 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前 shadow 交互已二次确认，但仍缺隔离模拟盘账号和回滚证据 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Auth Refresh Recovery Hardening 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| 读请求 401 refresh | 已完成 | GET/HEAD 和 `/api/auth/me` 遇到 401 时可用 refresh token 续期，并用新 access token 重试原请求一次。 |
| 写请求重复提交保护 | 已完成 | POST/PUT/PATCH/DELETE 401 不自动 refresh+重试，避免 live-smoke/live 写入重复提交。 |
| 记住登录存储保持 | 已完成 | localStorage/sessionStorage 的 refresh token 位置会在刷新后保留。 |
| 针对性验证 | 已完成 | API client/auth 单测 PASS，2 files / 12 tests；`typecheck` PASS；`lint` PASS；`app-shell-auth.spec.ts` PASS，11 tests。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8504，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `api:parity`、`request:trace`、`screenshot:parity`、`shadow:sample`、auth refresh recovery |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task/ETF池 安全写 | 未完成 | 缺明确 dry-run/apply/cancel/rollback 契约；当前仅 shadow/blocked | 明确安全契约、隔离环境和回滚证据后接入 live-smoke |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约；当前配置写入仍只做 shadow/blocked 记录 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前 shadow 交互已二次确认，但仍缺隔离模拟盘账号和回滚证据 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Backtest Workflow Tabs 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| `/next/backtest` 页签工作流 | 已完成 | 页面收敛为 `提交任务 / 结果概览 / 成交明细 / ETF T0 / 研究闭环`，对齐 backtest style spec。 |
| 任务列表可扫读 | 已完成 | 运行列表补“名称”列；点击任务进入结果概览。 |
| Shadow 写入边界 | 已完成 | 提交、取消、验证/优化继续通过二次确认和 mutation guard；E2E 写请求数组为空。 |
| ETF T0 边界 | 已完成 | 仅展示研究入口和 `blocked_contract_needed` 状态，不触发真实任务。 |
| 针对性验证 | 已完成 | `backtest-data-settings.spec.ts` PASS，3 tests；`typecheck`/`lint` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Shadow Submit And Menu Layer Stability 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| Shadow 提交中防重复 | 已完成 | `ShadowActionPanel` 提交期间禁用按钮并显示 `处理中`；wrapper 单测验证连续点击只调用一次 `onSubmit`。 |
| Shadow 失败恢复 | 已完成 | 提交失败显示错误，保留当前草稿和已确认状态，避免用户重新输入。 |
| AppShell 菜单层级 | 已完成 | topbar/user menu 层级高于页面 sticky 工具条，`app-shell-auth.spec.ts` 验证设置页内可正常退出登录。 |
| 页面 no-write 交互 | 已完成 | `interaction-parity.spec.ts` 覆盖 `/next/backtest`、`/next/data`、`/next/settings`，写请求数组仍为空。 |
| 全量验证 | 已完成 | `api:check` PASS；`typecheck` PASS；`lint` PASS；`test` PASS，17 files / 67 tests；`build` PASS；`e2e` PASS，34 tests；`perf:compare` PASS；`screenshot:parity` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8504，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task/ETF池 安全写 | 未完成 | 缺明确 dry-run/apply/cancel/rollback 契约；当前仅 shadow/blocked | 明确安全契约、隔离环境和回滚证据后接入 live-smoke |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约；当前配置写入仍只做 shadow/blocked 记录 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前 shadow 交互已二次确认，但仍缺隔离模拟盘账号和回滚证据 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Settings Section Shadow Management 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| 风控/LLM 配置写入反馈 | 已完成 shadow/blocked 展示 | `配置写入` 改为调用 guarded mutation；缺契约时返回 `blocked_contract_needed`，不伪造保存成功。 |
| 行业排除管理 | 已完成 shadow 展示 | 新增 `行业排除管理`，使用 typed payload 但真实写入被 mutation guard 阻断。 |
| 因子权重管理 | 已完成 shadow 展示 | 新增 `因子权重管理`，使用 typed payload 但真实写入被 mutation guard 阻断。 |
| 量化参数/策略治理管理 | 已完成 blocked 展示 | 新增 `量化参数管理`、`策略治理管理`，只记录本地意图，等待安全写契约。 |
| no-write 边界 | 已完成 | E2E 覆盖 settings 新增管理入口后写请求数组仍为空。 |
| 针对性验证 | 已完成 | `typecheck`、`lint`、mutation 单测、settings/data/backtest E2E 均 PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；新增 settings shadow 面板需下一轮截图 parity 刷新 | 用户逐页查看最新 review PNG，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| settings section 真实写入 | 未完成 | 风控、行业排除、因子、量化参数、策略治理均缺保存、回显、审计和回滚安全契约 | 明确分区保存 API、隔离数据、审计回显和回滚策略后接入 live-smoke |
| MFA setup/enable/disable 真实写入 | 未完成 | 当前只展示状态和记录 shadow 意图；缺账号安全写入、回显和回滚契约 | 明确隔离账号、TOTP setup/enable/disable API 契约、审计和回滚证据后接入 live-smoke |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task/ETF池 安全写 | 未完成 | 缺明确 dry-run/apply/cancel/rollback 契约；当前仅 shadow/blocked | 明确安全契约、隔离环境和回滚证据后接入 live-smoke |
| paper pause/resume/reconcile | 未完成真实写 | 当前 shadow 交互已二次确认，但仍缺隔离模拟盘账号和回滚证据 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Settings MFA Shadow Management 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| `/next/settings` MFA 状态 | 已完成 shadow parity | 账户与安全分区展示 TOTP 当前状态，来自 auth/me 用户字段。 |
| MFA 管理入口 | 已完成 shadow 展示 | 新增 `MFA 管理` 面板，支持记录 setup/disable 意图、动态口令和原因，必须二次确认。 |
| no-write 边界 | 已完成 | MFA 面板显示 `blocked_contract_needed`，E2E 只验证本地 shadow 结果，不调用真实 TOTP 写接口。 |
| 针对性验证 | 已完成 | `backtest-data-settings.spec.ts` PASS，3 tests；`typecheck` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8505，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| MFA setup/enable/disable 真实写入 | 未完成 | 当前只展示状态和记录 shadow 意图；缺账号安全写入、回显和回滚契约 | 明确隔离账号、TOTP setup/enable/disable API 契约、审计和回滚证据后接入 live-smoke |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task/ETF池 安全写 | 未完成 | 缺明确 dry-run/apply/cancel/rollback 契约；当前仅 shadow/blocked | 明确安全契约、隔离环境和回滚证据后接入 live-smoke |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约；当前配置写入和 MFA 变更仍只做 shadow 记录 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前 shadow 交互已二次确认，但仍缺隔离模拟盘账号和回滚证据 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Kline Worker Downsample Adapter 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| KlineChart worker downsample | 已完成 | `KlineChart` 接入 `downsampleChartPoints`，超过阈值时走 worker，失败/不可用时 sync fallback。 |
| 旧异步结果防护 | 已完成 | sequence guard 防止快速切换标的后旧采样结果覆盖新图；卸载后不再写入图表。 |
| 显示层边界 | 已完成 | 只处理图表点数组显示，不改变分析响应、后端数据、生产排序或策略判断。 |
| 针对性验证 | 已完成 | chart/worker 单测 PASS，3 files / 11 tests；`typecheck` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Chart Downsample Endpoint Stability 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| 图表降采样端点保留 | 已完成 | `downsample` 改为首尾保留的等距采样，不均匀点数下仍保留最新尾点。 |
| 单点降采样 | 已完成 | `maxPoints=1` 返回最新点，避免只显示早期旧点。 |
| 显示层边界 | 已完成 | 只影响 K 线/图表显示和 worker fallback，不改变后端、策略、排序或回测真实结果。 |
| 针对性验证 | 已完成 | worker/chart/analysis 单测 PASS，4 files / 12 tests；`typecheck` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Analysis Batch Worker Sort 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| `/next/analysis` 批量展示排序 | 已完成 | 批量分析结果先映射为展示行，再通过 worker `sort` 按 `score desc` 稳定排序；同分保持原顺序，缺失分数靠后。 |
| Worker fallback | 已完成 | Worker 不可用、超时、messageerror 或返回 `ok=false` 时回退同步排序；不会让页面空白。 |
| no-write/生产边界 | 已完成 | 排序仅用于分析页表格展示；不影响 `priority_board`、`production_score`、生产排序或策略判断。 |
| 针对性验证 | 已完成 | worker 单测 PASS，2 files / 6 tests；`typecheck`/`lint` PASS；`analysis-playbook.spec.ts` PASS，3 tests。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 兼容跳转 Query 保留后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| `/next/*` 兼容跳转上下文 | 已完成 | `/next/emotion`、`/next/low-buy`、`/next/strategy`、`/next/performance` 跳转时保留 query/search；`App.test.tsx`、`keyboardShortcuts.test.ts` 和 `app-shell-auth.spec.ts` 均 PASS。 |
| AppShell 导航测试覆盖 | 已完成 | `keyboardShortcuts.test.ts` 覆盖 Cmd/Ctrl+K 与 Cmd/Ctrl+1~8；`app-shell-auth.spec.ts` 覆盖 Command Palette 页面跳转和 390x844 移动导航。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 偏低需要用户确认是否接受机甲/完整 tab 布局 | 用户逐页查看 visual review 截图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 No Fake Chart Data / Copy Clarity 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| `/next/analysis` K 线空数据 | 已完成 | 无真实后端 bars 时不再回退测试样例曲线，`chartPoints(null)` 和无 bars 快照返回空数组。 |
| `/next/paper` 盈亏文案 | 已完成 | `unrealized_pnl` 可见文案改为“浮动盈亏”，避免误解为“功能未实现”；收益字段与口径不变。 |
| 单测覆盖 | 已补 | 新增 `analysisModel.test.ts`，最新全量 Vitest 13 files / 44 tests PASS。 |
| 最新新前端全链 | 已完成 | `api:check`、`typecheck`、`lint`、`test`、`build`、`e2e`、`perf:compare`、`screenshot:parity` 全 PASS；E2E 27/27。 |
| 最新截图 parity | 已完成 | 9 个 `/next/*` 页面 1440/1280/768/390 全 captured；最新 `/next/analysis` similarity 0.9325，且无导航错误、错误边界、JS 异常或失败 API 响应。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收` | 用户逐页查看并签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Auth Operation Adapter 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| Auth feature URL 收敛 | 已完成 | `features/auth/authModel.tsx` 改为走 `shared/api/auth.ts` 的 `authApi`，不再在 feature 层拼 `/api/auth/*`。 |
| Auth OpenAPI 类型收敛 | 已完成 | `AuthUser`、`AuthTokenResponse`、`AuthMfaSetupResponse` 等由 `shared/api/types.ts` 统一导出，类型仍来自 OpenAPI generated schema。 |
| 测试样例数据隔离 | 已完成 | 删除未使用的 `shared/testing/fixtures.ts`，避免样例优先榜/K 线数据未来误入业务页 fallback。 |
| 针对性验证 | 已完成 | `npm run typecheck` PASS；auth targeted tests 2 files / 3 tests PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收` | 用户逐页查看并签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Client Telemetry 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| 前端诊断 telemetry | 已完成 | 新增 `shared/telemetry/clientTelemetry.ts`，API/SSE/Worker/Chart/Mutation/UI 事件进入内存环形缓冲；敏感 meta 自动脱敏；不持久化、不上报后端。 |
| perf telemetry 输出 | 已完成 | `npm run perf:compare` 会输出每个核心路由的 `telemetry.byKind` 和 recent 事件，便于检查请求、SSE、Worker、Chart、Mutation 是否异常增长。 |
| telemetry 单测 | 已完成 | `clientTelemetry.test.ts` 覆盖 byKind 计数、敏感字段脱敏、诊断快照暴露；全量 Vitest 12 files / 42 tests PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收` | 用户逐页查看并签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token、fixture 和本地对照 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Client Telemetry 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| 前端内存 telemetry | 已完成 | 新增 `shared/telemetry`，覆盖 API/SSE/Worker/Chart/Mutation/UI 六类事件；只保留浏览器内存快照，不上报后端。 |
| telemetry 脱敏 | 已完成 | token、secret、password、authorization、cookie、credential 等 meta key 自动脱敏；不记录 payload/body/auth token。 |
| API 错误计数去重 | 已完成 | `requestJson` 对最终 HTTP 错误只记录一次 `http_error`；最新 `perf:compare` 未登录 profile 下每路由只出现 1 条 `/api/auth/me` 401。 |
| mutation guard 诊断 | 已完成 | 记录 shadow-only、blocked_contract_needed、write-disabled、mode-blocked、permission-blocked、sent；缺契约写入仍不发真实写。 |
| 最新新前端全链 | 已完成 | `api:check`、`typecheck`、`lint`、`test`、`build`、`e2e`、`perf:compare`、`screenshot:parity` 全 PASS；Vitest 12 files / 42 tests，E2E 27/27。 |
| 最新截图 parity | 已完成 | 9 个 `/next/*` 页面 1440/1280/768/390 全 captured，无导航错误、错误边界、JS 异常或失败 API 响应。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8504，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 和最新截图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token、fixture 和本地对照，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Query Cancellation / Resource Cleanup 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| TanStack Query cancellation | 已完成 | `/next/strategy-tracking` 通用 operation query 已传 TanStack `signal`；`/next/playbook` 已迁入 TanStack Query，并把 signal 传到 low-buy 读链路。 |
| 手动分析请求取消 | 已完成 | `/next/analysis` 单票/批量请求使用 `AbortController`；重复触发或切页会取消旧请求，避免旧响应回写。 |
| API wrapper signal 透传 | 已完成 | `requestOperation` 和 BFF/常用只读 wrapper 透传测试通过；`client.test.ts` 新增 abort/wrapper signal 覆盖。 |
| SSE 生命周期 | 已完成代码级证据 | `startQuoteSse` 同 URL ref-count，cleanup 绑定 source；SSE 单测覆盖共享连接、最终 cleanup close、JSON upsert、坏 JSON error；当前页面 request trace EventSource 仍为 0。 |
| Toast/Dialog 生命周期 | 已完成 | Toast 同 id 替换清旧 timer；Dialog 延迟 focus timer 在 close/unmount 清理；wrapper tests PASS。 |
| Chart/Canvas 释放 | 已完成 | Kline 空数据 `setData([])`；Lightweight Charts `remove()`、ECharts `dispose()`、机甲 Canvas RAF/resize cleanup 和 reduced-motion 均有单测。 |
| 新前端全链 | 已完成 | `api:check`、`typecheck`、`lint`、`test`、`build`、`e2e`、`perf:compare`、`screenshot:parity` 全 PASS；Vitest 11 files / 40 tests，E2E 27/27。 |
| 旧前端全链 | 已完成 | `api:check`、`typecheck`、`lint`、`test -- --run`、`build` 全 PASS；Vitest 80 files / 274 tests。 |
| 最新 request/SSE | 已完成 | `START_LEGACY_FRONTEND=1 npm run request:trace` PASS；9 个新路由请求数均不高于旧前端，EventSource 全为 0。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8504，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 和最新截图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token、fixture 和本地对照，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 QA Gate 加严后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| 截图验收错误检测 | 已完成 | `screenshot:parity` 现在会记录并阻断 `/next/*` 的错误边界、未捕获 JS 异常和失败 API 响应；最新 9 个新路由这些字段均为空。 |
| `/next/settings` 首屏稳定性 | 已完成 | 运行诊断改为“治理”页签懒加载；`request:trace` 中 `/next/settings` 新前端首屏 API 请求数为 1，旧前端为 8，EventSource 为 0。 |
| Shadow sample 证据字段 | 已完成 | `shadow:sample` 汇总已包含 `navigation_error`、`app_error`、`page_errors`、`failed_api_responses`，并要求 `/next/*` 全为空才通过。 |
| 两交易日 shadow run | 已完成 | 使用已有本地 shadow token 避免注册 429，`shadow:sample` PASS；`shadow:aggregate` PASS，交易日 `2026-06-05`、`2026-06-06`，`sample_count=5`。 |
| 新旧前端最终命令 | 已完成 | 新前端全链 PASS；旧前端 `api:check/typecheck/lint/test/build` 全 PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8504，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 稳定性与权限硬化后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| API 请求稳定性 | 已完成前端内闭环 | 15s timeout、AbortController、offline/network/timeout/aborted 分类、GET/HEAD 429/5xx 单次保守重试、Retry-After 上限和可取消等待；`client.test.ts` 7 tests PASS。 |
| Query retry 放大风险 | 已完成 | TanStack Query 不再对 `ApiError`/`ApiTransportError` 叠加重试；`request:trace` 9 路由请求数仍低于旧前端。 |
| 写入模式硬保护 | 已完成 | mutation client 同时检查 write flag、write mode、contract status、requiresAdmin；`mutations.test.ts` 6 tests PASS。 |
| `/next/settings` admin-only 权限 | 已完成 | 非 admin 隐藏 `开关/治理/Audit` 和“功能开关写入”；feature flag mutation 绑定 `auth.isAdmin`；E2E guard PASS。 |
| `/next/data` 与 `/next/paper` 权限负例 | 已完成 | 新增非 admin `/next/data`、无 `can_paper_trade` `/next/paper` E2E，均 PASS。 |
| Worker timeout/listener cleanup | 已完成 | timeout/error/messageerror 均 fallback 并清理 listener，新增 `disposeComputeWorker()`；`workerClient.test.ts` 2 tests PASS。 |
| 最新新前端全链 | 已完成 | `api:check`、`typecheck`、`lint`、`test`、`build`、`e2e`、`perf:compare`、`screenshot:parity` 全 PASS；E2E 27/27，Vitest 8 files / 30 tests。 |
| 最新旧新 request/SSE | 已完成 | `START_LEGACY_FRONTEND=1 npm run request:trace` PASS；9 个新路由请求数均低于旧前端，EventSource 全为 0。 |
| 最新旧新视觉 review | 已生成 | `START_LEGACY_FRONTEND=1 npm run screenshot:parity && npm run visual:review` PASS；9 页 `ready-for-human-signoff`，但仍需人工签收。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Command Palette 策略跳转后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| Command Palette 策略跳转 | 已完成 | 输入 `首板` 跳转 `/next/playbook?strategy=first_board`，输入 `N形` 跳转 `/next/strategy-tracking?strategy_key=n_pattern_long_wash`；`app-shell-auth.spec.ts` 新增策略跳转 E2E 并通过。 |
| 策略 query 同步 | 已完成 | `/next/playbook` 响应 `strategy` query 并同步策略页签；`/next/strategy-tracking` 响应 `strategy_key` query 并同步筛选。 |
| 策略边界 | 已完成 | 策略命令 registry 仅作导航索引，不保存生产排序、评分或策略真值；不改变 `priority_board`、`production_score`、生产策略语义或写入模式。 |
| 针对性验证 | 已完成 | `npm run typecheck` PASS；`npm test -- --run src/shared/config/strategyCommands.test.ts` PASS，1 file / 3 tests；`npm run e2e -- tests/e2e/app-shell-auth.spec.ts` PASS，8 tests。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 AppShell Auth/Navigation Usability 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| 用户菜单 | 已完成 | AppShell 顶栏新增账户菜单，支持“系统设置”和“退出登录”；替代原用户名标签 + 独立退出按钮，延续旧前端 Topbar 的用户菜单能力。 |
| 登录后深链路恢复 | 已完成 | `AuthGuard` 的 `redirect` 现在登录/注册成功后会回到白名单 `/next/*` 原始路径；外链、`/login` 等非 `/next/*` redirect 回落 `/next/monitor`。 |
| 输入态快捷键防误触 | 已完成 | `Cmd/Ctrl+K`、`Cmd/Ctrl+1~8` 在 input/textarea/select/contenteditable 内不触发全局命令面板或页面跳转。 |
| 针对性验证 | 已完成 | `npm run typecheck` PASS；`npm run lint` PASS；`npm test -- --run src/app/keyboardShortcuts.test.ts src/features/auth/LoginPage.test.ts` PASS，2 files / 5 tests；`npm run e2e -- tests/e2e/app-shell-auth.spec.ts` PASS，10 tests。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Command Palette Focus Trap 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| Command Palette focus trap | 已完成 | Command Palette 复用 `shared/ui/dialogFocus`，打开后焦点进入搜索框，Tab/Shift+Tab 限制在弹层内，Esc 关闭并恢复到触发按钮。 |
| Wrapper/a11y 收敛 | 已完成 | 保留现有视觉样式和命令行为，不引入第三方默认样式；补 `aria-label=\"打开全局搜索\"`，满足可访问触发入口。 |
| 针对性验证 | 已完成 | `npm run typecheck` PASS；`npm run lint` PASS；`npm run e2e -- tests/e2e/app-shell-auth.spec.ts` PASS，11 tests，其中包含 focus trap/焦点恢复用例。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Command Palette Shared UI Wrapper 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| Command Palette shared/ui wrapper | 已完成 | 新增 `frontend-next/src/shared/ui/CommandPalette.tsx`，弹层 DOM、输入框、列表、footer、Enter 执行、Esc/Tab focus 生命周期均走 shared wrapper。 |
| Feature 分层 | 已完成 | `features/trading-workspace/CommandPalette.tsx` 只保留页面/策略/股票代码命令构造和导航执行；不再直接渲染弹层 UI 或手写 focus 行为。 |
| 行为/视觉保持 | 已完成 | 继续使用 `.tq-command*` 旧兼容样式和原有文案，不引入第三方默认样式，不新增页面描述信息。 |
| 针对性验证 | 已完成 | `npm run typecheck` PASS；`npm run lint` PASS；`npm test -- --run src/shared/ui/__tests__/wrappers.test.tsx src/app/keyboardShortcuts.test.ts src/features/auth/LoginPage.test.ts src/shared/config/strategyCommands.test.ts` PASS，4 files / 16 tests；`npm run e2e -- tests/e2e/app-shell-auth.spec.ts` PASS，11 tests。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Paper Order Form Usability 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| `/next/paper` 委托推荐导入 | 已完成 | “推荐导入占位”改为“导入推荐”，可从当前订单/持仓回填草稿字段；不读取或改变生产排序。 |
| `/next/paper` 持仓导入与数量快捷 | 已完成 | 持仓卡片可导入卖出草稿；`+100/+500/+1000/1/4 仓/1/2 仓/全仓` 按 100 股手数取整。 |
| `/next/paper` 费用估算 | 已完成 | 二次确认摘要展示金额、费用和预计占用/回收，提交前可复核。 |
| shadow/no-write 边界 | 已完成 | 提交仍走 `mutationClient.createPaperOrder`，默认不发真实写请求；`paper-mecha.spec.ts` 验证写请求数组为空。 |
| 针对性验证 | 已完成 | `npm run typecheck` PASS；`npm run lint` PASS；`npm run e2e -- tests/e2e/paper-mecha.spec.ts` PASS，2 tests。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Analysis To Paper Shadow Handoff 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| `/next/analysis` 模拟下单入口 | 已完成 | 分析结果出现后，“决策摘要”可点击“模拟下单”进入 `/next/paper?source=analysis...`。 |
| `/next/paper` 草稿接收 | 已完成 | `source=analysis` search 会自动打开一次模拟委托弹窗，并填充代码、名称、数量、价格、策略和理由；非 analysis 来源不会自动弹窗。 |
| shadow/no-write 边界 | 已完成 | E2E 写请求数组只包含 `POST /api/analyze`，没有 paper order 写入；提交逻辑仍受默认 shadow mutation guard 保护。 |
| 针对性验证 | 已完成 | `npm run typecheck` PASS；`npm run lint` PASS；目标单测 PASS，3 files / 12 tests；`npm run e2e -- tests/e2e/analysis-playbook.spec.ts tests/e2e/paper-mecha.spec.ts` PASS，5 tests。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Symbol Analysis Navigation 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| `/next/analysis?symbol=` | 已完成 | 分析页读取 `symbol` query 并填入“分析代码”；Command Palette 输入 6 位代码后 E2E 验证输入框为目标代码。 |
| `/next/monitor` 去分析 | 已完成 | 生产优先榜选中标的后可点“分析”进入 `/next/analysis?symbol=...`；返回后保留选中标的。 |
| `/next/playbook` 去分析 | 已完成 | 候选详情可点“分析”进入 `/next/analysis?symbol=...`；返回后保留 `strategy + symbol` 上下文。 |
| URL 稳定性 | 已完成 | Router search 改为普通 query 序列化，避免字符串被 JSON 引号编码。 |
| 针对性验证 | 已完成 | `npm run typecheck` PASS；`npm run lint` PASS；相关 E2E PASS，16 tests；`npm run build` PASS；`git diff --check` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Shadow Action Draft Refresh 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| shared shadow 表单草稿刷新 | 已完成 | `ShadowActionPanel` 的父级字段变化会重置草稿、确认状态和结果文案，避免选中不同标的后提交旧草稿。 |
| no-write 边界 | 已完成 | 修复只影响本地表单状态；提交仍由各页面原有 shadow/mutation guard 控制。 |
| 针对性验证 | 已完成 | wrapper 单测 PASS，1 file / 9 tests；monitor + analysis/playbook E2E PASS，5 tests；`typecheck`/`lint` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 dry-run/apply/cancel 契约和隔离环境 |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Data Console Maintenance Workbench 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| `/next/data` 运维页签 | 已完成 | 数据运维收敛为 `SLA / 覆盖 / 任务 / Worker / 修复 / 检查 / 池管理`，采集、补齐、修复、检查和池管理均在对应页签内。 |
| `ETF/股票池` 维护边界 | 已完成 shadow 展示 | 新增池管理页签，明确 `blocked_contract_needed`，只做本地记录，不参与生产排序、信号计算、`production_score` 或 `priority_board`。 |
| no-write 边界 | 已完成 | E2E 覆盖采集、历史补齐、数据修复、个股检查、池变更，写请求数组仍为空。 |
| 针对性验证 | 已完成 | wrapper 单测 PASS，1 file / 9 tests；`backtest-data-settings.spec.ts` PASS，3 tests；`typecheck` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task/ETF池 安全写 | 未完成 | 缺明确 dry-run/apply/cancel/rollback 契约；当前仅 shadow/blocked | 明确安全契约、隔离环境和回滚证据后接入 live-smoke |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Strategy Tracking Filter Drawer 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| `/next/strategy-tracking` 筛选抽屉 | 已完成 | 常驻大筛选面板收敛为模式、板块、筛选摘要和“筛选条件”按钮；完整筛选项进入 `shared/ui/Drawer`。 |
| 筛选摘要 | 已完成 | 首屏展示结果数、关键词、策略、状态、信号、复盘等 active filters，抽屉应用后列表即时过滤。 |
| no-write 边界 | 已完成 | 筛选/详情/复盘中心 E2E 后写请求数组为空；复盘日志仍受 mutation guard 阻断。 |
| 针对性验证 | 已完成 | `strategy-tracking.spec.ts` PASS，1 test；`typecheck` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task/ETF池 安全写 | 未完成 | 缺明确 dry-run/apply/cancel/rollback 契约；当前仅 shadow/blocked | 明确安全契约、隔离环境和回滚证据后接入 live-smoke |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Settings Layout IA 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| `/next/settings` 设置 IA | 已完成 | 顶栏、左侧分区导航、右侧内容区已落地，对齐 settings style spec 的桌面布局。 |
| Admin 分区 | 已完成 shadow parity | 功能开关、策略治理、诊断与审计继续按 admin 权限显示；E2E 覆盖核心分区跳转。 |
| 写入归属 | 已完成 | 功能开关写入收回“功能开关”分区，配置写入收回“交易偏好”分区；非 feature-flag 写入仍 shadow/blocked。 |
| 针对性验证 | 已完成 | `backtest-data-settings.spec.ts` PASS，3 tests；`typecheck` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task/ETF池 安全写 | 未完成 | 缺明确 dry-run/apply/cancel/rollback 契约；当前仅 shadow/blocked | 明确安全契约、隔离环境和回滚证据后接入 live-smoke |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约；当前配置写入仍只做 shadow 记录 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前保持 shadow/blocked，避免影响账户状态 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Paper Guarded Account Actions 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| `/next/paper` 高风险动作确认 | 已完成 | 暂停/恢复账户、自动交易控制、对账/修复动作均先进入二次确认，再记录本地意图。 |
| blocked 契约可见 | 已完成 | 动作条显示 `blocked_contract_needed`，避免误解为真实账户写入。 |
| no-write 边界 | 已完成 | `paper-mecha.spec.ts` 验证机甲/API 失败可见、暂停账户二次确认、委托二次确认后写请求数组为空。 |
| 针对性验证 | 已完成 | `paper-mecha.spec.ts` PASS，2 tests；`typecheck` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8503，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task/ETF池 安全写 | 未完成 | 缺明确 dry-run/apply/cancel/rollback 契约；当前仅 shadow/blocked | 明确安全契约、隔离环境和回滚证据后接入 live-smoke |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约；当前配置写入仍只做 shadow 记录 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前 shadow 交互已二次确认，但仍缺隔离模拟盘账号和回滚证据 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 Paper Mecha Reduced Motion 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| `/next/paper` 机甲 Canvas 动效 | 已完成稳定性补强 | 系统 reduced motion 运行时开启后立即取消 RAF、移除 resize listener，并清理 Canvas；关闭后按当前状态恢复动效。 |
| display/review 边界 | 已完成 | 机甲头像、HUD、粒子和日志仍只作为模拟盘 display/review，不参与生产排序、信号计算、模拟委托判断、`production_score` 或 `priority_board`。 |
| 针对性验证 | 已完成 | `PaperMechaParticles.test.tsx` PASS，1 file / 3 tests；`typecheck` PASS；全量 `test` PASS，18 files / 72 tests。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8505，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task/ETF池 安全写 | 未完成 | 缺明确 dry-run/apply/cancel/rollback 契约；当前仅 shadow/blocked | 明确安全契约、隔离环境和回滚证据后接入 live-smoke |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约；当前配置写入仍只做 shadow 记录 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前 shadow 交互已二次确认，但仍缺隔离模拟盘账号和回滚证据 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |

## 2026-06-06 SSE Reconnect Stability 后最新状态

本轮又补齐：

| 项 | 最新状态 | 证据 |
|---|---|---|
| quote SSE 断连恢复 | 已完成稳定性补强 | `EventSource.onerror` 后关闭旧 source，并按 1s 起步、最大 15s 的退避重连。 |
| no-duplicate SSE | 已完成 | 同 URL active source 或 pending reconnect 均共享订阅计数；新增订阅不会创建重复 EventSource。 |
| 离页释放 | 已完成 | 最后订阅者 cleanup 会取消 pending reconnect timer 并关闭 active source，避免离页后后台重连。 |
| 针对性验证 | 已完成 | `sseClient.test.ts` PASS，1 file / 4 tests；`typecheck` PASS。 |

当前仍未完成：

| 项 | 状态 | 阻断/原因 | 后续动作 |
|---|---|---|---|
| 旧新视觉人工签收 | 未完成 | review PNG 已生成，`visual-signoff` 仍为 `待签收`；`/paper` similarity 0.8505，需要用户确认机甲/完整 tab 布局是否接受 | 用户逐页查看 `docs/reports/frontend-next-visual-review-2026-06-05/review-*.png` 中最新 9 张图，签收或指定继续调整项 |
| 正式验收账号复跑 | 未完成 | 当前最终证据主要来自本地 shadow token 和 E2E fixture，不等同正式账号 cutover 验收 | 提供正式验收账号/token 后复跑 `request:trace`、`screenshot:parity`、`shadow:sample` |
| strategy review/trade journal 安全写 | 未完成 | 缺明确可回滚安全写契约 | 明确 API 契约、隔离数据和回滚方式后接入 live-smoke |
| data repair/backfill/task/ETF池 安全写 | 未完成 | 缺明确 dry-run/apply/cancel/rollback 契约；当前仅 shadow/blocked | 明确安全契约、隔离环境和回滚证据后接入 live-smoke |
| settings 非 feature-flag 写入 | 未完成 | 缺保存/回显/回滚安全契约；当前配置写入仍只做 shadow 记录 | 明确分区保存 API、回滚策略、权限 gate |
| paper pause/resume/reconcile | 未完成真实写 | 当前 shadow 交互已二次确认，但仍缺隔离模拟盘账号和回滚证据 | 使用隔离模拟盘账号补 live-smoke 和回滚证据 |
| backtest cancel/validate/optimize | 未完成真实写 | 当前保持 shadow/blocked，避免任务状态假成功 | 明确任务取消/验证/优化回滚方式后接入 |
| cutover/部署 | 未执行 | 本轮未部署未切流；仍需要单独 cutover 授权 | 获得用户明确 cutover 授权后按 runbook 执行 |
| 飞书通知 | 未完成 | `lark-cli` 无用户登录且无目标会话 | 提供 `chat_id`/`user_id` 或完成飞书登录后发送 |
