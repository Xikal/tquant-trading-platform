# 后端性能下一阶段 N0 基线（2026-06-03）

## 范围
- 执行文档：`docs/superpowers/plans/2026-06-03-backend-performance-next-stage-development.md`
- 本报告只记录真实基线与 blocked/no_data 项，不把本地空指标当线上结论。
- 硬边界：未修改策略规则、评分公式、生产门禁、`strategy_policy.participates_in_priority_board`。

## 本地 `/metrics` 基线
采集命令：
`PYTHONPATH=backend:. backend/.venv/bin/python - <<'PY' ... app.main.prometheus_metrics(None) ...`

输出文件：
`/tmp/tquant-backend-compute-metrics.prom`

| 指标 | 当前值 | 说明 |
| --- | ---: | --- |
| `tquant_rust_math_fallback_ratio_bps` | 0 | 当前进程没有产生 Rust fallback。 |
| `tquant_runtime_task_duration_p95_ms` | 0 | 当前本地进程无 runtime task 样本。 |
| `tquant_local_quote_cache_coverage_ratio_bps` | 0 | `/metrics` 采集时未跑热需求 coverage。 |
| `tquant_read_model_cache_*` | 0/none | 当前进程无热接口请求流量。 |
| `tquant_live_overlay_*` | 0/none | 当前进程无 live overlay 请求流量。 |
| `tquant_response_*` | 0/none | 当前进程无热接口 payload 观测。 |
| `tquant_indicator_cache_*` | 0/none | 当前进程无派生指标缓存流量。 |

## Quote Cache Warmup 小样本
采集对象：`000001, 000002, 000003`

| 阶段 | covered/demand | coverage_ratio_bps | 状态 |
| --- | ---: | ---: | --- |
| warmup 前 | 0/3 | 0 | below_target |
| 写入 2 个快照后 | 2/3 | 6667 | below_target，缺 `000003` |

结论：本地 quote cache coverage 观测链路可用，但样本是人工小样本，不代表线上覆盖率。

## 热接口 p50/p95/p99
本地未启动长期服务并产生真实监控轮询流量，因此 `monitor_bff`、`market_pulse`、`priority_board`、`strategy_tracking list` 的 p50/p95/p99 标记为 `blocked`。

原因：当前验收在测试进程中执行；没有稳定本地 HTTP 压测窗口，也没有云端 SSH/鉴权凭据。

## 云端基线
状态：`blocked`

原因：
- `scripts/measure_cloud_go_rust_performance.py` 需要远端 SSH / 登录注册 / token 链路。
- 本轮没有可用远端凭据，不能把本地或空指标伪装成云端 p95。

## 结论
- N0 基线采集链路已建立。
- 可测项：本地 `/metrics`、quote cache coverage 小样本。
- 不可测项：云端 p95、真实热接口 p50/p95/p99、真实全市场扫描和 24M 线上报告墙钟。
- 所有 blocked/no_data 项已显式标注。

