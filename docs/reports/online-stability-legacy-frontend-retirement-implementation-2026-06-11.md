# 线上稳定性整改与旧前端退役本地实施报告

- 检查/实施时间：2026-06-11
- 工作目录：`/Users/j/Documents/gupiao`
- 批次性质：本地代码、测试、报告；未部署、未切流、未重启、未清理、未改线上配置、未写生产数据库
- 依据计划：`docs/superpowers/plans/2026-06-11-online-stability-legacy-frontend-retirement-integrated-plan.md`
- 关联审计：`docs/reports/online-service-status-audit-2026-06-11.md`
- 旧前端依据：`docs/reports/legacy-frontend-retirement-execution-2026-06-10.md`、`docs/reports/legacy-frontend-retirement-decision-2026-06-11.md`

## 开始前状态

开始前按要求执行 `git status --short`，当时仅有两份未跟踪文档：

```text
?? docs/reports/online-service-status-audit-2026-06-11.md
?? docs/superpowers/plans/2026-06-11-online-stability-legacy-frontend-retirement-integrated-plan.md
```

本轮新增和修改均在本地完成，未覆盖上述未跟踪文档。

## 改动摘要

| 方向 | 文件 | 结果 |
| --- | --- | --- |
| removed paper runtime task 收口 | `backend/app/services/tasks/queue.py` | 增加 `skipped` 终态与 `mark_skipped`；skipped 不进入 failed、不 retry、释放 idempotency key |
| removed paper runtime task 收口 | `backend/app/workers/runtime_worker.py` | runtime worker 会领取已移除 paper task 并标记 `skipped_removed_feature`；保留直接执行时的 removed feature 错误 |
| low-buy 失败隔离 | `backend/app/services/low_buy_materialization.py` | 只把参与 priority board 的生产策略作为必需策略；研究/非生产策略缺失标记 `skipped_strategies`，不拖垮整批 |
| low-buy 失败隔离 | `backend/app/workers/runtime_worker.py` | worker 错误口径改为 `missing_required_strategies`；生产必需策略缺失仍失败 |
| readyz 稳定性 | `backend/app/main.py` | DB readiness 增加 1s 短超时；使用单线程共享 probe，避免数据库卡住时每个请求堆积新线程 |
| 旧前端退役 guard | `Dockerfile.prebuilt` | 预构建镜像入口改为 `frontend-next-dist -> /app/frontend-next/dist`，移除旧 `/app/frontend/dist` 回流路径 |
| 测试覆盖 | `backend/tests/*` | 增加 skipped 终态、paper task skip、low-buy 非生产策略隔离、readyz timeout、prebuilt Dockerfile guard 测试 |

## 核心任务保护

- 未修改 `backend/app/services/low_buy/strategy_policy.py`。
- 未修改 `production_score` 计算逻辑。
- 未修改 priority board 排序实现和展示口径。
- 未停用行情刷新、日线刷新、低吸榜、推荐榜、priority board 物化、watchdog、数据新鲜度检查。
- 未恢复 `/paper` 或 `/next/paper` 页面入口。
- 未新增 `PAPER_RUNTIME_TASKS_ENABLED`，因为 active 模拟盘功能已经下线。
- 未删除 `frontend/` 源码目录。

## 关键行为

### removed paper task

- `paper_review_report`、`paper_portfolio_execution_preview`、`paper_ledger_reconcile_preview` 和 `paper_` 前缀任务被识别为已移除模拟盘任务。
- worker 会领取这些残留任务并写入：
  - `status=skipped`
  - `result.status=skipped_removed_feature`
  - `result.reason=removed_feature`
  - `result.feature=paper_trading`
- skipped 任务：
  - 不计入 failed
  - 不设置 retry `run_after`
  - 不再次被 claim
  - 会释放 `active_idempotency_key`

`runtime_tasks.status` 是普通 `String(24)` 字段，无 enum/check 约束，本轮不需要数据库迁移。

### low-buy materialization

- 生产必需策略由 `participates_in_priority_board(strategy)` 判断。
- 只有生产必需策略缺失时，`low_buy_materialization_refresh` 才失败。
- 研究/非生产/禁用策略缺失时，结果保留：
  - `skipped_strategies`
  - `is_partial=true`
  - `stale_reason=skipped_non_production_strategies`
- 不伪造数据，不补空结果，不改变分数和排序。

### readyz

- `/readyz` 的数据库探测不再无限等待同步 `ping_database()`。
- 默认短超时为 1s。
- 超时时返回 degraded，错误形如 `database: timeout_after_1.00s`。
- 使用单个共享 DB probe 线程，避免数据库长时间无响应时健康检查请求持续增加后台线程。

### BFF/provider

本轮未改 BFF/provider 主流程代码。复核结果显示现有代码已经具备：

- BFF workspace 总超时与 source 级超时。
- 慢源/异常源写入 `partial_errors`，核心 payload 降级返回。
- monitor workspace 请求优先使用 cached/materialized data，避免热路径同步等待外部慢源。
- market quote cache 有 stale 命中、async provider fallback 和 daily fallback 测试覆盖。

本轮通过目标测试验证这些保护仍有效。

### 旧前端退役

- 根 `Dockerfile` 已使用 `frontend-next/dist`。
- 本轮把 `Dockerfile.prebuilt` 从旧 `frontend-dist` 改为 `frontend-next-dist`。
- 已有 deploy scope 保持：
  - `frontend/` 变更只进入 `verify-only`
  - 显式 `frontend-hot` / `frontend-legacy` scope 被 blocked
  - 主部署脚本不构建旧 `Dockerfile.frontend-hot`
  - nginx 不再提供 `/__legacy/assets/`

旧 `frontend/` 物理删除仍不在本轮范围内。

## 测试结果

```text
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_phase4_runtime_worker_tasks.py \
  backend/tests/test_low_buy_materialization_priority_board.py \
  backend/tests/test_frontend_next_level1_cutover.py -q

43 passed, 1 warning
```

```text
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_bff_routes.py \
  backend/tests/test_bff_monitor_workspace.py \
  backend/tests/test_bff_strategy_workspace.py \
  backend/tests/test_bff_settings_workspace.py \
  backend/tests/test_market_provider_contract.py \
  backend/tests/test_market_quote_cache_refresh.py \
  backend/tests/test_deploy_scope.py \
  backend/tests/test_cloud_deploy_scripts.py -q

107 passed, 1 warning
```

合计目标测试：150 passed。警告为本地 Python/urllib3 的 LibreSSL 提示，不影响本轮改动结论。

## 本轮未执行操作

- 未执行 `docker restart/down/up/stop/start`。
- 未执行 `systemctl restart`。
- 未执行 `nginx reload`。
- 未执行 Docker prune、磁盘清理、日志清理。
- 未修改线上 `.env`、compose、nginx 配置。
- 未写生产数据库。
- 未部署、未切流。
- 未删除旧 `frontend/`。

## 上线启用步骤

以下仅为建议，需要用户明确授权后才能执行：

1. 合并本地代码并走 CI。
2. 选择部署窗口，先部署 backend/runtime worker 相关代码。
3. 部署后检查 `/readyz`、`/api/readyz`、`/api/bff/v1/workspace/monitor`、`/api/monitor/snapshot`、`/api/priority-board`。
4. 查看 runtime task summary，确认 removed paper task 进入 `skipped`，failed 不再增长。
5. 查看 low-buy materialization 日志，确认非生产策略缺失只进入 `skipped_strategies`，生产必需策略缺失仍报警失败。
6. 观察至少一个完整交易时段，确认行情刷新、日线刷新、低吸榜、推荐榜、priority board 物化、watchdog 无回退。

## 回滚方案

如果部署后出现异常，建议按影响范围回滚到上一版镜像或上一提交：

- readyz 异常：回滚 `backend/app/main.py` 相关变更。
- runtime task 状态异常：回滚 `backend/app/services/tasks/queue.py` 与 `backend/app/workers/runtime_worker.py`。
- low-buy 物化异常：回滚 `backend/app/services/low_buy_materialization.py` 与 worker 错误口径变更。
- prebuilt 镜像 artifact 异常：回滚 `Dockerfile.prebuilt`，但不要恢复旧前端线上入口；先暂停使用 prebuilt 镜像路径并改走常规根 `Dockerfile`。

## 仍需授权的后续项

| 项目 | 是否需要授权 | 说明 |
| --- | --- | --- |
| 线上部署本批代码 | 是 | 涉及 backend/runtime worker 行为变化 |
| 线上重启 worker/API | 是 | 部署生效需要受控重启或滚动替换 |
| 清理历史 failed paper task | 是 | 需要生产数据库写操作，本轮未做 |
| 清理线上旧镜像/旧容器/旧 dist | 是 | 属于清理和潜在资源释放，本轮未做 |
| 物理删除 `frontend/` | 是 | 需独立批次、归档 tag/branch、native/mobile owner review、引用复扫 |
