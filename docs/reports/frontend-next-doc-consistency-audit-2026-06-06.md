# Frontend Next Doc Consistency Audit - 2026-06-06

状态：文档一致性审计与最新证据收敛报告，未部署，未切流

## 审计范围

本报告核对以下文件与最新自动化证据是否一致：

- `docs/reports/frontend-next-acceptance-2026-06-05.md`
- `docs/reports/frontend-next-open-items-2026-06-05.md`
- `docs/frontend-next/traceability-matrix-2026-06-06.md`
- `docs/frontend-next/permissions-matrix-2026-06-06.md`
- `docs/frontend-next/optimization-registry-2026-06-06.md`

硬边界：未部署、未切流、未改后端、未改 `strategy_policy.py`、未改旧 `frontend/` 生产代码。

## 最新权威证据

| 证据 | 最新结果 |
|---|---|
| `npm run api:check` | PASS |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS，8 files / 30 tests |
| `npm run build` | PASS |
| `npm run e2e` | PASS，27/27 |
| `npm run perf:compare` | PASS |
| `npm run screenshot:parity` | PASS，9/9 新路由无错误 |
| `START_LEGACY_FRONTEND=1 npm run request:trace` | PASS，新路由请求数均低于旧路由，EventSource 全为 0 |
| `START_LEGACY_FRONTEND=1 npm run screenshot:parity && npm run visual:review` | PASS，9 页 ready-for-human-signoff |
| `FRONTEND_AUTH_TOKEN=<existing-local-shadow-token> npm run shadow:aggregate` | PASS，交易日 `2026-06-05`、`2026-06-06`，`sample_count=5` |
| `FRONTEND_AUTH_TOKEN=<existing-local-shadow-token> npm run write:rollback` | PASS，默认写入关闭，`live_results=[]` |

## Stale 段落登记

| 文件 | 旧声明 | 最新处理 |
|---|---|---|
| `frontend-next-acceptance-2026-06-05.md` | 早期章节仍包含 shell/style ready、两交易日未完成、旧测试数量等历史状态 | 追加第 18 节作为最新 closeout，明确本轮稳定性/权限硬化和最新命令结果。 |
| `frontend-next-open-items-2026-06-05.md` | 早期“当前未完成”表仍含两交易日 1/2、矩阵大量 gap_open 等旧状态 | 追加“稳定性与权限硬化后最新状态”，当前未完成只保留真实 open 项。 |
| `traceability-matrix-2026-06-06.md` | 初版主表保留大量 `gap_open` | 已有最新 evidence update 段覆盖；后续如做 cutover 准备，应将主表拆为历史初版和最新状态表。 |
| `permissions-matrix-2026-06-06.md` | 初版主表保留大量 `gap_open` | 追加“最新权限硬化证据”，覆盖已过期状态并列出仍需 open 的权限/写入项。 |
| `optimization-registry-2026-06-06.md` | 初版矩阵大量 `planned/evidence_needed` | 追加“最新优化收敛证据”，逐项标注 ready/shadow/blocked 最新状态。 |

## 状态收敛摘要

| 类别 | 最新状态 |
|---|---|
| 页面读链路和 route guard | `ready_for_cutover_review` |
| 观察池/模拟委托/回测提交等默认动作 | `shadow-only` |
| 缺契约危险写入 | `blocked_contract_needed` |
| 视觉人工签收 | open |
| 正式验收账号复跑 | open |
| cutover/部署 | open，需单独授权 |

## 写入证据一致性

当前最新 `write:rollback` 只证明默认写入关闭和 guard 生效，`live_results=[]`。不得把它解释为完整 live-smoke 通过。

live-smoke 的最低条件：

1. 用户单独授权。
2. 隔离账号或测试 run 标记。
3. admin/token 权限明确。
4. create/apply 后有 rollback/reset/cancel 证据。
5. 审计回显可追踪。

## 当前仍需 Open

| 项 | 原因 |
|---|---|
| 旧新视觉人工签收 | 9 张 review PNG 已生成但未人工签收，`/paper` similarity 0.8503 需确认机甲/完整 tab 布局是否接受。 |
| 正式验收账号复跑 | 当前证据主要来自本地 shadow token 和 E2E fixture。 |
| strategy review/trade journal 真实写 | 缺安全写契约、隔离数据和回滚路径。 |
| data repair/backfill/task 真实写 | 缺 dry-run/apply/cancel 契约和回滚路径。 |
| settings 非 feature-flag 写入 | 缺分区保存、回显、回滚契约。 |
| paper pause/resume/reconcile | 需隔离模拟盘账号和 rollback。 |
| backtest cancel/validate/optimize | 需测试 run 标记和回滚/取消证明。 |
| cutover/部署 | 本轮未授权执行。 |
| 飞书通知 | `lark-cli` 无用户登录且无目标会话。 |

## 平台影响

不影响。所有本轮新增稳定性和权限改动位于 `frontend-next/` 和文档层；未改变生产策略语义、生产排序、`production_score`、`priority_board` 口径。
