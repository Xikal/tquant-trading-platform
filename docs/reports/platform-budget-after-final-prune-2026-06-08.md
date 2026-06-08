# 平台连接池与 Worker 降载复验报告

- 生成时间：`2026-06-08T06:43:45.749270+00:00`
- 状态：`ok`
- 阻断项：无
- 警告项：无

## MySQL 与连接池

| 指标 | 当前值 |
| --- | ---: |
| max_connections | 120 |
| Threads_connected | 14 |
| Threads_running | 2 |
| 应用连接池预算总和 | 15 |

## 角色预算

| 角色 | 容器 | pool budget | low priority paused | background jobs | analytics |
| --- | --- | ---: | --- | --- | --- |
| web | tquant-app-mysql | 4 | n/a | false | false |
| runtime_worker | tquant-runtime-worker-mysql | 3 | false | false | n/a |
| runtime_scheduler | tquant-runtime-scheduler-mysql | 2 | false | true | n/a |
| backtest_worker | tquant-backtest-worker-mysql | 3 | false | n/a | true |
| analytics_worker | tquant-analytics-worker-mysql | 3 | false | n/a | true |

## 结论

连接池预算和 Worker 降载复验通过。
