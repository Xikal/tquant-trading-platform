# Frontend Next Solid Acceptance

状态：Shadow 前端阶段验收
日期：2026-06-05
范围：`frontend-next/` 并行新前端、P0-P7 本地验证

## 2026-06-07 自用可用性收尾

用户将目标口径调整为“满足自用即可，保证各功能都正常可用”。本轮据此完成一轮低风险收尾：不部署、不切流、不修改旧 `frontend/`、不修改 `strategy_policy.py`；后端仅做安全写契约最小改动（审计、review-only 记录、runtime task cancel、OpenAPI 同步），不改变生产策略语义、生产排序、`priority_board`、`production_score` 口径。

自用结论：`frontend-next/` 的 `/next/*` 页面当前可作为本地自用工作台使用。核心读取、页面跳转、登录守卫、权限守卫、分析、选股宝典、模拟盘、策略跟踪、回测、数据中心和设置页交互均通过 E2E；安全写 readiness 和隔离 rollback 已在本地通过。默认写入 flag 仍关闭，不会影响生产排序、`priority_board`、`production_score` 或生产策略口径。

本轮自用验收：

| Gate | 结果 | 证据 |
|---|---|---|
| 页面交互自用验收 | PASS | `npm run e2e`：44 tests passed，覆盖 9 个 `/next/*` 页面、登录/会话恢复、权限、移动导航、命令面板、模拟盘机甲、分析到模拟委托、数据/设置错误态。 |
| 基础质量 | PASS | `npm run api:check`、`npm run typecheck`、`npm run lint`、`npm test -- --run`、`npm run build` 均通过；单测 19 files / 86 tests。 |
| 请求/SSE | PASS | `npm run request:trace`：9 个 `/next/*` 路由均无导航错误；EventSource 全为 0；核心页面请求数稳定。 |
| 性能 | PASS（本地） | `npm run perf:compare`：`/next/monitor` 832ms/230 DOM、`/next/monitor/market` 576ms/271 DOM、`/next/paper` 688ms/398 DOM、`/next/strategy-tracking` 693ms/361 DOM；SSE 0。 |
| CSS 预算 | PASS | `npm run css:budget`：dist CSS gzip 47925 bytes，`!important` 51，预算未超。 |
| 正式写入 readiness | PASS（本地证据齐全） | `npm run write:readiness`：13 contracts，12 production-ready，0 blocked，1 cutover-excluded；rollback evidence `ok`，`cutover_ready=true`。 |

自用模式下的写入边界：

- 已有本地隔离回滚证据的写操作保留 guarded adapter 能力，但默认仍由写入 flag 控制。
- `playbook lifecycle`、`strategy review record`、`data task`、`data repair` 已补后端审计、回滚/取消、403 和读回一致证据；正式环境 cutover 前仍需用正式 admin token 复跑。
- `databaseMigrate` 继续 cutover-excluded，不作为前端默认能力开放。

## 2026-06-07 最新验收状态

本轮继续完成 cutover blocker remediation 的可落地部分；未部署、未切流。旧 `frontend/` 生产代码、`strategy_policy.py` 均未修改；后端仅做安全写契约最小改动，生产策略语义、生产排序、`production_score`、`priority_board` 口径未改变。

| Gate | 最新结果 | 证据 |
|---|---|---|
| 新前端基础命令 | PASS | `npm run api:check`、`npm run typecheck`、`npm run lint`、`npm test -- --run`、`npm run build` 均通过；单测 19 files / 86 tests。 |
| API cutover readiness | PASS（本地 admin-token 环境） | `API_BASE=http://127.0.0.1:8011 ADMIN_API_TOKEN=test-admin-token FRONTEND_ADMIN_TOKEN=test-admin-token npm run api:cutover-readiness`：6 probes / 0 failed。 |
| 安全写 rollback smoke | PASS（本地隔离） | `API_BASE=http://127.0.0.1:8011 ADMIN_API_TOKEN=test-admin-token FRONTEND_ADMIN_TOKEN=test-admin-token FRONTEND_NEXT_LOCAL_ADMIN_PROMOTE=1 npm run write:rollback -- --all --isolated`：全部 live_results `ok=true`。 |
| 安全写 readiness | PASS（本地证据齐全） | `npm run write:readiness`：13 contracts，12 production-ready，0 blocked，1 cutover-excluded；rollback evidence `ok`，`cutover_ready=true`。 |
| CSS 预算/未引用报告 | PASS | `npm run css:budget`、`npm run css:unused-report` 通过；dist CSS gzip 47925 bytes，`!important` 51。 |

安全写当前状态：

| 类别 | Contract |
|---|---|
| production-ready | `FNX-SW-AUTH-MFA`、`FNX-SW-WATCHLIST`、`FNX-SW-PAPER-ORDER`、`FNX-SW-PAPER-ACCOUNT`、`FNX-SW-TRADE-JOURNAL`、`FNX-SW-BACKTEST-TASK`、`FNX-SW-SETTINGS-SECTION`、`FNX-SW-FEATURE-FLAG`、`FNX-SW-PLAYBOOK-LIFECYCLE`、`FNX-SW-STRATEGY-REVIEW`、`FNX-SW-DATA-TASK`、`FNX-SW-DATA-REPAIR` |
| blocked | 无 |
| cutover-excluded | `FNX-SW-DATABASE-MAINTENANCE` 中 `databaseMigrate`；只允许 `databaseCheck` 作为只读检查证据 |

结论：`frontend-next/` 可继续 `/next/*` 本地使用和联调；本地 cutover readiness 脚本已通过。仍不可自动正式 cutover：需要用户单独授权，并用正式 admin token/environment 复跑 readiness、rollback 和 API gate。

## 1. 初始 Git Status

首次开始本轮大任务前在仓库根目录执行：

```bash
cd /Users/j/Documents/gupiao
git status --short
```

结果：无输出，工作区干净。

本次继续收尾前再次执行 `git status --short`，工作区已有本轮生成物：

```text
?? docs/frontend-next-architecture-design-2026-06-05.md
?? docs/frontend-next-cutover-runbook-2026-06-05.md
?? docs/frontend-next-feature-parity-matrix-2026-06-05.md
?? docs/frontend-next/
?? docs/reports/frontend-next-acceptance-2026-06-05.md
?? docs/reports/frontend-next-baseline-2026-06-05.md
?? docs/reports/frontend-next-open-items-2026-06-05.md
?? docs/reports/frontend-next-screenshots-2026-06-05/
?? docs/superpowers/plans/2026-06-05-rust-realtime-backtest-workers.md
?? frontend-next/
```

其中 `docs/superpowers/plans/2026-06-05-rust-realtime-backtest-workers.md` 不是本轮 frontend-next 交付物，未修改。

## 2. frontend-next 架构和目录

新增独立前端目录：`frontend-next/`。

核心结构：

- `src/app/`：Solid app shell、TanStack Router route tree、providers、error boundary。
- `src/generated/api-types.ts`：从 `../docs/contracts/openapi.json` 生成。
- `src/shared/api/`：typed API client、auth header、query keys、error helpers、flag-guarded mutation adapter。
- `src/shared/ui/`：Button、Panel、Tabs、Tag、MetricGrid、DataGrid、VirtualList、StockCard 等 wrapper。
- `src/shared/realtime/`：Solid signals quote store、SSE client、market session helpers。
- `src/shared/workers/`：Worker protocol、sync fallback、display filter/downsample worker。
- `src/shared/charts/`：Lightweight Charts K-line adapter、ECharts low-frequency adapter。
- `src/features/`：`monitor-action`、`monitor-market`、`paper`、`strategy-tracking`、`analysis`、`playbook`、`backtest`、`data-console`、`settings`。
- `scripts/`：`perf-profile.mjs`、`screenshot-parity.mjs`、`request-trace.mjs`、`api-parity.mjs`、`shadow-sample.mjs`、`write-rollback-smoke.mjs`、`script-utils.mjs`。
- `tests/e2e/`：`/next/*` smoke tests 和 no-write shadow interaction tests。

## 3. 新旧功能 Parity 矩阵

| 旧路由 | 新路由 | 状态 | 说明 |
|---|---|---|---|
| `/monitor` | `/next/monitor` | Shadow shell ready | 读取 monitor BFF；`priority_board` 保持服务端顺序，不前端重排。 |
| `/monitor/market` | `/next/monitor/market` | Shadow shell ready | 市场总闸、宽度、脉冲、板块/ETF、复盘结构已落位。 |
| `/paper` | `/next/paper` | Shadow shell ready | 账户/持仓/机甲/执行日志只读展示；模拟委托已补 no-write shadow 交互。 |
| `/strategy-tracking` | `/next/strategy-tracking` | Shadow shell ready | 跟踪表/复盘结构只读展示；复盘记录已补 no-write shadow 交互，不写回生产排序。 |
| `/analysis` | `/next/analysis` | Style shell ready | 分析输入、关键位、K 线结构落位；深度业务交互待对齐。 |
| `/playbook` | `/next/playbook` | Style shell ready | 生产策略页签结构落位；研究策略不混入生产选股。 |
| `/backtest` | `/next/backtest` | Shadow shell ready | 回测列表接口读取；回测提交已补 no-write shadow 交互。 |
| `/data` | `/next/data` | Style shell ready | 数据中心 admin-only 结构落位；采集任务已补 no-write shadow 交互。 |
| `/settings` | `/next/settings` | Shadow shell ready | 设置 BFF 读取；feature flag 写入已补 no-write shadow 交互。 |

结论：本轮完成 `/next/*` shadow 页面、工程命令闭环、写操作 no-write shadow 交互，以及真实写接口的 flag-guarded adapter。默认写入 flag 关闭，cutover 仍未执行。

## 3.1 写入 Adapter 边界

- `frontend-next/src/shared/api/mutations.ts` 已使用 generated API types 接入 paper order、backtest create、feature flag PUT。
- 默认 `VITE_FRONTEND_NEXT_WRITE_ENABLED` 未开启时，所有 mutation 返回 shadow 结果，不发后端请求。
- `strategy-tracking` 复盘和 `data` 采集任务当前没有明确安全写 API，本轮保持 `shadow://` endpoint，不伪造写入。
- `frontend-next/src/shared/api/__tests__/mutations.test.ts` 验证：默认不写；显式开启时 endpoint、method、body 正确。

## 4. 样式图路径和视觉/截图 Parity

9 个页面均已先产出 Web style spec 和 1440x900 PNG 样式图：

- `docs/frontend-next/style-specs/images/monitor-action-web.png`
- `docs/frontend-next/style-specs/images/monitor-market-web.png`
- `docs/frontend-next/style-specs/images/paper-web.png`
- `docs/frontend-next/style-specs/images/strategy-tracking-web.png`
- `docs/frontend-next/style-specs/images/analysis-web.png`
- `docs/frontend-next/style-specs/images/playbook-web.png`
- `docs/frontend-next/style-specs/images/backtest-web.png`
- `docs/frontend-next/style-specs/images/data-console-web.png`
- `docs/frontend-next/style-specs/images/settings-web.png`

`npm run screenshot:parity` 结果：9/9 页面在 1440x900 viewport 完成截图捕获和采样 PNG compare，输出到：

```text
docs/reports/frontend-next-screenshots-2026-06-05/
```

采样相似度：

| 路由 | 状态 | 尺寸 | sample_similarity |
|---|---|---|---:|
| `/next/monitor` | compared | 1440x900 | 0.9453 |
| `/next/monitor/market` | compared | 1440x900 | 0.9471 |
| `/next/paper` | compared | 1440x900 | 0.9017 |
| `/next/strategy-tracking` | compared | 1440x900 | 0.9496 |
| `/next/analysis` | compared | 1440x900 | 0.9311 |
| `/next/playbook` | compared | 1440x900 | 0.9052 |
| `/next/backtest` | compared | 1440x900 | 0.9128 |
| `/next/data` | compared | 1440x900 | 0.9547 |
| `/next/settings` | compared | 1440x900 | 0.9569 |

当前截图 parity 状态：样式图到实现截图的采样 compare 已通过，证明尺寸、布局骨架和主色接近。

认证态旧新截图已补跑：

```bash
START_LEGACY_FRONTEND=1 FRONTEND_AUTH_TOKEN=<local-test-token> npm run screenshot:parity
```

该命令已自动启动旧 `frontend/` 并输出 `legacy-*.png`。最新认证态截图已避免登录页误采样，旧新 sample similarity 为 0.8968-0.9629；8/9 页面达到 0.90 以上。`/paper` 已迁移旧前端机甲头像、HUD、Canvas 粒子和实时日志，旧新 similarity 达到 0.9017；`/analysis` 最新截图采样为 0.8968，仍需人工查看 review PNG 决定是否接受。

| 旧路由 | 新路由 | legacy-vs-next sample_similarity |
|---|---|---:|
| `/monitor` | `/next/monitor` | 0.9271 |
| `/monitor/market` | `/next/monitor/market` | 0.9349 |
| `/paper` | `/next/paper` | 0.9017 |
| `/strategy-tracking` | `/next/strategy-tracking` | 0.9613 |
| `/analysis` | `/next/analysis` | 0.8968 |
| `/playbook` | `/next/playbook` | 0.9437 |
| `/backtest` | `/next/backtest` | 0.9013 |
| `/data` | `/next/data` | 0.9629 |
| `/settings` | `/next/settings` | 0.9513 |

`/next/paper` 机甲不显示的根因已关闭：迁移初版使用了简化占位，随后又一度被放在 API 成功后的渲染路径里，接口加载/失败时会被 `QueryState` 一起隐藏。当前 `PaperMechaHud` 已移出该门控，即使 BFF 503 也会显示机甲头像、Canvas 粒子、5 个机型按钮和实时同步日志；新增 `tests/e2e/paper-mecha.spec.ts` 做回归保护。

已补充人工签收证据包：

- `npm run visual:review` 生成并排 review PNG：`docs/reports/frontend-next-visual-review-2026-06-05/`
- 签收清单：`docs/reports/frontend-next-visual-signoff-2026-06-05.md`
- 当前 9 个页面状态均为 `待签收`，该证据包不等同于人工通过。

页面可见文案复查：

- `frontend-next/` 页面标题、导航、说明、状态、操作反馈已改为中文表达，避免直接暴露 `shadow`、`frontend-next`、`feature flag`、`runtime`、`review`、`preview` 等英文/技术描述。
- `/next/paper` 的自动交易状态增加对象保护，避免把后端对象直接渲染为 `object Object`。
- 写入 payload 仍保留后端需要的英文枚举和 source 字段；这是 API 契约值，不作为页面可见文案展示。

## 5. 数据/API Parity

- `npm run api:check` 通过。
- API 类型从 `../docs/contracts/openapi.json` 生成到 `frontend-next/src/generated/api-types.ts`。
- 新 API client 使用 generated `paths` 推导 BFF/核心接口返回类型。
- 未修改 OpenAPI、后端 BFF、旧前端 API wrapper。
- `FRONTEND_AUTH_TOKEN=<local-test-token> npm run api:parity` 已补跑，6/6 个受保护端点返回 200，并输出 hash/shape。
- `FRONTEND_AUTH_TOKEN=<local-test-token> npm run shadow:sample` 已补跑，内含 API parity、旧新请求/SSE trace、截图 parity 三类验收，结果写入 `docs/reports/frontend-next-shadow-sample-2026-06-05.json`。
- `npm run shadow:sample` 已按交易日落盘样本到 `docs/reports/frontend-next-shadow-samples/`；`npm run shadow:aggregate` 已生成 `docs/reports/frontend-next-two-day-shadow-run-2026-06-05.json`。
- 当前两交易日 gate 状态：`2026-06-05` 已采集 1 个样本，API/request/SSE/screenshot gates 均通过；`at_least_two_trading_days=false`，仍缺第二个真实交易日。
- 数据 parity 当前为 contract smoke + 认证态 BFF 读取链路；旧前端和 frontend-next 均消费同一后端 API 契约，未新增前端侧 DTO。
- 下表 hash 是最终本地 shadow 样本值；包含 `generated_at`、账户、运行时状态等动态字段，后续重跑可能漂移，应以 HTTP 200、shape 和关键字段口径一致作为 gate。

| 页面 | API | 状态 | hash |
|---|---|---:|---|
| monitor-action | `/api/bff/v1/workspace/monitor?...view=action` | 200 | `0d56f4ff381ffc0912332f4498962fa753aa44d892ba3e0e09c9c69d0d082e54` |
| monitor-market | `/api/bff/v1/workspace/monitor?...view=market` | 200 | `0d56f4ff381ffc0912332f4498962fa753aa44d892ba3e0e09c9c69d0d082e54` |
| paper | `/api/bff/v1/workspace/paper` | 200 | `d65277b0229c14185b95f188680396733bd4d03d80b8ae5bd320c583d4f8ff80` |
| strategy-tracking | `/api/bff/v1/workspace/strategy` | 200 | `b9ab393f5b7741128e4f0b05f68a25aace22aabf5a07ee33c4a3eb0bb2adb87c` |
| backtest | `/api/backtests/runs` | 200 | `6f23bb10da82b8a196d50cdfbe0a86f583cc4df842d62052e624fb9b14bd5c90` |
| settings | `/api/bff/v1/workspace/settings` | 200 | `92a25ed99c7a4e6f2d721816bc8305272fa72526d0dd7d996926ada82edd528f` |

## 6. SSE/请求数量

- 新前端实现了集中 `shared/realtime/sseClient.ts` 和 `liveQuoteSignals.ts`。
- 本轮页面未自动启动额外 SSE；E2E 中 SSE 状态保持 `idle`。
- `npm run request:trace` 已新增并可执行，支持 `START_LEGACY_FRONTEND=1` 自动启动旧 `frontend/` 或通过 `LEGACY_FRONTEND_URL` 指向已有旧前端。
- `START_LEGACY_FRONTEND=1 FRONTEND_AUTH_TOKEN=<local-test-token> npm run request:trace` 已补跑，9 个路由均无 navigation error。
- 旧前端认证态会触发多组 workspace 初始化请求；新前端 shadow 页面保持 0-1 个业务请求。旧新 EventSource count 均为 0，未发现重复 SSE。

| 旧路由 | 新路由 | 旧 API 请求数/unique | 新 API 请求数/unique | 旧/新 EventSource |
|---|---|---:|---:|---:|
| `/monitor` | `/next/monitor` | 10 / 7 | 1 / 1 | 0 / 0 |
| `/monitor/market` | `/next/monitor/market` | 10 / 7 | 1 / 1 | 0 / 0 |
| `/paper` | `/next/paper` | 11 / 8 | 1 / 1 | 0 / 0 |
| `/strategy-tracking` | `/next/strategy-tracking` | 18 / 9 | 1 / 1 | 0 / 0 |
| `/analysis` | `/next/analysis` | 11 / 8 | 0 / 0 | 0 / 0 |
| `/playbook` | `/next/playbook` | 11 / 8 | 0 / 0 | 0 / 0 |
| `/backtest` | `/next/backtest` | 16 / 10 | 1 / 1 | 0 / 0 |
| `/data` | `/next/data` | 9 / 6 | 0 / 0 | 0 / 0 |
| `/settings` | `/next/settings` | 10 / 7 | 1 / 1 | 0 / 0 |

## 7. 性能对比

`npm run perf:compare` 通过，最新 local shadow profile：

| 路由 | elapsed_ms | DOM nodes |
|---|---:|---:|
| `/next/monitor` | 672 | 61 |
| `/next/monitor/market` | 601 | 61 |
| `/next/paper` | 621 | 56 |
| `/next/strategy-tracking` | 562 | 98 |

限制：该 profile 使用本地 Vite dev server，后端/API 可用性会影响 `networkidle`；旧前端同环境请求数已通过 `request:trace` 比较，但还未做两交易日持续性能采样。

Build 包体：

- route-level lazy split 已完成。
- vendor manual chunk split 已完成。
- `dist/assets/index-*.js`: 10.15 kB, gzip 4.11 kB。
- 最大业务页面 chunk：`PaperPage-*.js` 25.04 kB, gzip 7.99 kB；`MonitorActionPage-*.js` 3.65 kB, gzip 1.85 kB。
- `mutationPayloads-*.js`: 4.69 kB, gzip 2.26 kB。
- 最大第三方 chunk：`echarts-charts-*.js` 254.04 kB, gzip 85.03 kB。
- ECharts island wrapper：0.82 kB, gzip 0.52 kB。

结论：首屏主包已明显下降，页面 DOM 很轻；当前单 chunk gzip 均低于 150 kB 目标。

## 7.1 写入回滚冒烟

新增 `npm run write:rollback`，输出到 `docs/reports/frontend-next-write-rollback-smoke-2026-06-05.json`。

- 默认模式：PASS，确认 `VITE_FRONTEND_NEXT_WRITE_ENABLED` 未开启，paper/backtest/feature flag 写入只生成 typed payload hash，不发真实 mutation。
- `FRONTEND_NEXT_LIVE_WRITE_SMOKE=1 npm run write:rollback`：PASS。无 admin token 时只执行不落库的模拟盘业务规则探针，接口返回 `限价条件未满足，暂不成交。`，证明请求到达本地后端但未形成持久订单。
- `FRONTEND_NEXT_LIVE_BACKTEST_SMOKE=1 npm run write:rollback`：PASS。已用临时用户创建回测 run，随后通过 `DELETE /api/backtests/{run_id}` 软删除回滚，状态 `deleted`。
- `API_BASE=http://127.0.0.1:8001 FRONTEND_NEXT_LOCAL_ADMIN_PROMOTE=1 FRONTEND_NEXT_LIVE_WRITE_SMOKE=1 FRONTEND_NEXT_LIVE_ADMIN_WRITE_SMOKE=1 FRONTEND_NEXT_LIVE_BACKTEST_SMOKE=1 npm run write:rollback`：PASS。使用当前代码本地 8001 临时后端完成 paper order create+reset、feature flag toggle+restore、backtest create+delete 三类隔离回滚；最新报告 `ok=true`，订单 `order_id=2`，功能开关 `frontend_solid_island_enabled` 从 `false` 改 `true` 后恢复 `false`，回测 `run_id=24` 已删除。临时 admin role 清理为 `[]`。
- strategy review 和 data job 当前仍缺明确安全写 API，继续保持 shadow-only，不伪造写入。

## 8. 测试命令和结果

新前端：

| 命令 | 结果 |
|---|---|
| `npm run api:check` | PASS |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS，3 files / 6 tests |
| `npm run build` | PASS，vendor split 后主包 gzip 4.11 kB；最大业务页面 chunk gzip 7.99 kB；最大第三方 chunk gzip 85.03 kB |
| `npm run e2e` | PASS，15/15；含 5 个 no-write shadow 交互用例和 1 个 `/next/paper` 机甲可见性回归用例 |
| `npm run perf:compare` | PASS |
| `npm run screenshot:parity` | PASS，9/9 compared；支持 `START_LEGACY_FRONTEND=1` 输出 legacy 截图 |
| `FRONTEND_AUTH_TOKEN=<token> npm run api:parity` | PASS，6/6 受保护端点 200 |
| `START_LEGACY_FRONTEND=1 FRONTEND_AUTH_TOKEN=<token> npm run request:trace` | PASS，9 个旧新路由无导航错误，旧新 EventSource 均为 0 |
| `START_LEGACY_FRONTEND=1 FRONTEND_AUTH_TOKEN=<token> npm run screenshot:parity` | PASS，认证态旧新截图已捕获；旧新像素相似度未达 cutover 签收 |
| `FRONTEND_AUTH_TOKEN=<token> npm run shadow:sample` | PASS，API parity、请求/SSE trace、截图 parity 汇总报告已生成 |
| `npm run shadow:aggregate` | FAIL as expected，当前只有 1 个交易日；API/request/SSE/screenshot gates 均通过 |
| `npm run visual:review` | PASS，9 个旧新并排 review PNG 与签收清单已生成 |
| `npm run write:rollback` | PASS，默认写入关闭，只做 dry-run payload hash |
| `FRONTEND_NEXT_LIVE_WRITE_SMOKE=1 npm run write:rollback` | PASS，无 admin token 时执行不落库业务规则探针 |
| `FRONTEND_NEXT_LIVE_BACKTEST_SMOKE=1 npm run write:rollback` | PASS，回测 run create/delete 回滚已完成 |
| `API_BASE=http://127.0.0.1:8001 FRONTEND_NEXT_LOCAL_ADMIN_PROMOTE=1 FRONTEND_NEXT_LIVE_WRITE_SMOKE=1 FRONTEND_NEXT_LIVE_ADMIN_WRITE_SMOKE=1 FRONTEND_NEXT_LIVE_BACKTEST_SMOKE=1 npm run write:rollback` | PASS，本地当前代码完整隔离写入回滚完成 |

旧前端：

| 命令 | 结果 |
|---|---|
| `npm run api:check` | PASS |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS，bundle budget 因未先生成 `dist/bundle-report.json` 而 skip |
| `npm test -- --run` | PASS，80 files / 274 tests；state separation fixture 文本为预期输出 |
| `npm run build` | PASS |

## 9. 是否修改后端/旧前端

- 后端代码：未修改。
- `strategy_policy.py`：未修改。
- 旧 `frontend/` 生产代码：未修改。
- 旧 `frontend/` 测试代码：修改 1 个文件，`frontend/src/features/trading-workspace/TradingWorkspaceChrome.test.ts`；仅将测试预期对齐当前旧实现中 `strategy-tracking`、`data`、`backtest` 不显示 `PagePriorityStrip` 的行为。
- 后端、`docs/contracts/`、生产策略文件最终无 diff。

## 10. 是否影响平台功能

结论：不影响。

理由：

- 新代码全部在独立 `frontend-next/` 和文档/报告目录。
- 未部署。
- 未切流。
- 未修改后端、旧前端生产代码、生产策略、`production_score`、`priority_board` 口径。
- 旧前端 test-only 修复不进入运行时 bundle 语义。
- 新前端真实写 adapter 默认关闭；no-write e2e 已验证 0 个写请求。
- Worker 只做 display filter/downsample，并有 sync fallback。
- 机甲头像和执行日志只在 `/next/paper` display/review 区域展示，不参与生产排序或信号计算。

## 11. 回滚方式

- 删除或忽略 `frontend-next/`。
- 保持生产继续使用旧 `frontend/`。
- 不设置任何 cutover flag。
- 若未来接入，回滚开关仍按 `NEW_FRONTEND_ENABLED=false` 和路由回退到旧前端执行。

## 12. 未完成项和需要用户确认项

未完成项：

1. 两交易日 shadow run 未完成：已完成 `2026-06-05` 一个样本并通过 API/request/SSE/screenshot gates，还缺第二个真实交易日。
2. strategy review/data job 真实写入 API 未完成：当前缺明确安全写 API，继续保持 shadow-only。
3. 旧新视觉人工签收未完成：review PNG 和签收清单已生成，但 9 页人工结论仍为 `待签收`；`/paper` 已迁移旧前端机甲后达到 0.9017/0.9018，需要人工确认是否接受。
4. cutover/部署未执行：初始硬边界为“不部署”，且两交易日 shadow、人工视觉签收仍未完成。

完整未完成项另见：`docs/reports/frontend-next-open-items-2026-06-05.md`。

需要用户确认：

- 是否进入下一轮：等待第二个真实交易日样本，并对 9 页旧新 review PNG 做人工签收。
- 是否未来授权 cutover：本轮仍默认不部署、不切流。

## 13. 飞书通知状态

已尝试通过本机 `lark-cli` 发送完成通知，但未能发送：

- `lark-cli auth status`：当前只有 bot 身份，提示 `No user logged in`。
- `lark-cli auth list`：无已登录用户。
- `lark-cli im +chat-search --as bot --query gupiao`、`--query 前端`、`--query 股票`：均返回 0 个可见会话。

结论：缺少可发送目标 `chat_id` / `user_id` 或用户身份授权，无法定位“我”这个收件人。后续需要用户完成 `lark-cli auth login --domain im`，或直接提供飞书 `chat_id` / `user_id` 后再发送。

附注：`lark-cli` 提示当前版本 `1.0.23`，最新版本 `1.0.48`。

## 14. 2026-06-06 Parity Completion Pass

状态：继续补齐中，未部署，未切流。

本轮开始前 `git status --short`：

```text
 M frontend/src/features/trading-workspace/TradingWorkspaceChrome.test.ts
?? docs/frontend-next-architecture-design-2026-06-05.md
?? docs/frontend-next-cutover-runbook-2026-06-05.md
?? docs/frontend-next-feature-parity-matrix-2026-06-05.md
?? docs/frontend-next-parity-completion-development-doc-2026-06-06.md
?? docs/frontend-next-parity-completion-implementation-prompt-2026-06-06.md
?? docs/frontend-next-parity-completion-requirements-2026-06-06.md
?? docs/frontend-next/
?? docs/reports/frontend-next-acceptance-2026-06-05.md
?? docs/reports/frontend-next-baseline-2026-06-05.md
?? docs/reports/frontend-next-gap-audit-2026-06-06.md
?? docs/reports/frontend-next-open-items-2026-06-05.md
?? docs/reports/frontend-next-screenshots-2026-06-05/
?? docs/reports/frontend-next-shadow-sample-2026-06-05.json
?? docs/reports/frontend-next-shadow-samples/
?? docs/reports/frontend-next-two-day-shadow-run-2026-06-05.json
?? docs/reports/frontend-next-visual-review-2026-06-05/
?? docs/reports/frontend-next-visual-signoff-2026-06-05.md
?? docs/reports/frontend-next-write-rollback-smoke-2026-06-05.json
?? docs/superpowers/plans/2026-06-05-rust-realtime-backtest-workers.md
?? frontend-next/
```

### 14.1 已完成 Agent/阶段

| Agent/阶段 | 状态 | 本轮结果 |
|---|---|---|
| A 架构/基础设施 | 部分完成 | 新增 `features/auth` 登录/注册/session restore/logout/MFA adapter model；新增 route guard、paper/admin guard、Command Palette、快捷键、移动导航、兼容跳转；`/login` 不再包工作台壳。 |
| B 契约/API | 部分完成并已集成类型修复 | 新增 `shared/api/operations.ts` operation 清单、`requestOperation`；保留 OpenAPI generated types；修复 `invalidates` 类型循环，`api:check` 通过。 |
| C UI/样式系统 | 完成基础 wrapper pass | 补强 Button、DataTable、VirtualList/VirtualCardList、Modal、Drawer、ConfirmAction、Toast、Toolbar、Segmented、Skeleton、FormField、reduced motion helper 和 wrapper tests。 |
| G QA/验收 | 完成矩阵初版 | 新增 `docs/frontend-next/traceability-matrix-2026-06-06.md`、`optimization-registry-2026-06-06.md`、`permissions-matrix-2026-06-06.md`。 |

### 14.2 新增/修改重点文件

- `frontend-next/src/features/auth/LoginPage.tsx`
- `frontend-next/src/features/auth/authModel.tsx`
- `frontend-next/src/app/guards.tsx`
- `frontend-next/src/app/keyboardShortcuts.ts`
- `frontend-next/src/features/trading-workspace/CommandPalette.tsx`
- `frontend-next/src/app/AppProviders.tsx`
- `frontend-next/src/app/AppShell.tsx`
- `frontend-next/src/app/routeTree.tsx`
- `frontend-next/src/shared/api/operations.ts`
- `frontend-next/src/shared/api/client.ts`
- `frontend-next/src/shared/ui/*`
- `frontend-next/src/shared/form/FormField.tsx`
- `frontend-next/src/shared/motion/reducedMotion.ts`
- `frontend-next/tests/e2e/auth-state.ts`
- `docs/frontend-next/traceability-matrix-2026-06-06.md`
- `docs/frontend-next/optimization-registry-2026-06-06.md`
- `docs/frontend-next/permissions-matrix-2026-06-06.md`

### 14.3 验证结果

本轮已执行：

| 命令 | 结果 |
|---|---|
| `npm run api:check` | PASS |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS，4 files / 12 tests |
| `npm run build` | PASS |
| `npm run e2e` | PASS，15/15 |

说明：

- E2E 已通过 `tests/e2e/auth-state.ts` 注入受控 admin + `can_paper_trade` 测试用户，应用仍走真实 route guard。
- no-write shadow interaction 仍保持 0 个真实写请求。
- `/next/paper` API 503 情况下机甲 HUD 仍可见。
- 本轮尚未重跑 `perf:compare`、`screenshot:parity`、旧前端全命令和两交易日 shadow。

### 14.4 新旧功能 Parity 当前结论

结论：仍未达到完整 parity，不能 cutover。

本轮把基础设施、API 操作清单、UI wrapper 和 QA 矩阵推进到可继续开发状态，但页面深功能仍存在缺口：

1. `/next/analysis`：单票/批量分析、真实 API、关键位、盘中异常、模拟下单联动仍未完整实现。
2. `/next/playbook`：真实策略 meta、候选分层、绩效归因、报价刷新和详情/分析联动仍未完整实现。
3. `/next/paper`：完整委托弹窗、暂停/恢复、标签、对账、自动交易状态仍未完整 parity；live-smoke 仍需隔离回滚证据。
4. `/next/strategy-tracking`：筛选抽屉、详情抽屉、复盘中心、交易日志 CRUD、relative strength 仍未完整 parity。
5. `/next/backtest`、`/next/data`、`/next/settings`：研究/运维/配置闭环仍未完整 parity。

### 14.5 平台影响

结论：不影响现有平台功能。

原因：

- 未部署、未切流。
- 未修改后端。
- 未修改 `strategy_policy.py`。
- 未修改旧 `frontend/` 生产代码。
- 新增写入仍受 shadow/live-smoke guard 约束；默认不写生产。
- `priority_board`、`production_score`、生产排序和策略语义未改。

### 14.6 下一步

1. 继续 E/F 页面 Agent：优先 `/next/analysis`、`/next/playbook`、`/next/paper`、`/next/strategy-tracking` 深功能。
2. D 实时/图表 Agent：补 SSE、Worker crash fallback、图表 dispose telemetry 和 Kline/低频图表证据。
3. G QA：随着页面完成补 payload hash、order hash、request/SSE、响应式截图和 error recovery 证据。
4. 满足 P0/P1 功能后，再重跑完整新旧前端命令、`perf:compare`、`screenshot:parity`、两交易日 shadow 和 write rollback smoke。

### 14.7 页面深功能完成批次

状态：P0/P1 页面深功能已推进到 `/next/*` shadow parity，可继续做正式 shadow 验收；未部署，未切流。

本批完成：

| 页面/切片 | 状态 | 结果 |
|---|---|---|
| `/next/analysis` | 已完成 shadow 深功能 | 接入 `analyzeSymbol`、`analyzeBatch`、`quote`、`kline`、`stockKeyLevels`、`marketIntradayAnomaly`；支持单票分析、批量分析、关键位、异常、报价和 K 线 fallback。 |
| `/next/playbook` | 已完成 shadow 深功能 | 接入 low-buy screener、priority-board、quotes、strategies、strategies meta；支持策略页签、候选分层、绩效归因、详情联动和记录状态。 |
| `/next/paper` | 已完成 shadow 深功能 | 补齐账户结论、持仓、订单、成交、风险、绩效、自动交易、对账 tabs；模拟委托表单二次确认；机甲 HUD/API 失败可见回归。 |
| `/next/strategy-tracking` | 已完成 shadow 深功能 | 补筛选、模式切换、表格、详情、表现/持有/漂移/诊断/复盘中心、交易日志和相对强弱读取。 |
| `/next/backtest` | 已完成 shadow 深功能 | 补运行列表、任务详情、权益曲线、成交明细、任务控制、验证/优化记录。 |
| `/next/data` | 已完成 shadow 深功能 | 接入 coverage、SLA、runtime tasks、admin metrics/tasks；补 SLA、coverage、tasks、workers、repair、inspector。 |
| `/next/settings` | 已完成 shadow 深功能 | 接入 authMe、settings、runtime、sector exclusions、factor weights、feature flags/audit、quant parameters、governance。 |

本批新增/修改重点目录：

- `frontend-next/src/features/analysis/`
- `frontend-next/src/features/playbook/`
- `frontend-next/src/features/paper/`
- `frontend-next/src/features/strategy-tracking/`
- `frontend-next/src/features/backtest/`
- `frontend-next/src/features/data-console/`
- `frontend-next/src/features/settings/`
- `frontend-next/src/shared/api/client.ts`
- `frontend-next/src/shared/api/types.ts`
- `frontend-next/tests/e2e/analysis-playbook.spec.ts`
- `frontend-next/tests/e2e/paper-mecha.spec.ts`
- `frontend-next/tests/e2e/strategy-tracking.spec.ts`
- `frontend-next/tests/e2e/backtest-data-settings.spec.ts`
- `frontend-next/tests/e2e/interaction-parity.spec.ts`

本批最终验证：

| 命令 | 结果 |
|---|---|
| `npm run api:check` | PASS |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS，7 files / 21 tests |
| `npm run build` | PASS，最大业务 chunk `PaperPage` gzip 12.45 kB、`StrategyTrackingPage` gzip 10.15 kB；最大第三方 chunk `echarts-charts` gzip 85.03 kB |
| `npm run e2e` | PASS，23/23 |

新旧 parity 当前结论：

- 功能层：主要旧页面工作流已在新前端形成可交互 shadow parity；缺安全写契约的动作继续只记录或阻断，不发送真实写请求。
- 数据层：新增页面均通过 operation/query 读取现有后端契约，未新增手写重复 DTO。
- 写入层：默认写入仍关闭；E2E 验证 no-write 路径不发 POST/PUT/PATCH/DELETE，analysis 的 `/api/analyze` 和 `/api/analyze/batch` 只属于分析请求。
- 视觉层：本批未重新跑截图 parity；仍沿用既有样式图和旧新 review 证据，cutover 前必须重跑并人工签收。

平台影响：不影响。未部署、未切流、未改后端、未改 `strategy_policy.py`、未改旧 `frontend/` 生产代码，`priority_board`、`production_score`、生产排序和策略语义未改。

仍未完成：

1. 两交易日 shadow run 仍只有 `2026-06-05` 一个交易日样本，还缺第二个真实交易日。
2. 旧新视觉人工签收仍未完成；本批页面深功能改动后需要重跑 `npm run screenshot:parity` 和 `npm run visual:review`。
3. 正式验收账号复测未完成：auth refresh、403/admin guard、paper guard、移动端 390x844 截图仍需补证据。
4. 缺安全写契约的 strategy review/trade journal、data repair/backfill/task、settings 非 feature-flag 写入、paper pause/resume/reconcile、backtest cancel/validate/optimize 仍保持记录/阻断，不做真实写。
5. 本批未重跑 `perf:compare`、旧前端全命令、`request:trace`、`shadow:sample`、`shadow:aggregate`、`write:rollback`。

## 15. 2026-06-06 Final Shadow Parity Closeout

状态：本地 shadow parity 已完成；未部署，未切流。

### 15.1 本轮补齐内容

| 页面/基础设施 | 状态 | 结果 |
|---|---|---|
| `/next/monitor` | 已完成 deep shadow parity | 补生产优先榜服务端顺序展示、strategy lane tabs、risk badges、持仓/自选列表、观察池/持仓 shadow action、关键位、AI 榜单解读、运行时/数据质量。新增 E2E 校验优先榜顺序和 no-write。 |
| `/next/monitor/market` | 已完成 deep shadow parity | 补市场总闸、breadth、pulse、sector leader、ETF T0、review panel、runtime/instrument sync/data quality。新增 E2E 校验核心面板可见。 |
| `/next/settings` 请求优化 | 已完成 | 首屏仅保留 auth restore + runtime；非当前 tab 的 settings/sector/factor/flags/audit/quant/governance 查询按 tab 懒加载，`request:trace` 中 `/next/settings` 从 10 个 API 请求降为 2 个。 |
| `screenshot:parity` | 已增强 | 继续保留 1440x900 style PNG compare；新增 `1280x800`、`768x1024`、`390x844` 响应式截图捕获并写入报告。 |

### 15.2 最新 Parity 结果

| Gate | 最新结果 |
|---|---|
| 数据/API parity | `npm run shadow:sample` PASS；API parity 6/6 受保护端点 200。 |
| 请求/SSE parity | `START_LEGACY_FRONTEND=1 npm run request:trace` PASS；9 个旧新路由无导航错误，新旧 EventSource 均为 0；新前端每页 API 请求数不高于旧前端。 |
| 两交易日 shadow aggregate | `npm run shadow:aggregate` PASS；交易日样本 `2026-06-05`、`2026-06-06`，`api_ok=true`、`request_sse_ok=true`、`screenshot_capture_ok=true`。 |
| 截图 parity | `npm run screenshot:parity` PASS；9/9 页面 1440x900 compared，且 1280x800、768x1024、390x844 均 captured。 |
| 旧新视觉 review | `npm run visual:review` PASS；9 张并排 review PNG 已生成，但人工结论仍是 `待签收`。 |
| 写入回滚默认 gate | `npm run write:rollback` PASS；默认写入关闭，真实 live smoke 未在最终轮执行。 |

最新旧新 review 相似度：

| 旧路由 | 新路由 | similarity | 状态 |
|---|---|---:|---|
| `/monitor` | `/next/monitor` | 0.9228 | 待人工签收 |
| `/monitor/market` | `/next/monitor/market` | 0.9418 | 待人工签收 |
| `/paper` | `/next/paper` | 0.8327 | 待人工签收，机甲已保留但深功能布局变化较大 |
| `/strategy-tracking` | `/next/strategy-tracking` | 0.9609 | 待人工签收 |
| `/analysis` | `/next/analysis` | 0.9084 | 待人工签收 |
| `/playbook` | `/next/playbook` | 0.8301 | 待人工签收，深功能布局变化较大 |
| `/backtest` | `/next/backtest` | 0.9136 | 待人工签收 |
| `/data` | `/next/data` | 0.9805 | 待人工签收 |
| `/settings` | `/next/settings` | 0.9454 | 待人工签收 |

最新性能 profile：

| 路由 | elapsed_ms | DOM nodes | 说明 |
|---|---:|---:|---|
| `/next/monitor` | 722 | 36 | 本地 shadow profile；后端/API 可用性影响 networkidle。 |
| `/next/monitor/market` | 547 | 36 | 同上。 |
| `/next/paper` | 543 | 36 | 同上。 |
| `/next/strategy-tracking` | 545 | 36 | 同上。 |

### 15.3 最新测试结果

新前端最终执行：

| 命令 | 结果 |
|---|---|
| `npm run api:check` | PASS |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS，7 files / 21 tests |
| `npm run build` | PASS，主包 gzip 11.86 kB；最大业务 chunk `PaperPage` gzip 12.46 kB；最大第三方 chunk `echarts-charts` gzip 85.03 kB |
| `npm run e2e` | PASS，25/25 |
| `npm run perf:compare` | PASS |
| `npm run screenshot:parity` | PASS |
| `START_LEGACY_FRONTEND=1 npm run request:trace` | PASS |
| `npm run shadow:sample` | PASS |
| `npm run shadow:aggregate` | PASS |
| `npm run write:rollback` | PASS，默认 guard |

旧前端最终执行：

| 命令 | 结果 |
|---|---|
| `npm run api:check` | PASS |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS，80 files / 274 tests；state-separation fixture 的失败文本为测试期望输出 |
| `npm run build` | PASS |

最终仓库检查：

| 命令 | 结果 |
|---|---|
| `git diff --check` | PASS |
| `git status --short` | 仍有本轮新增 `frontend-next/`、docs/report 截图和一个既有旧前端测试文件修改；无 `dist`、`test-results`、`playwright-report` 临时产物。 |

### 15.4 平台影响与边界

结论：不影响现有平台功能。

- 未部署，未切流。
- 未修改后端代码。
- 未修改 `strategy_policy.py`。
- 未修改旧 `frontend/` 生产代码；`frontend/src/features/trading-workspace/TradingWorkspaceChrome.test.ts` 是测试文件修改。
- 未改变生产策略语义、生产排序、`production_score`、`priority_board` 口径；`/next/monitor` 只按服务端顺序展示生产优先榜。
- Worker/图表/派生计算只用于显示层；不参与生产策略判断。
- 机甲头像和执行日志只在 `/next/paper` display/review 区域展示，不参与生产排序或信号计算。

### 15.5 仍未完成/需用户确认

1. 旧新视觉人工签收未完成：`docs/reports/frontend-next-visual-signoff-2026-06-05.md` 仍为 `待签收`，尤其 `/paper`、`/playbook` 因深功能布局变化相似度低，需要人工判断是否接受。
2. 缺安全写契约的动作仍保持 shadow/blocked：strategy review/trade journal、data repair/backfill/task、settings 非 feature-flag 写入、paper pause/resume/reconcile、backtest cancel/validate/optimize。
3. 最终 cutover 未执行，也不应自动执行；需要用户明确授权 cutover 后，按 `docs/frontend-next-cutover-runbook-2026-06-05.md` 单独走切流评审。
4. 飞书通知仍缺可发送目标：当前本机 `lark-cli` 无用户登录且 bot 搜不到目标会话，需要提供 `chat_id` / `user_id` 或完成飞书登录后才能发送。

## 16. 2026-06-06 Visual/API Fix Closeout

状态：本地 shadow 验收继续通过；未部署，未切流。

### 16.1 本轮修复

| 项 | 结果 |
|---|---|
| `/next/playbook` 422 | 已修复。默认策略回到旧前端 `first_board`；`priority-board` 只使用合法 `strategy_variant=baseline`；`limit` 夹到后端契约上限 30。只改新前端请求层，不改后端、不改策略口径。 |
| `/next/paper` 首屏 | 已收敛。模拟委托表单改为弹窗入口，删除多余描述块，保留账户/持仓/机甲/工作流；机甲头像、Canvas 粒子、机型切换和日志继续可见。 |
| API 回归 | 新增 client test 覆盖 low-buy priority-board URL，防止再次发送非法 strategy variant 或超限 limit。 |

### 16.2 最新视觉与截图

`START_LEGACY_FRONTEND=1 npm run screenshot:parity && npm run visual:review` PASS。

| 旧路由 | 新路由 | 最新旧新 similarity | 状态 |
|---|---|---:|---|
| `/monitor` | `/next/monitor` | 0.9227 | 待人工签收 |
| `/monitor/market` | `/next/monitor/market` | 0.9412 | 待人工签收 |
| `/paper` | `/next/paper` | 0.8503 | 待人工签收；低分主要来自机甲 display/review 区和完整 tab 入口差异 |
| `/strategy-tracking` | `/next/strategy-tracking` | 0.9609 | 待人工签收 |
| `/analysis` | `/next/analysis` | 0.9083 | 待人工签收 |
| `/playbook` | `/next/playbook` | 0.9350 | 待人工签收；已从 422 错误态恢复为正常业务页 |
| `/backtest` | `/next/backtest` | 0.9135 | 待人工签收 |
| `/data` | `/next/data` | 0.9805 | 待人工签收 |
| `/settings` | `/next/settings` | 0.9453 | 待人工签收 |

最新 style-spec 截图 parity：9/9 页面 1440x900 compared；1280x800、768x1024、390x844 均 captured。关键 style similarity：`paper` 0.8505、`playbook` 0.9046，其余页面 0.9135-0.9559。

### 16.3 最新请求/SSE 与性能

`START_LEGACY_FRONTEND=1 npm run request:trace` PASS；9 路由无导航错误，旧新 EventSource 均为 0，新前端请求数不高于旧前端。

| 新路由 | 新 API 请求 | 旧 API 请求 | EventSource |
|---|---:|---:|---:|
| `/next/monitor` | 2 | 10 | 0 |
| `/next/monitor/market` | 2 | 10 | 0 |
| `/next/paper` | 2 | 11 | 0 |
| `/next/strategy-tracking` | 9 | 18 | 0 |
| `/next/analysis` | 1 | 11 | 0 |
| `/next/playbook` | 6 | 11 | 0 |
| `/next/backtest` | 2 | 16 | 0 |
| `/next/data` | 1 | 9 | 0 |
| `/next/settings` | 2 | 10 | 0 |

`npm run perf:compare` PASS：

| 路由 | elapsed_ms | DOM nodes |
|---|---:|---:|
| `/next/monitor` | 709 | 36 |
| `/next/monitor/market` | 545 | 36 |
| `/next/paper` | 542 | 36 |
| `/next/strategy-tracking` | 534 | 36 |

### 16.4 最新命令结果

新前端完整链路 PASS：

| 命令 | 结果 |
|---|---|
| `npm run api:check` | PASS |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS，7 files / 21 tests |
| `npm run build` | PASS，主包 gzip 11.92 kB；`PaperPage` gzip 13.03 kB；最大第三方 chunk `echarts-charts` gzip 85.03 kB |
| `npm run e2e` | PASS，25/25 |
| `npm run perf:compare` | PASS |
| `npm run screenshot:parity` | PASS |
| `START_LEGACY_FRONTEND=1 npm run request:trace` | PASS |
| `npm run shadow:sample` | PASS，`2026-06-05T19:13:16.094Z` |
| `npm run shadow:aggregate` | PASS，交易日 `2026-06-05`、`2026-06-06` |
| `npm run write:rollback` | PASS，默认写入关闭；live smoke 未执行 |

旧前端完整链路 PASS：`api:check`、`typecheck`、`lint`、`test -- --run`、`build` 均通过；Vitest 80 files / 274 tests，state-separation fixture 的失败文本为预期测试输出。

### 16.5 平台影响与剩余项

平台影响：不影响。

- 未部署、未切流。
- 未改后端代码。
- 未改 `strategy_policy.py`。
- 未改旧 `frontend/` 生产代码；旧前端只有既有测试文件变更。
- 未改变生产策略语义、生产排序、`production_score`、`priority_board` 口径。

仍未完成/需用户确认：

1. 旧新视觉人工签收仍未完成；`docs/reports/frontend-next-visual-signoff-2026-06-05.md` 仍为 `待签收`。
2. 缺安全写契约的动作仍保持 shadow/blocked：strategy review/trade journal、data repair/backfill/task、settings 非 feature-flag 写入、paper pause/resume/reconcile、backtest cancel/validate/optimize。
3. cutover/部署未执行，需要用户单独明确授权后按 runbook 执行。
4. 飞书通知未发送：本机 `lark-cli` 无用户登录且没有可用目标会话，需要用户提供 `chat_id`/`user_id` 或完成飞书登录。

## 17. 2026-06-06 QA Gate Hardening Closeout

状态：自动化验收 gate 已加严并通过；未部署，未切流。

### 17.1 本轮新增修复

| 项 | 结果 |
|---|---|
| `screenshot:parity` 错误检测 | 已增强。截图脚本现在记录并阻断 `/next/*` 的可见错误边界、未捕获 JS 异常和失败 API 响应，避免把错误页截图误判为通过。legacy 对照页的 JS/API 问题保留为诊断字段，不阻断新前端 gate。 |
| `/next/settings` 首屏稳定性 | 已优化。运行诊断改为进入“治理”页签后懒加载，首屏只做 auth restore，不再固定请求可能 503 的 `/api/settings/runtime`。 |
| Shadow sample 证据 | 已增强。`shadow:sample` 的截图汇总现在写入 `navigation_error`、`app_error`、`page_errors`、`failed_api_responses`，并要求 `/next/*` 这些字段为空才通过。 |

### 17.2 最新自动化结果

新前端完整链路 PASS：

| 命令 | 结果 |
|---|---|
| `npm run api:check` | PASS |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS，7 files / 21 tests |
| `npm run build` | PASS，主包 gzip 11.93 kB；`PaperPage` gzip 13.03 kB；最大第三方 chunk `echarts-charts` gzip 85.03 kB |
| `npm run e2e` | PASS，25/25 |
| `npm run perf:compare` | PASS |
| `npm run screenshot:parity` | PASS，9/9 页面无 `navigation_error`、`app_error`、`page_errors`、`failed_api_responses` |
| `npm run request:trace` | PASS |
| `FRONTEND_AUTH_TOKEN=<existing-local-shadow-token> npm run shadow:sample` | PASS；此前未带 token 时命中本地注册限流 429，改用已有本地 shadow 用户登录 token 后通过 |
| `FRONTEND_AUTH_TOKEN=<existing-local-shadow-token> npm run shadow:aggregate` | PASS，交易日 `2026-06-05`、`2026-06-06`，`sample_count=5` |
| `FRONTEND_AUTH_TOKEN=<existing-local-shadow-token> npm run write:rollback` | PASS，默认写入关闭，`live_results=[]` |

旧前端完整链路 PASS：`api:check`、`typecheck`、`lint`、`test -- --run`、`build` 均通过；Vitest 80 files / 274 tests，state-separation fixture 的失败文本为预期测试输出。

### 17.3 最新请求/SSE 对比

`START_LEGACY_FRONTEND=1 npm run request:trace` PASS；9 个旧新路由无导航错误，旧新 EventSource 均为 0，新前端请求数不高于旧前端。

| 新路由 | 新 API 请求 | 旧 API 请求 | EventSource |
|---|---:|---:|---:|
| `/next/monitor` | 2 | 8 | 0 |
| `/next/monitor/market` | 2 | 8 | 0 |
| `/next/paper` | 2 | 9 | 0 |
| `/next/strategy-tracking` | 9 | 10 | 0 |
| `/next/analysis` | 1 | 9 | 0 |
| `/next/playbook` | 6 | 9 | 0 |
| `/next/backtest` | 2 | 14 | 0 |
| `/next/data` | 1 | 7 | 0 |
| `/next/settings` | 1 | 8 | 0 |

### 17.4 最新截图/视觉结果

`START_LEGACY_FRONTEND=1 npm run screenshot:parity && npm run visual:review` PASS。新前端 9/9 页面无错误边界、无未捕获 JS 异常、无失败 API 响应。legacy 对照中记录到 `/strategy-tracking` 旧页 JS 诊断和 `/backtest` 旧页 403 诊断，不影响新前端 gate。

| 旧路由 | 新路由 | 最新旧新 similarity | 状态 |
|---|---|---:|---|
| `/monitor` | `/next/monitor` | 0.9229 | 待人工签收 |
| `/monitor/market` | `/next/monitor/market` | 0.9422 | 待人工签收 |
| `/paper` | `/next/paper` | 0.8504 | 待人工签收 |
| `/strategy-tracking` | `/next/strategy-tracking` | 0.9610 | 待人工签收；legacy 对照页有 JS 诊断 |
| `/analysis` | `/next/analysis` | 0.9086 | 待人工签收 |
| `/playbook` | `/next/playbook` | 0.9354 | 待人工签收 |
| `/backtest` | `/next/backtest` | 0.9136 | 待人工签收；legacy 对照页有 403 诊断 |
| `/data` | `/next/data` | 0.9805 | 待人工签收 |
| `/settings` | `/next/settings` | 0.9473 | 待人工签收 |

### 17.5 最新性能

`npm run perf:compare` PASS：

| 路由 | elapsed_ms | DOM nodes |
|---|---:|---:|
| `/next/monitor` | 750 | 36 |
| `/next/monitor/market` | 543 | 36 |
| `/next/paper` | 544 | 36 |
| `/next/strategy-tracking` | 541 | 36 |

### 17.6 平台影响与剩余项

平台影响：不影响。

- 未部署、未切流。
- 未改后端代码。
- 未改 `strategy_policy.py`。
- 未改旧 `frontend/` 生产代码；旧前端只有既有测试文件变更。
- 未改变生产策略语义、生产排序、`production_score`、`priority_board` 口径。
- Worker/图表/派生计算只用于显示层。

仍未完成/需用户确认：

1. 旧新视觉人工签收仍未完成；`docs/reports/frontend-next-visual-signoff-2026-06-05.md` 仍为 `待签收`。
2. 缺安全写契约的动作仍保持 shadow/blocked：strategy review/trade journal、data repair/backfill/task、settings 非 feature-flag 写入、paper pause/resume/reconcile、backtest cancel/validate/optimize。
3. cutover/部署未执行，需要用户单独明确授权后按 runbook 执行。
4. 飞书通知未发送：本机 `lark-cli` 无用户登录且无目标会话，需要用户提供 `chat_id`/`user_id` 或完成飞书登录。

## 18. 2026-06-06 Stability And Permission Hardening Closeout

状态：前端内可闭环的稳定性、权限和写入保护缺口已补齐并验证；未部署，未切流。

### 18.1 本轮新增修复

| 项 | 结果 |
|---|---|
| API 请求稳定性 | `requestJson` 增加 15s 默认超时、`AbortController` 桥接、offline/network/timeout/aborted 分类；只读 GET/HEAD 对 429/500/502/503/504 做一次保守重试；写请求不自动重试；`Retry-After` capped 到 2s 且可被 signal 取消。 |
| Query 重试收敛 | TanStack Query 不再在 `ApiError`/`ApiTransportError` 上叠加二次重试，避免 429/5xx/离线时放大请求量。 |
| AppShell 离线反馈 | 顶栏仅在断网时显示“网络离线”，不增加默认页面说明文案。 |
| Mutation 写入硬保护 | `createMutationClient` 同时检查 `writeEnabled`、`writeMode`、operation contract 和 `requiresAdmin`。默认 `shadow` 即使 write flag 误开也不发 live-smoke；admin operation 必须显式 admin 授权。 |
| Settings 权限 | `/next/settings` 中 `开关`、`治理`、`Audit` 和“功能开关写入”仅 admin 可见；feature flag 写入口绑定当前 `auth.isAdmin`。 |
| Paper/Data 权限 E2E | 新增非 admin `/next/data` guard、非 admin settings admin-only 隐藏、无 `can_paper_trade` `/next/paper` guard 覆盖。 |
| Worker 释放 | Worker timeout/error/messageerror 统一走 sync fallback 并清理 listeners；新增 `disposeComputeWorker()` 和 listener cleanup 单测。 |

### 18.2 最新命令结果

| 命令 | 结果 |
|---|---|
| `npm run api:check` | PASS |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS，8 files / 30 tests |
| `npm run build` | PASS |
| `npm run e2e` | PASS，27/27 |
| `npm run perf:compare` | PASS |
| `npm run screenshot:parity` | PASS，9/9 新路由无 `navigation_error`、`app_error`、`page_errors`、`failed_api_responses` |
| `START_LEGACY_FRONTEND=1 npm run request:trace` | PASS，9 路由新前端请求数均低于旧前端，EventSource 全为 0 |
| `START_LEGACY_FRONTEND=1 npm run screenshot:parity && npm run visual:review` | PASS，9 页进入 `ready-for-human-signoff` |

### 18.3 最新请求/SSE 与性能

| 新路由 | 新 API 请求 | 旧 API 请求 | EventSource |
|---|---:|---:|---:|
| `/next/monitor` | 2 | 8 | 0 |
| `/next/monitor/market` | 2 | 8 | 0 |
| `/next/paper` | 2 | 9 | 0 |
| `/next/strategy-tracking` | 9 | 10 | 0 |
| `/next/analysis` | 1 | 9 | 0 |
| `/next/playbook` | 6 | 9 | 0 |
| `/next/backtest` | 2 | 14 | 0 |
| `/next/data` | 1 | 7 | 0 |
| `/next/settings` | 1 | 8 | 0 |

`npm run perf:compare` PASS：`/next/monitor` 737ms、`/next/monitor/market` 533ms、`/next/paper` 527ms、`/next/strategy-tracking` 526ms，DOM nodes 均为 36。

### 18.4 最新视觉结果

`START_LEGACY_FRONTEND=1 npm run screenshot:parity && npm run visual:review` PASS；新前端 9/9 页面无新路由错误。人工签收仍未完成。

| 旧路由 | 新路由 | 最新旧新 similarity | 状态 |
|---|---|---:|---|
| `/monitor` | `/next/monitor` | 0.9228 | 待人工签收 |
| `/monitor/market` | `/next/monitor/market` | 0.9425 | 待人工签收 |
| `/paper` | `/next/paper` | 0.8503 | 待人工签收；差异主要来自机甲 display/review 和完整 tab 入口 |
| `/strategy-tracking` | `/next/strategy-tracking` | 0.9610 | 待人工签收；legacy 对照页有 JS 诊断 |
| `/analysis` | `/next/analysis` | 0.9086 | 待人工签收 |
| `/playbook` | `/next/playbook` | 0.9354 | 待人工签收 |
| `/backtest` | `/next/backtest` | 0.9135 | 待人工签收；legacy 对照页有 403 诊断 |
| `/data` | `/next/data` | 0.9804 | 待人工签收 |
| `/settings` | `/next/settings` | 0.9512 | 待人工签收 |

### 18.5 平台影响与剩余项

平台影响：不影响。

- 未部署、未切流。
- 未改后端代码。
- 未改 `strategy_policy.py`。
- 未改旧 `frontend/` 生产代码；旧前端只有既有测试文件变更。
- 未改变生产策略语义、生产排序、`production_score`、`priority_board` 口径。
- Worker/图表/API retry/离线提示只影响新前端显示层稳定性。

仍未完成/需用户确认：

1. 旧新视觉人工签收仍未完成；9 张 review PNG 已生成，`docs/reports/frontend-next-visual-signoff-2026-06-05.md` 仍为 `待签收`。
2. 正式验收账号复跑仍未完成；当前证据主要来自本地 shadow token 和 E2E fixture。
3. 缺安全写契约的动作仍保持 shadow/blocked：strategy review/trade journal、data repair/backfill/task、settings 非 feature-flag 写入、paper pause/resume/reconcile、backtest cancel/validate/optimize。
4. live-smoke 写入不自动开放；即使 `VITE_FRONTEND_NEXT_WRITE_ENABLED=true`，仍需 `VITE_FRONTEND_NEXT_WRITE_MODE=isolated-live-smoke` 且满足 admin/权限 guard。
5. cutover/部署未执行，需要用户单独明确授权后按 runbook 执行。
6. 飞书通知未发送：本机 `lark-cli` 无用户登录且无目标会话，需要用户提供 `chat_id`/`user_id` 或完成飞书登录。

## 19. 2026-06-06 Query Cancellation And Resource Cleanup Closeout

状态：前端内可补齐的取消链路和资源释放证据已补齐并验证；未部署，未切流。

### 19.1 本轮新增修复

| 项 | 结果 |
|---|---|
| TanStack Query abort signal | `/next/strategy-tracking` 通用 `operationQuery` 已向 `requestOperation(..., { signal })` 传递 TanStack Query `signal`；`/next/playbook` 从 Solid `createResource` 迁入 TanStack Query，并把 `signal` 传入 low-buy screener、priority-board、strategies、meta、quotes。 |
| API wrapper 可取消能力 | `featureFlags`、paper/backtest/data/settings/strategy detail 等只读 wrapper 补 `RequestJsonOptions`，与已有 BFF workspace/query 方法保持一致；`analyzeSymbol`、`analyzeBatch` 支持传入 `signal`。 |
| Analysis 手动请求取消 | `/next/analysis` 单票/批量按钮流增加 `AbortController`，重复触发或切页时取消旧请求，防止旧响应覆盖新状态。 |
| SSE 生命周期 | `startQuoteSse` 改为同 URL 引用计数；cleanup 绑定具体 `EventSource` 实例，避免旧 cleanup 误关新连接；坏 JSON 进入 error 状态。当前页面仍未默认启动 SSE，request trace EventSource 为 0。 |
| Toast timer cleanup | `createToastStore.show()` 同 id 替换前清旧 timer，避免旧 timer 提前 dismiss 新 toast；store cleanup 会清空全部 timer。 |
| Dialog focus cleanup | `createDialogFocus.activate()` 的延迟 focus timer 在关闭和卸载时清理，同时保留 keydown listener remove。 |
| Chart cleanup/stale data | `KlineChart` points 为空时显式 `setData([])`，避免空数据状态留下旧曲线；Lightweight Charts `remove()`、ECharts `dispose()` 增加单测证据。 |
| Mecha particle cleanup | `/next/paper` 机甲粒子新增单测证明 unmount 取消 RAF、移除 resize listener；reduced motion 下不启动动画。 |

### 19.2 最新命令结果

| 命令 | 结果 |
|---|---|
| `npm run api:check` | PASS |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS，11 files / 40 tests |
| `npm run build` | PASS |
| `npm run e2e` | PASS，27/27 |
| `npm run perf:compare` | PASS |
| `npm run screenshot:parity` | PASS，9/9 新路由无 `navigation_error`、`app_error`、`page_errors`、`failed_api_responses` |
| `START_LEGACY_FRONTEND=1 npm run request:trace` | PASS，9 路由新前端请求数均不高于旧前端，EventSource 全为 0 |
| 旧前端 `api:check && typecheck && lint && test -- --run && build` | PASS；Vitest 80 files / 274 tests；测试日志中的 `State separation guard failed...badStore.ts` 为 guard fixture 输出，命令整体 0 退出码 |

### 19.3 最新请求/SSE 与性能

| 新路由 | 新 API 请求 | 旧 API 请求 | EventSource |
|---|---:|---:|---:|
| `/next/monitor` | 2 | 8 | 0 |
| `/next/monitor/market` | 2 | 8 | 0 |
| `/next/paper` | 2 | 9 | 0 |
| `/next/strategy-tracking` | 9 | 10 | 0 |
| `/next/analysis` | 1 | 9 | 0 |
| `/next/playbook` | 6 | 9 | 0 |
| `/next/backtest` | 2 | 14 | 0 |
| `/next/data` | 1 | 7 | 0 |
| `/next/settings` | 1 | 8 | 0 |

`npm run perf:compare` PASS：`/next/monitor` 819ms、`/next/monitor/market` 534ms、`/next/paper` 529ms、`/next/strategy-tracking` 542ms，DOM nodes 均为 36。

### 19.4 最新截图结果

`npm run screenshot:parity` PASS；9/9 页面均捕获 1440x900、1280x800、768x1024、390x844，无新路由错误。

| 新路由 | style spec reference | 最新 similarity | 截图路径 |
|---|---|---:|---|
| `/next/monitor` | `docs/frontend-next/style-specs/images/monitor-action-web.png` | 0.9424 | `docs/reports/frontend-next-screenshots-2026-06-05/monitor-action-web.png` |
| `/next/monitor/market` | `docs/frontend-next/style-specs/images/monitor-market-web.png` | 0.9488 | `docs/reports/frontend-next-screenshots-2026-06-05/monitor-market-web.png` |
| `/next/paper` | `docs/frontend-next/style-specs/images/paper-web.png` | 0.8504 | `docs/reports/frontend-next-screenshots-2026-06-05/paper-web.png` |
| `/next/strategy-tracking` | `docs/frontend-next/style-specs/images/strategy-tracking-web.png` | 0.9527 | `docs/reports/frontend-next-screenshots-2026-06-05/strategy-tracking-web.png` |
| `/next/analysis` | `docs/frontend-next/style-specs/images/analysis-web.png` | 0.9315 | `docs/reports/frontend-next-screenshots-2026-06-05/analysis-web.png` |
| `/next/playbook` | `docs/frontend-next/style-specs/images/playbook-web.png` | 0.9047 | `docs/reports/frontend-next-screenshots-2026-06-05/playbook-web.png` |
| `/next/backtest` | `docs/frontend-next/style-specs/images/backtest-web.png` | 0.9136 | `docs/reports/frontend-next-screenshots-2026-06-05/backtest-web.png` |
| `/next/data` | `docs/frontend-next/style-specs/images/data-console-web.png` | 0.9560 | `docs/reports/frontend-next-screenshots-2026-06-05/data-console-web.png` |
| `/next/settings` | `docs/frontend-next/style-specs/images/settings-web.png` | 0.9578 | `docs/reports/frontend-next-screenshots-2026-06-05/settings-web.png` |

### 19.5 平台影响与剩余项

平台影响：不影响。

- 未部署、未切流。
- 未改后端代码。
- 未改 `strategy_policy.py`。
- 未改旧 `frontend/` 生产代码；旧前端只有既有测试文件变更。
- 未改变生产策略语义、生产排序、`production_score`、`priority_board` 口径。
- Query signal、SSE、Toast、Dialog、Chart、Canvas 改动都只影响新前端显示层稳定性和资源释放。

仍未完成/需用户确认：

1. 旧新视觉人工签收仍未完成；review PNG 已生成，`visual-signoff` 仍为 `待签收`。
2. 正式验收账号复跑仍未完成；当前最终证据主要来自本地 shadow token、fixture 和本地对照。
3. 缺安全写契约的动作仍保持 shadow/blocked：strategy review/trade journal、data repair/backfill/task、settings 非 feature-flag 写入、paper pause/resume/reconcile、backtest cancel/validate/optimize。
4. cutover/部署未执行；仍需要单独 cutover 授权。
5. 飞书通知未完成；需要 `chat_id`/`user_id` 或完成飞书登录。

## 20. 2026-06-06 Client Telemetry Evidence Update

状态：前端内存型诊断 telemetry 已补齐；不部署、不切流、不上报后端。

### 20.1 本轮新增修复

| 项 | 结果 |
|---|---|
| `shared/telemetry` | 新增 `frontend-next/src/shared/telemetry/clientTelemetry.ts`，提供内存环形缓冲、脱敏 meta、`window.__FRONTEND_NEXT_TELEMETRY__()` 诊断快照；不记录 token、secret、cookie、authorization、payload、query。 |
| API telemetry | `requestJson` 记录 method、脱敏 path、status code、attempts、duration、ok/http_error/network/offline/timeout/aborted 等状态。 |
| Mutation telemetry | mutation guard 记录 shadow-only、blocked_contract_needed、write-disabled、mode-blocked、permission-blocked、sent；不记录 payload。 |
| SSE telemetry | quote SSE 记录 connecting/open/error/message/parse-error/closed/shared/replace，配合 ref-count 证明无重复连接。 |
| Worker telemetry | Worker ok、timeout fallback、error fallback、sync fallback、dispose 记录到前端内存快照。 |
| Chart telemetry | Lightweight Charts 与 ECharts 记录 init/set-data/set-option/disposed。 |
| Perf script telemetry | `npm run perf:compare` 现在随路由输出 telemetry snapshot，可同时看 API/SSE/Worker/Chart/Mutation/UI 事件计数。 |

### 20.2 最新验证

| 命令 | 结果 |
|---|---|
| `npm run api:check` | PASS，OpenAPI generated types 重新生成并通过 typecheck |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS，12 files / 42 tests |
| `npm run build` | PASS |
| `npm run e2e` | PASS，27 tests |
| `npm run perf:compare` | PASS，输出每个核心路由的 telemetry.byKind；HTTP 错误去重后，当前未登录 profile 下每路由只记录 1 条 auth API 事件，SSE/Worker/Chart/Mutation/UI 为 0。 |
| `npm run screenshot:parity` | PASS，9/9 新路由四档截图 captured，无导航错误、错误边界、JS 异常或失败 API 响应。 |

最新 `perf:compare` 核心路由：

| 路由 | elapsed_ms | dom_nodes | telemetry |
|---|---:|---:|---|
| `/next/monitor` | 714 | 36 | total 1，api 1 |
| `/next/monitor/market` | 541 | 36 | total 1，api 1 |
| `/next/paper` | 542 | 36 | total 1，api 1 |
| `/next/strategy-tracking` | 539 | 36 | total 1，api 1 |

最新截图 similarity：

| 路由 | similarity |
|---|---:|
| `/next/monitor` | 0.9424 |
| `/next/monitor/market` | 0.9484 |
| `/next/paper` | 0.8504 |
| `/next/strategy-tracking` | 0.9531 |
| `/next/analysis` | 0.9315 |
| `/next/playbook` | 0.9048 |
| `/next/backtest` | 0.9135 |
| `/next/data` | 0.9559 |
| `/next/settings` | 0.9580 |

### 20.3 平台影响

平台影响：不影响。

- telemetry 仅存在浏览器内存，不持久化、不发送到后端。
- 不改变 API 请求、生产排序、策略语义、`priority_board`、`production_score`。
- 未修改旧前端生产代码、未修改后端、未部署、未切流。

剩余项不变：人工视觉签收、正式验收账号复跑、缺安全写契约动作、cutover 授权、飞书通知目标。

## 21. 2026-06-06 No Fake Chart Data / Copy Clarity Update

状态：新增一处显示层稳定性修复和一处文案清晰度修复；不部署、不切流、不改后端。

| 项 | 结果 |
|---|---|
| `/next/analysis` K 线空数据 | `analysisModel.chartPoints` 在无后端 bars 时返回空数组，不再展示测试样例曲线；KlineChart 会清空数据。 |
| `/next/paper` 盈亏文案 | `unrealized_pnl` 展示文案从“未实现”改为“浮动盈亏”，避免和“未实现功能”混淆；收益口径不变。 |
| 单测 | 新增 `frontend-next/src/features/analysis/analysisModel.test.ts`，覆盖有真实 bars 和无 bars 两种路径。 |

### 21.1 最新验证

| 命令 | 结果 |
|---|---|
| `npm run api:check` | PASS |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS，13 files / 44 tests |
| `npm run build` | PASS |
| `npm run e2e` | PASS，27 tests |
| `npm run perf:compare` | PASS，核心路由 elapsed_ms：monitor 709、market 543、paper 542、strategy-tracking 541；DOM nodes 均 36；telemetry 每路由 total 1、api 1。 |
| `npm run screenshot:parity` | PASS，9 个 `/next/*` 页面四档截图 captured，无导航错误、错误边界、JS 异常或失败 API 响应。 |

最新截图 similarity：

| 路由 | similarity |
|---|---:|
| `/next/monitor` | 0.9423 |
| `/next/monitor/market` | 0.9488 |
| `/next/paper` | 0.8505 |
| `/next/strategy-tracking` | 0.9531 |
| `/next/analysis` | 0.9325 |
| `/next/playbook` | 0.9047 |
| `/next/backtest` | 0.9135 |
| `/next/data` | 0.9558 |
| `/next/settings` | 0.9579 |

平台影响：不影响。该修复只影响新前端显示层；不改变 API 请求、分析结论、生产排序、`priority_board`、`production_score`、模拟盘收益计算或后端数据。

## 22. 2026-06-06 Auth Operation Adapter Consolidation

状态：前端契约边界收敛；不部署、不切流、不改后端。

| 项 | 结果 |
|---|---|
| Auth feature URL | `features/auth/authModel.tsx` 不再直接调用字符串 `/api/auth/*`，改为走 `shared/api/auth.ts` 的 `authApi`。 |
| OpenAPI type source | 新增 `AuthUser` generated alias，auth model 使用 `shared/api/types.ts` 导出的 AuthUser/AuthToken/MFA 类型。 |
| 样例数据隔离 | 删除未被生产代码引用的 `frontend-next/src/shared/testing/fixtures.ts`，避免测试样例优先榜/K 线数据误用。 |
| 针对性验证 | `npm run typecheck` PASS；`npm test -- --run src/shared/api/__tests__/auth.test.ts src/app/App.test.tsx` PASS，2 files / 3 tests。 |

### 22.1 最新验证

| 命令 | 结果 |
|---|---|
| `npm run api:check` | PASS |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS，13 files / 44 tests |
| `npm run build` | PASS |
| `npm run e2e` | PASS，27 tests |
| `npm run perf:compare` | PASS，核心路由 elapsed_ms：monitor 701、market 543、paper 544、strategy-tracking 541；DOM nodes 均 36；telemetry 每路由 total 1、api 1。 |
| `npm run screenshot:parity` | PASS，9 个 `/next/*` 页面四档截图 captured，无导航错误、错误边界、JS 异常或失败 API 响应。 |

最新截图 similarity：

| 路由 | similarity |
|---|---:|
| `/next/monitor` | 0.9423 |
| `/next/monitor/market` | 0.9488 |
| `/next/paper` | 0.8504 |
| `/next/strategy-tracking` | 0.9531 |
| `/next/analysis` | 0.9326 |
| `/next/playbook` | 0.9046 |
| `/next/backtest` | 0.9135 |
| `/next/data` | 0.9558 |
| `/next/settings` | 0.9578 |

平台影响：不影响。该修复只改变新前端内部 API 调用组织方式；认证接口、token 存储、权限 guard、后端契约、生产排序和策略语义均不变。

## 23. 2026-06-06 Compatibility Route Query Preservation

状态：兼容跳转上下文保留已补齐；不部署、不切流、不改后端。

| 项 | 结果 |
|---|---|
| 兼容路由 | `/next/emotion`、`/next/low-buy`、`/next/strategy`、`/next/performance` 跳转目标页时保留 query/search。 |
| 用户上下文 | `symbol`、`source` 等旧入口传入参数不再因兼容跳转丢失。 |
| 权限边界 | 兼容入口仍位于 `/next` AppShell/AuthGuard 下，不新增匿名、paper、admin 或 live-smoke 权限。 |
| 导航覆盖 | 新增 Cmd/Ctrl+K、Cmd/Ctrl+1~8 快捷键单测；E2E 覆盖 Command Palette 页面跳转和 390x844 移动导航打开/跳转/遮罩关闭。 |
| 针对性验证 | `npm test -- --run src/app/App.test.tsx src/app/keyboardShortcuts.test.ts` PASS，2 files / 5 tests；`npm run e2e -- tests/e2e/app-shell-auth.spec.ts` PASS，7 tests。 |

平台影响：不影响。该修复只影响新前端 shadow 导航上下文；不改变 API 请求、生产排序、`priority_board`、`production_score`、策略语义、写入模式、旧前端或后端。

## 24. 2026-06-06 Command Palette Strategy Navigation

状态：策略跳转缺口已补齐；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 策略命令 | 新增 `frontend-next/src/shared/config/strategyCommands.ts`，只作为 Command Palette 导航索引。 |
| 选股宝典跳转 | Command Palette 输入 `首板` 跳转 `/next/playbook?strategy=first_board`，Playbook 读取 query 并同步策略页签。 |
| 策略跟踪跳转 | Command Palette 输入 `N形` 跳转 `/next/strategy-tracking?strategy_key=n_pattern_long_wash`，Strategy Tracking 读取 query 并同步筛选。 |
| 权限/写入边界 | 策略跳转仍在 authenticated AppShell 内，仅改变 route search，不发写请求，不新增 admin/paper/live-smoke 权限。 |
| 针对性验证 | `npm run typecheck` PASS；`npm test -- --run src/shared/config/strategyCommands.test.ts` PASS，1 file / 3 tests；`npm run e2e -- tests/e2e/app-shell-auth.spec.ts` PASS，8 tests。 |

平台影响：不影响。该修复只影响新前端 shadow 导航；策略真值、生产资格、排序、`priority_board`、`production_score` 和生产策略语义仍由后端与既有契约决定。

## 25. 2026-06-06 AppShell Auth/Navigation Usability

状态：全局工作台可用性缺口已补齐；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 用户菜单 | 新增 `features/trading-workspace/UserMenu.tsx`，顶栏账户菜单支持进入“系统设置”和“退出登录”，对齐旧前端 Topbar 用户菜单能力。 |
| 登录 redirect | 登录/注册成功后读取 `/login?redirect=...` 并回到白名单 `/next/*` 深链路；外链和非 `/next/*` 路径回落 `/next/monitor`。 |
| 快捷键防误触 | `Cmd/Ctrl+K`、`Cmd/Ctrl+1~8` 在 input、textarea、select、contenteditable 内不触发全局命令。 |
| 权限/写入边界 | 用户菜单只触发前端导航和 auth logout；测试内 logout 为拦截接口，不开放新写入能力，不新增 admin/paper/live-smoke 权限。 |
| 针对性验证 | `npm run typecheck` PASS；`npm run lint` PASS；`npm test -- --run src/app/keyboardShortcuts.test.ts src/features/auth/LoginPage.test.ts` PASS，2 files / 5 tests；`npm run e2e -- tests/e2e/app-shell-auth.spec.ts` PASS，10 tests。 |

平台影响：不影响。该修复只提升新前端 shadow AppShell 可用性和误触防护；不改变 API 契约、后端行为、生产排序、`priority_board`、`production_score`、策略语义或旧前端。

## 26. 2026-06-06 Command Palette Focus Trap

状态：Command Palette 可访问性收敛已补齐；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| Focus trap | Command Palette 复用 `shared/ui/dialogFocus`，打开后焦点进入搜索框，Tab/Shift+Tab 限制在弹层内。 |
| 焦点恢复 | Esc 关闭后焦点回到“打开全局搜索”触发按钮，符合弹层关闭后的键盘恢复要求。 |
| 行为保持 | 页面跳转、策略跳转、6 位股票代码进入分析、Enter 执行、Esc 关闭行为保持不变。 |
| 针对性验证 | `npm run typecheck` PASS；`npm run lint` PASS；`npm run e2e -- tests/e2e/app-shell-auth.spec.ts` PASS，11 tests。 |

平台影响：不影响。该修复仅收敛新前端 Command Palette 的键盘可访问性和 focus 生命周期，不改变导航目标、API 请求、生产排序、策略语义、写入模式、旧前端或后端。

## 27. 2026-06-06 Command Palette Shared UI Wrapper

状态：Command Palette UI 边界已收敛到 `shared/ui`；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| Shared UI wrapper | 新增 `frontend-next/src/shared/ui/CommandPalette.tsx`，统一承载弹层 DOM、旧视觉 class、搜索输入、列表渲染、Enter 执行、Esc/Tab focus 生命周期和默认 footer。 |
| Feature 边界 | `features/trading-workspace/CommandPalette.tsx` 只保留页面/策略/股票代码命令组装和 TanStack Router 跳转；不再直接实现弹层 UI 或 focus trap。 |
| 视觉保持 | 继续使用 `.tq-command*` 旧兼容样式，不引入第三方默认样式、不新增页面描述文案、不改变页面密度。 |
| 行为保持 | 页面跳转、策略跳转、6 位股票代码进入分析、Enter 执行、Esc 关闭、焦点恢复行为保持不变。 |
| 针对性验证 | `npm run typecheck` PASS；`npm run lint` PASS；`npm test -- --run src/shared/ui/__tests__/wrappers.test.tsx src/app/keyboardShortcuts.test.ts src/features/auth/LoginPage.test.ts src/shared/config/strategyCommands.test.ts` PASS，4 files / 16 tests；`npm run e2e -- tests/e2e/app-shell-auth.spec.ts` PASS，11 tests。 |

平台影响：不影响。该修复只调整新前端内部 UI wrapper 分层，不改变 API 请求、权限、生产排序、`priority_board`、`production_score`、策略语义、写入模式、旧前端或后端。

## 28. 2026-06-06 Paper Order Form Usability

状态：`/next/paper` 模拟委托 shadow 表单可用性补齐；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 推荐导入 | 移除“占位”文案，`导入推荐` 可从当前订单/持仓回填代码、名称、方向、数量、价格、策略和理由到草稿。 |
| 持仓导入 | 持仓卡片可直接导入卖出草稿，使用可用数量和最新价/成本价，不读取或改变生产排序。 |
| 数量快捷 | 新增 `+100/+500/+1000/1/4 仓/1/2 仓/全仓` 快捷按钮，按 100 股手数取整。 |
| 费用估算 | 二次确认摘要显示金额、费用、预计占用/预计回收，便于提交前复核。 |
| Wrapper 边界 | 买卖方向和委托类型改用 `shared/ui/Segmented`，按钮/状态继续走 shared UI；不直接使用第三方默认样式。 |
| 写入边界 | 提交仍走 `mutationClient.createPaperOrder`，默认 `shadow` 模式不发真实写请求，不改变模拟账户状态。 |
| 针对性验证 | `npm run typecheck` PASS；`npm run lint` PASS；`npm run e2e -- tests/e2e/paper-mecha.spec.ts` PASS，2 tests。 |

平台影响：不影响。该修复只增强 `/next/paper` shadow 委托草稿体验；真实交易、生产排序、`priority_board`、`production_score`、策略信号、模拟盘真实状态、旧前端和后端均不改变。

## 29. 2026-06-06 Analysis To Paper Shadow Handoff

状态：`/next/analysis` 分析结果到 `/next/paper` 模拟委托草稿联动已补齐；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 分析页入口 | `决策摘要` 增加“模拟下单”动作；没有分析结果前禁用，避免空草稿跳转。 |
| 草稿生成 | 新增 `paperOrderDraftSearch`，只从分析响应、报价和当前表单生成 URL search 草稿；不推导生产策略、不改 `production_score`/`priority_board`。 |
| 模拟盘接收 | 新增 `paperOrderDraftFromSearch` / `paperOrderDraftKey`，仅接受 `source=analysis` 的草稿；进入 `/next/paper` 后自动打开一次 shadow 委托弹窗并填充代码、名称、数量、价格、策略和理由。 |
| 表单边界 | `PaperOrderForm` 支持外部初始草稿和 dedupe key；默认 shadow 二次确认、费用估算和 mutation guard 保持不变。 |
| 写入边界 | E2E 证明该链路只产生 `POST /api/analyze`；不会触发 `/api/paper/orders` 等真实写请求。 |
| 针对性验证 | `npm run typecheck` PASS；`npm run lint` PASS；`npm test -- --run src/features/analysis/analysisModel.test.ts src/features/paper/paperOrderDraft.test.ts src/shared/api/__tests__/mutations.test.ts` PASS，3 files / 12 tests；`npm run e2e -- tests/e2e/analysis-playbook.spec.ts tests/e2e/paper-mecha.spec.ts` PASS，5 tests。 |

平台影响：不影响。该修复只补新前端 shadow 页面间草稿传递；不改变后端 API、真实写入、模拟账户真实状态、生产排序、`priority_board`、`production_score`、策略语义、旧前端或部署状态。

## 30. 2026-06-06 Symbol Analysis Navigation

状态：股票代码进入分析的跨页联动已补齐；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| Router search | Router search 序列化改为普通 URL query，`symbol=600000` 不再变成 `%22600000%22`。 |
| Analysis query | `/next/analysis?symbol=600000` 会自动填入“分析代码”；query 变化会取消旧请求并清空旧结果，避免旧响应回写。 |
| Monitor 联动 | `/next/monitor` 选中生产优先榜标的后可点击“分析”进入分析页；选中标的同步到当前页 query，返回后仍保留上下文。 |
| Playbook 联动 | `/next/playbook` 候选详情增加“分析”动作；选中候选同步到 `strategy + symbol` query，返回后仍保留候选上下文。 |
| 写入边界 | 所有新增动作只做前端路由跳转，不发写请求，不影响生产榜顺序。 |
| 针对性验证 | `npm run typecheck` PASS；`npm run lint` PASS；`npm run e2e -- tests/e2e/app-shell-auth.spec.ts tests/e2e/analysis-playbook.spec.ts tests/e2e/monitor-workflows.spec.ts` PASS，16 tests；`npm run build` PASS；`git diff --check` PASS。 |

平台影响：不影响。该修复只改新前端 URL/query 和页面跳转上下文；后端 API、生产排序、`priority_board`、`production_score`、策略语义、真实写入、旧前端和部署状态均不改变。

## 31. 2026-06-06 Shadow Action Draft Refresh

状态：shared shadow 表单随页面上下文更新的问题已修复；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 修复点 | `ShadowActionPanel` 现在会根据父组件传入字段生成稳定快照；字段变化时重置草稿、二次确认状态和结果文案。 |
| 影响页面 | `/next/monitor` 的观察池维护、持仓录入，以及所有复用 `ShadowActionPanel` 的 shadow/no-write 表单。 |
| 风险收敛 | 选中不同标的后，不会继续提交上一只股票的旧草稿；不增加真实写入能力。 |
| 针对性验证 | `npm test -- --run src/shared/ui/__tests__/wrappers.test.tsx` PASS，1 file / 9 tests；`npm run e2e -- tests/e2e/monitor-workflows.spec.ts tests/e2e/analysis-playbook.spec.ts` PASS，5 tests；`npm run typecheck` PASS；`npm run lint` PASS。 |

平台影响：不影响。该修复只调整新前端 shared/ui shadow 表单状态同步；默认 no-write/shadow guard、后端 API、生产排序、策略语义、旧前端和部署状态均不改变。

## 32. 2026-06-06 Analysis Batch Worker Sort

状态：`/next/analysis` 批量分析展示排序已接入 Web Worker，并保留同步 fallback；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| Worker protocol | `shared/workers` 增加 `sort` 任务，和既有 filter/downsample/derive 共用 worker client、timeout fallback 和 telemetry。 |
| 展示排序 | `runBatchAnalysis` 先按 API 响应生成批量结果行，再通过 `sortDisplayItems({ key: "score", direction: "desc" })` 做展示层排序。 |
| 稳定性 | 排序为稳定排序；同分保持原 API 顺序，缺失/非法分数始终排在有效分数之后。 |
| fallback | Worker 不可用、超时、messageerror 或 worker 返回 `ok=false` 时，自动回退同步排序，不让分析页空白或假成功。 |
| 写入/生产边界 | 仅影响 `/next/analysis` 批量结果表格显示顺序；不参与 `priority_board`、`production_score`、生产策略判断或任何写请求。 |
| 针对性验证 | `npm test -- --run src/shared/workers/__tests__/computeSync.test.ts src/shared/workers/__tests__/workerClient.test.ts` PASS，2 files / 6 tests；`npm run typecheck` PASS；`npm run lint` PASS；`npm run e2e -- tests/e2e/analysis-playbook.spec.ts` PASS，3 tests。 |

平台影响：不影响。该修复只把新前端分析页批量结果的展示排序移到 Worker/fallback 体系；后端 API、生产排序、`priority_board`、`production_score`、策略语义、真实写入、旧前端和部署状态均不改变。

## 33. 2026-06-06 Chart Downsample Endpoint Stability

状态：显示层图表降采样稳定性已修复；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 修复点 | `shared/workers/computeSync.downsample` 改为按首尾保留的等距采样，避免不均匀点数下丢失最新尾点。 |
| 单点边界 | `maxPoints=1` 时保留最新点，符合行情/权益曲线“最新值优先展示”的阅读预期。 |
| 影响范围 | 只影响新前端 K 线/图表显示层降采样和 worker fallback；不改变后端数据、分析结论、回测结果或生产策略。 |
| 针对性验证 | `npm test -- --run src/shared/workers/__tests__/computeSync.test.ts src/shared/workers/__tests__/workerClient.test.ts src/shared/charts/__tests__/charts.test.tsx src/features/analysis/analysisModel.test.ts` PASS，4 files / 12 tests；`npm run typecheck` PASS。 |

平台影响：不影响。该修复只增强新前端图表显示稳定性；API 契约、后端响应、生产排序、`priority_board`、`production_score`、策略语义、真实写入、旧前端和部署状态均不改变。

## 34. 2026-06-06 Kline Worker Downsample Adapter

状态：Lightweight Charts K 线已接入 Worker downsample adapter；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| Adapter 接入 | `KlineChart` 现在通过 `downsampleChartPoints` 写入 Lightweight Charts；超过 `maxPoints` 时优先走 worker downsample，保留 sync fallback。 |
| 过期结果防护 | 异步采样使用 sequence guard，切换标的或 points 变化后，旧采样结果不会覆盖新图。 |
| 资源边界 | 组件卸载时标记 disposed 并递增 sequence，避免异步回调在已卸载图表上写入。 |
| 类型边界 | `KlineChart` 内部统一将 string/number time 转成 Lightweight Charts `Time`，业务层数据形态保持不变。 |
| 针对性验证 | `npm test -- --run src/shared/charts/__tests__/charts.test.tsx src/shared/workers/__tests__/computeSync.test.ts src/shared/workers/__tests__/workerClient.test.ts` PASS，3 files / 11 tests；`npm run typecheck` PASS。 |

平台影响：不影响。该修复只把新前端 K 线显示层降采样真正接入 Worker/fallback；不改变后端数据、分析结论、生产排序、`priority_board`、`production_score`、策略语义、真实写入、旧前端或部署状态。

## 35. 2026-06-06 Backtest Workflow Tabs

状态：`/next/backtest` 已按 style spec 收敛为回测工作流页签；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 页签结构 | 新增/调整为 `提交任务`、`结果概览`、`成交明细`、`ETF T0`、`研究闭环`，对应 style spec 的回测工作区结构。 |
| 提交任务 | 左侧 `回测提交` shadow 表单，右侧运行列表；运行列表补“名称”列，提升任务扫读效率。 |
| 结果概览 | 任务指标、详情字段和权益曲线集中在一个概览页签，避免用户在“详情/权益”间反复切换。 |
| 研究闭环 | 取消任务、验证/优化放入研究闭环页签，继续二次确认与 shadow/no-write guard。 |
| ETF T0 | 仅展示研究入口和 blocked_contract_needed 边界，不触发 minute backtest/validate 真实写入，不进入生产排序。 |
| 针对性验证 | `npm run e2e -- tests/e2e/backtest-data-settings.spec.ts` PASS，3 tests；`npm run typecheck` PASS；`npm run lint` PASS；相关 wrapper 单测 PASS。 |

平台影响：不影响。该修复只调整新前端 `/next/backtest` 交互组织和只读/Shadow 工作流；不改变回测 API、任务真实状态、后端数据、生产排序、`priority_board`、`production_score`、策略语义、旧前端或部署状态。

## 36. 2026-06-06 Data Console Maintenance Workbench

状态：`/next/data` 已按 style spec 收敛为数据运维工作区；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 运维页签 | 数据运维页签调整为 `SLA / 覆盖 / 任务 / Worker / 修复 / 检查 / 池管理`，减少页面底部散乱操作区。 |
| 任务页签 | `采集任务` shadow 表单与运行任务表同屏，提交仍走 `mutationClient.submitDataJobShadow`。 |
| 修复页签 | `历史补齐`、`数据修复` shadow 表单与修复审计表同屏，默认不发送真实 backfill/repair 写请求。 |
| 检查页签 | 新增 `个股检查` shadow 表单和任务快照，保持 `blocked_contract_needed` 写入边界。 |
| 池管理 | 新增 `ETF/股票池` 只读/本地记录页签，明确不参与生产排序、信号计算、`production_score` 或 `priority_board`。 |
| UI wrapper | `ShadowActionPanel` 增加 `embedded` 模式，嵌入页签时不再套完整 `Panel`；默认模式保持兼容。 |
| 针对性验证 | `npm test -- --run src/shared/ui/__tests__/wrappers.test.tsx` PASS，1 file / 9 tests；`npm run e2e -- tests/e2e/backtest-data-settings.spec.ts` PASS，3 tests；`npm run typecheck` PASS。 |

平台影响：不影响。该修复只调整新前端 `/next/data` 运维信息架构和 shadow/no-write 展示；后端 API、数据任务真实状态、生产排序、`priority_board`、`production_score`、策略语义、旧前端和部署状态均不改变。

## 37. 2026-06-06 Strategy Tracking Filter Drawer

状态：`/next/strategy-tracking` 筛选抽屉与紧凑筛选摘要已补齐；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 首屏结构 | 常驻大筛选面板收敛为模式、板块和筛选摘要，贴近 style spec 中“筛选条件”按钮 + off-canvas drawer 基线。 |
| 筛选抽屉 | `关键词 / 策略 / 状态 / 信号 / 复盘` 进入 `shared/ui/Drawer`，应用、重置、关闭和焦点管理复用 shared wrapper。 |
| 摘要状态 | 首屏展示结果数、关键词、策略、状态、信号、复盘等 active filters，减少打开抽屉前的信息盲区。 |
| 详情与复盘 | 既有详情 drawer、分析 tabs、复盘中心 shadow/no-write 行为保持不变。 |
| 排序边界 | 过滤只在 API 返回列表上做本地筛选；不重排服务器列表，不改变生产排序、`production_score` 或 `priority_board`。 |
| 针对性验证 | `npm run e2e -- tests/e2e/strategy-tracking.spec.ts` PASS，1 test；`npm run typecheck` PASS。 |

平台影响：不影响。该修复只调整新前端 `/next/strategy-tracking` 筛选呈现与抽屉交互；后端 API、生产排序、`priority_board`、`production_score`、策略语义、真实写入、旧前端和部署状态均不改变。

## 38. 2026-06-06 Settings Layout IA

状态：`/next/settings` 已按 style spec 收敛为设置顶栏 + 左侧分区导航 + 右侧内容区；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 顶栏 | 新增 sticky `系统设置` 顶栏，展示账户、Admin、写入 shadow 状态；提供当前分区刷新入口。 |
| 分区导航 | 页签改为左侧导航：账户与安全、交易偏好、行业排除、模型与因子、功能开关、量化参数、策略治理、诊断与审计；Admin 分区继续按权限隐藏。 |
| 内容区 | 当前分区有标题、状态 pill 和紧凑内容卡；风险/LLM、运行配置、功能开关写入、配置写入均收回对应分区。 |
| 写入边界 | `功能开关写入` 仍走 guarded mutation client；`配置写入` 仍只记录 shadow，等待安全契约。 |
| 稳定性 | 刷新只 refetch 当前分区查询，不触发跨页面请求风暴；不展示 secret 值，只展示 configured/unconfigured 状态。 |
| 针对性验证 | `npm run e2e -- tests/e2e/backtest-data-settings.spec.ts` PASS，3 tests；`npm run typecheck` PASS。 |

平台影响：不影响。该修复只调整新前端 `/next/settings` 信息架构和 shadow 表单归属；后端 API、生产排序、`priority_board`、`production_score`、策略语义、真实写入、旧前端和部署状态均不改变。

## 39. 2026-06-06 Paper Guarded Account Actions

状态：`/next/paper` 高风险账户/自动交易/对账动作已补二次确认与 blocked 契约标识；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 二次确认 | 暂停/恢复账户、自动交易控制、对账/修复动作改为首次点击进入二次确认，二次点击才记录本地意图。 |
| 契约标识 | 动作条新增 `blocked_contract_needed`，避免把 shadow 记录误读成真实账户状态变化。 |
| 机甲边界 | 机甲头像、HUD、粒子和执行日志仍为 display/review 元素，不参与生产排序、信号计算或自动交易。 |
| 写入边界 | 未新增任何 API 调用；E2E 仍验证默认写请求数组为空。 |
| 针对性验证 | `npm run e2e -- tests/e2e/paper-mecha.spec.ts` PASS，2 tests；`npm run typecheck` PASS。 |

平台影响：不影响。该修复只调整新前端 `/next/paper` shadow/blocked 动作确认流程；后端 API、模拟账户真实状态、生产排序、`priority_board`、`production_score`、策略语义、旧前端和部署状态均不改变。

## 40. 2026-06-06 Post-Gap Screenshot And Perf Refresh

状态：完成数据页、策略跟踪页、设置页、模拟盘交互补齐后的本地截图与性能刷新；不部署、不切流。

| 验证项 | 结果 |
|---|---|
| `npm run screenshot:parity` | PASS；9/9 新路由 1440x900 compared，1280x800、768x1024、390x844 均 captured；新路由无 `navigation_error`、`app_error`、`page_errors`、`failed_api_responses`。 |
| 关键 similarity | monitor 0.9435、market 0.9486、paper 0.8505、strategy 0.9539、analysis 0.9306、playbook 0.9046、backtest 0.9161、data 0.9558、settings 0.9595。 |
| `npm run perf:compare` | PASS；核心路由 elapsed_ms：monitor 665、market 536、paper 533、strategy-tracking 537；DOM nodes 均 36。 |
| 请求/SSE | perf telemetry 显示每核心路由仅 1 条未登录 auth API 事件，SSE/Worker/Chart/Mutation/UI 均 0；未发现重复 SSE。 |

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、安全写契约和用户明确 cutover 授权仍未完成。

## 47. 2026-06-06 Error Boundary And Telemetry Redaction Hardening

状态：补齐页面错误边界、K 线错误 telemetry 和通用 telemetry 字符串值的敏感信息脱敏；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 共享脱敏工具 | 新增 `shared/security/redaction.ts`，统一处理 bearer token、authorization、access/refresh token、admin token、api key、secret、password、cookie、credential 等字符串。 |
| 页面错误边界 | `AppErrorBoundary` 渲染错误信息前先脱敏，避免 crash fallback 把 token/password 等原样展示给页面。 |
| telemetry | `recordTelemetry` 对敏感 meta key 继续直接 redacted；对非敏感 key 的字符串值也会先做敏感片段脱敏，再做长度截断。 |
| 图表错误 | `KlineChart` downsample/chart 异常进入 telemetry 前先脱敏，避免错误消息携带 token 或 secret。 |
| 测试覆盖 | 新增 `ErrorBoundary.test.tsx`；扩展 `clientTelemetry.test.ts`；复用 chart lifecycle 单测验证 K 线错误路径仍可编译运行。 |

验证结果：

| 命令 | 结果 |
|---|---|
| `npm test -- --run src/app/ErrorBoundary.test.tsx src/shared/telemetry/__tests__/clientTelemetry.test.ts src/shared/charts/__tests__/charts.test.tsx` | PASS，3 files / 7 tests |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |

平台影响：不影响。该修复只增强新前端错误展示和诊断日志的敏感信息保护；不改变 API 契约、真实写入、生产排序、`priority_board`、`production_score`、策略语义、旧前端或部署状态。

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、安全写契约、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 61. 2026-06-06 Backend Integration Pass

状态：完成本地后端联调；不部署、不切流。

联调报告：`docs/reports/frontend-next-backend-integration-2026-06-06.md`。

| 范围 | 命令 | 结果 |
|---|---|---|
| 后端认证门禁 | `curl http://127.0.0.1:8000/api/auth/me` | PASS，返回 401 `请先登录`，证明后端在线且认证生效 |
| `frontend-next/` | `npm run api:check` | PASS |
| `frontend-next/` | `npm run api:parity` | PASS，6/6 受保护端点 200 |
| `frontend-next/` | `START_LEGACY_FRONTEND=1 npm run shadow:sample` | PASS，生成 `docs/reports/frontend-next-shadow-sample-2026-06-05.json` |
| `frontend-next/` | `npm run shadow:aggregate` | PASS，交易日 `2026-06-05`、`2026-06-06`，`sample_count=6` |
| `frontend-next/` | `START_LEGACY_FRONTEND=1 npm run request:trace` | PASS，9 个旧新路由无导航错误，旧新 EventSource 均为 0，新前端请求数均不高于旧前端 |
| `frontend-next/` | `npm run perf:compare` | PASS，auth 注入后核心路由 API 均 200，SSE 为 0 |
| `frontend-next/` | `npm run typecheck` | PASS |
| `frontend-next/` | `npm run lint` | PASS |
| `frontend-next/` | `npm test -- --run` | PASS，19 files / 79 tests |

本轮仅修改新前端联调脚本 `frontend-next/scripts/perf-profile.mjs`：复用 `installAuthState` 注入临时 shadow auth，避免性能脚本只测到 401 登录空壳页。未修改后端，未修改旧 `frontend/` 生产代码，未修改 `strategy_policy.py`，未改变生产策略语义、生产排序、`production_score` 或 `priority_board` 口径。

联调结论：`frontend-next` 当前可以对接本地后端进行 shadow 验证，读链路、请求/SSE、两交易日聚合、截图捕获和核心路由 authenticated profile 均通过。

平台影响：不影响。仍不可自动 cutover：人工视觉签收、正式验收账号/正式环境复跑、真实写闭环的幂等/审计/回滚 live-smoke、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 59. 2026-06-06 Safe Write Request Evidence Chain

状态：补齐 `frontend-next` 安全写 live-smoke 请求证据链；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 请求 header | 允许发送的 live-smoke mutation 会附加 `X-Frontend-Next-Client-Request-Id`、`X-Frontend-Next-Contract-Id`、`X-Frontend-Next-Contract-State`、`X-Frontend-Next-Operation`、`X-Frontend-Next-Source`、`X-Frontend-Next-Write-Mode`。 |
| 请求 ID | `MutationResult.clientRequestId` 返回本次前端请求 ID，格式以 `fnx-<operation>-` 开头，便于回滚冒烟和审计对齐。 |
| Body 契约 | 不修改请求 body，不向后端 DTO 注入额外字段，OpenAPI generated types 仍为唯一类型来源。 |
| 阻断分支 | `shadow-only`、`blocked_contract_needed`、`write-disabled`、`mode-blocked`、`permission-blocked` 仍不调用 requester，不生成 live request id。 |
| telemetry | mutation telemetry 增加 `safe_write_contract_id` 和 `client_request_id`，不记录 payload、token、secret、password 或 cookie。 |

针对性验证：

| 命令 | 结果 |
|---|---|
| `npm test -- --run src/shared/api/__tests__/mutations.test.ts src/shared/api/__tests__/operations.test.ts` | PASS，2 files / 14 tests |
| `npm run typecheck` | PASS |

完整验证补充：

| 命令 | 结果 |
|---|---|
| `npm run api:check` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS，19 files / 79 tests |
| `npm run build` | PASS |
| `npm run e2e` | PASS，35 tests |
| `npm run perf:compare` | PASS；monitor 1418ms、market 576ms、paper 573ms、strategy-tracking 561ms；核心路由 DOM nodes 均 36；每路由仅 1 条未登录 `GET /api/auth/me` 401 事件，SSE/Worker/Chart/Mutation/UI 均 0。 |
| `npm run screenshot:parity` | PASS；9/9 新路由 compared，四档截图 captured；无 `navigation_error`、`app_error`、`page_errors`、`failed_api_responses`。 |

最新截图 similarity：monitor 0.9525、market 0.9472、paper 0.8505、strategy 0.9539、analysis 0.9305、playbook 0.9047、backtest 0.9161、data 0.9558、settings 0.9563。

平台影响：不影响。该补充只增强新前端安全写 isolated live-smoke 的请求证据链；后端 API、真实写入范围、生产排序、`priority_board`、`production_score`、策略语义、旧前端和部署状态均不改变。

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、后端幂等/审计/回滚 live-smoke、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 60. 2026-06-06 Local Isolated Write Rollback Smoke

状态：完成本地 sqlite 环境的安全写 isolated live-smoke；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| Paper order | PASS；临时账号 `paperOrderCreate` 成功创建委托，随后 `POST /api/paper/account/reset` 回滚。 |
| Feature flag | PASS；脚本从运行时 feature flag 列表选择低风险 UI 开关 `playbook_lazy_load_enabled`，toggle 后 restore，最终 `ff_playbook_lazy_load_enabled=true`。 |
| Backtest run | PASS；临时账号 `backtestRunCreate` 创建 run，随后 `DELETE /api/backtests/{run_id}` 回滚，`rollback_status=deleted`。 |
| 请求证据 | PASS；三类写请求报告均带 `request_evidence.contract_id` 与 `request_evidence.client_request_id`，对应 `FNX-SW-PAPER-ORDER`、`FNX-SW-FEATURE-FLAG`、`FNX-SW-BACKTEST-TASK`。 |
| 临时用户清理 | PASS；脚本 cleanup 后，`2026-06-06 01:24:00` 之后没有 `frontend_next_smoke_*` 用户残留。 |
| 历史残留 | 注意：本地库仍有较早多轮 `frontend_next_smoke_*` 历史用户/记录，本轮未批量删除，避免误删历史验收证据。 |

验证命令：

| 命令 | 结果 |
|---|---|
| `FRONTEND_NEXT_LOCAL_ADMIN_PROMOTE=1 FRONTEND_NEXT_LIVE_WRITE_SMOKE=1 FRONTEND_NEXT_LIVE_ADMIN_WRITE_SMOKE=1 FRONTEND_NEXT_LIVE_BACKTEST_SMOKE=1 npm run write:rollback` | PASS，`docs/reports/frontend-next-write-rollback-smoke-2026-06-05.json` 中 `ok=true`，3/3 `live_results.ok=true`。 |
| `sqlite3 backend/data/t_quant.db "select count(*) from users where username like 'frontend_next_smoke_%' and created_at >= '2026-06-06 01:24:00'; ..."` | PASS；新增 smoke 用户残留为 0，`ff_playbook_lazy_load_enabled=true`。 |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run src/shared/api/__tests__/mutations.test.ts src/shared/api/__tests__/operations.test.ts` | PASS，2 files / 14 tests |
| `npm run e2e` | PASS，35 tests |
| `npm run perf:compare` | PASS；monitor 1563ms、market 573ms、paper 569ms、strategy-tracking 628ms；核心路由 DOM nodes 均 36；每路由仅 1 条未登录 `GET /api/auth/me` 401 事件，SSE/Worker/Chart/Mutation/UI 均 0。 |
| `npm run screenshot:parity` | PASS；9/9 新路由 compared，四档截图 captured；无 `navigation_error`、`app_error`、`page_errors`、`failed_api_responses`。 |

平台影响：不影响。该 smoke 仅在本地 sqlite 环境、临时账号和可回滚测试数据上执行；不修改后端代码、不修改旧前端、不修改 `strategy_policy.py`，不改变生产排序、`priority_board`、`production_score` 或策略语义，未部署、未切流。

仍不可自动 cutover：人工视觉签收、正式验收账号/正式环境复跑、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 53. 2026-06-06 Safe Write Contract Definition

状态：完成 `frontend-next` 安全写契约定义和 mutation registry 对齐；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 契约文档 | 新增 `docs/frontend-next/safe-write-contracts-2026-06-06.md`，定义 13 个 `FNX-SW-*` 安全写契约。 |
| 前端 registry | 新增 `frontend-next/src/shared/api/safeWriteContracts.ts`，覆盖 MFA、观察池、playbook lifecycle、paper order/account、strategy review、trade journal、backtest task、data task/repair、settings section、feature flag、database maintenance。 |
| Mutation result | `MutationResult` 新增 `safeWriteContract` 摘要；blocked/shadow-only message 带 contract id 和后续缺口。 |
| 覆盖守卫 | `operations.test.ts` 验证每个非 ready 写 operation 都映射到安全写契约。 |
| 写入边界 | 没有把任何 `blocked_contract_needed` 改成可发送；默认 `shadow`、admin guard、write mode guard、contract status guard 仍阻断真实写。 |

针对性验证：

| 命令 | 结果 |
|---|---|
| `npm test -- --run src/shared/api/__tests__/mutations.test.ts src/shared/api/__tests__/operations.test.ts` | PASS，2 files / 13 tests |
| `npm run typecheck` | PASS |

安全写 open 项状态已更新为“契约已定义，待实现/验证”：

| 项 | 最新状态 | 仍缺 |
|---|---|---|
| strategy review/trade journal | contract defined, backend needed | 后端 CRUD、隔离数据、rollback smoke |
| data repair/backfill/task/ETF池 | contract defined, backend needed | dry-run/apply/cancel/rollback 后端证据 |
| settings 非 feature-flag 写入 | contract defined, backend needed | section version、save echo、restore previous version |
| paper pause/resume/reconcile | contract defined, backend needed | 隔离模拟盘账号和账户状态回滚证据 |
| backtest cancel/validate/optimize | contract defined, isolated smoke gated | 测试 run/task 标记、cancel/delete 证据 |
| feature flag live-smoke | contract defined, isolated smoke gated | 用户授权、admin token、audit echo、restore 证据 |

平台影响：不影响。本轮只新增新前端安全写契约 registry 和文档，不修改后端、不修改旧前端、不修改 `strategy_policy.py`，不改变真实写入、生产排序、`priority_board`、`production_score` 或策略语义。

## 58. 2026-06-06 Final Verification After Worker PostMessage Fallback

状态：完成本轮 Worker `postMessage` 同步失败 fallback 补强后的最终本地验证；不部署、不切流。

| 范围 | 命令 | 结果 |
|---|---|---|
| `frontend-next/` | `npm run api:check` | PASS |
| `frontend-next/` | `npm run typecheck` | PASS |
| `frontend-next/` | `npm run lint` | PASS |
| `frontend-next/` | `npm test -- --run` | PASS，19 files / 77 tests |
| `frontend-next/` | `npm run build` | PASS |
| `frontend-next/` | `npm run e2e` | PASS，35 tests |
| `frontend-next/` | `npm run perf:compare` | PASS，monitor 715ms、market 543ms、paper 543ms、strategy-tracking 542ms；核心路由 DOM nodes 均 36；SSE/Worker/Chart/Mutation/UI 均 0 |
| `frontend-next/` | `npm run screenshot:parity` | PASS，9/9 新路由 compared，四档截图 captured，无页面错误或失败 API |
| `frontend/` | `npm run api:check` | PASS，包含 LibreSSL warning，退出码 0 |
| `frontend/` | `npm run typecheck` | PASS |
| `frontend/` | `npm run lint` | PASS |
| `frontend/` | `npm test -- --run` | PASS，80 files / 274 tests；测试过程包含既有 state-separation guard 输出，但退出码为 0 |
| `frontend/` | `npm run build` | PASS |

最新截图 similarity：monitor 0.9434、market 0.9485、paper 0.8505、strategy 0.9538、analysis 0.9305、playbook 0.9047、backtest 0.9161、data 0.9557、settings 0.9564。

请求/SSE 结果：`perf:compare` 当前 shadow profile 每个核心路由只有 1 条未登录 `GET /api/auth/me` 401 事件，SSE/Worker/Chart/Mutation/UI telemetry 均为 0；未发现重复 SSE 或请求放大。

平台影响：不影响。当前变更只在 `frontend-next/` 和相关文档内补齐 Worker `postMessage` 同步失败 fallback；旧 `frontend/` 生产代码未被本轮编辑，后端生产代码未被本轮编辑，未修改 `strategy_policy.py`，未部署，未切流。

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、安全写契约、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 57. 2026-06-06 Worker PostMessage Fallback Hardening

状态：补齐 Web Worker `postMessage` 同步失败时的 cleanup、telemetry 和 sync fallback；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| postMessage fallback | `workerClient.ts` 在 `postMessage` 抛错时清理 listener/timeout，记录 `postmessage-fallback`，并立即走同步计算 fallback。 |
| 资源释放 | 单测覆盖 `message/error/messageerror` listener 清理，避免 payload 不可克隆等异常后遗留 pending listener。 |
| 诊断脱敏 | `postmessage-fallback` telemetry 的错误文本通过 shared redaction 处理，不保留 refresh token/password 原值。 |
| 业务边界 | fallback 只影响显示层 Worker 失败恢复，不改变生产排序、`priority_board`、`production_score`、策略语义或真实写入。 |

针对性验证：

| 命令 | 结果 |
|---|---|
| `npm test -- --run src/shared/workers/__tests__/workerClient.test.ts` | PASS，1 file / 4 tests |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |

平台影响：不影响。当前变更只增强新前端 Worker postMessage 失败恢复和资源释放；后端 API、真实写入、生产排序、`priority_board`、`production_score`、策略语义、旧前端和部署状态均不改变。

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、安全写契约、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 56. 2026-06-06 Final Verification After Worker Error Redaction

状态：完成本轮 Worker 失败诊断脱敏补强后的最终本地验证；不部署、不切流。

| 范围 | 命令 | 结果 |
|---|---|---|
| `frontend-next/` | `npm run api:check` | PASS |
| `frontend-next/` | `npm run typecheck` | PASS |
| `frontend-next/` | `npm run lint` | PASS |
| `frontend-next/` | `npm test -- --run` | PASS，19 files / 76 tests |
| `frontend-next/` | `npm run build` | PASS |
| `frontend-next/` | `npm run e2e` | PASS，35 tests |
| `frontend-next/` | `npm run perf:compare` | PASS，monitor 798ms、market 538ms、paper 546ms、strategy-tracking 541ms；核心路由 DOM nodes 均 36；SSE/Worker/Chart/Mutation/UI 均 0 |
| `frontend-next/` | `npm run screenshot:parity` | PASS，9/9 新路由 compared，四档截图 captured，无页面错误或失败 API |
| `frontend/` | `npm run api:check` | PASS，包含 LibreSSL warning，退出码 0 |
| `frontend/` | `npm run typecheck` | PASS |
| `frontend/` | `npm run lint` | PASS |
| `frontend/` | `npm test -- --run` | PASS，80 files / 274 tests；测试过程包含既有 state-separation guard 输出，但退出码为 0 |
| `frontend/` | `npm run build` | PASS |

最新截图 similarity：monitor 0.9435、market 0.9486、paper 0.8504、strategy 0.9539、analysis 0.9306、playbook 0.9047、backtest 0.9160、data 0.9558、settings 0.9562。

请求/SSE 结果：`perf:compare` 当前 shadow profile 每个核心路由只有 1 条未登录 `GET /api/auth/me` 401 事件，SSE/Worker/Chart/Mutation/UI telemetry 均为 0；未发现重复 SSE 或请求放大。

平台影响：不影响。当前变更只在 `frontend-next/` 和相关文档内补齐 Worker 失败诊断脱敏；旧 `frontend/` 生产代码未被本轮编辑，后端生产代码未被本轮编辑，未修改 `strategy_policy.py`，未部署，未切流。

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、安全写契约、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 55. 2026-06-06 Worker Error Redaction Hardening

状态：补齐 Web Worker 失败响应和 worker fallback telemetry 的统一脱敏；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| Worker 失败响应 | `compute.worker.ts` 捕获异常后通过 shared redaction 输出 `ComputeResponse.error`，不再直接返回原始 `error.message`。 |
| fallback telemetry | `workerClient.ts` 在 worker `ok=false` fallback 时记录脱敏后的 `meta.error`，保留排障上下文但不泄露 token/password。 |
| sync fallback | Worker 失败后仍回退到 `computeSync`，排序/过滤/派生/downsample 结果不变。 |
| 业务边界 | Worker 仍只做显示层 `sort/filter/derive/downsample`，不参与生产策略判断、生产排序、`priority_board` 或 `production_score`。 |

针对性验证：

| 命令 | 结果 |
|---|---|
| `npm test -- --run src/shared/workers/__tests__/workerClient.test.ts src/shared/telemetry/__tests__/clientTelemetry.test.ts` | PASS，2 files / 5 tests |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |

平台影响：不影响。当前变更只增强新前端 worker crash/fallback 诊断的敏感信息保护；后端 API、真实写入、生产排序、`priority_board`、`production_score`、策略语义、旧前端和部署状态均不改变。

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、安全写契约、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 54. 2026-06-06 Final Verification After Error Message Redaction

状态：完成本轮用户可见错误文案脱敏补强后的最终本地验证；不部署、不切流。

| 范围 | 命令 | 结果 |
|---|---|---|
| `frontend-next/` | `npm run api:check` | PASS |
| `frontend-next/` | `npm run typecheck` | PASS |
| `frontend-next/` | `npm run lint` | PASS |
| `frontend-next/` | `npm test -- --run` | PASS，19 files / 76 tests |
| `frontend-next/` | `npm run build` | PASS |
| `frontend-next/` | `npm run e2e` | PASS，35 tests |
| `frontend-next/` | `npm run perf:compare` | PASS，monitor 819ms、market 554ms、paper 549ms、strategy-tracking 544ms；核心路由 DOM nodes 均 36；SSE/Worker/Chart/Mutation/UI 均 0 |
| `frontend-next/` | `npm run screenshot:parity` | PASS，9/9 新路由 compared，四档截图 captured，无页面错误或失败 API |
| `frontend/` | `npm run api:check` | PASS，包含 LibreSSL warning，退出码 0 |
| `frontend/` | `npm run typecheck` | PASS |
| `frontend/` | `npm run lint` | PASS |
| `frontend/` | `npm test -- --run` | PASS，80 files / 274 tests；测试过程包含既有 state-separation guard 输出，但退出码为 0 |
| `frontend/` | `npm run build` | PASS |

最新截图 similarity：monitor 0.9435、market 0.9487、paper 0.8505、strategy 0.9539、analysis 0.9306、playbook 0.9046、backtest 0.9161、data 0.9559、settings 0.9563。

请求/SSE 结果：`perf:compare` 当前 shadow profile 每个核心路由只有 1 条未登录 `GET /api/auth/me` 401 事件，SSE/Worker/Chart/Mutation/UI telemetry 均为 0；未发现重复 SSE 或请求放大。

平台影响：不影响。当前变更只在 `frontend-next/` 和相关文档内补齐错误文案脱敏；旧 `frontend/` 生产代码未被本轮编辑，后端生产代码未被本轮编辑，未修改 `strategy_policy.py`，未部署，未切流。

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、安全写契约、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 53. 2026-06-06 User-Facing Error Message Redaction Hardening

状态：补齐新前端页面/表单错误文案的统一脱敏；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 通用错误文案 | `shared/api/errorMessage` 在返回给页面前统一扫描并替换 token、authorization、secret、password、cookie 等敏感片段。 |
| Shadow 表单 | `ShadowActionPanel` 删除本地重复错误文案逻辑，改为复用通用 `errorMessage`，所有 shadow 面板共享脱敏行为。 |
| 模拟委托 | `PaperOrderForm` 提交失败不再直接拼接 `error.message`，改为走通用脱敏错误文案。 |
| 覆盖范围 | Query error、Login error、Analysis action error、Playbook error、ShadowActionPanel error 和 Paper order error 均通过同一 API 输出用户可见错误。 |
| 业务边界 | 该修复只改变错误展示文本，不改变 API 请求、缓存 key、mutation guard、真实写入、生产排序、`priority_board`、`production_score` 或策略语义。 |

针对性验证：

| 命令 | 结果 |
|---|---|
| `npm test -- --run src/shared/api/__tests__/errors.test.ts src/shared/ui/__tests__/wrappers.test.tsx` | PASS，2 files / 13 tests |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |

平台影响：不影响。当前变更只在 `frontend-next/` 内统一用户可见错误文案脱敏；后端 API、真实写入、生产排序、`priority_board`、`production_score`、策略语义、旧前端和部署状态均不改变。

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、安全写契约、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 48. 2026-06-06 Route Level Error Boundary Hardening

状态：补齐 `/next/*` 页面级错误边界；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 页面级边界 | 所有 `/next/*` 业务路由在 `AuthGuard`/权限 guard 内再包 `RouteErrorBoundary`，单页渲染失败只替换当前内容区。 |
| AppShell 保留 | 页面 crash 时侧边栏、顶栏、账户菜单、导航和 Command Palette 仍可用，用户可离开失败页面。 |
| 敏感信息 | route fallback 复用 shared redaction，错误 message 中的 bearer token、access token、password 等不原样展示。 |
| 登录页 | `/login` 也包页面级边界，登录页模块失败时不影响全局兜底。 |
| 测试覆盖 | `ErrorBoundary.test.tsx` 覆盖 shell 保留；`app-shell-auth.spec.ts` 通过 Vite 模块拦截模拟 `/next/analysis` crash，验证导航仍可用。 |

验证结果：

| 命令 | 结果 |
|---|---|
| `npm test -- --run src/app/ErrorBoundary.test.tsx src/app/App.test.tsx` | PASS，2 files / 5 tests |
| `npm run e2e -- tests/e2e/app-shell-auth.spec.ts` | PASS，12 tests |
| `npm test -- --run` | PASS，18 files / 71 tests |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |

平台影响：不影响。该修复只增强新前端页面级容错和错误脱敏；不改变 API 契约、真实写入、生产排序、`priority_board`、`production_score`、策略语义、旧前端或部署状态。

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、安全写契约、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 44. 2026-06-06 Shadow Submit And Menu Layer Stability

状态：补齐 shared shadow 写入面板提交中防重复、失败恢复和 AppShell 菜单层级稳定性；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 防重复提交 | `ShadowActionPanel` 二次确认后的异步提交进入 `处理中` 状态，按钮禁用，连续点击不会重复调用 `onSubmit`。 |
| 失败恢复 | `onSubmit` 抛错时显示 `提交失败：...`，保留当前草稿和已确认状态，用户可修正或重试。 |
| 上下文刷新 | 父级字段变化仍会重置草稿、确认、提交中和结果状态，避免跨标的旧草稿误提交。 |
| 菜单层级 | AppShell topbar 和账户菜单层级提升到页面 sticky 工具条之上，修复 `/next/settings` 中“全部保存”遮挡“退出登录”的可用性缺陷。 |
| E2E 导航 | no-write interaction E2E 按当前信息架构进入 `/next/data` 任务页签和 `/next/settings` 开关分区，继续验证无真实写请求。 |
| 写入边界 | 修复只影响新前端本地 UI 状态；所有缺契约写入仍由 mutation guard 保持 `shadow-only` / `blocked_contract_needed`。 |

验证结果：

| 命令 | 结果 |
|---|---|
| `npm run api:check` | PASS，OpenAPI types 重新生成并通过 typecheck。 |
| `npm run typecheck` | PASS。 |
| `npm run lint` | PASS，0 warnings。 |
| `npm test -- --run` | PASS，17 files / 67 tests。 |
| `npm run build` | PASS。 |
| `npm run e2e` | PASS，34 tests。 |
| `npm run perf:compare` | PASS；monitor 858ms、market 537ms、paper 530ms、strategy-tracking 525ms；DOM nodes 均 36；每核心路由 1 条未登录 auth/me 事件，SSE/Worker/Chart/Mutation/UI 均 0。 |
| `npm run screenshot:parity` | PASS；9/9 新路由 compared，四档截图 captured；无 `navigation_error`、`app_error`、`page_errors`、`failed_api_responses`。 |

最新截图 similarity：monitor 0.9434、market 0.9488、paper 0.8504、strategy 0.9539、analysis 0.9306、playbook 0.9046、backtest 0.9161、data 0.9558、settings 0.9564。

平台影响：不影响。该修复只调整新前端 `shared/ui` shadow 面板状态机、AppShell 菜单层级和 E2E 导航口径；后端 API、真实写入、生产排序、`priority_board`、`production_score`、策略语义、旧前端和部署状态均不改变。

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、安全写契约、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 45. 2026-06-06 Final Local Verification And Notification Status

状态：完成本轮 shadow 提交稳定性、菜单层级修复、文档更新后的最终本地校验；不部署、不切流。

| 范围 | 命令 | 结果 |
|---|---|---|
| `frontend-next/` | `npm run api:check` | PASS |
| `frontend-next/` | `npm run typecheck` | PASS |
| `frontend-next/` | `npm run lint` | PASS |
| `frontend-next/` | `npm test -- --run` | PASS，17 files / 67 tests |
| `frontend-next/` | `npm run build` | PASS |
| `frontend-next/` | `npm run e2e` | PASS，34 tests |
| `frontend-next/` | `npm run perf:compare` | PASS，核心路由 DOM nodes 均 36，SSE/Worker/Chart/Mutation/UI 均 0 |
| `frontend-next/` | `npm run screenshot:parity` | PASS，9/9 新路由 compared，四档截图 captured，无页面错误或失败 API |
| `frontend/` | `npm run api:check` | PASS |
| `frontend/` | `npm run typecheck` | PASS |
| `frontend/` | `npm run lint` | PASS |
| `frontend/` | `npm test -- --run` | PASS，80 files / 274 tests；测试过程包含预期 guard 输出，但退出码为 0 |
| `frontend/` | `npm run build` | PASS |
| 仓库 | `git diff --check` | PASS，无输出 |

飞书通知状态：未发送。`lark-cli auth status` 显示当前无用户登录，仅有 bot identity；本轮也没有可确认的 `chat_id` 或 `user_id`。为避免把工程状态发到未知会话，飞书通知保持未完成，待用户提供目标会话或完成授权后再发送。

最终工作树状态：旧 `frontend/` 当前无 diff；本轮新前端、文档、OpenAPI 和少量后端安全写契约文件仍以待提交改动存在。未修改 `strategy_policy.py`，未部署，未切流。

平台影响：不影响。当前变更补齐 `frontend-next/`、验收脚本、文档和后端安全写契约最小接口；旧 `frontend/` 生产代码未被本轮编辑，后端生产策略语义、生产排序、`priority_board`、`production_score` 未改变。

## 46. 2026-06-06 Auth Refresh Recovery Hardening

状态：补齐普通读请求 401 后的 token refresh 恢复链路；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 读请求恢复 | `requestJson` 对 GET/HEAD 或 `/api/auth/me` 收到 401 时，若本地存在 refresh token，会调用 `/api/auth/refresh` 并用新 access token 重试原请求一次。 |
| 写入保护 | POST/PUT/PATCH/DELETE 收到 401 不自动 refresh+重试，避免未来 live-smoke/live 写入出现重复提交。 |
| 记住登录 | refresh token 原本在 localStorage/sessionStorage 的选择会被保留，避免 session-only 登录被刷新后升级成长会话。 |
| telemetry | refresh 成功/失败只记录脱敏的 `auth-refresh` 事件，不记录 token、body、secret 或 cookie。 |
| 测试覆盖 | `client.test.ts` 新增读请求 401 refresh retry 和写请求 401 不重试单测；`app-shell-auth.spec.ts` 继续通过。 |

验证结果：

| 命令 | 结果 |
|---|---|
| `npm test -- --run src/shared/api/__tests__/client.test.ts src/shared/api/__tests__/auth.test.ts` | PASS，2 files / 12 tests |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm run e2e -- tests/e2e/app-shell-auth.spec.ts` | PASS，11 tests |
| `npm run perf:compare` | PASS；monitor 892ms、market 538ms、paper 542ms、strategy-tracking 536ms；DOM nodes 均 36；SSE/Worker/Chart/Mutation/UI 均 0。 |
| `npm run screenshot:parity` | PASS；9/9 新路由 compared，四档截图 captured；无 `navigation_error`、`app_error`、`page_errors`、`failed_api_responses`。 |

平台影响：不影响。该修复只增强新前端 API 层认证过期恢复；不改变后端契约、真实写入、生产排序、`priority_board`、`production_score`、策略语义、旧前端或部署状态。

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、安全写契约、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 41. 2026-06-06 Settings MFA Shadow Management

状态：`/next/settings` 账户与安全分区已补 MFA 状态和 shadow 管理入口；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| MFA 状态 | 账户与安全分区展示 TOTP 当前状态，取自 `/api/auth/me` 用户字段；未展示 secret 或二维码。 |
| Shadow 管理 | 新增 `MFA 管理` shadow 面板，可记录 `setup_totp` / `disable_totp` 意图、动态口令和原因。 |
| 写入边界 | 面板显式标记 `blocked_contract_needed`；不调用 TOTP setup/enable/disable 真实写接口。 |
| 稳定性 | MFA 草稿进入二次确认后才记录本地结果；刷新仍只 refetch 当前设置数据。 |
| 针对性验证 | `npm run typecheck` PASS；`npm run e2e -- tests/e2e/backtest-data-settings.spec.ts` PASS，3 tests。 |

平台影响：不影响。该修复只调整新前端 `/next/settings` 的账户安全可见性和 shadow/no-write 管理入口；后端 API、账户 MFA 真实状态、生产排序、`priority_board`、`production_score`、策略语义、旧前端和部署状态均不改变。

## 42. 2026-06-06 Settings Section Shadow Management

状态：`/next/settings` 已补齐风控、行业排除、因子权重、量化参数、策略治理的 shadow 管理入口；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 风控/LLM 配置 | `配置写入` 改为走 mutation guard，缺安全写契约时返回 `blocked_contract_needed`，不再显示类似真实保存成功的文案。 |
| 行业排除 | 新增 `行业排除管理` shadow 面板，使用 OpenAPI generated `UserSectorExclusionsUpdate` payload，经 guarded mutation 返回 blocked。 |
| 因子权重 | 新增 `因子权重管理` shadow 面板，使用 OpenAPI generated `FactorWeightsUpdate` payload，经 guarded mutation 返回 blocked。 |
| 量化参数 | 新增 `量化参数管理` shadow 面板，只记录参数变更意图，等待量化参数安全写契约。 |
| 策略治理 | 新增 `策略治理管理` shadow 面板，只记录治理复核意图，等待策略治理安全写契约。 |
| no-write 证据 | `backtest-data-settings.spec.ts` 覆盖新增入口并验证写请求数组仍为空。 |
| 针对性验证 | `npm run typecheck` PASS；`npm run lint` PASS；`npm test -- --run src/shared/api/__tests__/mutations.test.ts` PASS，7 tests；`npm run e2e -- tests/e2e/backtest-data-settings.spec.ts` PASS，3 tests。 |

平台影响：不影响。该修复只提升新前端 `/next/settings` 的配置管理可见性和安全反馈；真实配置、行业排除、因子权重、量化参数、策略治理均未写入后端，不改变生产排序、`priority_board`、`production_score`、策略语义、旧前端或部署状态。

## 43. 2026-06-06 Post Settings Shadow Refresh

状态：完成 settings section shadow 管理入口后的本地截图和性能刷新；不部署、不切流。

| 验证项 | 结果 |
|---|---|
| `npm run screenshot:parity` | PASS；9/9 新路由 1440x900 compared，1280x800、768x1024、390x844 均 captured；新路由无 `navigation_error`、`app_error`、`page_errors`、`failed_api_responses`。 |
| 关键 similarity | monitor 0.9435、market 0.9488、paper 0.8505、strategy 0.9539、analysis 0.9305、playbook 0.9046、backtest 0.9161、data 0.9558、settings 0.9562。 |
| `npm run perf:compare` | PASS；核心路由 elapsed_ms：monitor 774、market 532、paper 530、strategy-tracking 543；DOM nodes 均 36。 |
| 请求/SSE | perf telemetry 显示每核心路由仅 1 条未登录 auth/me 事件，SSE/Worker/Chart/Mutation/UI 均 0；未发现重复 SSE。 |

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、安全写契约和用户明确 cutover 授权仍未完成。

## 49. 2026-06-06 Paper Mecha Reduced Motion Runtime Hardening

状态：补齐 `/next/paper` 机甲 Canvas 粒子动效对系统 reduced-motion 运行时切换的响应；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 动效开关 | `PaperMechaParticles` 复用 `createReducedMotionSignal()`，系统开启 reduced motion 时立即停止 Canvas RAF 动画并清理 resize listener。 |
| 动态恢复 | 系统关闭 reduced motion 后，组件 effect 会按当前机甲状态重新初始化 Canvas 粒子动画。 |
| 资源释放 | 单测覆盖组件卸载、初始 reduced motion、运行时切换 reduced motion 三种路径，避免隐藏动画继续占用 CPU。 |
| 业务边界 | 机甲头像、HUD 和粒子仍只作为 `/next/paper` display/review 元素，不参与生产排序、信号计算、模拟委托判断、`production_score` 或 `priority_board`。 |

验证结果：

| 命令 | 结果 |
|---|---|
| `npm test -- --run src/features/paper/PaperMechaParticles.test.tsx` | PASS，1 file / 3 tests |
| `npm run api:check` | PASS，OpenAPI types 重新生成并通过 typecheck。 |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS，0 warnings。 |
| `npm test -- --run` | PASS，18 files / 72 tests。 |
| `npm run build` | PASS。 |
| `npm run e2e` | PASS，35 tests。 |
| `npm run perf:compare` | PASS；monitor 785ms、market 598ms、paper 545ms、strategy-tracking 563ms；DOM nodes 均 36；每核心路由 1 条未登录 auth/me 事件，SSE/Worker/Chart/Mutation/UI 均 0。 |
| `npm run screenshot:parity` | PASS；9/9 新路由 compared，四档截图 captured；无 `navigation_error`、`app_error`、`page_errors`、`failed_api_responses`。 |

最新截图 similarity：monitor 0.9435、market 0.9488、paper 0.8505、strategy 0.9539、analysis 0.9307、playbook 0.9044、backtest 0.9161、data 0.9558、settings 0.9560。

平台影响：不影响。该修复只增强新前端纸面盘 display/review 动效的可访问性和资源释放；后端 API、真实写入、生产排序、`priority_board`、`production_score`、策略语义、旧前端和部署状态均不改变。

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、安全写契约、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 50. 2026-06-06 Final Verification After Paper Motion Hardening

状态：完成本轮机甲 reduced-motion 稳定性补强后的最终本地验证；不部署、不切流。

| 范围 | 命令 | 结果 |
|---|---|---|
| `frontend-next/` | `npm run api:check` | PASS |
| `frontend-next/` | `npm run typecheck` | PASS |
| `frontend-next/` | `npm run lint` | PASS |
| `frontend-next/` | `npm test -- --run` | PASS，18 files / 72 tests |
| `frontend-next/` | `npm run build` | PASS |
| `frontend-next/` | `npm run e2e` | PASS，35 tests |
| `frontend-next/` | `npm run perf:compare` | PASS，核心路由 DOM nodes 均 36，SSE/Worker/Chart/Mutation/UI 均 0 |
| `frontend-next/` | `npm run screenshot:parity` | PASS，9/9 新路由 compared，四档截图 captured，无页面错误或失败 API |
| `frontend/` | `npm run api:check` | PASS，包含 LibreSSL warning，退出码 0 |
| `frontend/` | `npm run typecheck` | PASS，通过 `api:check` 和 `build` 内部 typecheck 验证 |
| `frontend/` | `npm run lint` | PASS |
| `frontend/` | `npm test -- --run` | PASS，80 files / 274 tests；测试过程包含既有 state-separation guard 输出，但退出码为 0 |
| `frontend/` | `npm run build` | PASS |
| 仓库 | `git diff --check` | PASS，无输出 |

浏览器验证说明：已按 in-app Browser 流程连接并尝试本地 `/next/paper`，但该路由需要 E2E fixture 的 auth/API route mocking；Browser 直接访问会进入登录保护页，不能作为 paper 页面成功证据。本轮渲染证据采用项目 Playwright E2E 和 `screenshot:parity`：`paper-mecha.spec.ts` 验证机甲头像、Canvas 粒子、机型切换和 API 503 可见；`screenshot:parity` 生成 `/next/paper` 四档视口截图且无页面错误。

最终工作树状态：仍存在一个本轮未修改的旧前端脏文件 `frontend/src/features/trading-workspace/TradingWorkspaceChrome.test.ts`；本轮新前端和文档仍以未跟踪文件/目录存在。`git diff --name-only` 只列出该旧前端既有修改，因为本轮新增 `frontend-next/` 和文档尚未纳入 Git 跟踪。

平台影响：不影响。当前变更只在 `frontend-next/` 和相关文档内补齐新前端 paper display/review 动效稳定性、可访问性和验证证据；旧 `frontend/` 生产代码未被本轮编辑，后端生产代码未被本轮编辑，未修改 `strategy_policy.py`，未部署，未切流。

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、安全写契约、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 51. 2026-06-06 SSE Reconnect Stability Hardening

状态：补齐新前端 quote SSE 断连后的退避重连与 cleanup 取消逻辑；不部署、不切流、不改后端、不改旧前端生产代码。

| 项 | 结果 |
|---|---|
| 断连恢复 | `startQuoteSse` 在 `EventSource.onerror` 后关闭旧连接，按 1s 起步、最大 15s 的指数退避重连。 |
| 不重复连接 | 同 URL 多订阅继续共享单条 active/pending SSE；已有 pending reconnect 时新增订阅不会创建第二条连接。 |
| 离页释放 | 最后一个订阅者 cleanup 时会取消 pending reconnect timer，并关闭 active source，避免切页后后台重连。 |
| 诊断证据 | telemetry 新增 `reconnect-scheduled`、`closed-replaced` 等 SSE 状态，仅记录 attempt/delay，不记录 token、payload 或策略字段。 |
| 业务边界 | SSE 只更新 live quote display signals，不改变 `priority_board` 服务端顺序、`production_score`、策略语义或任何写入状态。 |

针对性验证：

| 命令 | 结果 |
|---|---|
| `npm test -- --run src/shared/realtime/__tests__/sseClient.test.ts` | PASS，1 file / 4 tests |
| `npm run typecheck` | PASS |

平台影响：不影响。该修复只增强新前端实时行情连接的可用性和资源释放；后端 API、真实写入、生产排序、`priority_board`、`production_score`、策略语义、旧前端和部署状态均不改变。

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、安全写契约、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 52. 2026-06-06 Final Verification After SSE Reconnect Hardening

状态：完成本轮 SSE 断连恢复补强后的最终本地验证；不部署、不切流。

| 范围 | 命令 | 结果 |
|---|---|---|
| `frontend-next/` | `npm run api:check` | PASS |
| `frontend-next/` | `npm run typecheck` | PASS |
| `frontend-next/` | `npm run lint` | PASS |
| `frontend-next/` | `npm test -- --run` | PASS，18 files / 74 tests |
| `frontend-next/` | `npm run build` | PASS |
| `frontend-next/` | `npm run e2e` | PASS，35 tests |
| `frontend-next/` | `npm run perf:compare` | PASS，monitor 727ms、market 549ms、paper 554ms、strategy-tracking 549ms；核心路由 DOM nodes 均 36；SSE/Worker/Chart/Mutation/UI 均 0 |
| `frontend-next/` | `npm run screenshot:parity` | PASS，9/9 新路由 compared，四档截图 captured，无页面错误或失败 API |
| `frontend/` | `npm run api:check` | PASS，包含 LibreSSL warning，退出码 0 |
| `frontend/` | `npm run typecheck` | PASS |
| `frontend/` | `npm run lint` | PASS |
| `frontend/` | `npm test -- --run` | PASS，80 files / 274 tests；测试过程包含既有 state-separation guard 输出，但退出码为 0 |
| `frontend/` | `npm run build` | PASS |

最新截图 similarity：monitor 0.9435、market 0.9487、paper 0.8505、strategy 0.9539、analysis 0.9307、playbook 0.9046、backtest 0.9161、data 0.9559、settings 0.9562。

请求/SSE 结果：`perf:compare` 当前 shadow profile 每个核心路由只有 1 条未登录 `GET /api/auth/me` 401 事件，SSE/Worker/Chart/Mutation/UI telemetry 均为 0；新增 SSE 重连逻辑由单测覆盖，未引入默认 EventSource。

平台影响：不影响。当前变更只在 `frontend-next/` 和相关文档内补齐新前端实时显示层 SSE 断连恢复和资源释放；旧 `frontend/` 生产代码未被本轮编辑，后端生产代码未被本轮编辑，未修改 `strategy_policy.py`，未部署，未切流。

仍不可自动 cutover：人工视觉签收、正式验收账号复跑、安全写契约、飞书通知目标/登录和用户明确 cutover 授权仍未完成。

## 53. 2026-06-07 Cutover Blocker Remediation Verification

状态：完成本轮 cutover 阻断项修复、脚本化验收和文档收敛；不部署、不切流。

### 完成项

| 分组 | 结果 |
|---|---|
| 安全写契约审计 | `write:readiness` 自动枚举 `safeWriteContracts.ts` 与 `operations.ts`；当前 13 contracts，12 production-ready，0 blocked，1 cutover-excluded，`cutover_ready=true`。 |
| API cutover readiness | `api:cutover-readiness` 本地 admin-token 环境 6 probes / 0 failed；`strategy-tracking-items`、BFF strategy/settings/monitor、`/api/settings`、`/api/settings/factor-weights` 均 2xx。 |
| 设置页 503 噪音 | `/next/settings` 改为 BFF-first，只有存在 admin API token 才访问直连管理接口。 |
| strategy-tracking 422 | 新前端请求 `limit=50`，对齐 OpenAPI max 50，未改后端。 |
| rollback smoke | `write:rollback -- --all --isolated` PASS；覆盖 auth MFA、watchlist、trade journal、paper account/order、settings、feature flag、backtest run/validation/optimization、playbook lifecycle、strategy review、data task、data repair、database check。 |
| Auth 稳定性 | 验证脚本新增本地临时 auth token 缓存和 429 时本地临时账号复用登录，减少重复注册造成的限流。 |
| 功能级 E2E | 新增 monitor/analysis/playbook/paper/strategy/backtest/data-settings readiness specs，覆盖 401/403、错误态和 no-write guard。 |
| CSS/视觉 | 新增 `css:budget`、`css:unused-report`、`visual:consistency`；未使用 PurgeCSS，未做破坏性 CSS 删除。 |

### 写操作 Ready 状态

| 指标 | 当前值 |
|---|---:|
| safe write contracts | 13 |
| production-ready contracts | 12 |
| blocked contracts | 0 |
| covered write operations | 30 |
| uncovered write operations | 7 |

当前本地安全写 readiness 已通过。`databaseMigrate` 保持 cutover-excluded，正式 cutover 前仍需在正式 admin token/environment 下复跑。

### API 复验

| Probe | 结果 |
|---|---|
| `strategy-tracking-items` | 200 |
| `strategy-workspace-bff` | 200 |
| `settings-workspace-bff` | 200 |
| `monitor-workspace-bff` | 200 |
| `/api/settings` | 200（本地 admin-token 环境） |
| `/api/settings/factor-weights` | 200（本地 admin-token 环境） |

页面层不会在普通无 admin token 环境误打 `/api/settings`；正式 cutover 前仍必须用正式 admin token 复验管理端点。

### 请求/SSE 与性能

| 路由 | API 请求数 | SSE | 性能采样 |
|---|---:|---:|---:|
| `/next/monitor` | 2 | 0 | 841ms / 230 DOM |
| `/next/monitor/market` | 2 | 0 | 588ms / 271 DOM |
| `/next/paper` | 2 | 0 | 680ms / 398 DOM |
| `/next/strategy-tracking` | 10 | 0 | 697ms / 361 DOM |
| `/next/settings` | 2 | 0 | `request:trace` 通过，BFF-first |

`perf:compare` 当前只采核心路由；ECharts 保持低频独立 chunk，K 线仍使用 Lightweight Charts/Canvas 方案，Worker 只做显示层计算。

### CSS

| 指标 | 当前值 |
|---|---:|
| source CSS files | 29 |
| source CSS bytes | 297152 |
| source CSS gzip bytes | 59504 |
| source CSS lines | 15551 |
| dist CSS files | 11 |
| dist CSS bytes | 239003 |
| dist CSS gzip bytes | 47925 |
| `!important` count | 51 |

CSS 只做预算和候选报告；`css:unused-report` 发现 110 个候选未引用 selector、588 个 known dynamic/legacy selector，未删除。

### 视觉与 Shadow

| Gate | 结果 |
|---|---|
| `screenshot:parity` | 9/9 captured，无导航错误、无页面错误、无失败 API；旧相似度仅保留历史参考。 |
| `visual:consistency` | 9 页 x 4 视口，共 36 captures，failed 0。 |
| `shadow:aggregate` | PASS；样本日期 `2026-06-05`、`2026-06-06`、`2026-06-07`；API/request-SSE/screenshot gates 均 true。 |

### 命令结果

| 范围 | 命令 | 结果 |
|---|---|---|
| `frontend-next/` | `npm run api:check` | PASS |
| `frontend-next/` | `npm run typecheck` | PASS |
| `frontend-next/` | `npm run lint` | PASS |
| `frontend-next/` | `npm test -- --run` | PASS，19 files / 86 tests |
| `frontend-next/` | `npm run build` | PASS |
| `frontend-next/` | `npm run e2e` | PASS，44 tests |
| `frontend-next/` | `npm run api:cutover-readiness` | PASS，本地 admin-token 环境 6 probes / 0 failed |
| `frontend-next/` | `npm run write:readiness` | PASS，12 production-ready / 0 blocked / 1 cutover-excluded |
| `frontend-next/` | `npm run write:rollback -- --all --isolated` | PASS，覆盖准备开放的写操作 |
| `frontend-next/` | `npm run css:budget` | PASS |
| `frontend-next/` | `npm run css:unused-report` | PASS，report only |
| `frontend-next/` | `npm run shadow:sample` | PASS |
| `frontend-next/` | `npm run shadow:aggregate` | PASS |
| `frontend-next/` | `npm run request:trace` | PASS |
| `frontend-next/` | `npm run screenshot:parity` | PASS |
| `frontend-next/` | `npm run visual:consistency` | PASS |
| `frontend-next/` | `npm run perf:compare` | PASS |
| `frontend/` | `npm run api:check` | PASS |
| `frontend/` | `npm run typecheck` | PASS |
| `frontend/` | `npm run lint` | PASS |
| `frontend/` | `npm test -- --run` | PASS，85 files / 299 tests |
| `frontend/` | `npm run build` | PASS |

### 代码边界

| 项 | 结论 |
|---|---|
| 旧 `frontend/` 生产代码 | 本轮未主动修改；旧前端校验命令通过。 |
| 后端生产代码 | 有最小改动：安全写审计、review-only 记录、runtime task cancel、OpenAPI 同步；不改变生产策略语义。 |
| `strategy_policy.py` | 未修改。 |
| 生产排序、`priority_board`、`production_score` | 未修改；新前端只展示后端返回顺序和字段。 |
| 部署/切流 | 未执行。 |

### 平台影响

不影响。当前变更作用于 `frontend-next/`、验收脚本、文档和少量安全写后端契约；未部署、未切流，旧生产入口不变，生产排序、`priority_board`、`production_score` 不变。

### 剩余未完成项

1. 正式环境需用正式 `ADMIN_API_TOKEN`/验收账号复跑 `api:cutover-readiness`、`write:readiness`、`write:rollback -- --all --isolated`。
2. `databaseMigrate` 仍 cutover-excluded，需要单独运维授权。
3. cutover 仍需用户单独授权；本轮未部署、未切流。
