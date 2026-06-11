# Cloud Resource Contention And Legacy Closure Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 分三层解决线上“服务器资源争抢导致卡顿”问题，并完成旧前端与已停模拟盘残留收口，同时保证监控、行情缓存、低吸榜、priority board、策略追踪持续可用。

**Architecture:** 先用配置和队列门控停掉非核心常驻任务止血；再把独立 scheduler 合并到 runtime-worker 的嵌入式调度结构，减少常驻内存；最后专项处理 MySQL 内存/慢查询/机器规格根因。旧前端和模拟盘不作为核心链路恢复，只做防回流、残留任务跳过、脚本和文档收口。

**Tech Stack:** Docker Compose, FastAPI, MySQL 8.4, Redis 7, Python runtime worker, Go hot-read services, frontend-next, pytest, Playwright, curl, SSH runbook.

---

## 1. 背景结论

### 1.1 当前问题

最近线上审计和稳定性报告显示：

| 维度 | 结论 |
|---|---|
| 线上可用性 | IP 入口可用，域名 `weisilianghua.cloud` 仍有公网 reset 风险 |
| 最大资源瓶颈 | MySQL 贴近 `1GiB` 容器上限，runtime-worker/scheduler 周期性高内存和高 CPU |
| 主要卡顿来源 | 非核心 runtime task、行情源失败重试、低吸/监控物化、scheduler 和 worker 同时抢 CPU/IO |
| 前端资源 | `frontend-next` 不是主要资源瓶颈；旧 `frontend/` 已不在 git tracked 文件内 |
| 模拟盘 | 用户已确认可以停；当前方案不得恢复 active 模拟盘功能 |

### 1.2 本方案能解决什么

- 云服务器内存长期吃紧。
- swap 高或持续上涨。
- worker、扫描、刷新、回测、Web 抢 CPU/IO。
- 页面/API 在数据刷新或策略物化时变慢。
- runtime 任务堆积影响主服务。
- 部署后容器资源恢复慢。
- 已停模拟盘任务继续重试造成队列噪声。
- 旧前端或旧脚本引用回流到部署/验证链路。

### 1.3 本方案不能单独解决什么

- `weisilianghua.cloud` TLS/SNI reset。
- MySQL 真实慢查询和索引不足。
- priority board / monitor BFF 代码层查询过重。
- 外部行情源被限频、返回 HTML 或超时。
- 本地电脑断网、休眠、关机导致本地重任务不跑。
- 浏览器缓存、旧 chunk、用户端网络问题。

这些需要在本方案后续批次或独立专项里处理。

## 2. 硬边界

### 2.1 绝对禁止

- 不改 `backend/app/services/low_buy/strategy_policy.py`。
- 不改变生产策略语义。
- 不改变 `production_score`。
- 不改变 `priority_board` 排序和口径。
- 不停止 MySQL、Redis、Web、Go hot-read、核心 runtime-worker。
- 不把云端改成 Web-only。
- 不恢复 `/paper` 或 `/next/paper` active 模拟盘功能。
- 不把 research-only / shadow-only 策略接入生产排序。
- 不直接删除生产数据库表、binlog、volume 或核心缓存。

### 2.2 最新核心保护范围

本方案以用户最新授权为准，模拟盘不再作为核心保护项。核心必须持续可用：

| 核心能力 | 必须保持 |
|---|---|
| 监控 | `/next/monitor`、monitor snapshot、BFF workspace |
| 行情缓存 | quote cache、market pulse、Go market-read |
| 低吸榜 | low-buy materialization、推荐榜数据 |
| priority board | 排序、日期、口径和生产分不变 |
| 策略追踪 | strategy tracking snapshot 和页面 |
| watchdog | latest data watchdog、数据新鲜度检查 |
| 基础服务 | app、mysql、redis、frontend-next、go-bff、go-scan、runtime-worker |

## 3. 多 Agent 并行分工

### 3.1 总控角色

`trading-platform-supervisor`

- 负责阶段门禁、风险升级、线上授权点确认。
- 每个批次开始前执行 `git status --short`。
- 合并各 Agent 结果，决定是否进入下一批。
- 保证任何批次都不越过策略语义、生产分和 priority board 口径边界。

### 3.2 可并行工作流

| Agent | 工作流 | 可并行 | 主要输出 |
|---|---|---|---|
| `devops-operator` | Runbook、deploy/quick deploy、compose/env 示例、线上只读验收 | 可与 backend/QA 并行 | 运维文档、脚本 guard、回滚命令 |
| `fullstack-builder` | runtime task 门控、scheduler embed、budget verifier、paper residual skip | 可与 DevOps 并行 | 后端实现和 pytest |
| `qa-tester` | pytest、Playwright、HTTP smoke、p95 对比、长稳观察脚本 | 可独立并行 | 验收报告和失败证据 |
| `product-strategist` | 非核心关闭影响说明、页面入口口径、模拟盘停用说明 | 可并行 | 功能影响矩阵 |
| `ui-designer` | frontend-next 页面无白屏/堆叠/chunk 失败检查 | 可并行 | 前端可用性报告 |
| `trading-quant-lead` | 生产策略、排序、分数、交易语义不变审核 | 串行门禁 | 策略边界确认 |
| `stock-analysis-specialist` | 市场复盘关闭后对选股解释和交易上下文影响审核 | 串行门禁 | 市场阅读影响确认 |

### 3.3 串行上线门槛

本地开发可并行，线上生效必须串行：

1. D0 本地和线上只读基线。
2. D1 非核心任务止血。
3. D2 观察 2-4 小时。
4. D3 scheduler embed 本地和预发验证。
5. D4 维护窗口合并 scheduler。
6. D5 完整交易日观察。
7. D6 MySQL/机器规格根因治理。
8. D7 域名链路独立处理。

## 4. 目标稳态拓扑

### 4.1 云端常驻

| 服务 | 目标 | 说明 |
|---|---|---|
| `tquant-app-mysql` | 常驻 | API 和静态 frontend-next |
| `tquant-frontend-web` | 视入口策略保留或按需 | 当前资源很小，是否停用需单独授权 |
| `tquant-mysql` | 常驻 | 核心事实源，后续治理内存和慢查询 |
| `tquant-redis` | 常驻 | 缓存和事件通道 |
| `tquant-go-bff-gateway` | 常驻 | monitor/priority 热读聚合 |
| `tquant-go-market-read-service` | 常驻 | 行情热读 |
| `tquant-go-scan-worker` | 常驻 | 资源低，保留扫描加速 |
| `tquant-runtime-worker-mysql` | 常驻但瘦身 | 消费核心任务，后续可嵌入 scheduler |

### 4.2 默认关闭或按需

| 项 | 目标 | 功能影响 |
|---|---|---|
| `analytics-worker` | 按需 profile | DuckDB/Parquet/分析导出需手动拉起 |
| `backtest-worker` | 不常驻 | 长回测不在云端 steady state 跑 |
| 独立 `runtime-scheduler` | D4 后停用 | 调度由 runtime-worker embedded scheduler 承接 |
| `hermes_platform_autopilot` | 关闭 | 自动巡检/自愈建议停止 |
| `MARKET_REVIEW_ENABLED` | 关闭或降级 | 午盘/收盘复盘报告停止 |
| low-priority task | 暂停 | analytics/backtest/ML/factor/data repair/research 不抢资源 |
| 模拟盘自动任务 | 停止 | 已符合用户确认 |

## 5. 文件改动规划

### 5.1 新增文档

- Create: `docs/operations/cloud-core-worker-resource-runbook.md`
- Create: `docs/reports/cloud-resource-contention-remediation-2026-06-11.md`
- Create: `docs/reports/cloud-resource-contention-rollout-2026-06-11.md`

### 5.2 修改文档

- Modify: `PRODUCTION_RUNBOOK.md`
- Modify: `.env.deploy.local.example`
- Modify: `docs/reports/online-stability-remaining-7-items-final-2026-06-11.md` only if appending follow-up evidence

### 5.3 修改部署和预算脚本

- Modify: `scripts/deploy_cloud_server.sh`
- Modify: `scripts/quick_cloud_deploy.sh`
- Modify: `scripts/verify_platform_budget.py`
- Modify: `scripts/plan_platform_maintenance_window.py`

### 5.4 修改后端

- Modify: `backend/app/workers/runtime_worker.py`
- Modify: `backend/app/runtime/background_jobs.py`
- Modify: `backend/app/services/tasks/queue.py`
- Modify: `backend/app/core/config.py` only if a setting is missing

### 5.5 修改前端/旧入口收口

- Modify: `frontend-next/scripts/visual-review.mjs`
- Modify: `frontend-next/scripts/screenshot-parity.mjs`
- Modify: `frontend-next/scripts/visual-consistency.mjs`
- Modify: `frontend-next/scripts/perf-profile.mjs`
- Modify: `frontend-next/scripts/request-trace.mjs`
- Modify: `frontend-next/scripts/write-readiness.mjs`
- Modify: `frontend-next/scripts/write-rollback-smoke.mjs`

### 5.6 测试

- Test: `backend/tests/test_platform_budget_verifier.py`
- Test: `backend/tests/test_cloud_deploy_scripts.py`
- Test: `backend/tests/test_independent_runtime_components.py`
- Test: `backend/tests/test_runtime_task_queue.py`
- Test: `backend/tests/test_phase4_runtime_worker_tasks.py`
- Test: `backend/tests/test_frontend_next_level1_cutover.py`
- Test: frontend-next npm scripts and Playwright smoke

## 6. Task D0: Baseline And Safety Gate

**Owner:** `trading-platform-supervisor` + `devops-operator`

**Files:**

- Create/Update: `docs/reports/cloud-resource-contention-remediation-2026-06-11.md`

- [ ] **Step 1: Confirm worktree**

```bash
cd /Users/j/Documents/gupiao
git status --short
```

Expected:

- Empty output or documented unrelated files.
- Do not overwrite unrelated dirty files.

- [ ] **Step 2: Read required docs**

```bash
sed -n '1,220p' AGENTS.md
sed -n '1,260p' docs/engineering-conventions.md
sed -n '1,260p' docs/reports/online-service-status-audit-2026-06-11.md
sed -n '1,260p' docs/reports/online-stability-remaining-7-items-final-2026-06-11.md
sed -n '1,220p' docs/reports/legacy-frontend-retirement-decision-2026-06-11.md
```

Expected:

- Confirm core boundaries and current topology from repo docs, not assumptions.

- [ ] **Step 3: Capture online read-only baseline**

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
set -e
date
uptime
free -m
df -h /
df -ih /
cd /home/ubuntu/gupiao-upload
sudo docker compose -f docker-compose.mysql.yml ps --format "table {{.Name}}\t{{.Status}}"
sudo docker stats --no-stream --format "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | sort
sudo docker system df
curl -sS -o /tmp/readyz.json -w "readyz %{http_code} %{time_total}\n" --max-time 10 http://127.0.0.1:18090/readyz
'
```

Expected:

- No write operation.
- Report records memory, swap, disk, inode, container status and HTTP health.

## 7. Task D1: Non-Core Stop And Residual Paper Closure

**Owner:** `fullstack-builder` + `devops-operator`

**Files:**

- Modify: `.env.deploy.local.example`
- Modify: `backend/app/workers/runtime_worker.py`
- Modify: `backend/app/services/tasks/queue.py`
- Test: `backend/tests/test_runtime_task_queue.py`
- Test: `backend/tests/test_phase4_runtime_worker_tasks.py`

- [ ] **Step 1: Add resource stop profile to `.env.deploy.local.example`**

Add this block near runtime settings:

```dotenv
# Authorized small-host resource contention profile.
# Apply to production .env only in a maintenance window after baseline capture.
# It keeps Web/API/Go hot-read/core runtime tasks online and pauses non-core work.
# PLATFORM_AUTOPILOT_ENABLED=false
# RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true
# MARKET_REVIEW_ENABLED=false
# RUNTIME_STARTUP_CACHE_PREWARM_ENABLED=false
# RUNTIME_STARTUP_HISTORY_PREWARM_ENABLED=false
# DEPLOY_EMBED_RUNTIME_SCHEDULER=0
```

Expected:

- Example only; no secret.
- Existing default remains conservative.

- [ ] **Step 2: Preserve skipped removed-paper-task behavior**

Keep or add tests that prove removed paper tasks do not retry as failures:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_phase4_runtime_worker_tasks.py
```

Expected:

- Paper residual tasks are marked `skipped_removed_feature`.
- They do not grow `failed` counts.
- No active paper trading is restored.

- [ ] **Step 3: Add runbook stop matrix**

Create `docs/operations/cloud-core-worker-resource-runbook.md` with:

```markdown
# Cloud Core Worker Resource Runbook

## Protected Services

Do not stop MySQL, Redis, app, frontend-next, Go hot-read services, or runtime-worker.

## Stop Profile

Set `PLATFORM_AUTOPILOT_ENABLED=false`, `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true`,
`MARKET_REVIEW_ENABLED=false`, and keep startup prewarm disabled.

## Rollback

Restore the backed-up `.env` and recreate only app/runtime-worker/runtime-scheduler.
```

Expected:

- Runbook separates recommended commands from commands actually executed.
- Rollback is explicit.

## 8. Task D2: Platform Budget And Core Health Guard

**Owner:** `fullstack-builder` + `qa-tester`

**Files:**

- Modify: `scripts/verify_platform_budget.py`
- Test: `backend/tests/test_platform_budget_verifier.py`

- [ ] **Step 1: Extend verifier env collection**

Ensure budget reports include:

```python
"RUNTIME_LOW_PRIORITY_TASKS_PAUSED"
"RUNTIME_WORKER_EMBED_SCHEDULER"
"RUNTIME_SCHEDULER_BACKGROUND_JOBS_ENABLED"
"PLATFORM_AUTOPILOT_ENABLED"
"MARKET_REVIEW_ENABLED"
```

- [ ] **Step 2: Add core resource profile warnings**

Expected behavior:

- Warn if runtime worker low-priority pause is not enabled in resource mitigation mode.
- Warn if standalone scheduler is missing while embedded scheduler is false.
- Do not warn for missing standalone scheduler when `RUNTIME_WORKER_EMBED_SCHEDULER=true`.

- [ ] **Step 3: Test verifier**

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_platform_budget_verifier.py
```

Expected:

- PASS.
- Warnings are visible but do not block local development by default.

## 9. Task D3: Embedded Scheduler Deploy Support

**Owner:** `devops-operator` + `fullstack-builder`

**Files:**

- Modify: `scripts/deploy_cloud_server.sh`
- Modify: `scripts/quick_cloud_deploy.sh`
- Modify: `scripts/plan_platform_maintenance_window.py`
- Test: `backend/tests/test_cloud_deploy_scripts.py`
- Test: `backend/tests/test_independent_runtime_components.py`

- [ ] **Step 1: Add explicit deploy flag**

Add support for:

```bash
DEPLOY_EMBED_RUNTIME_SCHEDULER=1
```

Expected:

- Default behavior unchanged.
- With the flag, deployment sets `RUNTIME_WORKER_EMBED_SCHEDULER=true` and `RUNTIME_SCHEDULER_BACKGROUND_JOBS_ENABLED=false`.

- [ ] **Step 2: Make verification scheduler-aware**

Expected:

- Normal deploy waits for `tquant-runtime-scheduler-mysql`.
- Embedded mode prints `runtime_scheduler:embedded` and does not fail because standalone scheduler is absent.
- Image/container verification skips scheduler image check only in embedded mode.

- [ ] **Step 3: Test scripts**

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_cloud_deploy_scripts.py \
  backend/tests/test_independent_runtime_components.py
```

Expected:

- PASS.
- Compose still declares independent worker/scheduler; deploy flag controls runtime topology.

## 10. Task D4: Old Frontend And Paper Entry Closure

**Owner:** `product-strategist` + `ui-designer` + `qa-tester`

**Files:**

- Modify: `PRODUCTION_RUNBOOK.md`
- Modify: `frontend-next/scripts/visual-review.mjs`
- Modify: `frontend-next/scripts/screenshot-parity.mjs`
- Modify: `frontend-next/scripts/visual-consistency.mjs`
- Modify: `frontend-next/scripts/perf-profile.mjs`
- Modify: `frontend-next/scripts/request-trace.mjs`
- Modify: `frontend-next/scripts/write-readiness.mjs`
- Modify: `frontend-next/scripts/write-rollback-smoke.mjs`
- Test: `backend/tests/test_frontend_next_level1_cutover.py`

- [ ] **Step 1: Confirm old frontend is absent**

```bash
test -d frontend; echo "frontend_dir=$?"
git ls-files frontend | wc -l
```

Expected:

- `frontend_dir=1`.
- tracked file count is `0`.

- [ ] **Step 2: Remove active paper page from frontend validation scripts**

Replace `/paper` and `/next/paper` smoke routes with current active pages:

```text
/next/monitor
/next/monitor/market
/next/strategy-tracking
/next/analysis
/next/backtest
/next/data
/next/settings
```

Expected:

- No frontend test attempts active paper write workflows.
- Historical generated API fields are not edited manually.

- [ ] **Step 3: Update production runbook core loop**

Runbook should state:

```markdown
Current protected user loop: monitor, market monitor, low-buy board, priority board,
strategy tracking, analysis, backtest research view, data, settings.

Paper trading is retired from active production operation and must not be restored
without a separate product and data migration plan.
```

Expected:

- Runbook no longer implies paper is a protected active production path.
- It can still mention historical paper tables as read-only history.

- [ ] **Step 4: Test frontend and backend guards**

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_frontend_next_level1_cutover.py

cd frontend-next
npm run api:check
npm run lint
npm test -- --run
npm run build
```

Expected:

- PASS.
- No chunk 404 or old frontend fallback.

## 11. Task D5: Authorized Online Stop And Observation

**Owner:** `devops-operator` + `qa-tester`

**Online write:** yes, only after explicit authorization.

- [ ] **Step 1: Required authorization text**

```text
授权在维护窗口修改线上 .env，并仅重建 app/runtime-worker/runtime-scheduler 以启用非核心任务止血配置。
```

- [ ] **Step 2: Apply stop profile**

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
set -e
cd /home/ubuntu/gupiao-upload
cp .env ".env.backup.$(date +%Y%m%d%H%M%S)"
python3 - <<'"'"'PY'"'"'
from pathlib import Path
path = Path(".env")
pairs = {
    "PLATFORM_AUTOPILOT_ENABLED": "false",
    "RUNTIME_LOW_PRIORITY_TASKS_PAUSED": "true",
    "MARKET_REVIEW_ENABLED": "false",
    "RUNTIME_STARTUP_CACHE_PREWARM_ENABLED": "false",
    "RUNTIME_STARTUP_HISTORY_PREWARM_ENABLED": "false",
}
lines = path.read_text(encoding="utf-8").splitlines()
seen = set()
out = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in pairs:
        out.append(f"{key}={pairs[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, value in pairs.items():
    if key not in seen:
        out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate app runtime-worker runtime-scheduler
'
```

Expected:

- MySQL/Redis/Go/Frontend are not restarted by this command.
- `/readyz` returns 200 after recreation.

- [ ] **Step 3: Observe 2-4 hours**

Collect every 30 minutes:

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
date
uptime
free -m
cd /home/ubuntu/gupiao-upload
sudo docker stats --no-stream --format "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | sort
curl -sS -o /tmp/readyz.json -w "readyz %{http_code} %{time_total}\n" --max-time 10 http://127.0.0.1:18090/readyz
curl -sS -o /tmp/snapshot.json -w "monitor_snapshot %{http_code} %{time_total}\n" --max-time 20 http://127.0.0.1:18090/api/monitor/snapshot
curl -sS -o /tmp/priority.json -w "priority_board %{http_code} %{time_total}\n" --max-time 20 http://127.0.0.1:18090/api/screeners/low-buy/priority-board
'
```

Expected:

- `readyz` 200.
- Protected APIs return either 200 with auth or 401 without auth, not timeout/5xx.
- available memory stabilizes.
- swap does not keep rising.

## 12. Task D6: Authorized Embedded Scheduler Cutover

**Owner:** `devops-operator` + `qa-tester`

**Online write:** yes, only after D5 observation passes.

- [ ] **Step 1: Required authorization text**

```text
授权在维护窗口启用 RUNTIME_WORKER_EMBED_SCHEDULER=true，并停独立 runtime-scheduler。
```

- [ ] **Step 2: Apply embedded scheduler**

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
set -e
cd /home/ubuntu/gupiao-upload
cp .env ".env.scheduler-backup.$(date +%Y%m%d%H%M%S)"
python3 - <<'"'"'PY'"'"'
from pathlib import Path
path = Path(".env")
pairs = {
    "RUNTIME_WORKER_EMBED_SCHEDULER": "true",
    "RUNTIME_SCHEDULER_BACKGROUND_JOBS_ENABLED": "false",
}
lines = path.read_text(encoding="utf-8").splitlines()
seen = set()
out = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in pairs:
        out.append(f"{key}={pairs[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, value in pairs.items():
    if key not in seen:
        out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate runtime-worker
sudo docker rm -f tquant-runtime-scheduler-mysql
'
```

Expected:

- Runtime worker becomes the scheduler host.
- Standalone scheduler is absent by design.

- [ ] **Step 3: Verify heartbeat and core tasks**

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" "
cd /home/ubuntu/gupiao-upload &&
sudo docker exec tquant-mysql sh -lc 'mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -D \"\$MYSQL_DATABASE\" -e \"SELECT component, worker_id, status, updated_at FROM platform_component_heartbeats WHERE component = '\''runtime-scheduler'\'' ORDER BY updated_at DESC LIMIT 5; SELECT task_type, status, COUNT(*) cnt, MAX(updated_at) latest FROM runtime_tasks WHERE created_at >= NOW() - INTERVAL 8 HOUR AND task_type IN ('\''monitor_snapshot_refresh'\'','\''market_pulse_refresh'\'','\''low_buy_materialization_refresh'\'','\''strategy_tracking_snapshot_refresh'\'','\''market_quote_cache_refresh'\'','\''latest_data_watchdog'\'') GROUP BY task_type, status ORDER BY task_type, status;\"'
"
```

Expected:

- Scheduler heartbeat continues.
- Core tasks continue to enqueue and complete.
- No sustained backlog growth.

## 13. Task D7: MySQL And Machine Spec Root Cause

**Owner:** `devops-operator` + `fullstack-builder` + `qa-tester`

**Online write:** only after D5/D6 evidence shows resource pressure remains.

- [ ] **Step 1: Read-only MySQL diagnosis**

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" "
cd /home/ubuntu/gupiao-upload &&
sudo docker exec tquant-mysql sh -lc 'mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -D \"\$MYSQL_DATABASE\" -e \"SHOW GLOBAL STATUS LIKE '\''Threads_%'\''; SHOW GLOBAL STATUS LIKE '\''Slow_queries'\''; SHOW VARIABLES LIKE '\''max_connections'\''; SHOW VARIABLES LIKE '\''innodb_buffer_pool_size'\''; SELECT table_schema, ROUND(SUM(data_length+index_length)/1024/1024,2) AS mb FROM information_schema.tables WHERE table_schema NOT IN ('\''mysql'\'','\''performance_schema'\'','\''information_schema'\'','\''sys'\'') GROUP BY table_schema;\"'
"
```

Expected:

- No DB writes.
- Report includes connection pressure, slow query count, buffer pool and table size.

- [ ] **Step 2: Decide root fix**

Use this decision table:

| Condition | Action |
|---|---|
| MySQL still >90% memory after D5/D6 | Increase `MYSQL_MEM_LIMIT` and tune buffer pool in maintenance window |
| Worker still OOM risk after low-priority pause | Raise worker limit or split heavy handlers into on-demand worker |
| API p95 still high with resources stable | Inspect BFF/priority-board queries and indexes |
| Machine available memory remains <500MiB | Upgrade VM memory before further feature work |
| Resources stable for a full trading day | Keep current spec; do not downsize until another observation window passes |

Expected:

- Stability takes priority over cost reduction.
- Any MySQL config write has backup and rollback.

## 14. Task D8: Stability And Frontend Acceptance

**Owner:** `qa-tester` + `ui-designer`

- [ ] **Step 1: HTTP smoke**

```bash
BASE_URL=https://43.143.243.97
for path in / /readyz /next/monitor /next/monitor/market /next/strategy-tracking /next/analysis /next/backtest /next/data /next/settings; do
  curl -k -sS -o /tmp/gupiao-smoke.out -w "$path %{http_code} %{time_total}\n" --max-time 20 "$BASE_URL$path"
done
```

Expected:

- Pages return 200 or documented redirect.
- No timeout.

- [ ] **Step 2: Playwright check**

```bash
cd frontend-next
npx playwright test tests/e2e/monitor-workflows.spec.ts tests/e2e/strategy-tracking.spec.ts tests/e2e/analysis-playbook.spec.ts --project=chromium
```

Expected:

- PASS.
- No dynamic import 404.
- No blank page.

- [ ] **Step 3: Full trading-day observation**

Observe at:

```text
09:15 pre-open
09:35 after open
11:30 midday
13:05 afternoon reopen
14:55 close pressure
15:10 post-close
```

Record:

- uptime/load.
- free/swap.
- docker stats.
- readyz latency.
- core runtime task status.
- frontend page status.
- external行情源 error rate.

Expected:

- No P0/P1 resource incident.
- Core tasks complete.
- priority board and strategy tracking data fresh.

## 15. Task D9: Domain TLS Reset Independent Track

**Owner:** `devops-operator`

This track is independent from server resource contention.

- [ ] **Step 1: Multi-entry curl**

```bash
curl -vk --max-time 15 https://weisilianghua.cloud/readyz
curl -vk --resolve weisilianghua.cloud:443:43.143.243.97 --max-time 15 https://weisilianghua.cloud/readyz
curl -k -v --max-time 15 https://43.143.243.97/readyz
```

Expected:

- Identify whether reset is DNS/CDN/WAF/SNI/nginx-specific.

- [ ] **Step 2: Nginx config read-only audit**

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
sudo nginx -t
sudo nginx -T 2>/tmp/nginxT.err | sed -n "/server_name/p"
cat /tmp/nginxT.err
'
```

Expected:

- No nginx reload.
- Duplicate `server_name` or certificate mismatch is documented.

## 16. Commit Plan

Use small commits:

1. `docs: add cloud core worker resource runbook`
2. `test: guard cloud core resource profile`
3. `feat: add embedded scheduler deploy mode`
4. `fix: close retired paper and legacy frontend smoke paths`
5. `docs: record cloud resource rollout evidence`

Each commit must be independently testable.

## 17. Acceptance Gates

| Gate | Required result |
|---|---|
| Git safety | `git status --short` reviewed before each batch |
| Strategy safety | no changes to `strategy_policy.py`, `production_score`, priority board ordering |
| Core tasks | monitor, quote cache, low-buy, priority board, strategy tracking, watchdog complete |
| Resource | memory available stable, swap not rising, no MySQL/worker OOM |
| API | `/readyz` 200, core protected APIs no timeout/5xx |
| Frontend | frontend-next pages no blank, no chunk 404, no legacy frontend fallback |
| Scheduler | embedded scheduler heartbeat and task enqueue verified before standalone scheduler remains stopped |
| MySQL | slow query and memory plan backed by evidence before config/spec change |
| Rollback | every online write has backup and restore command |

## 18. Master Prompt

Copy this prompt for a coordinated multi-agent execution:

```text
你在 /Users/j/Documents/gupiao 项目中工作。目标：按照 docs/superpowers/plans/2026-06-11-cloud-resource-contention-and-legacy-closure-development-plan.md 完成“服务器资源争抢治理 + scheduler 合并 + MySQL/机器规格根因治理 + 旧前端/已停模拟盘残留收口”的开发批次。

开始前必须：
1. 执行 cd /Users/j/Documents/gupiao && git status --short，保护本地未提交文件。
2. 阅读 AGENTS.md、docs/engineering-conventions.md、docs/superpowers/plans/2026-06-11-cloud-resource-contention-and-legacy-closure-development-plan.md。
3. 阅读 docs/reports/online-service-status-audit-2026-06-11.md、docs/reports/online-stability-remaining-7-items-final-2026-06-11.md、docs/reports/legacy-frontend-retirement-decision-2026-06-11.md。
4. 用 rg 复核 RUNTIME_LOW_PRIORITY_TASKS_PAUSED、RUNTIME_WORKER_EMBED_SCHEDULER、PLATFORM_AUTOPILOT_ENABLED、MARKET_REVIEW_ENABLED、analytics-worker、backtest-worker、paper、frontend-legacy、frontend-hot、__legacy、frontend/dist 的当前引用，不要凭印象改。

硬边界：
- 不改 backend/app/services/low_buy/strategy_policy.py。
- 不改变生产策略语义、production_score、priority_board 排序和口径。
- 不恢复 active 模拟盘功能，不恢复 /paper 或 /next/paper 作为核心入口。
- 不把云端改成 Web-only。
- 不停止 MySQL、Redis、Web、Go hot-read、核心 runtime-worker。
- 未获明确授权前，不修改线上 .env、不重启/重建容器、不部署、不切流、不清理线上资源、不写生产数据库。

多 Agent 分工：
- trading-platform-supervisor：总控、阶段门禁、授权点、提交拆分。
- devops-operator：runbook、deploy/quick deploy、budget verify、线上只读验收和回滚命令。
- fullstack-builder：runtime task 门控、removed paper task skipped、scheduler embed、测试。
- qa-tester：pytest、frontend-next npm checks、Playwright、HTTP smoke、长稳观察。
- product-strategist/ui-designer：旧前端和模拟盘入口收口，确认页面说明和验证脚本不再依赖 retired path。
- trading-quant-lead/stock-analysis-specialist：确认策略语义、生产排序、市场解释口径不变。

实施顺序：
1. D0 只读基线和安全门。
2. D1 新增 cloud-core-worker-resource-runbook，并在 .env.deploy.local.example 增加授权止血 profile 示例。
3. D2 增强 scripts/verify_platform_budget.py，覆盖 low-priority pause 与 embedded scheduler 状态。
4. D3 增强 deploy_cloud_server.sh、quick_cloud_deploy.sh、plan_platform_maintenance_window.py 支持 DEPLOY_EMBED_RUNTIME_SCHEDULER=1，默认行为不变。
5. D4 收口旧前端和模拟盘残留验证路径：frontend-next 脚本不再以 /paper 或 /next/paper 为 active 页面，不恢复模拟盘写流程；PRODUCTION_RUNBOOK 更新当前核心保护环路。
6. D5-D6 线上动作只在用户明确授权后执行：先非核心任务止血并观察，再启用 embedded scheduler 并验证 heartbeat 与核心任务。
7. D7-D9 分别处理 MySQL/机器规格、完整交易日稳定性、域名 TLS reset。

测试要求：
- PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_platform_budget_verifier.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_independent_runtime_components.py backend/tests/test_runtime_task_queue.py backend/tests/test_phase4_runtime_worker_tasks.py backend/tests/test_frontend_next_level1_cutover.py
- cd frontend-next && npm run api:check && npm run lint && npm test -- --run && npm run build
- 若改到 Playwright 覆盖面，运行相关 e2e smoke。

输出要求：
- 每个批次一个小 commit。
- 写入 docs/reports/cloud-resource-contention-rollout-2026-06-11.md，记录执行命令、测试结果、线上是否写操作、未执行项、风险、回滚。
- 最终答复必须说明：当前是否已执行线上写操作、核心功能是否受影响、资源瓶颈是否缓解、仍需用户授权的下一步。
```

## 19. Agent-Specific Prompts

### 19.1 DevOps Prompt

```text
你是 devops-operator。只处理 docs/operations、PRODUCTION_RUNBOOK.md、.env.deploy.local.example、scripts/deploy_cloud_server.sh、scripts/quick_cloud_deploy.sh、scripts/plan_platform_maintenance_window.py、scripts/verify_platform_budget.py 和相关测试。目标是让非核心任务止血和 embedded scheduler 有明确 runbook、deploy flag、verify 兼容和回滚路径。默认不做线上写操作。修改前后执行 git status --short；运行 backend/tests/test_cloud_deploy_scripts.py、backend/tests/test_independent_runtime_components.py、backend/tests/test_platform_budget_verifier.py。不得改策略语义、不得改 priority board 口径。
```

### 19.2 Backend Prompt

```text
你是 fullstack-builder。只处理 runtime task、runtime worker、scheduler embed、removed paper residual skip 和后端测试。目标是保证 low-priority pause 生效、已停模拟盘任务进入 skipped_removed_feature 而不是失败重试、scheduler embed 不重复入队、不影响 monitor/quote cache/low-buy/priority board/strategy tracking/watchdog。禁止恢复 active paper 功能；禁止改 strategy_policy.py、production_score、priority_board 排序。运行 backend/tests/test_runtime_task_queue.py、backend/tests/test_phase4_runtime_worker_tasks.py、backend/tests/test_platform_budget_verifier.py。
```

### 19.3 Frontend And Product Prompt

```text
你是 product-strategist + ui-designer。只处理 frontend-next 验证脚本、页面入口说明和 PRODUCTION_RUNBOOK 当前产品口径。旧 frontend/ 已退役且不应恢复；模拟盘 active 功能已停，不要把 /paper 或 /next/paper 作为核心页面继续验收。把 smoke/page matrix 改为 /next/monitor、/next/monitor/market、/next/strategy-tracking、/next/analysis、/next/backtest、/next/data、/next/settings。运行 npm run api:check、npm run lint、npm test -- --run、npm run build。不得改后端策略语义或 API 契约，generated api-types 不手改。
```

### 19.4 QA Prompt

```text
你是 qa-tester。为本计划建立验收矩阵：pytest、frontend-next npm checks、Playwright smoke、curl HTTP smoke、线上只读资源快照、runtime task 状态、scheduler heartbeat、MySQL 状态、Redis 状态。任何线上写操作必须等用户明确授权。报告写入 docs/reports/cloud-resource-contention-rollout-2026-06-11.md，区分 PASS/FAIL/BLOCKED，并列出证据、影响和回滚建议。
```

### 19.5 Strategy Review Prompt

```text
你是 trading-quant-lead + stock-analysis-specialist。审查本批改动是否触碰生产策略语义、production_score、priority_board 排序、低吸榜口径、策略追踪解释口径和市场状态解释。只做审查和结论，不新增策略规则，不改 strategy_policy.py。输出“通过/阻断/需补证据”，并指出具体文件和风险。
```

## 20. Final Decision

最优路线是：

1. 先停非核心任务止血，降低 worker/MySQL 资源争抢。
2. 再合并 scheduler，减少一个常驻 Python 容器和重复调度风险。
3. 最后按证据处理 MySQL memory limit、buffer pool、慢查询、机器规格。
4. 旧前端和模拟盘只做收口和防回流，不恢复为核心产品路径。
5. 域名 TLS reset 独立处理，不把它误判成应用资源问题。

这不是“彻底解决所有线上问题”的单一开关，但它是当前不影响重心任务的最优执行路线。
