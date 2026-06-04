# 平台架构优化下一阶段开发计划(2026-06-04)

> 状态:草案(评审用)。本文是基于 A0–A7 第一轮整改 + Phase 1 模块化基线已落档后的**下一阶段最该做的事**;**不是新需求**,而是把已规划但未深化的方向按当下风险与证据排出优先级。
>
> **本文严格遵守 11 条硬边界**(用户当轮列出):不拆微服务、不推倒重写、不改 `strategy_policy.py` 生产准入语义、不替换 low-buy/priority board/front-row weighted/strategy tracking 生产排序、research_only/watch_only/near_entry/Shadow/Paper 不绕生产门、DuckDB/Parquet 不作生产事实源、Web 不执行重任务、OpenAPI 是契约事实源、不新增框架级依赖、不部署(除非明确要求)、不清理或 revert 无关脏改动。
>
> 关联文档:
> - `docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md`(7 Phase 总图)
> - `docs/platform-architecture-review-followup-development-plan-2026-06-04.md`(A0–A7 第一轮跟进)
> - `docs/architecture/current-boundary-map.md`(边界图)
> - `docs/reports/platform-architecture-performance-review-2026-06-04.md`(A7 性能告警与基线)
> - `docs/reports/platform-architecture-worker-observability-2026-06-04.md`(A6 观测落地证据)

---

## 1. 当前架构优化状态(基于证据,非估计)

### 1.1 已完成(可直接引用)

| 项 | 证据 |
|---|---|
| Phase 1 边界图 + 契约链 | `current-boundary-map.md`(102 行);`docs/contracts/openapi.json` + `openapi.hash` 同步 |
| A0 基线冻结 | `platform-architecture-review-baseline-2026-06-04.md` |
| A1 线上验收补证 | `platform-architecture-online-review-2026-06-04.md` |
| A2 24M coverage 语义修正(capped <=100 + required/actual/extra) | `platform-architecture-quality-semantics-2026-06-04.md`;`quality.py:224-230 capped_coverage_pct` |
| A3 Strategy Engine Shadow 接入(`production_sort_replaced=false / shadow_only=true`) | `platform-architecture-strategy-engine-shadow-2026-06-04.md`;`strategy_engine/shadow.py:29-41` |
| A4 Execution Model Preview(`blocked_reason=no_daily_return_path`) | `platform-architecture-execution-model-preview-2026-06-04.md`;`backtest/persistence.py:263,273,282,294` |
| A5 OpenAPI DTO 收敛(`dataQuality.ts / runtimeTasks.ts / backtestBaseTypes.ts`) | `platform-architecture-openapi-dto-convergence-2026-06-04.md`;`api-types.ts +389 行` |
| A6 Worker 观测能力(4 组件心跳) | `platform-architecture-worker-observability-2026-06-04.md`;`runtime_worker_health.py:23 DEFAULT_OBSERVED_COMPONENTS` |
| A7 第二次性能基线(部分通过) | `platform-architecture-performance-review-2026-06-04.md` |

### 1.2 未完成 / 真实风险(每条带证据)

| ID | 项 | 证据 |
|---|---|---|
| **R1** | A6 已实现但**未部署** | 性能报告自承 "A6 was not deployed in this follow-up run";online availability 表中 queue wait / worker failure rate 全部 "not available" |
| **R2** | A7 警告持续上升 | 两次 A7 间 BFF timeout 12→47、market-read unresolved misses 28→183、fallback 7→84;19:51 测量 `monitor_bff` p95 852ms / `priority_board` p95 1101ms 超 500ms 阈值 |
| **R3** | Execution Model 当前只是"阻断态" | `no_daily_return_path` 拒绝输出但**未补**真实 1/3/5/10 日 forward return + parity |
| **R4** | Strategy Engine Shadow 无长期 parity | shadow 只单点输出 delta,无累计统计、无差异解释、无回归报告 |
| **R5** | Analytics 链路治理欠缺 | manifest 生命周期、`blocked/no_data/stale/partial` 状态传播、DuckDB 报告版本追踪、Parquet 增量/过期均无统一治理 |
| **R6** | RuntimeTask 任务注册表治理欠缺 | 每类任务的 owner/worker/重试/产物/幂等键散落各处,无单一注册表;新增任务靠 grep |
| **R7** | dirty worktree 55 文件未提交 | 全部归属本轮架构整改;按规范应按 Task 拆 commit |

### 1.3 状态结论

- **没有 P0 阻断项**;平台正常运转,生产排序、策略口径、生产门均未被本轮改动碰过。
- **存在 P1 风险**:观测建好了未部署(R1)+ 警告增长无人盯(R2)= 真实可恶化的盲区。
- **存在 P2 治理缺口**:R3–R6 是"工程化做到一半"——能力具备,治理未闭环。
- 下一阶段的核心命题是 **"把已建好的能力部署生效 + 治理闭环"**,而不是再加新能力。

---

## 2. 下一阶段最该做的 5 个工作包(按优先级)

### 工作包总览

| 优先级 | ID | 工作包 | 对应候选方向 | 工作量 | 并行 |
|---|---|---|---|---|---|
| **P0** | **N1** | A6 观测部署 + B 性能根因联动 + G 部署验收 | A / B / G | 2-3 人日 | 与 N2 并行 |
| **P0** | **N2** | RuntimeTask 任务注册表治理 | A | 2-3 人日 | 与 N1 并行 |
| **P1** | **N3** | Execution Model 真实逐日 forward path + golden parity | C | 4-5 人日 | 必须等 N2 |
| **P1** | **N4** | Analytics manifest 生命周期 + 报告版本追踪 | E | 3-4 人日 | 与 N3 并行 |
| **P2** | **N5** | Strategy Engine 长期 shadow parity + 前端 Shadow/Preview 标签降噪 | D + F | 3-4 人日 | 必须等 N3/N4 |

---

## 工作包 N1｜A6 观测部署 + 性能根因联动 + 部署验收

### 目标
把 A6 的观测能力(`/api/runtime-tasks/summary|workers|failures|artifacts` + worker heartbeat)**真正部署到线上**;同时启动 A7 警告的根因排查,把"BFF source timeout、market-read fallback/unresolved miss"变成可解释、可监控的指标,而不是告警计数。

### 为什么现在做
A7 报告自承"A6 未部署导致 queue wait / failure rate 在线不可见";告警数在两次 A7 测量间显著上升却**没有人盯**。**这是当前可恶化的最大盲区**。已建的能力不部署 = 等于没建。

### 涉及文件 / 模块
- 后端:`backend/app/api/routes/runtime_tasks.py`、`backend/app/services/runtime_worker_health.py`、`backend/app/services/tasks/queue.py`
- 前端:`frontend/src/features/data-console/*`(展示 4 类 worker 心跳与队列)
- 部署:`docker-compose.mysql.yml`、`scripts/run_platform_component.sh`、deploy delta-package 脚本
- 性能根因:`backend/app/services/bff/*`、`market/local_quote_cache.py`、Go `market-read-service`(只读核验,不改 Go 代码)

### 不允许做什么
- ❌ 部署任何生产排序/策略口径变更
- ❌ 触发 RuntimeTask 写入操作(只读观测)
- ❌ 修改 Go 服务(本工作包只看 metrics 和日志做诊断)
- ❌ 引入新观测框架(Prometheus exporter 已有,Grafana 已有,沿用既有)
- ❌ 用部署绕过 `participates_in_priority_board` 单一生产门

### 验收标准
1. 线上 `GET /api/runtime-tasks/summary` 返回非 0 数据(队列/失败/等待时长齐全)
2. 线上 `GET /api/runtime-tasks/workers` 4 类组件心跳齐全(`runtime-worker / runtime-scheduler / analytics-worker / backtest-worker`)
3. 数据控制台页面展示 4 类 worker 心跳 + 失败任务 + 队列等待最长 + 产物路径
4. 性能基线报告新增:**BFF timeout / market-read fallback / unresolved miss 三项的根因分类**(至少识别出哪几个 Python source endpoint 慢、哪些 symbol 反复 unresolved)
5. 设立**回归阈值**:`monitor_bff p95 ≤ 500ms`、`priority_board p95 ≤ 500ms`、`market_read.unresolved < N`(N 由本轮基线确定)
6. 落档 `docs/reports/platform-architecture-observability-deployment-2026-06-XX.md`

### 测试命令
```bash
# 部署后线上验证(只读 GET)
curl -fsS -b "session=$TOKEN" "$BASE/api/runtime-tasks/summary" | jq .
curl -fsS -b "session=$TOKEN" "$BASE/api/runtime-tasks/workers" | jq '.workers[]|{component,worker_id,age_seconds,status}'
curl -fsS -H "X-Admin-Token: $ADMIN_API_TOKEN" "$BASE/metrics" | rg "bff_partial_timeout|market_read_unresolved|market_read_fallback|local_quote_cache"

# 本地回归
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_runtime_task_contracts.py backend/tests/test_runtime_worker_health.py -q
cd frontend && npm test -- --run src/features/data-console/DataConsolePage.test.tsx
```

### 风险与回滚
- **风险**:部署 A6 端点引入新读路径占用,可能短期推高 Web QPS。
- **回滚**:观测 API 增 feature flag `RUNTIME_TASK_OBSERVABILITY_ENABLED`,关掉即回退;data-console 页面入口可独立隐藏。
- **不破坏边界证明**:所有改动仅在 GET 路径(本轮上一份复查已断言 summary/workers 不写 DB);Go 服务不动。

---

## 工作包 N2｜RuntimeTask 任务注册表治理

### 目标
把所有 RuntimeTask 任务类型集中到**单一注册表**,声明 `owner / worker(归属)/ retry_policy / artifact_path / idempotency_key_pattern / expected_runtime_ms`,并由该注册表驱动 web 入口审计(确保 Web 请求线程不直接执行重任务)。

### 为什么现在做
- 跟进计划与 boundary-map 已列出 ~14 种 task type 散落各处;新增任务靠 grep,审计成本高。
- N1 部署后,前端要展示"task type → owner → 健康度",没有注册表就只能展示 task_type 字符串。
- **Web 重任务入口审计**是这次架构整改的核心承诺之一(boundary-map §"Web Process must not"),现在缺一份"治理工件"做长期守护。

### 涉及文件 / 模块
- 后端:`backend/app/services/tasks/registry.py`(扩)、`runtime_worker.py`、`analytics_handlers.py`、`scripts/analytics_worker.py`、`backtest_worker.py`、`runtime_scheduler.py`
- 守卫:新增 `backend/tests/test_runtime_task_registry_governance.py`、`test_web_route_no_heavy_compute.py`
- 文档:`docs/architecture/runtime-task-registry.md`(新建)

### 不允许做什么
- ❌ 改 task 实际执行逻辑(只做声明 + 守卫)
- ❌ 把任何 task 从 worker 拉回 Web 进程
- ❌ 改变 `RuntimeTaskQueue` 状态机
- ❌ 影响 production_score / priority_board / strategy_policy
- ❌ 引入新依赖(注册表用 dataclass / TypedDict 即可)

### 验收标准
1. `backend/app/services/tasks/registry.py` 暴露 `RUNTIME_TASK_REGISTRY: dict[str, TaskDefinition]`,字段:`owner_role`(quant/data/devops)、`worker`(runtime|analytics|backtest|scheduler)、`retry_policy`、`max_attempts`、`artifact_kind`、`idempotency_required: bool`、`expected_runtime_p95_ms`
2. 守卫测试:**`runtime_worker._execute_task` 与各 worker 注册的 task_type 必须全部在注册表里**;反之亦然(没有"幽灵任务")
3. **Web 路由守卫测试**:遍历 `app/api/routes/*.py` 抽出所有处理函数,确保它们**不直接调用** registry 中 `worker != "web"` 的处理器
4. `docs/architecture/runtime-task-registry.md` 落地,含表格 + owner 联系人 + 升级建议
5. `boundary-map` 同步更新引用本注册表

### 测试命令
```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_runtime_task_registry_governance.py \
  backend/tests/test_web_route_no_heavy_compute.py \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_runtime_task_contracts.py -q

# 注册表可读性
PYTHONPATH=backend:. backend/.venv/bin/python -c "from app.services.tasks.registry import RUNTIME_TASK_REGISTRY; import json; print(json.dumps(list(RUNTIME_TASK_REGISTRY), indent=2, ensure_ascii=False))"
```

### 风险与回滚
- **风险**:守卫测试发现历史漏接的 task type → 暂时进 allowlist 等下一波修。
- **回滚**:注册表纯声明 + 守卫测试,回退 = 删测试文件,无业务影响。

---

## 工作包 N3｜Execution Model 真实逐日 forward path + golden parity

### 目标
把 Execution Model 从"阻断态占位"升级到"真 parity 预览":补 1/3/5/10 日真实 forward return path(从 daily_bar OHLC 派生);建立 `signal/order/fill/position/exit → portfolio_backtest_metrics` 的 **golden parity**;**继续保持 `replacement_enabled=false`,不替换 backtest/paper 事实源**。

### 为什么现在做
- A4 报告自承"目前是 blocked_reason=no_daily_return_path",这是占位不是能力。
- 没有真实 forward path,前端 Execution Model 面板永远是阻断态,信息层级降噪(N5)也无法落地("Preview" 标签贴什么数据上?)。
- N2 注册表治理完成后,backtest_worker 的产物 schema 才能稳定,N3 才有可靠基底。

### 涉及文件 / 模块
- 后端:`backend/app/services/backtest/persistence.py`、`backend/app/services/backtest_job_service.py`、`backend/app/services/backtest/engine_helpers.py`(已有 `next_trade_dates`)
- 真值参照:`backend/scripts/low_buy_market_backtest_reporting.py: portfolio_backtest_metrics`(唯一组合事实源)
- 守卫:新增 `backend/tests/test_execution_model_forward_path_parity.py`、扩 `test_execution_model_backtest_golden.py / paper_golden.py`

### 不允许做什么
- ❌ `replacement_enabled` 改为 true(永久 false)
- ❌ Execution Model 输出影响生产排序或 production_score
- ❌ 用模型/外推/插值生成 forward return(只能用真实日线 OHLC)
- ❌ 并行实现 `portfolio_backtest_metrics`(违反单一事实源边界)
- ❌ 当 daily_bar 缺失时静默 fallback——必须显式 `blocked_reason / no_data / preview_unavailable`(沿用 A4 阻断态语义)

### 验收标准
1. `BacktestRun.persisted_signal` 含真实 `return_1d / return_2d / return_3d / return_4d / return_5d / max_gain_5d / max_drawdown_5d`(由 `next_trade_dates` + 真实日线计算)
2. **Golden parity 测试**:同一组 `signal/order/fill/position/exit`,Execution Model 输出与 `portfolio_backtest_metrics(max_5/max_10)` 在 max_5/max_10 真实组合收益 **1e-9 一致**
3. 缺数据(停牌/退市/复权口径冲突)**保留** `blocked_reason=no_daily_return_path | partial_path | suspended` 等多分类
4. Frontend `BacktestDashboard.panels.tsx` 显示 forward path + 显式标"Preview · 非事实源"
5. `replacement_enabled` 在代码中**写死 False**,有守卫测试断言
6. 落档 `docs/reports/platform-architecture-execution-model-parity-2026-06-XX.md`

### 测试命令
```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_execution_model_forward_path_parity.py \
  backend/tests/test_execution_model_backtest_golden.py \
  backend/tests/test_execution_model_paper_golden.py \
  backend/tests/test_execution_model_boundary.py \
  backend/tests/test_backtest_engine_regression.py -q

cd frontend && npm test -- --run src/features/backtest/BacktestDashboard.test.tsx
```

### 风险与回滚
- **风险**:历史 BacktestRun 缺日线 → parity 测试失败;处置 = 显式标 `blocked_reason=legacy_no_path`,不阻断新数据。
- **回滚**:回滚到 A4 阻断态行为(forward path 不展示);schema 字段可保留,前端隐藏即可。

---

## 工作包 N4｜Analytics manifest 生命周期 + 报告版本追踪

### 目标
把 24M Analytics 链路(Parquet export → manifest → quality → DuckDB report)的"生命周期"治理闭环:**manifest 版本追踪 + 增量过期 + 状态传播(blocked/no_data/stale/partial)+ 报告产物索引**。

### 为什么现在做
- A2 修了 coverage 语义,但 manifest 本身的版本/过期/失效尚无统一治理。
- DuckDB 报告任务耗时未观测,**长任务超时无人知**。
- 后续 Strategy Engine 长期 parity(N5)要读历史报告做对照,没有版本索引就读不到。
- 与 N1 观测部署天然协同(报告产物路径要进 data-console 展示)。

### 涉及文件 / 模块
- 后端:`backend/app/services/analytics/exporters.py / quality.py / report_queries.py / manifest.py`
- 报告产物:`backend/data/analytics/reports/`、`backend/data/analytics/parquet/`
- 任务编排:`backend/scripts/analytics_worker.py`、`backend/app/services/tasks/analytics_handlers.py`
- 守卫:`backend/tests/test_analytics_manifest_lifecycle.py`、`test_analytics_report_versioning.py`

### 不允许做什么
- ❌ 把 DuckDB/Parquet 提升为生产事实源(永远只是分析/报告层)
- ❌ Web 进程直接生成 manifest 或 Parquet
- ❌ 删除既有 manifest(只做"标记过期",保留可追溯)
- ❌ 修改 24M 报告口径(每日信号等权复利收益 + 真实组合 max5/max10 不变)
- ❌ 改 `coverage_pct` capped 语义(A2 已稳定)

### 验收标准
1. 每个 manifest 含:`manifest_id / dataset_version / generated_at / valid_until / superseded_by / status(active|stale|partial|blocked|no_data)`
2. Analytics worker 在生成新 manifest 时**自动标记上一份为 superseded**(不删,只标记)
3. DuckDB 报告产物索引:`backend/data/analytics/reports/index.json`(由 worker 自动维护,列出最近 N 份报告 + 对应 manifest_id + 生成耗时)
4. 状态传播:`quality.py` 的 `blocked/no_data/stale/partial` 必须沿调用链一路传到前端 `data-console`(不能 silently downgrade)
5. 数据控制台展示:最新报告 / 历史 N 份 / 每份耗时 / 对应 manifest
6. 落档 `docs/reports/platform-architecture-analytics-lifecycle-2026-06-XX.md`

### 测试命令
```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_analytics_manifest_lifecycle.py \
  backend/tests/test_analytics_report_versioning.py \
  backend/tests/test_analytics_layer.py \
  backend/tests/test_analytics_worker.py \
  backend/tests/test_analytics_worker_handlers.py -q

# 报告再生成 + 索引校验
DATABASE_URL=sqlite:///backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/run_duckdb_strategy_report.py \
  --output-md /tmp/analytics_report.md --output-json /tmp/analytics_report.json
rg -n "manifest_id|valid_until|superseded_by" /tmp/analytics_report.json
```

### 风险与回滚
- **风险**:旧 manifest 缺生命周期字段 → 标 legacy,不阻断现有读路径。
- **回滚**:字段是 schema 增量;不依赖新字段的旧消费方不受影响。

---

## 工作包 N5｜Strategy Engine 长期 shadow parity + 前端 Shadow/Preview 标签降噪

### 目标
两件事合在一起做(强相关,共享前端 schema):
1. **Strategy Engine 长期 shadow parity**:把 Shadow 输出从"单点 delta"升级为"累计 parity 统计"(总差异率/分布/缺失率)+ 差异解释报告;
2. **前端信息层级降噪**:监控页/纸面/策略追踪/数据控制台/回测中心的 `Shadow / Preview / Research / Paper / research_only / watch_only / near_entry` 标签明确化,**杜绝用户误读为真实买入依据**。

### 为什么现在做
- N3/N4 落地后,前端面板有"Shadow/Preview"实际数据可展示,降噪才有抓手。
- Shadow 单点输出**无法做长期决策**——必须有累计统计才能形成"是否未来可考虑接入"的证据。
- A3 已建 shadow,**A7 测试没回归到 shadow parity 漂移**,这是潜在盲区。

### 涉及文件 / 模块
- 后端:`backend/app/services/strategy_engine/shadow.py / low_buy_adapter.py`、新增 `strategy_engine/parity_tracker.py`
- 前端:`frontend/src/features/{data-console,monitor,strategy-tracking,paper,backtest}/*`、`pageResponsibilities.ts`、`workspace-shared/workspaceViewModels.ts`
- 守卫:`backend/tests/test_strategy_engine_parity_tracker.py`、扩 `test_strategy_engine_production_gate_guards.py`

### 不允许做什么
- ❌ Strategy Engine 进入 priority_board 排序或 production_score
- ❌ 修改 `participates_in_priority_board` 语义
- ❌ 把 `Shadow / Preview / Research` 标签转成"建议买入/卖出/必涨/低吸"(沿用既有文案守卫)
- ❌ 让 `near_entry` 进入生产收益排行
- ❌ 把 Paper 真实成交结果暴露成生产事实源
- ❌ 引入新前端框架(沿用 React/AntD/Vite,沿用既有 Zustand store + state-separation guard)

### 验收标准
1. `strategy_engine/parity_tracker.py`:累计统计 Strategy Engine vs 现生产 priority_score 的差异分布、缺失率、零分率、按策略分组
2. 落档 `docs/reports/platform-architecture-strategy-engine-parity-2026-06-XX.md`,含**至少 30 个交易日**的累计对照
3. 前端每个面板的 Shadow/Preview/Research/Paper 标签**有色块 + tooltip + 链接到说明文档**;**不混用**(Shadow ≠ Preview ≠ Paper ≠ Research)
4. 守卫测试:文案不出现"建议买入/卖出/低吸/必涨/突破即买";`page-responsibilities.ts` 守卫不回退
5. **核心硬断言**:Strategy Engine parity 报告**显式标注"非生产采纳依据,仅长期对照"**

### 测试命令
```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_strategy_engine_parity_tracker.py \
  backend/tests/test_strategy_engine_boundary.py \
  backend/tests/test_strategy_engine_production_gate_guards.py \
  backend/tests/test_strategy_engine_adapter_golden.py -q

cd frontend && npm run lint && npm test -- --run \
  src/features/trading-workspace/MonitorPage.test.tsx \
  src/features/strategy-tracking/StrategyTrackingPage.test.tsx \
  src/features/backtest/BacktestDashboard.test.tsx \
  src/features/data-console/DataConsolePage.test.tsx
```

### 风险与回滚
- **风险**:parity 报告显示 Strategy Engine 差异极大 → **正是它该被发现的事**,报告写明,**不替换生产**。
- **回滚**:前端标签纯展示层,关闭 feature flag 即回到现状;parity tracker 独立任务,关掉不影响 priority_board。

---

## 3. 并行 / 串行图

```
                P0 同步启动
    ┌─────────────────────────────────────────┐
    │                                         │
[N1 A6 观测部署 + B 性能根因 + G]      [N2 RuntimeTask 注册表治理]
    │                                         │
    ▼                                         ▼
    └────────────── 并行,互不依赖 ─────────────┘
                       │
        N2 完成是 N3 前置(产物 schema 稳定)
                       │
            ┌──────────┴───────────┐
            ▼                      ▼
   [N3 Execution Model    [N4 Analytics manifest
    forward path + parity]  生命周期 + 版本追踪]
            │                      │
            └──────────┬───────────┘
                       │
            N3 + N4 完成才进 N5
                       ▼
            [N5 Strategy Engine parity
             + 前端 Shadow/Preview 降噪]
```

**串行硬约束(必须遵守的顺序)**:
- N3 必须等 N2 完成:Execution Model parity 需要 backtest_worker 产物 schema 稳定
- N5 必须等 N3 + N4:前端降噪需要 forward path 真数据 + manifest 版本追踪
- N1 / N2 可同时启动
- N3 / N4 可同时启动(N4 不依赖 N3,反之亦然)

---

## 4. 明确不该现在做(本期硬否)

| # | 不做的事 | 理由 |
|---|---|---|
| 1 | 替换 low-buy / priority board / front-row weighted / strategy tracking 生产排序 | 硬边界 4;`strategy_policy.py` 单一事实源不动 |
| 2 | 修改 `strategy_policy.py` 生产准入语义 | 硬边界 3;研究/Shadow/Preview 任何路径都不绕生产门 |
| 3 | Execution Model `replacement_enabled=true` | 硬边界(Execution Model 仅 Preview);永久 false |
| 4 | Strategy Engine 进入生产打分 | 硬边界 5;Shadow 永远不影响 priority_board |
| 5 | DuckDB / Parquet 提升为生产交易事实源 | 硬边界 6;分析/报告层永久独立 |
| 6 | Web 进程执行重任务 | 硬边界 7;由 N2 注册表 + 守卫测试强制 |
| 7 | 拆微服务 | 硬边界 1 |
| 8 | 推倒重写 | 硬边界 2 |
| 9 | 新增框架级依赖(Celery / Kafka / K8s / Cython / JAX / 全栈 async) | 硬边界 9 |
| 10 | 部署(除非用户明确要求) | 硬边界 10;N1 的"部署"指明确请求后再做 |
| 11 | 清理或 revert 无关脏改动 | 硬边界 11;dirty worktree 55 文件保留 |
| 12 | 把 research_only / watch_only / near_entry / Paper 转生产 | 硬边界 5 |
| 13 | 把"做 T 推荐 / 智能买卖点 / 智能止损"接到 Strategy Engine | 越界为指令工具 |
| 14 | 再加新选股策略 | 24M 证据门未达不可加 |
| 15 | 写新规划文档(本文之外) | 现有方案已饱和,该执行 |

---

## 5. 整体执行节奏建议

- **第 1 周**:N1 + N2 同步启动(P0 并行,2-3 人日各 1)
- **第 2 周**:N1 收尾 + 部署窗口(用户确认后);N2 注册表合入 + 守卫测试上线
- **第 3 周**:N3 + N4 同步启动(P1 并行,4-5 + 3-4 人日)
- **第 4 周**:N3 / N4 收尾 + parity / lifecycle 报告落档
- **第 5 周**:N5(3-4 人日)+ 最终回归

**回归命令(每个工作包完成必跑)**:
```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
cd frontend && npm run api:check && npm run lint && npm test -- --run && npm run build && npm run analyze
```

**门禁回归**(任一红即不进下一工作包):
- `test_strategy_engine_boundary.py / test_strategy_engine_production_gate_guards.py`(Shadow 不进生产)
- `test_execution_model_boundary.py`(Preview 不替换事实源)
- `test_low_buy_production_scoring.py / test_low_buy_priority_board_strategy_variants.py`(生产排序未漂移)
- `test_contract_first_openapi.py`(契约未漂移)
- `check-state-separation.mjs / check-refactor-guard.mjs`(前端架构守卫)

---

## 6. 输出与提交节奏

- 工作包按文档规范 §6.1 **一项一 commit**(本期不在主体仓做修改;dirty 55 文件不在本文范围内)
- 每个工作包完成后产出对应 `docs/reports/platform-architecture-<topic>-2026-06-XX.md`,沿用 A0–A7 既有命名
- 守卫测试与新增 schema 字段必须随主代码同 commit;**严禁** "先合代码后补测试"
- 不部署:N1 的部署动作单独在用户明确要求时执行;本文不预先触发

---

## 7. 一句话结论

**第一波架构整改(Phase 1 + A0–A7)已落档完整;下一阶段的核心命题是"把已建好的能力部署生效 + 把工程化做到一半的能力治理闭环"**——不是再加新能力。按上面 5 个工作包(N1–N5),P0 两件并行启动,P1 两件并行接上,P2 一件收尾,5 周内可把架构整改第二轮做完且不动任何硬边界。
