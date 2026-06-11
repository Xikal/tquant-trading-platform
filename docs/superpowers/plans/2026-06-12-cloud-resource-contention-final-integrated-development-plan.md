# Cloud Resource Contention Final Integrated Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 分三层治理线上资源争抢导致的卡顿，并把旧前端退役与已移除模拟盘残留收口纳入同一执行路径，保证监控、行情缓存、低吸榜、priority board、策略追踪持续可用。

**Architecture:** 第一层先停非核心常驻任务止血，第二层合并或收敛调度结构并减少重复任务，第三层处理 MySQL、worker 内存、慢查询、机器规格和域名入口根因。云端保持模块化单体和核心 Worker 小闭环，不改生产策略语义，不把云端改成 Web-only。

**Tech Stack:** Docker Compose, FastAPI, MySQL 8.4, Redis 7, Python runtime worker, Go hot-read services, frontend-next, pytest, Playwright, curl, SSH runbook.

---

## 1. 当前事实基线

### 1.1 已确认问题

| 问题 | 当前证据 | 判断 |
|---|---|---|
| 云服务器资源争抢 | MySQL 曾 cgroup OOM；runtime-worker 多次贴近 `768MiB` 上限；swap 曾高位 | 主要卡顿根因 |
| 非核心任务占用 Worker | autopilot、analytics/backtest/data repair/research 类任务会进入队列或留下历史失败 | 可先止血 |
| scheduler 常驻开销 | 独立 `runtime-scheduler` 常驻约数百 MiB，并有 provider timeout/circuit-open 日志 | 可合并但不能立即强切 |
| 重复物化任务 | `a_key_level_materialization_refresh`、`strategy_tracking_snapshot_refresh` 曾同日重复大量入队 | 已有 dedupe 修复，需持续验收 |
| MySQL 旧限制过紧 | `1GiB` 限制下发生 OOM；后续提高到 `1536m/2048m` 后短窗稳定 | 根因仍需慢查询/规格专项 |
| 域名公网链路不稳 | `weisilianghua.cloud` 曾外部 TLS reset；IP HTTPS 可用 | 独立网络入口问题 |
| 旧前端 | 当前仓库 `frontend/` 目录 absent，tracked 文件数为 0；运行、CI、Docker 主链路指向 `frontend-next/` | 旧前端物理退役已基本完成，剩余是 guard 和历史引用收口 |
| 模拟盘 | active `/paper`、`/next/paper` 不再作为核心功能；历史 `paper_*` runtime task 已按 removed feature skipped | 不恢复，不作为核心保护项 |
| D5 gate | `2026-06-12 02:29 CST` collector: `d5_gate.ready=false`，blockers 为 full trading day incomplete、scheduler provider warnings、runtime non-terminal task count | 继续观察，不执行 scheduler embed |

### 1.1.1 最新线上快照

来源：`docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md`，生成时间 `2026-06-12 02:29 CST`。

| 项 | 最新值 | 判断 |
|---|---:|---|
| Host load | `0.54 / 0.73 / 0.65` | 当前不高 |
| Memory available | `1392MiB` | 已明显缓解 |
| Swap used | `33.47%` | 仍需观察，接近警戒线 |
| Root disk / inode | `62% / 13%` | 非当前瓶颈 |
| `runtime-worker` | `294.8MiB / 768MiB` | 当前有余量 |
| `runtime-scheduler` | `261.1MiB / 640MiB` | 常驻成本仍存在 |
| MySQL | `849.3MiB / 1.5GiB` | 当前稳定，但慢查询累计 `48` |
| `/readyz` | `200`, `0.006410s` | 可用 |
| `/next/*` 核心页面 | `/next/monitor`、`/next/monitor/market`、`/next/strategy-tracking`、`/next/analysis`、`/next/backtest`、`/next/data`、`/next/settings` 均 `200` | 页面壳可用 |
| D5 readiness | `false` | 不允许停独立 scheduler |

### 1.2 已完成事项

| 批次 | 状态 | 说明 |
|---|---|---|
| D0 资源基线 | 已完成 | `docs/reports/cloud-resource-contention-remediation-2026-06-11.md` |
| D1 非核心 stop profile 文档/Runbook | 已完成 | `docs/operations/cloud-core-worker-resource-runbook.md` |
| D2 budget verifier 守卫 | 已完成 | 包含 low-priority、scheduler embed、worker recycle env 检查 |
| D3 embedded scheduler deploy mode | 已完成 | 默认不启用，显式 flag 才允许 |
| D4 线上非核心止血 | 已执行 | `.env` 启用 non-core stop flags，保留核心服务 |
| D6 MySQL 资源上限止血 | 已执行 | `MYSQL_MEM_LIMIT=1536m`、`MYSQL_MEMSWAP_LIMIT=2048m` |
| D6 close-refresh dedupe | 已开发并最小部署到 scheduler | 阻止同日成功任务重复入队 |
| D6 worker recycle guard | 已开发 | 目标是任务边界回收高 RSS worker，需持续观察和确认线上启用状态 |
| D6 provider degraded guard | 已开发并 scheduler-only 发布 | 减少 provider fallback 链式压力；仍有 residual board-breadth warning，D5 未通过 |
| 旧前端删除/退役 | 已执行 | `frontend/` absent；CI/Docker/deploy 指向 `frontend-next` |
| removed paper task skipped | 已执行 | 历史 paper runtime task 不再污染 failed/retry |

### 1.3 仍未完成

| 优先级 | 未完成项 | 为什么还要做 |
|---|---|---|
| P1 | 完整交易日稳定性观察 | 当前多为短窗，不能证明 09:15-15:10 长时间稳定 |
| P1 | D5 scheduler 合并门槛复核 | worker RSS 仍曾达到 `92-98%`，立即合并会把 scheduler 压力转移进 worker |
| P1 | MySQL 慢查询、连接池、索引和机器规格根因 | 提高 limit 只是止血，不代表慢查询/规格已解决 |
| P1 | 域名 TLS/SNI reset 独立处理 | 资源方案不能解决公网链路 reset |
| P2 | provider timeout、fallback、缓存命中治理 | 已做 market regime degraded guard，但 scheduler 仍有 board-breadth provider warning |
| P2 | 历史 failed runtime_tasks 降噪 | 不影响核心功能，但影响运维判断；需要 DB 写授权 |
| P2 | 旧前端 guard 收尾 | 继续防止 `frontend-hot`、`frontend-legacy`、`/__legacy/*` 回流 |
| P3 | analytics/backtest/ML/factor 按需运行手册 | 非核心能力可用但不常驻，需要清楚的人工启动和回滚路径 |

## 2. 硬边界

### 2.1 绝对禁止

- 不改 `backend/app/services/low_buy/strategy_policy.py`。
- 不改变生产策略语义。
- 不改变 `production_score`。
- 不改变 `priority_board` 排序和口径。
- 不把 research/shadow/paper 历史口径绕过门控接入生产排序。
- 不停止 MySQL、Redis、Web/API、Go hot-read、Go scan、核心 runtime-worker。
- 不把云端改成 Web-only。
- 不恢复 active 模拟盘功能，不恢复 `/paper` 或 `/next/paper` 作为核心路径。
- 不直接删除生产数据库表、binlog、volume 或核心缓存。

### 2.2 必须单独授权的线上动作

- 修改线上 `.env`。
- 重建、重启、停止、删除线上容器。
- 停独立 `runtime-scheduler`。
- Docker image/build cache 清理。
- MySQL 配置调参、索引、schema 或数据写入。
- 归档/标记历史 runtime task。
- nginx reload、域名、证书、CDN/WAF、安全组调整。
- 升级云服务器规格。

### 2.3 当前核心保护范围

| 核心能力 | 必须保持 |
|---|---|
| 监控 | `/next/monitor`、`/next/monitor/market`、monitor snapshot、BFF workspace |
| 行情缓存 | quote cache、market pulse、Go market-read |
| 低吸榜/推荐榜 | low-buy materialization、推荐榜数据 |
| priority board | 排序、日期、口径、production score 不变 |
| 策略追踪 | strategy tracking snapshot、页面和 BFF 数据 |
| watchdog | latest data watchdog、数据新鲜度检查 |
| 基础服务 | app、mysql、redis、frontend-next、go-bff、go-scan、runtime-worker |

## 3. 三层最终方案

### 3.1 第一层：停非核心任务止血

目标：快速解除“云服务器资源争抢导致卡顿”这一大类问题，保持核心交易观察链路在线。

| 项 | 目标状态 | 功能影响 | 是否核心 |
|---|---|---|---|
| `PLATFORM_AUTOPILOT_ENABLED` | `false` | 自动巡检/自愈建议停止 | 否 |
| `RUNTIME_LOW_PRIORITY_TASKS_PAUSED` | `true` | analytics/backtest/ML/factor/data repair/research 不抢 worker | 否 |
| `MARKET_REVIEW_ENABLED` | `false` 或降频 | 午盘/收盘自动复盘停止 | 否 |
| startup prewarm | disabled | 部署后不做重预热 | 否 |
| `analytics-worker` | on-demand profile | DuckDB/Parquet/分析导出需手动拉起 | 否 |
| `backtest-worker` | 不常驻 | 24M/批量回测不在云端常驻跑 | 否 |
| Prometheus/Grafana | 不常驻 | 独立监控面板按需恢复 | 否 |
| active paper | 不恢复 | 模拟盘主动交易/自动任务停止 | 否 |

第一层能解决或明显改善：

- 内存长期吃紧。
- swap 高。
- worker、扫描、刷新、回测和 Web 抢 CPU/IO。
- 页面/API 在数据刷新或策略物化时变慢。
- runtime 低优先级任务挤占核心任务。
- 部署后容器资源恢复慢。

第一层不能解决：

- 域名公网 reset。
- MySQL 慢查询和索引不足。
- priority board / monitor BFF 查询过重。
- 外部行情源网络不稳。
- 本地机器断网导致本地重任务不跑。

### 3.2 第二层：合并调度结构和减少重复任务

目标：让云端保持一个“小而稳”的核心 runtime，减少常驻进程和重复入队。

| 子项 | 目标 | 门槛 |
|---|---|---|
| close-refresh dedupe | 同一 trade date 成功后不重复入队 A-key/strategy-tracking | 已部署后继续观察 |
| worker recycle guard | worker RSS 超阈值后在任务边界正常退出重启 | 先确认线上 env 和日志，阈值建议 `700MiB` 起 |
| scheduler embed | `runtime-worker` 承接 scheduler，停独立 scheduler | 仅在完整交易日稳定且 worker RSS 有足够余量后执行 |
| provider timeout/fallback | 慢源进入 degraded/stale，不拖垮热路径 | BFF 和 provider 测试覆盖 |
| runtime task 互斥 | 核心 materialization 同类任务不重复并发 | 不能影响数据新鲜度 |

当前判断：

- D5 embedded scheduler 不是立即执行项。
- 若 worker 仍在 `700MiB+ / 768MiB` 区间，保留独立 scheduler 更稳，因为它隔离了 provider/scheduler 压力。
- scheduler 合并能省常驻内存，但前提是 worker 有余量，否则会把两个风险合并到一个进程。
- provider degraded guard 只能减少 fallback 爆发，不能代替完整交易日长稳 gate。

### 3.3 第三层：处理 MySQL、机器规格和入口根因

目标：从根上减少 OOM、慢接口、连接抖动和公网不可达。

| 根因项 | 处理方式 | 授权级别 |
|---|---|---|
| MySQL 内存上限 | 保持 `1536m/2048m` 止血配置，继续观察是否仍 OOM | 已部分执行，继续只读观察 |
| buffer pool/连接池 | 根据 `Threads_*`、`Slow_queries`、p95 决定是否调整 | 需要授权 |
| 慢查询/索引 | 抓慢 SQL、EXPLAIN、加索引或改查询 | schema/query 改动需开发与部署授权 |
| VM 规格 | 若核心服务稳定后 available memory 仍长期 `<500MiB`，优先升级内存 | 需要用户授权和维护窗口 |
| 域名 TLS/SNI reset | DNS、nginx server block、证书、安全组、CDN/WAF 分轨排查 | 需要授权 |
| Docker cache/image | 受控 prune，只清 build cache/dangling image，不动 volume | 需要授权 |

## 4. 多 Agent 并行开发编排

### 4.1 执行顺序

遵循 `AGENTS.md` 默认顺序：

1. `trading-quant-lead`
2. `stock-analysis-specialist`
3. `product-strategist`
4. `ui-designer`
5. `fullstack-builder`
6. `qa-tester`
7. `devops-operator`

### 4.2 并行分工

| Agent | 可并行任务 | 交付物 | 不可触碰 |
|---|---|---|---|
| `trading-quant-lead` | 策略语义守卫审查 | 确认 `strategy_policy.py`、`production_score`、priority board 口径未变 | 不新增策略规则 |
| `stock-analysis-specialist` | 市场复盘关闭影响审查 | 确认关闭 `MARKET_REVIEW_ENABLED` 不影响核心选股解释 | 不把主观规则写入生产排序 |
| `product-strategist` | 功能影响矩阵 | 非核心关闭项对页面/用户功能的影响说明 | 不恢复 paper |
| `ui-designer` | frontend-next 可用性与旧入口检查 | 页面 smoke、白屏/chunk/堆叠报告 | 不引入旧前端 |
| `fullstack-builder` | worker guard、dedupe、provider fallback、verifier、测试 | 后端实现和 pytest | 不改策略语义 |
| `qa-tester` | HTTP/API/p95/交易日稳定性验收 | 验收报告和失败证据 | 不执行线上写入压测 |
| `devops-operator` | runbook、deploy flag、compose/env、线上只读/授权操作 | 运维步骤、回滚命令、线上验证 | 未授权不改线上 |

### 4.3 串行门禁

本地开发可并行，线上生效必须串行：

1. Gate A：`git status --short` 干净或已记录无关改动。
2. Gate B：本地测试通过，策略守卫测试通过。
3. Gate C：只读线上基线通过，核心服务可用。
4. Gate D：用户授权线上写动作。
5. Gate E：变更后 `/readyz`、核心 API、页面 smoke 通过。
6. Gate F：观察 2-4 小时无 OOM、swap 不持续升高。
7. Gate G：完整交易日 09:15-15:10 观察通过。
8. Gate H：才允许 D5 scheduler embed。
9. Gate I：MySQL/机器规格/域名进入独立授权专项。

## 5. 文件改动规划

### 5.1 已有文件继续维护

| 文件 | 责任 |
|---|---|
| `docs/operations/cloud-core-worker-resource-runbook.md` | 资源止血、worker recycle、scheduler embed、回滚命令 |
| `docs/reports/cloud-resource-contention-remediation-2026-06-11.md` | 已执行止血、D6、D5 gate 证据 |
| `scripts/verify_platform_budget.py` | 资源 profile、worker/scheduler/env 预算检查 |
| `scripts/collect_cloud_resource_gate_observation.py` / `scripts/cloud_resource_gate_observation/` | D5 交易日只读观察采集与 scheduler embed gate 判断 |
| `scripts/deploy_cloud_server.sh` | 显式 embedded scheduler deploy mode |
| `scripts/quick_cloud_deploy.sh` | embedded scheduler 验证兼容 |
| `backend/app/workers/runtime_worker.py` | removed paper task skipped、worker recycle guard |
| `backend/app/services/latest_data_close_refresh.py` | 成功任务 dedupe |
| `backend/app/services/market/regime.py` | market regime provider degraded cooldown、inflight probe guard、cached/warming fallback |
| `backend/app/services/market/providers/router.py` | all-provider circuit-open 快照判断 |
| `backend/app/services/tasks/queue.py` | skipped 终态和低优先级暂停 |
| `docker-compose.mysql.yml` | worker/scheduler env、低优先级任务类型、按需 analytics profile |

### 5.2 建议新增文件

| 文件 | 责任 |
|---|---|
| `docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md` | 完整交易日稳定性观察，正文记录实际观察日期 |
| `docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md` | 自动采集的一次只读 D5 gate 快照 |
| `docs/reports/mysql-runtime-root-cause-review-2026-06-12.md` | MySQL 慢查询、连接池、规格根因 |
| `docs/reports/provider-degraded-cooldown-market-regime-optimization-2026-06-12.md` | D6 provider degraded guard 设计、验证和上线记录 |
| `docs/reports/domain-entry-tls-reset-review-2026-06-12.md` | 域名公网 reset 独立排查 |
| `docs/reports/frontend-next-legacy-guard-final-2026-06-12.md` | 旧前端 guard 最终验收 |

### 5.3 不建议新增

- 不新增 `PAPER_RUNTIME_TASKS_ENABLED`。
- 不新增新的 active paper 页面。
- 不新增 Web 主进程后台 loop。
- 不新增大量微服务拆分。
- 不新增生产策略分数或排序字段。

## 6. 开发任务清单

### 6.0 并行批次与合并顺序

| 批次 | 可并行 Agent | 主要产出 | 合并门槛 | 是否允许线上写 |
|---|---|---|---|---|
| Batch 1: 状态收口 | `trading-platform-supervisor`、`qa-tester`、`devops-operator` | 当前状态报告、D5 gate 快照、未完成清单 | docs-only 或只读报告通过复核 | 否 |
| Batch 2: 策略/产品边界审查 | `trading-quant-lead`、`stock-analysis-specialist`、`product-strategist` | 策略守卫、市场复盘关闭影响、功能影响矩阵 | 明确不影响核心任务和生产口径 | 否 |
| Batch 3: 后端稳定性守卫 | `fullstack-builder`、`qa-tester` | provider degraded guard、dedupe、runtime queue、worker recycle 测试 | pytest 通过，低吸/priority-board 守卫通过 | 本地代码可改；线上需授权 |
| Batch 4: 前端/旧入口 guard | `ui-designer`、`qa-tester`、`devops-operator` | frontend-next smoke、legacy scope 阻断、CI/Docker guard | frontend-next build/test 与旧入口 guard 测试通过 | 否 |
| Batch 5: 完整交易日观察 | `qa-tester`、`devops-operator` | 09:15-15:30 资源/API/任务观测 | `d5_gate.ready=true` 且无 P0/P1 | 否 |
| Batch 6: D5 scheduler embed 候选 | `devops-operator`、`fullstack-builder`、`trading-platform-supervisor` | 维护窗口执行/回滚方案 | 用户明确授权 + Batch 5 通过 | 是，最小范围 |
| Batch 7: MySQL/机器规格/域名专项 | `devops-operator`、`fullstack-builder`、`qa-tester` | 慢查询、规格、TLS/SNI 根因处理 | 每项单独方案和授权 | 是，逐项授权 |

合并顺序：

1. Batch 1 和 Batch 2 可并行启动，先合并 docs/report。
2. Batch 3 和 Batch 4 可并行开发，但必须各自测试全绿后再进入 Batch 5。
3. Batch 5 必须覆盖完整交易日，不得用短窗替代。
4. Batch 6 只有在 Batch 5 通过后才允许进入维护窗口。
5. Batch 7 不阻塞 Batch 1-5，但任何 MySQL/域名/规格写动作都必须单独授权。

### Task A: 统一当前事实和状态报告

**Owner:** `trading-platform-supervisor`

**Files:**

- Modify: `docs/reports/cloud-resource-contention-remediation-2026-06-11.md`
- Create: `docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md`

- [ ] **Step 1: 确认工作区**

```bash
cd /Users/j/Documents/gupiao
git status --short
```

Expected:

- 空输出，或记录并保护无关改动。

- [ ] **Step 2: 汇总已完成和未完成状态**

```bash
rg -n "D4|D5|D6|worker recycle|scheduler|MySQL|OOM|frontend|paper" \
  docs/reports/cloud-resource-contention-remediation-2026-06-11.md \
  docs/reports/online-stability-remaining-7-items-final-2026-06-11.md \
  docs/reports/online-stability-legacy-frontend-retirement-implementation-2026-06-11.md
```

Expected:

- 明确 D5 未执行或未通过 gate。
- 明确旧前端 `frontend/` 当前 absent。
- 明确模拟盘不恢复。
- 明确 D6 provider degraded guard 已降低 fallback 链式压力，但 residual provider warning 仍阻塞 D5。

- [ ] **Step 3: 提交状态报告**

```bash
git add docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md
git commit -m "docs: add trading day resource observation plan"
```

Expected:

- docs-only commit。

### Task B: 第一层非核心 stop profile 验收

**Owner:** `devops-operator` + `qa-tester`

**Files:**

- Modify: `docs/operations/cloud-core-worker-resource-runbook.md`
- Test: `backend/tests/test_platform_budget_verifier.py`
- Test: `backend/tests/test_cloud_deploy_scripts.py`

- [ ] **Step 1: 本地 verifier 验证**

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_platform_budget_verifier.py \
  backend/tests/test_cloud_deploy_scripts.py
```

Expected:

- PASS。
- Verifier 能识别 low-priority pause、worker recycle、scheduler embed 状态。

- [ ] **Step 2: 线上只读确认 stop profile**

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
set -e
cd /home/ubuntu/gupiao-upload
sudo docker exec tquant-runtime-worker-mysql env | sort | egrep "PLATFORM_AUTOPILOT_ENABLED|RUNTIME_LOW_PRIORITY_TASKS_PAUSED|RUNTIME_WORKER_EMBED_SCHEDULER|RUNTIME_WORKER_RECYCLE_RSS_MB" || true
sudo docker exec tquant-runtime-scheduler-mysql env | sort | egrep "MARKET_REVIEW_ENABLED|RUNTIME_LOW_PRIORITY_TASKS_PAUSED|RUNTIME_WORKER_EMBED_SCHEDULER" || true
sudo docker stats --no-stream --format "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | sort
curl -sS -o /tmp/readyz.json -w "readyz %{http_code} %{time_total}\n" --max-time 10 http://127.0.0.1:18090/readyz
'
```

Expected:

- 只读。
- `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true`。
- `PLATFORM_AUTOPILOT_ENABLED=false`。
- 核心服务 healthy。

### Task C: 第二层 worker/scheduler 稳定性门禁

**Owner:** `fullstack-builder` + `devops-operator`

**Files:**

- Modify: `docs/operations/cloud-core-worker-resource-runbook.md`
- Modify: `scripts/verify_platform_budget.py`
- Test: `backend/tests/test_phase4_runtime_worker_tasks.py`
- Test: `backend/tests/test_independent_runtime_components.py`
- Test: `backend/tests/test_cloud_resource_gate_observation.py`

- [ ] **Step 1: 确认 worker recycle guard 默认关闭和可启用**

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_phase4_runtime_worker_tasks.py::test_runtime_worker_recycle_guard_defaults_off \
  backend/tests/test_phase4_runtime_worker_tasks.py::test_runtime_worker_recycle_guard_triggers_after_task \
  backend/tests/test_independent_runtime_components.py
```

Expected:

- PASS。
- Guard 只在任务完成后触发，不中断 running task。

- [ ] **Step 2: 线上只读观察 worker RSS**

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
set -e
date
free -m
cd /home/ubuntu/gupiao-upload
sudo docker stats --no-stream --format "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | egrep "runtime-worker|runtime-scheduler|mysql|app"
sudo docker logs --since 2h tquant-runtime-worker-mysql 2>&1 | egrep -i "recycle|rss|oom|killed|error" | tail -80 || true
'
```

Expected:

- 如果 worker RSS 长期高于 `700MiB`，不得执行 scheduler embed。
- 如果 recycle guard 已线上启用，检查是否在任务边界正常重启且任务不失败。

- [ ] **Step 3: 自动采集 D5 gate 快照**

```bash
python3 scripts/collect_cloud_resource_gate_observation.py \
  --ssh-host 43.143.243.97 \
  --ssh-user ubuntu \
  --ssh-key /Users/j/Downloads/gupiao.pem \
  --journal-since "2026-06-12 00:00:00" \
  --docker-logs-since 2h \
  --json-output docs/reports/cloud-resource-gate-observation-2026-06-12-latest.json \
  --markdown-output docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md
```

Expected:

- 只读。
- 输出 `d5_gate.ready=false` 时不得执行 scheduler embed。
- 输出 `d5_gate.ready=true` 也只代表技术门槛通过，仍需维护窗口确认。
- 报告必须列出本轮未执行 `.env` 修改、Docker restart/remove、DB write、nginx/systemd change、cleanup、deploy/cutover。

- [ ] **Step 4: D5 scheduler embed 执行前门槛**

必须同时满足：

- worker 连续完整交易日 RSS 峰值低于 `650MiB`，或 recycle guard 已证明能稳定释放 RSS。
- MySQL 无新 OOM。
- swap 不持续上涨。
- close-refresh dedupe 后同日 A-key/strategy-tracking 不重复入队。
- scheduler/provider timeout 不再高频。
- 用户明确授权停独立 scheduler。

### Task D: provider/BFF 降级和重复任务治理

**Owner:** `fullstack-builder` + `qa-tester`

**Files:**

- Modify only if needed: `backend/app/services/latest_data_close_refresh.py`
- Modify only if needed: `backend/app/services/market/regime.py`
- Modify only if needed: `backend/app/services/market/providers/router.py`
- Modify only if needed: BFF/provider route/service files found by `rg`
- Test: `backend/tests/test_latest_data_close_refresh.py`
- Test: `backend/tests/test_market_regime_strategy_p2.py`
- Test: `backend/tests/test_v4_remaining_contracts.py`
- Test: `backend/tests/test_bff_monitor_workspace.py`
- Test: `backend/tests/test_market_quote_cache_refresh.py`

- [ ] **Step 1: 复跑 dedupe 和 BFF/provider 测试**

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_latest_data_close_refresh.py \
  backend/tests/test_market_regime_strategy_p2.py \
  backend/tests/test_v4_remaining_contracts.py \
  backend/tests/test_bff_monitor_workspace.py \
  backend/tests/test_market_quote_cache_refresh.py
```

Expected:

- PASS。
- 不改变 priority board 排序和生产分。
- provider degraded/warming snapshot 必须显式标记 cached/warming，不伪装 live freshness。

- [ ] **Step 2: 线上只读任务分布**

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" "
cd /home/ubuntu/gupiao-upload &&
sudo docker exec tquant-mysql sh -lc 'mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -D \"\$MYSQL_DATABASE\" -e \"SELECT task_type,status,COUNT(*) cnt,MIN(created_at) oldest,MAX(updated_at) latest FROM runtime_tasks WHERE created_at >= NOW() - INTERVAL 2 HOUR GROUP BY task_type,status ORDER BY cnt DESC LIMIT 40;\"'
"
```

Expected:

- 同日已成功的 A-key/strategy-tracking 不再重复大量新增。
- low-priority 任务不被 worker claim。

- [ ] **Step 3: D5 residual provider warning 复核**

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
cd /home/ubuntu/gupiao-upload
sudo docker logs --since 30m tquant-runtime-scheduler-mysql 2>&1 | \
  egrep -i "market provider circuit open|EastMoney|AkShare|fetch_intraday_bars|board_breadth|provider.*failed|timeout" | tail -120 || true
'
```

Expected:

- `fetch_intraday_bars` 链式 fallback 不应重新出现。
- board-breadth provider warning 若仍存在，D5 继续阻塞。
- 只记录问题，不通过重启 scheduler 来“清日志”。

### Task E: MySQL 根因专项

**Owner:** `devops-operator` + `fullstack-builder`

**Files:**

- Create: `docs/reports/mysql-runtime-root-cause-review-2026-06-12.md`
- Modify only after separate approval: DB index migration or query files

- [ ] **Step 1: 只读 MySQL 诊断**

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" "
cd /home/ubuntu/gupiao-upload &&
sudo docker exec tquant-mysql sh -lc 'mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -D \"\$MYSQL_DATABASE\" -e \"SHOW GLOBAL STATUS LIKE '\''Threads_%'\''; SHOW GLOBAL STATUS LIKE '\''Slow_queries'\''; SHOW VARIABLES LIKE '\''max_connections'\''; SHOW VARIABLES LIKE '\''innodb_buffer_pool_size'\''; SELECT table_schema, ROUND(SUM(data_length+index_length)/1024/1024,2) AS mb FROM information_schema.tables WHERE table_schema NOT IN ('\''mysql'\'','\''performance_schema'\'','\''information_schema'\'','\''sys'\'') GROUP BY table_schema;\"'
"
```

Expected:

- 只读。
- 报告连接数、慢查询累计、buffer pool、表空间。

- [ ] **Step 2: 决策表**

| 条件 | 下一步 |
|---|---|
| MySQL 仍 >90% memory 或有新 OOM | 优先升级 VM 内存或继续调整 MySQL limit/buffer pool |
| Slow_queries 增速高 | 抓慢 SQL、EXPLAIN、加索引或改查询 |
| Threads_running 长期高 | 查连接池和慢 API |
| API p95 高但资源稳定 | 查 BFF/priority board 查询路径 |
| 可用内存完整交易日仍 <500MiB | 优先升配，不再挤压核心服务 |

### Task F: 旧前端最终 guard

**Owner:** `ui-designer` + `qa-tester` + `devops-operator`

**Files:**

- Create: `docs/reports/frontend-next-legacy-guard-final-2026-06-12.md`
- Test: `backend/tests/test_frontend_next_level1_cutover.py`
- Test: `backend/tests/test_deploy_scope.py`
- Test: `backend/tests/test_cloud_deploy_scripts.py`

- [ ] **Step 1: 确认 `frontend/` 当前不存在**

```bash
test -d frontend; printf "frontend_dir_exit=%s\n" "$?"
git ls-files frontend | wc -l
```

Expected:

- `frontend_dir_exit=1`。
- tracked count `0`。

- [ ] **Step 2: 复跑旧入口防回流测试**

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_frontend_next_level1_cutover.py \
  backend/tests/test_deploy_scope.py \
  backend/tests/test_cloud_deploy_scripts.py
```

Expected:

- PASS。
- `frontend-hot`、`frontend-legacy` 不可部署。
- `/__legacy/*` 不恢复。
- CI/Docker 只构建 `frontend-next/dist`。

### Task G: 前端和核心页面稳定性验收

**Owner:** `ui-designer` + `qa-tester`

**Files:**

- Create: `docs/reports/frontend-next-core-pages-smoke-2026-06-12.md`

- [ ] **Step 1: frontend-next 本地验收**

```bash
cd frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
```

Expected:

- PASS。
- 无 chunk 404、无旧前端回流。

- [ ] **Step 2: 线上页面 smoke**

```bash
BASE_URL=http://43.143.243.97:18090
for path in / /readyz /next/monitor /next/monitor/market /next/strategy-tracking /next/analysis /next/backtest /next/data /next/settings; do
  curl -sS -o /tmp/gupiao-smoke.out -w "$path %{http_code} %{time_total}\n" --max-time 20 "$BASE_URL$path"
done
```

Expected:

- 页面 200 或明确重定向。
- 受保护 API 未登录返回 401，不能 timeout/5xx。

### Task H: 域名入口独立专项

**Owner:** `devops-operator`

**Files:**

- Create: `docs/reports/domain-entry-tls-reset-review-2026-06-12.md`

- [ ] **Step 1: 多入口 curl**

```bash
curl -vk --max-time 15 https://weisilianghua.cloud/readyz
curl -vk --resolve weisilianghua.cloud:443:43.143.243.97 --max-time 15 https://weisilianghua.cloud/readyz
curl -k -v --max-time 15 https://43.143.243.97/readyz
```

Expected:

- 区分 DNS/CDN/WAF/SNI/nginx/server block 问题。

- [ ] **Step 2: nginx 只读检查**

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
sudo nginx -t
sudo nginx -T 2>/tmp/nginxT.err | sed -n "/server_name/p"
cat /tmp/nginxT.err
'
```

Expected:

- 不 reload。
- 只记录重复 `server_name`、证书/SNI 风险。

## 7. 验收矩阵

| 验收项 | 必须通过 |
|---|---|
| Git | 每批开始前 `git status --short`；提交只包含本批文件 |
| 策略守卫 | `strategy_policy.py` 未改；production score 和 priority board 测试通过 |
| 核心 API | `/readyz` 200；受保护 API 401 快速返回；无 5xx/timeout |
| 核心页面 | `/next/monitor`、`/next/monitor/market`、`/next/strategy-tracking`、`/next/analysis`、`/next/backtest`、`/next/data`、`/next/settings` 可打开 |
| 资源 | MySQL 无 OOM；worker 不持续贴边；swap 不持续上涨 |
| 任务 | low-priority paused；核心任务完成；同日重复任务不爆量 |
| D5 gate | `collect_cloud_resource_gate_observation.py --full-trading-day-complete` 后 `d5_gate.ready=true` |
| 旧前端 | `frontend/` absent；CI/Docker/deploy 不回流旧前端 |
| 模拟盘 | active paper 不恢复；历史 paper task skipped，不 failed/retry |
| 长稳 | 完整交易日观察无 P0/P1 |
| 回滚 | 每个线上写动作都有 backup 和 rollback command |

## 8. 最终决策原则

### 8.1 是否最优

当前三层方案是现阶段最优的低风险方案：

- 它先解决最确定的资源争抢根因。
- 它不牺牲监控、行情缓存、低吸榜、priority board、策略追踪。
- 它不把 scheduler 合并这种有风险动作提前执行。
- 它承认 MySQL、域名、慢查询是独立根因，而不是把所有问题都归因到 worker。
- 它符合项目“模块化单体优先、重任务 Worker 化、分析/回测按需”的架构基线。

### 8.2 不能承诺彻底解决

本方案不能保证彻底解决所有线上问题，但能基本消掉“服务器资源争抢导致卡顿”这一大类问题。要接近彻底解决，必须组合完成：

1. 第一层非核心任务止血。
2. 第二层重复任务治理、worker RSS guard、scheduler 合并门槛。
3. 第三层 MySQL/慢查询/机器规格根因。
4. 域名公网链路修复。
5. 完整交易日长稳观察。

## 9. 多 Agent 分角色提示词

### 9.1 trading-platform-supervisor 总控提示词

```text
你是 trading-platform-supervisor，在 /Users/j/Documents/gupiao 总控云服务器资源争抢卡顿治理。

目标：按 docs/superpowers/plans/2026-06-12-cloud-resource-contention-final-integrated-development-plan.md 串行推进线上生效门禁，并协调各 Agent 并行完成本地开发、只读验证和报告。

开始前：
1. 执行 cd /Users/j/Documents/gupiao && git status --short。
2. 阅读 AGENTS.md、docs/engineering-conventions.md、docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md。
3. 阅读本计划、docs/reports/cloud-resource-contention-remediation-2026-06-11.md、docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md、docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md、docs/reports/mysql-runtime-root-cause-review-2026-06-12.md。

硬边界：
- 不改 backend/app/services/low_buy/strategy_policy.py。
- 不改变生产策略语义、production_score、priority_board 排序和口径。
- 不停止 MySQL、Redis、Web/API、Go hot-read、Go scan、核心 runtime-worker。
- 不把云端改成 Web-only。
- 未获授权不得修改线上 .env、不得重启/重建/停止容器、不得清理 Docker/磁盘、不得改 nginx/MySQL、不得写生产数据库。

执行要求：
- 本地开发可多 Agent 并行，线上动作必须串行并记录授权。
- D5 embedded scheduler 只有完整交易日 gate 通过后才能执行。
- provider degraded guard、worker recycle guard、dedupe 都只能作为 D5 前置稳定性条件，不能单独替代完整交易日 gate。
- 每批输出：完成项、失败项、风险、证据、是否执行线上写操作、下一步授权清单。
- 每批结束前复核 git status，并保护无关未提交文件。
```

### 9.2 devops-operator 提示词

```text
你是 devops-operator，只处理云端运维、runbook、部署脚本、compose/env 示例、只读线上验证和授权操作记录。

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
3. 输出 D5 交易日只读观察记录，未达 gate 不执行 scheduler embed。
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
2. removed paper 历史任务进入 skipped_removed_feature，不恢复 active 模拟盘。
3. worker recycle guard 只在任务完成后触发，不中断 running task。
4. close-refresh dedupe 防止同日成功任务重复入队。
5. scheduler embed 支持但默认关闭，不能重复跑 scheduler。
6. market regime provider degraded guard 使用 cached/warming snapshot 降级，减少 provider fallback 链式压力。

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
1. 建立 D0-D7 验收矩阵，区分 PASS/WARN/FAIL。
2. 验证核心服务：/readyz、核心 API、/next/monitor、/next/monitor/market、/next/strategy-tracking、/next/analysis、/next/backtest、/next/data、/next/settings。
3. 验证资源：uptime/load/free/swap/df/df -ih/docker ps/docker stats/docker system df。
4. 验证任务：runtime_tasks、scheduler heartbeat、worker heartbeat、low-priority pause、dedupe。
5. 验证前端：无白屏、无 chunk 404、无旧前端入口回流。
6. 验证 D5 gate：full trading day incomplete、scheduler provider warnings、non-terminal tasks 任一存在时必须保持 blocked。

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
4. 明确模拟盘不恢复为核心功能，历史入口只做降噪和 skipped。
5. 明确关闭项是否影响当前用户重心任务；若影响，必须提供替代路径或恢复条件。

禁止：
- 不提出恢复 active paper 作为核心路径。
- 不改变 priority board、production_score 或生产策略口径。

输出：
- docs/reports/cloud-resource-contention-product-impact-2026-06-12.md
- 每个关闭项必须写清：用户可见影响、替代路径、恢复条件、是否需要授权。
```

### 9.6 ui-designer 提示词

```text
你是 ui-designer，负责 frontend-next 页面可用性、旧前端退役 guard 和页面信息可读性检查。

目标：
1. 检查 /next/monitor、/next/monitor/market、/next/strategy-tracking、/next/analysis、/next/backtest、/next/data、/next/settings。
2. 验证无白屏、无 JS chunk 404、无动态 import 失败、无明显组件堆叠。
3. 验证旧 frontend/ 不回流，frontend-hot、frontend-legacy、/__legacy/* 不恢复。
4. 不恢复 /paper 或 /next/paper 为核心页面。

禁止：
- 不引入旧前端。
- 不做 landing page 式重构。
- 不改变生产策略展示口径。

验证：
- cd frontend-next && npm run api:check && npm run typecheck && npm run lint && npm test -- --run && npm run build
- PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_frontend_next_level1_cutover.py backend/tests/test_deploy_scope.py backend/tests/test_cloud_deploy_scripts.py
```

### 9.7 trading-quant-lead 提示词

```text
你是 trading-quant-lead，只做策略语义守卫审查，不实现新策略。

目标：
1. 确认本方案不会改变可交易性过滤、信号规则、仓位风控、production_score、priority_board 排序。
2. 确认关闭非核心任务不会影响低吸榜、priority board、策略追踪的生产口径。
3. 对任何可能影响生产策略结果的代码改动标为 blocker。

禁止：
- 不改 backend/app/services/low_buy/strategy_policy.py。
- 不新增策略规则。
- 不把 research/shadow/paper 口径接入生产排序。

验证：
- PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py
```

### 9.8 stock-analysis-specialist 提示词

```text
你是 stock-analysis-specialist，只审查市场复盘、热点板块、情绪周期相关能力被停用后的解释影响，不改生产排序。

目标：
1. 判断 MARKET_REVIEW_ENABLED=false 对用户看到的市场解读、午盘/收盘复盘、热点板块解释有什么影响。
2. 确认核心监控、行情缓存、低吸榜、priority board、策略追踪仍能支撑交易观察。
3. 输出哪些市场阅读能力应改为按需运行，而不是常驻抢资源。

禁止：
- 不把主观市场判断写入生产排序。
- 不修改 production_score。
- 不恢复 active paper。

输出：
- docs/reports/cloud-resource-contention-market-review-impact-2026-06-12.md
```

## 10. 总控可复制执行提示词

```text
你在 /Users/j/Documents/gupiao 项目中工作。请按 docs/superpowers/plans/2026-06-12-cloud-resource-contention-final-integrated-development-plan.md 执行下一批开发/验证。

目标：三层治理线上资源争抢导致的卡顿，并融合旧前端退役与已移除模拟盘残留收口。核心必须持续可用：监控、行情缓存、低吸榜、priority board、策略追踪、watchdog、app/mysql/redis/frontend-next/go-bff/go-market-read/go-scan/runtime-worker。

开始前必须执行：
1. cd /Users/j/Documents/gupiao && git status --short
2. 阅读 AGENTS.md、docs/engineering-conventions.md、docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md
3. 阅读 docs/superpowers/plans/2026-06-12-cloud-resource-contention-final-integrated-development-plan.md
4. 阅读 docs/reports/cloud-resource-contention-remediation-2026-06-11.md、docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md、docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md、docs/reports/mysql-runtime-root-cause-review-2026-06-12.md、docs/reports/provider-degraded-cooldown-market-regime-optimization-2026-06-12.md、docs/reports/online-stability-legacy-frontend-retirement-implementation-2026-06-11.md

硬边界：
- 不改 backend/app/services/low_buy/strategy_policy.py
- 不改变生产策略语义、production_score、priority_board 排序和口径
- 不停止 MySQL、Redis、Web/API、Go hot-read、Go scan、核心 runtime-worker
- 不把云端改成 Web-only
- 不恢复 active 模拟盘，不恢复 /paper 或 /next/paper 作为核心路径
- 未获授权不得改线上 .env、不得重启/重建/停止容器、不得清理 Docker/磁盘、不得改 nginx/MySQL、不得写生产数据库
- D5 embedded scheduler 不得在 d5_gate.ready=false 时执行
- 域名 TLS/SNI、MySQL schema/index/配置、Docker cleanup、机器升配都必须作为独立授权专项

执行方式：
- 可多 Agent 并行：trading-quant-lead 做策略守卫，stock-analysis-specialist 做市场复盘关闭影响审查，product-strategist 做功能影响矩阵，ui-designer 做 frontend-next 页面/旧入口检查，fullstack-builder 做后端 guard/dedupe/provider/verifier，qa-tester 做测试和长稳验收，devops-operator 做 runbook/只读线上验证/授权操作。
- 本地开发可并行，线上生效必须串行：先只读基线，再本地测试，再用户授权，再最小范围变更，再 2-4 小时观察，再完整交易日观察。
- D5 embedded scheduler 只有在 worker RSS、MySQL、swap、任务队列完整交易日稳定后才能执行；否则继续保留独立 scheduler。

本批优先做：
1. 更新或新增 docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md，记录完整交易日观察模板和当前未完成项。
2. 复核第一层 stop profile 是否在线生效：PLATFORM_AUTOPILOT_ENABLED=false、RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true、MARKET_REVIEW_ENABLED=false。
3. 复核 worker recycle guard 是否已启用及是否在任务边界正常工作；未稳定前不得执行 scheduler embed。
4. 复核 provider degraded guard 是否减少 fallback 链式压力；如仍有 scheduler_provider_warnings_present，D5 继续阻塞。
5. 复跑 dedupe、runtime task、priority board、low-buy、frontend-next cutover 相关测试。
6. 输出下一步授权清单：哪些可以只读，哪些需要用户明确授权。

验收命令至少包含：
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_platform_budget_verifier.py backend/tests/test_runtime_task_queue.py backend/tests/test_phase4_runtime_worker_tasks.py backend/tests/test_independent_runtime_components.py backend/tests/test_cloud_deploy_scripts.py
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_latest_data_close_refresh.py backend/tests/test_market_regime_strategy_p2.py backend/tests/test_v4_remaining_contracts.py backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py backend/tests/test_frontend_next_level1_cutover.py backend/tests/test_deploy_scope.py
cd frontend-next && npm run api:check && npm run typecheck && npm run lint && npm test -- --run && npm run build

输出：
- 更新/新增 Markdown 报告和必要代码/测试
- 说明已完成、未完成、需要授权的线上动作
- 明确本轮是否执行任何写操作/重启/清理/部署
- 给出下一步最小风险执行顺序
```
