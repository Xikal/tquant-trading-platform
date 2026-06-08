# Frontend Next Cutover Runbook - 2026-06-05

状态：cutover 预案，默认禁止执行
适用范围：未来 `frontend-next/` 完成 shadow/parity 后的可授权切流流程
最后核验日期：2026-06-07

## 一句话结论

默认不切流。`frontend-next/` 只能在所有 gate 通过并获得用户明确授权后，才允许从 `/next/*` shadow 模式进入页面级或默认入口 cutover。本文不是授权。

2026-06-07 最新状态：本地 readiness gate 已通过，包含 `api:cutover-readiness`、`write:readiness`、`write:rollback -- --all --isolated`、功能级 E2E、单测、构建、请求/SSE 和视觉一致性检查。仍未部署、未切流；正式 cutover 前必须用正式 admin token/environment 复跑，并获得用户单独授权。

## 禁止条件

任一条件成立时禁止 cutover：

1. 用户未明确授权。
2. 旧 `frontend/` 不可用或验证不通过。
3. `frontend-next/` 任一 P0 页面未通过数据 parity、截图 parity、交互 parity。
4. `priority_board`、`production_score`、生产排序或策略门控存在差异。
5. SSE 连接数重复或 BFF 请求数回归。
6. 核心页面性能慢于旧前端且没有批准豁免。
7. style spec 或 Web style image 缺失。
8. 回滚开关、旧入口或发布回滚路径未验证。

## Cutover 前置 Gate

| Gate | 必须结果 |
|---|---|
| Git 状态 | 无无关脏改；所有待发改动可解释 |
| 旧前端验证 | `api:check`、`typecheck`、`lint`、tests、build 通过 |
| 新前端验证 | `api:check`、`typecheck`、`lint`、tests、build、E2E、perf、screenshot parity 通过 |
| API parity | old/new 同用户同后端 payload 字段一致或兼容 |
| API cutover readiness | `api:cutover-readiness` 正式环境 0 failed |
| 安全写 readiness | `write:readiness` 正式环境 0 blocked，`databaseMigrate` 明确 excluded |
| 安全写 rollback | `write:rollback -- --all --isolated` 覆盖所有准备开放的写操作，含审计、403、读回一致 |
| 平台资源 readiness | `scripts/verify_platform_optimization_readiness.py --fail-on-blocking` 正式环境 0 blocking |
| Analytics manifest | `scripts/verify_analytics_manifests.py --fail-on-blocking` 目标数据集 0 missing / 0 blocked |
| 截图 parity | 每个目标页面匹配批准 Web style image |
| 性能 parity | 核心页面等于或优于旧前端 |
| 生产策略保护 | `priority_board` 顺序、`production_score`、策略状态无差异 |
| Shadow 观察 | 至少两个交易日无 P0/P1 问题 |
| 回滚演练 | 关闭新前端后旧入口可恢复 |

## 允许的 Cutover 级别

| 级别 | 说明 | 默认建议 |
|---|---|---|
| Level 0 | 仅 `/next/*` shadow，旧前端仍默认 | 默认保持 |
| Level 1 | 单页灰度到新前端，例如只切 `/monitor` | 需逐页授权 |
| Level 2 | P0 页面组合切流 | 需完整 P0 shadow 报告 |
| Level 3 | 新前端成为默认入口 | 需全量 parity、性能和回滚验收 |

## 授权模板

执行 cutover 前，必须有类似以下明确授权：

```text
授权执行 frontend-next cutover：级别 Level X，页面范围为 ...，允许部署/切流，保留 NEW_FRONTEND_ENABLED=false 回滚。
```

没有这类明确授权时，只能继续 shadow、验证或写文档。

## 标准执行步骤

1. 记录执行前状态：

```bash
cd /Users/j/Documents/gupiao
git status --short
```

2. 跑旧前端验证：

```bash
cd /Users/j/Documents/gupiao/frontend
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
```

3. 跑新前端验证：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run e2e
npm run perf:compare
npm run screenshot:parity
```

4. 核对 parity 报告：

```text
docs/reports/frontend-next-acceptance-YYYY-MM-DD.md
docs/frontend-next-feature-parity-matrix-2026-06-05.md
docs/frontend-next/style-specs/*.md
docs/frontend-next/style-specs/images/*.png
```

5. 按授权级别启用新前端路由或开关。

6. 切流后立即验证：

```text
/monitor 或授权页面可访问
/next/* shadow 仍可访问
生产优先榜顺序一致
feature flag 状态一致
SSE 连接数无重复
BFF 请求数无回归
```

7. 记录结果到 acceptance report。

## 回滚方式

首选回滚：

```text
NEW_FRONTEND_ENABLED=false
```

等价回滚必须恢复：

1. 默认入口指回旧 `frontend/`。
2. `/monitor`、`/strategy-tracking`、`/paper`、`/backtest`、`/analysis`、`/playbook`、`/data`、`/settings` 回旧实现。
3. `/next/*` 可保留为 shadow 或暂时下线，但不能影响旧入口。
4. 后端服务、策略引擎、Worker 队列、数据库事实源不变。

回滚后验证：

```bash
cd /Users/j/Documents/gupiao/frontend
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
```

并人工核对：

```text
/monitor 旧页面可访问
生产优先榜顺序与回滚前旧前端基线一致
模拟盘和策略跟踪数据可读
settings feature flag 状态正常
```

## 不影响生产策略的控制点

1. 切流只改变展示入口，不改变后端策略计算。
2. `priority_board` 只展示后端返回顺序。
3. `production_score` 只展示后端字段。
4. 研究、观察、shadow、paper 状态不能进入生产排序。
5. Worker/WASM 不参与生产策略判断。
6. 任何生产边界变化都不属于本 runbook，必须另立计划、测试和授权。

## 事故处理

| 现象 | 立即动作 | 回滚后检查 |
|---|---|---|
| 页面无法访问 | 关闭新前端开关，恢复旧入口 | 旧前端 build 产物、路由、静态资源 |
| 数据字段缺失 | 回滚旧前端，保留 payload 证据 | OpenAPI/generated types 差异 |
| 优先榜顺序差异 | 立即回滚，冻结 cutover | 是否存在前端本地生产 re-sort |
| SSE 重复 | 回滚或关闭新 SSE client | connection lifecycle 和重连策略 |
| 性能明显退化 | 回滚授权页面 | bundle、长任务、虚拟列表和图表 profile |

## 当前状态

截至 2026-06-07，`frontend-next/` 已具备 `/next/*` shadow、本地联调、功能级 E2E、视觉一致性、请求/SSE trace、两交易日 shadow aggregate、CSS/性能报告、安全写 readiness 和完整隔离 rollback 证据。本地 readiness 已通过；当前默认生产路径仍是旧 `frontend/`，本轮工作不部署、不切流，不影响平台功能。

## 2026-06-07 Cutover 前新增硬门槛

以下门槛全部满足前，禁止执行切流：

| Gate | 当前状态 | 切流前必须达到 |
|---|---|---|
| `npm run api:cutover-readiness` | 本地 PASS；6 probes / 0 failed | 正式 admin/token 环境下全部 probes 200，报告 `cutover_ready=true`。 |
| `npm run write:readiness` | 本地 PASS；13 contracts，12 production-ready，0 blocked，1 cutover-excluded | 所有准备 cutover 的写 operation 有 generated types、client_request_id/idempotency、audit、403、rollback、读回一致证据；0 blocked contracts。 |
| `npm run write:rollback -- --all --isolated` | 本地 PASS；覆盖准备开放的写操作 | 正式隔离账号 + admin token 下覆盖 feature flag、paper、backtest、playbook、strategy review、data task、data repair 以及所有准备开放的写操作。 |
| `npm run visual:consistency` | PASS | 保持 9 页 x 4 视口无页面错误、无横向溢出、无失败 API；视觉以新前端当前体系为准。 |
| `npm run shadow:aggregate` | PASS | 保持至少两个交易日样本，API/request-SSE/screenshot gates 均 true。 |
| 用户授权 | 未授权 | 用户单独明确授权 cutover；本轮“全部授权”不等于生产切流授权。 |

切流命令前必须重新运行并归档：

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
npm run request:trace
npm run visual:consistency
npm run perf:compare
```

平台资源 gate 同步执行并归档：

```bash
cd /Users/j/Documents/gupiao
python3 scripts/collect_platform_resource_report.py \
  --json-output docs/reports/platform-resource-baseline-$(date +%F).json \
  --markdown-output docs/reports/platform-resource-baseline-$(date +%F).md
python3 scripts/verify_platform_budget.py \
  --json-output docs/reports/platform-budget-$(date +%F).json \
  --markdown-output docs/reports/platform-budget-$(date +%F).md
python3 scripts/verify_analytics_manifests.py \
  --json-output docs/reports/platform-analytics-manifests-$(date +%F).json \
  --markdown-output docs/reports/platform-analytics-manifests-$(date +%F).md \
  --fail-on-blocking
python3 scripts/verify_platform_optimization_readiness.py \
  --json-output docs/reports/platform-optimization-readiness-$(date +%F).json \
  --markdown-output docs/reports/platform-optimization-readiness-$(date +%F).md \
  --fail-on-blocking
```

资源 gate 失败即停止，不进入部署或切流。失败项必须回到 `docs/operations/mysql-maintenance-runbook.md` 的维护窗口流程处理；不得通过删除 MySQL `.ibd`、直接删除 binlog 或 Docker volume 规避。

旧前端仍需保持：

```bash
cd /Users/j/Documents/gupiao/frontend
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
```
