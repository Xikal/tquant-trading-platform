# Cloud Resource Contention Final Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 通过“非核心任务止血 + 云端核心小闭环 + scheduler 合并 + MySQL/worker 根因治理”解决线上云服务器资源争抢导致的卡顿，同时保证监控、行情缓存、低吸榜、priority board、策略追踪持续可用。

**Architecture:** 云端保留 Web、MySQL、Redis、Go 热读/扫描、最小 runtime-worker；analytics/backtest/ML/factor/data repair 等重任务改为本地或按需运行。先用现有 feature flag 和 compose env 降低非核心任务，再用 `RUNTIME_WORKER_EMBED_SCHEDULER=true` 合并 scheduler，最后治理 MySQL 慢查询和核心任务重复刷新。

**Tech Stack:** Docker Compose, FastAPI, MySQL 8.4, Redis 7, Python runtime worker, Go BFF/market/scan services, Playwright/curl smoke checks, existing runtime task queue.

---

## 0. 适用范围与硬边界

### 0.1 本计划解决什么

本计划主要解决“云服务器资源争抢导致的卡顿”：

- 云服务器内存长期吃紧。
- swap 持续使用或上涨。
- worker、扫描、刷新、回测、Web 抢 CPU/IO。
- 页面/API 在数据刷新或策略物化时变慢。
- runtime 任务队列被低优先级任务挤占。
- 部署后容器资源恢复慢。

### 0.2 本计划不承诺解决什么

以下问题必须作为独立事项处理：

- `weisilianghua.cloud` TLS/SNI connection reset。
- MySQL 慢查询、索引不足导致的业务慢接口。
- priority board / monitor BFF 代码层查询过重。
- 本地电脑断网、休眠、关机导致本地重任务不跑。
- 本地到云 MySQL/Redis 网络不稳导致的数据刷新延迟。
- 浏览器缓存、旧 chunk、前端资源策略之外的前端 bug。

### 0.3 绝对禁止

- 不改 `backend/app/services/low_buy/strategy_policy.py`。
- 不改变生产策略语义。
- 不改变 `production_score`。
- 不改变 `priority_board` 排序和口径。
- 不改变核心交易日发布门控。
- 不直接清理线上数据库、binlog、volume、镜像或缓存。
- 不直接停 MySQL、Redis、Web、Go 热读/扫描、核心 runtime-worker。
- 不把云端改成纯 Web-only。

### 0.4 需要授权的动作

以下动作必须在用户明确授权和维护窗口内执行：

- 修改线上 `.env`。
- 重建或重启容器。
- 停独立 `runtime-scheduler`。
- 清理 Docker image/build cache。
- 修改 MySQL 配置。
- 停止或归档历史 runtime task。
- 切换域名、CDN/WAF 或公网入口。

---

## 1. 当前线上证据

最近只读快照显示：

| 项 | 状态 |
|---|---:|
| 内存 | `3723MiB total / 3252MiB used / 470MiB available` |
| Swap | `1987MiB total / 659MiB used` |
| 根磁盘 | `32G / 59G, 56%` |
| inode | `11%` |
| `tquant-mysql` | `964.9MiB / 1GiB`, CPU `32.72%` |
| `tquant-runtime-worker-mysql` | `644.5MiB / 768MiB`, CPU `69.23%` |
| `tquant-runtime-scheduler-mysql` | `424.2MiB / 640MiB` |
| `tquant-frontend-web` | `2.867MiB / 128MiB` |
| Docker images | `11.48GB`, reclaimable `8.066GB` |
| Docker build cache | `5.551GB` |

当前资源瓶颈不是前端，也不是磁盘；主要是 MySQL、runtime-worker、runtime-scheduler 以及后台任务入队频率。

最近 24h runtime task 分布显示：

| 任务 | 24h 状态 |
|---|---:|
| `low_buy_materialization_refresh` | succeeded `714`, failed `231`, running `1` |
| `strategy_tracking_snapshot_refresh` | succeeded `417`, queued `1` |
| `market_quote_cache_refresh` | succeeded `385` |
| `hermes_platform_autopilot` | succeeded `293`, queued `1` |
| `a_key_level_materialization_refresh` | succeeded `231`, queued `1` |
| `monitor_snapshot_refresh` | succeeded `127`, queued `2` |
| `latest_data_watchdog` | succeeded `97`, queued `1` |

这说明第一优先级不是继续删前端资源，而是减少非核心 runtime task 对 worker/MySQL 的抢占。

---

## 2. 最终目标拓扑

### 2.1 云端必须保留

| 服务 | 目标状态 | 原因 |
|---|---|---|
| `frontend-web` | 保留 | 线上前端入口 |
| `app` | 保留 | API 与 Web 主服务 |
| `mysql` | 保留 | 核心事实源 |
| `redis` | 保留 | 缓存与事件通道 |
| `go-bff-gateway` | 保留 | monitor/priority 热读聚合 |
| `go-market-read-service` | 保留 | 行情热读 |
| `go-scan-worker` | 保留 | 扫描加速，资源占用低 |
| `runtime-worker` | 保留但瘦身 | 核心任务消费 |

### 2.2 云端改为关闭或按需

| 项 | 目标状态 | 功能影响 |
|---|---|---|
| `analytics-worker` | 默认不常驻 | Parquet/DuckDB/分析导出按需运行 |
| `backtest-worker` | 不常驻 | 长回测按需运行 |
| Prometheus/Grafana | 不常驻 | 独立监控面板按需恢复 |
| `hermes_platform_autopilot` | 关闭 | 自动巡检/自愈建议停止 |
| `MARKET_REVIEW_ENABLED` | 关闭或降级 | 午盘/收盘复盘停止 |
| 低优先级任务 | 暂停 | analytics/backtest/ML/factor/data repair/research 不抢资源 |
| 模拟盘自动任务 | 关闭 | 自动模拟交易停止，已符合用户确认 |

### 2.3 本地或按需承接

- 24M 回测。
- 批量 backtest。
- analytics export。
- DuckDB/Parquet 报告。
- ML/factor mining。
- 数据补齐/数据修复。
- 研究型任务。

---

## 3. 多 Agent 并行分工

### 3.1 总控

`trading-platform-supervisor`

- 维护本计划的任务状态、风险升级、授权点。
- 确认每个阶段没有越过“不改策略语义、不改 priority board 口径”的边界。
- 合并各 Agent 输出，决定是否进入下一阶段。

### 3.2 可并行 Agent

| Agent | 任务范围 | 可并行性 | 不可触碰 |
|---|---|---|---|
| `devops-operator` | compose/env/runbook/维护窗口/线上只读验证 | 可与 QA 并行 | 不直接重启或改线上配置，除非获授权 |
| `fullstack-builder` | runtime task pause、scheduler embed、预算脚本、核心任务守卫 | 可与 DevOps 并行开发 | 不改生产策略公式 |
| `qa-tester` | 本地测试、云端只读验收、p95 对比、核心 API smoke | 可独立并行 | 不造线上写入压测 |
| `product-strategist` | 判断停用项对页面和用户功能的影响，更新说明 | 可并行 | 不扩大功能范围 |
| `trading-quant-lead` | 确认策略语义、生产排序、核心任务清单不变 | 审核门控 | 不新增策略改动 |
| `stock-analysis-specialist` | 确认市场复盘关闭不影响核心选股解释和交易决策 | 审核门控 | 不新增主观规则 |

### 3.3 串行门槛

必须按以下顺序推进：

1. D0 只读基线。
2. D1 非核心任务止血。
3. D2 观察 2-4 小时。
4. D3 scheduler embed 预发/本地验证。
5. D4 维护窗口合并 scheduler。
6. D5 完整交易日观察。
7. D6 MySQL/worker 根因治理。
8. D7 域名链路独立处理。

---

## 4. 文件结构

本计划建议创建或修改的文件如下。执行时必须以实际 checkout 为准，先执行 `git status --short`。

### 4.1 文档与 Runbook

- Create: `docs/operations/cloud-core-worker-resource-runbook.md`
  - 记录线上止血、scheduler 合并、回滚、验收命令。
- Create: `docs/reports/cloud-resource-contention-remediation-YYYY-MM-DD.md`
  - 记录每次线上只读快照、变更、观察结果。
- Modify: `PRODUCTION_RUNBOOK.md`
  - 只追加链接到新 runbook，不复制长文。

### 4.2 配置与部署脚本

- Modify: `.env.production.example`
  - 增加资源瘦身建议配置示例，不改默认生产语义。
- Modify: `docker-compose.mysql.yml`
  - 仅在需要时增加 explicit env 或 profile，不直接删除服务。
- Modify: `scripts/deploy_cloud_server.sh`
  - 增加“核心 worker only / embedded scheduler”部署选项时必须有测试保护。
- Modify: `scripts/quick_cloud_deploy.sh`
  - 增加 verify 对 embedded scheduler 的兼容。
- Modify: `scripts/verify_platform_budget.py`
  - 增强对 scheduler embed、非核心任务暂停、核心任务健康的检查。

### 4.3 后端守卫与测试

- Modify: `backend/app/core/config.py`
  - 只在缺少配置声明时补齐；当前已有关键配置，不应重复新增。
- Modify: `backend/app/runtime/background_jobs.py`
  - 如需增强 compact/core-only 行为，只做门控和日志，不改变核心任务语义。
- Modify: `backend/app/services/tasks/queue.py`
  - 保持低优先级暂停逻辑；如增强 summary，只增加可观测字段。
- Test: `backend/tests/test_cloud_deploy_scripts.py`
- Test: `backend/tests/test_independent_runtime_components.py`
- Test: `backend/tests/test_runtime_task_queue.py`
- Test: `backend/tests/test_platform_budget_verifier.py`

---

## 5. Task D0: Baseline And Safety Gate

**Files:**

- Create: `docs/reports/cloud-resource-contention-remediation-YYYY-MM-DD.md`
- Read only: `AGENTS.md`
- Read only: `docs/engineering-conventions.md`
- Read only: `docker-compose.mysql.yml`
- Read only: `scripts/verify_platform_budget.py`

- [ ] **Step 1: Confirm clean or protected worktree**

Run:

```bash
cd /Users/j/Documents/gupiao
git status --short
```

Expected:

- Empty output means clean.
- If non-empty, list unrelated files in the report and do not overwrite them.

- [ ] **Step 2: Capture local config facts**

Run:

```bash
cd /Users/j/Documents/gupiao
rg -n "RUNTIME_LOW_PRIORITY_TASKS_PAUSED|PLATFORM_AUTOPILOT_ENABLED|MARKET_REVIEW_ENABLED|RUNTIME_WORKER_EMBED_SCHEDULER|analytics-worker|backtest-worker" docker-compose.mysql.yml backend/app/core/config.py backend/app/runtime/background_jobs.py scripts/verify_platform_budget.py
```

Expected:

- Existing config anchors are found.
- No strategy files need edits.

- [ ] **Step 3: Capture read-only online resource baseline**

Run after setting the correct SSH variables:

```bash
ssh -i "$CLOUD_SSH_KEY" -o StrictHostKeyChecking=no "$CLOUD_USER@$CLOUD_HOST" '
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
'
```

Expected:

- No write operation.
- Report includes memory, swap, disk, inode, container status, Docker size.

- [ ] **Step 4: Capture runtime queue distribution**

Run:

```bash
ssh -i "$CLOUD_SSH_KEY" -o StrictHostKeyChecking=no "$CLOUD_USER@$CLOUD_HOST" "
cd /home/ubuntu/gupiao-upload &&
sudo docker exec tquant-mysql sh -lc 'mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -D \"\$MYSQL_DATABASE\" -e \"SELECT status, task_type, priority, COUNT(*) AS cnt, MIN(created_at) AS oldest, MAX(updated_at) AS latest FROM runtime_tasks WHERE status IN ('\''queued'\'', '\''running'\'', '\''failed'\'') GROUP BY status, task_type, priority ORDER BY FIELD(status, '\''running'\'', '\''queued'\'', '\''failed'\''), priority DESC, cnt DESC LIMIT 80; SELECT task_type, status, COUNT(*) AS cnt, MAX(updated_at) AS latest FROM runtime_tasks WHERE created_at >= NOW() - INTERVAL 24 HOUR GROUP BY task_type, status ORDER BY cnt DESC LIMIT 80;\"'
"
```

Expected:

- No write operation.
- Identifies whether non-core tasks are stealing runtime capacity.

- [ ] **Step 5: Write baseline report**

Create `docs/reports/cloud-resource-contention-remediation-YYYY-MM-DD.md` with:

```markdown
# Cloud Resource Contention Remediation Baseline - YYYY-MM-DD

## Scope

Read-only baseline before resource contention remediation.

## Git Status

`git status --short` output:

```text
<paste output>
```

## Resource Snapshot

| Metric | Value |
|---|---|
| Time |  |
| Load average |  |
| Memory |  |
| Swap |  |
| Root disk |  |
| inode |  |

## Container Snapshot

| Container | Status | CPU | Memory |
|---|---|---:|---:|

## Runtime Queue Snapshot

| Task type | Status | Count | Latest |
|---|---|---:|---|

## Candidate Non-Core Stops

| Item | Recommendation | Reason | Expected impact |
|---|---|---|---|

## No Write Operations

This baseline did not modify `.env`, compose files, database rows, containers, images, volumes, nginx, or system services.
```

- [ ] **Step 6: Commit D0 if report is created**

Run:

```bash
git add docs/reports/cloud-resource-contention-remediation-YYYY-MM-DD.md
git commit -m "docs: add cloud resource contention baseline"
```

Expected:

- Commit contains only the baseline report.

---

## 6. Task D1: Non-Core Task Stop Plan

**Files:**

- Create: `docs/operations/cloud-core-worker-resource-runbook.md`
- Modify: `.env.production.example`
- Test: `backend/tests/test_cloud_deploy_scripts.py`
- Test: `backend/tests/test_platform_budget_verifier.py`

- [ ] **Step 1: Add safe env example**

In `.env.production.example`, add this commented block near runtime settings:

```dotenv
# Resource contention mitigation profile.
# Keep cloud Web/API/hot-read/core runtime tasks online, but pause non-core heavy jobs.
# Apply to production .env only during an authorized maintenance window.
PLATFORM_AUTOPILOT_ENABLED=false
RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true
MARKET_REVIEW_ENABLED=false
RUNTIME_STARTUP_CACHE_PREWARM_ENABLED=false
RUNTIME_STARTUP_HISTORY_PREWARM_ENABLED=false
```

Expected:

- Example only; no production default change.
- No secrets.

- [ ] **Step 2: Add deploy-script regression test for removed paper flags**

Verify existing test still covers removed paper flags:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_cloud_deploy_scripts.py::test_cloud_deploy_does_not_write_removed_paper_auto_trading_flag
```

Expected:

- PASS.
- `PAPER_AUTO_TRADING_ENABLED` and `PAPER_PERF_ARCHIVE_ENABLED` are not reintroduced.

- [ ] **Step 3: Add runbook stop matrix**

Create `docs/operations/cloud-core-worker-resource-runbook.md`:

```markdown
# Cloud Core Worker Resource Runbook

## Goal

Reduce cloud resource contention without interrupting monitor, quote cache, low-buy board, priority board, strategy tracking, MySQL, Redis, Web, or Go hot-read services.

## Protected Core

Do not stop:

- `tquant-app-mysql`
- `tquant-frontend-web`
- `tquant-mysql`
- `tquant-redis`
- `tquant-go-bff-gateway`
- `tquant-go-market-read-service`
- `tquant-go-scan-worker`
- `tquant-runtime-worker-mysql`

## Non-Core Stops

| Setting or service | Target | Effect |
|---|---|---|
| `PLATFORM_AUTOPILOT_ENABLED` | `false` | Stop platform autopilot tasks |
| `RUNTIME_LOW_PRIORITY_TASKS_PAUSED` | `true` | Pause analytics/backtest/ML/factor/data repair/research tasks |
| `MARKET_REVIEW_ENABLED` | `false` | Stop midday/close market review reports |
| `analytics-worker` | on-demand only | Stop analytics export from running constantly |
| `backtest-worker` | on-demand only | Keep long backtests out of cloud steady state |

## Authorized Change Commands

These commands are examples for a maintenance window. Do not run them during read-only audit.

```bash
cd /home/ubuntu/gupiao-upload
cp .env ".env.backup.$(date +%Y%m%d%H%M%S)"
python3 - <<'PY'
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
```

## Rollback Commands

```bash
cd /home/ubuntu/gupiao-upload
cp .env.backup.YYYYMMDDHHMMSS .env
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate app runtime-worker runtime-scheduler
```

## Post-Change Checks

```bash
curl -sS -f --max-time 10 http://127.0.0.1:18090/readyz
curl -sS -o /tmp/monitor.json -w "%{http_code} %{time_total}\n" --max-time 20 http://127.0.0.1:18090/api/monitor
curl -sS -o /tmp/priority.json -w "%{http_code} %{time_total}\n" --max-time 20 http://127.0.0.1:18090/api/priority-board
sudo docker stats --no-stream
```
```

Expected:

- Runbook clearly separates examples from executed commands.
- Includes rollback.

- [ ] **Step 4: Verify platform budget script still passes locally**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_platform_budget_verifier.py backend/tests/test_cloud_deploy_scripts.py
```

Expected:

- PASS.

- [ ] **Step 5: Commit D1**

Run:

```bash
git add .env.production.example docs/operations/cloud-core-worker-resource-runbook.md backend/tests/test_cloud_deploy_scripts.py backend/tests/test_platform_budget_verifier.py
git commit -m "docs: add cloud core worker resource runbook"
```

Expected:

- Commit includes docs and any tests changed for documentation guards only.

---

## 7. Task D2: Runtime Queue And Core-Only Guard

**Files:**

- Modify: `scripts/verify_platform_budget.py`
- Test: `backend/tests/test_platform_budget_verifier.py`
- Test: `backend/tests/test_runtime_task_queue.py`

- [ ] **Step 1: Add expected steady-state checks**

Extend `scripts/verify_platform_budget.py` with a resource profile check:

```python
CORE_REQUIRED_TRUE_OR_PRESENT = {
    "runtime_worker": {
        "RUNTIME_LOW_PRIORITY_TASKS_PAUSED": "true",
    },
    "runtime_scheduler": {
        "RUNTIME_LOW_PRIORITY_TASKS_PAUSED": "true",
    },
}


def evaluate_core_resource_profile(report: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    roles = report.get("roles", {})
    for role_name, expected in CORE_REQUIRED_TRUE_OR_PRESENT.items():
        env = roles.get(role_name, {}).get("env", {})
        for key, value in expected.items():
            if str(env.get(key, "")).lower() != value:
                warnings.append(f"core_resource_profile:{role_name}:{key}={env.get(key, 'missing')}")
    return warnings
```

Then call it inside `evaluate()`:

```python
warnings.extend(evaluate_core_resource_profile(report))
```

Expected:

- Script warns if low priority pause is not active for worker/scheduler.
- Does not block local development by default.

- [ ] **Step 2: Add verifier test**

Add to `backend/tests/test_platform_budget_verifier.py`:

```python
def test_core_resource_profile_warns_when_low_priority_not_paused():
    from scripts.verify_platform_budget import evaluate

    report = {
        "mysql": {"max_connections": 120},
        "pool_budget": {"total": 12},
        "roles": {
            "web": {"env": {"RUNTIME_BACKGROUND_JOBS_ENABLED": "false", "TQUANT_ANALYTICS_ENABLED": "false"}},
            "runtime_worker": {"container_present": True, "env": {"RUNTIME_LOW_PRIORITY_TASKS_PAUSED": "false"}},
            "runtime_scheduler": {"container_present": True, "env": {"RUNTIME_LOW_PRIORITY_TASKS_PAUSED": "false"}},
        },
        "commands": {"compose_config": {"returncode": 0}, "mysql_status": {"returncode": 0}},
    }

    result = evaluate(report, {"mysql_max_connections": 120, "pool_budget": 40})

    assert result["status"] == "warning"
    assert "core_resource_profile:runtime_worker:RUNTIME_LOW_PRIORITY_TASKS_PAUSED=false" in result["warnings"]
    assert "core_resource_profile:runtime_scheduler:RUNTIME_LOW_PRIORITY_TASKS_PAUSED=false" in result["warnings"]
```

Expected:

- Test fails before implementation if function not wired.
- Test passes after implementation.

- [ ] **Step 3: Verify runtime queue pause behavior**

Run existing queue tests:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_runtime_task_queue.py::test_runtime_task_queue_pauses_configured_low_priority_tasks backend/tests/test_runtime_task_queue.py::test_runtime_task_summary_reports_paused_low_priority_backlog
```

Expected:

- PASS.
- Confirms low-priority pause is enforced by queue claim behavior.

- [ ] **Step 4: Run verifier tests**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_platform_budget_verifier.py
```

Expected:

- PASS.

- [ ] **Step 5: Commit D2**

Run:

```bash
git add scripts/verify_platform_budget.py backend/tests/test_platform_budget_verifier.py
git commit -m "test: guard cloud core resource profile"
```

Expected:

- Commit contains only verifier and tests.

---

## 8. Task D3: Embedded Scheduler Deployment Guard

**Files:**

- Modify: `scripts/deploy_cloud_server.sh`
- Modify: `scripts/quick_cloud_deploy.sh`
- Modify: `scripts/verify_platform_budget.py`
- Test: `backend/tests/test_cloud_deploy_scripts.py`
- Test: `backend/tests/test_independent_runtime_components.py`

- [ ] **Step 1: Add deploy mode flag**

Add a deploy env switch to `scripts/deploy_cloud_server.sh`:

```bash
embedded_scheduler_enabled() {
  case "$(printf '%s' "${DEPLOY_EMBED_RUNTIME_SCHEDULER:-0}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

runtime_worker_services() {
  if embedded_scheduler_enabled; then
    printf 'runtime-worker'
  else
    printf 'runtime-scheduler runtime-worker'
  fi
}

removed_runtime_scheduler_container() {
  if embedded_scheduler_enabled; then
    sudo docker rm -f tquant-runtime-scheduler-mysql 2>/dev/null || true
  fi
}
```

Call `removed_runtime_scheduler_container` immediately after `stop_removed_backtest_worker` in worker update branches.

Expected:

- Default behavior unchanged.
- Scheduler is removed only when `DEPLOY_EMBED_RUNTIME_SCHEDULER` is explicitly true.

- [ ] **Step 2: Ensure env is upserted only when explicitly requested**

In deploy script remote env update section, add:

```bash
if embedded_scheduler_enabled; then
  upsert_env_value RUNTIME_WORKER_EMBED_SCHEDULER true
  upsert_env_value RUNTIME_SCHEDULER_BACKGROUND_JOBS_ENABLED false
fi
```

Expected:

- Without the flag, no production behavior changes.
- With the flag, worker embeds scheduler and standalone scheduler background loop is disabled.

- [ ] **Step 3: Update quick verification**

In `scripts/quick_cloud_deploy.sh`, gate scheduler wait:

```bash
if test "${DEPLOY_EMBED_RUNTIME_SCHEDULER:-0}" = "1" || test "${DEPLOY_EMBED_RUNTIME_SCHEDULER:-}" = "true"; then
  echo "runtime_scheduler:embedded"
else
  wait_for_container tquant-runtime-scheduler-mysql
fi
```

Expected:

- Existing deployments still wait for scheduler.
- Embedded deployments do not fail because standalone scheduler is absent.

- [ ] **Step 4: Add script tests**

Add to `backend/tests/test_cloud_deploy_scripts.py`:

```python
def test_deploy_supports_explicit_embedded_runtime_scheduler_mode() -> None:
    deploy_script = read_repo_file("scripts/deploy_cloud_server.sh")
    quick_script = read_repo_file("scripts/quick_cloud_deploy.sh")

    assert "DEPLOY_EMBED_RUNTIME_SCHEDULER" in deploy_script
    assert "embedded_scheduler_enabled()" in deploy_script
    assert "RUNTIME_WORKER_EMBED_SCHEDULER" in deploy_script
    assert "RUNTIME_SCHEDULER_BACKGROUND_JOBS_ENABLED" in deploy_script
    assert "tquant-runtime-scheduler-mysql" in deploy_script
    assert "runtime_scheduler:embedded" in quick_script
```

Expected:

- Test fails before implementation.
- Test passes after implementation.

- [ ] **Step 5: Keep compose topology test green**

Run:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_cloud_deploy_scripts.py::test_deploy_supports_explicit_embedded_runtime_scheduler_mode backend/tests/test_independent_runtime_components.py::test_runtime_services_are_independent_in_mysql_compose
```

Expected:

- PASS.
- Compose still declares both worker and scheduler; deploy flag controls runtime behavior.

- [ ] **Step 6: Commit D3**

Run:

```bash
git add scripts/deploy_cloud_server.sh scripts/quick_cloud_deploy.sh backend/tests/test_cloud_deploy_scripts.py
git commit -m "feat: add explicit embedded scheduler deploy mode"
```

Expected:

- Commit contains only deployment guard changes.

---

## 9. Task D4: Authorized Online Stop And Observation

**Files:**

- Modify only after authorization: remote `/home/ubuntu/gupiao-upload/.env`
- Create: `docs/reports/cloud-resource-contention-remediation-YYYY-MM-DD.md`

- [ ] **Step 1: Confirm authorization**

Required plain-language approval:

```text
授权在维护窗口修改线上 .env，并重启 app/runtime-worker/runtime-scheduler。
```

Expected:

- Without this approval, do not execute any command in this task.

- [ ] **Step 2: Apply non-core stop profile**

Run only after authorization:

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

- Only app/runtime-worker/runtime-scheduler are recreated.
- MySQL/Redis/Go/Frontend are not restarted by this command.

- [ ] **Step 3: Observe for 2-4 hours**

Run every 30 minutes:

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
date
uptime
free -m
cd /home/ubuntu/gupiao-upload
sudo docker stats --no-stream --format "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | sort
curl -sS -o /tmp/readyz.json -w "readyz %{http_code} %{time_total}\n" --max-time 10 http://127.0.0.1:18090/readyz
curl -sS -o /tmp/monitor.json -w "monitor %{http_code} %{time_total}\n" --max-time 20 http://127.0.0.1:18090/api/monitor
curl -sS -o /tmp/priority.json -w "priority %{http_code} %{time_total}\n" --max-time 20 http://127.0.0.1:18090/api/priority-board
'
```

Expected:

- `/readyz` 200.
- `/api/monitor` 200.
- `/api/priority-board` 200.
- available memory improves or stabilizes.
- swap does not continue rising.

- [ ] **Step 4: Record observation**

Append to report:

```markdown
## D4 Non-Core Stop Observation

| Time | Available memory | Swap used | Runtime worker CPU/Mem | MySQL CPU/Mem | readyz | monitor | priority-board |
|---|---:|---:|---|---|---|---|---|

## Decision

- Continue to D5 embedded scheduler: yes/no
- Reason:
- Rollback required: yes/no
```

Expected:

- Evidence is enough to decide whether to proceed.

---

## 10. Task D5: Authorized Embedded Scheduler Cutover

**Files:**

- Modify only after authorization: remote `/home/ubuntu/gupiao-upload/.env`
- Create or update: `docs/reports/cloud-resource-contention-remediation-YYYY-MM-DD.md`

- [ ] **Step 1: Confirm authorization**

Required approval:

```text
授权在维护窗口启用 RUNTIME_WORKER_EMBED_SCHEDULER=true，并停独立 runtime-scheduler。
```

Expected:

- Without this approval, do not execute any command in this task.

- [ ] **Step 2: Apply embedded scheduler**

Run only after authorization:

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

- Runtime worker restarts with embedded scheduler.
- Standalone scheduler is stopped after worker is healthy.

- [ ] **Step 3: Verify scheduler heartbeat**

Run:

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" "
cd /home/ubuntu/gupiao-upload &&
sudo docker exec tquant-mysql sh -lc 'mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -D \"\$MYSQL_DATABASE\" -e \"SELECT component, worker_id, status, updated_at FROM platform_component_heartbeats WHERE component = '\''runtime-scheduler'\'' ORDER BY updated_at DESC LIMIT 5;\"'
"
```

Expected:

- Latest heartbeat worker id is `runtime-worker-embedded-scheduler`.
- Status is `running`.

- [ ] **Step 4: Verify core tasks over one trading day**

Run at least after open, midday, close:

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" "
cd /home/ubuntu/gupiao-upload &&
sudo docker exec tquant-mysql sh -lc 'mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -D \"\$MYSQL_DATABASE\" -e \"SELECT task_type, status, COUNT(*) cnt, MAX(updated_at) latest FROM runtime_tasks WHERE created_at >= NOW() - INTERVAL 8 HOUR AND task_type IN ('\''monitor_snapshot_refresh'\'','\''market_pulse_refresh'\'','\''low_buy_materialization_refresh'\'','\''strategy_tracking_snapshot_refresh'\'','\''market_quote_cache_refresh'\'','\''latest_data_watchdog'\'') GROUP BY task_type, status ORDER BY task_type, status;\"'
"
```

Expected:

- Core tasks continue to enqueue and complete.
- No sustained growth in queued/running backlog.

- [ ] **Step 5: Rollback if heartbeat or tasks fail**

Run only if required:

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
set -e
cd /home/ubuntu/gupiao-upload
cp .env.scheduler-backup.YYYYMMDDHHMMSS .env
sudo docker compose -f docker-compose.mysql.yml up -d --no-deps --force-recreate runtime-worker runtime-scheduler
'
```

Expected:

- Standalone scheduler restored.
- Worker restored to prior config.

- [ ] **Step 6: Commit D5 report**

Run locally:

```bash
git add docs/reports/cloud-resource-contention-remediation-YYYY-MM-DD.md
git commit -m "docs: record embedded scheduler cutover observation"
```

Expected:

- Report includes before/after memory, swap, queue, heartbeat, and rollback status.

---

## 11. Task D6: MySQL And Core Worker Root-Cause Work

**Files:**

- Create: `docs/reports/mysql-worker-root-cause-review-YYYY-MM-DD.md`
- Modify only if evidence proves need: core read-path tests and services
- Test: `backend/tests/test_low_buy_read_paths.py`
- Test: `backend/tests/test_low_buy_priority_board_strategy_variants.py`
- Test: `backend/tests/test_low_buy_production_scoring.py`

- [ ] **Step 1: Capture MySQL read-only facts**

Run:

```bash
ssh -i "$CLOUD_SSH_KEY" "$CLOUD_USER@$CLOUD_HOST" '
cd /home/ubuntu/gupiao-upload
sudo docker exec tquant-mysql sh -lc '"'"'
mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -D "$MYSQL_DATABASE" -e "
SHOW GLOBAL STATUS LIKE '\''Threads_connected'\'';
SHOW GLOBAL STATUS LIKE '\''Threads_running'\'';
SHOW GLOBAL STATUS LIKE '\''Slow_queries'\'';
SHOW VARIABLES LIKE '\''max_connections'\'';
SHOW VARIABLES LIKE '\''innodb_buffer_pool_size'\'';
SHOW VARIABLES LIKE '\''long_query_time'\'';
SHOW VARIABLES LIKE '\''slow_query_log'\'';
SELECT table_schema, ROUND(SUM(data_length+index_length)/1024/1024,1) mb FROM information_schema.tables WHERE table_schema = DATABASE() GROUP BY table_schema;
"
'"'"'
'
```

Expected:

- No write operation.
- Report can distinguish connection pressure, memory pressure, and slow-query pressure.

- [ ] **Step 2: Measure hot endpoint p95**

Run:

```bash
python3 scripts/measure_cloud_go_rust_performance.py --host "$CLOUD_HOST" --ssh-key "$CLOUD_SSH_KEY" --rounds 2 --samples 8
```

Expected:

- Produces p95 for monitor BFF, priority board, Go services.
- Does not change strategy output.

- [ ] **Step 3: Only optimize code after query-count evidence**

If and only if query-count tests prove linear query growth, modify read paths. Required tests:

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py
```

Expected:

- PASS.
- priority board ordering, `production_score`, `priority_score`, lane, and shadow fields are unchanged.

- [ ] **Step 4: Commit D6 report or code**

If report only:

```bash
git add docs/reports/mysql-worker-root-cause-review-YYYY-MM-DD.md
git commit -m "docs: add mysql worker root cause review"
```

If code changed:

```bash
git add backend/app backend/tests docs/reports/mysql-worker-root-cause-review-YYYY-MM-DD.md
git commit -m "perf: reduce core worker database pressure"
```

Expected:

- Code commit must include evidence and guard tests.

---

## 12. Task D7: Domain TLS/SNI Separate Track

**Files:**

- Create: `docs/operations/domain-entry-runbook.md`
- Create: `docs/reports/domain-entry-review-YYYY-MM-DD.md`

- [ ] **Step 1: Confirm failure mode**

Run:

```bash
curl -vk --connect-timeout 10 --max-time 20 https://weisilianghua.cloud/readyz
curl -vk --resolve weisilianghua.cloud:443:<SERVER_IP> --connect-timeout 10 --max-time 20 https://weisilianghua.cloud/readyz
curl -sS -o /tmp/ip_readyz.json -w "%{http_code} %{time_total}\n" --connect-timeout 10 --max-time 20 https://<SERVER_IP>/readyz
```

Expected:

- Distinguishes domain/SNI/public entry issue from app health.

- [ ] **Step 2: Write options**

Create report with:

```markdown
# Domain Entry Review - YYYY-MM-DD

## Evidence

| Check | Result |
|---|---|

## Options

| Option | Fixes | Risk | Rollback |
|---|---|---|---|
| Change domain | TLS/SNI RST | DNS propagation | Restore DNS |
| Add CDN/WAF | Public entry instability | Cache and WAF config | Bypass CDN |
| Fix Nginx/cert/SNI | Certificate or SNI mismatch | Requires entry reload | Restore config |

## Recommendation

Treat domain chain separately from cloud resource contention.
```

Expected:

- No resource-task changes mixed into domain track.

---

## 13. Acceptance Criteria

### 13.1 Resource

| Metric | Target |
|---|---|
| available memory | stable `800MiB-1GiB+` after D5, or clearly improved from baseline |
| swap | not continuously increasing |
| `runtime-worker` CPU | not long-running at high utilization outside scheduled refresh |
| `runtime-scheduler` | absent only after embedded scheduler heartbeat proves healthy |
| Docker disk | root disk below operational threshold; cleanup requires separate authorization |

### 13.2 Functional

| Area | Required result |
|---|---|
| `/readyz` | 200 |
| `/api/monitor` | 200 |
| `/api/priority-board` | 200 |
| `/next/monitor` | renders |
| `/next/monitor/market` | renders |
| `/next/strategy-tracking` | renders |
| priority board | ordering and口径 unchanged |
| `production_score` | unchanged |
| strategy semantics | unchanged |

### 13.3 Runtime tasks

Core tasks must continue:

- `monitor_snapshot_refresh`
- `market_pulse_refresh`
- `low_buy_materialization_refresh`
- `strategy_tracking_snapshot_refresh`
- `market_quote_cache_refresh`
- `latest_data_watchdog`
- scheduler heartbeat

Non-core tasks may pause:

- analytics export tasks.
- 24M reports.
- ML/factor mining.
- research backtests.
- data backfill/repair.
- market review.
- autopilot.
- paper auto tasks.

---

## 14. Final Implementation Prompt

Copy this prompt into a new agent session when ready to implement. It assumes the implementer has access to `/Users/j/Documents/gupiao` and must follow this plan.

```text
你在 /Users/j/Documents/gupiao 项目中工作。目标：按 docs/superpowers/plans/2026-06-11-cloud-resource-contention-final-remediation.md 实施“云服务器资源争抢卡顿治理”方案。该方案分三层：先停非核心任务止血，再合并 scheduler 到 runtime-worker，最后处理 MySQL/worker 根因。允许多 Agent 并行，但必须由 trading-platform-supervisor 控制顺序和授权点。

开始前必须执行：
1. cd /Users/j/Documents/gupiao && git status --short
2. 阅读 AGENTS.md、docs/engineering-conventions.md、docs/superpowers/plans/2026-06-11-cloud-resource-contention-final-remediation.md
3. 阅读 docker-compose.mysql.yml、backend/app/core/config.py、backend/app/runtime/background_jobs.py、backend/app/services/tasks/queue.py、scripts/verify_platform_budget.py、scripts/deploy_cloud_server.sh、scripts/quick_cloud_deploy.sh

硬边界：
- 不改 backend/app/services/low_buy/strategy_policy.py。
- 不改变生产策略语义、production_score、priority_board 排序和口径。
- 不停 MySQL、Redis、Web、Go 热读/扫描、核心 runtime-worker。
- 不把云端改成纯 Web-only。
- 未经用户明确授权，不修改线上 .env，不重启容器，不清理 Docker，不改 MySQL，不停 runtime-scheduler。
- analytics/backtest/ML/factor/data repair/research/paper auto 属于非核心，可以通过配置计划为关闭或按需，但线上执行必须等授权。

多 Agent 分工：
1. trading-platform-supervisor：总控顺序、风险升级、授权检查、合并报告。
2. devops-operator：D0/D1/D3/D4/D5，负责 runbook、deploy 脚本、线上只读快照、维护窗口命令和回滚。
3. fullstack-builder：D2/D3/D6，负责 verify_platform_budget、runtime queue guard、embedded scheduler 兼容、必要测试。
4. qa-tester：负责 D0-D6 验收矩阵，curl/API/Playwright/pytest/p95 对比。
5. product-strategist：确认关闭 autopilot、market review、analytics/backtest 常驻、模拟盘自动任务对页面和用户功能的影响说明。
6. trading-quant-lead 与 stock-analysis-specialist：只做边界审核，确认核心选股、排序、信号语义不变，不新增策略。

执行顺序：
D0 只读基线：输出 docs/reports/cloud-resource-contention-remediation-YYYY-MM-DD.md，包含 git status、资源、docker stats、runtime queue、HTTP/API、未执行写操作。
D1 非核心任务止血文档与示例：新增 docs/operations/cloud-core-worker-resource-runbook.md，必要时补 .env.production.example 注释块；不得直接改线上。
D2 增强资源预算/低优先级任务 guard：优先测试 scripts/verify_platform_budget.py 和 backend/tests/test_runtime_task_queue.py。
D3 增加 explicit embedded scheduler deploy mode：默认行为不变，只有 DEPLOY_EMBED_RUNTIME_SCHEDULER=true 才 upsert RUNTIME_WORKER_EMBED_SCHEDULER=true 并允许移除 standalone scheduler。
D4 只有用户授权后，才执行线上非核心止血配置和有限重启；观察 2-4 小时。
D5 只有用户授权后，才启用 RUNTIME_WORKER_EMBED_SCHEDULER=true 并停独立 runtime-scheduler；观察完整交易日。
D6 用证据处理 MySQL/worker 根因，先慢查询/连接池/队列/endpoint p95，只有 query-count 证明需要时才改核心读路径。
D7 域名 TLS/SNI RST 单独成文处理，不和资源治理混在一起。

测试最低要求：
- PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_platform_budget_verifier.py backend/tests/test_runtime_task_queue.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_independent_runtime_components.py
- 涉及 priority board/read path 时必须额外跑：
  PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py
- 部署脚本变更必须证明默认路径行为不变，embedded scheduler 只有显式 flag 生效。

线上验收必须记录：
- uptime/load/free/swap/df/df -ih/docker ps/docker stats/docker system df
- runtime_tasks 核心任务入队和完成情况
- scheduler heartbeat，embedded 后 worker_id 应为 runtime-worker-embedded-scheduler
- /readyz、/api/monitor、/api/priority-board 状态码和耗时
- /next/monitor、/next/monitor/market、/next/strategy-tracking 页面可用
- 本轮是否执行写操作、重启、清理、部署

交付要求：
- 每个阶段一个小提交，提交信息表达阶段。
- 报告必须明确列出：正常/异常/风险、证据、影响、根因判断、回滚方案、下一步。
- 如果需要线上写操作但未授权，只记录建议命令，不执行。
```

---

## 15. Self-Review

### 15.1 Coverage

| Requirement | Covered by |
|---|---|
| 非核心任务止血 | D1, D4 |
| 云端保留核心小 worker | Section 2, D1 |
| scheduler 合并 | D3, D5 |
| MySQL/worker 根因治理 | D6 |
| TLS/SNI 独立处理 | D7 |
| 多 Agent 并行 | Section 3 |
| 不影响重心任务 | Sections 0, 2, 13 |
| 提示词 | Section 14 |

### 15.2 Placeholder Scan

This plan does not use `TBD`, `TODO`, or “implement later”. Date-bearing report names use `YYYY-MM-DD` because each execution must stamp the actual run date.

### 15.3 Type And Command Consistency

All named env variables exist in the current config or compose surface:

- `PLATFORM_AUTOPILOT_ENABLED`
- `RUNTIME_LOW_PRIORITY_TASKS_PAUSED`
- `MARKET_REVIEW_ENABLED`
- `RUNTIME_WORKER_EMBED_SCHEDULER`
- `RUNTIME_SCHEDULER_BACKGROUND_JOBS_ENABLED`

All protected core tasks and service names match the current MySQL compose topology.
