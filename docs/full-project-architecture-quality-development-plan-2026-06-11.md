# 全项目架构质量提升开发计划（2026-06-11）

状态：待实施  
需求来源：`docs/full-project-architecture-quality-requirements-2026-06-11.md`  
审查来源：`docs/reports/full-project-architecture-quality-audit-2026-06-11.md`  
适用仓库：`/Users/j/Documents/gupiao`  
执行原则：本地可验证项先行；线上资源、性能复测、部署和删除类动作必须单独授权  

## 1. 目标

把全项目架构质量审查中可落地的问题转成可执行开发批次，优先增强观测、固化热读和测试守卫，再治理大文件、脚本、旧前端退役决策和前端 chunk 测量，最后只准备线上资源/性能授权包，不执行线上动作。

本计划不扩业务功能、不调策略参数、不做微服务化、不删除旧前端源码、不部署不切流。

## 2. 硬边界

1. 不修改 `backend/app/services/low_buy/strategy_policy.py`。
2. 不改变 `production_score`、priority board 排序语义、生产策略公式、风控阈值、交易日发布门控。
3. `strategy_engine` 保持 shadow-only，`replacement_enabled=false`。
4. 不把 research、ML、因子、重分析任务放回 Web 主进程。
5. `portfolio_backtest_metrics` 继续作为真实组合回测唯一事实源。
6. 不物理删除 `frontend/` 或其它源码目录，除非用户另行明确授权。
7. 不执行服务器写操作、不部署、不切流、不停容器、不清 Docker cache、不改 sysctl。
8. 不覆盖集合竞价 spike 在途改动；涉及同文件时先停下来报告。

## 3. 开工基线

每次开始实施前必须先执行：

```bash
git status --short
git branch --show-current
```

当前核验时存在在途改动：

- `IMPLEMENTATION_PLAN.md`
- `backend/app/services/auction/`
- `backend/scripts/call_auction_provider_spike.py`
- `backend/tests/test_call_auction_provider_spike.py`
- `docs/call-auction-assist-execution-plan-2026-06-11.md`
- `docs/reports/call-auction-provider-spike-2026-06-11.md`
- `docs/reports/full-project-architecture-quality-audit-2026-06-11.md`
- `docs/full-project-architecture-quality-requirements-2026-06-11.md`

实施时以实时 `git status --short` 为准，保护所有无关改动。

## 4. 批次计划

### D0. 基线冻结与任务护栏

优先级：P0  
需求来源：R1-R10 共用  
类型：只读基线

动作：

1. 记录 `git status --short`、分支名和当前在途文件。
2. 核对权威输入：
   - `docs/full-project-architecture-quality-requirements-2026-06-11.md`
   - `docs/reports/full-project-architecture-quality-audit-2026-06-11.md`
   - `docs/engineering-conventions.md`
   - `docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md`
   - `AGENTS.md`
3. 建立本轮产物清单，后续报告放 `docs/reports/`，机器 JSON 放 `backend/data/reports/` 或既有 artifact 目录。

验收：

```bash
git status --short
git branch --show-current
test -f docs/full-project-architecture-quality-requirements-2026-06-11.md
```

停止条件：发现与集合竞价 spike 或其它在途改动同文件冲突，先报告，不继续编辑。

### D1. 结构化日志增强

优先级：P1  
需求来源：R3  
预计文件：

- `backend/app/core/logging_config.py`
- `backend/app/services/tasks/worker.py`
- `backend/app/services/market/quote_router.py` 或 provider fallback 相关文件
- `backend/app/services/low_buy/priority_board.py`
- `backend/tests/test_logging_config.py`
- 可选：`docs/operations/observability-runbook.md` 或既有 operations 文档

动作：

1. 保留现有 `JsonLogFormatter` 和 `STRUCTURED_LOGS`，不引入重型日志库。
2. 为 formatter 增加 `extra` 字段白名单：
   - `request_id`
   - `task_id`
   - `task_type`
   - `trade_date`
   - `symbol`
   - `component`
   - `provider`
   - `read_path`
3. 在关键路径补结构化上下文：
   - runtime task worker start/success/failure。
   - market provider fallback/timeout。
   - priority board cache miss/read model fallback/read_path。
4. 增加日志测试：
   - structured JSON 可解析。
   - extra 字段输出。
   - exception 字段保留。
   - 非 structured 模式不被 JSON formatter 强制覆盖。
5. 不输出 token、secret、完整账号等敏感字段。

验收：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_logging_config.py
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_phase4_runtime_worker_tasks.py backend/tests/test_priority_board_cache_fast_path.py
git diff -- backend/app/services/low_buy/strategy_policy.py backend/app/services/low_buy/production_scoring.py
```

停止条件：日志增强改变业务异常、任务状态机、priority board 输出或泄露敏感字段。

### D2. Priority Board 热读守卫确认

优先级：P1  
需求来源：R4  
预计文件：

- `backend/tests/test_low_buy_read_paths.py`
- 可选新增：`docs/reports/priority-board-hot-read-guard-review-2026-06-11.md`
- 只有测出真实退化时才允许改 `backend/app/services/low_buy/*`

动作：

1. 复核现有查询计数测试和 golden 守卫是否覆盖：
   - N=5 与 N=20 查询数不随候选线性增长。
   - `shadow_only=true`。
   - `replacement_enabled=false`。
   - `production_sort_replaced=false`。
   - 排序、分数、lane、strategy key 的 golden digest。
2. 如覆盖不足，只增强测试或报告，不改生产路径。
3. 如新测量证明退化，再做批量预取或共享上下文缓存，并保持 golden 零漂移。

验收：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py
```

停止条件：golden sha256 漂移、生产分漂移、排序漂移或 strategy_engine shadow 字段漂移。

### D3. 日期窗口测试规范推广

优先级：P3  
需求来源：R8  
预计文件：

- `docs/engineering-conventions.md`
- `backend/tests/support/export_time.py`
- `backend/tests/test_analytics_layer.py`
- `backend/tests/test_low_buy_read_paths.py`
- 其它明确属于窗口过滤 fixture 的测试

动作：

1. 在工程规范中增加“日期窗口测试”小节。
2. 明确窗口过滤、导出、manifest、latest trade date 类测试必须使用显式 fixture 时间。
3. 扫描固定日期测试，区分业务规则日期和窗口 fixture 日期。
4. 只迁移窗口 fixture，不追求全仓库日期常量清零。

验收：

```bash
rg -n "EXPORT_WINDOW_END_DATE|export_window_date|export_window_datetime" backend/tests docs/engineering-conventions.md
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_analytics_layer.py backend/tests/test_low_buy_read_paths.py
```

停止条件：测试日期改动影响交易日历、涨跌停制度、业务固定日期语义。

### D4. 大 JSON 出库前置改造

优先级：P2  
需求来源：R5  
预计文件：

- `backend/scripts/front_row_weighted_production_scoring_backtest.py`
- `backend/scripts/front_row_weighted_readiness_report.py`
- `backend/scripts/front_row_weighted_oos_manifest.py`
- `backend/scripts/front_row_weighted_walk_forward_validation.py`
- `backend/scripts/front_row_weighted_weak_market_compression.py`
- `backend/scripts/front_row_weighted_minute_tick_tradability.py`
- `backend/tests/test_cloud_deploy_scripts.py`
- `docs/reports/platform-slimming-artifact-manifest-2026-06-09.md`
- 新增 `docs/reports/front-row-weighted-artifact-migration-2026-06-11.md`

动作：

1. 不直接删除或移动 `docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json`。
2. 先把脚本默认输入/输出迁到 `backend/data/reports/` 或明确 artifact 目录。
3. 保留显式参数兼容旧路径，避免历史命令立即失效。
4. 更新测试断言，避免部署脚本依赖 docs 大 JSON。
5. 更新 manifest，说明旧 JSON 的迁移状态、残留引用和删除条件。
6. 若仍有代码默认依赖旧 JSON，本批不得删除旧文件。

验收：

```bash
rg -n "front-row-weighted-production-scoring-backtest-2026-05-29.json" backend scripts docs
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_cloud_deploy_scripts.py
git ls-files -z | xargs -0 ls -lh 2>/dev/null | awk '$5 ~ /M$/ || $5 ~ /G$/ {print $5, $9}'
```

停止条件：仍有代码默认依赖旧路径，或迁移会导致历史报告不可追溯。

### D5. Scripts 分类与入口收敛

优先级：P2  
需求来源：R7  
预计文件：

- 新增 `docs/reports/scripts-inventory-and-archive-plan-2026-06-11.md`
- 可选：`docs/operations/*runbook*.md`
- 不默认移动脚本

动作：

1. 生成 `scripts/` 和 `backend/scripts/` 清单。
2. 分类：
   - 生产部署链路。
   - 本地开发链路。
   - 回测/研究工具。
   - 一次性审计/历史 spike。
   - CI/文档仍引用的脚本。
3. 给出 archive 候选，但不在本批移动文件，除非证据充分且无引用。
4. 标出应收敛到 Makefile/Runbook 的高频入口。

验收：

```bash
find scripts backend/scripts -maxdepth 1 -type f | sort
rg -n "scripts/|backend/scripts/" .github docs Makefile README.md
test -f docs/reports/scripts-inventory-and-archive-plan-2026-06-11.md
```

停止条件：无法证明脚本无引用或用途不明，先标记 `keep_until_owner_review`。

### D6. 旧前端退役决策包

优先级：P2  
需求来源：R6  
预计文件：

- 新增 `docs/reports/legacy-frontend-retirement-decision-2026-06-11.md`
- 可选：`docs/operations/deployment-topology-runbook.md`
- 不删除 `frontend/`

动作：

1. 扫描 CI、Docker、后端静态服务、deploy scope、脚本、文档中旧 `frontend/` 引用。
2. 按用途分组：
   - 必须保留。
   - 可迁移到 frontend-next。
   - 仅历史/归档。
   - 删除需授权。
3. 写清旧前端物理删除前置条件：
   - frontend-next 线上稳定观察。
   - 归档 tag/分支。
   - 脚本引用处理。
   - deploy scope 和 cloud deploy 测试通过。
4. 不物理删除源码。

验收：

```bash
rg -n "frontend/|frontend-next|frontend/dist|__legacy" .github deploy backend scripts docs
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_deploy_scope.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_frontend_next_level1_cutover.py
test -f docs/reports/legacy-frontend-retirement-decision-2026-06-11.md
```

停止条件：发现仍有生产路径依赖旧 frontend，标记 blocker，不删除不迁移。

### D7. Frontend-next chunk 测量

优先级：P3  
需求来源：R10  
预计文件：

- 新增或更新 `docs/reports/frontend-next-chunk-profile-2026-06-11.md`
- 可选 JSON：`docs/reports/frontend-next-chunk-profile-2026-06-11.json`
- 默认不改前端代码

动作：

1. 执行 build 和 chunk profile。
2. 记录 TanStack 相关 chunk、首屏影响、bundle budget。
3. 若收益不足，明确输出“不拆分”结论。
4. 只有证明收益明确且不增加路由复杂度时，才另起任务拆分。

验收：

```bash
cd frontend-next
npm run build
npm run chunk:profile
```

停止条件：profile 未证明收益，不能为了“优化”改代码。

### D8. 线上资源/性能/Internal Token 授权包

优先级：P1/P3  
需求来源：R1、R2、R9  
预计文件：

- 新增 `docs/reports/platform-online-resource-performance-authorization-pack-2026-06-11.md`
- 可选更新 `docs/operations/deployment-topology-runbook.md`
- 可选更新 `docs/operations/worker-runbook.md`

动作：

1. 准备资源收口授权包：
   - 只读基线命令。
   - `RUNTIME_WORKER_EMBED_SCHEDULER=true` 灰度步骤。
   - swappiness、Docker builder prune 等动作的授权边界。
   - 回滚步骤。
2. 准备只读性能复测包：
   - `/metrics`。
   - `/readyz`。
   - p95 和 cache hit 采样。
   - 报告模板。
3. 补 internal token 文档：
   - `TQUANT_INTERNAL_SERVICE_TOKEN` 长度和轮换。
   - separated deploy / scan-worker / BFF remote client 的 403 排查。
   - fail-closed 行为说明。
4. 不执行线上动作。

验收：

```bash
rg -n "RUNTIME_WORKER_EMBED_SCHEDULER|swappiness|docker builder prune|TQUANT_INTERNAL_SERVICE_TOKEN|X-Internal-Service-Token|/metrics|/readyz" docs/operations docs/reports
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_auth_cookie_security.py backend/tests/test_go_scan_worker_async.py
test -f docs/reports/platform-online-resource-performance-authorization-pack-2026-06-11.md
```

停止条件：任何需要服务器写操作、停容器、部署、切流、sysctl 或 Docker cache 清理的步骤都必须停下等待用户授权。

## 5. 全量回归建议

完成所有本地批次后建议跑：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_logging_config.py backend/tests/test_phase4_runtime_worker_tasks.py backend/tests/test_priority_board_cache_fast_path.py backend/tests/test_low_buy_read_paths.py backend/tests/test_low_buy_priority_board_strategy_variants.py backend/tests/test_low_buy_production_scoring.py backend/tests/test_analytics_layer.py backend/tests/test_auth_cookie_security.py backend/tests/test_go_scan_worker_async.py backend/tests/test_deploy_scope.py backend/tests/test_cloud_deploy_scripts.py backend/tests/test_frontend_next_level1_cutover.py
cd frontend-next && npm run check:all
git diff --check
```

若改动触及公共后端服务或部署脚本，升级为：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests
```

## 6. 交付物

必须交付：

1. 结构化日志增强代码与测试，或明确说明该批仅评估无需改。
2. priority board 热读守卫回归结果。
3. 日期窗口测试规范更新。
4. 大 JSON 迁移计划和引用清单。
5. scripts inventory 和 archive 建议。
6. 旧前端退役决策包。
7. frontend-next chunk profile 结论。
8. 线上资源/性能/internal token 授权包。
9. 最终实施报告，说明：
   - 改了哪些文件。
   - 跑了哪些命令。
   - 哪些未跑及原因。
   - 是否部署、切流、线上写操作；默认必须为未部署、未切流、未执行线上写操作。

## 7. 实施提示词

```text
你现在在 /Users/j/Documents/gupiao 仓库执行“全项目架构质量提升收口”开发任务。请严格依据：
- docs/full-project-architecture-quality-requirements-2026-06-11.md
- docs/full-project-architecture-quality-development-plan-2026-06-11.md
- docs/reports/full-project-architecture-quality-audit-2026-06-11.md
- docs/engineering-conventions.md
- docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md
- AGENTS.md

开始前必须执行 git status --short 和 git branch --show-current，保护所有在途改动；不得回滚、删除或覆盖与本任务无关的改动。当前可能存在集合竞价 spike 相关在途文件，必须保护。默认不部署、不切流、不执行线上写操作、不停容器、不清 Docker cache、不改 sysctl；所有线上资源、性能复测、Docker/sysctl/容器动作必须等我单独授权。

硬边界：
1. 不修改 backend/app/services/low_buy/strategy_policy.py。
2. 不改变 production_score、priority board 排序语义、生产策略公式、风控阈值、交易日发布门控。
3. strategy_engine 保持 shadow-only，replacement_enabled=false。
4. 不把 research/ML/因子/重分析任务放回 Web 主进程。
5. portfolio_backtest_metrics 继续作为真实组合回测唯一事实源。
6. 不物理删除 frontend/ 或其它源码目录，除非我另行明确授权。
7. 本任务不处理 first_board OOS 策略调参。

按批次串行执行，每批先读相关代码和现有报告，再做最小改动，跑该批验收；失败要定位修复，不能删除核心断言或放松策略守卫：

D0 基线：记录 git 状态、分支、在途改动、权威文档和可触碰文件范围。
D1 结构化日志增强：保留现有 JsonLogFormatter/STRUCTURED_LOGS，只增强 extra 字段白名单和关键路径日志上下文；补 test_logging_config，不改业务行为。
D2 priority board 热读守卫：复核/增强查询计数和 golden 守卫；只有新测量证明查询随候选线性增长才改生产代码，且必须保持排序、production_score、priority_score、lane、shadow 字段零漂移。
D3 日期窗口测试规范：把 export_time helper 约定写入 docs/engineering-conventions.md，只迁移窗口 fixture 日期，不动业务规则固定日期。
D4 大 JSON 出库前置改造：不得直接删除或移动 docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json；先迁移脚本默认路径/测试/manifest，保留历史可追溯。
D5 scripts 分类：输出 scripts inventory 和 archive 建议；不默认移动脚本，无法证明无引用的标记 keep_until_owner_review。
D6 旧前端退役决策包：扫描 CI/Docker/backend/deploy/scripts/docs 引用，输出决策报告；不物理删除 frontend/。
D7 frontend-next chunk 测量：运行 build 和 chunk:profile；收益不足就写不拆结论，默认不改前端代码。
D8 线上授权包：只准备资源收口、只读性能复测、internal token 运维文档和报告模板；不执行线上动作。

必须交付：
- 所有新增 Markdown 报告放 docs/reports/。
- 如生成机器 JSON，放 backend/data/reports/ 或既有 artifact 目录，不把大型 JSON 放 docs/reports/。
- 最终说明改了哪些文件、跑了哪些命令、结果如何、哪些未跑及原因，并明确未部署、未切流、未执行线上写操作，除非我另行授权。
```

