# 平台瘦身优化落地计划（2026-06-09）

## 1. 背景与目标

来源报告：`docs/reports/platform-slimming-audit-2026-06-09.md`。

本计划目标不是“清理磁盘”或“删功能”，而是在不影响交易闭环、生产排序、性能和可回滚能力的前提下，降低仓库体积、运行面复杂度、长期双维护成本和可选研究能力的认知负担。

核心结论：

1. 本地占盘大头是 `backend/data/`、`.venv`、Rust `target/`、`node_modules`，多数已 gitignore，属于开发机/运行时空间，不是仓库瘦身主战场。
2. 真正进入仓库的膨胀集中在 `docs/reports/` 的大 JSON 和截图产物，优先出库/归档，ROI 最高且风险最低。
3. 生产低吸、priority board、market、paper、backtest、BFF、任务队列是 P0，不参与删除。
4. 研究/ML/因子/agent/AKeyLevel/trading_experience 当前多数已 default-off 或 hidden，优先维持门控和标记，不直接删除。
5. 两套前端长期并存是架构成本，但 cutover 决策前不得移除任一套。

## 2. 硬边界

全阶段必须遵守：

- 不改 `backend/app/services/low_buy/strategy_policy.py`。
- 不改变生产策略语义、生产排序、`production_score`、priority board 口径。
- 不删除或停用核心闭环：`monitor -> monitor/market -> analysis -> playbook -> backtest -> paper -> data -> settings`。
- 不停核心 job：`low_buy_full_scan`、`daily_bar_refresh`、`latest_data_watchdog`、`low_buy_materialization_refresh`、market review、watchlist、paper 相关任务。
- 不把 DuckDB/Parquet 作为生产交易事实源。
- 不把 research-only/shadow 能力接入生产排序。
- 不改旧前端生产代码，除非当轮任务明确要求。
- 不部署、不切流，除非用户另行授权。
- 删除/移动文件前必须先做引用检查、列 manifest、保留可恢复路径。

## 3. 分级处置原则

| 等级 | 对象 | 处置原则 |
|---|---|---|
| P0 | low_buy 生产、market、paper、backtest、tasks、BFF、OpenAPI、核心前端闭环 | 不删除、不停用，只做读路径和入口瘦身 |
| P1 | 大 route、大 service、重复文档索引 | 保留契约，拆入口/文档索引，减少维护成本 |
| P2 | AKeyLevel、trading_experience、agent、部分研究 UI | 维持 hidden/default-off，补状态记录 |
| P3 | ML/因子/研究 job | 确认默认关，避免误开，保留测试 |
| P4 | docs/reports 大 JSON、截图、一次性机器产物 | 出库/归档，仓库保留 Markdown 摘要和 manifest |

## 4. Phase 0：执行前基线

目标：确保瘦身有可比较基线，保护已有改动。

任务：

1. 执行并记录：
   - `git status --short`
   - `git ls-files | wc -l`
   - `du -sh docs/reports backend/data backend/.venv rust/tquant-rs/target frontend/node_modules frontend-next/node_modules 2>/dev/null`
   - `git ls-files docs/reports | xargs -I{} du -k "{}" | sort -nr | head -40`
2. 输出基线报告：`docs/reports/platform-slimming-baseline-2026-06-09.md`。
3. 明确本轮不会触碰 P0、旧前端生产代码、策略排序逻辑。

验收：

- 基线报告包含仓库文件数、`docs/reports` 跟踪大文件 TOP40、本地大目录大小。
- `git diff --check` 通过。

## 5. Phase 1：零风险仓库瘦身

目标：把机器产物从 `docs/reports/` 人读文档区移出，仓库保留摘要和指针。

任务：

1. 建立 artifact manifest：
   - 新增 `docs/reports/platform-slimming-artifact-manifest-2026-06-09.md`
   - 记录每个大文件：原路径、大小、类型、生成日期、引用位置、建议归档位置、恢复方式。
2. 引用检查：
   - 对审计报告点名文件逐个执行 `rg --fixed-strings "<basename>"`
   - 如果只有报告引用，可归档；如果脚本或测试引用，先不移动。
3. 归档策略：
   - `.md` 人读报告留在 `docs/reports/`
   - 大 JSON、截图、zip、长机器产物移动到 `backend/data/reports/archived/2026-06-09/` 或外部 artifacts 指针
   - 仓库内新增/保留同名 `.md` 摘要，说明原产物位置和恢复命令
4. 首批候选：
   - `docs/reports/front-row-weighted-production-scoring-backtest-2026-05-29.json`
   - `docs/reports/strategy-24m-*.json`
   - `docs/reports/market-state-guard-walk-forward*`
   - `docs/reports/daily-history-backfill-runs*`
   - frontend-next 视觉截图目录，仅保留最新签收索引和必要代表图

验收：

- `docs/reports/` 不再新增大型机器 JSON。
- 被移动文件都有 manifest 记录和恢复路径。
- `rg` 引用检查记录入 manifest。
- `git diff --check` 通过。

回滚：

- 根据 manifest 使用 `git checkout <old_sha> -- <path>` 或从 artifact 路径复制回原位置。

## 6. Phase 2：默认关闭能力复核

目标：确认研究/ML/因子/agent/AKeyLevel/trading_experience 不在默认运行路径消耗资源。

任务：

1. 检查配置默认值：
   - `tquant_research_jobs_enabled`
   - `tquant_ml_jobs_enabled`
   - `tquant_factor_jobs_enabled`
   - `a_key_level_engine_enabled`
   - `trading_experience_suite_enabled`
   - agent/MCP/Hermes/通知相关开关
2. 检查实际环境样例和运行配置，确认没有误开。
3. 新增报告：`docs/reports/platform-slimming-feature-flag-review-2026-06-09.md`。
4. 对需要长期隐藏的模块补文档状态：`default_off`、`research_only` 或 `hidden`，不删代码。

验收：

- 报告列出每个模块的 flag、默认值、当前环境值、入口是否可见、任务是否会运行。
- 不改变生产排序和核心 job。
- 相关测试仍通过。

建议验证：

- `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_engine_boundary.py backend/tests/test_strategy_engine_production_gate_guards.py -q`
- 对 trading_experience/key_levels 仅跑现有契约测试，不启用生产入口。

## 7. Phase 3：死代码与入口引用清单

目标：在不删除的前提下，建立可审计的移除候选清单。

任务：

1. 对 P2/P3/P4 候选做 import/route/job/测试引用检查：
   - `backend/app/services/ml_signal`
   - `backend/app/services/factor_mining`
   - `backend/app/services/decision_context`
   - `backend/app/services/strategy_improvement`
   - `backend/app/services/trading_experience`
   - `backend/app/services/key_levels`
   - agent 相关 route/job
   - 旧前端 `ritual-ui`、`key-levels`、`trading-experience`
2. 输出 `docs/reports/platform-slimming-remove-candidate-inventory-2026-06-09.md`。
3. 给每个候选标状态：
   - `active`
   - `default_off`
   - `research_only`
   - `deprecated`
   - `remove_candidate`
4. 任何 `remove_candidate` 必须写明替代路径、恢复路径、最近一次引用检查。

验收：

- 只产出清单和状态，不删除代码。
- P0 模块全部标为 protected。
- 清单覆盖 route、service、job、frontend entry、tests。

## 8. Phase 4：入口瘦身与路由拆分

目标：降低大 route 文件维护成本，不改变 API 契约。

候选：

- `backend/app/api/routes/bff.py`
- `backend/app/api/routes/backtests.py`
- `backend/app/api/routes/screeners.py`
- `backend/app/api/routes/strategy_tracking.py`

任务：

1. 先写边界说明，明确 route 只做鉴权、参数解析、响应编排。
2. 抽 query/service helper，保留原 endpoint path、operationId、response schema。
3. 每个 route 文件分批改，每批只拆一个文件。
4. 每批都跑对应 API 契约测试和前端 typecheck。

验收：

- OpenAPI diff 不出现破坏性变更。
- 后端目标 pytest 通过。
- `frontend-next npm run typecheck` 通过。

不做：

- 不重写低吸策略。
- 不改 scoring/sorting。
- 不把重任务塞回 Web 请求线程。

## 9. Phase 5：前端双栈收敛决策

目标：为 cutover 后减少双维护成本做决策准备，不在本计划中直接删除任一前端。

任务：

1. 更新双前端成本报告：
   - 依赖大小
   - 构建时间
   - 页面覆盖
   - E2E 覆盖
   - 已切流/未切流页面
2. 输出：`docs/reports/frontend-stack-consolidation-readiness-2026-06-09.md`。
3. 给出三种选项：
   - 保留旧前端生产，新前端继续 shadow
   - frontend-next 全面 cutover 后归档旧前端
   - 按页面长期双栈保留

验收：

- 只做报告，不部署、不切流。
- cutover 仍需用户单独授权。

## 10. 推荐执行顺序

1. Phase 0：基线。
2. Phase 1：`docs/reports` 大产物出库/manifest。
3. Phase 2：feature flag/default-off 复核。
4. Phase 3：remove candidate inventory。
5. Phase 4：只在用户确认后做 route 瘦身。
6. Phase 5：只在 cutover 决策前做前端双栈收敛评估。

## 11. 最低验证命令

按阶段选择，不要求每次全跑：

```bash
cd /Users/j/Documents/gupiao
git status --short
git diff --check

cd /Users/j/Documents/gupiao/frontend-next
npm run typecheck
npm run lint
npm test -- --run
npm run build

cd /Users/j/Documents/gupiao
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_strategy_engine_boundary.py \
  backend/tests/test_strategy_engine_production_gate_guards.py \
  backend/tests/test_bff_monitor_workspace.py \
  backend/tests/test_bff_strategy_workspace.py \
  backend/tests/test_low_buy_read_paths.py \
  -q
```

如 Phase 4 涉及后端 route 拆分，还必须跑对应 route/API 测试和 OpenAPI 导出/类型生成检查。

## 12. 交付物清单

必须产出：

1. `docs/reports/platform-slimming-baseline-2026-06-09.md`
2. `docs/reports/platform-slimming-artifact-manifest-2026-06-09.md`
3. `docs/reports/platform-slimming-feature-flag-review-2026-06-09.md`
4. `docs/reports/platform-slimming-remove-candidate-inventory-2026-06-09.md`
5. 每阶段验证命令和结果记录

可选产出：

1. `docs/reports/frontend-stack-consolidation-readiness-2026-06-09.md`
2. `docs/operations/artifact-archive-runbook.md`

## 13. 执行提示词

```text
你在 /Users/j/Documents/gupiao 工作。请根据 docs/reports/platform-slimming-audit-2026-06-09.md 和 docs/platform-slimming-optimization-execution-plan-2026-06-09.md 执行平台瘦身落地，但本轮不部署、不切流、不删除生产核心能力。

开始前必须执行：git status --short。保护已有未提交/未跟踪文件，不回滚他人改动。

硬边界：
1. 不改 strategy_policy.py，不改变生产策略语义、production_score、priority_board 排序和口径。
2. 不停 low_buy、market、paper、backtest、tasks、BFF、monitor_snapshot_service、RuntimeTaskQueue 核心能力。
3. 不把 research/shadow/ML/factor/agent 能力接入生产排序。
4. 不改旧前端生产代码，除非明确需要且先说明。
5. 不部署、不切流；frontend-next/旧 frontend 收敛只做报告，不执行删除。
6. 移动/归档文件前必须先做 rg 引用检查并写 manifest；没有恢复路径不得移动。

执行范围按顺序：
Phase 0：生成 docs/reports/platform-slimming-baseline-2026-06-09.md，记录 git 文件数、docs/reports 跟踪大文件 TOP40、本地大目录大小。
Phase 1：对 docs/reports 大 JSON/截图/一次性机器产物做 artifact manifest；只移动确认无运行引用的机器产物到 backend/data/reports/archived/2026-06-09/ 或保留外部 artifacts 指针，仓库保留 md 摘要与恢复方式。
Phase 2：复核 research/ML/factor/AKeyLevel/trading_experience/agent feature flag 默认值和当前环境值，输出 docs/reports/platform-slimming-feature-flag-review-2026-06-09.md；只记录和标 default_off/research_only，不启用不删除。
Phase 3：建立 remove candidate inventory，覆盖 route/service/job/frontend entry/tests，输出 docs/reports/platform-slimming-remove-candidate-inventory-2026-06-09.md；只标 active/default_off/research_only/deprecated/remove_candidate，不实际删代码。

最低验证：
cd /Users/j/Documents/gupiao && git diff --check && git status --short
如触碰 frontend-next：cd frontend-next && npm run typecheck && npm run lint && npm test -- --run && npm run build
如触碰后端：PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_strategy_engine_boundary.py backend/tests/test_strategy_engine_production_gate_guards.py backend/tests/test_bff_monitor_workspace.py backend/tests/test_low_buy_read_paths.py -q

最终报告必须说明：完成项、移动/归档清单、未处理项、保护的 P0 模块、flag 状态、验证结果、是否影响平台功能。默认结论：未部署、未切流；cutover 和真实删除仍需用户单独授权。
```
