# 后端计算加速落地报告

日期：2026-06-03
主依据：`docs/reports/backend-compute-acceleration-landable-scope-2026-06-03.md`
参考：`docs/superpowers/plans/2026-06-03-backend-compute-acceleration-final.md`、`docs/engineering-conventions.md`、`AGENTS.md`

## 完成项

1. M0 基线
   - 新增 `docs/reports/backend-compute-acceleration-baseline-2026-06-03.md`。
   - 记录本地 `/metrics` 中 Rust、derived indicator cache、local quote cache、BFF、provider、runtime task duration 指标。
   - `monitor_bff`、`market_pulse`、`priority_board`、全市场扫描、24M 报告未强跑，原因已标注为 blocked/research_only。

2. Rust 统一 API 与 fallback
   - `backend/app/services/finance/rust_math.py` 新增高层 API：
     `rolling_mean`、`rolling_std`、`atr`、`rsi_wilder`、`vwap`、`bollinger_bands`、`beta`、`correlation`、`rank_ic`、`max_drawdown`、`volatility`。
   - `backend/app/services/finance/rust_math_fallbacks.py` 承载同口径 Python fallback，避免 `rust_math.py` 超过工程规范必须拆分阈值。
   - 保留全部既有 `rust_*` wrapper。
   - `rust_finance_math_enabled=False` 时高层 API 走 Python fallback。
   - 新增派生指标 LRU 缓存与指标：hits/misses/size。
   - 新增 parity/cache 测试：`backend/tests/test_finance_rust_math_api.py`。

3. Rust 热路径低风险接入
   - `backend/app/services/finance/performance_math.py`：最大回撤走高层 `max_drawdown`。
   - `backend/app/services/indicators.py`：ATR、RSI、VWAP、Bollinger Bands 走高层 API。
   - `backend/app/services/low_buy/atr_metrics.py`：低吸日线 ATR 优先走高层 `atr`，保留原 Python 兜底。
   - `backend/app/services/factor_mining/evaluation.py`：rank IC 走高层 `rank_ic`。
   - `backend/app/services/backtest/analyzer.py` 已经通过 `performance_math.sequence_max_drawdown_pct` 复用新入口。
   - `backend/app/services/analytics/report_queries.py` 本轮未改：该文件当前主要是报告读取/渲染，没有可安全替换的纯数学热循环。

4. I/O 与缓存治理
   - 复核 mysqlclient/PyMySQL fallback：沿用 `backend/tests/test_database_url_driver.py`。
   - `backend/app/services/market_quote_cache_refresh.py` 增加策略跟踪快照 symbols 到行情缓存核心目标集合。
   - 测试覆盖自选、优先榜、纸面持仓、监控板块成员、策略跟踪热需求。

5. N+1 守卫
   - `strategy_tracking` 已有 `test_strategy_tracking_list_keeps_hot_queries_bounded`。
   - 新增 `backend/tests/test_backend_compute_query_guards.py`，守卫 `priority_items.build_priority_items` 构建阶段不做 SQL 查询。

6. Metrics 与预算
   - `/metrics` 新增：
     - `tquant_rust_math_fallback_ratio_bps`
     - `tquant_derived_indicator_cache_hits_total`
     - `tquant_derived_indicator_cache_misses_total`
     - `tquant_derived_indicator_cache_size`
     - `tquant_runtime_task_duration_samples`
     - `tquant_runtime_task_duration_p95_ms`
   - 新增 `scripts/check_backend_perf_budget.py`，初期为可选报告门，默认不强阻塞。

7. Go/BFF fallback 冒烟
   - Go market-read tests 补成功、RemoteBffError/timeout fallback、schema mismatch 跳过坏项保留好项、stale 字段兼容。
   - BFF remote adapter tests 补 schema mismatch 与 remote failure fallback。

## 未完成项 / 风险

| 项 | 状态 | 原因 / 后续 |
|---|---|---|
| K3 全市场扫描并行化 | 未实施 | 明确禁止本轮直接实施。需单独 spike 串行 vs 并行 golden 一致后再推进。 |
| 24M 回测并行化 | 未实施 | 明确禁止本轮直接实施；`portfolio_backtest_metrics` 是组合唯一事实源，不能按月份/日期贸然分片。 |
| 全量 async 改造 | 未实施 | 明确禁止；本轮只补 fallback 测试和缓存覆盖。 |
| Go/Rust 业务重写 | 未实施 | 明确禁止；Rust 只作为可回退数学 API。 |
| 云端 p95 基线 | blocked | `scripts/measure_cloud_go_rust_performance.py` 需要 SSH 云端并注册临时用户，本轮未做部署/云端验收。 |
| 本地 quote cache coverage | no_data | 未执行缓存预热，所以 coverage_ratio_bps=0 只代表本地未采样。 |

## 基线与最终指标

本轮本地可测指标见 `docs/reports/backend-compute-acceleration-baseline-2026-06-03.md`。

新增后本地 `/metrics` 已能输出：

- Rust fallback 比例。
- 派生指标缓存 hits/misses/size。
- Runtime worker task duration samples/p95。

可选预算烟测：

```bash
python3 scripts/check_backend_perf_budget.py --metrics-file /tmp/tquant-backend-compute-metrics.prom
```

结果：退出码 0；`strict=false`；quote cache coverage 由于本地未预热显示 exceeded，但不阻断。

## 验证结果

已通过：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_finance_performance_math.py \
  backend/tests/test_finance_rust_math_api.py \
  backend/tests/test_market_quote_cache_refresh.py \
  backend/tests/test_backend_compute_query_guards.py \
  backend/tests/test_backend_refactor_foundation.py \
  backend/tests/test_bff_routes.py \
  backend/tests/test_performance_regression.py \
  backend/tests/test_backend_perf_budget_script.py -q
```

结果：`62 passed, 1 warning`。warning 为本地 LibreSSL/urllib3 环境 warning。

最终验收命令：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_finance_performance_math.py -q
```

结果：`11 passed, 1 warning`。

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_database_url_driver.py backend/tests/test_market_quote_cache_refresh.py backend/tests/test_performance_regression.py -q
```

结果：`17 passed, 1 warning`。

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
```

结果：`1186 passed, 1 warning`。

```bash
git diff --check
```

结果：通过。

```bash
git status --short
```

结果：工作树存在本轮代码/报告改动；另有未跟踪 `docs/reports/backend-compute-acceleration-benefit-risk-2026-06-03.md`，本轮未修改该文件。

## 生产排序影响

- 未修改 `strategy_policy`。
- 未绕过 `strategy_policy.participates_in_priority_board`。
- 未产生或替换 `production_score`。
- 未替换 low-buy、priority board、front-row weighted 或任何现有生产排序。
- 本轮加速改动只影响可回退数学计算入口、缓存目标集合、观测和测试，不改变策略规则或评分公式。
