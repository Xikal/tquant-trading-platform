# Analytics Manifest 导出任务提交预览

- 生成时间：`2026-06-08T05:16:27.168811+00:00`
- 模式：`dry-run`
- 安全边界：默认 dry-run；不执行 exporter；不清 MySQL 源表；apply 模式只写 runtime task 队列。

## 汇总

| 指标 | 当前值 |
| --- | ---: |
| selected tasks | 9 |
| submitted tasks | 0 |

## 任务

| Dataset | Action | Task | Priority | Idempotency |
| --- | --- | --- | ---: | --- |
| strategy_tracking_snapshots | export_required | analytics_export_strategy_tracking_snapshots | 900 | analytics-export:strategy_tracking_snapshots:2026-06-08:container-root-v2 |
| key_level_snapshots | export_required | analytics_export_key_level_snapshots | 900 | analytics-export:key_level_snapshots:2026-06-08:container-root-v2 |
| low_buy_result_snapshots | export_required | analytics_export_low_buy_result_snapshots | 900 | analytics-export:low_buy_result_snapshots:2026-06-08:container-root-v2 |
| backtest_runs | export_required | analytics_export_backtest_runs | 900 | analytics-export:backtest_runs:2026-06-08:container-root-v2 |
| backtest_trades | export_required | analytics_export_backtest_trades | 900 | analytics-export:backtest_trades:2026-06-08:container-root-v2 |
| backtest_daily_snapshots | export_required | analytics_export_backtest_daily_snapshots | 900 | analytics-export:backtest_daily_snapshots:2026-06-08:container-root-v2 |
| analysis_logs | export_required | analytics_export_analysis_logs | 900 | analytics-export:analysis_logs:2026-06-08:container-root-v2 |
| market_review_reports | export_required | analytics_export_market_review_reports | 900 | analytics-export:market_review_reports:2026-06-08:container-root-v2 |
| paper_review_reports | export_required | analytics_export_paper_review_reports | 900 | analytics-export:paper_review_reports:2026-06-08:container-root-v2 |
