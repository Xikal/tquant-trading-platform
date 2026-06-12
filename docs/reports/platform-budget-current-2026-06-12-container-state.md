# 平台连接池与 Worker 降载复验报告

- 生成时间：`2026-06-12T13:51:12.296090+00:00`
- 状态：`ok`
- 阻断项：无
- 警告项：无

## MySQL 与连接池

| 指标 | 当前值 |
| --- | ---: |
| max_connections | 120 |
| Threads_connected | 10 |
| Threads_running | 2 |
| 运行中应用连接池预算总和 | 16 |

## 角色预算

| 角色 | 容器 | 状态 | 运行中 | runtime pool budget | configured pool budget | low priority paused | background jobs | analytics |
| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| web | tquant-app-mysql | running | True | 4 | 4 | n/a | false | false |
| runtime_worker | tquant-runtime-worker-mysql | running | True | 6 | 6 | true | false | n/a |
| runtime_scheduler | tquant-runtime-scheduler-mysql | running | True | 6 | 6 | true | true | n/a |
| analytics_worker | tquant-analytics-worker-mysql | exited | False | 0 | 4 | false | n/a | true |

## 结论

连接池预算和 Worker 降载复验通过。
