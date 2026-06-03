# Backend Performance Next Stage Development Document (2026-06-03)

> **执行定位：** 本文是 `docs/superpowers/plans/2026-06-03-backend-performance-next-stage-optimization.md` 的开发落地文档。上一阶段 `docs/reports/backend-compute-acceleration-landable-scope-2026-06-03.md` 已完成，结果见 `docs/reports/backend-compute-acceleration-implementation-report-2026-06-03.md`。本轮不重复 Rust 统一 API、基础 metrics、基础行情缓存和 mysqlclient fallback。

状态：待开发执行
适用范围：后端热读路径、读模型物化、结构/行情分层缓存、二次数学热点替换、派生指标缓存、并行化 spike、24M 回测前置加速
最后核验日期：2026-06-03
目标：在不改变策略语义和生产排序的前提下，把性能优化推进到用户可感知的端态：热读接口 p95 更稳定、轮询不重复构建大 payload、全市场扫描和 24M 报告具备可验证的下一步加速路径。

## 1. 权威输入

必须先读：

- `AGENTS.md`
- `docs/engineering-conventions.md`
- `docs/superpowers/plans/2026-06-03-backend-performance-next-stage-optimization.md`
- `docs/reports/backend-compute-acceleration-implementation-report-2026-06-03.md`
- `docs/reports/backend-compute-acceleration-baseline-2026-06-03.md`

当前已知完成项：

- `backend/app/services/finance/rust_math.py` 已有高层数学 API。
- `backend/app/services/finance/rust_math_fallbacks.py` 已承载 Python fallback。
- `backend/app/main.py` 已有 Rust fallback ratio、derived indicator cache、RuntimeTask duration metrics。
- `backend/app/services/market_quote_cache_refresh.py` 已扩展行情缓存目标集合。
- `scripts/check_backend_perf_budget.py` 已存在，但初期是可选报告门。

## 2. 开发总原则

1. 测量先行：每批先记录 N0/Nx 基线，再改，再复测。
2. 请求线程只读：热读接口只能读缓存、物化快照或轻量 overlay，不直连外部行情源，不做全量重算。
3. 排序不漂移：生产排序字段来自 stable structure；live overlay 不得改变生产排序。
4. 语义不变：策略规则、评分公式、组合约束、生产门禁不变。
5. 缺数据显式：所有降级必须写明 `stale / partial / no_data / blocked`。
6. 可回退：所有新缓存、物化、预算、spike 都要有开关或回退路径。
7. 不新增大型机器 JSON 到 `docs/reports/`；大型产物放 `backend/data/analytics/` 或忽略目录，并用 Markdown 摘要说明。

## 3. 硬边界

禁止：

- 改 `strategy_policy.participates_in_priority_board`。
- 新建第二套 `portfolio_backtest_metrics`。
- 按月份分片后各自计算 max5/max10 再合并。
- 全量 async SQLAlchemy 改造。
- 引入 Celery/Kafka/Temporal/K8s。
- 新增 Web 后台 loop。
- 让 live quote overlay 影响生产排序。
- 用缓存隐藏错误数据或缺数据。

允许：

- 新增短 TTL read model cache。
- 新增 worker 侧物化任务。
- 新增只读派生指标缓存。
- 新增 metrics、预算脚本、报告。
- 新增并行化 spike，但不能写生产表。
- 24M 只加速前置数据准备，最终组合指标仍走唯一事实源。

## 4. 目标模块与建议文件

### 4.1 热读读模型

建议新增或改造：

- `backend/app/services/read_models/`
  - `monitor_read_model.py`
  - `priority_board_read_model.py`
  - `strategy_tracking_read_model.py`
  - `read_model_cache.py`
  - `live_quote_overlay.py`
- `backend/tests/test_read_model_materialization.py`
- `backend/tests/test_read_model_live_overlay.py`

如果仓库已有等价目录或服务，应复用现有结构，不强行新建。

### 4.2 Metrics

建议扩展：

- `backend/app/main.py`
- 现有 metrics snapshot helper，或新增 `backend/app/services/performance/read_model_metrics.py`

指标建议：

- `tquant_read_model_cache_hits_total{model=...}`
- `tquant_read_model_cache_misses_total{model=...}`
- `tquant_read_model_age_seconds{model=...}`
- `tquant_live_overlay_hits_total{source=...}`
- `tquant_live_overlay_misses_total{source=...}`
- `tquant_response_payload_bytes{route=...}` 或采样等价指标
- `tquant_response_serialization_ms{route=...}` 或采样等价指标

### 4.3 二次 Rust/pandas 热点

候选文件：

- `backend/app/services/low_buy/history_frames.py`
- `backend/scripts/low_buy_market_backtest_outcomes.py`
- `backend/app/services/low_buy/main_force_model_features.py`
- `backend/app/services/low_buy/candidate_metrics.py`
- `backend/app/services/low_buy/multi_timeframe.py`

规则：

- 只替换纯数学片段。
- 每个文件先 golden。
- 不散点调用低层 `rust_*` wrapper，统一走 `finance/rust_math.py` 高层 API。

### 4.4 并行化 spike

建议新增：

- `backend/scripts/parallel_scan_spike.py`
- `backend/tests/test_parallel_scan_spike.py`
- `docs/reports/parallel-scan-spike-2026-06-03.md`

要求：

- 不写生产表。
- 不替换现有物化任务。
- 只对固定策略、固定日期、固定 symbol 集做串并行对比。

### 4.5 24M 前置加速

建议新增或改造：

- `backend/scripts/backtest_24m_precompute_spike.py`
- `backend/tests/test_backtest_24m_precompute_parity.py`
- `docs/reports/backtest-24m-precompute-acceleration-report-2026-06-03.md`

要求：

- 不改 `portfolio_backtest_metrics` 规则。
- 可缓存 TradeOutcome 前置构建结果。
- 关键指标必须与原报告一致。

## 5. 数据与响应结构建议

### 5.1 Read Model Envelope

热读接口如果新增 read model envelope，建议包含：

```json
{
  "schema_version": "read-model-v1",
  "model": "priority_board",
  "snapshot_as_of": "2026-06-03T15:00:00+08:00",
  "live_as_of": "2026-06-03T15:00:05+08:00",
  "data_quality": "fresh",
  "partial_errors": [],
  "items": []
}
```

字段要求：

- `snapshot_as_of` 表示 stable structure 时间。
- `live_as_of` 表示 live quote overlay 时间。
- `data_quality` 必须可为 `fresh/stale/partial/no_data`。
- `partial_errors` 不能阻塞主链路，但必须可见。

### 5.2 Stable Structure

稳定结构可包含：

- symbol/name/strategy_key/strategy_title
- stable rank / production_score / watch_score
- strategy explanations
- risk tags
- historical performance summary
- entry/exit context
- snapshot data_quality

不得包含会随秒级行情变化而改变排序的字段。

### 5.3 Live Overlay

live overlay 可包含：

- latest_price
- change_pct
- quote_timestamp
- source_quality
- is_stale
- data_quality_message

live overlay 只能更新展示字段，不得重新计算生产排序。

## 6. 分批开发

### Batch N0：真实基线

输出：

- `docs/reports/backend-performance-next-stage-baseline-2026-06-03.md`

必须记录：

- 冷启动与 warm 后指标。
- 本地与云端分开。
- quote cache warmup 前后 coverage。
- 热接口 p50/p95/p99。
- Rust fallback ratio。
- derived cache hits/misses。
- RuntimeTask duration p95。

验收：

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
git diff --check
```

### Batch N1：热读读模型物化

开发内容：

- 为 monitor workspace、priority board、strategy tracking list 梳理 stable structure 和 live overlay。
- 增加 read model cache 或物化读取服务。
- 增加 read model metrics。
- 外部行情源不可达时，热读接口仍能返回 stale/partial 结构。

测试：

- read model 与旧同步构建 golden 一致。
- live overlay 不改变排序。
- cache hit/miss metrics 正常。
- 无快照时返回显式 stale/partial。

验收报告：

- `docs/reports/backend-read-model-materialization-report-2026-06-03.md`

### Batch N2：结构/行情分层缓存与 payload 观测

开发内容：

- 对热列表接口记录 item count、response bytes、serialization ms。
- 结构缓存 TTL 30-120 秒。
- live quote overlay 走 quote cache / Go market-read。
- 大字段先做体积观测，不直接删除。

测试：

- cache key 受参数影响。
- stale 标记可见。
- payload metrics 存在。

### Batch N3：Rust/pandas 二次热点替换

开发内容：

- 每个候选文件先写 golden。
- 替换纯数学 rolling/mean/std/volatility 片段。
- 复用 Rust 高层 API。

测试：

- 每个文件有 parity/golden。
- 关键策略报告指标不漂移。

### Batch N4：派生指标缓存扩大试点

开发内容：

- 选择 ATR、MA、strategy tracking summary stats 中 2-3 个试点。
- key 包含 `indicator|symbol|trade_date|params_hash|indicator_version`。
- 暴露按 indicator 的 hits/misses/size。

测试：

- 同 key 二次命中。
- version 变化 miss。
- TTL 到期 miss。
- flag 关闭后走原始计算。

### Batch N5：全市场扫描并行 spike

开发内容：

- 固定单策略、固定 100-300 symbols、固定 trade_date。
- 串行 baseline 与并行 feature extraction 对比。
- 输出 payload hash、排序、score、buy_signal_state 对比。

准入下一阶段：

- 100% golden 一致。
- 墙钟下降至少 25%。
- DB 查询数没有明显放大。

禁止：

- 写生产表。
- 替换现有物化任务。

### Batch N6：24M 回测前置加速

开发内容：

- 只加速数据准备和 TradeOutcome 前置构建。
- 最终仍调用 `portfolio_backtest_metrics`。
- 可使用 DuckDB/Parquet/Rust/cache。

测试：

- PF、平均单笔、max5、max10、最大回撤一致。
- 前置构建墙钟下降。

### Batch N7：性能预算分级准入

开发内容：

- Level 1 CI 强阻塞：fallback ratio、query budget、schema。
- Level 2 本地服务预算：热接口 p95、serialization ms。
- Level 3 云端巡检：monitor_bff、market_pulse、priority_board、quote coverage。

规则：

- 不把云端网络波动直接作为普通 PR 阻塞。
- 阈值调整必须写报告。

## 7. 测试矩阵

| 类型 | 必跑命令/测试 | 适用批次 |
|---|---|---|
| 全量回归 | `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q` | 每批 |
| 数学 parity | `test_finance_performance_math.py`、`test_finance_rust_math_api.py` | N3/N4 |
| 查询预算 | `test_backend_compute_query_guards.py` 与新增 read model tests | N1/N2 |
| 缓存失效 | 新增 indicator cache tests | N4 |
| 并行 spike | `test_parallel_scan_spike.py` | N5 |
| 24M parity | `test_backtest_24m_precompute_parity.py` | N6 |
| 预算脚本 | `python3 scripts/check_backend_perf_budget.py ...` | N7 |
| 空白检查 | `git diff --check` | 每批 |

## 8. 报告要求

每批报告必须写：

- 改动范围。
- 测量前后数据。
- cold/warm 是否区分。
- cache hit/miss。
- p95 或墙钟结果。
- 未测项和原因。
- 是否影响生产排序。
- 回滚方式。

报告路径：

- N0：`docs/reports/backend-performance-next-stage-baseline-2026-06-03.md`
- N1/N2：`docs/reports/backend-read-model-materialization-report-2026-06-03.md`
- N5：`docs/reports/parallel-scan-spike-2026-06-03.md`
- N6：`docs/reports/backtest-24m-precompute-acceleration-report-2026-06-03.md`
- N7：可写入 `docs/reports/backend-performance-budget-gates-2026-06-03.md`

## 9. 回滚方案

- Read model cache：关闭 feature flag 或 TTL 设 0，回到旧同步读路径。
- Live overlay：关闭 overlay，返回 stable snapshot 的 stale 行情字段。
- Payload metrics：只读观测，可保留。
- Rust 二次替换：按文件 revert，或关闭 `rust_finance_math_enabled`。
- Indicator cache：关闭 cache flag。
- 并行 spike：删除/停用实验脚本，不影响生产。
- 24M 前置缓存：清空缓存，回到原 TradeOutcome 构建。
- 预算门：Level 2/3 可降级为报告；Level 1 只允许在有报告说明时临时放宽。

## 10. Definition of Done

- N0 真实基线完成，no-data 项有明确原因。
- 热读接口具备 stable structure + live overlay，且排序不因 live overlay 漂移。
- 外部行情源不可达时，monitor/priority/strategy tracking 可返回 stale/partial 结构。
- 热接口 p95 或 serialization ms 较 N0 有明确下降；若未下降，报告说明瓶颈转移。
- Rust/pandas 二次替换有 golden，无策略指标漂移。
- 派生指标缓存有 version/TTL/metrics/关闭开关。
- 并行扫描只完成 spike，不进生产路径；若结果一致再另立生产化计划。
- 24M 回测只加速前置数据，`portfolio_backtest_metrics` 唯一事实源不变。
- 全量 `pytest backend/tests -q` 与 `git diff --check` 通过。
