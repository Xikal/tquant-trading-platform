# Frontend Next Backend Integration Report

日期：2026-06-06
范围：`frontend-next/` 本地后端联调，shadow-only，不部署、不切流

## 1. 初始状态

本轮联调开始前执行：

```bash
cd /Users/j/Documents/gupiao
git status --short
```

结果显示旧前端已有 1 个测试文件脏改，另有 `frontend-next/` 和文档/报告未跟踪；本轮未回退这些既有变更：

```text
 M frontend/src/features/trading-workspace/TradingWorkspaceChrome.test.ts
?? docs/frontend-next-architecture-design-2026-06-05.md
?? docs/frontend-next-cutover-runbook-2026-06-05.md
?? docs/frontend-next-feature-parity-matrix-2026-06-05.md
?? docs/frontend-next-legacy-ui-architecture-migration-development-doc-2026-06-06.md
?? docs/frontend-next-legacy-ui-architecture-migration-prompt-2026-06-06.md
?? docs/frontend-next-parity-completion-development-doc-2026-06-06.md
?? docs/frontend-next-parity-completion-implementation-prompt-2026-06-06.md
?? docs/frontend-next-parity-completion-requirements-2026-06-06.md
?? docs/frontend-next/
?? docs/reports/frontend-next-acceptance-2026-06-05.md
?? docs/reports/frontend-next-baseline-2026-06-05.md
?? docs/reports/frontend-next-claude-review-2026-06-06/
?? docs/reports/frontend-next-density-review-2026-06-06/
?? docs/reports/frontend-next-doc-consistency-audit-2026-06-06.md
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
?? docs/superpowers/plans/2026-06-06-frontend-next-legacy-ui-architecture-migration.md
?? frontend-next/
```

本地后端检查：

- `127.0.0.1:8000` 有 Python 进程监听。
- 未带 token 请求 `/api/auth/me` 返回 `401 {"detail":"请先登录"}`，说明后端在线且认证门禁生效。
- `frontend-next` 联调脚本通过临时 shadow auth token 访问受保护接口，未输出 token。

## 2. 本轮代码变更

只修改了新前端联调脚本：

- `frontend-next/scripts/perf-profile.mjs`

变更原因：`perf:compare` 原先没有注入临时 auth 状态，只测到登录态 401 空壳页面。现在复用 `installAuthState`，与 `api:parity`、`request:trace`、`screenshot:parity` 的联调认证方式保持一致。

未修改：

- 旧 `frontend/` 生产代码：未修改。
- 后端代码：未修改。
- `strategy_policy.py`：未修改。
- 生产策略语义、生产排序、`production_score`、`priority_board` 口径：未修改。

## 3. API 契约联调

命令：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run api:parity
```

结果：PASS。6 个受保护端点均返回 200。

| 页面 | API | 状态 |
|---|---|---:|
| monitor-action | `/api/bff/v1/workspace/monitor?...view=action` | 200 |
| monitor-market | `/api/bff/v1/workspace/monitor?...view=market` | 200 |
| paper | `/api/bff/v1/workspace/paper` | 200 |
| strategy-tracking | `/api/bff/v1/workspace/strategy` | 200 |
| backtest | `/api/backtests/runs` | 200 |
| settings | `/api/bff/v1/workspace/settings` | 200 |

`npm run api:check` 也已通过，OpenAPI generated types 可重新生成并完成 typecheck。

## 4. Shadow Sample 与两交易日聚合

命令：

```bash
START_LEGACY_FRONTEND=1 npm run shadow:sample
npm run shadow:aggregate
```

结果：

- `shadow:sample` PASS，报告：`docs/reports/frontend-next-shadow-sample-2026-06-05.json`
- `shadow:aggregate` PASS，报告：`docs/reports/frontend-next-two-day-shadow-run-2026-06-05.json`
- 聚合交易日：`2026-06-05`、`2026-06-06`
- `sample_count=6`

Gate：

| Gate | 结果 |
|---|---|
| 至少两个交易日 | PASS |
| API parity | PASS |
| request/SSE | PASS |
| screenshot capture | PASS |

## 5. 请求数量与 SSE

命令：

```bash
START_LEGACY_FRONTEND=1 npm run request:trace
```

结果：PASS。9 个旧新路由均无导航错误；旧新 `EventSource` 均为 0；新前端请求数均不高于旧前端。

| 旧路由 | 新路由 | 旧 API/unique | 新 API/unique | 旧/新 EventSource |
|---|---|---:|---:|---:|
| `/monitor` | `/next/monitor` | 10 / 7 | 2 / 2 | 0 / 0 |
| `/monitor/market` | `/next/monitor/market` | 10 / 7 | 2 / 2 | 0 / 0 |
| `/paper` | `/next/paper` | 11 / 8 | 2 / 2 | 0 / 0 |
| `/strategy-tracking` | `/next/strategy-tracking` | 18 / 9 | 9 / 9 | 0 / 0 |
| `/analysis` | `/next/analysis` | 11 / 8 | 1 / 1 | 0 / 0 |
| `/playbook` | `/next/playbook` | 11 / 8 | 6 / 6 | 0 / 0 |
| `/backtest` | `/next/backtest` | 16 / 10 | 2 / 2 | 0 / 0 |
| `/data` | `/next/data` | 9 / 6 | 1 / 1 | 0 / 0 |
| `/settings` | `/next/settings` | 10 / 7 | 1 / 1 | 0 / 0 |

结论：当前本地联调未发现重复 SSE，也未发现新前端请求膨胀。

## 6. 截图 Parity

`shadow:sample` 内含截图 parity，9 个页面均 compared。

| 新路由 | style similarity | legacy similarity | 新前端失败 API | 旧前端失败 API |
|---|---:|---:|---:|---:|
| `/next/monitor` | 0.9570 | 0.9389 | 0 | 0 |
| `/next/monitor/market` | 0.9518 | 0.9565 | 0 | 0 |
| `/next/paper` | 0.9361 | 0.9362 | 0 | 0 |
| `/next/strategy-tracking` | 0.9634 | 0.9541 | 0 | 0 |
| `/next/analysis` | 0.9410 | 0.9168 | 0 | 0 |
| `/next/playbook` | 0.9472 | 0.9241 | 0 | 0 |
| `/next/backtest` | 0.9646 | 0.9362 | 0 | 4 |
| `/next/data` | 0.9646 | 0.9897 | 0 | 0 |
| `/next/settings` | 0.9665 | 0.9600 | 0 | 0 |

截图目录：

- `docs/reports/frontend-next-screenshots-2026-06-05/`
- `docs/reports/frontend-next-density-review-2026-06-06/`

说明：`/backtest` 的失败 API 出现在旧前端截图流程中，主要是旧页面请求 `validate/optimize` 的受限接口；新前端本轮截图中没有失败 API。

## 7. 性能联调

命令：

```bash
npm run perf:compare
```

修复 auth 注入后复跑结果：PASS。核心路由 API 均为 200，SSE 为 0。

| 新路由 | elapsed_ms | DOM nodes | API telemetry | SSE |
|---|---:|---:|---:|---:|
| `/next/monitor` | 1120 | 261 | 2 个 ok | 0 |
| `/next/monitor/market` | 630 | 462 | 2 个 ok | 0 |
| `/next/paper` | 699 | 351 | 2 个 ok | 0 |
| `/next/strategy-tracking` | 648 | 159 | 9 个 ok | 0 |

说明：这是本地 Vite dev server + 本地后端 profile，`networkidle` 会受本机和后端状态影响；当前更适合作为联调健康证据，不等同生产性能基线。

## 8. 测试命令

本轮联调已执行：

| 命令 | 结果 |
|---|---|
| `npm run api:check` | PASS |
| `npm run api:parity` | PASS，6/6 受保护端点 200 |
| `START_LEGACY_FRONTEND=1 npm run shadow:sample` | PASS |
| `npm run shadow:aggregate` | PASS，交易日 `2026-06-05`、`2026-06-06` |
| `START_LEGACY_FRONTEND=1 npm run request:trace` | PASS |
| `npm run perf:compare` | PASS，auth 注入后复跑真实页面 |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS，19 files / 79 tests |

## 9. 结论

当前新前端可以对接本地后端做 shadow 联调，且主要读链路已通过：

- API 契约读取：通过。
- 旧新请求/SSE 对比：通过。
- 两交易日 shadow aggregate：通过。
- 截图 parity 捕获：通过。
- 核心路由 authenticated perf profile：通过。

是否影响平台功能：不影响。

原因：未部署、未切流、未改后端、未改旧 `frontend/` 生产代码、未改 `strategy_policy.py`，并且真实写入仍受 shadow/guard 约束。

## 10. 仍不可 Cutover 的原因

1. 旧新视觉人工签收仍未完成，`docs/reports/frontend-next-visual-signoff-2026-06-05.md` 仍为 `待签收`。
2. 正式验收账号/正式环境复跑仍未完成；本轮证据来自本地 shadow token 和本地后端。
3. strategy review/trade journal、data repair/backfill/task、settings 非 feature-flag、paper pause/resume/reconcile、backtest cancel/validate/optimize 等真实写闭环仍缺后端幂等/审计/回滚 live-smoke。
4. 用户尚未单独授权 cutover；本轮按硬边界不部署、不切流。
