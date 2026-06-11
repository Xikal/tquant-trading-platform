# 策略成功率优化需求文档（2026-06-11）

> 来源计划：`docs/strategy-success-rate-optimization-plan-2026-06-10.md`
> 核验结论：计划中识别的问题成立，解决方向整体可行；但所有优化必须先以 research/shadow 形式验证，不能直接改生产策略、生产排序、`production_score`、风控阈值或交易日发布门控。
> 核验方式：只读核对现有报告、脚本、服务与测试；本需求文档不执行回测、不部署、不切流、不写线上数据。

## 1. 背景

2026-05-31 生成的 `docs/reports/strategy_24m_duckdb_report.md` 已覆盖 2024-05-31 至 2026-05-31 的 24 个月日线窗口，Manifest 完整性为 `ok`。报告显示当前生产层策略存在明确优化空间：

| 策略 | 当前层级 | 主要问题 | 核验结论 |
| --- | --- | --- | --- |
| `first_board` | core | 样本内强，但最近 quarter_proxy OOS 为 PF 0.75、收益 -1.01% | 问题成立，必须先诊断 OOS 失效原因 |
| `volume_shrink` | core | 平均单笔 0.619%、最大回撤 -13.24%、OOS PF 0.90 | 问题成立，对成本、滑点、状态门控最敏感 |
| `late_session_strong_support` | auxiliary | 样本 58、walk-forward 0/7 | 限权合理，不能仅凭高 PF 升权 |
| N 字家族等研究策略 | research | raw 信号回撤大或 PF 不足 | 只能研究态复验，不能人工捞回生产 |

胜率提升只能作为辅助目标。最终准入必须同时验证净期望、PF、最大回撤、样本外稳定性、交易成本敏感性和真实组合 max5/max10 结果。

## 2. 当前项目基线

已具备的可复用能力：

1. 24M DuckDB 报告与数据完整性门禁：`docs/reports/strategy_24m_duckdb_report.md`、`backend/app/services/analytics/report_queries.py`。
2. 低吸执行回测与组合事实源：`backend/scripts/low_buy_market_backtest.py`、`backend/scripts/low_buy_execution_matrix.py`、`backend/scripts/low_buy_market_backtest_reporting.py` 的 `portfolio_backtest_metrics`。
3. 研究态出场覆盖参数：`ExecutionSimulationOverride` 已支持 `stop_loss_pct`、`atr_stop_multiplier`、`first_take_profit_pct`、`trailing_stop_pct`、`max_holding_days`、`force_t1_exit`、`force_t2_exit`。
4. 市场状态门控：`backend/app/services/decision_context/market_gate.py` 已有 allow/reduce/block 状态机和守卫测试。
5. 分时确认：`backend/app/services/low_buy/intraday_confirmation.py` 已支持 VWAP 与尾盘确认，但当前策略集合不包含 `volume_shrink`。
6. 真实组合约束：`portfolio_backtest_metrics` 已有同票持仓期间不重复、策略日限制、板块限制、弱市仓位上限、额外成本 bps 压测。
7. track record 账本与漂移监控：`backend/app/services/track_record/*`、`backend/tests/test_track_record_ledger.py`、`backend/tests/test_track_record_drift.py` 已覆盖 append-only、无自动策略变更、告警 flag 门控。
8. 策略引擎隔离：`backend/app/services/strategy_engine/shadow.py` 明确 `shadow_only=true`、`replacement_enabled=false`。

需要补齐或谨慎处理的能力：

1. 分批止盈卖出一半尚不是现有执行模拟的严格能力；当前只支持一次性触发首次止盈或移动防守。
2. `volume_shrink` 分时确认需要分钟数据覆盖率和研究态回测，不得直接加入生产确认集合。
3. 按流动性分桶的滑点/冲击成本尚未成为组合事实源参数，只能先做研究报告或扩展回测参数。
4. 策略级市场状态门控不能直接替换全局生产门控，必须以矩阵报告和守卫测试驱动。

## 3. 目标

1. 找出三个生产策略胜率和稳定性下降的主要来源。
2. 用 research/shadow 回测验证出场、状态门控、确认、成本、组合去相关等候选改动。
3. 建立可复现的 24M + walk-forward + OOS + 真实组合报告链路。
4. 给退役或研究策略提供证据驱动的回归路径。
5. 建立实战漂移监控闭环，但漂移结论仅 advisory，不自动改生产分层。

## 4. 非目标

1. 不承诺“提高胜率”一定发生，只交付可验证的改进候选和准入结论。
2. 不直接修改 `backend/app/services/low_buy/strategy_policy.py`。
3. 不改变 `production_score`、priority board 排序语义、生产策略公式、生产风控阈值、交易日发布门控。
4. 不让 research/ML/因子/重分析任务进入 Web 主进程。
5. 不引入自动下单、自动调参、自动升降级策略。
6. 不部署、不切流、不执行线上写操作；track record 线上启用必须单独授权。

## 5. 硬边界

1. `strategy_engine` 保持 shadow-only，`replacement_enabled=false`。
2. 所有候选变体先走 research/shadow；生产变更只能由最新 24M 报告、walk-forward、OOS、A4 守卫测试共同驱动。
3. `portfolio_backtest_metrics` 是真实组合回测唯一事实源；不得并行发明另一套组合收益口径。
4. 回测必须遵守时间顺序、T+1、真实费用、涨跌停/停牌拒单、缺数据显式降级。
5. `spike_return_*`、`avg_max_gain_5d`、`max_gain_5d` 只能用于诊断冲高机会，不得作为可成交收益或生产晋级指标。
6. 数据不足、分钟覆盖不足、OOS 样本不足时必须返回 `blocked_by_data`、`partial_data`、`insufficient_sample` 或等价状态。

## 6. 可行性核验

| 工作包 | 可行性 | 依据 | 必须补充的前置条件 |
| --- | --- | --- | --- |
| S1 出场优化 | 部分现成，整体可行 | 执行矩阵已有 `quick_tp3_trailing1`、T+1/T+2、移动防守参数 | “止盈一半”需新增分批出场研究模型和测试 |
| S2 `first_board` OOS 诊断 | 可行 | 24M 报告已有 OOS 弱化；outcomes 含日期、策略、状态、行业字段 | 需输出月份 x market_state x 板块归因报告 |
| S3 策略 x 市场状态门控 | 可行 | `market_gate.py` 与市场状态回测产物已存在 | 生产门控变更必须新增策略级守卫测试 |
| S4 `volume_shrink` 分时确认 | 可行但受数据约束 | `intraday_confirmation.py` 有 VWAP/尾盘确认机制 | 先验证分钟数据覆盖和样本留存，不得直接改生产集合 |
| S5 成本/滑点分桶 | 可行但需扩展 | `portfolio_backtest_metrics(extra_cost_bps)` 可做成本压测，日线有 `amount` | 需新增按成交额桶映射成本的研究参数 |
| S6 信号去相关 | 可行 | 组合事实源已有同票和板块约束 | 需新增同日同票/同板块重叠诊断与“保留分高者”变体 |
| S7 退役策略回归路径 | 可行 | N 字 observe_confirmed 已有测试先例，研究策略默认不进生产 | 只能按 A1 门禁重走 24M，不允许人工特批 |
| S8 漂移监控 | 可行 | ledger/drift 服务、迁移和测试已存在 | 线上捕获会写库，必须单独授权后启用 |

## 7. 功能需求

### R1 数据完整性与基线固化

1. 固化本轮输入报告和 Manifest 信息：数据窗口、交易日数、策略样本数、关键阻断项。
2. 若 `daily_bars`、市场状态、行业映射、分钟数据、track record 任一关键输入缺失，报告必须声明影响范围。
3. 输出 `docs/reports/strategy-success-rate-baseline-YYYY-MM-DD.md` 和机器可读 JSON。

验收：

1. 报告能复述三个生产策略的样本、PF、平均单笔、最大回撤、walk-forward、OOS。
2. 不出现裸“总收益”作为生产结论。
3. 缺数据不造样本、不裁剪亏损样本。

### R2 指标语义与准入规则

1. 胜率仅作为辅助指标，必须与 PF、净期望、最大回撤、样本外稳定性并列展示。
2. 每个候选变体必须输出基线对照：胜率、PF、平均单笔、最大回撤、真实组合 max5/max10、样本留存、交易频率。
3. 候选进入生产评审的最低条件：
   - 24M 净期望和 PF 不低于基线 95%；
   - 最大回撤不放大；
   - OOS PF >= 1 或有明确不采纳结论；
   - 样本留存达到该工作包要求；
   - 守卫测试全绿。

### R3 `first_board` OOS 失效诊断

1. 对最近 quarter_proxy 的 46 笔样本按月份、market_state、板块、行业、成本敏感性拆解。
2. 诊断结论必须落入三类之一：
   - 退潮/恐慌状态门控不足；
   - 首板生态变化；
   - 成本/滑点或样本期特例。
3. 未完成诊断前，不允许对 `first_board` 做生产参数调整。

交付：

1. `docs/reports/first-board-oos-diagnosis-YYYY-MM-DD.md`
2. `backend/data/reports/first-board-oos-diagnosis-YYYY-MM-DD.json`

### R4 出场变体矩阵

1. 先复用现有执行矩阵跑以下候选：
   - baseline/default_exit；
   - `quick_tp3_trailing1`；
   - T+1/T+2 强制收盘退出；
   - ATR 止损；
   - 固定止损。
2. 新增“回吐池”诊断：`max_gain_5d >= 3%` 且 `return_5d <= 0` 的占比、策略分布和日期分布。
3. 若要严格验证“+3% 止盈一半 + 剩余移动止损”，必须新增 research-only 分批出场模拟：
   - 支持 partial sell ratio；
   - 支持剩余仓位 trailing stop；
   - 输出分批成交的净收益；
   - 不影响现有生产 `exit_plan`。

验收：

1. 分批出场新增逻辑必须有单元测试覆盖收益计算、费用、T+1、止损优先级。
2. 任何生产候选必须和 baseline 同窗口、同候选池对照。

### R5 策略 x 市场状态门控矩阵

1. 输出 `strategy_key x market_state` 的样本数、成交数、胜率、PF、平均单笔、最大回撤。
2. 仅当某策略亏损集中在特定弱市/退潮状态时，才允许生成该策略专属暂停/降权研究变体。
3. 生产门控变更必须保持当前全局 `market_gate` 语义可回退，新增策略级规则需 feature flag 默认关闭。

验收：

1. `test_decision_context_market_gate.py` 保持全绿。
2. 若新增策略级门控，必须补充策略级 allow/reduce/block 守卫测试。
3. priority board 原排序语义不得漂移。

### R6 `volume_shrink` 盘中确认研究

1. 研究态验证 `volume_shrink + 尾盘/VWAP 确认`。
2. 分钟数据覆盖不足时，输出 `blocked_by_data` 或 `partial_minute_coverage`，不得把缺数据当作通过。
3. 样本留存必须 >= 原样本 60%，且 PF、胜率、OOS 至少不劣化，才允许进入生产评审。

验收：

1. 不直接把 `volume_shrink` 写入生产确认集合。
2. `test_low_buy_intraday_confirmation.py` 保持全绿。
3. 新增确认策略需覆盖“无分钟数据”“低于 VWAP”“尾盘确认通过/不通过”。

### R7 成本、滑点与流动性分桶

1. 基于成交额分桶复跑成本敏感性，例如：
   - `< 5000 万`；
   - `5000 万 - 2 亿`；
   - `> 2 亿`。
2. 每个桶输出基础成本、额外成本 bps、PF、平均单笔、真实组合 max5/max10。
3. 若某桶净期望为负，只能先生成研究态流动性门槛变体，不得直接改生产阈值。

验收：

1. `portfolio_backtest_metrics` 的现有 extra cost 行为不变。
2. 新增桶化成本必须有单测证明总成本和样本归桶正确。
3. 样本留存低于 70% 时默认不采纳。

### R8 信号去相关与组合执行层

1. 统计核心策略的同日同票、同日同板块、持仓重叠率。
2. 若重叠率 > 15% 且拖累组合收益，研究“同票同日仅保留 production/priority 分高者”变体。
3. 该变体只影响组合执行层，不改变单策略信号本身。

验收：

1. `portfolio_backtest_metrics` 的 same-symbol open position block 语义不变。
2. 新增 same-day dedupe 规则必须可开关、默认研究态。
3. 输出组合 max5/max10 与单策略指标的分离对照。

### R9 退役策略回归路径

1. `late_session_strong_support` 继续低样本限权，达到成交 >= 100 且 walk-forward >= 4/7 前不得升权。
2. N 字家族只能以 `observe_confirmed` 研究变体重跑 24M。
3. 所有 research 策略必须满足统一 A1 门禁，不能人工例外。

验收：

1. `test_n_pattern_observe_confirmed.py` 保持全绿。
2. `strategy_policy.py` 不发生变化。
3. 晋级建议只输出 review，不写生产 override。

### R10 真实战绩漂移监控

1. 账本只捕获 `buy_now` / `soft_buy_now` 且参与 priority board 的生产策略。
2. `signal_time`、`data_cutoff_time`、`return_start_time` 必填，禁止未来函数。
3. 漂移结果只做 advisory，不自动改策略分层、生产分或排序。
4. `DRIFT_ALERT_ENABLED` 默认 false；首月只观察，不发生产告警。

验收：

1. `test_track_record_ledger.py`、`test_track_record_realized.py`、`test_track_record_drift.py` 全绿。
2. 线上启用捕获任务前必须获得单独授权，因为会写数据库。

### R11 报告与产品展示

1. 每个工作包必须输出 Markdown 报告和 JSON 产物，Markdown 放 `docs/reports/`，大型 JSON 放 `backend/data/reports/`。
2. 前端只读取已有 API 或报告摘要，不在 Web 主进程触发 24M 重任务。
3. `/strategy-tracking`、`/backtest`、`/playbook` 如展示新结论，必须显示研究态、样本数、数据质量和是否生产可用。

验收：

1. 前端不得展示“已提升胜率”这类未经 OOS 验证的确定性文案。
2. 研究态候选不得出现可直接生产启用的按钮。

## 8. 分阶段实施建议

### G0 基线确认

交付：

1. git 状态和分支记录。
2. 当前 24M 报告、策略层级、守卫测试清单。
3. 本需求文档与原计划的差异说明。

验收命令：

```bash
git status --short
git branch --show-current
```

### G1 OOS 与回吐诊断

交付：

1. `first_board` OOS 诊断报告。
2. 三个生产策略的回吐池统计。

验收：

1. 诊断必须有明确结论。
2. 不能在无结论情况下调参。

### G2 出场矩阵与分批出场前置

交付：

1. 现有执行矩阵完整复跑。
2. 如需要，新增分批出场 research-only 模型。

建议命令：

```bash
PYTHONPATH=backend backend/.venv/bin/python backend/scripts/low_buy_execution_matrix.py \
  --months 24 \
  --strategies first_board,volume_shrink,late_session_strong_support \
  --states confirmed \
  --engine fast \
  --materialization-mode isolated
```

### G3 状态门控、确认、成本分桶、去相关

交付：

1. 策略 x 市场状态矩阵。
2. `volume_shrink` 分时确认研究报告。
3. 成本/滑点/流动性分桶报告。
4. 同日同票/板块重叠与组合执行变体报告。

验收：

1. 每个变体都有“采纳/不采纳/继续观察”结论。
2. 研究失败也必须落档，不能只保留好结果。

### G4 退役策略与漂移闭环

交付：

1. N 字 observe_confirmed 24M 研究报告。
2. track record 漂移报告模板和离线测试结果。

验收：

1. 不升权、不写生产分层。
2. 线上账本捕获等待授权。

### G5 生产评审包

触发条件：

1. 至少一个变体在 24M、walk-forward、OOS、真实组合、成本敏感性上全部过门。
2. 守卫测试全绿。
3. 有回滚方案和 feature flag。

交付：

1. 生产候选评审报告。
2. 对 `production_score`、priority board 排序、风控阈值的影响声明。
3. 明确是否需要改生产代码；若需要，必须单独获得授权。

## 9. 最低测试要求

局部研究/报告变更：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest -q \
  backend/tests/test_low_buy_backtest_isolation.py \
  backend/tests/test_low_buy_trade_controls.py \
  backend/tests/test_strategy_24m_optimization_report.py
```

门控/确认/漂移相关变更：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest -q \
  backend/tests/test_decision_context_market_gate.py \
  backend/tests/test_low_buy_intraday_confirmation.py \
  backend/tests/test_track_record_ledger.py \
  backend/tests/test_track_record_realized.py \
  backend/tests/test_track_record_drift.py
```

任何可能影响生产排序、生产分、策略层级、priority board 的变更：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest -q \
  backend/tests/test_low_buy_production_scoring.py \
  backend/tests/test_low_buy_priority_board_strategy_variants.py \
  backend/tests/test_strategy_engine_production_gate_guards.py \
  backend/tests/test_strategy_engine_boundary.py
```

生产评审前：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests
```

## 10. 风险与应对

| 风险 | 表现 | 应对 |
| --- | --- | --- |
| 过拟合 | 样本内改善、OOS 失败 | 必须 walk-forward + OOS + 参数稳定性 |
| 胜率幻觉 | 止盈过早导致 PF/期望下降 | 胜率不得单独作为采纳条件 |
| 数据缺失 | 分钟、行业、市场状态覆盖不足 | 显式 `blocked_by_data`，不造样本 |
| 成本低估 | `volume_shrink` 单笔利润被滑点吞噬 | 成本分桶和 extra bps 压测 |
| 生产漂移 | 研究结论误入生产排序 | feature flag 默认关，守卫测试覆盖 |
| Web 进程变重 | 24M 任务在页面请求中执行 | 走 worker/script/report 产物，不进 Web 主进程 |

## 11. Definition of Done

1. S1-S8 每项均有“可行/受限/不采纳”的落档结论。
2. 所有研究变体均有同窗口 baseline 对照。
3. 至少生成以下报告：
   - `first-board-oos-diagnosis-YYYY-MM-DD.md`
   - `strategy-exit-variants-YYYY-MM-DD.md`
   - `strategy-market-state-matrix-YYYY-MM-DD.md`
   - `strategy-cost-liquidity-sensitivity-YYYY-MM-DD.md`
   - `strategy-correlation-dedup-YYYY-MM-DD.md`
   - `strategy-drift-observation-YYYY-MM-DD.md`
4. 所有报告明确数据窗口、样本数、成本假设、是否生产可用。
5. `strategy_policy.py`、生产排序、`production_score`、风控阈值未被直接修改。
6. 未部署、未切流、未执行线上写操作，除非后续获得单独授权。
