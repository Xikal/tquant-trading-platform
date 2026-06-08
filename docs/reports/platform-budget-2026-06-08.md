# 平台连接池与 Worker 降载复验报告

- 生成时间：`2026-06-07T22:03:09.246744+00:00`
- 状态：`warning`
- 阻断项：无
- 警告项：mysql_max_connections=300, low_priority_pause_env_missing=runtime_worker, low_priority_pause_env_missing=runtime_scheduler, low_priority_pause_env_missing=backtest_worker, low_priority_pause_env_missing=analytics_worker

## MySQL 与连接池

| 指标 | 当前值 |
| --- | ---: |
| max_connections | 300 |
| Threads_connected | 26 |
| Threads_running | 2 |
| 应用连接池预算总和 | 28 |

## 角色预算

| 角色 | 容器 | pool budget | low priority paused | background jobs | analytics |
| --- | --- | ---: | --- | --- | --- |
| web | tquant-app-mysql | 8 | n/a | false | false |
| runtime_worker | tquant-runtime-worker-mysql | 4 | n/a | false | n/a |
| runtime_scheduler | tquant-runtime-scheduler-mysql | 4 | n/a | true | n/a |
| backtest_worker | tquant-backtest-worker-mysql | 4 | n/a | n/a | n/a |
| analytics_worker | tquant-analytics-worker-mysql | 8 | n/a | n/a | true |

## 结论

无 blocking 项，但仍有 warning，需要继续资源治理或在线复验。
