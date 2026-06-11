# Cloud Resource Contention Legacy Closure Final Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 分三层治理线上资源争抢导致的卡顿，并把旧前端退役、模拟盘残留收口、长稳验收、MySQL/域名根因治理合并成一套可并行开发、串行上线的执行文档。

**Architecture:** 云端保持核心小闭环：Web/API、MySQL、Redis、Go 热读/扫描、核心 runtime-worker、独立 scheduler 在 D5 gate 通过前继续隔离。第一层先停非核心任务止血，第二层治理 worker/scheduler/provider/队列重复，第三层处理 MySQL、机器规格、域名入口根因。旧前端只做防回流和归档门槛，active 模拟盘不恢复。

**Tech Stack:** Docker Compose, FastAPI, MySQL 8.4, Redis 7, Python runtime worker, Go hot-read services, frontend-next, pytest, Playwright, curl, SSH runbook.

---

## 0. 权威输入

本计划以以下文件为事实来源，执行前必须重新读取并确认没有新版本替代：

- `AGENTS.md`
- `docs/engineering-conventions.md`
- `docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md`
- `docs/superpowers/plans/2026-06-12-cloud-resource-contention-final-integrated-development-plan.md`
- `docs/superpowers/plans/2026-06-11-cloud-resource-contention-final-remediation.md`
- `docs/reports/cloud-resource-contention-remediation-2026-06-11.md`
- `docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md`
- `docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md`
- `docs/reports/legacy-frontend-retirement-decision-2026-06-11.md`
- `docs/reports/legacy-frontend-retirement-execution-2026-06-10.md`
- `docs/reports/provider-degraded-cooldown-market-regime-optimization-2026-06-12.md`
- `docs/reports/runtime-task-summary-read-model-optimization-2026-06-12.md`
- `docs/reports/daily-bar-coverage-read-model-optimization-2026-06-12.md`

### 0.1 执行入口

后续执行只以本文件作为总入口。若需要拆分给多个 Agent，同一批次只能在本文件列出的 P1-P7 包内领取任务，不得新增第八个隐形工作面。

执行规则：

1. 每个 Agent 开始前必须运行 `git status --short`，记录并保护无关脏文件。
2. 本地代码、测试、文档可以并行；线上生效、重启、清理、配置变更必须串行并等待用户明确授权。
3. 每个 P 包单独提交；不要把报告、代码、部署脚本、格式化和无关清理混成一个提交。
4. 若发现必须写线上环境才能修复，只记录证据、影响、建议命令和回滚命令，不直接执行。
5. 任何触碰 low-buy、priority board、策略分数、生产排序的改动，必须先由 `trading-quant-lead` 做策略守卫审查。

### 0.2 交付物

最终交付必须包含：

- P1-P7 每包 PASS/WARN/FAIL 结果。
- 每包提交 hash，或未提交原因。
- 本地测试命令和结果。
- 线上只读证据：资源、容器、HTTP/API、任务队列、heartbeat、前端页面。
- 核心功能影响结论：监控、行情缓存、低吸榜、priority board、策略追踪是否正常。
- D5 scheduler embed 是否允许执行；若不允许，列 blocker。
- 需要用户授权的下一步清单。
- 本轮是否执行任何线上写操作、重启、清理、部署。

## 1. 当前结论

### 1.1 能解决什么

本计划可以解决或明显改善“服务器资源争抢导致卡顿”这一大类问题：

- 云服务器内存长期吃紧。
- swap 高或持续上涨。
- worker、扫描、刷新、回测和 Web 抢 CPU/IO。
- 页面/API 在数据刷新或策略物化时变慢。
- runtime 任务堆积影响主服务。
- 部署后容器资源恢复慢。
- 已移除模拟盘任务继续失败/重试造成队列噪声。
- 旧前端入口、部署 scope、CI/Docker 链路回流风险。

### 1.2 不能单独解决什么

以下问题必须作为第三层或独立专项处理：

- `weisilianghua.cloud` TLS/SNI reset。
- MySQL 慢查询、索引不足、buffer pool/连接池配置不合理。
- priority board / monitor BFF 查询本身过重。
- 外部行情源限频、返回 HTML、超时、断连。
- 本地机器断网、休眠、关机导致本地重任务不跑。
- 用户浏览器缓存、旧 chunk、用户端网络问题。

### 1.3 当前 D5 状态

`docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md` 显示：

| 项 | 状态 |
|---|---|
| 线上可用性 | `/readyz` 200，核心 `/next/*` 页面 200 |
| 资源 | worker/MySQL 当前短窗有余量，swap 仍需观察 |
| 队列 | 旧 `data_quality_sla_refresh` 非核心残留已取消 |
| D5 embedded scheduler | `ready=false` |
| 硬阻塞原因 | `full_trading_day_observation_incomplete`、`scheduler_provider_warning_lines=28` |
| 持续观察项 | MySQL slow queries、worker RSS、swap、runtime queue |

结论：不能停独立 `runtime-scheduler`，不能启用 embedded scheduler，必须继续完整交易日观察。provider warning 是 D5 的重要观察项；只有达到采集器定义的 sustained provider pressure 阈值或导致 `d5_gate.ready=false` 的明确 blocker 时，才作为硬阻塞。低频 warning 只记录为风险，不单独替代完整交易日 gate；当前 `2026-06-12 03:36 CST` 只读快照为 `scheduler_provider_warning_lines=28`，已超过阈值 `20`，所以属于本轮 D5 blocker。

### 1.4 模拟盘状态判定

active 模拟盘已经不作为当前核心功能恢复。本计划里的“模拟盘残留收口”不是重新建设模拟盘，而是处理已移除功能留下的运行时噪声：

| 项 | 判定 | 本计划动作 |
|---|---|---|
| active paper 自动任务 | 不恢复 | 不新增开关、不重新入队、不常驻运行 |
| `/paper`、`/next/paper` | 不作为核心路径 | 不纳入核心 smoke；如仍存在历史入口，只能只读或隐藏 |
| `paper_*` runtime task | removed-feature 残留 | 标记 `skipped`/`cancelled`，不 failed/retry storm |
| paper 账本历史数据 | 历史数据 | 不清表、不迁移、不写生产库，除非单独授权 |
| paper 相关前端引用 | 退役检查对象 | 确认不回到主导航、不影响核心页面 |

因此，P2 的目标是降噪和防误恢复，不是恢复模拟盘交易能力。任何实现如果把 active paper 重新接回调度、策略门控或核心页面，必须立即停止并升级为 P0。

### 1.5 旧前端状态判定

旧前端收口分为“运行链路退役”和“源码物理删除”两件事，不能混为一谈。

| 层级 | 当前目标 | 验收 |
|---|---|---|
| 运行入口 | `frontend-next` 是唯一默认入口 | `/` 和 `/next/*` 不回到旧 React/AntD 产物 |
| CI/Docker/deploy | 不再构建、上传、部署旧前端 | `frontend-hot`、`frontend-legacy` 被阻断 |
| 后端静态服务 | 不服务旧前端 dist | `/__legacy/*` 不恢复静态资源 |
| 源码目录 `frontend/` | 只作为 retired source/archive candidate | 物理删除必须单独授权 |
| 回滚策略 | 短期靠 tag/branch/归档，不靠默认入口保留旧前端 | 删除前完成引用复扫和回滚说明 |

P6 只负责防回流和删除门槛。物理删除 `frontend/` 需要额外满足 1-2 个交易日稳定观察、native/mobile owner review、引用复扫、归档或可回滚 tag、用户明确授权。

### 1.6 当前未完成清单

| 编号 | 未完成项 | 当前处理 |
|---|---|---|
| U1 | D5 完整交易日 gate 未通过 | 继续采集 09:15、09:35、10:30、11:30、13:05、14:55、15:10、15:30 checkpoint |
| U2 | `runtime-scheduler` 不能停 | 保持独立 scheduler，直到 `d5_gate.ready=true` 且用户授权维护窗口 |
| U3 | provider warning 仍可能阻塞 D5 | 继续用 collector 区分 sustained pressure 与低频 warning |
| U4 | MySQL 慢查询/规格仍是根因专项 | 先只读诊断；索引、buffer pool、连接池、升配都需授权 |
| U5 | 旧前端物理删除未完成 | P6 先做防回流报告，删除另开授权批次 |
| U6 | active paper 残留需要持续降噪 | `paper_*` 任务进入 skipped/cancelled，不恢复 active paper |
| U7 | 前端长稳和 chunk 验证需要持续 | P7 输出页面 smoke 和完整交易日长稳证据 |

## 2. 硬边界

### 2.1 禁止项

- 不改 `backend/app/services/low_buy/strategy_policy.py`。
- 不改变生产策略语义。
- 不改变 `production_score`。
- 不改变 `priority_board` 排序和口径。
- 不把 research/shadow/paper 历史口径绕过门控接入生产排序。
- 不停止 MySQL、Redis、Web/API、Go hot-read、Go scan、核心 runtime-worker。
- 不把云端改成 Web-only。
- 不恢复 active 模拟盘功能，不恢复 `/paper` 或 `/next/paper` 为核心路径。
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

### 2.3 核心保护范围

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

目标：快速解除资源争抢，不影响核心交易观察链路。

| 项 | 目标状态 | 用户影响 | 恢复条件 |
|---|---|---|---|
| `PLATFORM_AUTOPILOT_ENABLED` | `false` | 自动巡检/自愈建议停止 | 资源稳定且用户需要 |
| `RUNTIME_LOW_PRIORITY_TASKS_PAUSED` | `true` | analytics/backtest/ML/factor/data repair/research 不抢 worker | 按需任务窗口 |
| `MARKET_REVIEW_ENABLED` | `false` 或降频 | 午盘/收盘自动复盘停止 | 资源稳定或改为按需 |
| startup prewarm | disabled | 部署后不做重预热 | 新机器或低峰窗口 |
| `analytics-worker` | on-demand profile | DuckDB/Parquet/分析导出需手动拉起 | 明确分析窗口 |
| `backtest-worker` | 不常驻 | 24M/批量回测不在云端常驻跑 | 明确回测窗口 |
| Prometheus/Grafana | 不常驻 | 独立监控面板按需恢复 | 需要图形监控 |
| active paper | 不恢复 | 模拟盘主动交易/自动任务停止 | 另立产品方案 |

### 3.2 第二层：合并调度结构前的稳定性治理

目标：先减少重复任务和 provider 压力，再决定是否合并 scheduler。

| 子项 | 当前策略 | D5 前门槛 |
|---|---|---|
| close-refresh dedupe | 同一 trade date 成功后不重复入队 | 交易日内无重复爆量 |
| worker recycle guard | 任务边界回收高 RSS worker | 不中断 running task，无 restart loop |
| provider degraded guard | 慢源/坏源返回 cached/warming/stale | provider warning 低于 sustained pressure 阈值，无 fallback storm |
| runtime queue terminal state | removed paper task 标记 skipped/cancelled | 不计 failed，不 retry |
| scheduler embed | 支持但默认关闭 | 完整交易日 gate 通过后维护窗口执行 |

### 3.3 第三层：MySQL、机器规格、域名根因

目标：解决资源止血以外的真实根因。

| 根因 | 处理方式 | 授权 |
|---|---|---|
| MySQL 内存 | 继续观察 `1536m/2048m` 后是否 OOM | 只读观察；调参需授权 |
| 慢查询 | 抓慢 SQL、EXPLAIN、索引或查询优化 | 开发/DB 授权 |
| 连接池 | 观测 `Threads_*`、API p95、连接等待 | 配置授权 |
| 机器规格 | 可用内存完整交易日仍 `<500MiB` 时升配 | 用户授权 |
| 域名 TLS/SNI | DNS/nginx/证书/CDN/WAF 分轨排查 | 独立授权 |
| Docker cache | 只清 build cache/dangling image，不动 volume | 维护窗口授权 |

## 4. 七个并行开发包

本地开发可并行，线上生效必须串行。每包都要单独提交，不能混入无关清理。

| 包 | Owner | 可并行 | 主要输出 | 线上写 |
|---|---|---|---|---|
| P1 状态基线与门禁 | `trading-platform-supervisor`、`qa-tester` | 是 | 状态报告、D5 gate、未完成清单 | 否 |
| P2 非核心止血与模拟盘残留 | `fullstack-builder`、`product-strategist` | 是 | stop profile、removed paper skipped/cancelled、影响矩阵 | 需授权 |
| P3 runtime/provider/队列稳定性 | `fullstack-builder`、`qa-tester` | 是 | dedupe、provider degraded、worker recycle、测试 | 部署需授权 |
| P4 scheduler 合并候选 | `devops-operator`、`fullstack-builder` | 受 P3/P5 约束 | embedded scheduler runbook、回滚命令 | 仅 D5 通过后 |
| P5 MySQL/机器规格根因 | `devops-operator`、`fullstack-builder` | 是 | 慢查询/连接/规格报告 | 调参需授权 |
| P6 旧前端最终收口 | `ui-designer`、`qa-tester` | 是 | 防回流测试、归档/删除门槛 | 删除需授权 |
| P7 前端/HTTP/长稳验收 | `qa-tester`、`ui-designer` | 是 | 页面 smoke、p95、完整交易日观察 | 否 |

### 4.1 并行依赖图

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

### 4.2 最终执行判定

当前最优路线不是云端 Web-only，也不是立即合并 scheduler；最优路线是三层串行生效、七包并行开发：

1. 第一层先停非核心任务止血，解决资源争抢导致的卡顿。
2. 第二层治理重复任务、provider fallback、worker RSS 和 scheduler 合并门槛。
3. 第三层处理 MySQL 慢查询/规格、域名 TLS/SNI、Docker cache 和机器升配。

其中 P2/P3/P5/P6/P7 可以在本地并行开发和只读验证；任何线上写动作必须回到 `trading-platform-supervisor` 统一串行授权。

## 5. 多 Agent 编排

### 5.1 角色职责

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

### 5.2 串行上线门禁

1. Gate A：每批开始 `git status --short`，保护无关未提交文件。
2. Gate B：本地测试通过，策略守卫测试通过。
3. Gate C：线上只读基线显示核心服务可用。
4. Gate D：用户明确授权线上写动作。
5. Gate E：最小范围变更后 `/readyz`、核心 API、页面 smoke 通过。
6. Gate F：观察 2-4 小时无 OOM、swap 不持续升高、核心任务无积压。
7. Gate G：完整交易日 09:15-15:30 观察通过。
8. Gate H：`d5_gate.ready=true` 后才允许 D5 scheduler embed。
9. Gate I：MySQL/域名/机器规格进入独立授权专项。

## 6. 文件改动规划

### 6.1 文档

| 文件 | 动作 | 责任 |
|---|---|---|
| `docs/operations/cloud-core-worker-resource-runbook.md` | 维护 | 止血、scheduler、回滚 |
| `docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md` | 维护 | D5 完整交易日观察 |
| `docs/reports/cloud-resource-gate-observation-2026-06-12-latest.md` | 生成/维护 | 自动 gate 快照 |
| `docs/reports/mysql-runtime-root-cause-review-2026-06-12.md` | 新增/维护 | MySQL 根因 |
| `docs/reports/frontend-next-legacy-guard-final-2026-06-12.md` | 新增 | 旧前端最终 guard |
| `docs/reports/cloud-resource-contention-product-impact-2026-06-12.md` | 新增 | 功能影响矩阵 |
| `docs/reports/domain-entry-tls-reset-review-2026-06-12.md` | 新增 | 域名入口专项 |

### 6.2 后端与脚本

| 文件 | 可改内容 |
|---|---|
| `backend/app/workers/runtime_worker.py` | removed paper task skipped、worker recycle guard |
| `backend/app/services/tasks/queue.py` | terminal status、summary、cancel/skipped 行为 |
| `backend/app/services/latest_data_close_refresh.py` | 同日成功任务 dedupe |
| `backend/app/services/market/regime.py` | provider degraded cooldown、cached/warming fallback |
| `backend/app/services/market/providers/router.py` | provider timeout/circuit-open 降级 |
| `backend/app/core/config.py` | 缺失 setting 声明，不能靠未声明 env |
| `backend/app/runtime/background_jobs.py` | scheduler/market review 门控 |
| `scripts/verify_platform_budget.py` | 预算和 D5 gate 检查 |
| `scripts/collect_cloud_resource_gate_observation.py` | 只读长稳采集 |
| `scripts/deploy_cloud_server.sh` | explicit scheduler embed mode guard |
| `scripts/quick_cloud_deploy.sh` | frontend-next 和 scheduler embed 验证兼容 |

### 6.3 前端/旧入口

| 文件 | 可改内容 |
|---|---|
| `backend/app/main.py` | 保持 `frontend-next/dist` 和 `/__legacy/*` 退役 404 |
| `scripts/deploy_scope.py` | 阻断 `frontend-hot`、`frontend-legacy` |
| `deploy/frontend/Dockerfile` | 只构建 `frontend-next` |
| `Dockerfile` | 只复制 `frontend-next/dist` |
| `.github/workflows/ci.yml` | 只上传 `frontend-next/dist` artifact |
| `frontend-next/scripts/*` | 页面 smoke、trace、visual/perf 验证 |

## 7. 开发任务

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

记录：

- 是否完整交易日观察完成。
- 是否仍有 scheduler provider warnings。
- MySQL 是否有新 OOM。
- worker RSS 是否稳定。
- runtime queue 是否有非核心积压。
- 本轮是否执行任何写操作。

### Task P2: 非核心止血与模拟盘残留

**Owner:** `fullstack-builder` + `product-strategist`

**Files:**

- Modify: `backend/app/workers/runtime_worker.py`
- Modify: `backend/app/services/tasks/queue.py`
- Modify: `backend/tests/test_runtime_task_queue.py`
- Modify: `backend/tests/test_phase4_runtime_worker_tasks.py`
- Create: `docs/reports/cloud-resource-contention-product-impact-2026-06-12.md`

- [ ] **Step 1: 锁定 active paper 不恢复**

检查：

```bash
rg -n "paper|PAPER|/next/paper|/paper" backend frontend-next frontend scripts docs | head -200
```

Expected:

- `/next/paper` 不作为核心入口恢复。
- `paper_*` runtime task 是 removed-feature 残留处理对象。
- 不新增 `PAPER_RUNTIME_TASKS_ENABLED` 作为恢复开关。

- [ ] **Step 2: 测试 removed paper task 进入终态**

新增或保留测试覆盖：

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

### Task P3: runtime/provider/队列稳定性

**Owner:** `fullstack-builder` + `qa-tester`

**Files:**

- Modify if needed: `backend/app/services/latest_data_close_refresh.py`
- Modify if needed: `backend/app/services/market/regime.py`
- Modify if needed: `backend/app/services/market/providers/router.py`
- Modify if needed: `backend/app/runtime/background_jobs.py`
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

### Task P4: scheduler 合并候选与回滚

**Owner:** `devops-operator` + `fullstack-builder`

**Files:**

- Modify: `docs/operations/cloud-core-worker-resource-runbook.md`
- Modify: `scripts/deploy_cloud_server.sh`
- Modify: `scripts/quick_cloud_deploy.sh`
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

### Task P6: 旧前端最终收口

**Owner:** `ui-designer` + `qa-tester` + `devops-operator`

**Files:**

- Create: `docs/reports/frontend-next-legacy-guard-final-2026-06-12.md`
- Test: `backend/tests/test_frontend_next_level1_cutover.py`
- Test: `backend/tests/test_deploy_scope.py`
- Test: `backend/tests/test_cloud_deploy_scripts.py`

- [ ] **Step 1: 确认旧前端运行链路已退役**

```bash
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

### Task P7: 前端、HTTP、长稳验收

**Owner:** `qa-tester` + `ui-designer`

**Files:**

- Create: `docs/reports/frontend-next-core-pages-smoke-2026-06-12.md`
- Modify: `docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md`

- [ ] **Step 1: frontend-next 本地验收**

```bash
cd frontend-next
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

## 8. 验收矩阵

| 验收项 | 必须通过 |
|---|---|
| Git | 每批开始前 `git status --short`；提交只包含本批文件 |
| 策略守卫 | `strategy_policy.py` 未改；production score 和 priority board 测试通过 |
| 核心 API | `/readyz` 200；受保护 API 401 快速返回；无 5xx/timeout |
| 核心页面 | `/next/monitor`、`/next/monitor/market`、`/next/strategy-tracking`、`/next/analysis`、`/next/backtest`、`/next/data`、`/next/settings` 可打开 |
| 资源 | MySQL 无 OOM；worker 不持续贴边；swap 不持续上涨 |
| 任务 | low-priority paused；核心任务完成；同日重复任务不爆量 |
| D5 gate | `collect_cloud_resource_gate_observation.py --full-trading-day-complete` 后 `d5_gate.ready=true` |
| 旧前端 | `frontend/` 不在运行链路；CI/Docker/deploy 不回流旧前端 |
| 模拟盘 | active paper 不恢复；历史 paper task skipped/cancelled，不 failed/retry |
| 长稳 | 完整交易日观察无 P0/P1 |
| 回滚 | 每个线上写动作都有 backup 和 rollback command |

## 9. 分角色提示词

### 9.1 总控提示词

```text
你是 trading-platform-supervisor，在 /Users/j/Documents/gupiao 总控云服务器资源争抢卡顿治理、旧前端退役收口和模拟盘残留降噪。

目标：按 docs/superpowers/plans/2026-06-12-cloud-resource-contention-legacy-final-development-doc.md 推进 P1-P7。核心必须持续可用：监控、行情缓存、低吸榜、priority board、策略追踪、watchdog、app/mysql/redis/frontend-next/go-bff/go-market-read/go-scan/runtime-worker。

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

## 10. 一键总提示词

```text
你在 /Users/j/Documents/gupiao 项目中工作。请按 docs/superpowers/plans/2026-06-12-cloud-resource-contention-legacy-final-development-doc.md 执行下一批开发/验证。

目标：三层治理线上资源争抢导致的卡顿，并融合旧前端退役与已移除模拟盘残留收口。核心必须持续可用：监控、行情缓存、低吸榜、priority board、策略追踪、watchdog、app/mysql/redis/frontend-next/go-bff/go-market-read/go-scan/runtime-worker。

开始前必须执行：
1. cd /Users/j/Documents/gupiao && git status --short
2. 阅读 AGENTS.md、docs/engineering-conventions.md、docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md
3. 阅读 docs/superpowers/plans/2026-06-12-cloud-resource-contention-legacy-final-development-doc.md
4. 阅读本计划第 0 节列出的权威输入文件

硬边界：
- 不改 backend/app/services/low_buy/strategy_policy.py
- 不改变生产策略语义、production_score、priority_board 排序和口径
- 不停止 MySQL、Redis、Web/API、Go hot-read、Go scan、核心 runtime-worker
- 不把云端改成 Web-only
- 不恢复 active 模拟盘，不恢复 /paper 或 /next/paper 作为核心路径
- 未获授权不得改线上 .env、不得重启/重建/停止容器、不得清理 Docker/磁盘、不得改 nginx/MySQL、不得写生产数据库
- D5 embedded scheduler 不得在 d5_gate.ready=false 时执行
- 域名 TLS/SNI、MySQL schema/index/配置、Docker cleanup、机器升配、frontend/ 物理删除都必须作为独立授权专项

执行方式：
- 可多 Agent 并行：trading-quant-lead 做策略守卫，stock-analysis-specialist 做市场复盘关闭影响审查，product-strategist 做功能影响矩阵，ui-designer 做 frontend-next 页面/旧入口检查，fullstack-builder 做后端 guard/dedupe/provider/verifier，qa-tester 做测试和长稳验收，devops-operator 做 runbook/只读线上验证/授权操作。
- 本地开发可并行，线上生效必须串行：先只读基线，再本地测试，再用户授权，再最小范围变更，再 2-4 小时观察，再完整交易日观察。
- D5 embedded scheduler 只有在 worker RSS、MySQL、swap、任务队列完整交易日稳定后才能执行；否则继续保留独立 scheduler。

本批优先做：
1. 更新 docs/reports/cloud-resource-contention-trading-day-observation-2026-06-12.md，记录完整交易日观察模板、当前未完成项和 D5 blocker。
2. 复核第一层 stop profile 是否在线生效：PLATFORM_AUTOPILOT_ENABLED=false、RUNTIME_LOW_PRIORITY_TASKS_PAUSED=true、MARKET_REVIEW_ENABLED=false。
3. 复核 worker recycle guard 是否已启用及是否在任务边界正常工作；未稳定前不得执行 scheduler embed。
4. 复核 provider degraded guard 是否减少 fallback 链式压力；如仍有 sustained scheduler provider pressure 或 collector 明确输出 D5 blocker，D5 继续阻塞；低频 warning 只记录为观察风险。
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
