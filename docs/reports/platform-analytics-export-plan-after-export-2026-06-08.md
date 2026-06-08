# Analytics Manifest 导出计划

- 生成时间：`2026-06-08T05:47:02.269462+00:00`
- Analytics root：`/var/lib/docker/volumes/tquant-mysql_app_runtime_data/_data/analytics`
- Task output root：`/app/backend/data/analytics`
- 截止日期：`2026-06-08`
- 状态：`warning`
- 安全边界：dry-run 报告；不 enqueue、不执行 exporter、不修改 MySQL、不清源表。

## 汇总

| 指标 | 当前值 |
| --- | ---: |
| 数据集数量 | 10 |
| ready | 10 |
| optional refresh | 1 |
| export required | 0 |
| reexport required | 0 |
| manual investigation | 0 |
| required tasks | 0 |

## 数据集计划

| Dataset | Action | Task | Window | Source | Blockers |
| --- | --- | --- | --- | --- | --- |
| daily_bars | lifecycle_refresh_optional | analytics_export_daily_bars | months=24, end_date=2026-06-08 | daily_bar_snapshots | - |
| strategy_tracking_snapshots | ready | analytics_export_strategy_tracking_snapshots | days=90, end_date=2026-06-08 | strategy_tracking_snapshots | - |
| key_level_snapshots | ready | analytics_export_key_level_snapshots | days=90, end_date=2026-06-08 | key_level_snapshots | - |
| low_buy_result_snapshots | ready | analytics_export_low_buy_result_snapshots | days=90, end_date=2026-06-08 | low_buy_result_snapshots | - |
| backtest_runs | ready | analytics_export_backtest_runs | days=180, end_date=2026-06-08 | backtest_runs | - |
| backtest_trades | ready | analytics_export_backtest_trades | days=180, end_date=2026-06-08 | backtest_trades | - |
| backtest_daily_snapshots | ready | analytics_export_backtest_daily_snapshots | days=180, end_date=2026-06-08 | backtest_daily_snapshots | - |
| analysis_logs | ready | analytics_export_analysis_logs | days=90, end_date=2026-06-08 | analysis_logs | - |
| market_review_reports | ready | analytics_export_market_review_reports | days=90, end_date=2026-06-08 | market_review_reports | - |
| paper_review_reports | ready | analytics_export_paper_review_reports | days=90, end_date=2026-06-08 | paper_review_reports | - |

## 执行说明

本报告只把 manifest 复验结果转成低优先级 analytics worker 任务计划；需要运维窗口或任务系统另行提交。任务完成后必须复跑 manifest 复验，所有相关数据集无 blocking 前，不能执行 MySQL 热库保留窗口清理。

复验命令：

```bash
python3 scripts/verify_analytics_manifests.py --analytics-root /var/lib/docker/volumes/tquant-mysql_app_runtime_data/_data/analytics --json-output docs/reports/platform-analytics-manifests-2026-06-08.json --markdown-output docs/reports/platform-analytics-manifests-2026-06-08.md
```
