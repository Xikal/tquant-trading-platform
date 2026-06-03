# 后端性能预算分级准入（2026-06-03）

## 分级
- Level 1 CI 强阻塞：Rust fallback ratio 等稳定机器指标。
- Level 2 本地服务预算：runtime task p95、hot response serialization ms。
- Level 3 云端巡检：quote coverage、monitor_bff、market_pulse、priority_board 等线上巡检项。

## 脚本
`scripts/check_backend_perf_budget.py`

新增参数：
- `--level all|level1|level2|level3`
- `--strict`

默认 `--level all --strict` 时只让 Level 1 exceeded 阻塞；Level 2/3 会报告 exceeded，但不作为普通 PR 的硬失败。

## 本地预算烟测
命令：
`python3 scripts/check_backend_perf_budget.py --metrics-file /tmp/tquant-backend-compute-metrics.prom || true`

结果：
- Level 1 `tquant_rust_math_fallback_ratio_bps=0`：ok
- Level 2 `tquant_runtime_task_duration_p95_ms=0`：ok
- Level 2 `tquant_response_serialization_ms`：not_measured（当前进程未产生热接口流量，`route="none"` 占位会被忽略）
- Level 3 `tquant_local_quote_cache_coverage_ratio_bps=0`：exceeded（当前 `/metrics` 采集时未跑 coverage）
- 脚本总 `ok=true`，因为 Level 3 不阻塞普通 PR。

多 label 处理：
- 同一 metric 有多个 label 样本时，max budget 使用真实样本最大值，min budget 使用真实样本最小值。
- `label="none"` 的 Prometheus 占位样本只表示 no_data，不参与预算判断。

## 阈值
| Level | Metric | Budget |
| --- | --- | ---: |
| 1 | `tquant_rust_math_fallback_ratio_bps` | <= 5000 |
| 2 | `tquant_runtime_task_duration_p95_ms` | <= 600000 |
| 2 | `tquant_response_serialization_ms` | <= 250 |
| 3 | `tquant_local_quote_cache_coverage_ratio_bps` | >= 9000 |

## 风险
- Level 2/3 仍需要真实服务流量或云端巡检数据，否则只能显示 `not_measured` 或空进程指标。
- 云端网络抖动不得直接作为普通 PR 阻塞，需要巡检报告确认。
