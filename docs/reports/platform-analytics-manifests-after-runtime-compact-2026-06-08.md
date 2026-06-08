# Analytics Manifest 只读复验报告

- 生成时间：`2026-06-08T06:08:37.838772+00:00`
- Analytics root：`/var/lib/docker/volumes/tquant-mysql_app_runtime_data/_data/analytics`
- 状态：`warning`
- 阻断项：无
- 警告项：manifest_warning_dataset_count=1

## 汇总

| 指标 | 当前值 |
| --- | ---: |
| 数据集数量 | 10 |
| ready datasets | 10 |
| missing manifests | 0 |
| blocked datasets | 0 |
| warning datasets | 1 |
| total rows | 2468404 |
| verified files | 267 |

## 数据集

| Dataset | Manifest | Rows | Quality | Files | Warnings | Blockers |
| --- | --- | ---: | --- | ---: | --- | --- |
| daily_bars | present | 2443775 | ok | 25 | manifest_id_missing | - |
| strategy_tracking_snapshots | present | 2 | ok | 2 | - | - |
| key_level_snapshots | present | 16372 | ok | 5 | - | - |
| low_buy_result_snapshots | present | 5259 | ok | 42 | - | - |
| backtest_runs | present | 48 | ok | 22 | - | - |
| backtest_trades | present | 775 | ok | 29 | - | - |
| backtest_daily_snapshots | present | 2068 | ok | 107 | - | - |
| analysis_logs | present | 82 | ok | 24 | - | - |
| market_review_reports | present | 17 | ok | 9 | - | - |
| paper_review_reports | present | 6 | ok | 2 | - | - |

## 结论

当前 manifest 复验无 blocking，但有缺失项，需要继续生成/校验真实 manifest。
