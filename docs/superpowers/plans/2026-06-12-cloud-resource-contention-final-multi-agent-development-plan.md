# Cloud Resource Contention Final Multi-Agent Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 通过“先停非核心任务止血、再收敛调度结构、最后治理 MySQL/机器规格/域名根因”的三层方案，解决线上服务器资源争抢导致的卡顿，同时确保监控、行情缓存、低吸榜、priority board、策略追踪继续运行。

**Architecture:** 云端保持核心小闭环，不切成 Web-only：Web/API、MySQL、Redis、Go 热读/扫描、核心 runtime-worker、独立 runtime-scheduler 在 D5 gate 通过前继续保留。非核心 analytics/backtest/ML/factor/data repair/research/active paper/autopilot/market review 改为默认关闭或按需运行；scheduler embed 只能在完整交易日稳定性证明后进入维护窗口；MySQL 慢查询、规格、TLS/SNI 入口问题单独授权治理。

**Tech Stack:** Docker Compose, FastAPI, MySQL 8.4, Redis 7, Python runtime worker, Go hot-read services, frontend-next, pytest, Playwright/curl, SSH runbook, existing runtime task queue.

---

## 0. 权威输入

执行前必须重新读取以下文件，若文件内容与本计划冲突，以用户当轮明确要求和更高优先级权威文档为准：

- `AGENTS.md`
- `docs/engineering-conventions.md`
- `docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md`
- `docs/superpowers/plans/2026-06-11-cloud-resource-contention-final-remediation.md`
- `docs/superpowers/plans/2026-06-12-cloud-resource-contention-final-integrated-development-plan.md`
- `docs/superpowers/plans/2026-06-12-cloud-resource-contention-legacy-final-development-doc.md`
- `docs/reports/cloud-resource-contention-remediation-2026-06-11.md`
- `docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md`
- `docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md`
- `docs/reports/mysql-runtime-root-cause-review-2026-06-12.md`
- `docs/reports/provider-degraded-cooldown-market-regime-optimization-2026-06-12.md`
- `docs/reports/legacy-frontend-retirement-decision-2026-06-11.md`
- `docs/reports/legacy-frontend-retirement-execution-2026-06-10.md`
- `docs/reports/runtime-task-summary-read-model-optimization-2026-06-12.md`

## 1. 当前结论

### 1.1 这个方案能解决什么

本计划能解决或明显改善“云服务器资源争抢导致卡顿”这一大类问题：

- 云服务器内存长期吃紧。
- swap 高或持续上涨。
- worker、扫描、刷新、回测、Web 抢 CPU/IO。
- 页面/API 在数据刷新、provider fallback、策略物化时变慢。
- runtime 任务队列被低优先级任务挤占。
- 部署后容器资源恢复慢。
- 已移除模拟盘任务继续失败、重试或污染 failed 统计。
- 旧前端入口、部署 scope、CI/Docker 链路回流风险。

### 1.2 这个方案不能单独解决什么

以下问题必须作为第三层或独立专项处理，不能指望只靠停非核心任务彻底解决：

- `weisilianghua.cloud` TLS/SNI connection reset。
- MySQL 慢查询、索引不足、buffer pool 或连接池配置不合理。
- priority board / monitor BFF 查询本身过重。
- 外部行情源限频、返回 HTML、超时、断连。
- 本地机器断网、休眠、关机导致本地重任务不跑。
- 用户浏览器缓存、旧 chunk、用户端网络问题。

### 1.3 当前最优路线

当前最优方案不是“直接 Web-only”，也不是“立即合并 scheduler”，而是：

1. 第一层：先停非核心任务止血，马上减少云端资源争抢。
2. 第二层：治理重复任务、provider fallback、worker RSS 和 scheduler embed 门槛。
3. 第三层：治理 MySQL 慢查询/规格、域名 TLS/SNI、Docker cache 和机器升配。

这条路线对重心任务影响最小，因为核心链路继续保持：

- 监控：`/next/monitor`、`/next/monitor/market`、monitor snapshot、BFF workspace。
- 行情缓存：quote cache、market pulse、Go market-read。
- 低吸榜/推荐榜：low-buy materialization、推荐榜数据。
- priority board：排序、日期、口径、`production_score` 不变。
- 策略追踪：strategy tracking snapshot、页面和 BFF 数据。
- watchdog：latest data watchdog、数据新鲜度检查。

## 2. 硬边界

### 2.1 绝对禁止

- 不改 `backend/app/services/low_buy/strategy_policy.py`。
- 不改变生产策略语义。
- 不改变 `production_score`。
- 不改变 `priority_board` 排序和口径。
- 不把 research/shadow/paper 历史口径绕过门控接入生产排序。
- 不停止 MySQL、Redis、Web/API、Go hot-read、Go scan、核心 runtime-worker。
- 不把云端改成 Web-only。
- 不恢复 active 模拟盘功能。
- 不恢复 `/paper` 或 `/next/paper` 为核心路径。
- 不直接删除生产数据库表、binlog、volume 或核心缓存。
- 不用短窗观察替代完整交易日 D5 gate。

### 2.2 必须单独授权的线上动作

- 修改线上 `.env`。
- 重建、重启、停止、删除线上容器。
- 停独立 `runtime-scheduler`。
- Docker image/build cache 清理。
- MySQL 配置、索引、schema、数据写入。
- 归档、取消、重跑线上 runtime task。
- nginx reload、域名、证书、CDN/WAF、安全组调整。
- 云服务器升配。
- 物理删除或归档 `frontend/` 源码目录。

### 2.3 D5 scheduler embed 硬门槛

`runtime-worker` 内嵌 scheduler 只有在以下条件全部满足后才能进入维护窗口：

| 条件 | 通过标准 |
|---|---|
| 完整交易日观察 | 覆盖 09:15、09:35、10:30、11:30、13:05、14:55、15:10、15:30 |
| `d5_gate.ready` | collector 明确为 `true` |
| MySQL | 无新 OOM；慢查询无异常增速；连接数稳定 |
| Worker RSS | 不持续贴近 limit；recycle guard 无 restart loop |
| Swap | 不持续上涨 |
| Provider pressure | 无 sustained provider fallback storm |
| Queue | 无核心任务积压；无重复 A-key/strategy-tracking 爆量 |
| HTTP/pages | `/readyz` 与核心 `/next/*` 页面可用 |
| 授权 | 用户明确授权 D5 维护窗口 |

当前若 `d5_gate.ready=false`，只允许记录命令，不允许执行 scheduler embed。

## 3. 三层最终方案

### 3.1 第一层：停非核心任务止血

目标：快速减少资源争抢，不影响核心交易观察链路。

| 项 | 目标状态 | 用户影响 | 替代路径 | 恢复条件 |
|---|---|---|---|---|
| `PLATFORM_AUTOPILOT_ENABLED` | `false` | 自动巡检/自愈建议停止 | 人工 runbook | 资源稳定且用户需要 |
| `RUNTIME_LOW_PRIORITY_TASKS_PAUSED` | `true` | analytics/backtest/ML/factor/data repair/research 不抢 worker | 本地或按需 worker | 授权任务窗口 |
| `MARKET_REVIEW_ENABLED` | `false` 或降频 | 午盘/收盘自动复盘停止 | 按需报告 | 资源稳定或低峰窗口 |
| startup prewarm | disabled | 部署后不做重预热 | 必要时人工预热 | 新机器或低峰窗口 |
| `analytics-worker` | on-demand profile | DuckDB/Parquet/分析导出需手动拉起 | 本地或按需容器 | 明确分析窗口 |
| `backtest-worker` | 不常驻 | 24M/批量回测不在云端常驻跑 | 本地或按需 worker | 明确回测窗口 |
| Prometheus/Grafana | 不常驻 | 独立监控面板不可常开 | 只读脚本/临时面板 | 需要图形监控 |
| active paper | 不恢复 | 模拟盘主动交易/自动任务停止 | 监控、策略追踪、回测 | 独立产品方案 |

第一层执行后预期效果：

- 内存可用量增加。
- swap 增速下降。
- runtime-worker 被低优先级任务抢占减少。
- API/page 在刷新和物化时的卡顿减少。
- 部署后容器更快恢复到低资源态。

### 3.2 第二层：合并调度结构前的稳定性治理

目标：先减少重复任务、provider 压力和 worker 内存不确定性，再决定是否合并 scheduler。

| 子项 | 当前策略 | D5 前门槛 |
|---|---|---|
| close-refresh dedupe | 同一 trade date 成功后不重复入队 A-key/strategy-tracking | 交易日内无重复爆量 |
| worker recycle guard | 任务边界回收高 RSS worker | 不中断 running task，无 restart loop |
| provider degraded guard | 慢源/坏源返回 cached/warming/stale | provider warning 低于 sustained pressure 阈值，无 fallback storm |
| runtime queue terminal state | removed paper task 标记 skipped/cancelled | 不计 failed，不 retry |
| scheduler embed | 支持但默认关闭 | 完整交易日 gate 通过后维护窗口执行 |

当前判断：

- D5 embedded scheduler 不是立即执行项。
- 如果 worker 仍在 `700MiB+ / 768MiB` 区间，保留独立 scheduler 更稳。
- scheduler 合并能省常驻内存，但前提是 worker 有余量。
- provider degraded guard 只能减少 fallback 爆发，不能代替完整交易日长稳 gate。

### 3.3 第三层：MySQL、机器规格和入口根因

目标：解决资源止血之外的真实根因。

| 根因 | 处理方式 | 授权要求 |
|---|---|---|
| MySQL 内存 | 继续观察 `1536m/2048m` 后是否 OOM | 只读观察；调参需授权 |
| 慢查询 | 抓慢 SQL、EXPLAIN、索引或查询优化 | 开发/DB 授权 |
| 连接池 | 观测 `Threads_*`、API p95、连接等待 | 配置授权 |
| 机器规格 | 完整交易日 available memory 仍 `<500MiB` 时升配 | 用户授权 |
| 域名 TLS/SNI | DNS/nginx/证书/CDN/WAF 分轨排查 | 独立授权 |
| Docker cache | 只清 build cache/dangling image，不动 volume | 维护窗口授权 |

## 4. 多 Agent 并行编排

### 4.1 总控顺序

遵循 `AGENTS.md` 默认顺序：

1. `trading-quant-lead`
2. `stock-analysis-specialist`
3. `product-strategist`
4. `ui-designer`
5. `fullstack-builder`
6. `qa-tester`
7. `devops-operator`

实际开发可以并行，但线上生效必须由 `trading-platform-supervisor` 串行门禁。

### 4.2 角色职责

| Agent | 职责 | 不可触碰 |
|---|---|---|
| `trading-platform-supervisor` | 阶段门禁、风险升级、授权点、合并各包结果 | 不绕过 D5 gate |
| `trading-quant-lead` | 策略语义、生产分、priority board 口径守卫 | 不新增策略规则 |
| `stock-analysis-specialist` | 市场复盘关闭影响审查，判断解释能力是否可按需 | 不把主观规则写入生产排序 |
| `product-strategist` | 非核心关闭项功能影响矩阵和恢复条件 | 不恢复 active paper |
| `ui-designer` | frontend-next 页面可用性、旧入口防回流、白屏/chunk 检查 | 不引入旧前端 |
| `fullstack-builder` | runtime queue、worker guard、provider degraded、dedupe、预算脚本 | 不改策略语义 |
| `qa-tester` | pytest、Playwright/curl、线上只读 smoke、完整交易日观察 | 不做线上写入压测 |
| `devops-operator` | runbook、compose/env 示例、deploy guard、只读线上验证、授权操作 | 未授权不改线上 |

### 4.3 七个并行开发包

| 包 | Owner | 可并行 | 主要输出 | 线上写 |
|---|---|---|---|---|
| P1 状态基线与门禁 | `trading-platform-supervisor`、`qa-tester` | 是 | 状态报告、D5 gate、未完成清单 | 否 |
| P2 非核心止血与模拟盘残留 | `fullstack-builder`、`product-strategist` | 是 | stop profile、removed paper skipped/cancelled、影响矩阵 | 需授权 |
| P3 runtime/provider/队列稳定性 | `fullstack-builder`、`qa-tester` | 是 | dedupe、provider degraded、worker recycle、测试 | 部署需授权 |
| P4 scheduler 合并候选 | `devops-operator`、`fullstack-builder` | 受 P3/P5/P7 约束 | embedded scheduler runbook、回滚命令 | 仅 D5 通过后 |
| P5 MySQL/机器规格根因 | `devops-operator`、`fullstack-builder` | 是 | 慢查询/连接/规格报告 | 调参需授权 |
| P6 旧前端最终收口 | `ui-designer`、`qa-tester` | 是 | 防回流测试、归档/删除门槛 | 删除需授权 |
| P7 前端/HTTP/长稳验收 | `qa-tester`、`ui-designer` | 是 | 页面 smoke、p95、完整交易日观察 | 否 |

### 4.4 依赖图

```text
P1 状态基线与门禁
  ├─ P2 非核心止血与模拟盘残留
  ├─ P3 runtime/provider/队列稳定性
  ├─ P5 MySQL/机器规格根因
  ├─ P6 旧前端最终收口
  └─ P7 前端/HTTP/长稳验收

P4 scheduler 合并候选
  └─ 只能在 P1/P3/P5/P7 均无 P0/P1 blocker，且完整交易日 D5 gate 通过后进入授权执行
```

### 4.5 串行上线门禁

1. Gate A：每批开始 `git status --short`，保护无关未提交文件。
2. Gate B：本地测试通过，策略守卫测试通过。
3. Gate C：线上只读基线显示核心服务可用。
4. Gate D：用户明确授权线上写动作。
5. Gate E：最小范围变更后 `/readyz`、核心 API、页面 smoke 通过。
6. Gate F：观察 2-4 小时无 OOM、swap 不持续升高、核心任务无积压。
7. Gate G：完整交易日 09:15-15:30 观察通过。
8. Gate H：`d5_gate.ready=true` 后才允许 D5 scheduler embed。
9. Gate I：MySQL/域名/机器规格进入独立授权专项。

## 5. 文件改动规划

### 5.1 文档与报告

| 文件 | 动作 | 责任 |
|---|---|---|
| `docs/operations/cloud-core-worker-resource-runbook.md` | 维护 | 止血、scheduler、回滚 |
| `docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md` | 维护 | D5 完整交易日观察 |
| `docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md` | 生成/维护 | 自动 gate 快照 |
| `docs/reports/mysql-runtime-root-cause-review-2026-06-12.md` | 维护 | MySQL 根因 |
| `docs/reports/provider-degraded-cooldown-market-regime-optimization-2026-06-12.md` | 维护 | provider 降级与 cooldown |
| `docs/reports/frontend-next-legacy-guard-final-2026-06-12.md` | 新增 | 旧前端最终 guard |
| `docs/reports/cloud-resource-contention-product-impact-2026-06-12.md` | 新增 | 功能影响矩阵 |
| `docs/reports/domain-entry-tls-reset-review-2026-06-12.md` | 新增 | 域名入口专项 |
| `docs/reports/frontend-next-core-pages-smoke-2026-06-12.md` | 新增 | 前端核心页面 smoke |

### 5.2 后端与脚本

| 文件 | 可改内容 |
|---|---|
| `backend/app/workers/runtime_worker.py` | removed paper task skipped、worker recycle guard |
| `backend/app/services/tasks/queue.py` | terminal status、summary、cancel/skipped 行为 |
| `backend/app/services/latest_data_close_refresh.py` | 同日成功任务 dedupe |
| `backend/app/services/market/regime.py` | provider degraded cooldown/backoff、cached/warming fallback |
| `backend/app/services/market/providers/router.py` | provider timeout/circuit-open 降级 |
| `backend/app/core/config.py` | 缺失 setting 声明，不能靠未声明 env |
| `backend/app/runtime/background_jobs.py` | scheduler/market review 门控 |
| `scripts/verify_platform_budget.py` | 预算和 D5 gate 检查 |
| `scripts/collect_cloud_resource_gate_observation.py` | 只读长稳采集 |
| `scripts/cloud_resource_gate_observation/collector.py` | collector 数据采集 |
| `scripts/cloud_resource_gate_observation/parsers.py` | sustained pressure 解析 |
| `scripts/summarize_cloud_resource_gate_observations.py` | 完整交易日汇总 |
| `scripts/deploy_cloud_server.sh` | explicit scheduler embed mode guard |
| `scripts/quick_cloud_deploy.sh` | frontend-next 和 scheduler embed 验证兼容 |

### 5.3 前端与旧入口

| 文件 | 可改内容 |
|---|---|
| `backend/app/main.py` | 保持 `frontend-next/dist` 和 `/__legacy/*` 退役 404 |
| `scripts/deploy_scope.py` | 阻断 `frontend-hot`、`frontend-legacy` |
| `deploy/frontend/Dockerfile` | 只构建 `frontend-next` |
| `Dockerfile` | 只复制 `frontend-next/dist` |
| `.github/workflows/ci.yml` | 只上传 `frontend-next/dist` artifact |
| `frontend-next/scripts/*` | 页面 smoke、trace、visual/perf 验证 |

### 5.4 不建议新增

- 不新增 `PAPER_RUNTIME_TASKS_ENABLED`。
- 不新增新的 active paper 页面。
- 不新增 Web 主进程后台 loop。
- 不新增大量微服务拆分。
- 不新增生产策略分数或排序字段。

## 6. 开发任务

### Task P1: 状态基线与门禁报告

**Owner:** `trading-platform-supervisor` + `qa-tester`

**Files:**

- Modify: `docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md`
- Modify: `docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md`

- [ ] **Step 1: 确认工作区**

```bash
cd /Users/j/Documents/gupiao
git status --short
```

Expected: 空输出，或记录并保护无关改动。

- [ ] **Step 2: 生成只读 gate 快照**

```bash
cd /Users/j/Documents/gupiao
python3 scripts/collect_cloud_resource_gate_observation.py \
  --ssh-host 43.143.243.97 \
  --ssh-user ubuntu \
  --ssh-key /Users/j/Downloads/gupiao.pem \
  --journal-since "2026-06-12 00:00:00" \
  --docker-logs-since 2h \
  --json-output docs/reports/cloud-resource-gate-observation-2026-06-12-latest.json \
  --markdown-output docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md
```

Expected: 只读；若 `d5_gate.ready=false`，不得执行 scheduler embed。

- [ ] **Step 3: 更新未完成项**

记录以下状态：

- 是否完整交易日观察完成。
- 是否仍有 scheduler provider warnings。
- MySQL 是否有新 OOM。
- worker RSS 是否稳定。
- runtime queue 是否有非核心积压。
- 本轮是否执行任何写操作。

- [ ] **Step 4: 提交**

```bash
git add docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md
git commit -m "docs: refresh cloud resource gate baseline"
```

Expected: 只提交 P1 报告文件。

### Task P2: 非核心止血与模拟盘残留

**Owner:** `fullstack-builder` + `product-strategist`

**Files:**

- Modify if needed: `backend/app/workers/runtime_worker.py`
- Modify if needed: `backend/app/services/tasks/queue.py`
- Test: `backend/tests/test_runtime_task_queue.py`
- Test: `backend/tests/test_phase4_runtime_worker_tasks.py`
- Create: `docs/reports/cloud-resource-contention-product-impact-2026-06-12.md`

- [ ] **Step 1: 锁定 active paper 不恢复**

```bash
cd /Users/j/Documents/gupiao
rg -n "paper|PAPER|/next/paper|/paper" backend frontend-next frontend scripts docs | head -200
```

Expected:

- `/next/paper` 不作为核心入口恢复。
- `paper_*` runtime task 是 removed-feature 残留处理对象。
- 不新增 `PAPER_RUNTIME_TASKS_ENABLED` 作为恢复开关。

- [ ] **Step 2: 测试 removed paper task 进入终态**

需要测试覆盖：

- `paper_` 前缀任务被 worker 识别为 removed feature。
- 状态为 `skipped` 或 `cancelled`，不进入 failed。
- 清空 active idempotency key。
- 不再 retry。
- 核心任务不受影响。

运行：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_phase4_runtime_worker_tasks.py \
  backend/tests/test_independent_runtime_components.py
```

Expected: PASS。

- [ ] **Step 3: 输出功能影响矩阵**

`docs/reports/cloud-resource-contention-product-impact-2026-06-12.md` 必须包含：

| 关闭项 | 用户可见影响 | 替代路径 | 恢复条件 | 是否核心 |
|---|---|---|---|---|
| autopilot | 自动巡检停止 | 人工 runbook | 资源稳定且授权 | 否 |
| market review | 自动午盘/收盘复盘停止 | 按需报告 | 资源稳定或低峰 | 否 |
| analytics/backtest/ML/factor/data repair | 常驻停止 | 本地或按需 worker | 授权窗口 | 否 |
| active paper | 不恢复 | 监控/策略追踪/回测 | 独立产品方案 | 否 |

- [ ] **Step 4: 提交**

```bash
git add backend/app/workers/runtime_worker.py backend/app/services/tasks/queue.py backend/tests/test_runtime_task_queue.py backend/tests/test_phase4_runtime_worker_tasks.py docs/reports/cloud-resource-contention-product-impact-2026-06-12.md
git commit -m "D2: stop non-core paper task residue"
```

Expected: 若某些文件未改，`git add` 时删除未改文件即可；不混入无关清理。

### Task P3: runtime/provider/队列稳定性

**Owner:** `fullstack-builder` + `qa-tester`

**Files:**

- Modify if needed: `backend/app/services/latest_data_close_refresh.py`
- Modify if needed: `backend/app/services/market/regime.py`
- Modify if needed: `backend/app/services/market/providers/router.py`
- Modify if needed: `backend/app/runtime/background_jobs.py`
- Modify if needed: `backend/app/core/config.py`
- Test: `backend/tests/test_latest_data_close_refresh.py`
- Test: `backend/tests/test_market_regime_strategy_p2.py`
- Test: `backend/tests/test_v4_remaining_contracts.py`
- Test: `backend/tests/test_market_quote_cache_refresh.py`

- [ ] **Step 1: 复跑稳定性测试**

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_latest_data_close_refresh.py \
  backend/tests/test_market_regime_strategy_p2.py \
  backend/tests/test_v4_remaining_contracts.py \
  backend/tests/test_market_quote_cache_refresh.py \
  backend/tests/test_platform_budget_verifier.py
```

Expected: PASS。

- [ ] **Step 2: 策略守卫测试**

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_low_buy_read_paths.py \
  backend/tests/test_low_buy_priority_board_strategy_variants.py \
  backend/tests/test_low_buy_production_scoring.py
```

Expected: PASS；不得改变生产分和 priority board 排序。

- [ ] **Step 3: 线上只读任务分布**

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97 "
cd /home/ubuntu/gupiao-upload &&
sudo docker exec tquant-mysql sh -lc 'mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -D \"\$MYSQL_DATABASE\" -e \"SELECT task_type,status,COUNT(*) cnt,MIN(created_at) oldest,MAX(updated_at) latest FROM runtime_tasks WHERE created_at >= NOW() - INTERVAL 2 HOUR GROUP BY task_type,status ORDER BY cnt DESC LIMIT 40;\"'
"
```

Expected:

- 同日成功的 A-key/strategy-tracking 不重复爆量。
- low-priority task 不被核心 worker claim。
- paper removed task 不污染 failed/retry。

- [ ] **Step 4: provider 降级原则**

如需要继续优化 `backend/app/services/market/regime.py`，必须满足：

- 慢源/坏源返回 cached/warming/stale，不伪装为 live。
- cooldown/backoff 只减少 provider fallback 压力，不改变策略排序。
- 成功 live provider 恢复后清理 degraded 状态。
- 测试覆盖 invalid setting fallback、backoff、success reset。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/latest_data_close_refresh.py backend/app/services/market/regime.py backend/app/services/market/providers/router.py backend/app/runtime/background_jobs.py backend/app/core/config.py backend/tests/test_latest_data_close_refresh.py backend/tests/test_market_regime_strategy_p2.py backend/tests/test_v4_remaining_contracts.py backend/tests/test_market_quote_cache_refresh.py docs/reports/provider-degraded-cooldown-market-regime-optimization-2026-06-12.md
git commit -m "D6: stabilize runtime provider and queue pressure"
```

Expected: 提交前删除未改文件；策略守卫测试已通过。

### Task P4: scheduler 合并候选与回滚

**Owner:** `devops-operator` + `fullstack-builder`

**Files:**

- Modify: `docs/operations/cloud-core-worker-resource-runbook.md`
- Modify if needed: `scripts/deploy_cloud_server.sh`
- Modify if needed: `scripts/quick_cloud_deploy.sh`
- Test: `backend/tests/test_cloud_deploy_scripts.py`
- Test: `backend/tests/test_independent_runtime_components.py`

- [ ] **Step 1: 验证 embedded scheduler 默认关闭**

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_cloud_deploy_scripts.py \
  backend/tests/test_independent_runtime_components.py
```

Expected:

- `RUNTIME_WORKER_EMBED_SCHEDULER=false` 为默认。
- deploy script 只有显式 mode 才允许 embed。
- 不出现 worker 和 standalone scheduler 同时跑同一调度的隐患。

- [ ] **Step 2: 写入 D5 执行前门槛**

Runbook 必须明确以下条件全部通过才可执行：

- 完整交易日观察已完成。
- worker RSS 峰值低于阈值，或 recycle guard 已证明稳定。
- MySQL 无新 OOM。
- swap 不持续上涨。
- provider warnings 不再高频。
- queue 无核心积压。
- 用户授权维护窗口。

- [ ] **Step 3: 只记录命令，不执行**

在 D5 未通过前，只记录 later-use 命令，不能执行：

```bash
cd /home/ubuntu/gupiao-upload
cp .env ".env.scheduler-embed-backup.$(date +%Y%m%d%H%M%S)"
# set RUNTIME_WORKER_EMBED_SCHEDULER=true and RUNTIME_SCHEDULER_BACKGROUND_JOBS_ENABLED=false
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate runtime-worker
sudo docker rm -f tquant-runtime-scheduler-mysql
```

Expected: 当前阶段不执行。

- [ ] **Step 4: 提交**

```bash
git add docs/operations/cloud-core-worker-resource-runbook.md scripts/deploy_cloud_server.sh scripts/quick_cloud_deploy.sh backend/tests/test_cloud_deploy_scripts.py backend/tests/test_independent_runtime_components.py
git commit -m "D5: document scheduler embed gate and rollback"
```

Expected: 只提交 runbook、脚本 guard 和测试。

### Task P5: MySQL/机器规格根因

**Owner:** `devops-operator` + `fullstack-builder`

**Files:**

- Create/Modify: `docs/reports/mysql-runtime-root-cause-review-2026-06-12.md`
- Modify only after approval: DB index migration or query files identified by EXPLAIN

- [ ] **Step 1: 只读 MySQL 诊断**

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97 "
cd /home/ubuntu/gupiao-upload &&
sudo docker exec tquant-mysql sh -lc 'mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -D \"\$MYSQL_DATABASE\" -e \"SHOW GLOBAL STATUS LIKE '\''Threads_%'\''; SHOW GLOBAL STATUS LIKE '\''Slow_queries'\''; SHOW VARIABLES LIKE '\''max_connections'\''; SHOW VARIABLES LIKE '\''innodb_buffer_pool_size'\''; SELECT table_schema, ROUND(SUM(data_length+index_length)/1024/1024,2) AS mb FROM information_schema.tables WHERE table_schema NOT IN ('\''mysql'\'','\''performance_schema'\'','\''information_schema'\'','\''sys'\'') GROUP BY table_schema;\"'
"
```

Expected: 只读，记录连接数、慢查询、buffer pool、表空间。

- [ ] **Step 2: 决策矩阵**

| 条件 | 下一步 |
|---|---|
| MySQL 仍 >90% memory 或有新 OOM | 优先升配或重新评估 MySQL limit/buffer pool |
| `Slow_queries` 增速高 | 抓慢 SQL、EXPLAIN、加索引或改查询 |
| `Threads_running` 长期高 | 查连接池和慢 API |
| API p95 高但资源稳定 | 查 BFF/priority board 查询路径 |
| 完整交易日 available memory 仍 `<500MiB` | 升级机器内存，不继续挤压核心服务 |

- [ ] **Step 3: 提交报告**

```bash
git add docs/reports/mysql-runtime-root-cause-review-2026-06-12.md
git commit -m "docs: refresh mysql runtime root cause review"
```

Expected: 若没有授权，不提交 schema/index/配置变更。

### Task P6: 旧前端最终收口

**Owner:** `ui-designer` + `qa-tester` + `devops-operator`

**Files:**

- Create: `docs/reports/frontend-next-legacy-guard-final-2026-06-12.md`
- Test: `backend/tests/test_frontend_next_level1_cutover.py`
- Test: `backend/tests/test_deploy_scope.py`
- Test: `backend/tests/test_cloud_deploy_scripts.py`

- [ ] **Step 1: 确认旧前端运行链路已退役**

```bash
cd /Users/j/Documents/gupiao
test -d frontend; printf "frontend_dir_exit=%s\n" "$?"
git ls-files frontend | wc -l
rg -n "frontend-hot|frontend-legacy|frontend/dist|html-root|__legacy" Dockerfile deploy scripts backend .github Makefile
```

Expected:

- 若 `frontend/` 不存在，记录为 absent。
- 若存在，只能作为 retired source / archive candidate，不能作为运行入口。
- `frontend-hot`、`frontend-legacy` 必须保持 blocked。
- `/__legacy/*` 不恢复静态资源。

- [ ] **Step 2: 复跑旧入口防回流测试**

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_frontend_next_level1_cutover.py \
  backend/tests/test_deploy_scope.py \
  backend/tests/test_cloud_deploy_scripts.py
```

Expected: PASS。

- [ ] **Step 3: 写清物理删除门槛**

删除 `frontend/` 必须单独批次，且满足：

- `frontend-next` 线上稳定观察 1-2 个交易日。
- native/mobile owner 确认不依赖 `frontend/android`、`frontend/ios`。
- 脚本引用复扫只剩历史文档、清理保护或删除说明。
- 创建可回滚 tag/branch 或归档包。
- 用户明确授权物理删除。

- [ ] **Step 4: 提交**

```bash
git add docs/reports/frontend-next-legacy-guard-final-2026-06-12.md backend/tests/test_frontend_next_level1_cutover.py backend/tests/test_deploy_scope.py backend/tests/test_cloud_deploy_scripts.py
git commit -m "docs: finalize frontend-next legacy guard"
```

Expected: 不物理删除 `frontend/`，除非单独授权。

### Task P7: 前端、HTTP、长稳验收

**Owner:** `qa-tester` + `ui-designer`

**Files:**

- Create: `docs/reports/frontend-next-core-pages-smoke-2026-06-12.md`
- Modify: `docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md`

- [ ] **Step 1: frontend-next 本地验收**

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
```

Expected: PASS，无 chunk 404、无旧前端回流。

- [ ] **Step 2: 线上页面只读 smoke**

```bash
BASE_URL=http://43.143.243.97:18090
for path in / /readyz /next/monitor /next/monitor/market /next/strategy-tracking /next/analysis /next/backtest /next/data /next/settings; do
  curl -sS -o /tmp/gupiao-smoke.out -w "$path %{http_code} %{time_total}\n" --max-time 20 "$BASE_URL$path"
done
```

Expected:

- 页面 200 或明确重定向。
- 受保护 API 未登录返回 401，不能 timeout/5xx。

- [ ] **Step 3: 完整交易日观察**

按北京时间记录：

| 时间 | 目的 |
|---|---|
| 09:15 | pre-open baseline |
| 09:35 | after open pressure |
| 10:30 | sustained morning load |
| 11:30 | midday close |
| 13:05 | afternoon reopen |
| 14:55 | close pressure |
| 15:10 | post-close tasks |
| 15:30 | close-refresh cooldown |

Expected:

- MySQL 无新 OOM。
- worker RSS 不持续贴边。
- swap 不持续上涨。
- provider warning 不高频。
- queue 无核心积压。
- 核心页面/API 可用。

- [ ] **Step 4: 汇总 gate**

```bash
cd /Users/j/Documents/gupiao
python3 scripts/summarize_cloud_resource_gate_observations.py \
  docs/reports/cloud-resource-gate-observations/2026-06-12-*.json \
  --json-output docs/reports/cloud-resource-trading-day-gate-summary-2026-06-12.json \
  --markdown-output docs/reports/cloud-resource-trading-day-gate-summary-2026-06-12.md \
  --fail-on-d5-blocked
```

Expected:

- 缺少任何 checkpoint 时 `d5_ready=false`。
- 任何 P0/P1 blocker 时 `d5_ready=false`。
- 只有完整交易日和全部指标通过后，才进入 D5 授权决策。

- [ ] **Step 5: 提交**

```bash
git add docs/reports/frontend-next-core-pages-smoke-2026-06-12.md docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md docs/reports/cloud-resource-trading-day-gate-summary-2026-06-12.md docs/reports/cloud-resource-trading-day-gate-summary-2026-06-12.json
git commit -m "docs: add frontend and trading day stability evidence"
```

Expected: 若 JSON 是生成产物，确认体积和引用后再提交。

## 7. 验收矩阵

| 验收项 | 必须通过 |
|---|---|
| Git | 每批开始前 `git status --short`；提交只包含本批文件 |
| 策略守卫 | `strategy_policy.py` 无修改；`production_score` 和 priority board 测试通过 |
| 核心 API | `/readyz` 200；受保护 API 401 快速返回；无 5xx/timeout |
| 核心页面 | `/next/monitor`、`/next/monitor/market`、`/next/strategy-tracking`、`/next/analysis`、`/next/backtest`、`/next/data`、`/next/settings` 可打开 |
| 资源 | MySQL 无 OOM；worker 不持续贴边；swap 不持续上涨 |
| 任务 | low-priority paused；核心任务完成；同日重复任务不爆量 |
| D5 gate | `collect_cloud_resource_gate_observation.py --full-trading-day-complete` 后 `d5_gate.ready=true` |
| 旧前端 | `frontend/` 不在运行链路；CI/Docker/deploy 不回流旧前端 |
| 模拟盘 | active paper 不恢复；历史 paper task skipped/cancelled，不 failed/retry |
| 长稳 | 完整交易日观察无 P0/P1 |
| 回滚 | 每个线上写动作都有 backup 和 rollback command |

## 8. 推荐测试命令

### 8.1 平台/runtime/deploy/gate

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_cloud_resource_gate_observation.py \
  backend/tests/test_platform_budget_verifier.py \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_cloud_deploy_scripts.py \
  backend/tests/test_independent_runtime_components.py
```

### 8.2 策略守卫

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_low_buy_read_paths.py \
  backend/tests/test_low_buy_priority_board_strategy_variants.py \
  backend/tests/test_low_buy_production_scoring.py
```

### 8.3 provider/runtime 稳定性

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_latest_data_close_refresh.py \
  backend/tests/test_market_regime_strategy_p2.py \
  backend/tests/test_v4_remaining_contracts.py \
  backend/tests/test_market_quote_cache_refresh.py
```

### 8.4 旧前端防回流

```bash
cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_frontend_next_level1_cutover.py \
  backend/tests/test_deploy_scope.py \
  backend/tests/test_cloud_deploy_scripts.py
```

### 8.5 frontend-next

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
```

### 8.6 最终检查

```bash
cd /Users/j/Documents/gupiao
git diff --check
git status --short
```

## 9. 分角色提示词

### 9.1 总控提示词

```text
你是 trading-platform-supervisor，在 /Users/j/Documents/gupiao 总控云服务器资源争抢卡顿治理、旧前端退役收口和模拟盘残留降噪。

目标：按 docs/superpowers/plans/2026-06-12-cloud-resource-contention-final-multi-agent-development-plan.md 推进 P1-P7。核心必须持续可用：监控、行情缓存、低吸榜、priority board、策略追踪、watchdog、app/mysql/redis/frontend-next/go-bff/go-market-read/go-scan/runtime-worker。

开始前：
1. 执行 cd /Users/j/Documents/gupiao && git status --short。
2. 阅读 AGENTS.md、docs/engineering-conventions.md、docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md。
3. 阅读本计划和第 0 节列出的权威输入。

硬边界：
- 不改 backend/app/services/low_buy/strategy_policy.py。
- 不改变生产策略语义、production_score、priority_board 排序和口径。
- 不停止 MySQL、Redis、Web/API、Go hot-read、Go scan、核心 runtime-worker。
- 不把云端改成 Web-only。
- 不恢复 active 模拟盘。
- 未获授权不得改线上 .env、不得重启/重建/停止容器、不得清理 Docker/磁盘、不得改 nginx/MySQL、不得写生产数据库。
- D5 embedded scheduler 不得在 d5_gate.ready=false 时执行。

执行方式：
- 本地开发可多 Agent 并行；线上生效必须串行。
- 每批输出：完成项、失败项、风险、证据、是否执行线上写操作、下一步授权清单。
- 每批结束前复核 git status，保护无关未提交文件。
```

### 9.2 devops-operator 提示词

```text
你是 devops-operator，只处理云端运维、runbook、部署脚本、compose/env 示例、线上只读验证和授权操作记录。

范围：
- docs/operations/cloud-core-worker-resource-runbook.md
- scripts/deploy_cloud_server.sh
- scripts/quick_cloud_deploy.sh
- scripts/verify_platform_budget.py
- docker-compose.mysql.yml
- .env.deploy.local.example、.env.docker.example
- docs/reports/*resource*、*domain*、*mysql*

目标：
1. 保证第一层非核心 stop profile 有清晰启停、验证、回滚步骤。
2. 保证 embedded scheduler 默认不启用，只能通过显式 flag 生效。
3. 输出 D5 完整交易日只读观察记录，未达 gate 不执行 scheduler embed。
4. 单独输出 MySQL 根因和域名 TLS/SNI reset 报告。

禁止：
- 未授权修改线上 .env、重启/停止/删除容器、清理 Docker、改 nginx、改 MySQL。
- 不停 MySQL/Redis/Web/Go/core runtime-worker。
- 不把云端改成 Web-only。

验证：
- bash -n scripts/deploy_cloud_server.sh scripts/quick_cloud_deploy.sh scripts/one_click_cloud_deploy.sh scripts/prod_preflight.sh
- PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_platform_budget_verifier.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_independent_runtime_components.py
```

### 9.3 fullstack-builder 提示词

```text
你是 fullstack-builder，只处理后端 runtime task、worker guard、scheduler embed 兼容、provider/BFF 降级、dedupe 和相关测试。

范围：
- backend/app/workers/runtime_worker.py
- backend/app/services/latest_data_close_refresh.py
- backend/app/services/market/regime.py
- backend/app/services/market/providers/router.py
- backend/app/services/tasks/queue.py
- backend/app/core/config.py
- backend/app/runtime/background_jobs.py
- backend/tests/test_runtime_task_queue.py
- backend/tests/test_phase4_runtime_worker_tasks.py
- backend/tests/test_latest_data_close_refresh.py
- backend/tests/test_market_regime_strategy_p2.py
- backend/tests/test_v4_remaining_contracts.py
- backend/tests/test_platform_budget_verifier.py

目标：
1. low-priority pause 对 analytics/backtest/ML/factor/data repair/research/paper auto 生效。
2. removed paper 历史任务进入 skipped/cancelled，不恢复 active 模拟盘。
3. worker recycle guard 只在任务完成后触发，不中断 running task。
4. close-refresh dedupe 防止同日成功任务重复入队。
5. scheduler embed 支持但默认关闭，不能重复跑 scheduler。
6. market regime provider degraded guard 使用 cached/warming/stale 降级，减少 provider fallback 链式压力。

禁止：
- 不改 backend/app/services/low_buy/strategy_policy.py。
- 不改变生产策略语义、production_score、priority_board 排序和口径。
- 不新增 active paper 功能。
- 不把 provider 降级结果伪装为 live freshness。

验证：
- PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_runtime_task_queue.py backend/tests/test_phase4_runtime_worker_tasks.py backend/tests/test_latest_data_close_refresh.py backend/tests/test_market_regime_strategy_p2.py backend/tests/test_v4_remaining_contracts.py backend/tests/test_platform_budget_verifier.py backend/tests/test_independent_runtime_components.py
- 如触碰 low-buy/priority-board/read path，额外跑 backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py
```

### 9.4 qa-tester 提示词

```text
你是 qa-tester，负责本方案的回归、线上只读 smoke、长稳观察和证据归档。

目标：
1. 建立 P1-P7 验收矩阵，区分 PASS/WARN/FAIL。
2. 验证核心服务：/readyz、核心 API、/next/monitor、/next/monitor/market、/next/strategy-tracking、/next/analysis、/next/backtest、/next/data、/next/settings。
3. 验证资源：uptime/load/free/swap/df/df -ih/docker ps/docker stats/docker system df。
4. 验证任务：runtime_tasks、scheduler heartbeat、worker heartbeat、low-priority pause、dedupe。
5. 验证前端：无白屏、无 chunk 404、无旧前端入口回流。
6. 验证 D5 gate：full trading day incomplete、sustained scheduler provider pressure、non-terminal core tasks、MySQL OOM、worker RSS 持续贴边任一成为 collector blocker 时必须保持 blocked；低频 provider warning 只记录为 WARN。

禁止：
- 不做线上写操作。
- 不执行破坏性压测。
- 不修改生产配置。

输出：
- docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md
- docs/reports/frontend-next-core-pages-smoke-2026-06-12.md
- 每条失败必须包含证据、影响、可能根因和建议下一步。
```

### 9.5 product-strategist 提示词

```text
你是 product-strategist，负责判断非核心功能关闭对用户体验和产品路径的影响。

目标：
1. 输出功能影响矩阵：autopilot、market review、analytics-worker、backtest-worker、ML/factor/data repair/research、active paper、Prometheus/Grafana。
2. 明确哪些是核心必须保留：监控、行情缓存、低吸榜、priority board、策略追踪、watchdog。
3. 明确哪些是按需能力：analytics、backtest、ML/factor、数据修复、研究任务、监控面板。
4. 明确模拟盘不恢复为核心功能，历史入口只做降噪和 skipped/cancelled。
5. 明确关闭项是否影响当前用户重心任务；若影响，必须提供替代路径或恢复条件。

禁止：
- 不提出恢复 active paper 作为核心路径。
- 不改变 priority board、production_score 或生产策略口径。

输出：
- docs/reports/cloud-resource-contention-product-impact-2026-06-12.md
```

### 9.6 ui-designer 提示词

```text
你是 ui-designer，负责 frontend-next 页面可用性、旧前端防回流和视觉/交互 smoke。

范围：
- frontend-next
- backend/app/main.py 旧入口行为
- deploy/frontend/Dockerfile
- Dockerfile
- .github/workflows/ci.yml
- scripts/deploy_scope.py
- docs/reports/frontend-next-legacy-guard-final-2026-06-12.md
- docs/reports/frontend-next-core-pages-smoke-2026-06-12.md

目标：
1. 验证核心页面可打开：/next/monitor、/next/monitor/market、/next/strategy-tracking、/next/analysis、/next/backtest、/next/data、/next/settings。
2. 检查无白屏、无 chunk 404、无动态 import 失败、无旧前端资源回流。
3. 保持 CI/Docker/deploy/backend 静态入口只指向 frontend-next。
4. 输出旧前端物理删除门槛：稳定观察、native owner review、引用复扫、归档、用户授权。

禁止：
- 不恢复 frontend/ 为运行入口。
- 不恢复 /__legacy/* 静态资源。
- 不恢复 /paper 或 /next/paper 为核心路径。
- 不进行与资源治理无关的 UI 重设计。

验证：
- cd frontend-next && npm run api:check && npm run typecheck && npm run lint && npm test -- --run && npm run build
- PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_frontend_next_level1_cutover.py backend/tests/test_deploy_scope.py backend/tests/test_cloud_deploy_scripts.py
```

### 9.7 trading-quant-lead 提示词

```text
你是 trading-quant-lead，负责确认本方案不会改变生产策略语义、production_score 和 priority board 排序口径。

范围：
- backend/app/services/low_buy/strategy_policy.py 只读，不可修改
- backend/tests/test_low_buy_read_paths.py
- backend/tests/test_low_buy_priority_board_strategy_variants.py
- backend/tests/test_low_buy_production_scoring.py
- docs/reports/cloud-resource-contention-product-impact-2026-06-12.md

目标：
1. 确认资源治理只影响任务调度、非核心能力、provider 降级和观测，不改策略公式。
2. 确认 cached/warming/stale 只影响数据新鲜度标记，不伪造生产分。
3. 确认 priority board 排序、production_score、生产候选门控不变。
4. 若任何实现触碰生产策略语义，立即标记 P0 并停止合并。

验证：
- git diff -- backend/app/services/low_buy/strategy_policy.py 必须为空。
- PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py
```

### 9.8 stock-analysis-specialist 提示词

```text
你是 stock-analysis-specialist，负责判断关闭 market review、autopilot、研究任务后，是否影响 A 股市场阅读和选股解释链路。

目标：
1. 区分核心行情/低吸榜/priority board 与非核心午盘/收盘自动复盘。
2. 说明 MARKET_REVIEW_ENABLED=false 后用户失去的是自动复盘报告，不是监控、行情缓存、低吸榜、策略追踪。
3. 若需要保留市场解释能力，提出按需运行或低峰运行方案，不要求云端常驻。
4. 不新增主观规则进入生产排序，不改变 production_score。

输出：
- 在 docs/reports/cloud-resource-contention-product-impact-2026-06-12.md 增加市场复盘影响说明。
```

## 10. 最终主提示词

```text
你在 /Users/j/Documents/gupiao 工作。目标：按照 docs/superpowers/plans/2026-06-12-cloud-resource-contention-final-multi-agent-development-plan.md 完成线上资源争抢治理、旧前端退役收口、模拟盘残留降噪和长稳验收。允许多 Agent 并行开发，但线上生效必须串行门禁。

开始前：
1. 执行 cd /Users/j/Documents/gupiao && git status --short，保护本地未提交文件。
2. 阅读 AGENTS.md、docs/engineering-conventions.md、docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md。
3. 阅读本计划第 0 节列出的权威输入，不要凭记忆猜测线上连接、compose、部署脚本、health endpoint。

最终方案：
第一层先停非核心任务止血：autopilot、market review、analytics/backtest/ML/factor/data repair/research、active paper、Prometheus/Grafana、startup prewarm 默认关闭或按需运行。
第二层收敛调度结构：dedupe、worker recycle guard、provider degraded guard、runtime queue terminal state；scheduler embed 只在完整交易日 D5 gate 通过后执行。
第三层处理根因：MySQL 慢查询/连接池/索引/规格、域名 TLS/SNI、Docker cache、机器升配，每项单独授权。

核心必须持续可用：
- 监控、行情缓存、低吸榜、priority board、策略追踪、watchdog。
- app、mysql、redis、frontend-next、go-bff、go-market-read、go-scan、runtime-worker。

硬边界：
- 不改 backend/app/services/low_buy/strategy_policy.py。
- 不改变生产策略语义、production_score、priority_board 排序和口径。
- 不把云端改成 Web-only。
- 不恢复 active 模拟盘。
- 不停止 MySQL、Redis、Web/API、Go hot-read、Go scan、核心 runtime-worker。
- 未获授权不得改线上 .env、不得重启/重建/停止容器、不得清理 Docker/磁盘、不得改 nginx/MySQL、不得写生产数据库。
- d5_gate.ready=false 时不得执行 embedded scheduler，不得停 runtime-scheduler。

任务拆分：
P1 状态基线与门禁报告。
P2 非核心止血与模拟盘残留。
P3 runtime/provider/队列稳定性。
P4 scheduler 合并候选与回滚。
P5 MySQL/机器规格根因。
P6 旧前端最终收口。
P7 前端、HTTP、长稳验收。

每个包要求：
- 一包一提交。
- 先写或复跑相关测试，再改实现或报告。
- 每批结束执行 git diff --check 和 git status --short。
- 输出完成项、失败项、证据、风险、是否执行线上写操作、下一步授权清单。

必须跑的守卫：
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_cloud_resource_gate_observation.py backend/tests/test_platform_budget_verifier.py backend/tests/test_runtime_task_queue.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_independent_runtime_components.py
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py

最终输出：
1. 每个 P 包的提交 hash 或未提交原因。
2. 测试命令和结果。
3. 核心功能是否受影响。
4. 当前线上是否可用。
5. 是否还有 P0/P1。
6. D5 是否允许执行。
7. 需要用户授权的下一步清单。
```

## 11. 完成定义

本计划只有在以下全部满足后才算完成：

- P1-P7 均有明确 PASS/WARN/FAIL 结果。
- 所有本地测试和策略守卫通过，或失败有明确 blocker 和证据。
- 核心服务和核心页面可用。
- active paper 未恢复，历史 paper task 不再 failed/retry storm。
- 旧前端不在运行链路，防回流测试通过。
- 完整交易日 gate 明确给出 D5 是否可执行。
- 所有线上写操作都有授权、备份、回滚和验收记录。
- 未授权项只记录建议命令，不执行。
