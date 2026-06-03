# 后端计算加速 M0 基线

日期：2026-06-03
执行范围：`docs/reports/backend-compute-acceleration-landable-scope-2026-06-03.md` 中“可以确定落地”的 M0 基线项。
边界：本报告只记录基线，不实施全市场扫描并行化、24M 回测并行化、全量 async 改造或 Go/Rust 业务重写。

## /metrics 本地基线

采集命令：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python - <<'PY'
from app.main import prometheus_metrics
print(prometheus_metrics(None).body.decode("utf-8"))
PY
```

采集说明：

- 本地未启动完整生产服务；通过 `app.main.prometheus_metrics(None)` 直接读取 Prometheus 文本。
- 本地 SQLite/审计表状态不完整，`agent audit metrics unavailable` 与 `phase4 metrics unavailable` 以 0 兜底；这些项不能代表云端生产值。
- `urllib3` LibreSSL warning 为本地 Python/SSL 环境 warning，不影响本次指标读取。

| 指标 | 当前值 | 状态 |
|---|---:|---|
| `tquant_rust_math_hits_total` | 0 | measured |
| `tquant_rust_math_fallbacks_total` | 0 | measured |
| `tquant_rust_math_errors_total` | 0 | measured |
| `tquant_rust_math_disabled_total` | 0 | measured |
| `tquant_rust_math_fallback_ratio_bps` | 0 | measured |
| `tquant_derived_indicator_cache_hits_total` | 0 | measured |
| `tquant_derived_indicator_cache_misses_total` | 0 | measured |
| `tquant_derived_indicator_cache_size` | 0 | measured |
| `tquant_local_quote_cache_reads_total` | 0 | measured |
| `tquant_local_quote_cache_hits_total` | 0 | measured |
| `tquant_local_quote_cache_misses_total` | 0 | measured |
| `tquant_local_quote_cache_coverage_ratio_bps` | 0 | no_data，本地未执行缓存预热 |
| `tquant_bff_workspace_cache_reads_total` | 0 | measured |
| `tquant_bff_workspace_cache_hits_total` | 0 | measured |
| `tquant_bff_remote_calls_total` | 0 | measured |
| `tquant_bff_remote_failures_total` | 0 | measured |
| `tquant_provider_calls_total` | 0 | measured |
| `tquant_provider_failures_total` | 0 | measured |
| `tquant_provider_slow_calls_total` | 0 | measured |
| `tquant_runtime_task_duration_samples` | 0 | blocked，本地 RuntimeTask 表不可完整读取 |
| `tquant_runtime_task_duration_p95_ms` | 0 | blocked，本地 RuntimeTask 表不可完整读取 |

## 热路径基线

| 项 | 计划要求 | 当前基线 | 状态 |
|---|---|---|---|
| `monitor_bff` | 记录 p95 | 未跑云端 `scripts/measure_cloud_go_rust_performance.py` | blocked：该脚本会远程 SSH 并注册临时用户，本轮非部署验收不强跑 |
| `market_pulse` | 记录 p95 | 未跑云端脚本 | blocked：同上 |
| `priority_board` | 记录 p95 | 未跑云端脚本 | blocked：同上 |
| 全市场扫描 | 记录墙钟 | 未执行生产物化/全市场扫描 | research_only：本轮禁止直接实施或扩大并行化 |
| 24M 报告 | 记录墙钟/关键口径 | 未重跑 24M 全报告 | research_only：本轮禁止 24M 并行；不为基线生成大机器产物 |

## 可选预算烟测

采集命令：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python - <<'PY'
from pathlib import Path
from app.main import prometheus_metrics
Path("/tmp/tquant-backend-compute-metrics.prom").write_text(prometheus_metrics(None).body.decode("utf-8"), encoding="utf-8")
PY
python3 scripts/check_backend_perf_budget.py --metrics-file /tmp/tquant-backend-compute-metrics.prom
```

结果：

- `tquant_rust_math_fallback_ratio_bps=0`：ok。
- `tquant_local_quote_cache_coverage_ratio_bps=0`：exceeded，但 `strict=false`，原因是本地未执行 quote cache warmup，不作为阻断。
- `tquant_runtime_task_duration_p95_ms=0`：ok，但样本为 0，只能视为 no_data。
