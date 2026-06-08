# Analytics Manifest 只读复验报告

- 生成时间：`2026-06-07T22:03:05.585849+00:00`
- Analytics root：`/var/lib/docker/volumes/tquant-mysql_app_runtime_data/_data/analytics`
- 状态：`blocking`
- 阻断项：manifest_blocked_count=9
- 警告项：manifest_missing_count=9, manifest_warning_dataset_count=1

## 汇总

| 指标 | 当前值 |
| --- | ---: |
| 数据集数量 | 10 |
| ready datasets | 1 |
| missing manifests | 9 |
| blocked datasets | 9 |
| warning datasets | 1 |
| total rows | 2443775 |
| verified files | 25 |

## 数据集

| Dataset | Manifest | Rows | Quality | Files | Warnings | Blockers |
| --- | --- | ---: | --- | ---: | --- | --- |
| daily_bars | present | 2443775 | ok | 25 | manifest_id_missing | - |
| strategy_tracking_snapshots | missing | 0 |  | 0 | - | manifest_missing |
| key_level_snapshots | missing | 0 |  | 0 | - | manifest_missing |
| low_buy_result_snapshots | missing | 0 |  | 0 | - | manifest_missing |
| backtest_runs | missing | 0 |  | 0 | - | manifest_missing |
| backtest_trades | missing | 0 |  | 0 | - | manifest_missing |
| backtest_daily_snapshots | missing | 0 |  | 0 | - | manifest_missing |
| analysis_logs | missing | 0 |  | 0 | - | manifest_missing |
| market_review_reports | missing | 0 |  | 0 | - | manifest_missing |
| paper_review_reports | missing | 0 |  | 0 | - | manifest_missing |

## 结论

当前 manifest 复验存在 blocking 项，不能作为 MySQL 热库清理依据。
