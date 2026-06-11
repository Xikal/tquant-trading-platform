# 信号去相关与组合执行层报告（2026-06-11）

- 批次：`D6`
- 状态：`blocked_by_data`
- 生成时间：`2026-06-11T08:50:55+08:00`
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
- 同日同票/同板块重叠统计：`blocked_by_data`。
- 单策略信号未变，组合层去重变体未启用。

批次结论：`blocked_by_data`；生产变更允许：`False`。

## 机器产物
- JSON：`backend/data/reports/strategy-success-rate/strategy-correlation-dedup-2026-06-11.json`
- Markdown：`docs/reports/strategy-correlation-dedup-2026-06-11.md`
