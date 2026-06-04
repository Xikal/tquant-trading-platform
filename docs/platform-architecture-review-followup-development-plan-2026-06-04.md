# 平台架构复审后续优化开发文档

日期：2026-06-04  
项目路径：`/Users/j/Documents/gupiao`  
性质：复审后下一阶段开发计划  
依据：`docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md`、架构复审结论、当前线上运行状态  

## 1. 当前结论

当前架构基线已经基本实现：

1. Web、runtime-worker、runtime-scheduler、analytics-worker、backtest-worker 已独立运行。
2. RuntimeTaskQueue 已支持任务提交、认领、进度、重试、失败、产物和事件。
3. Analytics worker 已接入 DuckDB/Parquet、24 个月数据质量检查和策略报告。
4. OpenAPI → frontend generated types → typecheck 的契约链路可用。
5. Strategy Engine 已有 gate/output/adapter 基线。
6. Execution Model 已有事件、规则、recommendation 和 parity preview 基线。
7. 前端页面分工和信息降噪已完成到可验收状态。

但当前不能表述为“所有核心路径已完全替换”：

1. `strategy_engine` 当前是并行 adapter，默认关闭，不替换生产排序。
2. `execution_model` 当前是 parity preview，`replacement_enabled=false`，不替代既有 `portfolio_backtest_metrics` 事实源。
3. B6 线上验收报告仍有 pending 字段，需要补最新线上证据。
4. 24 个月数据质量中的 `coverage_pct` 可能超过 100%，需要修正语义，避免误导。
5. 前端仍保留一部分手写 DTO，需要继续向 OpenAPI generated types 收敛。
6. Worker 已运行，但运维页面和告警维度还不够完整。

## 2. 本轮目标

本轮目标不是继续扩大架构，而是把已实现架构做实、做稳、做可观测：

1. 补齐线上验收报告，修正文档与线上事实不一致。
2. 修正 24 个月数据覆盖率语义，避免 `coverage_pct > 100%` 误导。
3. 将 Strategy Engine 接入 Shadow 读路径，开始记录与旧生产评分的差异，但不替换排序。
4. 将 Execution Model 接入一个低风险试点，只做 preview/parity，不替换事实源。
5. 继续减少前端手写 DTO，让更多 wrapper 使用 OpenAPI generated types。
6. 新增 Worker 观测面板或接口聚合，能看队列长度、失败任务、运行任务、心跳和产物。
7. 做一轮线上性能与稳定性对比，形成后续优化依据。

## 3. 硬边界

1. 不拆成大量微服务。
2. 不重写现有平台。
3. 不修改 `strategy_policy.py` 的生产准入语义。
4. 不替换低吸榜、优先榜、front_row_weighted、策略跟踪当前生产排序。
5. 不让 `research_only`、`watch_only`、`near_entry`、Shadow、Paper 绕过生产门控。
6. 不让实时行情 overlay 影响 `priority_score`、`production_score`、`buy_signal_state` 或 `elite_watch_score`。
7. 不把 DuckDB/Parquet 当生产交易事实源。
8. 不在 Web 请求中执行全市场扫描、24 个月回测、补数据、DuckDB 报告、模型训练或批量验证。
9. 不造假数据、假分数、假推荐。
10. 缺数据必须显式输出 `blocked`、`no_data`、`stale`、`partial` 或 `research_only`。
11. 未经过 Shadow/Paper 与 parity 验证，不允许开启生产替换。
12. 除非用户明确要求，不部署上线。

## 4. 阶段总览

| 阶段 | 名称 | 核心结果 |
|---|---|---|
| A0 | 复审基线冻结 | 记录当前线上与本地真实状态 |
| A1 | 线上验收补证 | B6 pending 变成可追溯验收报告 |
| A2 | 24M 覆盖率语义修正 | 数据质量指标不再超过 100% 或误导 |
| A3 | Strategy Engine Shadow 接入 | 生产页面可读 Shadow 输出，不改变排序 |
| A4 | Execution Model 低风险试点 | 一个业务入口展示 preview/parity，不替换事实源 |
| A5 | OpenAPI DTO 收敛 | 重点 API wrapper 减少手写类型 |
| A6 | Worker 观测面板 | 页面可看任务健康、失败、队列和产物 |
| A7 | 线上性能对比 | 形成架构上线后性能与稳定性报告 |

## 5. A0：复审基线冻结

### 目标

将本次复审结论沉淀为开发前基线，避免后续误判“已完成”和“可替换”。

### 重点文件

- `docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md`
- `docs/architecture/current-boundary-map.md`
- `docs/reports/platform-next-stage-baseline-2026-06-04.md`
- `docs/reports/platform-next-stage-b1-web-heavy-task-migration-2026-06-04.md`
- `docs/reports/platform-next-stage-b2-analytics-production-chain-2026-06-04.md`
- `docs/reports/platform-next-stage-b3-strategy-engine-integration-2026-06-04.md`
- `docs/reports/platform-next-stage-b4-execution-model-integration-2026-06-04.md`
- `docs/reports/platform-next-stage-b5-frontend-information-denoising-2026-06-04.md`
- `docs/reports/platform-next-stage-b6-independent-runtime-online-acceptance-2026-06-04.md`

### 任务

1. 运行 `git status --short`，记录当前未提交文件。
2. 复读上述基线与验收报告。
3. 明确当前完成状态：
   - `strategy_engine_adapter_enabled=false`
   - `execution_model_shared_rules_enabled=false`
   - `replacement_enabled=false`
   - 生产排序未替换
4. 输出复审基线报告：
   - `docs/reports/platform-architecture-review-baseline-2026-06-04.md`

### 验收

```bash
cd /Users/j/Documents/gupiao
git status --short
git diff --check
```

验收标准：

1. 基线报告存在。
2. 明确列出“已完成”“部分完成”“未替换”的边界。
3. 没有代码行为变更。

## 6. A1：线上验收补证

### 目标

修复 B6 报告仍显示 pending 的问题，用当前线上实测状态补齐证据。

### 重点文件

- `docs/reports/platform-next-stage-b6-independent-runtime-online-acceptance-2026-06-04.md`
- `docs/operations/deployment-topology-runbook.md`
- `docs/operations/worker-runbook.md`

### 建议新增报告

- `docs/reports/platform-architecture-online-review-2026-06-04.md`

### 检查项

1. 公网健康检查：
   - `http://43.143.243.97:18090/readyz`
2. 线上容器：
   - `tquant-app-mysql`
   - `tquant-runtime-worker-mysql`
   - `tquant-runtime-scheduler-mysql`
   - `tquant-analytics-worker-mysql`
   - `tquant-backtest-worker-mysql`
   - `tquant-mysql`
   - `tquant-redis`
3. analytics-worker 依赖：
   - `duckdb`
   - `pyarrow`
   - DB ping
4. analytics-worker 日志：
   - 确认 task types 注册成功。
5. backtest-worker 状态：
   - 如果没有 healthcheck，需要在报告中标注“容器运行但未配置 healthcheck”。

### 验收命令

```bash
curl -sS --max-time 10 http://43.143.243.97:18090/readyz

ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97 \
  "sudo docker ps --format '{{.Names}} {{.Status}}' | grep -E 'tquant-(app|runtime-worker|runtime-scheduler|backtest-worker|analytics-worker|mysql|redis)'"

ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97 \
  "sudo docker exec tquant-analytics-worker-mysql python -c 'import duckdb, pyarrow; from app.core.database import ping_database; print(duckdb.__version__); print(pyarrow.__version__); print(ping_database())'"

ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97 \
  "sudo docker logs --tail=80 tquant-analytics-worker-mysql 2>&1"
```

### 验收标准

1. Web readyz 正常。
2. runtime-worker、runtime-scheduler、analytics-worker、app、mysql、redis healthy 或运行正常。
3. analytics-worker 能导入 DuckDB/PyArrow。
4. 报告中不再保留未解释的 pending。
5. 如 backtest-worker 无 healthcheck，必须明确列为后续优化项。

## 7. A2：24M 覆盖率语义修正

### 问题

当前 analytics 质量检查可能出现：

```text
expected_days=355
actual_days=481
coverage_pct=135.493%
```

这会误导读者，以为覆盖率可以超过 100%。应修正字段语义或拆分指标。

### 重点文件

- `backend/app/services/analytics/quality.py`
- `backend/app/services/analytics/exporters.py`
- `backend/app/services/analytics/manifest.py`
- `backend/app/services/analytics/schemas.py`
- `backend/app/services/tasks/analytics_handlers.py`
- `backend/tests/test_analytics_layer.py`
- `backend/tests/test_analytics_worker.py`
- `backend/tests/test_analytics_worker_handlers.py`

### 目标字段

建议输出：

1. `required_trade_days`：24 个月窗口应覆盖交易日数。
2. `actual_trade_days`：本地实际有数据的交易日数。
3. `complete_trade_days`：满足完整样本口径的交易日数。
4. `missing_trade_days`：缺失交易日数。
5. `coverage_pct`：`min(100, actual / required * 100)`。
6. `over_coverage_trade_days`：超过最低要求的额外天数。
7. `coverage_status`：`ok / partial / fail`。
8. `actual_start` / `actual_end`。
9. `required_start` / `required_end`。

### 任务

1. 修改 quality 输出字段。
2. 保留旧字段兼容，但报告优先展示新字段。
3. Manifest 写入新字段。
4. DuckDB 报告展示新字段。
5. Worker 结果返回新字段。
6. 增加测试：
   - 覆盖率不得超过 100。
   - 额外覆盖天数单独展示。
   - 数据不足时仍 blocked。
   - Manifest 与 worker result 字段一致。

### 验收命令

```bash
cd /Users/j/Documents/gupiao
DATABASE_URL=sqlite:///backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_analytics_layer.py \
  backend/tests/test_analytics_worker.py \
  backend/tests/test_analytics_worker_handlers.py \
  -q

DATABASE_URL=sqlite:///backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/run_duckdb_strategy_report.py \
  --output-md /tmp/tquant_strategy_24m_duckdb_quality_check.md \
  --output-json /tmp/tquant_strategy_24m_duckdb_quality_check.json
```

### 验收标准

1. `coverage_pct <= 100`。
2. 报告中清楚解释 required、actual、complete、missing。
3. 数据不足时仍触发补数或 blocked，不允许静默通过。
4. 旧消费方不因字段调整报错。

## 8. A3：Strategy Engine Shadow 接入

### 目标

把 Strategy Engine 从“测试里的 adapter”推进到页面可读的 Shadow 输出，但不替换生产排序。

### 重点文件

- `backend/app/services/strategy_engine/`
- `backend/app/services/low_buy/priority_board.py`
- `backend/app/services/low_buy/priority_scoring.py`
- `backend/app/services/strategy_tracking.py`
- `backend/app/models/schema_defs/low_buy.py`
- `backend/app/models/schema_defs/strategy_tracking.py`
- `frontend/src/types/strategyLanes.ts`
- `frontend/src/types/strategyTracking.ts`
- `frontend/src/features/low-buy/`
- `frontend/src/features/strategy-tracking/`

### 输出字段

建议新增只读字段：

1. `strategy_engine_shadow`
2. `strategy_engine_decision`
3. `strategy_engine_warning_tags`
4. `strategy_engine_exclusion_reasons`
5. `strategy_engine_score_delta`
6. `strategy_engine_parity_status`

### 任务

1. 后端在优先榜和策略跟踪返回中增加 Shadow 字段。
2. `strategy_engine_adapter_enabled=false` 时不改变旧排序，只返回可选 Shadow 诊断。
3. 比较旧 `production_score/watch_score` 与 Strategy Engine 输出。
4. 记录差异：
   - 分数一致
   - 分数偏差
   - production/watch 决策不一致
   - near_entry 是否误入生产
5. 前端只展示“影子校验”标签，不作为买入依据。
6. 增加测试：
   - 生产排序不变。
   - near_entry 仍 watch-only。
   - research_only 不进生产。
   - front_row_only 不生成 production_score。
   - Shadow 字段缺失时页面不报错。

### 验收命令

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_strategy_engine_adapter_golden.py \
  backend/tests/test_strategy_engine_boundary.py \
  backend/tests/test_strategy_engine_production_gate_guards.py \
  backend/tests/test_low_buy_priority_board_strategy_variants.py \
  backend/tests/test_strategy_tracking.py \
  -q

cd frontend && npm run api:check && npm test -- --run \
  src/features/strategy-tracking/StrategyTrackingPage.test.tsx \
  src/features/trading-workspace/MonitorPage.test.tsx
```

### 验收标准

1. 旧排序不变。
2. 新字段只是 Shadow 诊断。
3. 页面提示清楚：“影子校验，不影响真实排序”。
4. 未通过前不得开启生产替换。

## 9. A4：Execution Model 低风险试点

### 目标

把 Execution Model 从测试预览推进到一个低风险页面或报告入口，继续保持 `replacement_enabled=false`。

### 推荐试点

优先选择其中一个：

1. 回测报告中的“执行模型一致性预览”。
2. 模拟盘复盘中的“执行规则校验”。
3. 策略跟踪详情中的“真实组合执行预览”。

不建议一开始改生产回测事实源。

### 重点文件

- `backend/app/services/execution_model/`
- `backend/app/services/decision_context/portfolio_executor.py`
- `backend/app/services/backtest/portfolio.py`
- `backend/app/services/paper/`
- `backend/app/models/schema_defs/backtest.py`
- `frontend/src/features/backtest/`
- `frontend/src/features/paper/`
- `frontend/src/features/strategy-tracking/`

### 任务

1. 选择一个入口接入 `build_backtest_execution_model_preview` 或 `build_paper_execution_model_preview`。
2. 返回：
   - `replacement_enabled=false`
   - `final_fact_source`
   - `parity`
   - `event_counts`
   - `max_5`
   - `max_10`
3. 前端展示为“执行模型预览”，不能展示为真实收益替换。
4. 增加测试：
   - preview 与原 facts 一致。
   - parity false 时给出差异原因。
   - feature flag 关闭时页面保持旧行为。

### 验收命令

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_execution_model_boundary.py \
  backend/tests/test_execution_model_backtest_golden.py \
  backend/tests/test_execution_model_paper_golden.py \
  backend/tests/test_backtest_engine_regression.py \
  -q

cd frontend && npm run api:check && npm test -- --run \
  src/features/backtest/BacktestDashboard.test.tsx \
  src/features/paper/PaperTradingPerformance.test.tsx
```

### 验收标准

1. `replacement_enabled=false`。
2. 事实源不变。
3. 页面只提示“预览/一致性校验”。
4. 试点结果可用于后续是否替换的判断。

## 10. A5：OpenAPI DTO 收敛

### 目标

减少前端手写 DTO，降低前后端字段漂移风险。

### 优先范围

1. `frontend/src/api/backtests.ts`
2. `frontend/src/api/backtestTypes.ts`
3. `frontend/src/api/runtimeTasks.ts`
4. `frontend/src/api/dataQuality.ts`
5. `frontend/src/api/client.ts` 中新增/改动接口

### 任务

1. 保留 ViewModel 类型，但 request/response DTO 尽量来自 `frontend/src/generated/api-types.ts`。
2. 对 backtest API 做分批迁移，不一次性大改所有类型。
3. 每迁移一个 wrapper，增加或更新测试。
4. `api:check` 必须通过。

### 验收命令

```bash
cd /Users/j/Documents/gupiao/frontend
npm run api:check
npm test -- --run src/api/backtests.test.ts src/api/dataQuality.test.ts src/api/base.test.ts
```

### 验收标准

1. 新增或改动 API 不再复制后端 DTO。
2. ViewModel 与 DTO 分层清楚。
3. TypeScript 能暴露契约漂移。

## 11. A6：Worker 观测面板

### 目标

让独立 Worker 能被页面直接观察，而不是只能看日志。

### 建议能力

1. 队列长度：
   - queued
   - running
   - failed
   - retrying
   - succeeded recent
2. 最长等待任务。
3. 最近失败任务。
4. Worker heartbeat：
   - runtime-worker
   - runtime-scheduler
   - analytics-worker
   - backtest-worker
5. 任务产物链接。
6. 任务类型分布。
7. 一键查看任务详情。

### 重点文件

- `backend/app/api/routes/runtime_tasks.py`
- `backend/app/services/tasks/queue.py`
- `backend/app/services/runtime_worker_health.py`
- `backend/app/models/schema_defs/phase4.py`
- `frontend/src/api/runtimeTasks.ts`
- `frontend/src/features/data-console/`
- `frontend/src/features/settings/` 或合适管理页

### API 建议

新增或增强：

1. `GET /api/runtime-tasks/summary`
2. `GET /api/runtime-tasks/workers`
3. `GET /api/runtime-tasks/failures`
4. `GET /api/runtime-tasks/artifacts`

如果不新增路由，也可以先在数据控制台聚合现有 list/events。

### 验收命令

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_runtime_task_contracts.py \
  backend/tests/test_runtime_worker_health.py \
  -q

cd frontend && npm run api:check && npm test -- --run \
  src/features/data-console/DataConsolePage.test.tsx
```

### 验收标准

1. 页面能看到任务健康。
2. 失败任务有原因。
3. 运行中任务有进度。
4. Worker 缺失时有明确提示。
5. 产物路径可追踪。

## 12. A7：线上性能与稳定性对比

### 目标

用实测数据确认架构升级后的效果，而不是只看功能完成。

### 指标

1. Web readyz 响应。
2. 低吸优先榜响应。
3. 策略跟踪响应。
4. 数据控制台响应。
5. Runtime task 提交耗时。
6. Analytics task claim 延迟。
7. DuckDB 报告任务耗时。
8. Worker 失败率。
9. 队列最长等待时间。
10. 线上容器健康状态。

### 建议报告

- `docs/reports/platform-architecture-performance-review-2026-06-04.md`
- `docs/reports/platform-architecture-performance-review-2026-06-04.json`  
  如 JSON 较大，应放到 `backend/data/analytics/reports/`。

### 验收命令

```bash
cd /Users/j/Documents/gupiao
curl -sS --max-time 10 http://43.143.243.97:18090/readyz

PYTHONPATH=backend:. backend/.venv/bin/python scripts/check_cloud_performance.py \
  --base-url http://43.143.243.97:18090 \
  --output docs/reports/gupiao-cloud-performance-architecture-review-2026-06-04.json
```

如果现有性能脚本路径不同，应使用项目现有脚本，并在报告中记录命令。

### 验收标准

1. 报告包含成功率和耗时。
2. 报告区分线上已部署状态和本地代码状态。
3. 如果某项失败，必须给出原因和下一步。
4. 不用单次快照宣称长期稳定，至少记录两轮或说明样本不足。

## 13. 总验收命令

完成 A0-A7 后，至少运行：

```bash
cd /Users/j/Documents/gupiao

PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_contract_first_openapi.py \
  backend/tests/test_analytics_layer.py \
  backend/tests/test_analytics_worker.py \
  backend/tests/test_analytics_worker_handlers.py \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_runtime_task_contracts.py \
  backend/tests/test_runtime_worker_health.py \
  backend/tests/test_strategy_engine_boundary.py \
  backend/tests/test_strategy_engine_adapter_golden.py \
  backend/tests/test_strategy_engine_production_gate_guards.py \
  backend/tests/test_execution_model_boundary.py \
  backend/tests/test_execution_model_backtest_golden.py \
  backend/tests/test_execution_model_paper_golden.py \
  -q

PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/export_openapi_schema.py

cd frontend
npm run api:check
npm test -- --run \
  src/features/data-console/DataConsolePage.test.tsx \
  src/features/monitor/MonitorPage.structure.test.ts \
  src/features/trading-workspace/MonitorPage.test.tsx \
  src/features/strategy-tracking/StrategyTrackingPage.test.tsx \
  src/features/backtest/BacktestDashboard.test.tsx

cd /Users/j/Documents/gupiao
DATABASE_URL=sqlite:///backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/run_duckdb_strategy_report.py \
  --output-md /tmp/tquant_strategy_24m_duckdb_review.md \
  --output-json /tmp/tquant_strategy_24m_duckdb_review.json

scripts/run_platform_component.sh runtime-worker --print-command
scripts/run_platform_component.sh scheduler --print-command
scripts/run_platform_component.sh analytics-worker --print-command
scripts/run_platform_component.sh backtest-worker --print-command

git diff --check
git status --short
```

## 14. 最终交付物

本轮完成后必须输出：

1. `docs/reports/platform-architecture-review-baseline-2026-06-04.md`
2. `docs/reports/platform-architecture-online-review-2026-06-04.md`
3. `docs/reports/platform-architecture-quality-semantics-2026-06-04.md`
4. `docs/reports/platform-architecture-strategy-engine-shadow-2026-06-04.md`
5. `docs/reports/platform-architecture-execution-model-preview-2026-06-04.md`
6. `docs/reports/platform-architecture-openapi-dto-convergence-2026-06-04.md`
7. `docs/reports/platform-architecture-worker-observability-2026-06-04.md`
8. `docs/reports/platform-architecture-performance-review-2026-06-04.md`

如涉及大型 JSON，放到：

- `backend/data/analytics/reports/`

不要把大型机器产物直接放入 `docs/reports/`。

## 15. 进入下一阶段的判断

可以进入下一阶段的条件：

1. 线上验收文档不再 pending。
2. 24M 覆盖率语义修正，覆盖率不再超过 100。
3. Strategy Engine Shadow 结果可见，且不改变生产排序。
4. Execution Model 试点可见，且不替换事实源。
5. OpenAPI generated types 覆盖新增/改动 API。
6. Worker 观测面板可查看队列和失败原因。
7. 线上性能报告有至少一轮完整数据。

不得进入生产替换的情况：

1. Strategy Engine 与旧评分存在未解释差异。
2. Execution Model parity 不通过。
3. Worker 队列失败率或等待时间不可控。
4. 数据质量存在 blocked/no_data/stale 且被忽略。
5. 页面把 Shadow/Preview 展示成真实生产依据。

## 16. 给执行 Agent 的提示词

```text
你在 /Users/j/Documents/gupiao 项目中继续开发。

请严格按照以下文档执行：
/Users/j/Documents/gupiao/docs/platform-architecture-review-followup-development-plan-2026-06-04.md

必须先阅读：
/Users/j/Documents/gupiao/AGENTS.md
/Users/j/Documents/gupiao/docs/engineering-conventions.md
/Users/j/Documents/gupiao/docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md
/Users/j/Documents/gupiao/docs/architecture/current-boundary-map.md

执行目标：
1. 补齐线上架构验收证据。
2. 修正 24M 数据质量 coverage_pct 语义，避免超过 100% 的误导。
3. Strategy Engine 只接入 Shadow 读路径，不替换生产排序。
4. Execution Model 只接入低风险 preview/parity，不替换事实源。
5. 前端 API wrapper 继续向 OpenAPI generated types 收敛。
6. 新增 Worker 观测能力。
7. 输出线上性能与稳定性对比报告。

硬边界：
1. 不拆微服务。
2. 不重写平台。
3. 不修改 strategy_policy.py 的生产准入语义。
4. 不替换生产排序。
5. 不让 research_only/watch_only/near_entry/Shadow/Paper 绕过生产门控。
6. 不把 DuckDB/Parquet 当生产交易事实源。
7. 不在 Web 请求里跑重任务。
8. 不部署，除非用户明确要求。

开始前：
1. 运行 git status --short。
2. 保护已有未提交改动。
3. 按 A0-A7 串行执行。
4. 每阶段完成后运行对应测试并输出报告。

最终回复必须包含：
1. 完成到哪个阶段。
2. 改了哪些文件。
3. 新增了哪些报告。
4. 跑了哪些测试，结果如何。
5. 线上验收是否补齐。
6. 24M coverage 语义是否修正。
7. Strategy Engine 是否仍只 Shadow。
8. Execution Model 是否仍只 Preview。
9. Worker 观测是否完成。
10. 是否部署：未部署，除非用户明确要求。
```
