# Backend Compute Acceleration 可确定落地范围分析

状态：可执行范围审查  
适用范围：`docs/superpowers/plans/2026-06-03-backend-compute-acceleration-final.md` 的实施拆分  
最后核验日期：2026-06-03  
结论：计划方向与当前工程基本匹配，但不能把所有批次都视为同等确定。当前可确定落地的是“已有加速栈接线、I/O/缓存治理、N+1 守卫、观测与预算门”；“全市场扫描并行化、24M 回测并行化”可作为后续专项，但必须先做 parity spike 和基线测量后再进入开发。

## 事实基线

- Rust 侧已有 11 个 finance pyfunction：`rust/tquant-rs/src/finance_core.rs` 与 `rust/tquant-rs/src/lib.rs` 覆盖 `rolling_mean`、`rolling_std`、`ATR`、`RSI`、`VWAP`、`Bollinger`、`beta`、`correlation`、`rank_ic`、`max_drawdown`、`volatility`。
- Python 侧已有 Rust 适配层：`backend/app/services/finance/rust_math.py` 暴露 `rust_*` wrapper，并已有 `hits/fallbacks/errors/disabled` metrics。
- Rust 已部分接入业务路径：`backend/app/services/indicators.py` 使用 ATR/RSI/Bollinger/VWAP；`backend/app/services/finance/performance_math.py` 使用 max drawdown；`backend/app/services/factor_mining/evaluation.py` 使用 rank IC。
- Rust parity 测试已有基础：`backend/tests/test_finance_performance_math.py` 已覆盖 fake Rust module 与 Python reference 的一致性，但还不是按每个热路径文件的 golden 测试。
- Go market-read 与 BFF adapter 已存在：`backend/app/services/market/go_read_client.py`、`backend/app/services/bff/remote_adapters.py`，并保留失败回退。
- 行情缓存覆盖治理已有明显落地基础：`backend/app/services/market_quote_cache_refresh.py` 已把自选、优先榜、纸面持仓、热门板块成员纳入 core demand，默认 `DEFAULT_LIMIT=1200`，并记录覆盖率。
- `/metrics` 已暴露 HTTP p95、BFF remote/cache、provider、local quote cache、Rust math 等指标：`backend/app/main.py`。
- MySQL driver 偏好 mysqlclient 的兼容层已存在：`backend/app/core/database_url.py`，测试在 `backend/tests/test_database_url_driver.py`。
- RuntimeTask DB 队列与 worker 已存在：`backend/app/services/tasks/queue.py`、`backend/app/services/tasks/worker.py`、`backend/scripts/analytics_worker.py`。
- 组合回测唯一事实源已存在：`backend/scripts/low_buy_market_backtest_reporting.py` 的 `portfolio_backtest_metrics`。

## 可以确定落地的事项

### P0-1 M0 基线测量与口径冻结

可以确定落地。原因是计划要求的观测面已有代码锚点，且不会改变业务语义。

落地内容：
- 增加或整理一份基线报告，记录 `/metrics` 中 `tquant_rust_math_*`、`tquant_local_quote_cache_*`、`tquant_bff_*`、`tquant_provider_*`。
- 记录 `monitor_bff`、`market_pulse`、`priority_board`、全市场扫描、24M 报告的当前墙钟或 p95。
- 固化关键策略口径基线：PF、平均单笔、max5、max10、最大回撤。

验收：
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q`
- 生成 `docs/reports/backend-compute-acceleration-baseline-2026-06-03.md` 或同类人读报告。

### P0-2 Rust 适配层补齐为统一 API

可以确定落地。Rust wrapper 已存在，但当前是 `rust_*` 低层接口；计划中的统一 `rolling_mean(values, window)`、`atr(...)`、`vwap(...)` 等可在 `finance/rust_math.py` 内增量补齐，不需要引入新语言或新框架。

落地内容：
- 在 `backend/app/services/finance/rust_math.py` 中补统一高层函数，内部按 `rust_finance_math_enabled` 选择 Rust 或 Python fallback。
- 保留现有 `rust_*` wrapper，避免破坏已接入调用方。
- 补 `metrics_snapshot` 维度或复用现有 `rust_math_metrics_snapshot()`。
- 明确 fallback 规则：Rust 不可用、输入非法、开关关闭时走 Python reference。

验收：
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_finance_performance_math.py -q`
- 新增 parity 用例覆盖每个统一 API。

### P0-3 Rust 热路径逐项接入与 golden 守卫

可以确定落地，但必须按文件逐项做，不能一次性大批量替换。

优先可落地路径：
- `backend/app/services/low_buy/atr_metrics.py`：ATR 已有 Rust wrapper 和指标函数，可优先接入。
- `backend/app/services/low_buy/history_frames.py`、`backend/scripts/low_buy_market_backtest_outcomes.py`：滚动均线目前使用 pandas rolling，可先做小范围 parity spike，再替换高频路径。
- `backend/app/services/low_buy/main_force_model_features.py`：均线、波动类派生指标可接统一 Rust/Python API，但要先写 golden。
- `backend/app/services/analytics/report_queries.py`、`backend/app/services/backtest/analyzer.py`：max drawdown 已有 `sequence_max_drawdown_pct` 路径，优先做复用检查和测试补强，不重复实现。
- `backend/app/services/factor_mining/evaluation.py`：rank IC 已接 Rust，可补 metrics 与 parity 守卫。

验收：
- 每个替换文件先建立旧输出 golden，再替换实现。
- 数值容差按计划控制在 `1e-9` 或既有测试约定。
- `rust_finance_math_enabled=False` 时结果与开启一致。

### P0-4 mysqlclient 优先与 PyMySQL fallback 继续完善

可以确定落地，而且当前已有大部分实现。

现状证据：
- `backend/requirements.txt` 已含 `mysqlclient>=2.2,<3.0` 和 `pymysql>=1.1,<2.0`。
- `backend/app/core/database_url.py` 已实现 MySQL URL driver 自动切换。
- `backend/tests/test_database_url_driver.py` 已覆盖 mysqlclient 优先、缺失时回退 PyMySQL、部署模板默认 mysqldb。

后续可落地内容：
- 复核部署脚本和 compose 中的系统库安装、环境变量与测试是否全部一致。
- 增加一条运行时日志或 readiness 输出，明确实际使用的 driver。

验收：
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_database_url_driver.py -q`

### P0-5 行情缓存覆盖治理

可以确定落地。当前实现已经不是计划中旧的 `DEFAULT_LIMIT=200`，而是 `DEFAULT_LIMIT=1200`，并已纳入多类核心需求。

已落地基础：
- `_core_demand_symbols()` 包含自选、优先榜、纸面持仓、监控板块成员。
- `record_quote_cache_demand_coverage()` 已记录 demand、miss、coverage ratio。
- `/metrics` 已输出本地行情缓存读写、命中、miss、coverage 等指标。
- `backend/tests/test_market_quote_cache_refresh.py` 已覆盖 core demand 优先与 coverage alert。

后续可确定落地内容：
- 增加“实际热查询符号集合”的覆盖对账报告，确认 demand 是否还漏掉策略追踪、ETF 或其他高频页面。
- 把 coverage 低于 90% 的原因写入报告和告警样例。

验收：
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_market_quote_cache_refresh.py -q`
- `/metrics` 可见 `tquant_local_quote_cache_coverage_ratio_bps`。

### P0-6 N+1 查询上界守卫与小范围批量预取

可以确定落地。计划中点名的 `priority_items.py` 和 `strategy_tracking.py` 已有明确热点，但现状不是完全未治理，尤其 `strategy_tracking.py` 已有批量拉取 bars、lifecycles、instruments 的实现。

落地内容：
- 对 `backend/app/services/low_buy/priority_items.py` 增加查询次数上界测试，重点围绕 `_build_priority_item()` 中 `score_low_buy_candidate_for_production()`、`main_force_rank_bonus()` 等可能间接访问上下文的位置。
- 对 `backend/app/services/strategy_tracking.py` 增加查询次数上界测试，保护 `_build_summary_items()` 的批量 bars、lifecycles、instruments 行为。
- 如测试暴露 N+1，再做批量预取和共享上下文传参。

验收：
- 新增 `backend/tests/test_priority_board_query_budget.py` 或同类测试。
- 新增 `backend/tests/test_strategy_tracking_query_budget.py` 或同类测试。
- 同输入输出 golden 一致，DB 往返次数有明确上界。

### P0-7 `/metrics` 观测面补强

可以确定落地。现有 `/metrics` 已覆盖大部分计划项，增量风险低。

可落地内容：
- 保留并核验 `tquant_rust_math_hits_total`、`fallbacks_total`、`errors_total`、`disabled_total`。
- 补派生指标缓存命中率、worker task duration p95、可选 N+1 估算值。
- 不把告警逻辑直接耦合进业务路径，先作为指标暴露。

验收：
- `backend/tests/test_performance_regression.py` 或新增 metrics 测试中断言新增指标存在。
- `curl /metrics | rg "tquant_rust_math_|tquant_local_quote_cache_|tquant_bff_"` 可查。

### P0-8 口径守卫测试常驻

可以确定落地。该项主要是“防回退”，不要求大改业务。

落地内容：
- 保留并扩展 Rust parity、生产评分、24M DuckDB 报告、组合执行唯一口径等守卫。
- 新增“禁止并行实现 `portfolio_backtest_metrics`”的轻量静态或单元测试，确保报告、paper 预览、决策上下文继续复用同一口径。

验收：
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_finance_performance_math.py backend/tests/test_low_buy_backtest_isolation.py backend/tests/test_decision_context_portfolio_executor.py -q`

### P1-1 Go market-read / BFF fallback parity 冒烟

可以确定落地，但目标应是“冒烟和覆盖补齐”，不是强行改所有 Python 直查路径。

落地内容：
- 为 `backend/app/services/market/go_read_client.py` 补 schema mismatch、Go 超时、空 payload、部分缺 symbol 的 fallback 测试。
- 为 `backend/app/services/bff/remote_adapters.py` 补远程 BFF 成功、失败、schema mismatch 触发 circuit 的测试。
- 增加 `fallback_available=true` 或等价运行状态输出时，确保 Python fallback 字段与 Go 字段一致。

验收：
- 定向 pytest 覆盖 Go adapter 和 BFF adapter。

### P1-2 派生指标缓存治理

可以确定落地，但应从局部、只读、纯函数派生指标开始，不一次性铺满全仓。

优先对象：
- 均线、ATR、滚动分位、板块强度、相对强度这类 `(symbol, trade_date, params_hash, version)` 可稳定定位的只读指标。

落地规则：
- 缓存 key 必须包含 `indicator_version`。
- 缓存必须可关闭。
- 不缓存可写、有状态、依赖当前时间变化的对象。
- 优先使用现有依赖；如果 `cachetools` 已在环境中存在可复用，若未声明则不要在本轮新增框架级依赖。

验收：
- 二次调用命中缓存。
- version 改变强制 miss。
- `/metrics` 暴露 hits/misses/size。

### P1-3 性能预算门与巡检脚本

可以确定落地，但初期应做“烟测预算门”，不要直接把不稳定云端 p95 做成强阻塞。

落地内容：
- 新增或复用性能脚本，比较关键端点 p95 与基线。
- 初期把预算门用于本地 smoke 或 CI 可选步骤；基线稳定后再改成强阻塞。
- 与 `verify_go_rust_performance_acceptance.py` 或现有云性能脚本协同，避免重复。

验收：
- 脚本能读取基线、输出 pass/fail 与超限端点。
- 报告写明是否阻塞 CI。

## 暂不建议直接承诺落地的事项

### K3 全市场扫描并行化

方向可行，但不能列为“当前可以确定直接落地”。原因：
- RuntimeTask worker 已有，但计划中的 `(strategy, symbol_bucket)` 分片、合并顺序、取消、超时、partial 标记尚无明确现成实现。
- 全市场扫描涉及策略排序、物化结果、生产准入，任何并行合并差异都可能造成口径漂移。

建议处理：
- 先做 P0 spike：单策略、固定小 symbol 集、串行 vs 并行 golden 完全一致。
- spike 通过后再立专项计划。

### 24M 回测并行化

方向可行，但必须后置。原因：
- `portfolio_backtest_metrics` 是唯一事实源，月度分片后再聚合很容易破坏 max5/max10、同票冷却、同板块约束等跨时间约束。
- 只有当并行方案仍在唯一事实源内部或只并行安全的前置数据准备时，才可落地。

建议处理：
- 优先并行数据准备，不并行组合规则。
- 对 PF、平均单笔、max5、max10、最大回撤做 golden 后再推进。

### async SQLAlchemy / 全量 async 改造

计划已明确排除，当前也不应落地。

### Go/Rust 重写业务

计划已明确排除，当前也不应落地。只允许把已有 Rust/Go 加速能力接入热路径。

## 推荐最终落地顺序

1. P0 基线测量与报告。
2. Rust 统一 API + parity 测试补齐。
3. Rust 热路径逐文件接入：先 ATR/RSI/Bollinger/VWAP/max drawdown/rank IC 已有附近路径，再推进 rolling mean/std。
4. mysqlclient/部署 driver 复核。
5. 行情缓存覆盖对账与缺口补齐。
6. priority board / strategy tracking 查询上界测试，发现问题后小范围批量预取。
7. `/metrics` 增补缓存、worker、fallback 比例指标。
8. Go/BFF fallback parity 冒烟。
9. 派生指标缓存局部试点。
10. 性能预算门先烟测，稳定后再 CI 强阻塞。
11. K3/K24M 并行只做 spike，通过后另起专项。

## 建议新开发计划拆分

### Batch A：测量与守卫

- 产出基线报告。
- 固化 Rust parity、组合口径、生产准入、缓存覆盖、查询次数上界测试。
- 不改业务算法。

### Batch B：Rust 复用接线

- 统一 `finance/rust_math.py` API。
- 逐文件替换热路径。
- 每个文件附 golden 测试。

### Batch C：I/O 与缓存覆盖

- 复核 mysqlclient 默认与 fallback。
- 补行情缓存 demand 缺口。
- 补 Go/BFF fallback parity 冒烟。

### Batch D：观测与预算

- `/metrics` 补缓存、worker、fallback 比例。
- 增性能预算烟测脚本。

### Batch E：并行化 spike

- 只做小样本串并行 parity。
- 不进入生产路径，不改 24M 报告事实源。

## 本轮不应进入实施范围

- 不改策略规则、评分公式、组合约束、生产门禁。
- 不新建第二套组合回测实现。
- 不全量 async 重写。
- 不引入 Celery/Kafka/Temporal/K8s。
- 不引入 Cython/Numba/JAX。
- 不把 Web 请求线程接入外部行情源或新增 Web 后台 loop。
- 不把 K3/K24M 并行作为无 spike 的确定性交付。

