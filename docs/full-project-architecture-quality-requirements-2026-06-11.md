# 全项目架构质量提升需求文档（核验版）

状态：需求定稿，待实施  
日期：2026-06-11  
来源审查：`docs/reports/full-project-architecture-quality-audit-2026-06-11.md`  
适用仓库：`/Users/j/Documents/gupiao`  
核验方式：对照当前代码、CI、配置、测试、既有平台优化文档和工程规范逐项核验  

## 1. 核验结论

`full-project-architecture-quality-audit-2026-06-11.md` 中大部分问题判断成立，解决方向总体可行，但有 4 类内容必须按当前仓库事实修正后才能进入实施：

1. 线上内存收口、线上性能复测属于真实风险，但只能准备授权包和只读验收；未获授权前不得部署、切流、停容器、清 Docker cache 或改 sysctl。
2. priority board 热读 N+1 已有查询计数和 golden 守卫测试，当前需求不应重复建设，而应保留守卫、扩大观测范围，并仅在新计数证明退化时改生产路径。
3. 结构化日志并非从零缺失。当前已有 `backend/app/core/logging_config.py`、`STRUCTURED_LOGS` 配置和日志测试；需求应修正为增强结构化字段、覆盖关键路径和补运行手册，而不是重建日志框架。
4. 日期窗口测试工具已存在并被 `test_analytics_layer.py`、`test_low_buy_read_paths.py` 使用；剩余需求是写入工程规范并推广到仍有显式窗口日期的测试。

本需求是“质量提升与稳定性收口”需求，不是功能扩张、策略调参或删除授权。所有实施都必须保留当前生产策略语义和交易闭环。

## 2. 当前工作树与保护事项

实施前必须执行并记录：

```bash
git status --short
git branch --show-current
```

当前核验时工作树存在以下在途改动，实施时必须保护，不得回滚或覆盖：

- `IMPLEMENTATION_PLAN.md`
- `backend/app/services/auction/`
- `backend/scripts/call_auction_provider_spike.py`
- `backend/tests/test_call_auction_provider_spike.py`
- `docs/call-auction-assist-execution-plan-2026-06-11.md`
- `docs/reports/call-auction-provider-spike-2026-06-11.md`
- `docs/reports/full-project-architecture-quality-audit-2026-06-11.md`

若实施时工作树状态已变化，以当时 `git status --short` 为准，继续保护所有无关在途改动。

## 3. 硬边界

1. 不修改 `backend/app/services/low_buy/strategy_policy.py`。
2. 不改变 `production_score`、priority board 排序语义、生产策略公式、风控阈值、交易日发布门控。
3. `strategy_engine` 继续 shadow-only，`replacement_enabled=false`，不得替代生产排序。
4. 不把 research、ML、因子、重分析任务放回 Web 主进程。
5. `portfolio_backtest_metrics` 继续作为真实组合回测唯一事实源。
6. 不直接拆成大量微服务；继续遵循模块化单体优先、重任务 Worker 化、DuckDB/Parquet 分析层。
7. 不物理删除 `frontend/` 或其它源码目录，除非另行获得明确删除授权。
8. 不执行线上部署、切流、服务器写操作、停容器、清 Docker cache、改 sysctl，除非用户单独授权。
9. 本需求不覆盖 first_board OOS 策略调参；该问题已归入策略成功率优化链路，必须按独立策略需求处理。

## 4. 当前事实基线

### 4.1 后端与运行时

- 后端为 FastAPI + SQLAlchemy，入口在 `backend/app/main.py`。
- `backend/app/core/config.py` 已包含 `runtime_worker_embed_scheduler`、`structured_logs`、`tquant_internal_service_token` 等配置。
- `docker-compose.mysql.yml`、`docker-compose.separated.yml` 已声明 `STRUCTURED_LOGS` 和内部服务 token 相关环境变量。
- `backend/app/core/security_config.py` 在配置微服务 URL 但未设置 `TQUANT_INTERNAL_SERVICE_TOKEN` 时 fail-closed。
- Web 主进程只服务 frontend-next 静态产物，`backend/app/main.py` 已指向 `frontend-next/dist`。

### 4.2 日志与观测

- 已有 `JsonLogFormatter` 和 `configure_logging(structured=settings.structured_logs)`。
- 现有 JSON 日志字段只有 `timestamp`、`level`、`module`、`message`、`exception`，缺少稳定的业务上下文字段。
- 已有 `backend/tests/test_logging_config.py`，但缺少关键路径日志字段覆盖。
- healthz、readyz、metrics 已存在，日志是当前观测体系中需要增强的部分。

### 4.3 Priority Board 热读

- `backend/app/services/low_buy/priority_items.py` 仍以逐候选循环构造 item，但该循环本身不等价于数据库 N+1。
- `backend/tests/test_low_buy_read_paths.py` 已包含 `test_priority_board_hot_read_query_budget_does_not_scale_with_candidates` 和 golden sha256 守卫。
- 当前需求只允许增强测量、保留守卫或在测出退化后做批量化；不得直接改排序、分数、lane 或 shadow 字段。

### 4.4 日期窗口测试

- `backend/tests/support/export_time.py` 已提供 `EXPORT_WINDOW_END_DATE`、`export_window_date()`、`export_window_datetime()`。
- `backend/tests/test_analytics_layer.py` 已使用 `EXPORT_WINDOW_END_DATE`。
- `backend/tests/test_low_buy_read_paths.py` 已使用 `export_window_date()`。
- 仍有若干测试直接写固定日期，需区分是否为业务规则固定日期；只有窗口过滤类 fixture 需要迁移。

### 4.5 CI 与前端

- `.github/workflows/ci.yml` 已包含 backend 全量 pytest、frontend-next `api:check -> typecheck -> lint -> test -> build` 串行步骤，以及 go-rust job。
- `frontend-next/package.json` 已有 `check:all`。
- 旧 `frontend/` 不在 CI 主链和后端静态服务路径中，但仍存在部分脚本引用，如 native 配置、version sync、legacy route audit 和 local cleanup 脚本。

### 4.6 大文件与报告产物

- 当前跟踪文件中最大项仍是 `docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json`，约 13MB。
- 多个脚本、测试和派生报告仍引用该 JSON，不能直接移动或删除。
- `docs/reports/platform-slimming-artifact-manifest-2026-06-09.md` 已指出该文件需先改默认路径、测试和派生指针后再迁移。

## 5. 需求总览

| 编号 | 需求 | 优先级 | 状态判断 | 类型 |
|---|---|---|---|---|
| R1 | 线上资源收口授权包 | P1 | 可行，需授权 | 运维稳定性 |
| R2 | 线上性能只读复测包 | P1 | 可行，需授权 | 性能观测 |
| R3 | 结构化日志增强 | P1 | 可行，修正为增强而非新建 | 可观测性 |
| R4 | priority board 热读守卫保留与扩展 | P1 | 已部分完成，继续守护 | 性能回归 |
| R5 | 大 JSON 出库前置改造 | P2 | 可行，需分阶段 | 仓库治理 |
| R6 | 旧前端退役决策包 | P2 | 可行，不含删除授权 | 架构收口 |
| R7 | scripts 分类与入口收敛 | P2 | 可行，先盘点后移动 | 可维护性 |
| R8 | 日期窗口测试规范推广 | P3 | 已部分完成，补规范与剩余迁移 | 测试稳定性 |
| R9 | internal token 部署文档化 | P3 | 部分已有，需补部署拓扑核对 | 运维配置 |
| R10 | TanStack chunk 仅测量不强拆 | P3 | 可行，收益不足则不拆 | 前端性能 |

## 6. 功能与非功能需求

### R1. 线上资源收口授权包

优先级：P1  
性质：线上授权项，默认不执行

需求：

1. 准备一份可执行但不自动执行的资源收口授权包，覆盖：
   - 只读基线命令。
   - 资源调整步骤。
   - 每步验收指标。
   - 回滚命令。
   - 交易日观察要求。
2. 授权包必须复用既有开关和配置：
   - `RUNTIME_WORKER_EMBED_SCHEDULER=true` 灰度。
   - analytics worker 按需 profile。
   - `deploy/sysctl/tquant-swappiness.conf`。
   - 现有 compose resource limit。
3. 未授权前只能输出文档，不得执行 `docker compose up/down/restart`、`docker builder prune`、`sysctl` 或远程写操作。
4. 不能把 `APP_WORKERS 2 -> 1` 作为新收益，除非只读基线证明线上仍大于 1。

验收：

```bash
rg -n "RUNTIME_WORKER_EMBED_SCHEDULER|swappiness|docker builder prune|rollback" docs/operations docs/reports
```

授权后验收目标：

- `free -m` 中 swap 使用低于 300M。
- `/readyz` 全部关键检查为 true。
- 收盘发布和定时任务连续 1 个交易日正常。

### R2. 线上性能只读复测包

优先级：P1  
性质：线上只读授权项

需求：

1. 准备只读复测脚本或报告模板，采集：
   - `/metrics` 中 local quote cache、BFF、market-read、provider 指标。
   - `/readyz`。
   - 核心页面/API p95。
   - `bff_partial_timeout` 或等价降级计数。
2. 复测必须明确是“优化后新数据”，不得继续引用 5 月末或 6 月初旧指标作为当前结论。
3. 如果只读复测未达门槛，只输出问题定位建议，不自动改线上配置。

验收门槛：

- 热读需求缓存命中率目标 ≥90%。
- priority board / monitor BFF p95 目标 ≤500ms。
- `bff_partial_timeout=0` 或有明确降级原因。
- 生成 `docs/reports/cloud-performance-recheck-YYYY-MM-DD.md/json`。

### R3. 结构化日志增强

优先级：P1  
性质：可观测性增强

需求：

1. 保留现有 `backend/app/core/logging_config.py` 和 `STRUCTURED_LOGS` 配置，不引入重型日志框架。
2. 扩展 JSON formatter 支持 `extra` 字段白名单，至少支持：
   - `request_id`
   - `task_id`
   - `task_type`
   - `trade_date`
   - `symbol`
   - `component`
   - `provider`
   - `read_path`
3. 在关键路径补结构化日志上下文：
   - runtime task worker 任务开始、成功、失败。
   - market provider fallback / timeout。
   - priority board read path / cache miss / read model fallback。
   - 收盘发布或数据刷新失败。
4. 日志增强不得改变业务返回、异常类型和任务状态机。
5. 增加测试验证 JSON 可解析、extra 字段输出、非 structured 模式保持兼容。

验收：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_logging_config.py
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_phase4_runtime_worker_tasks.py backend/tests/test_priority_board_cache_fast_path.py
```

### R4. Priority board 热读守卫保留与扩展

优先级：P1  
性质：性能回归守卫

需求：

1. 保留现有查询计数测试：
   - `test_priority_board_hot_read_query_budget_does_not_scale_with_candidates`
   - `test_priority_board_hot_read_golden_output_keeps_order_and_strategy_guards`
2. 将审查报告中的“疑似 N+1”修正为 `needs_measurement / guarded`，不得在没有新证据时改生产热路径。
3. 若未来新增候选上下文或榜单字段，必须同步更新查询预算测试和 golden 输出字段。
4. 若测出查询随候选数线性增长，只允许做批量预取或共享上下文缓存，且必须保持：
   - 排序不变。
   - `production_score` 不变。
   - `priority_score` 不变。
   - lane/display 字段不变。
   - strategy_engine shadow 字段不变。

验收：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py
```

停止条件：golden sha256 漂移、生产分漂移、排序漂移时必须停止并定位，不得放松断言。

### R5. 大 JSON 出库前置改造

优先级：P2  
性质：仓库治理

需求：

1. 不直接删除或移动 `docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json`。
2. 先完成引用迁移清单，至少覆盖：
   - `backend/scripts/front_row_weighted_production_scoring_backtest.py`
   - `backend/scripts/front_row_weighted_readiness_report.py`
   - `backend/scripts/front_row_weighted_oos_manifest.py`
   - `backend/scripts/front_row_weighted_walk_forward_validation.py`
   - `backend/scripts/front_row_weighted_weak_market_compression.py`
   - `backend/scripts/front_row_weighted_minute_tick_tradability.py`
   - `backend/tests/test_cloud_deploy_scripts.py`
   - 派生报告中的 source pointer。
3. 新机器 JSON 默认输出到 `backend/data/reports/` 或 artifact 目录，人读摘要继续放 `docs/reports/`。
4. 迁移后保留 Markdown 摘要和 manifest 指针，确保历史报告可追溯。
5. 出库/删除跟踪 JSON 需要单独提交，并在提交说明中列出引用迁移证据。

验收：

```bash
rg -n "front-row-weighted-production-scoring-backtest-2026-05-29.json" backend scripts docs
git ls-files -z | xargs -0 ls -lh 2>/dev/null | awk '$5 ~ /M$/ || $5 ~ /G$/ {print $5, $9}'
```

通过标准：迁移后代码默认路径不再依赖该 docs JSON；如仍有历史文档引用，必须指向 manifest 或 archive 说明。

### R6. 旧前端退役决策包

优先级：P2  
性质：架构收口，不含删除授权

需求：

1. 输出旧 `frontend/` 退役决策包，列明：
   - 当前 CI、Docker、后端静态服务、部署 scope 对旧前端的依赖情况。
   - 仍存在的脚本引用及用途，例如 native release、version sync、legacy route audit、local cleanup。
   - 可删除、需保留、需迁移到 archive 的文件范围。
2. 默认只做文档和守卫，不物理删除 `frontend/`。
3. 如后续获得删除授权，必须先：
   - 建立归档 tag 或分支。
   - 证明 `frontend-next` 线上稳定观察满足要求。
   - 修改或删除仍引用 `frontend/` 的脚本。
   - 跑 deploy scope、cloud deploy script、frontend-next 全量检查。

验收：

```bash
rg -n "frontend/|frontend-next|frontend/dist|__legacy" .github deploy backend scripts docs
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_deploy_scope.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_frontend_next_level1_cutover.py
```

### R7. scripts 分类与入口收敛

优先级：P2  
性质：可维护性治理

需求：

1. 先生成脚本清单，不移动文件：
   - 生产部署链路。
   - 本地开发链路。
   - 回测/研究工具。
   - 一次性审计/历史 spike。
   - 仍被 CI 或文档引用的脚本。
2. 只对确认无引用、无复用价值的一次性脚本提出 archive 建议。
3. 常用入口应收敛到 Makefile、Runbook 或少量稳定脚本，不新增平行 deploy 入口。
4. 移动脚本前必须更新所有引用和测试。

验收：

```bash
find scripts backend/scripts -maxdepth 1 -type f | sort
rg -n "scripts/|backend/scripts/" .github docs Makefile README.md
```

输出：`docs/reports/scripts-inventory-and-archive-plan-YYYY-MM-DD.md`。

### R8. 日期窗口测试规范推广

优先级：P3  
性质：测试稳定性

需求：

1. 在 `docs/engineering-conventions.md` 增加日期窗口测试规范：
   - 窗口过滤、导出、manifest、latest trade date 类测试必须用显式 fixture 时间。
   - 禁止依赖当前日期、DB 默认时间或 `datetime.now()`。
   - 推荐复用 `backend/tests/support/export_time.py`。
2. 扫描仍直接写固定窗口日期的测试，区分：
   - 业务规则固定日期：保留。
   - 导出窗口 fixture：迁移到 helper。
3. 不追求全仓库日期常量清零，避免破坏交易日历、涨跌停制度日期、业务规则测试。

验收：

```bash
rg -n "EXPORT_WINDOW_END_DATE|export_window_date|export_window_datetime" backend/tests docs/engineering-conventions.md
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_analytics_layer.py backend/tests/test_low_buy_read_paths.py
```

### R9. Internal service token 部署文档化

优先级：P3  
性质：运维配置收口

需求：

1. 核对并补充 separated deploy / scan-worker / BFF remote client 的 internal token 配置说明。
2. 保留 fail-closed 行为：配置微服务 URL 但无 `TQUANT_INTERNAL_SERVICE_TOKEN` 时必须失败或显式报错，不允许静默降级为无鉴权。
3. 在 Runbook 中说明 token 轮换、长度要求、验证命令和 403 排查路径。

验收：

```bash
rg -n "TQUANT_INTERNAL_SERVICE_TOKEN|X-Internal-Service-Token|scan-worker|separated" docs/operations docs docker-compose*.yml scripts
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_auth_cookie_security.py backend/tests/test_go_scan_worker_async.py
```

### R10. TanStack chunk 测量

优先级：P3  
性质：前端性能评估

需求：

1. 只运行 `frontend-next` chunk profile，输出当前 chunk 结构和 TanStack 依赖分布。
2. 只有在满足以下条件时才进入代码拆分：
   - bundle budget 接近或超过阈值。
   - TanStack 相关 chunk 影响首屏。
   - 拆分收益可量化且不会增加路由复杂度。
3. 如果收益不足，输出“不拆分”结论并记录证据。

验收：

```bash
cd frontend-next
npm run build
npm run chunk:profile
```

输出：`docs/reports/frontend-next-chunk-profile-YYYY-MM-DD.md/json`。

## 7. 已支持 / 部分支持 / 待实施矩阵

| 审查项 | 当前支持状态 | 修正后的实施建议 |
|---|---|---|
| 后端全量测试和 frontend-next 串行 CI | 已支持 | 保持，不重复实施 |
| `frontend-next check:all` | 已支持 | 保持，作为验收命令 |
| priority board 查询预算守卫 | 已支持 | 保留并作为后续热路径变更必跑项 |
| 日期窗口 helper | 部分支持 | 补规范，迁移剩余窗口类测试 |
| 结构化日志 | 部分支持 | 增强字段和关键路径覆盖 |
| 线上资源收口 | 方案支持，线上未执行 | 准备授权包，等待授权 |
| 线上性能复测 | 待执行 | 准备只读复测包，等待授权 |
| 大 JSON 出库 | 待实施，直接删除不可行 | 先迁移引用，再出库 |
| 旧前端删除 | 不授权 | 只做决策包和引用清单 |
| scripts 归档 | 待盘点 | 先 inventory，后 archive |

## 8. 非功能需求

### 稳定性

- 新增或修改守卫必须 fail closed，不能静默吞错。
- 热路径优化必须有 before/after 计数或性能证据。
- 线上操作必须有回滚路径和观察窗口。

### 性能

- 任何性能优化都必须先有测量。
- 优化结果必须记录为 Markdown + 可选 JSON 报告。
- 不为理论收益引入复杂架构。

### 可观测性

- 日志增强需保持 JSON 可解析。
- 关键路径日志必须包含足以定位的业务字段。
- 不输出密钥、token、完整账户信息等敏感数据。

### 可维护性

- 新文档遵循 `docs/engineering-conventions.md`。
- 新脚本必须有清晰入口和 `--help`。
- 一次性脚本优先归档，不新增平行工具链。

## 9. 验收命令总表

基础检查：

```bash
git status --short
git branch --show-current
git diff --check
```

后端重点回归：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_logging_config.py
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_analytics_layer.py backend/tests/test_auth_cookie_security.py backend/tests/test_go_scan_worker_async.py
```

前端重点回归：

```bash
cd frontend-next
npm run check:all
npm run chunk:profile
```

旧前端/部署引用检查：

```bash
rg -n "frontend/|frontend-next|frontend/dist|__legacy" .github deploy backend scripts docs
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_deploy_scope.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_frontend_next_level1_cutover.py
```

大文件检查：

```bash
git ls-files -z | xargs -0 ls -lh 2>/dev/null | awk '$5 ~ /M$/ || $5 ~ /G$/ {print $5, $9}'
rg -n "front-row-weighted-production-scoring-backtest-2026-05-29.json" backend scripts docs
```

## 10. 风险与停止条件

| 风险 | 停止条件 | 处理 |
|---|---|---|
| 热路径输出漂移 | priority board golden sha256 变化 | 停止，定位，不能放松断言 |
| 生产策略语义被误改 | `strategy_policy.py` 或 production scoring diff | 停止并报告，不继续实施 |
| 线上操作越权 | 需要停容器/改 sysctl/部署 | 停止，等用户授权 |
| 大 JSON 迁移破坏引用 | `rg` 仍发现代码默认依赖旧路径 | 不删除旧文件 |
| 日志字段泄露敏感信息 | token/secret 出现在日志测试样例 | 停止并加脱敏 |
| 旧前端删除条件不满足 | 仍有脚本/部署引用 | 不删除，只输出决策包 |

## 11. 分批实施建议

### D0. 基线冻结

- 记录 git 状态、当前审查报告、当前需求文档、已支持项和在途集合竞价改动。
- 不改代码。

### D1. 观测与日志增强

- 实施 R3。
- 只改 core logging、关键路径日志调用和测试。

### D2. 热读守卫确认

- 实施 R4。
- 若现有测试已满足，补文档和回归记录即可。
- 只有新测量证明退化才改生产代码。

### D3. 测试日期规范

- 实施 R8。
- 补工程规范和剩余窗口类测试迁移。

### D4. 大文件与脚本治理

- 实施 R5、R7。
- 先 inventory 和引用迁移，不直接删除。

### D5. 旧前端退役决策包

- 实施 R6。
- 只输出决策与引用清单，不物理删除。

### D6. 前端 chunk 测量

- 实施 R10。
- 收益不足则明确不拆。

### D7. 线上授权包

- 实施 R1、R2、R9 的文档和只读命令包。
- 未授权前不执行线上动作。

## 12. 最终完成标准

本需求完成时必须满足：

1. 所有已完成项均有命令和报告证据。
2. 所有需授权项均只形成授权包，未越权执行。
3. priority board 查询预算和 golden 守卫保持通过。
4. 结构化日志增强不破坏非 structured 日志模式。
5. 大文件迁移如未完成，必须保留阻断原因和引用清单。
6. 旧前端如未删除，必须说明原因和下一授权条件。
7. 最终交付说明明确：
   - 改了哪些文件。
   - 跑了哪些命令。
   - 哪些未跑及原因。
   - 是否部署、切流、线上写操作；默认应为未部署、未切流、未执行线上写操作。

