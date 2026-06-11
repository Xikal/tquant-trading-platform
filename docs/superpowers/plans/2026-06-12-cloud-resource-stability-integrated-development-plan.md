# Cloud Resource Stability Integrated Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` for parallel local implementation and review, or `superpowers:executing-plans` for serialized execution. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 通过“非核心任务止血、调度结构合并、MySQL/worker 根因治理、旧前端退役收口、长时间稳定性验证”降低线上资源争抢导致的卡顿，同时保证监控、行情缓存、低吸榜、priority board、策略追踪继续运行。

**Architecture:** 云端保持核心小闭环：`frontend-next`、FastAPI app、MySQL、Redis、Go hot-read/scan、最小 runtime-worker。非核心重任务默认停用或按需运行；scheduler 只在完整交易日 gate 通过后合并进 runtime-worker；MySQL/慢查询/机器规格作为最后根因层处理。

**Tech Stack:** Docker Compose, FastAPI, MySQL 8.4, Redis 7, Python RuntimeTask queue, Go BFF/market/scan services, SolidJS `frontend-next`, Playwright/curl/SSH read-only probes, existing budget verifier and cloud observation scripts.

---

## 1. 背景与当前事实

本计划融合四条线：

1. 线上资源争抢最终方案：先停非核心任务止血，再合并 scheduler，最后处理 MySQL/机器规格根因。
2. 线上稳定性验证：短窗验证已证明 IP 入口可用，但仍缺完整交易日长窗稳定性证据。
3. 模拟盘状态修正：active 模拟盘入口已移除，不应恢复 `/paper` 或新增模拟盘暂停开关；只处理历史 paper 残留任务。
4. 旧前端退役收口：当前本地 `git ls-files frontend` 为 `0`，本地 `frontend/` 目录不存在；后续重点是防回归 guard、脚本/文档残留收口和线上部署链路验证。

当前代码里已经存在的能力，后续 Agent 必须先复核再决定是否补强：

| 能力 | 当前锚点 | 处理原则 |
|---|---|---|
| removed paper task skipped | `backend/app/workers/runtime_worker.py`, `backend/app/services/tasks/queue.py`, `backend/tests/test_phase4_runtime_worker_tasks.py` | 不重复造 `PAPER_RUNTIME_TASKS_ENABLED`；只补缺口或报告证据 |
| low_buy 非生产缺失隔离 | `backend/app/services/low_buy_materialization.py`, `backend/tests/test_low_buy_materialization_priority_board.py` | 不改 `strategy_policy.py`、不改分数/排序 |
| provider degraded backoff | `backend/app/services/market/regime.py`, `backend/app/core/config.py` | 只做观测和必要降级补强 |
| embedded scheduler 部署守卫 | `scripts/deploy_cloud_server.sh`, `scripts/quick_cloud_deploy.sh`, `scripts/verify_platform_budget.py` | D5 前只读 gate，不直接停 scheduler |
| 旧前端运行链路退役 | `backend/tests/test_frontend_next_level1_cutover.py`, `backend/tests/test_deploy_scope.py`, `backend/tests/test_cloud_deploy_scripts.py` | 禁止恢复旧前端入口 |

## 2. 本方案能解决什么

方案主要解决“云服务器资源争抢导致的卡顿”：

- 云服务器内存长期吃紧。
- swap 持续使用或上涨。
- runtime-worker、scheduler、扫描、刷新、回测、Web 抢 CPU/IO。
- 页面/API 在数据刷新、低吸物化或策略快照刷新时变慢。
- 低优先级任务挤占 RuntimeTask queue。
- 部署后容器资源恢复慢。

方案不能单独解决：

- `weisilianghua.cloud` TLS/SNI connection reset。
- MySQL 本身慢查询、索引不足、表膨胀。
- priority board / monitor BFF 代码层查询过重。
- 本地电脑断网、休眠、关机导致本地重任务不跑。
- 本地到云 MySQL/Redis 网络不稳导致数据刷新延迟。
- 浏览器缓存、旧 chunk、前端资源策略之外的前端 bug。

准确目标是：先把“云端资源争抢”这一类问题基本消掉，再用观测数据判断 MySQL/查询/机器规格是否仍是瓶颈。

## 3. 硬边界

全程遵守：

- 不改 `backend/app/services/low_buy/strategy_policy.py`。
- 不改变生产策略语义。
- 不改变 `production_score`。
- 不改变 `priority_board` 排序和口径。
- 不停 MySQL、Redis、Web/API、Go hot-read/scan、核心 runtime-worker。
- 不恢复 `/paper` 或 `/next/paper` active 模拟盘入口。
- 不新增 `PAPER_RUNTIME_TASKS_ENABLED` 作为新暂停开关。
- 不把云端改成纯 Web-only。
- 不在未授权情况下改线上 `.env`、compose、nginx、MySQL 配置。
- 不在未授权情况下执行 Docker restart/down/up/stop/start、Docker prune、DB 写入、部署、切流。
- D5 scheduler 合并必须等完整交易日 gate 通过，不因短窗健康就提前停独立 scheduler。

## 4. 最终运行拓扑

### 4.1 云端必须保留

| 服务 | 目标状态 | 原因 |
|---|---|---|
| `frontend-web` / `frontend-next` | 保留 | 当前线上前端入口 |
| `app` | 保留 | API 与 Web 主服务 |
| `mysql` | 保留 | 核心事实源 |
| `redis` | 保留 | 缓存与事件通道 |
| `go-bff-gateway` | 保留 | monitor/priority 热读聚合 |
| `go-market-read-service` | 保留 | 行情热读 |
| `go-scan-worker` | 保留 | 扫描加速，资源占用低 |
| `runtime-worker` | 保留但瘦身 | 核心任务消费 |

### 4.2 云端默认关闭或按需

| 项 | 目标状态 | 功能影响 |
|---|---|---|
| `analytics-worker` | profile/on-demand | Parquet/DuckDB/分析导出改为按需 |
| `backtest-worker` | profile/on-demand | 长回测不常驻云端 |
| `PLATFORM_AUTOPILOT_ENABLED` | `false` | 自动巡检/自愈建议停止 |
| `RUNTIME_LOW_PRIORITY_TASKS_PAUSED` | `true` | analytics/backtest/ML/factor/data repair/research 不抢资源 |
| `MARKET_REVIEW_ENABLED` | `false` 或降级 | 午盘/收盘复盘停止或改手动 |
| startup prewarm | `false` | 部署后减少启动抢资源 |
| paper active tasks | removed/skipped | active 模拟盘已移除，只保留历史只读样本 |

### 4.3 本地或按需承接

- 24 个月回测。
- 批量 backtest。
- analytics export。
- DuckDB/Parquet 报告。
- ML/factor mining。
- 数据补齐/修复。
- 研究型任务。

## 5. 多 Agent 并行开发模型

### 5.1 角色

| Agent | 负责范围 | 可并行 | 严禁 |
|---|---|---:|---|
| `trading-platform-supervisor` | 总控、风险升级、合并证据、授权点判断 | 是 | 跳过 gate 直接上线 |
| `devops-operator` | compose/env/runbook/观测脚本/线上只读验证 | 是 | 未授权改线上配置或重启 |
| `fullstack-builder-runtime` | RuntimeTask、removed paper、low-priority pause、scheduler embed 守卫 | 是 | 改策略语义 |
| `fullstack-builder-api` | provider/BFF/readyz 降级、hot-read 查询保护 | 是 | 让 Web 同步等待慢 provider |
| `qa-tester` | 本地测试、Playwright/curl、长窗稳定性报告 | 是 | 对线上做写入压测 |
| `product-strategist` | 停用项功能影响说明、页面入口状态、用户可见降级文案 | 是 | 扩功能范围 |
| `trading-quant-lead` | 策略语义、生产分、priority board 口径审核 | 审核并行 | 修改生产排序 |
| `stock-analysis-specialist` | 市场复盘关闭对交易决策影响审核 | 审核并行 | 新增未验证主观规则 |

### 5.2 并行与串行边界

可并行：

- A 线：removed paper / low-priority queue / runtime guard。
- B 线：provider/BFF/readyz 降级。
- C 线：旧前端退役 guard、native/mobile 脚本收口、docs/runbook 修正。
- D 线：QA 长窗观测脚本、Playwright/curl 验收矩阵。
- E 线：MySQL read-only 慢查询与表空间诊断。

必须串行：

1. D0 基线与 worktree 保护。
2. D1 本地代码和测试。
3. D2 非核心任务线上止血，需授权。
4. D3 2-4 小时短窗观察。
5. D4 完整交易日观察。
6. D5 embedded scheduler 合并，需维护窗口授权。
7. D6 MySQL/worker 根因治理，需单独授权。
8. D7 域名/CDN/WAF/TLS 链路处理，需单独授权。

## 6. 文件与产物设计

### 6.1 计划和报告

- Update/Create: `docs/operations/cloud-core-worker-resource-runbook.md`
- Update/Create: `docs/reports/cloud-resource-contention-remediation-YYYY-MM-DD.md`
- Update/Create: `docs/reports/cloud-resource-trading-day-stability-YYYY-MM-DD.md`
- Update: `docs/operations/frontend-backend-separated-deployment-runbook.md`
- Update: `docs/operations/deployment-topology-runbook.md`

### 6.2 配置、脚本、部署守卫

- Update: `.env.deploy.local.example`
- Update: `docker-compose.mysql.yml`
- Update: `scripts/verify_platform_budget.py`
- Update: `scripts/deploy_cloud_server.sh`
- Update: `scripts/quick_cloud_deploy.sh`
- Update: `scripts/deploy_scope.py`
- Update: `scripts/harden_native_release_config.py`
- Update: `scripts/native_release_check.py`

### 6.3 后端与测试

- Verify/Update: `backend/app/services/tasks/queue.py`
- Verify/Update: `backend/app/workers/runtime_worker.py`
- Verify/Update: `backend/app/services/low_buy_materialization.py`
- Verify/Update: `backend/app/services/market/regime.py`
- Verify/Update: monitor/BFF/readyz 相关 route/service。
- Test: `backend/tests/test_runtime_task_queue.py`
- Test: `backend/tests/test_phase4_runtime_worker_tasks.py`
- Test: `backend/tests/test_low_buy_materialization_priority_board.py`
- Test: `backend/tests/test_platform_budget_verifier.py`
- Test: `backend/tests/test_cloud_deploy_scripts.py`
- Test: `backend/tests/test_frontend_next_level1_cutover.py`
- Test: `backend/tests/test_deploy_scope.py`
- Test: BFF/provider 相关测试。

## 7. 开发批次

### D0: Baseline And Safety Gate

- [ ] 执行 `cd /Users/j/Documents/gupiao && git status --short`。
- [ ] 阅读 `AGENTS.md`、`docs/engineering-conventions.md`、本计划、现有资源治理报告。
- [ ] 保护已有脏文件，不回滚非本轮改动。
- [ ] 复核当前事实：

```bash
cd /Users/j/Documents/gupiao
git ls-files frontend | wc -l
test -d frontend; echo $?
rg -n "RUNTIME_LOW_PRIORITY_TASKS_PAUSED|PLATFORM_AUTOPILOT_ENABLED|MARKET_REVIEW_ENABLED|RUNTIME_WORKER_EMBED_SCHEDULER|MARKET_REGIME_PROVIDER_DEGRADED" \
  docker-compose.mysql.yml backend/app/core/config.py scripts/verify_platform_budget.py .env.deploy.local.example
rg -n "paper trading feature has been removed|skipped_removed_feature|mark_skipped|missing_required_strategies|skipped_non_production_strategies" \
  backend/app backend/tests
```

验收：

- 输出当前状态清单。
- 不执行线上写操作。

### D1: Non-Core Stop Profile

目标：用已有配置把非核心常驻任务从云端抢资源路径移走。

- [ ] 确认 `.env.deploy.local.example` 中存在资源瘦身配置示例：
  - `PLATFORM_AUTOPILOT_ENABLED=false`
  - `RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true`
  - `MARKET_REVIEW_ENABLED=false`
  - `RUNTIME_STARTUP_CACHE_PREWARM_ENABLED=false`
  - `RUNTIME_STARTUP_HISTORY_PREWARM_ENABLED=false`
- [ ] 确认 `docker-compose.mysql.yml` 对 app/worker/scheduler 透传对应 env。
- [ ] 确认 `scripts/verify_platform_budget.py` 会对 worker/scheduler 的低优先级暂停状态出 warning。
- [ ] 补充 runbook：哪些功能会停，哪些核心任务必须继续。

测试：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_platform_budget_verifier.py \
  backend/tests/test_cloud_deploy_scripts.py \
  backend/tests/test_runtime_task_queue.py
```

### D2: Removed Paper Residual Closure

目标：active 模拟盘已移除，历史 paper task 不再污染 failed、不重试、不占 worker。

- [ ] 复核 `RuntimeTaskQueue.mark_skipped()` 和 `TERMINAL_STATUSES` 是否覆盖 skipped。
- [ ] 复核 `RuntimeWorker` 是否识别：
  - `paper_review_report`
  - `paper_portfolio_execution_preview`
  - `paper_ledger_reconcile_preview`
  - 所有 `paper_` 前缀任务。
- [ ] 如缺测试，补充：
  - removed paper task 被 worker 领取后标记 skipped。
  - skipped 是 terminal，不会再次 claim。
  - skipped 不进入 failed，不 retry。
  - 非 paper 核心任务仍正常执行。
- [ ] 保留 paper 历史表和只读样本，不删表、不迁移。

测试：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_phase4_runtime_worker_tasks.py \
  backend/tests/test_independent_runtime_components.py \
  backend/tests/test_paper_routes.py
```

### D3: Low-Buy Materialization Isolation

目标：非生产/禁用/研究策略缺失不拖垮整批低吸物化，生产必需策略缺失仍阻断。

- [ ] 复核 `refresh_latest_low_buy_materialization()` 是否输出：
  - `required_strategies`
  - `missing_strategies`
  - `missing_required_strategies`
  - `skipped_strategies`
  - `is_partial`
  - `stale_reason`
- [ ] 复核 `low_buy_materialization_refresh` worker 对 `missing_required_strategies` 的失败口径。
- [ ] 如缺口存在，只补隔离和观测字段，不改策略分、不改排序。
- [ ] 对高频失败增加 queue backoff 或避免 retry storm，必须保留核心失败可见性。

测试：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_low_buy_materialization_priority_board.py \
  backend/tests/test_low_buy_read_paths.py \
  backend/tests/test_low_buy_priority_board_strategy_variants.py \
  backend/tests/test_low_buy_production_scoring.py
```

### D4: Provider, BFF, And Readiness Degradation

目标：外部源慢/断/返回 HTML 时，页面可用，核心热读不被拖垮。

- [ ] 复核 market regime provider degraded cooldown/backoff 是否生效。
- [ ] 对 EastMoney/AkShare/Go market-read 异常，优先返回缓存或 stale/degraded 标记。
- [ ] BFF 每个 source 独立 timeout，慢源不能拖垮整页。
- [ ] `/healthz` 表示进程活着；`/readyz` 用短超时依赖检查，不能长时间挂起。
- [ ] 页面/API 要暴露 stale/degraded，不白屏、不假新鲜。

测试：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_market_regime_strategy_p2.py \
  backend/tests/test_bff_monitor_workspace.py \
  backend/tests/test_low_buy_read_paths.py \
  backend/tests/test_market_routes.py
```

### D5: Embedded Scheduler Gate

目标：只在完整交易日 gate 通过后，把 standalone scheduler 合并到 runtime-worker，减少常驻进程和调度重复。

- [ ] 复核 deploy 脚本已支持 `DEPLOY_EMBED_RUNTIME_SCHEDULER`。
- [ ] 复核 budget verifier 在 embedded 模式下允许 standalone scheduler absent。
- [ ] 完整交易日 gate 必须包含：
  - 09:15 开盘前。
  - 10:30 盘中。
  - 13:30 午后。
  - 14:55 收盘前。
  - 15:10 收盘后。
  - 20:00 夜间低负载。
- [ ] gate 全部通过后，才允许维护窗口启用：
  - `RUNTIME_WORKER_EMBED_SCHEDULER=true`
  - `RUNTIME_SCHEDULER_BACKGROUND_JOBS_ENABLED=false`
- [ ] 停独立 scheduler 必须先看到 embedded heartbeat 和核心任务正常。

只读 gate 命令：

```bash
python3 scripts/collect_cloud_resource_gate_observation.py \
  --ssh-host 43.143.243.97 \
  --ssh-user ubuntu \
  --ssh-key /Users/j/Downloads/gupiao.pem \
  --journal-since "YYYY-MM-DD 00:00:00" \
  --docker-logs-since 30m \
  --checkpoint-label trading-day-<label> \
  --json-output docs/reports/cloud-resource-gate-observations/YYYY-MM-DD-<label>.json \
  --markdown-output docs/reports/cloud-resource-gate-observations/YYYY-MM-DD-<label>.md
```

本地测试：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_cloud_deploy_scripts.py \
  backend/tests/test_independent_runtime_components.py \
  backend/tests/test_platform_budget_verifier.py
```

### D6: MySQL And Worker Root Cause

目标：在 D1-D5 后仍慢时，处理真正根因，而不是继续靠关功能。

- [ ] 只读采集：
  - `SHOW GLOBAL STATUS LIKE 'Threads_%';`
  - `SHOW GLOBAL STATUS LIKE 'Slow_queries';`
  - `SHOW VARIABLES LIKE 'innodb_buffer_pool_size';`
  - 表空间前 20。
  - 慢查询摘要。
  - RuntimeTask 最近 4h/24h 分布。
- [ ] 若慢查询集中在 monitor/priority board，先做索引/查询计划评审，不直接调大机器。
- [ ] 若 MySQL RSS 仍贴近 limit，评估：
  - 调整 MySQL container memory limit。
  - 调整 buffer pool。
  - 扩机器规格。
  - 拆分析/报告任务到本地或按需 worker。
- [ ] 所有 DB schema/index/config 改动必须单独授权、可回滚、带迁移和慢查询对比。

输出：

- `docs/reports/mysql-runtime-root-cause-review-YYYY-MM-DD.md`
- `docs/reports/cloud-resource-after-non-core-stop-YYYY-MM-DD.md`

### D7: Old Frontend Retirement Closure

目标：旧前端不再回流到运行链路，剩余 native/mobile/docs 残留有明确归档口径。

- [ ] 保持 `git ls-files frontend | wc -l` 为 `0`。
- [ ] 保持本地 `frontend/` 目录 absent。
- [ ] 保持 deploy scope 禁止 `frontend-hot` / `frontend-legacy`。
- [ ] 保持 backend `/__legacy/*` 返回 retired 404。
- [ ] 更新 stale runbook，不再写旧 `frontend/dist` 是生产入口。
- [ ] 对 native/mobile 相关脚本给出 retired message 或归档说明：
  - `scripts/harden_native_release_config.py`
  - `scripts/native_release_check.py`
  - `Makefile` native targets。
- [ ] 历史 docs/reports 不批量改写，只新增“旧前端已退役”索引或说明。

测试：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q \
  backend/tests/test_frontend_next_level1_cutover.py \
  backend/tests/test_deploy_scope.py \
  backend/tests/test_cloud_deploy_scripts.py
```

### D8: Frontend-Next Stability And Cache Guard

目标：保证新前端长期运行不白屏、无 chunk 404、无旧入口回流。

- [ ] 线上检查：
  - `/`
  - `/next/monitor`
  - `/next/monitor/market`
  - `/next/strategy-tracking`
  - `/next/analysis`
  - `/next/backtest`
  - `/next/data`
  - `/next/settings`
- [ ] 检查动态 import/chunk：
  - 无 404。
  - 缺失资源返回 JSON 404，不 fallback 到 SPA HTML。
  - `index.html` no-store 策略保留。
- [ ] 受保护 API 401 属正常，页面不能因此白屏。

测试：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run lint
npm test -- --run
npm run build
npm run e2e
```

### D9: Online Rollout And Long-Run Validation

目标：部署后确认“卡顿来自资源争抢”这一类问题被解决或显著改善。

需用户明确授权后才执行线上写操作。

- [ ] 维护窗口前：
  - `git status --short` 干净或变更已归档。
  - 本地测试通过。
  - 回滚命令写入 runbook。
- [ ] 维护窗口内：
  - 先部署 D1-D4 的非破坏性代码/config。
  - 观察 2-4 小时。
  - 完整交易日 gate 通过后再做 D5。
- [ ] 稳定性观察：
  - 每 10-30 分钟采集 CPU/内存/swap/MySQL/RuntimeTask/API。
  - 至少覆盖一个完整交易日。
  - 观察部署后容器 RSS 是否恢复更快。

失败回滚条件：

- `/readyz` 持续失败。
- monitor/priority board p95 明显劣化。
- core task backlog 持续增长。
- MySQL 或 runtime-worker 重启次数增长。
- swap 持续上升且 available memory 下降。
- priority board 口径或排序出现不一致。

## 8. 验收矩阵

| 领域 | 验收标准 |
|---|---|
| 核心功能 | 监控、行情缓存、低吸榜、priority board、策略追踪继续运行 |
| 策略语义 | `strategy_policy.py` 无修改，`production_score` 和 priority board 排序不变 |
| 非核心止血 | analytics/backtest/ML/factor/data repair/research 不常驻抢资源 |
| 模拟盘 | active 入口不恢复；paper 残留任务 skipped，不 failed/retry |
| scheduler | D5 前 standalone 仍在；D5 后只有 embedded heartbeat，核心任务正常 |
| MySQL | 无 OOM；Threads/Slow_queries 有趋势记录；慢 SQL 有根因报告 |
| Redis | `evicted_keys=0`，连接数和 key 数稳定 |
| 前端 | `/` 和 `/next/*` 主要页面可用，无 chunk 404/白屏 |
| 旧前端 | `frontend/` 不回到 git；CI/Docker/deploy/backend 不依赖旧入口 |
| 资源 | worker/scheduler/MySQL RSS 稳定，swap 不持续上升 |
| 稳定性 | 至少 1 个完整交易日观察通过 |
| 运维边界 | 报告列明执行与未执行的线上写操作 |

## 9. 推荐提交拆分

| Commit | 内容 |
|---|---|
| `docs: refresh cloud resource stability plan` | 文档和 runbook |
| `test: guard removed paper task terminal state` | paper skipped 测试补强 |
| `test: guard low buy materialization isolation` | low_buy 隔离测试补强 |
| `feat: harden provider degraded fallback` | provider/BFF/readyz 降级代码 |
| `test: guard frontend-next legacy retirement` | 旧前端退役 guard |
| `docs: record trading day stability observation` | 线上只读观察报告 |

不要把 D6 MySQL 配置/索引、D5 scheduler 停用、Docker 清理、域名修复混进同一提交。

## 10. 总控执行提示词

```text
你在 /Users/j/Documents/gupiao 项目中工作。目标：按照 docs/superpowers/plans/2026-06-12-cloud-resource-stability-integrated-development-plan.md，完成“非核心任务止血 + scheduler 合并 gate + MySQL/worker 根因治理 + 旧前端退役收口 + 长时间稳定性验证”的开发与验收准备。允许多 Agent 并行开发，但线上写操作、部署、重启、清理、切流必须等用户单独授权。

开始前必须：
1. 执行 cd /Users/j/Documents/gupiao && git status --short，保护未提交文件。
2. 阅读 AGENTS.md、docs/engineering-conventions.md。
3. 阅读 docs/superpowers/plans/2026-06-12-cloud-resource-stability-integrated-development-plan.md。
4. 阅读 docs/superpowers/plans/2026-06-11-cloud-resource-contention-final-remediation.md。
5. 阅读 docs/reports/online-stability-remaining-7-items-final-2026-06-11.md、docs/reports/legacy-frontend-retirement-execution-2026-06-10.md。
6. 用 rg 复核 runtime task、paper、low_buy_materialization、provider degraded、frontend/dist、frontend-hot、frontend-legacy、__legacy、RUNTIME_WORKER_EMBED_SCHEDULER 相关代码，不要凭印象改。

硬边界：
- 不改 backend/app/services/low_buy/strategy_policy.py。
- 不改变 production_score。
- 不改变 priority_board 排序和口径。
- 不停、不降级核心行情刷新、日线刷新、低吸榜、推荐榜、priority board 物化、watchdog、数据新鲜度检查。
- 不恢复 /paper 或 /next/paper active 模拟盘入口。
- 不新增 PAPER_RUNTIME_TASKS_ENABLED。
- 不把云端改成 Web-only。
- 不执行 docker restart/down/up/stop/start、systemctl restart、nginx reload、Docker prune、线上 .env 修改、compose 生效修改、数据库写操作。
- 不部署、不切流，除非用户在当前上下文明确授权。
- D5 embedded scheduler 必须等完整交易日 gate 通过后才能执行。

并行开发安排：
1. devops-operator：runbook、budget verifier、deploy guard、线上只读 gate。
2. fullstack-builder-runtime：removed paper skipped、low-priority pause、RuntimeTask 终态和 scheduler embed 守卫。
3. fullstack-builder-api：provider/BFF/readyz 降级和热读保护。
4. qa-tester：后端 pytest、frontend-next 测试、Playwright/curl、长窗稳定性报告。
5. product-strategist：停用项功能影响说明和用户可见降级口径。
6. trading-quant-lead：确认 strategy_policy.py、production_score、priority_board 口径未变。
7. stock-analysis-specialist：确认关闭市场复盘/研究任务不影响核心交易决策链路。

优先级：
1. D0 baseline 与状态复核。
2. D1-D4 本地开发和测试补强。
3. D7-D8 旧前端和 frontend-next 防回归。
4. D9 只读稳定性观察报告。
5. 只有在用户授权后，才执行线上止血配置、部署、scheduler 合并、MySQL/域名/清理等写操作。

测试要求：
- 根据改动运行定向 pytest，不伪造全绿。
- 修改 runtime task 必跑 test_runtime_task_queue.py、test_phase4_runtime_worker_tasks.py、test_independent_runtime_components.py。
- 修改 low_buy 必跑 low_buy materialization/read path/production scoring 相关测试。
- 修改 BFF/provider 必跑 market_regime、bff_monitor_workspace、market_routes 相关测试。
- 修改 frontend-next 必跑 npm run api:check、lint、test、build、e2e。
- 最后运行 git diff --check 和 git status --short。

输出要求：
1. 写 docs/reports/<topic>-YYYY-MM-DD.md，记录改动、证据、测试、未执行线上写操作、需要授权的下一步。
2. 最终回复列出修改文件、测试结果、核心任务保护结果、是否仍需 D5/D6/D7 授权。
3. 明确说明本轮未执行部署、重启、清理、线上配置修改、数据库写操作、旧入口恢复。
```

## 11. 子 Agent 提示词

### 11.1 DevOps Operator

```text
你是 devops-operator，在 /Users/j/Documents/gupiao 工作。只处理资源治理 runbook、deploy guard、budget verifier、线上只读 gate 和报告。禁止部署、重启、清理、改线上配置、写数据库。先 git status --short，阅读本计划、AGENTS.md、docs/engineering-conventions.md。复核 docker-compose.mysql.yml、scripts/verify_platform_budget.py、scripts/deploy_cloud_server.sh、scripts/quick_cloud_deploy.sh、.env.deploy.local.example。输出：非核心止血配置矩阵、embedded scheduler gate、回滚命令、完整交易日观测命令、需要用户授权清单。测试至少运行 test_platform_budget_verifier.py、test_cloud_deploy_scripts.py，并运行 git diff --check。
```

### 11.2 Fullstack Builder Runtime

```text
你是 fullstack-builder-runtime，在 /Users/j/Documents/gupiao 工作。目标是复核并补强 RuntimeTask 资源治理：removed paper task skipped 终态、low-priority pause、low_buy_materialization 非生产缺失隔离、scheduler embed 守卫。禁止改 strategy_policy.py、production_score、priority_board 排序。先用 rg 复核 backend/app/workers/runtime_worker.py、backend/app/services/tasks/queue.py、backend/app/services/low_buy_materialization.py 和相关测试，已有实现不重复造。补缺口时先写测试。必须运行 test_runtime_task_queue.py、test_phase4_runtime_worker_tasks.py、test_low_buy_materialization_priority_board.py、test_low_buy_production_scoring.py，最后 git diff --check。
```

### 11.3 Fullstack Builder API

```text
你是 fullstack-builder-api，在 /Users/j/Documents/gupiao 工作。目标是 provider/BFF/readyz 降级隔离：外部行情源 HTML/超时/断连时返回 stale/degraded 或缓存；BFF 每个 source 独立 timeout；readyz 短超时，不长时间挂起。禁止让 Web 请求同步等待慢 provider，禁止改生产策略排序和分数。先复核 market regime provider degraded backoff 已有实现，再补缺口。测试运行 test_market_regime_strategy_p2.py、test_bff_monitor_workspace.py、test_low_buy_read_paths.py、test_market_routes.py，最后 git diff --check。
```

### 11.4 QA Tester

```text
你是 qa-tester，在 /Users/j/Documents/gupiao 工作。目标是验证本计划的本地和线上只读验收，不做任何线上写操作。先 git status --short，阅读本计划。构建测试矩阵：runtime task、low_buy、provider/BFF、frontend-next、旧前端退役 guard、cloud budget verifier。运行定向 pytest 和 frontend-next api:check/lint/test/build/e2e。线上只读时只允许 curl/ssh/docker ps/docker stats/mysql SELECT/SHOW，不允许 restart/down/up/prune/DB write。输出 docs/reports/cloud-resource-stability-verification-YYYY-MM-DD.md，列明命令、结果、失败项和未执行操作。
```

### 11.5 Product Strategist

```text
你是 product-strategist，在 /Users/j/Documents/gupiao 工作。目标是把资源治理停用项转成用户可理解的功能影响说明。必须保护核心任务：监控、行情缓存、低吸榜、priority board、策略追踪。明确说明 analytics/backtest/ML/factor/data repair/research、platform autopilot、market review、paper active entry 停用或按需后影响什么、不影响什么、如何恢复。不要提出新功能，不恢复模拟盘入口。输出 docs/reports/cloud-resource-feature-impact-YYYY-MM-DD.md。
```

### 11.6 Trading Quant Lead

```text
你是 trading-quant-lead，在 /Users/j/Documents/gupiao 工作。目标是审核本轮资源治理没有改变策略语义。只读检查 strategy_policy.py、production_score、priority_board 排序、low_buy materialization 输出字段、生产必需策略缺失阻断逻辑。禁止改代码，除非总控明确分配测试补强。输出审核结论：哪些测试证明口径不变，哪些风险需要阻断上线。
```

### 11.7 Stock Analysis Specialist

```text
你是 stock-analysis-specialist，在 /Users/j/Documents/gupiao 工作。目标是审核关闭 market review、研究任务、paper active entry 后，对市场阅读、板块/龙头/情绪周期和选股解释链路的影响。不得新增主观交易规则，不改策略公式。输出功能影响和替代观测路径：核心 monitor、market、priority board、strategy tracking 是否仍能支撑交易判断。
```
