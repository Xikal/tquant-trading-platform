# 尾盘推荐榜本地运行手册

## 目标

本手册用于本地验证 `late_session_recommendation_refresh` 任务与三类尾盘 slot。它只描述队列任务、payload、验收查询和风险边界，不包含服务重启、切流、线上配置修改或磁盘清理步骤。

## Slot

| slot | 目标时间 | 语义 |
| --- | --- | --- |
| `preview_1450` | 14:50 | 尾盘预警 |
| `snapshot_1455` | 14:55 | 尾盘快照 |
| `final_1457` | 14:57 | 尾盘终版 |

## Runtime Task

任务类型：

```text
late_session_recommendation_refresh
```

示例 payload：

```json
{"slot":"preview_1450","reason":"late_session_preview_1450","source_limit":30,"limit":12,"strategy_variant":"baseline"}
{"slot":"snapshot_1455","reason":"late_session_snapshot_1455","source_limit":30,"limit":12,"strategy_variant":"baseline"}
{"slot":"final_1457","reason":"late_session_final_1457","source_limit":30,"limit":12,"strategy_variant":"baseline"}
```

幂等键格式：

```text
late_session_recommendation_refresh:{trade_date}:preview_1450
late_session_recommendation_refresh:{trade_date}:snapshot_1455
late_session_recommendation_refresh:{trade_date}:final_1457
```

## 本地验收

后端任务分发测试：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_late_session_runtime_task.py
```

API 队列语义测试：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest -q backend/tests/test_late_session_board_api.py
```

研究脚本帮助：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python backend/scripts/late_session_board_backtest.py --help
```

## 线上启用前检查

- `runtime_tasks` 已支持 `late_session_recommendation_refresh`。
- `runtime-worker` 能执行该任务。
- `/api/screeners/low-buy/late-session-board?refresh=async` 只入队该任务。
- 三个 slot 使用不同幂等键，不互相覆盖。
- 任务只读取已物化 priority board 候选、quote cache、分钟线和市场状态。
- 任务不做全市场扫描、不重算生产分、不修改原 priority board 快照。

## 需要授权的后续事项

- 将 14:50、14:55、14:57 自动入队接入线上调度。
- 将尾盘快照持久化到共享缓存或数据库表。
- 接入通知通道或告警面板。

## 禁止事项

- 不在 Web 请求中同步触发全市场低吸扫描、24M 回测、DuckDB 报告或重分析任务。
- 不修改生产策略准入、`production_score`、priority board 默认排序和默认字段语义。
- 不把研究/factor 策略升级为正式尾盘确认。
- 不输出自动下单或确定买入口径。
