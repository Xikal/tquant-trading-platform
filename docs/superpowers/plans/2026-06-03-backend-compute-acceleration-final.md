# Backend Compute Acceleration Final Plan (2026-06-03)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 或 superpowers:executing-plans。Steps 用 `- [ ]` 跟踪。
>
> **定位(诚实结论)**:后端计算性能问题**不是"算法慢"也不是"该换语言"**。平台已经有 Rust(`tquant_rs` 11 个 pyfunction)、Go(bff-gateway / market-read-service / scan-worker)、DuckDB、Redis、RuntimeTask 完整加速栈,**真实问题是这些加速能力严重欠复用**——以及 I/O 同步阻塞 + 缓存覆盖不足。本计划是**最终方案**:不引新语言、不上 async 全量重写、不替换主框架;通过"复用现成 Rust + 治理 I/O + 缓存覆盖 + 选择性并行 + 口径冻结守卫"把计算速度系统性拉起来,**严格保证策略稳定性**(同输入同输出)。
>
> **关联**:`docs/superpowers/plans/2026-05-30-backend-performance-hardening.md`(G1/G2/G3 I/O 层强化,本计划复用其结论)、`docs/engineering-conventions.md`(单一事实源、生产/研究边界)、`backend/scripts/low_buy_market_backtest_reporting.py`(`portfolio_backtest_metrics` 唯一组合实现)。

**Goal:** 在不改业务语义、不影响策略稳定性的前提下,把全市场扫描/优先榜物化/24M 回测/策略跟踪/分析层的端到端耗时显著拉低,把已有 Rust/Go 加速从"角落里"接到所有热路径,把同步阻塞 I/O 降到该 worker 走 worker、该缓存走缓存、该批量走批量。

**Tech Stack(保持)**:FastAPI(sync) + SQLAlchemy 2.0 + MySQL + Redis + DuckDB + Rust(`tquant_rs`) + Go(bff/market-read/scan-worker) + RuntimeTask。**唯一驱动级变更**:PyMySQL → mysqlclient(C)(沿用 G2);**零新增运行时框架**。

---

## 1. 真实瓶颈诊断(2026-06-03 实测)

| 现象 | 实测证据 | 根因 |
|---|---|---|
| Rust 加速严重欠复用 | `rg "tquant_rs\|rust_finance_math\|finance/rust_math" app -g'*.py'` 命中仅 `finance/rust_math.py:7` + `core/config.py:1` | 11 个 Rust 函数(`rolling_mean/std`、`ATR`、`RSI`、`VWAP`、`Bollinger`、`beta`、`correlation`、`rank_ic`、`max_drawdown`、`volatility`)只在 1 个适配文件用,**28 个 pandas/numpy 文件没接** |
| Go 加速复用度有限 | market-read 客户端 4 处、bff 2 处、go_scan 6 处 | 多数 Python 路径直接打 MySQL,没走 Go 读聚合 |
| 同步阻塞 | 409 个 `sync def` 路由 vs 4 个 `async def`;PyMySQL 纯 Python | 每个 DB/外部 I/O 阻塞一个 worker;并发只能加 worker |
| 行情缓存覆盖窄 | `market_quote_cache_refresh.py:14` `DEFAULT_LIMIT=200`,云报告 Redis 命中 643 / MySQL 回退 2494(~20% 命中) | 预热口径=自选+高流动性 ≠ 实际被查询集合 |
| N+1 嫌疑 | `priority_items.py:70 for row in rows`(逐行 `score_low_buy_candidate_for_production`)、`strategy_tracking.py:452/605` 循环里查 DB | 热聚合按行往返 |
| 缓存使用率极低 | `lru_cache/cachetools/TTLCache` 全仓 < 10 处 | 热点指标重复计算 |
| `low_buy` 域过大 | 24.5K 行 / ~130 文件 | 大量按需可缓存/可批量的派生计算散落 |
| 物化全量扫描慢 | `low_buy_materialization.py:271` 已用 `fetch_rows_for_symbols` 批量(好);但策略 × 板块 × 多日线指标仍逐 symbol 在 Python 中循环 | Python 循环 + pandas 单标的算法栈 |

**结论:瓶颈是"既有加速没接 + I/O 阻塞 + 缓存覆盖薄 + Python 循环里重算"。** 不是 CPU 上限,不是并发上限,不是"该换语言"。

---

## 2. 明确排除(即便不计成本也不做,理由必须留档)

| 选项 | 裁决 | 理由 |
|---|---|---|
| async SQLAlchemy + asyncmy 全量重写 | ❌ | 112K 行同步代码重写、风险巨大;少用户场景瓶颈不在请求并发上限;ROI/风险极低 |
| Go/Rust 重写业务 | ❌ | 丢弃成熟领域逻辑;CPU 密集路径已由 Rust/Go 承担(只是没接);慢的是 I/O 与未复用 |
| 换 NoSQL / 新存储 | ❌ | MySQL(OLTP)+Redis(缓存)+DuckDB(OLAP) 已覆盖,再加是过度工程 |
| Celery/Kafka/Temporal | ❌ | RuntimeTask DB 队列在此规模够用,引入只增运维面 |
| K8s 微服务爆炸 | ❌ | 单实例 compose 适配少用户;拆只增运维 |
| 全站 Cython / Numba | ❌ | 与既有 Rust 重叠,且不稳定;直接接 Rust 即可 |

**唯一值得的"架构动作"是 G3 的选择性异步**:让请求线程永不直连外部行情源,外部拉取收敛到 worker + 异步 httpx。这是增量隔离,不是重写。

---

## 3. 硬边界(不可跑偏 · 策略稳定性保护)

**这一节是本计划区别于"性能优化"和"破坏稳定性"的分界线,实施期必须始终成立:**

1. **不改业务语义/口径**:本计划只换"实现",不动"规则"。任何加速都必须输出**完全相同**的数值(同输入 → 同输出)。
2. **`portfolio_backtest_metrics` 唯一事实源**:max5/max10/同票冷却/同策略/同板块/弱市/退潮口径只此一份;加速只接它,不并行实现。
3. **生产准入唯一门 = `strategy_policy.participates_in_priority_board`**:`production_scoring` 不维护第二份名单;加速不绕过门。
4. **缺数据显式降级**:`blocked / research_only / no_data / stale`,禁空值/假值/默认 0 占位。
5. **Rust/Go 必须有 Python fallback parity**:Rust 不可用时回落 Python,**parity 测试守住数值一致**(浮点容差 ≤1e-9 或既有约定)。
6. **重计算只在 worker**:Web 默认 `WEB_RUNTIME_BACKGROUND_JOBS_ENABLED=false`,不新增 Web 后台 loop;请求线程不直连外部源。
7. **可复现**:同输入 + 同 `engine_version` + 同参数 → 同结果(golden 测试守);加速版本变更必须 bump version + 守卫测试。
8. **测量先行,无回归才进下一批**:每批前后基线对比;数值/分布回归即停。
9. **守卫测试不可回退**:`test_low_buy_production_scoring`、`test_core_aux_strategies_match_latest_24m_report` 等口径守卫必须全绿。

---

## 4. 加速三栈复用全景(本计划的核心增量)

### 4.1 Rust(`tquant_rs`)接入清单(最高 ROI)

| Rust 函数 | 当前 Python 实现位置(应替换) | 调用频率 | 验收 |
|---|---|---|---|
| `rolling_mean_values` | `low_buy/candidate_metrics.py`、`backtest/*`、`analytics/*` | 高(扫描 × 全市场 × 每日) | parity 1e-9 |
| `rolling_std_values` | 同上 | 高 | parity 1e-9 |
| `atr_wilder_values` | `low_buy/atr_metrics.py`、`backtest/broker.py` | 高 | parity 1e-9 |
| `rsi_wilder_value` | `low_buy/factor_functions.py` 等 | 中 | parity 1e-9 |
| `vwap_value` | `low_buy/candidate.py`、`market/*` | 中 | parity 1e-9 |
| `bollinger_bands_values` | `low_buy/factor_*` | 中 | parity 1e-9 |
| `beta_value`/`correlation_value` | 因子/归因 | 中 | parity 1e-9 |
| `rank_ic_value` | `factor_mining/*` | 低-中 | parity 1e-9 |
| `max_drawdown_values` | `backtest/*`、`analytics/*` | 高 | parity 1e-9 |
| `volatility_value` | `backtest/*` | 中 | parity 1e-9 |

**操作规则**:
- 不直接散点调用,统一经 `finance/rust_math.py` 暴露 `rolling_mean(values, window) -> list[float | None]` 等 API,内部自动选择 `tquant_rs` 或 Python fallback。
- **每个函数附 parity 测试**:同一输入跑 Rust 与 Python,断言数值一致(浮点容差既有约定)。
- 加速器禁用开关:`rust_finance_math_enabled=False` 时全走 Python fallback,作为应急回退。

### 4.2 Go(bff-gateway / market-read / scan-worker)接入

| Go 服务 | 当前 Python 直查 MySQL 的热点 | 应改走 Go |
|---|---|---|
| market-read | 全市场报价聚合、ETF 行情、板块成员行情 | 经 `market/go_read_client.py` |
| bff-gateway | 监控/优先榜/纸面/策略追踪 workspace 聚合 | 经 `bff/remote_adapters.py` |
| scan-worker | 全市场扫描(已在用) | 保留 |

**操作规则**:
- Python 保留 fallback;Go 失败/超时自动回退,**fallback 路径必须 parity**(数值/字段一致)。
- Go 服务的 `fallback_available=true` 必须有冒烟测试。

### 4.3 DuckDB(已有 analytics worker)接入

- 24M 大扫描、归因聚合、跨策略对比:走 DuckDB(Parquet)从 OLTP 卸载,**不再压 MySQL**(参考 D1 Analytics 一等公民)。
- 物化产物落 `backend/data/analytics/`,manifest 可追溯;守卫测试断言"同 manifest 重跑结果一致"。

---

## 5. Existing Code Anchors(复用,勿重写)

- Rust 适配:`backend/app/services/finance/rust_math.py`(已实现 `metrics_snapshot/_rust_module/_python_fallback` 模式,复用)
- Rust 源码:`rust/tquant-rs/src/{lib.rs,finance_core.rs}`(11 个 pyfunction)
- Go 客户端:`backend/app/services/market/go_read_client.py`、`backend/app/services/bff/remote_adapters.py`、`backend/app/services/low_buy/go_scan_worker.py`
- 行情缓存:`backend/app/services/market_quote_cache_refresh.py`(目标符号集合 `_target_symbols`)
- 物化:`backend/app/services/low_buy_materialization.py:271`(批量 `fetch_rows_for_symbols`)、`backend/scripts/analytics_worker.py`
- 组合唯一口径:`backend/scripts/low_buy_market_backtest_reporting.py: portfolio_backtest_metrics` (:679-840)
- 守卫测试:`backend/tests/test_low_buy_production_scoring.py`、`test_strategy_24m_duckdb_report.py`、`test_analytics_worker.py`、`test_rust_finance_math.py`(若无则补)
- DB:`backend/app/core/database.py`(sync engine + pool),compose `mysql+pymysql://`
- 指标观测:`backend/app/main.py /metrics`(provider_*、local_quote_cache_*、bff_*、rust_*)

---

## 6. Milestones(5 批,按 ROI 排序,独立可验收/回滚)

### M0 基线测量(0.5d)
取基线 + 冻结口径:
- `/metrics`(`local_quote_cache_*` / `provider_*` / `rust_math_*` / `bff_*`)
- Go market-read `/metrics`(hits / mysql_fallbacks / unresolved)
- 跑云性能脚本:`monitor_bff` / `market_pulse` / `priority_board` / 全市场扫描 / 24M 回测的 p95 与墙钟
- 跑全量 `pytest backend/tests` 留绿基线 + 24M 报告基线(关键策略 PF/平均单笔/max5/max10/回撤)

### Batch K1 ｜ Rust 复用接入(最高 ROI · 先做)
让既有 11 个 Rust 函数全面接入热路径;**parity 测试守住稳定性**。

### Batch K2 ｜ I/O 治理(沿用既有 G1/G2/G3)
本批引用 `2026-05-30-backend-performance-hardening.md` 的 G1/G2/G3,**不重复实施**;只补本计划新发现的 N+1 与缓存治理。

### Batch K3 ｜ 全市场扫描并行化
利用 RuntimeTask 任务分片 + 进程池,把"全市场 5000 标的 × 多策略"按"组(symbol 分桶)+ 策略"分片并行;**结果合并保持顺序与口径稳定**。

### Batch K4 ｜ 缓存覆盖治理
扩 `lru_cache` / `TTLCache` 到热点派生指标(均线/ATR/分位/板块强度),按 `(symbol, trade_date, indicator_version)` 缓存;失效策略明确。

### Batch K5 ｜ 持续观测与守卫
`/metrics` 暴露 Rust 命中率、Python fallback 次数、N+1 计数、缓存命中率;CI 守卫不允许 fallback 比例突增。

---

## 7. Batch K1 ｜ Rust 复用接入

### K1-1 适配层标准化
- [ ] 失败用例:对 `finance/rust_math.py` 已有的 10 个 Python fallback,断言**与 Rust 数值一致**(parity 测试集 `test_rust_finance_math_parity.py`)——一致即可发起替换;若 parity 失败,先修 Rust 或 fallback,绝不在不一致状态下替换业务调用。
- [ ] `finance/rust_math.py` 暴露统一签名:`rolling_mean(values, window) -> list[float | None]`、`atr(highs, lows, closes, period) -> list[float|None]`、`vwap(prices, volumes) -> Optional[float]` 等;内部 `_rust_or_python(name, *args)` 自动选择 + 记录 `rust_math_metrics`。
- [ ] 测试:`pytest backend/tests/test_rust_finance_math.py -q`(若无则建)、`metrics_snapshot()` 含 `hits/fallbacks/errors/disabled`。

### K1-2 替换业务调用(逐文件 parity)
- [ ] 失败用例:针对每个待替换文件(`low_buy/candidate_metrics.py` 等),先存 Python 老版本输出快照(golden);替换后跑同一输入,数值 1e-9 容差通过。
- [ ] 替换顺序:`atr_metrics` → `candidate_metrics(rolling_mean/std)` → `factor_functions(RSI/Bollinger)` → `backtest/broker(ATR/MD)` → `analytics/report_queries(MD)` → 因子/归因(beta/corr/rank_ic)。
- [ ] 每替换一个文件单独提交,**golden 测试守口径**(同标的同日数据,关键指标数值一致)。
- [ ] **禁止合并多文件提交**:一旦回归,定位代价指数上升。

### K1-3 应急开关
- [ ] `rust_finance_math_enabled=False` 时全走 Python fallback;运行时可切换。
- [ ] 守卫测试:`enabled=False` 下结果与 `enabled=True` 一致(parity)。

**K1 验收**:
- Rust `hits` 显著上升、`fallbacks` ≈ 0、`errors=0`;
- 全市场扫描墙钟较 M0 显著下降(预计 30–60%,视具体指标占比);
- `pytest backend/tests` 全绿;24M 报告关键策略数值与 M0 1e-9 一致(golden);
- 关闭 flag → 走 Python fallback,结果与开启一致(应急回退验证)。

---

## 8. Batch K2 ｜ I/O 治理(引用 G1/G2/G3,补本计划新发现)

### K2-1 引用既有 G1/G2/G3
- 行情缓存按需扩展(G1):`market_quote_cache_refresh._target_symbols` 并入"自选+优先榜物化候选+持仓+板块成员"。
- PyMySQL → mysqlclient(G2):URL `mysql+pymysql://` → `mysql+mysqldb://`;Dockerfile 装系统库;保留 fallback。
- 热端点请求隔离(G3):`market_pulse` 等只读缓存/物化,外部源不可达不阻塞请求线程。
- **不在本文件实施**,只列对应验收门。

### K2-2 N+1 治理(本计划新发现)
- [ ] 失败用例:对 `priority_items._build_priority_item`(`:70-204`)逐行 `score_low_buy_candidate_for_production`,加"DB 往返次数 ≤ N"断言;对 `strategy_tracking.py:452/605` 等同理。
- [ ] 修复:批量预取(`selectinload`/`in_` 批取代替逐行);共享上下文(market_context、shadow_status)只查一次再传入。
- [ ] 测试:同输入下旧/新实现 golden 一致;DB 往返次数下降。

### K2-3 连接池/驱动复核
- [ ] 校验 `db_pool_size / max_overflow` 与 `APP_WORKERS × 每请求连接` 匹配;`pool_pre_ping=True` 保留。
- [ ] 不盲目加大;不回退 SEC2(限流 worker 口径)。

**K2 验收**:Redis 命中率 ≥90%、MySQL 回退降 ≥80%、`unresolved_misses=0`、`bff_partial_timeout=0`;priority_board/market_pulse p95 显著下降;`pytest backend/tests` 全绿;N+1 测试守住上界。

---

## 9. Batch K3 ｜ 全市场扫描并行化

### K3-1 任务分片(symbol 分桶 × 策略)
- [ ] 现状:`low_buy_materialization` 全市场扫描已批量 `fetch_rows_for_symbols`(:271),但策略 × symbol 仍 Python 循环。
- [ ] 失败用例:把扫描任务按 `(strategy, symbol_bucket)` 分片入 `RuntimeTaskQueue`,由 backtest-worker / analytics-worker 并行消费;**断言合并结果与单进程顺序版本数值与排序完全一致**(golden,稳定性核心)。
- [ ] 分桶大小可配(如 100 symbols/桶);进程池规模受 `BACKTEST_WORKER_CONCURRENCY` 控制,**不与 web 共享 CPU**(已天然隔离)。

### K3-2 24M 回测并行
- [ ] 类似按 `(strategy, year-month-bucket)` 分片;最终聚合走 `portfolio_backtest_metrics`(单一事实源,不并行实现规则)。
- [ ] 测试:并行版 vs 串行版结果 1e-9 一致(关键指标:成交数、PF、平均单笔、最大回撤、max5/max10)。

### K3-3 取消/超时/恢复
- [ ] 每分片支持取消标记;心跳/进度上报;失败可重试。
- [ ] 一次任务整体超时阈值;超时分片不计入结果(显式 `partial` 标记,**不影响整体口径**)。

**K3 验收**:全市场扫描/24M 回测墙钟显著下降;并行 vs 串行 golden 一致;失败/超时显式标记不静默。

---

## 10. Batch K4 ｜ 缓存治理

### K4-1 派生指标 LRU/TTL
- [ ] 失败用例:同 `(symbol, trade_date, indicator_version)` 二次调用应命中缓存;`indicator_version` 改变必须 miss。
- [ ] 引入 `cachetools.TTLCache` 或 `functools.lru_cache(maxsize)`,**按指标版本 invalidate**;版本随算法变更 bump,自动失效旧缓存。
- [ ] 适用对象:均线、ATR、滚动分位、板块强度、相对强度等"派生只读"指标。
- [ ] **不缓存可写/有状态/有时间窗依赖时间戳变化的对象**(避免读到陈旧数据)。

### K4-2 缓存键稳定性与可追溯
- [ ] 缓存 key = `f"{indicator}|{symbol}|{trade_date}|{params_hash}|{version}"`;不得依赖 dict 顺序。
- [ ] `/metrics` 暴露每类缓存的 `hits/misses/size`。
- [ ] 命中率 < 阈值告警(可观测,不阻塞)。

**K4 验收**:重复请求显著加速;命中率经 `/metrics` 可见;版本变更触发自动失效(测试);Memory footprint 受控(`maxsize` + TTL)。

---

## 11. Batch K5 ｜ 观测与守卫

### K5-1 `/metrics` 扩展
- [ ] 暴露:`rust_math_*`(hits/fallbacks/errors/disabled,已有保留)、`db_n_plus_one_estimated`(可选,启发式)、`cache_*_hits/misses/size`、`worker_task_duration_p95`(分 task_type)。
- [ ] CI/巡检:`fallbacks` 比例突增即告警(异常回退到 Python 通常意味着 Rust 编译/加载有问题)。

### K5-2 守卫测试不可回退
- [ ] 沿用并扩展:`test_rust_finance_math_parity`、`test_low_buy_production_scoring`、`test_strategy_24m_duckdb_report`、`test_baseline_board_excludes_non_production_strong_buy`、新增 `test_parallel_scan_parity`、`test_priority_board_query_round_trip_upper_bound`。
- [ ] CI 必须跑全量 `pytest backend/tests`,任一守卫红即拒合入。

### K5-3 性能预算门
- [ ] 增 `scripts/check_perf_budget.py`(若无):跑一次冒烟性能脚本,断言关键端点 p95 不超过基线 ×1.2;突破即报错。
- [ ] 与既有 `verify_go_rust_performance_acceptance.py` 协同。

**K5 验收**:`/metrics` 完整;CI 含守卫与预算门;故意回退即红。

---

## 12. Verification Commands(每批 + 总验收)

```bash
# 每批前后必跑(与 M0 对比)
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
cd backend && .venv/bin/python -c "from app.core.database import ping_database; ping_database(); print('db-ok')"

# Rust 加速验收(K1)
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_rust_finance_math*.py -q
curl -fsS -H "X-Admin-Token: $ADMIN_API_TOKEN" $BASE/metrics | rg "rust_math_|local_quote_cache|provider_|bff_"

# 24M 回测口径冻结(K1/K3 后)
PYTHONPATH=backend backend/.venv/bin/python backend/scripts/run_duckdb_strategy_report.py --output /tmp/report-K.md
diff <(rg "策略|PF|max5|max10|最大回撤" /tmp/report-K.md) <(rg "策略|PF|max5|max10|最大回撤" docs/reports/strategy_24m_duckdb_report.md)
# 关键策略数值必须 1e-9 一致(golden 已在 pytest 守卫里)

# 全市场扫描墙钟对比(K3)
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_parallel_scan_parity.py -q
time PYTHONPATH=backend backend/.venv/bin/python backend/scripts/strategy_24m_backtest_report.py --strategy first_board --months 24

# 总验收
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
cd frontend && npm run api:check && npm run lint && npm test -- --run && npm run build
```

---

## 13. 量化验收门

| 指标 | M0 基线 | 目标 | 来源 |
|---|---|---|---|
| Rust `hits` / 同函数 Python 调用 | 待测 | ≥ 95% | `/metrics rust_math_*` |
| Rust `fallbacks` / `errors` | 待测 | `errors=0`,`fallbacks` 异常突增即告警 | `/metrics` |
| Redis 命中率(market-read) | ~20% | ≥ 90% | Go market-read `/metrics` |
| MySQL 回退次数 | 2494 | ≤ M0 × 0.2 | Go `/metrics` |
| `bff_partial_timeout` | 2 | 0 | 云性能 observability |
| `market_pulse` / `priority_board` p95 | 197 / 160 ms | 显著下降 | 云性能脚本 |
| 全市场扫描墙钟 | 待测 | ≥30% 下降 | `time` 实测 |
| 24M 回测墙钟 | 待测 | ≥30% 下降 | `time` 实测 |
| 关键策略 PF/avg/max5/max10/回撤 | M0 数值 | **1e-9 一致(稳定性核心)** | golden 守卫 |
| 守卫测试 | 全绿 | 全绿 | `pytest backend/tests` |

---

## 14. Rollback

每批独立可回退;无业务语义/数据契约变更:
- **K1**:`rust_finance_math_enabled=False` 全走 Python fallback;按文件 revert 单次替换提交。
- **K2**:G1/G2/G3 各自的开关回退(URL 驱动可切回 PyMySQL;缓存预热集合阈值回退);N+1 修复按文件 revert。
- **K3**:RuntimeTask 并行版可切回 `--workers=1` 串行版;dispatch flag 回退到旧实现。
- **K4**:缓存 disable env var(`indicator_cache_enabled=false`);全走原始计算。
- **K5**:观测/预算门可降级为告警(不阻塞 CI)。

---

## 15. Definition Of Done

- Rust 复用率 ≥95%,fallbacks 接近 0,错误 0;Python fallback 与 Rust parity(1e-9)守卫常驻。
- Redis 命中率 ≥90%、MySQL 回退降 ≥80%、`unresolved=0`、`bff_partial_timeout=0`;关键热端点 p95 显著下降。
- 全市场扫描 + 24M 回测墙钟 ≥30% 下降;并行版 vs 串行版结果 golden 一致(稳定性核心)。
- N+1 修复完成,priority_board / strategy_tracking 查询次数有上界守卫。
- 缓存命中率经 `/metrics` 可见,版本变更触发自动失效。
- `pytest backend/tests` 全绿,口径守卫(production_scoring/24M/lanes/N 字非生产)不回退。
- 未换主框架、未引新语言、未做 async 全量重写;业务语义/口径不变。
- 加速能力默认开启,但 `rust_finance_math_enabled=false` 等回退开关可一键关掉。

---

## 16. 不做清单(避免范围漂移)

- 不改任何策略规则、不动评分公式、不动组合约束、不动门禁阈值。
- 不并行实现 `portfolio_backtest_metrics`(唯一事实源,只在它内部加速)。
- 不引入 Cython/Numba/JAX(与既有 Rust 重叠且不稳定)。
- 不上 async 全量重写;不引 Celery/Kafka/Temporal/K8s 微服务。
- 不为加速而牺牲精度(浮点容差与既有约定一致)。
- 不为加速绕过缺数据降级(`blocked / research_only / no_data / stale` 必须保留)。
- 不引入新 npm/pypi 框架级依赖;仅必要时加 `cachetools` 等成熟轻量库(若已装则复用)。

---

## 17. 优先级与执行节奏(建议)

- **第 1 周**:M0 基线测量(0.5d)+ K1 Rust 复用接入(逐文件,带 golden,4d)
- **第 2 周**:K2 I/O 治理(引用 G1/G2/G3 + 本计划新 N+1 修复)
- **第 3 周**:K3 全市场扫描并行化(分片 + parity 守卫)
- **第 4 周**:K4 缓存治理 + K5 观测与守卫
- **持续**:每批前后跑 `/metrics`、跑性能脚本、跑全量 pytest;不允许"测试红"或"指标回归"的情况下进入下一批。

---

## 18. 风险与处置

| 风险 | 处置 |
|---|---|
| Rust 与 Python fallback 浮点不一致 | parity 测试守 1e-9;不一致先修 Rust 或 fallback,绝不替换业务调用 |
| K3 并行后顺序/合并差异导致 golden 漂移 | 强制 sorted 合并;关键聚合用 `portfolio_backtest_metrics` 单一实现 |
| 缓存陈旧导致策略读到旧值 | 缓存 key 含 `version`;变更必 bump version + 失效 |
| Rust 模块加载失败(镜像/平台问题) | fallbacks 突增即告警;`rust_finance_math_enabled=false` 应急回退 |
| 并行进程间数据不一致 | 进程级隔离;每分片只读;最终聚合走单一引擎 |
| 改动散落引入回归 | 一文件一提交;golden 守卫;CI 全绿才合入 |
| N+1 修复改写大量代码 | 优先批量预取 + 共享上下文(改动小);只在循环热点修 |

---

## 19. 一句话总结

**这套方案的全部增量是"让平台已有的加速能力(Rust 11 函数 / Go 三件套 / DuckDB)真正接到所有热路径 + 修 I/O 与缓存的根因,并用 parity/golden 守卫把策略口径焊死"。** 不换语言、不返工架构、不动业务规则——通过测量先行 + 逐文件替换 + 守卫测试,把计算速度系统性拉起来的同时,**策略稳定性获得比改造前更强的保证**(因为每一个加速路径都有 parity 与 golden 测试盯着)。
