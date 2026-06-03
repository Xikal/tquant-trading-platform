# Backend Performance Next Stage Optimization Plan (2026-06-03)

> **前置状态：** `docs/reports/backend-compute-acceleration-landable-scope-2026-06-03.md` 中的确定性需求已完成，落地结果见 `docs/reports/backend-compute-acceleration-implementation-report-2026-06-03.md`。本计划只处理下一阶段性能优化，不重复 Rust 统一 API、基础缓存覆盖、mysqlclient fallback、基础 metrics 和守卫测试。

状态：下一阶段执行计划
适用范围：后端热读路径、全市场扫描、24M 回测前置计算、策略追踪/优先榜读模型
最后核验日期：2026-06-03
目标：在不改策略语义、不改生产准入、不新建并行组合引擎的前提下，把后端性能优化从“基础加速栈接线”推进到“真实生产体感变快”：热页面 p95 稳定下降，全市场扫描/24M 报告有可证明的墙钟下降，缓存命中与 fallback 比例可观测并可控。

## 1. 当前基线与已完成能力

已完成：
- Rust finance math 高层 API 与 Python fallback。
- Rust 热路径低风险接入：指标、ATR、RSI、VWAP、Bollinger、rank IC、max drawdown。
- mysqlclient 优先与 PyMySQL fallback。
- 行情缓存核心目标集合扩展。
- priority board / strategy tracking 查询上界守卫。
- `/metrics` 新增 Rust fallback ratio、derived indicator cache、RuntimeTask duration。
- 可选性能预算脚本。

仍然不足：
- 当前 `backend-compute-acceleration-baseline-2026-06-03.md` 主要是本地 no-data 基线，不能证明云端用户体感已提升。
- 全市场扫描并行化、24M 回测并行化尚未做，只能作为 spike。
- 热接口仍可能在结构数据、行情数据、策略派生字段之间重复构建大 payload。
- 策略追踪、优先榜、监控页需要更明确的“稳定结构缓存 + live 字段覆盖”读模型。
- 缓存命中率与 p95 预算还没有形成稳定强门。

## 2. 硬边界

1. 不改策略规则、评分公式、组合约束、生产门禁。
2. 不并行实现 `portfolio_backtest_metrics`；24M 组合指标仍使用唯一事实源。
3. 不做全量 async SQLAlchemy，不重写 FastAPI 主框架。
4. 不引入 Celery/Kafka/Temporal/K8s。
5. 不把 Web 请求线程接入外部行情源或新增 Web 后台 loop。
6. 缺数据必须显式标记 `blocked / research_only / no_data / stale / partial`。
7. 所有优化必须先测量、再修改、再复测。
8. 任何缓存必须有版本、TTL、失效策略和 metrics。
9. 并行化只能先做 spike；串行/并行 golden 未通过前不得进生产读写路径。

## 3. 总体路线

| 阶段 | 主题 | 收益 | 风险 | 结论 |
|---|---|---|---|---|
| N0 | 当前实现真实测量 | 解决 no-data 基线问题 | 需要云端/本地服务可用 | 必须先做 |
| N1 | 热读读模型物化 | 降 p95、减少重复构建 payload | 缓存陈旧/字段漏更新 | 高优先级 |
| N2 | 结构/行情分层缓存 | 监控页、优先榜、策略追踪体感提升 | stale 标记不清会误导 | 高优先级 |
| N3 | Rust/pandas 热点二次替换 | 降 CPU 循环和 pandas rolling 开销 | 浮点/窗口口径漂移 | 中高优先级 |
| N4 | 派生指标缓存扩大试点 | 重复刷新更快 | key/version 错误 | 中优先级 |
| N5 | 全市场扫描并行 spike | 潜在最大墙钟收益 | 合并/排序/partial 破坏口径 | 只做 spike |
| N6 | 24M 回测前置加速 | 报告生成更快 | 组合状态跨时间约束复杂 | 只加速前置数据 |
| N7 | 性能预算从报告门到准入门 | 防回退 | 指标波动误报 | 分级推进 |

## 4. N0 当前实现真实测量

### 目标

把上一阶段的本地 no-data 基线替换为“可用于决策”的真实基线。

### 任务

- 启动当前后端服务和必要依赖，采集本地 warm/cold 指标。
- 如果云端已部署本轮改动，跑云端性能脚本，记录：
  - `monitor_bff` p50/p95/p99
  - `market_pulse` p50/p95/p99
  - `priority_board` p50/p95/p99
  - `/metrics` 中 Rust hits/fallbacks/errors、quote cache coverage、BFF cache、provider slow calls
  - RuntimeTask duration p95
- 对 quote cache 做一次 warmup，再记录 coverage，而不是保留 `coverage_ratio_bps=0` 的 no-data 状态。
- 输出 `docs/reports/backend-performance-next-stage-baseline-2026-06-03.md`。

### 验收

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
curl -fsS -H "X-Admin-Token: $ADMIN_API_TOKEN" "$BASE/metrics" | rg "rust_math|local_quote_cache|bff_|provider_|runtime_task"
```

### 风险控制

- 报告必须区分本地、云端、未部署、no_data。
- 不能用旧云端报告替代本轮实现后的真实状态。

## 5. N1 热读读模型物化

### 目标

把监控页、优先榜、策略追踪的重复聚合从请求线程移到 worker 或短 TTL 读模型，让请求线程只读已准备好的结构，再覆盖 live 字段。

### 任务

- 梳理三个热读模型：
  - monitor workspace
  - priority board
  - strategy tracking list
- 为每个模型拆出：
  - stable structure：策略、分组、静态解释、风控说明、历史统计、排序依据。
  - live overlay：最新价、涨跌幅、quote timestamp、data_quality、stale 状态。
- stable structure 使用物化快照或短 TTL cache，live overlay 从 quote cache / Go market-read 读取。
- 请求线程禁止重新跑全量策略聚合；缺快照时返回 stale/partial，而不是同步重算。
- 增加 `read_model_age_seconds`、`read_model_hit/miss`、`live_overlay_hit/miss` metrics。

### 预期收益

- 监控页和优先榜 p95 下降。
- BFF partial timeout 降低。
- 请求 payload 构建更稳定，外部行情波动不再拖垮整页。

### 主要风险

- stale structure 与 live overlay 时间不一致。
- 读模型字段遗漏导致前端显示不完整。
- 快照失效时误返回旧排序。

### 风险控制

- 响应必须包含 `snapshot_as_of`、`live_as_of`、`data_quality`。
- 排序字段来自 stable structure，live overlay 不改变生产排序。
- 缺快照时返回 `partial/stale`，不静默。

### 验收

- 外部行情源不可达时，热页面仍返回结构。
- 同一输入下物化模型与旧同步构建模型 golden 一致。
- p95 较 N0 下降，或者在报告中说明瓶颈转移。

## 6. N2 结构/行情分层缓存

### 目标

减少每次轮询时“结构 + live 行情 + 大字段解释”一起重建。

### 任务

- 热接口列表响应改为分层缓存：
  - structure TTL：30-120 秒，按页面和参数区分。
  - live quote TTL：沿用本地 quote cache。
  - heavy explanation/detail：必要时懒加载或 detail endpoint。
- 对大列表 payload 增加字段体积统计：
  - item count
  - response bytes
  - serialization ms
- 对策略追踪和优先榜的大字段做“列表轻量字段 / 详情完整字段”拆分评估，不立即删除字段。

### 预期收益

- 轮询型页面更稳定。
- JSON serialization 时间下降。
- 前端首包和 BFF payload 更小。

### 主要风险

- 前端依赖列表中的完整字段。
- detail 拆分可能引入额外请求。

### 风险控制

- 先只加 payload metrics，不直接删字段。
- 若拆字段，必须保留兼容期或 feature flag。
- 前端 API 契约和测试同步。

## 7. N3 Rust/pandas 热点二次替换

### 目标

继续推进上一阶段未覆盖的 pandas rolling / Python 循环热点。

### 候选路径

- `backend/app/services/low_buy/history_frames.py`：ma5/ma10/ma20/ma60 rolling。
- `backend/scripts/low_buy_market_backtest_outcomes.py`：历史 MA rolling。
- `backend/app/services/low_buy/main_force_model_features.py`：均线、波动率、量能均值。
- `backend/app/services/low_buy/candidate_metrics.py`：成交量均值、post-board 均值、部分 rolling 派生。
- `backend/app/services/low_buy/multi_timeframe.py`：weekly/monthly rolling。

### 任务

- 对每个文件先写 golden。
- 只替换纯数学、无业务分支的计算片段。
- 复用 `finance/rust_math.py` 高层 API，不散点调用低层 `rust_*` wrapper。
- 每个文件单独提交、单独测试。

### 预期收益

- 全市场扫描 CPU 时间下降。
- 24M 报告前置样本构建时间下降。
- Rust hit rate 上升。

### 主要风险

- pandas rolling 与 Rust rolling 的 NaN/None/窗口边界不同。
- 四舍五入口径影响阈值边界。

### 风险控制

- golden 覆盖短窗口、缺值、完整窗口、边界阈值。
- 替换后关键策略报告数值必须一致。

## 8. N4 派生指标缓存扩大试点

### 目标

把上一阶段的派生指标缓存从基础能力推进到真实热指标。

### 任务

- 选择 2-3 个高频只读指标试点：
  - ATR
  - MA/rolling mean
  - strategy tracking summary stats
- key 格式固定：
  - `indicator|symbol|trade_date|params_hash|indicator_version`
- 增加 cache invalidation 测试：
  - 同 key 二次命中。
  - version 改变 miss。
  - TTL 到期 miss。
- `/metrics` 按 indicator 输出 hits/misses/size。

### 预期收益

- 同日重复刷新更快。
- worker 重算时避免重复派生。

### 主要风险

- 缓存陈旧。
- 内存增长。
- 对依赖当前时间的指标误缓存。

### 风险控制

- 只缓存可复现只读指标。
- maxsize + TTL。
- 允许通过 env flag 关闭。

## 9. N5 全市场扫描并行化 spike

### 目标

验证并行化是否能在不改变结果的前提下降低墙钟。本阶段只做 spike，不进入生产路径。

### 任务

- 选择单策略、固定 100-300 个 symbol、固定 trade_date。
- 实现实验性分片：
  - serial baseline
  - parallel candidate feature extraction
- 合并后按稳定排序输出。
- 对比串行/并行：
  - symbol count
  - candidate count
  - score
  - buy_signal_state
  - ordering
  - payload hash
- 输出 `docs/reports/parallel-scan-spike-2026-06-03.md`。

### 预期收益

- 如果 spike 成功，可进入生产化计划。
- 如果失败，也能定位是合并、排序还是跨 symbol 上下文问题。

### 主要风险

- 并行结果顺序漂移。
- partial 分片造成隐性缺数据。
- worker 并发抢占 DB/CPU。

### 风险控制

- 不写生产表。
- 不影响现有物化任务。
- 失败分片必须显式 `partial`。

### 进入下一阶段条件

- 串行/并行 golden 100% 一致。
- 墙钟下降至少 25%。
- DB 查询数没有明显放大。

## 10. N6 24M 回测前置加速

### 目标

降低 24M 报告耗时，但不并行实现组合规则。

### 允许优化

- 并行读取或准备历史数据。
- DuckDB/Parquet 预聚合每日候选样本。
- Rust 加速 drawdown/rolling/volatility。
- 缓存 TradeOutcome 前置构建结果。

### 禁止优化

- 按月份分片后各自计算 max5/max10 再相加。
- 新建第二套 `portfolio_backtest_metrics`。
- 改同票冷却、同板块、弱市、退潮等组合约束。

### 验收

- `portfolio_backtest_metrics` 调用路径不变。
- PF、平均单笔、max5、max10、最大回撤与基线一致。
- 前置构建墙钟下降。

## 11. N7 性能预算分级准入

### 目标

把性能预算从“可选烟测”推进到分级准入，防止回退。

### 分级

- Level 1：本地静态预算，CI 强阻塞。
  - Rust fallback ratio 不异常。
  - 测试中的 query budget 不超上界。
  - payload schema 不破坏。
- Level 2：本地服务预算，PR 可选或 nightly。
  - 热接口 p95 不超过基线 ×1.2。
  - serialization ms 不超过阈值。
- Level 3：云端巡检预算，不阻塞普通 PR。
  - monitor_bff、market_pulse、priority_board p95。
  - quote cache coverage。
  - BFF partial timeout。

### 风险控制

- 不把云端网络波动直接作为普通 CI 阻塞。
- 每次阈值调整必须写报告。

## 12. 验收命令

```bash
# 全量后端回归
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q

# 定向性能守卫
PYTHONPATH=backend backend/.venv/bin/python -m pytest \
  backend/tests/test_finance_performance_math.py \
  backend/tests/test_finance_rust_math_api.py \
  backend/tests/test_backend_compute_query_guards.py \
  backend/tests/test_performance_regression.py -q

# 可选预算烟测
python3 scripts/check_backend_perf_budget.py --metrics-file /tmp/tquant-backend-compute-metrics.prom

# 代码空白检查
git diff --check
```

## 13. 交付物

- `docs/reports/backend-performance-next-stage-baseline-2026-06-03.md`
- `docs/reports/backend-read-model-materialization-report-2026-06-03.md`
- `docs/reports/parallel-scan-spike-2026-06-03.md`
- `docs/reports/backtest-24m-precompute-acceleration-report-2026-06-03.md`
- 代码改动必须配套定向测试和全量 pytest 结果。

## 14. 推荐执行顺序

1. N0 当前实现真实测量。
2. N1 热读读模型物化。
3. N2 结构/行情分层缓存。
4. N3 Rust/pandas 热点二次替换。
5. N4 派生指标缓存扩大试点。
6. N7 性能预算分级准入。
7. N5 全市场扫描并行化 spike。
8. N6 24M 回测前置加速。

## 15. 一句话结论

下一步不要急着做全市场并行或 24M 并行。先把当前实现的真实 p95 和缓存命中测出来，再把热读路径改成“物化结构 + live overlay”，这是最可能改善用户体感、同时最不容易破坏策略口径的优化。并行化要做，但必须以 spike 和 golden 一致为准入门槛。
