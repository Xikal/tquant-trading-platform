# 策略成功率优化完整开发计划（2026-06-11）

> 权威输入：`docs/strategy-success-rate-optimization-plan-2026-06-10.md`、`docs/strategy-success-rate-optimization-requirements-2026-06-11.md`
> 当前性质：可执行开发计划与提示词。本文用于后续实现，不代表已执行回测、上线或生产变更。
> 总原则：先诊断、再 research/shadow 回测、再评审；没有 24M + walk-forward + OOS + 守卫测试证据，不改生产策略语义。

## 1. 执行边界

### 必须遵守

1. 开始前执行：
   - `git status --short`
   - `git branch --show-current`
2. 保护当前所有在途改动，不回滚、不删除、不覆盖与本任务无关的改动。
3. 默认不部署、不切流、不执行线上写操作、不停容器、不清 Docker cache、不改 sysctl。
4. 线上账本捕获、线上任务写库、生产发布、生产策略切换必须等用户单独授权。
5. 研究/ML/因子/重分析任务不得放回 Web 主进程，必须走脚本、worker 或离线报告产物。

### 硬边界

1. 不修改 `backend/app/services/low_buy/strategy_policy.py`。
2. 不改变 `production_score`、priority board 排序语义、生产策略公式、风控阈值、交易日发布门控。
3. `strategy_engine` 保持 shadow-only，`replacement_enabled=false`。
4. `portfolio_backtest_metrics` 继续作为真实组合回测唯一事实源，不并行造组合收益口径。
5. `spike_return_*`、`avg_max_gain_5d`、`max_gain_5d` 只用于诊断冲高机会，不作为可成交收益或生产晋级指标。
6. 缺数据必须显式降级或阻断，不造样本、不裁剪亏损样本。

## 2. 目标交付

本轮最终交付应包含：

1. 基线报告：`docs/reports/strategy-success-rate-baseline-YYYY-MM-DD.md`
2. OOS 诊断：`docs/reports/first-board-oos-diagnosis-YYYY-MM-DD.md`
3. 回吐池与出场矩阵：`docs/reports/strategy-exit-variants-YYYY-MM-DD.md`
4. 市场状态矩阵：`docs/reports/strategy-market-state-matrix-YYYY-MM-DD.md`
5. 成本/滑点/流动性报告：`docs/reports/strategy-cost-liquidity-sensitivity-YYYY-MM-DD.md`
6. 去相关/组合执行报告：`docs/reports/strategy-correlation-dedup-YYYY-MM-DD.md`
7. 退役策略研究报告：`docs/reports/strategy-retired-reentry-research-YYYY-MM-DD.md`
8. 漂移观察模板：`docs/reports/strategy-drift-observation-YYYY-MM-DD.md`
9. 对应机器可读 JSON 产物，优先落 `backend/data/reports/strategy-success-rate/`
10. 测试与命令执行记录，写入最终总结或 `docs/reports/strategy-success-rate-implementation-report-YYYY-MM-DD.md`

## 3. 批次计划

### D0 基线与现状保护

目的：确认输入、代码锚点和测试锚点，不做业务变更。

实施：

1. 记录 git 状态和当前分支。
2. 核对权威文档：
   - `docs/strategy-success-rate-optimization-plan-2026-06-10.md`
   - `docs/strategy-success-rate-optimization-requirements-2026-06-11.md`
   - `docs/reports/strategy_24m_duckdb_report.md`
   - `TRADING_QUANT_LEAD_PLAYBOOK.md`
   - `docs/engineering-conventions.md`
3. 核对现有代码锚点：
   - `backend/scripts/low_buy_market_backtest_reporting.py`
   - `backend/scripts/low_buy_execution_matrix.py`
   - `backend/app/services/low_buy/execution_simulation.py`
   - `backend/app/services/decision_context/market_gate.py`
   - `backend/app/services/low_buy/intraday_confirmation.py`
   - `backend/app/services/track_record/`
4. 输出基线报告，明确数据窗口、策略样本、当前问题、已有能力和受限能力。

验收：

```bash
git status --short
git branch --show-current
PYTHONPATH=backend backend/.venv/bin/python -m pytest -q backend/tests/test_strategy_24m_duckdb_report.py
```

通过标准：

1. 基线报告能复述 `first_board`、`volume_shrink`、`late_session_strong_support` 的 24M 核心指标。
2. 报告明确本轮不改生产语义。
3. 如测试环境不可用，记录失败原因，不用删除断言绕过。

### D1 first_board OOS 与回吐池诊断

目的：先定位 `first_board` 最近 OOS 失效和三策略浮盈回吐来源。

建议新增：

1. `backend/scripts/strategy_success_rate_diagnostics.py`
2. `backend/tests/test_strategy_success_rate_diagnostics.py`

实现要求：

1. 从 24M 回测产物或现有 outcome/report 结构读取成交记录。
2. 输出 `first_board` quarter_proxy/OOS 样本的月份、market_state、板块/行业、成本敏感性拆解。
3. 输出三策略回吐池统计：`max_gain_5d >= 3%` 且 `return_5d <= 0`。
4. 诊断结论必须落入：
   - 退潮/恐慌状态门控不足；
   - 首板生态变化；
   - 成本/滑点或样本期特例；
   - 数据不足，阻断调参。

验收：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest -q backend/tests/test_strategy_success_rate_diagnostics.py
```

通过标准：

1. 生成 `docs/reports/first-board-oos-diagnosis-YYYY-MM-DD.md`。
2. 生成 `docs/reports/strategy-success-rate-baseline-YYYY-MM-DD.md` 或补充基线章节。
3. 无明确诊断结论时，后续只能继续诊断，不能调参。

### D2 出场矩阵与分批出场研究模型

目的：先复用现有出场矩阵，再决定是否补严格分批出场能力。

优先复用：

1. `backend/scripts/low_buy_execution_matrix.py`
2. `backend/app/services/low_buy/execution_simulation.py`
3. `backend/tests/test_low_buy_trade_controls.py`
4. `backend/tests/test_low_buy_backtest_isolation.py`

实施步骤：

1. 先跑现有矩阵：`default_exit`、固定止损、ATR 止损、T+1/T+2、`quick_tp3_trailing1`。
2. 若“+3% 止盈一半 + 剩余移动止损”仍是必需研究项，再扩展 research-only 模型：
   - `partial_take_profit_pct`
   - `partial_take_profit_sell_ratio`
   - `partial_trailing_stop_pct`
   - 分批成交净收益与费用计算
3. 默认参数不变，未传 override 时现有生产/回测行为必须字节级保持。
4. 报告必须对照 baseline，不允许只展示胜出的变体。

建议命令：

```bash
PYTHONPATH=backend backend/.venv/bin/python backend/scripts/low_buy_execution_matrix.py \
  --months 24 \
  --strategies first_board,volume_shrink,late_session_strong_support \
  --states confirmed \
  --engine fast \
  --materialization-mode isolated
```

验收：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest -q \
  backend/tests/test_low_buy_trade_controls.py \
  backend/tests/test_low_buy_backtest_isolation.py
```

通过标准：

1. `docs/reports/strategy-exit-variants-YYYY-MM-DD.md` 有基线和全部变体对照。
2. 新增分批出场时，测试覆盖费用、T+1、止损优先级、半仓收益合成。
3. 未改 `strategy_policy.py`，未改生产排序。

### D3 策略 x 市场状态矩阵

目的：验证亏损是否集中在特定市场状态，再决定是否研究策略级状态门控。

建议新增：

1. `backend/scripts/strategy_market_state_matrix.py`
2. `backend/tests/test_strategy_market_state_matrix.py`

涉及现有文件：

1. `backend/app/services/decision_context/market_gate.py`
2. `backend/tests/test_decision_context_market_gate.py`
3. `backend/scripts/low_buy_market_backtest_reporting.py`

实施要求：

1. 输出 `strategy_key x market_state` 的样本数、成交数、胜率、PF、平均单笔、最大回撤。
2. 只生成 research variant，不直接改全局 `market_gate`。
3. 如果新增策略级门控配置，必须 feature flag 默认关闭，并补 allow/reduce/block 测试。

验收：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest -q \
  backend/tests/test_decision_context_market_gate.py \
  backend/tests/test_strategy_market_state_matrix.py
```

通过标准：

1. 生成 `docs/reports/strategy-market-state-matrix-YYYY-MM-DD.md`。
2. 每个状态门控建议都有样本量和 OOS 影响说明。
3. priority board 原语义未漂移。

### D4 volume_shrink 分时确认研究

目的：验证 `volume_shrink + VWAP/尾盘确认` 是否能减少假信号。

涉及现有文件：

1. `backend/app/services/low_buy/intraday_confirmation.py`
2. `backend/tests/test_low_buy_intraday_confirmation.py`

建议新增：

1. `backend/scripts/strategy_intraday_confirmation_research.py`
2. `backend/tests/test_strategy_intraday_confirmation_research.py`

实施要求：

1. 不直接把 `volume_shrink` 加入生产 `VWAP_CONFIRMATION_STRATEGIES` 或 `LATE_SESSION_CONFIRMATION_STRATEGIES`。
2. 先检查分钟数据覆盖率；不足则报告 `partial_minute_coverage` 或 `blocked_by_data`。
3. 样本留存 >= 60%，PF、胜率、OOS 不劣化，才进入生产评审。

验收：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest -q \
  backend/tests/test_low_buy_intraday_confirmation.py \
  backend/tests/test_strategy_intraday_confirmation_research.py
```

通过标准：

1. 生成 `docs/reports/strategy-volume-shrink-intraday-confirmation-YYYY-MM-DD.md`。
2. 无分钟数据时不能假通过。
3. 不产生生产确认集合变更。

### D5 成本/滑点/流动性分桶

目的：验证低流动性和额外成本是否吞噬 `volume_shrink` 的薄利润。

涉及现有文件：

1. `backend/scripts/low_buy_market_backtest_reporting.py`
2. `backend/tests/test_low_buy_backtest_isolation.py`

建议新增：

1. `backend/scripts/strategy_cost_liquidity_sensitivity.py`
2. `backend/tests/test_strategy_cost_liquidity_sensitivity.py`

实施要求：

1. 基于 `amount` 分桶：`<5000万`、`5000万-2亿`、`>2亿`。
2. 每桶输出基础成本、额外 bps、PF、平均单笔、真实组合 max5/max10。
3. 可扩展 `portfolio_backtest_metrics` 的可选参数，但默认行为必须完全不变。
4. 如果样本留存低于 70%，默认不采纳。

验收：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest -q \
  backend/tests/test_low_buy_backtest_isolation.py \
  backend/tests/test_strategy_cost_liquidity_sensitivity.py
```

通过标准：

1. 生成 `docs/reports/strategy-cost-liquidity-sensitivity-YYYY-MM-DD.md`。
2. 流动性桶、成本映射和总成本假设可复查。
3. 未直接改生产流动性阈值。

### D6 信号去相关与组合执行层变体

目的：统计核心策略同日同票/同板块重叠，并验证组合层去重是否降低回撤。

涉及现有文件：

1. `backend/scripts/low_buy_market_backtest_reporting.py`
2. `backend/tests/test_low_buy_backtest_isolation.py`

建议新增：

1. `backend/scripts/strategy_correlation_dedup.py`
2. `backend/tests/test_strategy_correlation_dedup.py`

实施要求：

1. 统计 `first_board` 与 `volume_shrink` 的同日同票、同日同板块、持仓重叠率。
2. 只有重叠率 > 15% 且拖累组合收益时，才研究“同票同日保留 production/priority 分高者”。
3. 变体只影响组合执行层，不改变单策略信号。

验收：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest -q \
  backend/tests/test_low_buy_backtest_isolation.py \
  backend/tests/test_strategy_correlation_dedup.py
```

通过标准：

1. 生成 `docs/reports/strategy-correlation-dedup-YYYY-MM-DD.md`。
2. 单策略口径和组合口径分开展示。
3. `same_symbol_reentry_blocked` 既有语义不变。

### D7 退役策略回归路径

目的：给 `late_session_strong_support` 和 N 字家族一条证据驱动路径，不人工捞。

涉及现有文件：

1. `backend/tests/test_n_pattern_observe_confirmed.py`
2. `backend/scripts/low_buy_market_backtest.py`
3. `backend/scripts/low_buy_execution_matrix.py`

实施要求：

1. `late_session_strong_support` 不升权，继续低样本限权。
2. N 字家族只跑 `observe_confirmed` 研究变体。
3. 所有结论只写 review/report，不写生产 override。

验收：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest -q backend/tests/test_n_pattern_observe_confirmed.py
```

通过标准：

1. 生成 `docs/reports/strategy-retired-reentry-research-YYYY-MM-DD.md`。
2. 不修改 `strategy_policy.py`。
3. 不新增生产候选。

### D8 track record 漂移观察包

目的：准备实战漂移闭环，但不在未授权情况下写线上库。

涉及现有文件：

1. `backend/app/services/track_record/signal_ledger.py`
2. `backend/app/services/track_record/drift_metrics.py`
3. `backend/app/services/track_record/drift_alerts.py`
4. `backend/tests/test_track_record_ledger.py`
5. `backend/tests/test_track_record_realized.py`
6. `backend/tests/test_track_record_drift.py`

实施要求：

1. 本地/测试库验证 append-only、`signal_time`、`data_cutoff_time`、`return_start_time`。
2. `DRIFT_ALERT_ENABLED=false` 默认保持。
3. 线上捕获任务只准备命令和授权说明，不执行。

验收：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest -q \
  backend/tests/test_track_record_ledger.py \
  backend/tests/test_track_record_realized.py \
  backend/tests/test_track_record_drift.py
```

通过标准：

1. 生成 `docs/reports/strategy-drift-observation-YYYY-MM-DD.md`。
2. 漂移结论只 advisory，不自动改分层。
3. 交付说明明确“未执行线上写操作”。

### D9 生产评审包

目的：只在证据完整时准备生产评审，不默认改生产代码。

触发条件：

1. 至少一个变体在 24M、walk-forward、OOS、真实组合、成本敏感性上全部过门。
2. 所有相关守卫测试全绿。
3. 有 feature flag、回滚方案和生产影响说明。

实施：

1. 输出 `docs/reports/strategy-success-rate-production-review-YYYY-MM-DD.md`。
2. 说明是否需要改生产代码；如需要，列出最小改动文件和风险。
3. 等用户单独授权后，才进入生产代码变更。

全量验收：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests
```

生产敏感守卫：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest -q \
  backend/tests/test_low_buy_production_scoring.py \
  backend/tests/test_low_buy_priority_board_strategy_variants.py \
  backend/tests/test_strategy_engine_production_gate_guards.py \
  backend/tests/test_strategy_engine_boundary.py
```

## 4. 推荐提交策略

1. D0-D1：诊断与基线报告一个 commit。
2. D2：出场矩阵/分批出场模型一个 commit。
3. D3-D4：状态门控矩阵和分时确认研究一个 commit。
4. D5-D6：成本分桶和组合去相关一个 commit。
5. D7-D8：退役策略和漂移观察包一个 commit。
6. D9：生产评审包单独 commit；生产代码变更如获授权，另开 commit。

每个 commit 前后都执行 `git status --short`，交付说明必须列出命令、结果、未跑项及原因。

## 5. 可复制执行提示词

```text
你现在在 /Users/j/Documents/gupiao 仓库执行“策略成功率优化收口”开发任务。请严格依据：
- docs/strategy-success-rate-optimization-plan-2026-06-10.md
- docs/strategy-success-rate-optimization-requirements-2026-06-11.md
- docs/strategy-success-rate-optimization-development-plan-2026-06-11.md
- docs/engineering-conventions.md
- TRADING_QUANT_LEAD_PLAYBOOK.md

开始前必须执行 git status --short 和 git branch --show-current，保护所有在途改动；不要回滚、删除或覆盖与本任务无关的改动。默认不部署、不切流、不执行线上写操作、不停容器、不清 Docker cache、不改 sysctl；线上账本捕获、线上任务写库、生产发布必须等我单独授权。

硬边界：不修改 backend/app/services/low_buy/strategy_policy.py；不改变 production_score、priority board 排序语义、生产策略公式、风控阈值、交易日发布门控；strategy_engine 保持 shadow-only，replacement_enabled=false；不把 research/ML/因子/重分析任务放回 Web 主进程；portfolio_backtest_metrics 继续作为真实组合回测唯一事实源；不得把 spike_return_*、avg_max_gain_5d、max_gain_5d 当作生产晋级收益指标。

按批次串行执行，每批先读现有代码与报告，再实现最小改动，跑该批验收；失败要定位修复，不能删除核心断言或放松策略守卫：
D0 基线：核对 24M 报告、策略层级、现有脚本/测试，输出 strategy-success-rate-baseline 报告。
D1 诊断：新增 first_board OOS 诊断与三策略回吐池统计，输出 first-board-oos-diagnosis；无明确结论不得调参。
D2 出场：先跑现有 low_buy_execution_matrix；如确需“止盈一半+剩余移动止损”，只新增 research-only 分批出场模型和测试，默认行为不变。
D3 状态：输出 strategy x market_state 矩阵；策略级门控只能 research/flag-off，不改生产门控语义。
D4 确认：研究 volume_shrink + VWAP/尾盘确认；分钟数据不足必须 blocked_by_data/partial_minute_coverage，不得直接加入生产确认集合。
D5 成本：按成交额分桶做成本/滑点敏感性；可扩展可选研究参数，但 portfolio_backtest_metrics 默认行为不变。
D6 去相关：统计同日同票/同板块重叠；只在组合执行层研究保留高分者，不改单策略信号。
D7 回归：late_session 继续低样本限权；N 字仅 observe_confirmed 研究态 24M 复验，不写生产 override。
D8 漂移：只准备 track record 漂移观察包和本地测试；DRIFT_ALERT_ENABLED 默认 false，不执行线上捕获。
D9 评审：只有 24M、walk-forward、OOS、真实组合、成本敏感性、守卫测试全部过门，才输出生产评审包；生产代码变更需另行授权。

重点文件锚点：
backend/scripts/low_buy_market_backtest_reporting.py
backend/scripts/low_buy_execution_matrix.py
backend/app/services/low_buy/execution_simulation.py
backend/app/services/decision_context/market_gate.py
backend/app/services/low_buy/intraday_confirmation.py
backend/app/services/track_record/
backend/tests/test_low_buy_trade_controls.py
backend/tests/test_low_buy_backtest_isolation.py
backend/tests/test_decision_context_market_gate.py
backend/tests/test_low_buy_intraday_confirmation.py
backend/tests/test_track_record_ledger.py
backend/tests/test_track_record_realized.py
backend/tests/test_track_record_drift.py
backend/tests/test_low_buy_production_scoring.py
backend/tests/test_low_buy_priority_board_strategy_variants.py
backend/tests/test_strategy_engine_production_gate_guards.py
backend/tests/test_strategy_engine_boundary.py

必须交付：各批 Markdown 报告放 docs/reports/，大型 JSON 放 backend/data/reports/strategy-success-rate/；最终说明改了哪些文件、跑了哪些命令、结果如何、哪些未跑及原因，并明确未部署/未切流/未执行线上写操作，除非我另行授权。
```
