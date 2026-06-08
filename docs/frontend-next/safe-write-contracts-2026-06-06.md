# Frontend Next Safe Write Contracts - 2026-06-06

状态：安全写契约定义完成，后端实现和隔离 live-smoke 未执行
适用范围：`frontend-next/` 所有 `shadow-only`、`live-smoke`、`blocked_contract_needed` 写入

## 结论

本文件把 `frontend-next` 危险写入从“缺契约”收敛为“契约已定义、待后端实现和隔离验证”。当前不部署、不切流、不修改后端、不修改旧 `frontend/` 生产代码，不修改 `strategy_policy.py`，不改变生产策略语义、生产排序、`production_score` 或 `priority_board`。

安全写契约定义已经落到前端 registry：

- `frontend-next/src/shared/api/safeWriteContracts.ts`
- `frontend-next/src/shared/api/mutations.ts`
- `frontend-next/src/shared/api/__tests__/mutations.test.ts`
- `frontend-next/src/shared/api/__tests__/operations.test.ts`

注意：契约定义不等于真实写入可用。任何危险写入仍必须满足后端实现、隔离账号或测试数据、审计回显、回滚证据和用户授权后，才允许进入 `isolated-live-smoke`。

## 通用安全写协议

所有危险写入必须同时满足：

1. 使用 OpenAPI generated types，不手写重复 DTO。
2. 请求包含 `client_request_id` 或等价幂等键。
3. 页面进入二次确认后才允许提交。
4. `VITE_FRONTEND_NEXT_WRITE_ENABLED=true` 只能打开 guard，不绕过契约状态。
5. `VITE_FRONTEND_NEXT_WRITE_MODE=isolated-live-smoke` 只允许 `contractStatus=live-smoke` 且权限满足的 operation。
6. `live` 模式本阶段禁止。
7. admin 写入必须有 admin guard、403 fixture 和审计回显。
8. dry-run/apply 类动作必须先 dry-run，apply 必须引用 dry-run id 或 apply token。
9. create/apply 后必须有 cancel/rollback/reset/restore 证据。
10. UI 不得显示“保存成功/写入成功”，除非响应来自真实后端且回显可验证。
11. telemetry、错误文案和审计摘要不得记录 token、secret、password、cookie、authorization 或完整 payload。
12. 写入不得改变生产排序、`priority_board` 服务端顺序、`production_score`、策略语义或 research/production 边界。

## 契约状态词典

| 状态 | 含义 | 当前发送规则 |
|---|---|---|
| `defined_shadow_only` | 只有 shadow/no-write 意图记录，暂不设计真实写 | mutation guard 不发送请求 |
| `defined_backend_needed` | 已定义请求、响应、审计和回滚要求，但后端或隔离数据未完成 | mutation guard 返回 `blocked_contract_needed` |
| `defined_isolated_live_smoke` | 契约和现有后端路径可支撑隔离 smoke，但仍需用户授权与回滚证据 | 只有 `isolated-live-smoke` + 权限满足才可发送 |

## 契约清单

| Contract ID | 范围 | operations | 状态 | 必须角色/模式 | 关键回滚证据 |
|---|---|---|---|---|---|
| `FNX-SW-AUTH-MFA` | MFA setup/enable/disable | `authTotpSetup`、`authTotpEnable`、`authTotpDisable` | `defined_backend_needed` | authenticated + isolated smoke | 隔离账号恢复原 MFA 状态 |
| `FNX-SW-WATCHLIST` | 观察池维护 | `watchlistUpsert`、`watchlistRemove` | `defined_backend_needed` | authenticated observer + isolated smoke | 删除新建项或恢复旧快照 |
| `FNX-SW-PLAYBOOK-LIFECYCLE` | playbook 生命周期/治理 | `lowBuyLifecycleUpdate`、`lowBuyStrategyUpdate` | `defined_backend_needed` | admin/strategy operator + isolated smoke | 恢复 lifecycle/strategy snapshot |
| `FNX-SW-PAPER-ORDER` | 模拟委托创建/撤销 | `paperOrderCreate`、`paperOrderCancel` | `defined_isolated_live_smoke` | `can_paper_trade` + live-smoke operator | cancel order 或 reset 隔离模拟盘账号 |
| `FNX-SW-PAPER-ACCOUNT` | pause/resume/reconcile/refresh | `paperAccountPause`、`paperAccountResume`、`paperAccountReconcile`、`paperPositionsRefresh` | `defined_backend_needed` | paper 权限；reconcile 需 admin | 恢复账户状态或 reset 隔离账号 |
| `FNX-SW-STRATEGY-REVIEW` | 复盘记录/刷新 | `strategyReviewRecord`、`strategyTrackingRefresh` | `defined_backend_needed` | reviewer + isolated smoke | 删除复盘或恢复 review snapshot |
| `FNX-SW-TRADE-JOURNAL` | 交易日志 CRUD | `tradeJournalCreate` | `defined_backend_needed` | authenticated observer + isolated smoke | 删除新建日志或恢复旧日志 |
| `FNX-SW-BACKTEST-TASK` | 回测 create/cancel/validate/optimize | `backtestRunCreate`、`backtestRunCancel`、`backtestValidationCreate`、`backtestOptimizationCreate` | `defined_isolated_live_smoke` | authenticated + live-smoke operator | cancel task 或 soft-delete test run |
| `FNX-SW-DATA-TASK` | 数据任务/回补入队 | `dataJobSubmit`、`dataQualityBackfill`、`runtimeTaskCreate` | `defined_backend_needed` | admin + live-smoke operator | cancel queued test task |
| `FNX-SW-DATA-REPAIR` | 数据修复 dry-run/apply | `dataQualityRepair` | `defined_backend_needed` | admin + live-smoke operator | rollback repair_id 或恢复数据快照 |
| `FNX-SW-SETTINGS-SECTION` | 设置分区保存 | `settingsUpdate`、`sectorExclusionsUpdate`、`factorWeightsUpdate` | `defined_backend_needed` | section role + isolated smoke | restore previous section version |
| `FNX-SW-FEATURE-FLAG` | feature flag 更新 | `featureFlagUpdate` | `defined_isolated_live_smoke` | admin + live-smoke operator | restore previous flag value and audit echo |
| `FNX-SW-DATABASE-MAINTENANCE` | 数据库检查/迁移 | `databaseCheck`、`databaseMigrate` | `defined_backend_needed` | admin + live-smoke operator | dry-run report + documented rollback plan |

## 前端实现约束

`createMutationClient` 当前必须保持：

- `shadow` 模式不发送真实写请求。
- `blocked_contract_needed` 不发送真实写请求。
- `shadow-only` 不发送真实写请求。
- 写请求 401 不自动 refresh+retry，避免重复提交。
- admin operation 非 admin 不发送请求。
- mutation telemetry 只记录 operation、method、endpoint、contract status、write mode、safe write contract id、client request id 和 guard 结果，不记录 payload。

## 前端请求证据链

当且仅当 operation 已通过 `writeEnabled`、`writeMode`、contract status、admin/paper 等 guard，且即将真实发送到后端时，`createMutationClient` 会为请求附加以下 header：

| Header | 用途 |
|---|---|
| `X-Frontend-Next-Client-Request-Id` | 前端生成的单次请求追踪 ID，格式以 `fnx-<operation>-` 开头。 |
| `X-Frontend-Next-Contract-Id` | 对应 `FNX-SW-*` 安全写契约 ID。 |
| `X-Frontend-Next-Contract-State` | 当前契约状态，例如 `defined_isolated_live_smoke`。 |
| `X-Frontend-Next-Operation` | 对应 `ApiOperationName`。 |
| `X-Frontend-Next-Source` | 固定为 `frontend-next`。 |
| `X-Frontend-Next-Write-Mode` | 当前写模式，例如 `isolated-live-smoke`。 |

约束：

- 不修改请求 body，避免向现有后端 DTO 注入额外字段。
- 不在 header、telemetry 或 UI 中记录 token、secret、password、cookie 或业务 payload。
- blocked/shadow-only/write-disabled/mode-blocked/permission-blocked 分支不会生成 live 请求 ID，也不会调用 requester。
- header 证据不能替代后端幂等、审计回显和回滚证据；它只是 isolated live-smoke 的前端侧追踪基础。

## 本地 isolated live-smoke 状态

`frontend-next/scripts/write-rollback-smoke.mjs` 当前支持本地 sqlite 隔离 smoke：

- `paperOrderCreate`：临时账号 create paper order 后 `POST /api/paper/account/reset` 回滚。
- `featureFlagUpdate`：运行时读取当前后端 feature flag 列表，优先选择 `frontend_*`，否则选择低风险 UI 开关 `playbook_lazy_load_enabled`/`smart_mode_enabled`，toggle 后 restore。
- `backtestRunCreate`：临时账号 create backtest run 后 `DELETE /api/backtests/{run_id}` 回滚。
- 每个 live-smoke 写请求均附加 `X-Frontend-Next-*` header，并在 JSON 报告里写入 `request_evidence.contract_id` 与 `request_evidence.client_request_id`。
- 脚本只在 `FRONTEND_NEXT_LOCAL_ADMIN_PROMOTE=1` 且数据库 URL 为 sqlite 时允许临时 admin promote，并在 finally cleanup 中删除本次临时 `frontend_next_smoke_*` 用户、session、paper account 和本次 backtest run。

最新本地证据：`FRONTEND_NEXT_LOCAL_ADMIN_PROMOTE=1 FRONTEND_NEXT_LIVE_WRITE_SMOKE=1 FRONTEND_NEXT_LIVE_ADMIN_WRITE_SMOKE=1 FRONTEND_NEXT_LIVE_BACKTEST_SMOKE=1 npm run write:rollback` PASS，报告路径 `docs/reports/frontend-next-write-rollback-smoke-2026-06-05.json`，三项 `live_results` 均 `ok=true`。

## 后端契约待实现要求

后续若实现后端安全写，每个 operation 必须补：

1. OpenAPI request/response schema。
2. 幂等字段或 server-side idempotency。
3. 审计表或审计响应字段。
4. rollback/cancel/reset/restore API 或明确可验证的回滚流程。
5. 403/422/409/429/5xx 错误语义。
6. 隔离账号、测试 run、测试 task 或 bounded dataset 标记。
7. 对应 backend tests 和 frontend `api:check`。

## 验收门槛

任一契约进入 `isolated-live-smoke` 前必须提供：

| 证据 | 要求 |
|---|---|
| OpenAPI | `docs/contracts/openapi.json` 更新并生成 `frontend-next/src/generated/api-types.ts` |
| 权限 | anonymous/non-admin/no-paper 负例 fixture |
| 请求 | request trace 证明只发送预期写请求 |
| 审计 | 响应或 audit endpoint 能查到 operator/action/before/after |
| 回滚 | create/apply 后 cancel/rollback/reset/restore 成功 |
| UI | 成功只显示真实后端回显；失败保留草稿 |
| 平台边界 | 证明不改变 `priority_board`、`production_score`、生产策略语义 |

## 当前仍保持 blocked 的原因

契约定义完成后，以下项不再是“需求不清”，但仍不能真实写：

- `strategy review/trade journal`：后端 review CRUD、journal update/delete、隔离数据和 rollback 仍未实现/未验证。
- `data repair/backfill/task/ETF池`：缺 dry-run/apply/cancel/rollback 的完整后端和隔离环境证据。
- `settings 非 feature-flag 写入`：缺 section version、save echo 和 restore previous version。
- `paper pause/resume/reconcile`：缺隔离模拟盘账号状态恢复和 reconcile rollback。
- `backtest cancel/validate/optimize`：缺测试 run/task 标记和 cancel/delete 证据。
- `MFA/数据库维护/playbook lifecycle/watchlist`：契约已定义，但后端安全写验收未完成。

## 回滚方式

本轮只新增 `frontend-next` registry 和文档。回滚方式：

1. 删除 `frontend-next/src/shared/api/safeWriteContracts.ts`。
2. 还原 `frontend-next/src/shared/api/mutations.ts` 中 `safeWriteContract` 返回字段和 blocked message。
3. 还原新增单测断言。
4. 删除本文和各报告追加段。

该回滚不涉及生产数据、旧前端、后端、部署或切流。
