# 策略 x market_state 矩阵（2026-06-11）

- 批次：`D3`
- 状态：`ready`
- 生成时间：`2026-06-11T08:50:54+08:00`
- 分支：`codex/phase4-phase5-architecture`

## 硬边界
- 不修改 backend/app/services/low_buy/strategy_policy.py。
- 不改变 production_score、priority board 排序语义、生产策略公式、风控阈值、交易日发布门控。
- strategy_engine 保持 shadow-only，replacement_enabled=false。
- research/ML/因子/重分析任务不回到 Web 主进程。
- portfolio_backtest_metrics 继续作为真实组合回测唯一事实源。
- spike_return_*、avg_max_gain_5d、max_gain_5d 只作诊断，不作生产晋级收益指标。
- 本轮不部署、不切流、不执行线上写操作。

## 数据源
- `strategy_24m`：`backend/data/analytics/reports/strategy_24m_duckdb_report.json`
- `execution_matrix`：`backend/data/reports/execution_matrix/low_buy_execution_matrix_24m_confirmed_all_2025-10-09_2026-04-28.json`
- `target_execution_matrix`：`backend/data/reports/execution_matrix/low_buy_execution_matrix_24m_confirmed_first_board_volume_shrink_late_session_strong_support_auto_auto.json`
- `tradability`：`docs/reports/front-row-weighted-minute-tick-tradability-2026-05-30.json`
- `n_pattern_observe`：`backend/data/reports/n_pattern_observe_confirmed/low_buy_market_backtest_24m_empty.json`
- `latest_backtest`：`backend/data/reports/low_buy_market_backtest_24m_confirmed_2025-10-09_2026-04-20.json`

## Git 保护状态
- `M .gitignore`
- ` M IMPLEMENTATION_PLAN.md`
- `?? backend/data/`
- `?? backend/scripts/strategy_success_rate_diagnostics.py`
- `?? backend/tests/test_strategy_success_rate_diagnostics.py`
- `?? docs/reports/first-board-oos-diagnosis-2026-06-11.md`
- `?? docs/reports/strategy-correlation-dedup-2026-06-11.md`
- `?? docs/reports/strategy-cost-liquidity-sensitivity-2026-06-11.md`
- `?? docs/reports/strategy-drift-observation-2026-06-11.md`
- `?? docs/reports/strategy-exit-variants-2026-06-11.md`
- `?? docs/reports/strategy-market-state-matrix-2026-06-11.md`
- `?? docs/reports/strategy-retired-reentry-research-2026-06-11.md`
- `?? docs/reports/strategy-success-rate-baseline-2026-06-11.md`
- `?? docs/reports/strategy-success-rate-implementation-report-2026-06-11.md`
- `?? docs/reports/strategy-success-rate-production-review-2026-06-11.md`
- `?? docs/reports/strategy-volume-shrink-intraday-confirmation-2026-06-11.md`
- `?? docs/strategy-success-rate-optimization-development-plan-2026-06-11.md`
- `?? docs/strategy-success-rate-optimization-requirements-2026-06-11.md`

## 核心内容
| 策略 | market_state | 样本 | 成交 | 胜率 | PF | 平均单笔 | 最大回撤 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| first_board | broad_rally | 609 | 588 | 50.51% | 2.2624 | 0.9166% | -5.4221% |
| first_board | low_volume_wait | 32 | 31 | 64.52% | 3.7387 | 1.8626% | 0.0% |
| first_board | repair | 467 | 445 | 56.63% | 3.086 | 1.3414% | -3.7504% |
| volume_shrink | broad_rally | 329 | 305 | 58.03% | 1.7348 | 0.624% | -12.2554% |
| volume_shrink | repair | 199 | 181 | 55.25% | 1.5936 | 0.5989% | -7.1119% |
| volume_shrink | weight_support_active | 24 | 24 | 50.0% | 1.4601 | 0.7067% | -5.4603% |
| late_session_strong_support | broad_rally | 38 | 37 | 48.65% | 1.6297 | 0.8851% | -15.6403% |
| late_session_strong_support | repair | 22 | 21 | 66.67% | 5.0476 | 2.1612% | -2.812% |
- 策略级门控：`no_strategy_gate_change`，仅 research/flag-off。

批次结论：`ready`；生产变更允许：`False`。

## 机器产物
- JSON：`backend/data/reports/strategy-success-rate/strategy-market-state-matrix-2026-06-11.json`
- Markdown：`docs/reports/strategy-market-state-matrix-2026-06-11.md`
