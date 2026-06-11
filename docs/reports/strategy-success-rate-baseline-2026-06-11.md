# 策略成功率优化基线报告（2026-06-11）

- 批次：`D0`
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
| 策略 | 层级 | 样本 | 成交 | 胜率 | PF | 平均单笔 | 回撤 | WF | OOS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_board | core | 1108 | 1064 | 53.48% | 2.6258 | 1.1219% | -5.4221% | 7/7 pass | quarter_proxy filled=46 PF=0.7516 return=-1.0111% |
| volume_shrink | core | 552 | 510 | 56.67% | 1.6597 | 0.619% | -13.2359% | 6/7 pass | quarter_proxy filled=15 PF=0.9014 return=0.1452% |
| late_session_strong_support | auxiliary | 60 | 58 | 55.17% | 2.2359 | 1.3472% | -7.7415% | 0/7 pass | quarter_proxy filled=5 PF=2.5574 return=1.9044% |

批次结论：`ready`；生产变更允许：`False`。

## 机器产物
- JSON：`backend/data/reports/strategy-success-rate/strategy-success-rate-baseline-2026-06-11.json`
- Markdown：`docs/reports/strategy-success-rate-baseline-2026-06-11.md`
