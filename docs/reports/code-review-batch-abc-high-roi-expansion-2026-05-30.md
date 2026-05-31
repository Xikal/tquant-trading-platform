# 代码复审报告 · Batch A/B/C 高 ROI 平台扩展

> 复审日期：2026-05-30　性质：只复审、不改代码、不提交
> 仓库：`/Users/j/Documents/gupiao`
> 权威计划：`docs/superpowers/plans/2026-05-30-high-roi-platform-expansion.md`
> 提交范围：Base `576ab02d` → Head `2a6e8b95`（`git diff 576ab02d..2a6e8b95`，87 文件 / +6995 −277）
> Batch A：`a7a6f862` `2ebe8d5c` `32701ae9` `1191002d`
> Batch B：`b0f28153` `3ea105e8` `bdadc573` `1201558d` `37baff67`
> Batch C：`a980e641` `0e586ec1` `5a45d831` `2a6e8b95`
> 方法：按提交范围核验（`git show 2a6e8b95:<file>`），worktree 脏改动单列为环境风险，不混入 A/B/C 结论。

---

## 1. 复审结论

**不通过（合入当前提交范围会破坏生产）。**

Batch A/B/C 新增的 `decision_context` 决策层本身**实现质量高，且严格满足硬边界 #3/#4/#5**（晋级仅建议、组合执行复用既有口径、市场缺数据降级而非全局清空），feature flag 与 24M 报告口径在提交内均正确。

但存在一个 **S0 阻断**：整个 A/B/C 赖以成立的 **P0-A 地基（N 字降级为 RESEARCH + `participates_in_priority_board` 生产门 + 守卫测试）从未提交，只存在于未提交的 worktree 脏改动中**。在提交 HEAD `2a6e8b95` 上：

- `strategy_policy.CORE` 仍含 `n_pattern_long_wash` / `n_pattern_short_wash`；
- `production_scoring` 仍用旧 `PAUSED_PRODUCTION_STRATEGIES`（且 `n_pattern_long_wash` 未 paused）。

因此**按提交范围合入会让一只 24M 回撤 −51% 的策略（`n_pattern_long_wash`）以 CORE 满权重进入生产优先榜并取得 `production_score`，直接违反硬边界 #1**。当前“测试全绿”是**跑在带脏改动 worktree 上的假绿**，提交态本身会让守卫测试失败。

- **最高 ROI 部分：** 避坑过滤器（A2）+ 市场状态总闸（A3）+ 组合执行器复用（B2）——实现高价值且合规。
- **最大风险：** 地基（P0-A/P2）未提交，导致整批 A/B/C 不可作为干净提交范围合入。

---

## 2. 环境 / 工作区风险（必须先解决，否则一切验收无效）

**R1｜P0-A/P2 地基是未提交脏改动，且与无关脏文件混在一起。**

- worktree 脏文件含本批依赖的地基：`backend/app/services/low_buy/strategy_policy.py`、`production_scoring.py`、`production_scoring_config.py`、`backend/tests/test_low_buy_production_scoring.py`、`backend/app/core/security_config.py`、`backend/app/runtime/background_jobs.py`、`Dockerfile`、`.github/workflows/ci.yml`、`.gitignore`。
- 同时混有疑似无关历史脏改：`feishu_*`、`hermes_workflow_runner.py`、`agent_report_service.py`、`strategy_tracking_*`、`candidate_rules_n_pattern.py`、`ai_decision_support.py` 等。
- 证据：`git diff --name-only 576ab02d..2a6e8b95` 不含 `strategy_policy/production_scoring`；`git status --short` 含上述全部。
- 影响：既不能直接合入提交范围（缺地基 → 破生产），也不能简单“把 worktree 全提交”（会卷入无关改动）。
- 修正：把 P0-A/P2 地基**单独整理为前置提交**（与无关脏改动严格分离），rebase 到 A/B/C 之前，再重测。

---

## 3. 阻断问题 S0

### S0-1｜P0-A 地基未提交，提交态违反硬边界 #1
- **问题：** 提交 HEAD `2a6e8b95` 的 `strategy_policy.CORE = {first_board, volume_shrink, n_pattern_long_wash, n_pattern_short_wash}`；`production_scoring.py` 仍 `import PAUSED_PRODUCTION_STRATEGIES` 并以其为门（非 `participates_in_priority_board`）。
- **证据：**
  - `git show 2a6e8b95:backend/app/services/low_buy/strategy_policy.py` → :13-18 CORE 含 N 字；
  - `git show 2a6e8b95:backend/app/services/low_buy/production_scoring.py` → :18,:128 用 `PAUSED_PRODUCTION_STRATEGIES`；
  - `git show 2a6e8b95:backend/app/services/low_buy/production_scoring_config.py` → :137-141 PAUSED 含 `n_pattern_short_wash`，**不含** `n_pattern_long_wash`；
  - `production_scoring.py` 在 `git diff 576ab02d..2a6e8b95` 中为 **0 行**（不在范围），worktree 差异 64 行（未提交）；
  - `priority_items.py`（committed）:106 调 `score_low_buy_candidate_for_production` + :69/:88 套 gate 乘子；`priority_scoring.py:193` 以 `get_tier_weight` 给 CORE 权重 1.0。
- **影响：** 提交态下 `participates_in_priority_board("n_pattern_long_wash")==True` 且未 paused → 产出真实 `production_score` 并以 CORE 满权重进生产榜；`n_pattern_short_wash` 虽 paused（score=None）仍以 CORE 满权重进榜。**直接违反硬边界 #1。**
- **修正：** 将 worktree 的 `strategy_policy.py`（CORE={first_board,volume_shrink}）、`production_scoring.py`（改用 `participates_in_priority_board`、删除第二份 PAUSED 名单）、`production_scoring_config.py` 作为前置提交落地后再合 A/B/C，并重跑守卫测试。

### S0-2｜守卫测试“假绿”，提交态实际会红
- **问题：** `test_low_buy_production_scoring.py::test_n_pattern_long_wash_has_no_production_score_or_prior`（断言 long_wash 无 production_score）当前通过，但该测试文件本身是 **worktree-only（未提交）**；committed HEAD 测试中**无**该断言。
- **证据：** `git diff --quiet -- backend/tests/test_low_buy_production_scoring.py` → DIRTY；`git show 2a6e8b95:backend/tests/test_low_buy_production_scoring.py | rg n_pattern_long_wash` → 无命中；`PYTHONPATH=backend pytest backend/tests/test_low_buy_production_scoring.py` → 12 passed（跑在带脏改 worktree）。
- **影响：** “测试全绿”是基于未提交地基的假象；按提交态（N 字 CORE + long_wash 未 paused + 旧 PAUSED 门），该断言会失败 → 提交态 CI 红。验收结论被脏改动掩盖。
- **修正：** 测试与被测地基同批提交；在干净提交态（base + 本批前置地基）重跑全量，确认真绿后才接受验收。

---

## 4. 高优先级问题 S1

### S1-1｜24M 报告产物层级一致性
- **问题：** 提交内 `docs/reports/strategy_24m_duckdb_report.md` 收益口径正确（无裸“总收益”，含每日信号等权复利收益 + 真实组合 max5/max10，:24-26），但报告中策略**层级/建议**列若在带 worktree P0-A 的环境生成（N 字显示 RESEARCH/delete_candidate），将与提交态 `strategy_policy`（N 字=CORE）不一致。
- **证据：** 报告在范围内（diff --stat 130 行）；提交态 `strategy_policy` N 字=CORE。
- **影响：** 报告与提交代码事实源不一致，误导生产放行判断。
- **修正：** 地基前置提交后重生成报告，确保层级列 == 提交态 `strategy_policy`。

### S1-2｜新 RuntimeTask 归属与 research 门控逐条核验（需进一步验证）
- **问题：** 计划要求新增 task 类型在 `runtime_worker._execute_task` 注册并显式声明是否纳入 research/ml/factor 门控；本轮新增 `signal_attribution_refresh`/`event_risk_refresh`/`intraday_entry_snapshot_refresh`/`strategy_promotion_review` 等归属未逐条确认。
- **证据：** `analytics_handlers.py`、`runtime_worker.py` 均 committed-clean，但未逐行核验注册与门控分支。
- **影响：** 若研究型任务未门控或重任务回到 Web，违反硬边界 #5/#6。
- **修正：** 实测 `rg "register|_execute_task" backend/app/services/tasks/analytics_handlers.py backend/app/workers/runtime_worker.py` 核对每个新 task 归属与门控；确认 Web 仍 `WEB_RUNTIME_BACKGROUND_JOBS_ENABLED=false`（该 flag 在 worktree-dirty 的 compose/config，属 R1）。

### S1-3｜事件风险 LLM “拒绝买卖建议”约束需在提交态核验（需进一步验证）
- **问题：** `ai_decision_support.py` 为 worktree-dirty，C3 事件摘要“LLM 仅摘要、拒绝买卖建议”约束在提交态 vs worktree 可能不同。
- **证据：** `git status` 含 `backend/app/services/ai_decision_support.py` M。
- **影响：** 若约束仅在未提交脏改动里，提交态可能允许 LLM 输出买卖建议，违反硬边界 #6。
- **修正：** 以 `git show 2a6e8b95:backend/app/services/ai_decision_support.py` 核验提交态是否含硬约束；若也在脏改动里，归入 R1 一并前置提交。

---

## 5. 中低优先级问题 S2

- **S2-1｜promotion_engine 在 N=CORE 提交态下语义空转：** `get_strategy_tier("n_pattern_long_wash")` 返回 `core`，`current_tier="core"`，晋级建议对 N 字无意义。地基修正后自然解决。
- **S2-2｜`portfolio_executor` 顶层 `from scripts.low_buy_market_backtest_reporting import ...`：** 依赖 `scripts` 在 sys.path；需在 runbook/Verification 明确该 import 前提，避免 worker 容器内 ImportError（需实测 worker 容器内可导入）。
- **S2-3｜`event_cache.py` 新建但数据源由 C0 决定：** 提交态 `EVENT_RISK_PRODUCTION_BLOCK_ENABLED=False` 正确；需确认无源时仅摘要、`data_quality=missing`，不进生产阻断（与 C0 runbook 结论一致）。

---

## 6. 硬边界逐条核验（提交态 2a6e8b95）

| # | 边界 | 结论 | 证据 |
|---|---|---|---|
| 1 | 生产分仅 participates=True；N 字/RESEARCH 恒 None 不进榜 | **❌ 违反** | 提交态 N 字=CORE、long_wash 未 paused → 拿 production_score + 满权重进榜（S0-1） |
| 2 | 门控只做乘子/加减分/标记，不改策略规则、不自动改 policy | ✅ 符合 | `market_gate.py`/`sector_leader_gate.py` 只产 GateDecision+乘子；`promotion_engine` 不改 policy |
| 3 | 晋级仅建议、不自动生效 | ✅ 符合 | `promotion_engine.py:42,52,66 can_apply_override=False`；只 `_upsert_review`；`promotion_engine_auto_apply_enabled=False`(config:57) |
| 4 | 组合 max5/max10 单一实现，复用既有 | ✅ 符合 | `portfolio_executor.py:29` 薄封装直调 `portfolio_backtest_metrics` |
| 5 | 缺数据降级不全局清空 | ✅ 符合 | `market_gate.py:38-52` symbol→research_only、market-level→reduce+保留上日 |
| 6 | 重任务归 worker、Web 无后台 loop、不实盘、不换栈、新面板懒加载 | ⚠️ 大部分符合，部分待验 | `VirtualCardList.tsx` 在范围；Web 后台 flag 在 worktree-dirty(R1)；新 task 门控待核验(S1-2)；LLM 约束待核验(S1-3) |

---

## 7. 各 Batch 与 Acceptance 覆盖

| 项 | 提交态结论 | 证据 |
|---|---|---|
| A1 存储/schema/迁移/flags | ✅ 提交完整 | `config.py:51-57` 七个 flag 默认值正确；迁移在范围内 |
| A2 避坑过滤器 | ✅ 实现，⚠️ 依赖未提交 hard_risk 地基 | `hard_risk_filter.py` clean；`hard_risk.py` 改动需核验 |
| A3 市场总闸（降级） | ✅ 实现合规 | `market_gate.py` 全文 |
| B1 板块/龙头 | ✅ 实现 | `sector_leader_gate.py` clean、`priority_items.py:88` 接入 |
| B2 组合执行器 | ✅ 合规复用 | `portfolio_executor.py` |
| B3 晋级仅建议 | ✅ 合规 | `promotion_engine.py` |
| C0 数据门 runbook | ✅ 在范围 | `docs/high-roi-platform-expansion-runbook-2026-05-30.md`（250 行） |
| C1/C2/C3 | ⚠️ 实现存在，门控/LLM 约束待提交态核验 | S1-2、S1-3 |
| 24M 报告口径 | ✅ 提交正确，⚠️ 层级一致性 | S1-1 |
| 前端性能 | ✅ VirtualCardList 在范围 | `frontend/src/ui/list/VirtualCardList.tsx`（105 行） |

---

## 8. 最终建议

- **是否现在合入提交范围：否。** 直接合 `576ab02d..2a6e8b95` 会让 N 字以 CORE 进生产榜并拿 production_score，破坏生产（S0-1）。
- **必须先做的 2-3 件事：**
  1. 把 P0-A 地基整理成**独立前置提交**（`strategy_policy.py` CORE={first_board,volume_shrink}、`production_scoring.py` 改用 `participates_in_priority_board`、`production_scoring_config.py`、对应守卫测试），与无关脏改动严格分离（R1）。
  2. rebase A/B/C 到该前置提交之上，在**干净 worktree**（无脏改动）下重跑：`pytest backend/tests` 全量 + 守卫 `test_low_buy_production_scoring.py` + 前端 `api:check/lint/build/test`，确认**真绿**（非脏改动假绿，S0-2）。
  3. 地基提交后重生成 24M 报告，确认报告层级 == 提交态 `strategy_policy`（S1-1）。
- **可延后：** C1/C2/C3 的 research 门控与 LLM 约束逐条核验（S1-2/S1-3），随干净提交一并验。
- **必须写死防跑偏的边界：**
  - 生产分唯一门 = `participates_in_priority_board`；删除 `PAUSED_PRODUCTION_STRATEGIES` 第二份名单，保持单一事实源。
  - CI 必须在**干净提交态**跑 `test_low_buy_production_scoring.py`，禁止依赖 worktree 脏改动让其变绿。
  - `promotion_engine_auto_apply_enabled` 永久 False；`event_risk_production_block_enabled`、`intraday_entry_production_boost_enabled` 默认 False 直到对应证据/数据源到位。

> 一句话：**新决策层写得好且大体合规，但它“踩在”一摊未提交的地基上。** 当务之急不是改新代码，而是把 P0-A/P2 地基从 worktree 脏改动中**单独提交并与无关改动分离**；否则这批 A/B/C 在干净提交态下既破生产又会 CI 红。
```
