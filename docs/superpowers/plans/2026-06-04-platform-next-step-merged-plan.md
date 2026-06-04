# 平台下一阶段开发计划 · 融合版(2026-06-04)

> **For agentic workers**:REQUIRED SUB-SKILL — superpowers:executing-plans。Steps 用 `- [ ]` 跟踪。
>
> **本文是融合方案,不是新需求**。融合源:
> - `docs/platform-architecture-next-step-plan-2026-06-04.md`(架构整改下一阶段,N1–N5)
> - `docs/superpowers/plans/2026-06-04-frontend-loading-stability-final.md`(前端加载稳定性最终方案,L1–L4)
>
> **融合后视角**:同时覆盖**用户体感(前端慢+加载失败)** 与 **架构治理(观测部署 + 注册表 + parity)** 两条主线;两边互不冲突,合并后按"用户立即可感知"和"架构长线治理"的 ROI 统一排序。
>
> **关联文档**:
> - `docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md`(7 Phase 总图)
> - `docs/platform-architecture-review-followup-development-plan-2026-06-04.md`(A0–A7 第一轮跟进)
> - `docs/architecture/current-boundary-map.md`(边界图)
> - `docs/reports/platform-architecture-performance-review-2026-06-04.md`(A7 性能告警)
> - `docs/reports/platform-architecture-worker-observability-2026-06-04.md`(A6 观测落地证据)
> - `docs/superpowers/plans/2026-06-03-monitor-priority-board-latency-final.md`(L1/L2/L4 起源)

---

## 1. 当前状态:用户体感 vs 架构治理(两条主线)

### 1.1 用户体感主线(前端 5 个实测真因)

| # | 问题 | 实测证据 | 严重度 |
|---|---|---|---|
| **B1** | TanStack Query 全局 `retry: false` → 任何抖动失败一次直接红屏 | `frontend/src/state/queryClient.ts:10,17,35` 三处全是 `retry: false`(queries / mutations / createAppQueryClient) | 🔴 这就是"容易加载失败"的核心根因 |
| **B2** | 监控页 13 个独立 useQuery 并发(任一失败即模块空) | `frontend/src/features/trading-workspace/useMonitorData.ts:41-92` `MONITOR_SERVER_KEYS` 列 13 key | 🔴 慢 + 易失败叠加 |
| **B3** | 后端 BFF 合包**已存在**,前端 **0 引用** | `backend/app/api/routes/bff.py:89,121 def monitor_workspace_bff` 已实现合包 + cache + remote fallback;前端 `rg "bff/v1/workspace/monitor"` 命中 0 | 🔴 现成能力没接上 |
| **B4** | 首屏关键路径 chunks 偏重 | dist 实测:`antd-core 329K + antd-check-controls 316K + antd-display 186K` 三块 ~800K 进入首屏 | 🟡 加载慢次因 |
| **B5** | `api/base.ts` 有 `retryRequest` 但被顶层 `retry: false` 绕过 | `api/base.ts:50,245-258` 有重试封装,query 层 `retry: false` 让它形同虚设 | 🔴 与 B1 同源 |

### 1.2 架构治理主线(后端 7 个真实风险)

| ID | 项 | 证据 |
|---|---|---|
| **R1** | A6 已实现但**未部署** | 性能报告自承 "A6 was not deployed in this follow-up run";online availability 表中 queue wait / worker failure rate 全部 "not available" |
| **R2** | A7 警告持续上升 | 两次 A7 间 BFF timeout 12→47、market-read unresolved misses 28→183、fallback 7→84;19:51 测量 `monitor_bff` p95 852ms / `priority_board` p95 1101ms 超 500ms 阈值 |
| **R3** | Execution Model 当前是"阻断态" | `no_daily_return_path` 拒绝输出但**未补**真实 1/3/5/10 日 forward return + parity |
| **R4** | Strategy Engine Shadow 无长期 parity | shadow 只单点输出 delta,无累计统计、无差异解释、无回归报告 |
| **R5** | Analytics 链路治理欠缺 | manifest 生命周期、`blocked/no_data/stale/partial` 状态传播、DuckDB 报告版本追踪、Parquet 增量/过期均无统一治理 |
| **R6** | RuntimeTask 任务注册表治理欠缺 | 每类任务的 owner/worker/重试/产物/幂等键散落各处;新增任务靠 grep |
| **R7** | dirty worktree 55 文件未提交 | 全部归属本轮架构整改;按规范应按 Task 拆 commit |

### 1.3 已完成基线(可直接引用,不在本计划重做)

Phase 1 边界图 + 契约链 + A0–A7 第一轮整改全部已落档,**无 P0 阻断**:
- A0 基线冻结、A1 线上验收补证、A2 24M coverage 语义修正、A3 Strategy Engine Shadow 接入、A4 Execution Model Preview(阻断态)、A5 OpenAPI DTO 收敛、A6 Worker 观测能力(本地)、A7 第二次性能基线
- 47+42 个定向测试全绿(上一轮复查证据)

### 1.4 核心命题(融合后的)

> **下一阶段同时做两件事**:
> ① **立即修用户体感**(L1 retry + L2 BFF + L4 错误兜底 + N1 观测部署)——3-5 人日可见极大改善;
> ② **架构长线治理闭环**(N2 注册表 + N3 ExecModel parity + N4 Analytics 生命周期 + L3 包预算 + N5 Strategy Engine parity)——4-5 周完成。
>
> 不再加新能力,不动业务边界,不部署除非明确要求。

---

## 2. 统一硬边界(15 条,实施期始终成立)

来自两份文档合并去重:

1. **栈冻结**:不换 React / AntD / Vite / ECharts;零新增 npm/pypi 框架级依赖。
2. **不拆微服务,不推倒重写**。
3. **生产口径不动**:`strategy_policy.py` 生产准入语义、`participates_in_priority_board`、`production_score`、priority_board 排序不受本计划影响。
4. **不替换生产排序**:low-buy / priority board / front-row weighted / strategy tracking 全部沿用现状。
5. **research_only / watch_only / near_entry / Shadow / Paper 不绕生产门**。
6. **DuckDB / Parquet 仅作分析/报告层**,永不作为生产交易事实源。
7. **Web 进程不执行重任务**(由 N2 注册表 + 守卫测试强制)。
8. **OpenAPI 是前后端契约事实源**;前端 wrapper 类型从 `generated/api-types.ts` 取。
9. **服务端态唯一在 TanStack Query**;不复制进 Zustand store。
10. **零 useState / useReducer**(沿用 `check-state-separation.mjs / check-refactor-guard.mjs`)。
11. **stale 标识端到端透传**;**接口抖动不闪空白**(`placeholderData` 已建)。
12. **每项改动可独立 feature flag 回退**,无 schema 变更、无数据迁移。
13. **不部署**(除非用户明确要求);N1/L2 的"部署"指明确请求后再执行。
14. **不清理或 revert 无关脏改动**(dirty 55 文件保留)。
15. **不写新规划文档**(本文之外)——现有方案已饱和,该执行。

---

## 3. 工作包总览(融合后的 9 项,按优先级)

| 优先级 | ID | 工作包 | 源文档 | 工作量 | 并行性 |
|---|---|---|---|---|---|
| **P0** | **W1** | L1 全局 retry 改"有限指数退避" | L1 | 0.5 天 | 与 W2/W3/W4/W5 并行 |
| **P0** | **W2** | L2 接入后端已有 BFF 合包 | L2 | 1-2 天 | 与 W1 并行 |
| **P0** | **W3** | N1 A6 观测部署 + 性能根因 + 部署验收 | N1 | 2-3 人日 | 与 W4 并行 |
| **P0** | **W4** | N2 RuntimeTask 任务注册表治理 | N2 | 2-3 人日 | 与 W3 并行 |
| **P0** | **W5** | L4 全局错误兜底 `QueryErrorBoundary` | L4 | 1 天 | 必须等 W1 |
| **P1** | **W6** | N3 Execution Model 真实逐日 forward path + golden parity | N3 | 4-5 人日 | 必须等 W4 |
| **P1** | **W7** | N4 Analytics manifest 生命周期 + 报告版本追踪 | N4 | 3-4 人日 | 与 W6 并行 |
| **P1** | **W8** | L3 AntD 首屏切片再走一刀 + 性能预算门接入 CI | L3 | 1-2 天 | 与 W6/W7 并行 |
| **P2** | **W9** | N5 Strategy Engine 长期 shadow parity + 前端 Shadow/Preview 标签降噪 | N5 | 3-4 人日 | 必须等 W6/W7 |

**优先级语义**:
- **P0(立即,1-2 周内)**:用户体感修复(W1/W2/W5) + 架构关键观测部署(W3) + 注册表治理(W4)
- **P1(深化,3-4 周内)**:工程治理闭环(W6/W7/W8)
- **P2(长线,5-6 周内)**:Shadow parity 长期对照与信息层级降噪(W9)

---

## 4. P0 工作包详情(立即开工)

### 工作包 W1｜L1 全局 retry 改"有限指数退避"

#### 目标
立即消除"抖动失败一次就红屏"——这是用户最直接的痛点,改 1 个常量即可极大改善。

#### 为什么现在做
B1 已实测:`queryClient.ts` 三处 `retry: false`,且 `placeholderData` 虽建但"失败 = 空白"仍存在。L1 修对,W5(错误兜底)才有意义。

#### 涉及文件 / 模块
- `frontend/src/state/queryClient.ts`(改默认 retry / retryDelay)
- `frontend/src/api/base.ts`(与既有 `retryRequest` 统一口径,不嵌套)
- 测试:`frontend/src/state/queryClient.test.ts`(新建)、`frontend/src/api/base.test.ts`(扩)

#### 不允许做什么
- ❌ 写操作(mutations)启用重试(仍 `retry: false`,避免重复写)
- ❌ 401 / 403 / 400 / 404 / 422 重试(用户/认证错误立即返回)
- ❌ AbortError 重试(组件卸载)
- ❌ 重试上限 > 2 次(避免重试风暴)
- ❌ 改其他业务语义

#### 验收标准
1. `queryClient.ts queryClientDefaults.retry`:`(failureCount, error) => failureCount < 2 && isRetryableError(error)`
2. `isRetryableError`:**只对网络/5xx/超时重试**;401/403/4xx 不重试;Abort 不重试
3. `retryDelay: (i) => Math.min(1000 * 2 ** i, 8000)` 指数退避
4. mutations 仍 `retry: false`
5. 监控页 mock 单接口失败一次后重试成功,**UI 不闪红**
6. mock 401 → 不重试直接走登录

#### 测试命令
```bash
cd frontend && npm test -- --run src/state/queryClient.test.ts src/api/base.test.ts
cd frontend && npm test -- --run src/features/trading-workspace/MonitorPage.test.tsx
```

#### 风险与回滚
- **风险**:5xx 持续故障时重试导致 QPS 短期推高;指数退避 + max=2 限住。
- **回滚**:`retry` 改回 `false`(单常量回退);无 schema 变更。

---

### 工作包 W2｜L2 接入后端已有 BFF 合包

#### 目标
监控页一次刷新 **13 次 RT → 1 次 RT**;后端 `monitor_workspace_bff` 已就绪(cache + overlay + remote fallback),前端只是"接到位"。

#### 为什么现在做
B3 已实测:后端 `bff.py:89,121` 早已实现,前端 0 引用——**已建好的能力没接上**。

#### 涉及文件 / 模块
- 新建 `frontend/src/features/trading-workspace/useMonitorWorkspaceBff.ts`
- 改造 `frontend/src/features/trading-workspace/useMonitorData.ts`(默认走合包 + 失败降级)
- 新建 `frontend/src/features/trading-workspace/useMonitorWorkspaceBff.test.ts`
- 后端契约不动:`backend/app/api/routes/bff.py: monitor_workspace_bff`

#### 不允许做什么
- ❌ 修改后端 BFF 合包逻辑(已就绪,只接入)
- ❌ 拆 13 个 useQuery(保留作 fallback)
- ❌ 把响应数据复制进 Zustand store(沿用 service state)
- ❌ 改 stale 标识传递(端到端透传)

#### 验收标准
1. 浏览器 DevTools Network:监控页一次刷新只 1 个 `bff/v1/workspace/monitor` 请求
2. 合包失败时降级到独立 13 个 useServerState(feature flag `MONITOR_BFF_AGGREGATE_ENABLED=true`,可关)
3. 监控页 P95 较 M0 ↓≥50%(冷启)/ ↓≥30%(热)
4. **关键字段 sha256 合包前后一致**(parity 守卫):`priority_board.items[*].{symbol/priority_score/production_score/buy_signal_state/elite_watch_score}`
5. `npm test --run` 全绿,含新 `useMonitorWorkspaceBff.test.ts`

#### 测试命令
```bash
cd frontend && npm run api:check && npm test -- --run \
  src/features/trading-workspace/useMonitorWorkspaceBff.test.ts \
  src/features/trading-workspace/MonitorPage.test.tsx
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_bff_*.py -q
```

#### 风险与回滚
- **风险**:合包 payload schema 与既有 13 个 query 字段不完全对应(实测后端 schema 已覆盖,但需验证)
- **回滚**:`MONITOR_BFF_AGGREGATE_ENABLED=false` 立即回到现状 13 个独立 query

---

### 工作包 W3｜N1 A6 观测部署 + 性能根因 + 部署验收

#### 目标
把 A6 的观测能力(`/api/runtime-tasks/summary|workers|failures|artifacts` + worker heartbeat)**真正部署到线上**;同时启动 A7 警告的根因排查。

#### 为什么现在做
R1+R2 已实测:A6 自承"未部署导致 queue wait / failure rate 在线不可见";告警增长无人盯。**已建的能力不部署 = 等于没建**。

#### 涉及文件 / 模块
- 后端:`backend/app/api/routes/runtime_tasks.py`、`backend/app/services/runtime_worker_health.py`、`backend/app/services/tasks/queue.py`
- 前端:`frontend/src/features/data-console/*`(展示 4 类 worker 心跳与队列)
- 部署:`docker-compose.mysql.yml`、`scripts/run_platform_component.sh`、deploy delta-package 脚本
- 性能根因:`backend/app/services/bff/*`、`market/local_quote_cache.py`、Go `market-read-service`(只读核验)

#### 不允许做什么
- ❌ 部署任何生产排序/策略口径变更
- ❌ 触发 RuntimeTask 写入操作(只读观测)
- ❌ 修改 Go 服务(本工作包只看 metrics 和日志做诊断)
- ❌ 引入新观测框架(Prometheus exporter 已有,Grafana 已有)
- ❌ 用部署绕过 `participates_in_priority_board` 单一生产门

#### 验收标准
1. 线上 `GET /api/runtime-tasks/summary` 返回非 0 数据(队列/失败/等待时长齐全)
2. 线上 `GET /api/runtime-tasks/workers` 4 类组件心跳齐全(`runtime-worker / runtime-scheduler / analytics-worker / backtest-worker`)
3. 数据控制台页面展示 4 类 worker 心跳 + 失败任务 + 队列等待最长 + 产物路径
4. 性能基线报告新增:**BFF timeout / market-read fallback / unresolved miss 三项的根因分类**
5. 设立**回归阈值**:`monitor_bff p95 ≤ 500ms`、`priority_board p95 ≤ 500ms`、`market_read.unresolved < N`
6. 落档 `docs/reports/platform-architecture-observability-deployment-2026-06-XX.md`

#### 测试命令
```bash
# 部署后线上验证(只读 GET)
curl -fsS -b "session=$TOKEN" "$BASE/api/runtime-tasks/summary" | jq .
curl -fsS -b "session=$TOKEN" "$BASE/api/runtime-tasks/workers" | jq '.workers[]|{component,worker_id,age_seconds,status}'
curl -fsS -H "X-Admin-Token: $ADMIN_API_TOKEN" "$BASE/metrics" | rg "bff_partial_timeout|market_read_unresolved|market_read_fallback|local_quote_cache"

# 本地回归
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_runtime_task_contracts.py backend/tests/test_runtime_worker_health.py -q
cd frontend && npm test -- --run src/features/data-console/DataConsolePage.test.tsx
```

#### 风险与回滚
- **风险**:部署 A6 端点引入新读路径占用,可能短期推高 Web QPS
- **回滚**:观测 API 增 feature flag `RUNTIME_TASK_OBSERVABILITY_ENABLED`,关掉即回退
- **不破坏边界证明**:所有改动仅在 GET 路径(上一份复查已断言 summary/workers 不写 DB)

---

### 工作包 W4｜N2 RuntimeTask 任务注册表治理

#### 目标
把所有 RuntimeTask 任务类型集中到**单一注册表**,声明 `owner / worker / retry_policy / artifact_path / idempotency_key_pattern / expected_runtime_ms`,并由该注册表驱动 Web 入口审计。

#### 为什么现在做
- R6 已实测:~14 种 task type 散落各处;新增任务靠 grep,审计成本高
- W3 部署后,前端要展示"task type → owner → 健康度",没有注册表就只能展示字符串
- Web 重任务入口审计是这次架构整改的核心承诺(boundary-map §"Web Process must not")

#### 涉及文件 / 模块
- 后端:`backend/app/services/tasks/registry.py`(扩)、`runtime_worker.py`、`analytics_handlers.py`、`scripts/analytics_worker.py`、`backtest_worker.py`、`runtime_scheduler.py`
- 守卫:新增 `backend/tests/test_runtime_task_registry_governance.py`、`test_web_route_no_heavy_compute.py`
- 文档:`docs/architecture/runtime-task-registry.md`(新建)

#### 不允许做什么
- ❌ 改 task 实际执行逻辑(只做声明 + 守卫)
- ❌ 把任何 task 从 worker 拉回 Web 进程
- ❌ 改变 `RuntimeTaskQueue` 状态机
- ❌ 影响 production_score / priority_board / strategy_policy
- ❌ 引入新依赖(注册表用 dataclass / TypedDict 即可)

#### 验收标准
1. `backend/app/services/tasks/registry.py` 暴露 `RUNTIME_TASK_REGISTRY: dict[str, TaskDefinition]`,字段:`owner_role`(quant/data/devops)、`worker`(runtime|analytics|backtest|scheduler)、`retry_policy`、`max_attempts`、`artifact_kind`、`idempotency_required: bool`、`expected_runtime_p95_ms`
2. 守卫测试:`runtime_worker._execute_task` 与各 worker 注册的 task_type 必须全部在注册表里;反之亦然(没有"幽灵任务")
3. **Web 路由守卫**:遍历 `app/api/routes/*.py` 抽出所有处理函数,确保不直接调用 registry 中 `worker != "web"` 的处理器
4. `docs/architecture/runtime-task-registry.md` 落地,含表格 + owner 联系人
5. `boundary-map` 同步更新引用本注册表

#### 测试命令
```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_runtime_task_registry_governance.py \
  backend/tests/test_web_route_no_heavy_compute.py \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_runtime_task_contracts.py -q

# 注册表可读性
PYTHONPATH=backend:. backend/.venv/bin/python -c "from app.services.tasks.registry import RUNTIME_TASK_REGISTRY; import json; print(json.dumps(list(RUNTIME_TASK_REGISTRY), indent=2, ensure_ascii=False))"
```

#### 风险与回滚
- **风险**:守卫测试发现历史漏接的 task type → 暂时进 allowlist 等下一波修
- **回滚**:注册表纯声明 + 守卫测试,回退 = 删测试文件,无业务影响

---

### 工作包 W5｜L4 全局错误兜底 `QueryErrorBoundary`

#### 目标
接口失败时各页面 UI 行为一致化:**"加载失败,正在重试…"+ 上次缓存可见**,杜绝裸红屏/空白。

#### 为什么现在做
W1(retry)修了底层,W5 才有"显式失败 UI"可展示;若 W1 未先做,boundary 只会暴露"红"而不能自动重试。

#### 涉及文件 / 模块
- 新建 `frontend/src/ui/feedback/QueryErrorBoundary.tsx` + test
- 改造监控/纸面/策略追踪/回测/数据控制台等关键页面包裹 boundary
- `frontend/src/api/base.ts` 显式化 `timeoutMs` 默认值

#### 不允许做什么
- ❌ Boundary 内调真实接口(让 Query 自己重试)
- ❌ 失败文案出现"建议/必涨/低吸/突破即买"等业务误导词(沿用既有文案守卫)
- ❌ 自定义重试逻辑绕过 W1 的 retry 策略
- ❌ 改业务语义或字段口径

#### 验收标准
1. 模拟接口 500 → 显示"加载失败,正在重试…",**不闪空**;重试成功后 UI 自动恢复
2. 模拟 401 → 走登录态,**不进 boundary 重试循环**
3. 接口 `timeoutMs` 默认值显式化(如 8s),在 `api/base.ts` 集中
4. 关键页面单测:每个页面包裹 boundary 后,mock 失败一次,UI 文案 + 可见性正确

#### 测试命令
```bash
cd frontend && npm test -- --run \
  src/ui/feedback/QueryErrorBoundary.test.tsx \
  src/features/trading-workspace/MonitorPage.test.tsx \
  src/features/strategy-tracking/StrategyTrackingPage.test.tsx \
  src/features/paper/PaperTradingPage.test.tsx \
  src/features/backtest/BacktestDashboard.test.tsx \
  src/features/data-console/DataConsolePage.test.tsx
```

#### 风险与回滚
- **风险**:boundary 可能屏蔽真实错误日志 → 必须显式上报 console.error + Sentry(若有)
- **回滚**:删除 `QueryErrorBoundary` 包裹,各页面回到现状

---

## 5. P1 工作包详情(深化)

### 工作包 W6｜N3 Execution Model 真实逐日 forward path + golden parity

#### 目标
把 Execution Model 从"阻断态占位"升级到"真 parity 预览":补 1/3/5/10 日真实 forward return path,建立 `signal/order/fill/position/exit → portfolio_backtest_metrics` 的 **golden parity**;**继续保持 `replacement_enabled=false`**。

#### 为什么现在做
- R3 已实测:A4 报告自承"目前是 blocked_reason=no_daily_return_path",这是占位不是能力
- W4 完成后 backtest_worker 产物 schema 才能稳定,W6 才有可靠基底
- 没有真实 forward path,W9 前端 Preview 降噪也无法落地

#### 涉及文件 / 模块
- 后端:`backend/app/services/backtest/persistence.py`、`backend/app/services/backtest_job_service.py`、`backend/app/services/backtest/engine_helpers.py`(已有 `next_trade_dates`)
- 真值参照:`backend/scripts/low_buy_market_backtest_reporting.py: portfolio_backtest_metrics`(唯一组合事实源)
- 守卫:新增 `backend/tests/test_execution_model_forward_path_parity.py`、扩 `test_execution_model_backtest_golden.py / paper_golden.py`

#### 不允许做什么
- ❌ `replacement_enabled` 改为 true(永久 false)
- ❌ Execution Model 输出影响生产排序或 production_score
- ❌ 用模型/外推/插值生成 forward return(只能用真实日线 OHLC)
- ❌ 并行实现 `portfolio_backtest_metrics`(违反单一事实源边界)
- ❌ 当 daily_bar 缺失时静默 fallback——必须显式 `blocked_reason / no_data / preview_unavailable`

#### 验收标准
1. `BacktestRun.persisted_signal` 含真实 `return_1d / return_2d / return_3d / return_4d / return_5d / max_gain_5d / max_drawdown_5d`(由 `next_trade_dates` + 真实日线计算)
2. **Golden parity 测试**:同一组 signal/order/fill,Execution Model 输出与 `portfolio_backtest_metrics(max_5/max_10)` 在 max_5/max_10 真实组合收益 **1e-9 一致**
3. 缺数据(停牌/退市/复权口径冲突)**保留** `blocked_reason=no_daily_return_path | partial_path | suspended` 多分类
4. Frontend `BacktestDashboard.panels.tsx` 显示 forward path + 显式标"Preview · 非事实源"
5. `replacement_enabled` 在代码中**写死 False**,有守卫测试断言
6. 落档 `docs/reports/platform-architecture-execution-model-parity-2026-06-XX.md`

#### 测试命令
```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_execution_model_forward_path_parity.py \
  backend/tests/test_execution_model_backtest_golden.py \
  backend/tests/test_execution_model_paper_golden.py \
  backend/tests/test_execution_model_boundary.py \
  backend/tests/test_backtest_engine_regression.py -q

cd frontend && npm test -- --run src/features/backtest/BacktestDashboard.test.tsx
```

#### 风险与回滚
- **风险**:历史 BacktestRun 缺日线 → parity 测试失败;处置 = 显式标 `blocked_reason=legacy_no_path`
- **回滚**:回滚到 A4 阻断态行为(forward path 不展示);schema 字段可保留,前端隐藏即可

---

### 工作包 W7｜N4 Analytics manifest 生命周期 + 报告版本追踪

#### 目标
把 24M Analytics 链路(Parquet export → manifest → quality → DuckDB report)的"生命周期"治理闭环:**manifest 版本追踪 + 增量过期 + 状态传播 + 报告产物索引**。

#### 为什么现在做
- R5 已实测:manifest 本身的版本/过期/失效无统一治理;DuckDB 报告任务耗时未观测
- W9 长期 parity 要读历史报告做对照,没有版本索引就读不到
- 与 W3 观测部署天然协同(报告产物路径要进 data-console 展示)

#### 涉及文件 / 模块
- 后端:`backend/app/services/analytics/exporters.py / quality.py / report_queries.py / manifest.py`
- 报告产物:`backend/data/analytics/reports/`、`backend/data/analytics/parquet/`
- 任务编排:`backend/scripts/analytics_worker.py`、`backend/app/services/tasks/analytics_handlers.py`
- 守卫:`backend/tests/test_analytics_manifest_lifecycle.py`、`test_analytics_report_versioning.py`

#### 不允许做什么
- ❌ 把 DuckDB/Parquet 提升为生产事实源(永远只是分析/报告层)
- ❌ Web 进程直接生成 manifest 或 Parquet
- ❌ 删除既有 manifest(只做"标记过期",保留可追溯)
- ❌ 修改 24M 报告口径(每日信号等权复利收益 + 真实组合 max5/max10 不变)
- ❌ 改 `coverage_pct` capped 语义(A2 已稳定)

#### 验收标准
1. 每个 manifest 含:`manifest_id / dataset_version / generated_at / valid_until / superseded_by / status(active|stale|partial|blocked|no_data)`
2. Analytics worker 生成新 manifest 时**自动标记上一份为 superseded**(不删,只标记)
3. DuckDB 报告产物索引:`backend/data/analytics/reports/index.json`
4. 状态传播:`quality.py` 的 `blocked/no_data/stale/partial` 沿调用链一路传到前端 `data-console`
5. 数据控制台展示:最新报告 / 历史 N 份 / 每份耗时 / 对应 manifest
6. 落档 `docs/reports/platform-architecture-analytics-lifecycle-2026-06-XX.md`

#### 测试命令
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

#### 风险与回滚
- **风险**:旧 manifest 缺生命周期字段 → 标 legacy,不阻断现有读路径
- **回滚**:字段是 schema 增量;不依赖新字段的旧消费方不受影响

---

### 工作包 W8｜L3 AntD 首屏切片再走一刀 + 性能预算门接入 CI

#### 目标
首屏 gz ↓≥20%;接入性能预算门防止回退。

#### 为什么现在做
- B4 已实测:`antd-core 329K + antd-check-controls 316K + antd-display 186K` 仍偏重
- W1/W2/W5 修了体感,W8 是"压预算 + 防回退"的工程化收尾

#### 涉及文件 / 模块
- `frontend/vite.config.ts`(复审 manualChunks)
- 新建 `frontend/src/ui/icons/index.ts`(图标集中索引)
- 新建 `frontend/scripts/check-bundle-budget.mjs`
- `frontend/package.json` 加 `"check:bundle-budget"`,接入 `npm run lint`
- 新建 `frontend/.bundle-allowlist.json`

#### 不允许做什么
- ❌ 引入新打包工具(沿用 Vite + rolldown)
- ❌ 移除任何 AntD 组件(只是按页面 lazy)
- ❌ 改 ECharts 引入方式(canvas + 手动实例 + lazy 已最优)
- ❌ 修改业务页面布局

#### 验收标准
1. `vite.config.ts` manualChunks 复审:`antd-check-controls`(Checkbox/Radio/Switch/Slider)按页面 lazy;`antd-display`(Table/List/Tree)审查首屏必要性
2. `@ant-design/icons` 按需 import,集中索引 `frontend/src/ui/icons/index.ts`
3. `check-bundle-budget.mjs` 断言 `first_screen_js_gzip_kb ≤ 350`、单 chunk gz ≤ 150(超须 `.bundle-allowlist.json` 显式列出)
4. `npm run lint` 含 `check:bundle-budget`
5. `npm run analyze` 首屏 gz 较 M0 ↓ ≥ 20%
6. CI 故意把 Detail 组件挪回首屏 → 红;恢复 → 绿

#### 测试命令
```bash
cd frontend && npm run lint && npm run build && npm run analyze
```

#### 风险与回滚
- **风险**:首屏 lazy chunk 增多可能让第二屏切换略慢;`react-router` 预加载可缓解
- **回滚**:`vite.config.ts` 切片回退到当前 splitVendorChunks;`.bundle-allowlist.json` 临时放宽

---

## 6. P2 工作包详情(长线)

### 工作包 W9｜N5 Strategy Engine 长期 shadow parity + 前端 Shadow/Preview 标签降噪

#### 目标
两件事合在一起做(强相关,共享前端 schema):
1. **Strategy Engine 长期 shadow parity**:Shadow 输出从"单点 delta"升级为"累计 parity 统计"
2. **前端信息层级降噪**:监控页/纸面/策略追踪/数据控制台/回测中心的 `Shadow / Preview / Research / Paper / research_only / watch_only / near_entry` 标签明确化

#### 为什么现在做
- R4 已实测:shadow 单点输出无法做长期决策
- W6/W7 落地后,前端面板有 Shadow/Preview 实际数据可展示,降噪才有抓手
- A3 已建 shadow,A7 测试没回归到 shadow parity 漂移——潜在盲区

#### 涉及文件 / 模块
- 后端:`backend/app/services/strategy_engine/shadow.py / low_buy_adapter.py`、新增 `strategy_engine/parity_tracker.py`
- 前端:`frontend/src/features/{data-console,monitor,strategy-tracking,paper,backtest}/*`、`pageResponsibilities.ts`、`workspace-shared/workspaceViewModels.ts`
- 守卫:`backend/tests/test_strategy_engine_parity_tracker.py`、扩 `test_strategy_engine_production_gate_guards.py`

#### 不允许做什么
- ❌ Strategy Engine 进入 priority_board 排序或 production_score
- ❌ 修改 `participates_in_priority_board` 语义
- ❌ 把 `Shadow / Preview / Research` 标签转成"建议买入/卖出/必涨/低吸"
- ❌ 让 `near_entry` 进入生产收益排行
- ❌ 把 Paper 真实成交结果暴露成生产事实源
- ❌ 引入新前端框架

#### 验收标准
1. `strategy_engine/parity_tracker.py`:累计统计 Strategy Engine vs 现生产 priority_score 的差异分布、缺失率、零分率、按策略分组
2. 落档 `docs/reports/platform-architecture-strategy-engine-parity-2026-06-XX.md`,含**至少 30 个交易日**的累计对照
3. 前端每个面板的 Shadow/Preview/Research/Paper 标签**有色块 + tooltip + 链接到说明文档**;**不混用**
4. 守卫测试:文案不出现"建议买入/卖出/低吸/必涨/突破即买";`page-responsibilities.ts` 守卫不回退
5. **核心硬断言**:Strategy Engine parity 报告**显式标注"非生产采纳依据,仅长期对照"**

#### 测试命令
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

#### 风险与回滚
- **风险**:parity 报告显示 Strategy Engine 差异极大 → **正是它该被发现的事**,报告写明,**不替换生产**
- **回滚**:前端标签纯展示层,关闭 feature flag 即回到现状;parity tracker 独立任务,关掉不影响 priority_board

---

## 7. 并行 / 串行图(融合后)

```
                        P0 同步启动(第 1-2 周)
   ┌─────────────────────────────────────────────────────────────┐
   │                                                             │
[W1 retry 改]    [W2 BFF 合包接入]   [W3 N1 观测部署]   [W4 N2 注册表]
   (0.5天)         (1-2天)            (2-3天)            (2-3天)
   │                │                   │                │
   ├────────┬───────┘                   │                │
   │        ▼                           │                │
   │  [W5 L4 错误兜底]                  │                │
   │       (1天)                        │                │
   │                                    │                │
   ▼                                    ▼                ▼
   并行,W5 必须等 W1               P0 完成才进 P1
                                         │
                P1 同步启动(第 3-4 周)
              ┌──────────────┬──────────┴────────────┐
              ▼              ▼                       ▼
      [W6 N3 ExecModel    [W7 N4 Analytics      [W8 L3 包预算门]
       forward parity]    manifest 生命周期]      (1-2 天)
       (4-5 天)           (3-4 天)               (与 W6/W7 并行)
              │              │
              └──────┬───────┘
                     │
              P1 完成才进 P2(第 5 周)
                     ▼
        [W9 N5 Strategy Engine parity
         + 前端 Shadow/Preview 降噪]
              (3-4 天)
```

### 串行硬约束
- **W5 必须等 W1**:错误兜底依赖底层 retry 正确
- **W6 必须等 W4**:ExecModel parity 依赖 backtest_worker 产物 schema 稳定
- **W9 必须等 W6+W7**:前端降噪需要 forward path 真数据 + manifest 版本追踪
- W1/W2/W3/W4 完全并行
- W6/W7/W8 完全并行

---

## 8. 明确不该现在做(本期硬否)

| # | 不做的事 | 理由 |
|---|---|---|
| 1 | 替换 low-buy / priority board / front-row weighted / strategy tracking 生产排序 | 硬边界 4 |
| 2 | 修改 `strategy_policy.py` 生产准入语义 | 硬边界 3 |
| 3 | Execution Model `replacement_enabled=true` | 永久 false |
| 4 | Strategy Engine 进入生产打分 | 硬边界 5;Shadow 永远不影响 priority_board |
| 5 | DuckDB / Parquet 提升为生产交易事实源 | 硬边界 6 |
| 6 | Web 进程执行重任务 | 硬边界 7;由 W4 注册表 + 守卫测试强制 |
| 7 | 拆微服务 | 硬边界 1 |
| 8 | 推倒重写 | 硬边界 2 |
| 9 | 新增框架级依赖(Celery / Kafka / K8s / Cython / JAX / 全栈 async / SSR / RSC / WASM / 微前端 / WebSocket) | 硬边界 1+9 |
| 10 | 部署 | 硬边界 13;仅 W3/W2 在用户明确确认后执行 |
| 11 | 清理或 revert 无关脏改动 | 硬边界 14;dirty worktree 55 文件保留 |
| 12 | 把 research_only / watch_only / near_entry / Paper 转生产 | 硬边界 5 |
| 13 | 把"做 T 推荐 / 智能买卖点 / 智能止损"接到 Strategy Engine | 越界为指令工具 |
| 14 | 再加新选股策略 | 24M 证据门未达不可加 |
| 15 | 写新规划文档(本文之外) | 现有方案已饱和,该执行 |
| 16 | 改 30s 轮询频率、实现增量物化(L5)、引 WebSocket | 改快放大问题;前端方案明确排除 |
| 17 | 改 24M 报告口径(每日信号等权复利收益 + max5/max10) | 沿用既有 |
| 18 | 改 `coverage_pct` capped 语义 | A2 已稳定 |

---

## 9. 量化验收门(融合)

| 维度 | 指标 | M0 基线 | 目标 |
|---|---|---|---|
| **用户体感** | 监控页"一次抖动失败导致红屏"率 | 高(retry=false) | **0**(W1) |
| **用户体感** | 监控页一次刷新请求数 | 13 | **1**(W2) |
| **用户体感** | 监控页 P95 冷启 | 850ms+(云报告) | **↓≥50%**(W2) |
| **用户体感** | 监控页 P95 热路径 | 受 overlay/filter 拖累 | **↓≥30%**(W2) |
| **用户体感** | 首屏 gz | 待 analyze | **↓≥20%**(W8) |
| **用户体感** | 单 chunk gz | antd 最大 ~150KB | **≤150KB gz**(W8) |
| **用户体感** | 接口失败 UI | 空白/红屏 | **统一"加载失败,正在重试"+ 上次缓存**(W5) |
| **架构治理** | 在线 worker 心跳可见 | 不可见(A6 未部署) | **4 类组件齐全**(W3) |
| **架构治理** | 在线 queue wait / failure rate | 不可见 | **可见**(W3) |
| **架构治理** | `monitor_bff` p95 阈值 | 一度 852ms | **≤500ms**(W3) |
| **架构治理** | `priority_board` p95 阈值 | 一度 1101ms | **≤500ms**(W3) |
| **架构治理** | RuntimeTask 注册表 task type 覆盖率 | 散落 | **100% 注册 + 守卫**(W4) |
| **可信度** | ExecModel max5/max10 与 portfolio_backtest_metrics parity | 不可用(阻断态) | **1e-9 一致**(W6) |
| **可信度** | Analytics manifest 生命周期字段 | 缺失 | **完整 5 状态**(W7) |
| **可信度** | Strategy Engine 长期 parity 报告 | 无 | **≥30 个交易日累计对照**(W9) |
| **回归** | 关键字段 sha256(合包前后) | — | **一致**(W2 parity) |
| **回归** | `pytest backend/tests` | 全绿 | **全绿** |
| **回归** | `npm test --run` | 全绿 | **全绿** |
| **回归** | `npm run api:check` | 通过 | **通过** |

---

## 10. Verification Commands(总验收)

```bash
# 后端
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q

# 前端
cd frontend
npm run api:check          # 契约不漂移
npm run lint               # 含 check-state-separation / check-refactor-guard / check-bundle-budget(W8 后)
npm test -- --run          # 含新 useMonitorWorkspaceBff.test.ts / QueryErrorBoundary.test.tsx / queryClient.test.ts
npm run build
npm run analyze            # 看 first_screen_js_gzip_kb / Top chunks

# 浏览器实测(W1+W2+W5 验证)
# 进入监控页 → DevTools Network → 只 1 个 /api/bff/v1/workspace/monitor 请求
# 模拟接口 500 → UI 显示"加载失败,正在重试…" + 1-2 秒后自动恢复
# 模拟 401 → 走登录,不重试

# 在线只读验证(W3 部署后)
curl -fsS -b "session=$TOKEN" "$BASE/api/runtime-tasks/summary" | jq .
curl -fsS -b "session=$TOKEN" "$BASE/api/runtime-tasks/workers" | jq '.workers[]|{component,worker_id,age_seconds,status}'
curl -fsS -H "X-Admin-Token: $ADMIN_API_TOKEN" "$BASE/metrics" | rg "bff_partial_timeout|market_read_unresolved|market_read_fallback"

# DuckDB 报告(W7 后)
DATABASE_URL=sqlite:///backend/data/t_quant.db PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/run_duckdb_strategy_report.py \
  --output-md /tmp/analytics_report.md --output-json /tmp/analytics_report.json
```

### 门禁回归(任一红即不进下一工作包)
- `test_strategy_engine_boundary.py / test_strategy_engine_production_gate_guards.py`(Shadow 不进生产)
- `test_execution_model_boundary.py`(Preview 不替换事实源)
- `test_low_buy_production_scoring.py / test_low_buy_priority_board_strategy_variants.py`(生产排序未漂移)
- `test_contract_first_openapi.py`(契约未漂移)
- `check-state-separation.mjs / check-refactor-guard.mjs / check-bundle-budget.mjs`(前端架构守卫)
- W2 parity 测试:关键字段 sha256 合包前后一致
- W6 parity 测试:ExecModel 与 portfolio_backtest_metrics 1e-9 一致

---

## 11. 整体执行节奏

```
第 1 周:W1 retry 改 + W2 BFF 接入 + W3 观测部署 + W4 注册表治理(P0 并行)
        ↓ W5 错误兜底(必须等 W1,本周内完成)
第 2 周:W3 部署窗口(用户确认后);W2/W4 收尾合入;P0 验收报告
第 3 周:W6 ExecModel parity + W7 Analytics manifest + W8 包预算门(P1 并行)
第 4 周:P1 收尾,parity / lifecycle 报告落档
第 5 周:W9 Strategy Engine parity + 前端 Shadow/Preview 降噪
第 6 周:最终回归 + 总验收报告
```

**回归命令(每个工作包完成必跑)**:
```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
cd frontend && npm run api:check && npm run lint && npm test -- --run && npm run build && npm run analyze
```

---

## 12. 输出与提交节奏

- 工作包按文档规范 §6.1 **一项一 commit**(本期不在主体仓做修改;dirty 55 文件不在本文范围内,沿用既有 PR 节奏)
- 每个工作包完成后产出对应 `docs/reports/platform-architecture-<topic>-2026-06-XX.md`,沿用 A0–A7 既有命名
- 守卫测试与新增 schema 字段必须随主代码同 commit;**严禁** "先合代码后补测试"
- 不部署:W3/W2 的部署动作单独在用户明确请求时执行;本文不预先触发
- Rollback flag 全部就绪:`MONITOR_BFF_AGGREGATE_ENABLED`、`RUNTIME_TASK_OBSERVABILITY_ENABLED`、`EXECUTION_MODEL_REPLACEMENT_ENABLED=false`(永久)、`STRATEGY_ENGINE_PARITY_REPORT_ENABLED`、`BUNDLE_BUDGET_GATE_ENABLED`

---

## 13. 总工作量与 ROI

| 优先级 | 工作包数 | 工作量 | 用户感知 ROI |
|---|---|---|---|
| **P0** | W1+W2+W3+W4+W5(5 项) | ~6-9 人日(并行 1-2 周) | **极大**:UI 不再"一抖即红";监控页 P95 下降一半;线上观测可见;治理基础打地基 |
| **P1** | W6+W7+W8(3 项) | ~8-10 人日(并行 2 周) | **中**:工程治理闭环;ExecModel 可信度;前端预算门 |
| **P2** | W9(1 项) | ~3-4 人日(1 周) | **中**:Shadow parity 长期对照;前端标签降噪 |
| **合计** | **9 项** | **~17-23 人日,约 5-6 周** | **用户体感 + 架构治理双线收口** |

---

## 14. Definition Of Done

- ✅ 监控页一次刷新只 1 个 BFF 请求(W2)
- ✅ 抖动失败一次 UI **不闪红**,自动重试 1-2 次成功(W1)
- ✅ 接口失败统一走 `QueryErrorBoundary`,不出现空白/裸红屏(W5)
- ✅ 首屏 gz 较 M0 ↓≥20%(W8);单 chunk ≤ 150KB gz
- ✅ 线上 4 类 worker 心跳齐全 + queue wait/failure rate 可见(W3)
- ✅ RuntimeTask 注册表 100% 覆盖 + Web 路由守卫绿(W4)
- ✅ ExecModel max5/max10 与 portfolio_backtest_metrics parity 1e-9 一致(W6)
- ✅ Analytics manifest 5 状态生命周期 + 报告产物索引(W7)
- ✅ Strategy Engine ≥30 个交易日累计 parity 报告 + 前端 Shadow/Preview 标签明确化(W9)
- ✅ 关键字段 sha256 合包前后一致(W2)
- ✅ `pytest backend/tests` + `npm test --run` + `npm run api:check` + `npm run analyze` 全绿
- ✅ 未换 React/AntD/Vite/ECharts;未引新依赖
- ✅ 业务语义/策略口径/生产门未受影响
- ✅ 每项可独立 flag 回退,无 schema 变更、无数据迁移

---

## 15. 一句话结论

**下一阶段不是再加新能力,而是同时做两件事**:
- **用户体感立即改善**(W1 retry 修复 + W2 接已就绪的后端 BFF 合包 + W5 错误兜底 UI)——~3-5 人日就能从"一抖即红"和"13 次串行请求"变成"统一容错重试 + 1 次合包",这是最直接可感知的改善;
- **架构治理闭环**(W3 观测上线 + W4 注册表 + W6/W7 深化 + W8 预算门 + W9 长期对照)——4-5 周把第一波 A0–A7 整改建好的能力**部署生效 + 工程化闭环**。

**P0 五项并行 1-2 周内可见效;P1/P2 共 4 项串行收尾 3-4 周**。全程**不换栈、不改业务、不动策略口径**,9 项全部独立 flag 可回退。
