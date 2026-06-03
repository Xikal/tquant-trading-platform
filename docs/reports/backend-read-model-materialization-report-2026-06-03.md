# 后端性能 N1/N2 读模型物化与 Payload 观测报告（2026-06-03）

## 完成项
- 为已有热路径缓存补指标，不新建改变语义的生产缓存层：
  - BFF workspace cache：`bff-workspace-v1`，`bff_monitor` 等 read model hit/miss/write/stale。
  - Priority board response cache：`priority-response-v1`，`priority_board` hit/miss/write/stale。
  - Strategy tracking 内存读模型：`strategy-tracking-read-model-v1`，`strategy_tracking` hit/miss/write/stale/age。
  - Monitor snapshot cache：`monitor_workspace` hit/miss。
- 新增 live quote overlay：
  - 只读取本地 quote cache。
  - 只更新展示行情字段：最新价、涨跌幅、时间戳、data_quality。
  - 不重排、不改 `priority_score`、`production_score`、`buy_signal_state`。
- 新增 payload 观测：
  - `item_count`
  - serialized `response_bytes`
  - serialization ms
- `/metrics` 新增：
  - `tquant_read_model_cache_*`
  - `tquant_live_overlay_*`
  - `tquant_response_*`
  - `tquant_indicator_cache_*`

## 接入接口
- `/api/bff/v1/workspace/monitor`
- `/api/screeners/low-buy/priority-board`
- `/api/v1/strategy/priority-board`
- `/api/strategy-tracking/items`

## 回退方式
- `READ_MODEL_LIVE_OVERLAY_ENABLED=false`：关闭 live overlay，接口回到原始缓存/构建结果。
- `RESPONSE_PAYLOAD_METRICS_ENABLED=false`：关闭额外 payload 序列化观测。
- 读模型指标只记录计数，不参与业务返回。

## 本地观测
当前 `/metrics` 采集进程没有真实热接口流量，因此新增运行态指标为 0/none：
- `tquant_read_model_cache_hits_total{model="none"} 0`
- `tquant_live_overlay_hits_total{source="none"} 0`
- `tquant_response_serialization_ms{route="none"} 0`

这表示当前进程未触发接口请求，不表示线上无命中。

## 测试
- `backend/tests/test_read_model_materialization.py`
- `backend/tests/test_read_model_live_overlay.py`
- `backend/tests/test_performance_regression.py`

局部结果：
`13 passed, 1 warning`

## 生产排序影响
无。live overlay 不改排序字段，不改变候选集合，不替换 low-buy、priority board、front-row weighted 或任何生产排序。
