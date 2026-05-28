# TQuant Go/Rust 迁移与止盈止损辅助模型开发方案

日期：2026-05-27

适用项目：`/Users/j/Documents/gupiao`

## 1. 背景与目标

本方案整理当前平台中**适合迁移到 Go 或 Rust 的需求**，并合并“止盈止损辅助模型”的完整落地方案。文档同时明确放弃不适合迁移的策略真源、风控真源和账本语义迁移，避免因为多语言或模型引入造成交易口径漂移。

当前平台已经具备以下边界：

- Go 服务已经作为非策略生产主路径组件：`bff-gateway`、`market-read-service`、`scan-worker`。
- Rust `tquant_rs` 作为 Python 调用的指标加速层。
- 策略、筛选、风控、回测语义、模拟盘决策结果仍以 Python reference 为准。
- 止盈止损现有规则系统仍是生产决策主路径，模型只能作为旁路建议和 Shadow 验证层逐步接入。

本次目标不是“用 Go/Rust 替代 Python”，而是：

1. 让 Go 承担高并发读服务、聚合、缓存、扫描编排和可观测链路。
2. 让 Rust 承担纯数值指标计算热点。
3. 让止盈止损辅助模型先做 Shadow 建议层，长期为动态止盈、保护性减仓和止损参数优化提供证据。
4. 明确放弃高风险迁移项，避免多语言策略漂移和模型绕过风控。
5. 保留 Python 作为策略真源、风控真源、模拟盘账本和回测语义真源。

## 2. 总体边界

| 语言 | 定位 | 可以做 | 不可以做 |
|---|---|---|---|
| Go | 高并发读服务、BFF 聚合、扫描编排、缓存网关、可观测入口 | 批量读、聚合、timeout、partial response、fallback、metrics、traceparent | 独立策略公式、候选排序真源、风控决策、交易决策 |
| Rust | Python 调用的纯数值计算加速层 | ATR、RSI、VWAP、RankIC、rolling、回撤、回测指标、因子指标 | Web 服务、策略结果真源、风控结果真源、模拟盘账本 |
| Python | 策略与交易语义真源 | 策略、回测语义、风控、账本、模拟盘决策、参数治理、研究实验 | 高并发读聚合不应继续无限膨胀 |
| 退出模型 | 规则系统旁路的 Shadow 建议层 | 回吐风险预测、止盈减仓比例建议、移动止盈参数建议、模型效果评估 | 直接下单、取消止损、补仓开仓、修改账本、绕过权限或风控 |

核心原则：

- Go/Rust 启停不得改变策略结果。
- Go/Rust 失败必须 fallback 或返回可观测降级状态。
- 已迁移能力必须有 hit/fallback/error/disabled 指标。
- 所有迁移项必须有 Python reference parity 或字段兼容测试。
- 硬止损、日亏损暂停、最大持仓、自动交易约束永远由规则系统直接执行。
- 止盈止损模型第一阶段只记录建议，不改变真实交易动作。
- 模型失败、特征缺失或置信度不足时必须回退到现有规则系统。

## 3. 适合迁移到 Go 的需求

### 3.1 BFF 聚合主路径

适合迁移内容：

- `monitor` workspace 聚合。
- `paper` workspace 聚合。
- `strategy` workspace 聚合。
- `settings` workspace 聚合。
- `factor` workspace 聚合。

适合原因：

- 页面聚合是高并发 IO 问题，不是策略语义问题。
- Go 更适合并发请求、超时隔离和 partial response。
- 可以将慢子源失败隔离，不拖垮整个页面。

涉及模块：

- `go-services/bff-gateway`
- `backend/app/api/routes/bff.py`
- `backend/app/services/bff/remote_client.py`
- `frontend/src/features/trading-workspace/*`

开发要求：

- Go 响应字段必须兼容 Python BFF。
- 子源请求必须有 timeout。
- 子源失败返回 `partial_errors`，不能白屏。
- Python 保留 fallback。
- metrics 必须包含 aggregate hit、proxy fallback、cache hit、partial source failure。

验收标准：

- Go 启用时，workspace 请求优先命中 Go。
- Go 关闭或失败时，Python BFF 可完整回退。
- 前端页面无字段缺失错误。
- `go test ./...` 通过。
- BFF p95 不高于现有 Python 路径。

### 3.2 行情批量读取服务

适合迁移内容：

- 批量 quote。
- intraday latest batch。
- sector strength。
- key levels。
- market breadth 只读聚合。
- data_quality 聚合。
- ETF quote batch。
- ETF universe 只读查询。

适合原因：

- 行情读取主要是 Redis/MySQL/缓存 IO。
- Go 的连接复用、批量查询、MGET 和超时控制更稳定。
- 可以显著减少 Python 热路径里每个 symbol 单独查询的问题。

涉及模块：

- `go-services/market-read-service`
- `backend/app/services/market/quotes.py`
- `backend/app/services/market/quote_router.py`
- `backend/app/services/market_quote_cache_refresh.py`
- `backend/app/services/sector_etf_t0.py`
- `backend/app/services/etf/universe.py`

开发要求：

- Redis 批量 MGET。
- Redis miss 后 MySQL 批量 fallback。
- 返回每个 symbol 的 `data_quality`。
- 支持 `fresh / stale / partial / unavailable`。
- 不允许直接调用外部慢数据源阻塞热路径。

验收标准：

- 批量请求缺失率可观测。
- Redis hit、MySQL fallback、cache miss 有 metrics。
- 行情源失败时仍返回 partial response。
- 禁止因单个 symbol 缺失导致整批失败。

### 3.3 扫描编排入口

适合迁移内容：

- 全市场扫描任务触发。
- 扫描运行状态。
- 扫描超时控制。
- fallback reason。
- 防止失败污染 latest。
- 扫描任务 metrics。

适合原因：

- 编排和调度适合 Go。
- 策略公式和候选排序仍调用 Python reference。
- Go 可以提供稳定的生产入口和观测面。

涉及模块：

- `go-services/scan-worker`
- `backend/app/services/low_buy/go_scan_worker.py`
- `backend/app/api/routes/internal_scan_worker.py`
- `backend/app/runtime/background_jobs.py`
- `backend/app/services/low_buy_materialization.py`

开发要求：

- 响应必须标注 `strategy_engine=python_reference`。
- 响应必须标注 `scan_worker_role=go_orchestrated_reference`。
- Go 只能触发 Python reference，不独立写策略公式。
- Python reference 成功写入后才允许发布 latest。
- Go 失败时返回 fallback reason。

验收标准：

- Go scan-worker 状态接口可见 `production_scan_enabled=true`。
- Go 编排失败不污染 latest snapshot。
- Python fallback 可用。
- scan accepted、runs、failures、fallbacks 有 metrics。

### 3.4 实时监控读路径

适合迁移内容：

- market pulse 只读聚合。
- 市场宽度读取。
- 龙头强度读取。
- 小时级快照读取。
- 复盘状态读取。
- 监控页面静态/半静态数据聚合。

适合原因：

- 实时监控首屏读多写少。
- 数据源失败时需要 partial response。
- Go 能减少 Python BFF 串行等待。

涉及模块：

- `go-services/bff-gateway`
- `go-services/market-read-service`
- `backend/app/api/routes/market.py`
- `backend/app/services/market/pulse.py`
- `backend/app/services/monitor_snapshot_service.py`
- `frontend/src/features/monitor/MonitorPage.tsx`

开发要求：

- 只读，不重算策略。
- 保留 `data_quality`。
- 缺少部分数据时返回可解释的 `partial_errors`。
- 页面不能白屏。

验收标准：

- `/api/market/pulse` 和 monitor BFF 在 Go 启用时性能达标。
- `fresh/stale/partial/unavailable` 状态前后端一致。
- 日志能定位缺失来源。

### 3.5 ETF 读服务和 ETF 数据质量聚合

适合迁移内容：

- ETF universe 只读查询。
- ETF quote batch。
- ETF RS 读取。
- ETF data_quality 聚合。
- ETF 类型、T+0 能力、流动性约束读取。

适合原因：

- ETF 做T最终决策不迁 Go，但 ETF 数据读取适合 Go。
- ETF 批量读可复用 market-read-service。
- 前端和 Python 策略可共用一个稳定读接口。

涉及模块：

- `go-services/market-read-service`
- `backend/app/services/etf/universe.py`
- `backend/app/services/etf/t0_signal.py`
- `backend/app/services/sector_etf_t0.py`

开发要求：

- Go 只返回 ETF 只读状态，不输出交易决策。
- T+0 能力字段必须来自 Python/DB 配置或静态 universe。
- data_quality 必须逐 ETF 标注。

验收标准：

- ETF 分类、T+0 能力、流动性字段一致。
- Go 读接口关闭后 Python 原路径可用。
- ETF 做T信号决策仍由 Python 执行。

### 3.6 内部服务安全和可观测性

适合迁移内容：

- internal token 校验。
- 生产环境 token 为空拒绝启动。
- `/readyz`、`/metrics`。
- hit/fallback/partial/timeout/cache metrics。
- OpenTelemetry 第一阶段：Go BFF 接收/生成并传播 `traceparent`。

适合原因：

- Go 服务边界清晰。
- 运维诊断需要统一健康和指标。
- BFF 是链路入口，适合先传播 trace。

涉及模块：

- `go-services/bff-gateway/cmd/bff-gateway/main.go`
- `go-services/market-read-service/cmd/market-read-service/main.go`
- `go-services/scan-worker/cmd/scan-worker/main.go`
- `backend/app/main.py`
- `docker-compose.mysql.yml`

开发要求：

- production 环境 token 为空直接启动失败。
- metrics 不泄露 token。
- traceparent 透传到 Python 请求。
- Python 记录同一个 trace header。

验收标准：

- 无 token 的生产配置启动失败。
- 有 token 时服务健康。
- metrics 可用于证明 Go 命中和 fallback。
- traceparent 在 Go/Python 日志中可串联。

## 4. 适合迁移到 Rust 的需求

### 4.1 技术指标计算

适合迁移内容：

- ATR / ATR Wilder。
- RSI / RSI Wilder。
- VWAP。
- rolling mean。
- rolling std。
- max drawdown。
- RankIC。

适合原因：

- 纯数值计算，输入输出明确。
- 易做 Python parity。
- 可被回测、因子实验、ETF 做T、风险归因复用。

涉及模块：

- `rust/tquant-rs`
- `backend/app/services/finance/rust_math.py`
- `backend/app/services/indicators.py`
- `backend/app/services/paper/smart_t_backtest.py`
- `backend/app/services/etf/t0_signal.py`

开发要求：

- 支持空数组、短数组、NaN、None、warmup None。
- Python wrapper 保留 fallback。
- 启用时默认命中 Rust。
- 误差阈值明确。

验收标准：

- Rust 单元测试通过。
- Python parity 测试通过。
- wheel import smoke 通过。
- metrics 显示 hits/fallbacks/errors/disabled。

### 4.2 回测指标计算

适合迁移内容：

- 收益曲线统计。
- 最大回撤。
- Sharpe。
- Calmar。
- Profit Factor。
- 胜率。
- 盈亏比。
- 持仓周期统计。
- 参数网格结果聚合。

适合原因：

- 回测结果指标是纯计算。
- 大量参数组合时 Python 循环成本高。
- Rust 可作为加速内核，不改变策略语义。

涉及模块：

- `backend/app/services/backtest*`
- `backend/app/services/backtest_validation_service.py`
- `backend/app/services/backtest_optimization_service.py`
- `backend/app/services/finance/rust_math.py`
- `rust/tquant-rs`

开发要求：

- Rust 只计算指标，不决定买卖点。
- 回测成交、持仓、止盈止损语义仍在 Python。
- 指标结果必须与 Python reference 一致。

验收标准：

- 同一回测任务启用/关闭 Rust，策略交易明细一致。
- 指标误差在阈值内。
- 大参数网格任务耗时下降。

### 4.3 因子实验室指标

适合迁移内容：

- RankIC。
- ICIR。
- 分组收益。
- 因子分位。
- 因子相关性矩阵。
- rolling IC。

适合原因：

- 因子实验是数组计算密集型。
- Rust 能降低大样本计算耗时。
- Python 保留研究和编排体验。

涉及模块：

- `backend/app/services/factor_mining/*`
- `backend/app/services/finance/rust_math.py`
- `rust/tquant-rs`

开发要求：

- 输入必须清洗 NaN 和缺失值。
- 输出必须包含样本数和有效样本数。
- fallback 可观测。

验收标准：

- 因子实验结果与 Python reference 一致。
- 大样本计算耗时下降。
- 缺失值不会导致崩溃。

### 4.4 ETF 做T指标计算

适合迁移内容：

- 分钟 VWAP。
- 分钟 RSI。
- 布林带。
- ATR。
- 滑点敏感性。
- 参数热力图基础计算。

适合原因：

- ETF 做T依赖分钟级序列，计算频率高。
- Rust 能加速指标，不触碰最终交易决策。

涉及模块：

- `backend/app/services/etf/t0_signal.py`
- `backend/app/services/etf/t0_backtest.py`
- `backend/app/services/paper/smart_t_backtest.py`
- `rust/tquant-rs`

开发要求：

- Rust 输出指标序列，Python 决定是否交易。
- 分钟数据不足时返回 warmup None 或 unavailable。
- 不允许 Rust 直接返回买卖决策。

验收标准：

- ETF 分时指标与 Python 计算一致。
- 数据不足时不生成交易建议。
- 参数热力图可复跑。

### 4.5 风险归因指标

适合迁移内容：

- 波动率。
- beta。
- 相关性。
- 回撤贡献。
- 仓位暴露统计。
- 组合收益分解。

适合原因：

- 属于后验分析和纯统计。
- 不影响实时交易决策。
- 对模拟盘和量化分析页面有性能收益。

涉及模块：

- `backend/app/services/paper/performance.py`
- `backend/app/services/paper/dashboard.py`
- `backend/app/services/strategy_portfolio_optimizer.py`
- `backend/app/services/finance/rust_math.py`

开发要求：

- Rust 只做统计。
- Python 保留归因口径和展示口径。
- 结果带样本数和数据质量。

验收标准：

- 历史 dashboard 指标一致。
- 异常数组不崩溃。
- fallback 可观测。

## 5. 止盈止损辅助模型开发方案

### 5.1 定位与边界

止盈止损辅助模型不是替代现有规则系统，也不是自动交易执行器。它的定位是：

1. 在现有止盈止损、动态退出、智能做T和模拟盘复盘旁边增加一个**旁路建议层**。
2. 用历史持仓、行情、市场状态和执行后结果训练模型，预测“继续持有是否容易回吐”“现在减仓是否更优”“应减多少仓更稳”。
3. 第一阶段只做 Shadow 记录和复盘评估；第二阶段只允许影响保护性止盈参数；第三阶段经过 3-6 个月模拟盘验证后，才评估是否进入更高权限的生产辅助。

不可突破的边界：

- 硬止损永远由规则系统直接触发，模型不能取消、延后或放宽硬止损。
- 日亏损暂停、最大持仓数、单票仓位、自动交易权限、实盘确认机制不能被模型绕过。
- 模型不能直接补仓、开仓、修改账本或写入成交。
- 模型不可用、置信度不足、特征缺失、数据质量非 fresh 时，必须回退到原规则系统。
- 模型输出必须带 `model_version`、`confidence`、`reason`、`feature_snapshot` 和 fallback reason。

### 5.2 推荐技术路线

第一版使用 CPU 表格模型，不上深度学习：

| 阶段 | 模型 | 目标 | 是否需要 GPU | 说明 |
|---|---|---|---|---|
| V1 Shadow | LightGBM / XGBoost / CatBoost 三选一 | 回吐风险、卖出比例、未来收益分桶 | 不需要 | A 股持仓样本是典型结构化表格数据，CPU 足够 |
| V2 模拟盘辅助 | LightGBM + 规则融合 | 调整保护性止盈和分批减仓比例 | 不需要 | 只影响建议和保护性参数，不改变硬止损 |
| V3 研究增强 | 序列模型或 Transformer | 分钟级走势、板块轮动序列特征 | 视情况需要 | 只有当 V1/V2 有稳定收益证据后再评估 |

硬件评估：

- 本地或云端 CPU 训练即可，建议 8 核 CPU、32GB 内存、SSD。
- 10 万到 200 万条样本的 LightGBM/XGBoost 训练通常为数分钟到 1 小时级，取决于特征数量和交叉验证轮数。
- 暂不采购 GPU。若后续进入 V3 序列模型，可评估 RTX 4060 Ti 16GB、T4、A10 或同级云 GPU，预计单次训练从 1 小时到数小时不等。

### 5.3 模型输出

模型输出必须是建议，不是交易指令：

```json
{
  "action": "hold | sell_30 | sell_50 | sell_70 | sell_all",
  "confidence": 0.0,
  "pullback_risk": 0.0,
  "expected_return_next": 0.0,
  "suggested_trailing_stop_pct": 0.0,
  "reason": ["profit_pullback_high", "market_weak", "sector_leader_fading"],
  "model_version": "exit-model-v1",
  "feature_snapshot": {},
  "fallback_reason": null
}
```

动作含义：

- `hold`：继续持有，原规则系统照常生效。
- `sell_30` / `sell_50` / `sell_70`：建议分批止盈或保护性减仓。
- `sell_all`：只作为高风险提示进入 Shadow 或人工确认，不允许绕过硬风控直接成交。

### 5.4 样本与标签定义

训练样本以“持仓在某个交易时点的状态”为一条记录，不能随机打散未来数据。

样本来源：

- 模拟盘持仓、委托、成交、今日动作、动态退出记录。
- 回测持仓明细、历史止盈止损触发点、策略候选排序结果。
- 行情 K 线、分钟线、成交额、量比、VWAP、ATR、RSI、布林带。
- market pulse、市场宽度、情绪温度、龙头强度、板块强度、data_quality。
- ETF 做T记录、ETF 溢折价、T+0 能力、流动性约束。

标签建议：

| 标签 | 类型 | 说明 |
|---|---|---|
| `sell_now_better` | 二分类 | 当前卖出是否优于继续持有 N 个交易窗口 |
| `pullback_risk` | 二分类/概率 | 后续是否从浮盈高点明显回撤 |
| `best_sell_ratio` | 多分类 | 当前更适合卖出 0/30/50/70/100% |
| `next_return_pct` | 回归 | 后续 N 个窗口的收益 |
| `hit_stop_loss_next` | 二分类 | 后续是否触发止损或跌破保护线 |

切分要求：

- 必须按时间切分 train/validation/test，禁止随机切分造成未来函数。
- 至少按牛市、震荡、弱市、极端下跌四类市场状态分组评估。
- 每个策略族单独输出效果：低吸回撤、主线龙头、N 字结构、ETF 做T、防守观察。

### 5.5 特征工程

持仓与收益特征：

- 当前浮盈浮亏、最大浮盈、从高点回吐比例、持仓天数、仓位占比、策略来源、候选优先级。
- 入场价、当前价、成本线、移动止盈线、硬止损线、盈亏比、风险收益比。
- 已执行卖出比例、剩余仓位、是否部分止盈、是否触发过风控提醒。

行情与技术特征：

- ATR、RSI、VWAP、VWAP 偏离、布林带位置、近 N 日涨跌幅、近 N 日成交额变化。
- 最高价回撤、低点抬高、放量滞涨、缩量回踩、突破失败、关键支撑/压力距离。
- Rust 适合承担 ATR、RSI、VWAP、rolling、波动率、回撤等纯数值特征计算。

市场与板块特征：

- market pulse 状态、市场宽度、上涨家数比例、跌停/大跌数量、情绪温度、龙头强度。
- 所属板块强度、板块排名变化、板块龙头是否走弱、市场 data_quality。
- Go 适合提供批量行情读取、板块强度、pulse、data_quality 只读聚合。

风控与账户特征：

- 当日盈亏、连续亏损次数、日亏损暂停状态、总仓位、现金保留比例、单票仓位。
- 账户是否接近最大持仓数、是否已有同板块集中暴露、是否处于风险降档。

ETF 专属特征：

- ETF 类型、T+0 能力、溢折价、成交额、盘口流动性、分钟 VWAP 偏离、分时 RSI。
- ETF 做T信号强弱、网格位置、回撤幅度、流动性降级原因。

### 5.6 决策融合规则

模型只能影响“建议”和“保护性止盈”，不能影响硬止损。

| 场景 | 规则系统 | 模型处理 |
|---|---|---|
| 触发硬止损 | 立即按规则止损 | 只能记录，不可拦截 |
| 触发日亏损暂停 | 禁止新增风险 | 只能记录，不可恢复交易 |
| 数据质量非 fresh | 规则降级或观望 | 模型输出 unavailable |
| 低置信度 | 规则系统原样执行 | 只记录 Shadow |
| 中置信度 | 规则系统原样执行 | 可提示减仓比例和原因 |
| 高置信度且非硬风控场景 | 规则系统仍为准 | 可建议保护性止盈参数收紧 |

建议融合方式：

1. `confidence < 0.55`：只记录，不展示强建议。
2. `0.55 <= confidence < 0.75`：展示“模型提示”，不改变动作。
3. `confidence >= 0.75`：允许进入“保护性止盈建议”，但仍需现有规则、风控和用户确认。
4. 任何模型输出都必须保留 `rule_action`，用于对比规则系统和模型建议。

### 5.7 Shadow 闭环

每次现有规则系统产生持仓检查、今日动作或止盈止损建议时，同步记录：

- `trade_id`、`symbol`、`strategy_key`、`as_of`。
- `rule_action`、`rule_reason`、`rule_sell_ratio`。
- `model_action`、`model_confidence`、`model_reason`、`model_version`。
- 完整 `feature_snapshot`。
- 后续 1 日、3 日、5 日、10 日结果。
- 是否实际触发止损、是否回吐、是否卖早、是否卖晚。

Shadow 报告需要输出：

- 模型建议相比规则系统是否降低回吐。
- 模型建议是否降低最大回撤。
- 模型是否减少亏损扩大。
- 模型是否过早卖飞强势票。
- 分策略、分市场状态、分板块强弱的效果差异。

### 5.8 涉及模块和新增文件

优先复用现有模块：

- `backend/app/services/paper/dynamic_exit.py`
- `backend/app/services/paper/scheduler_exit.py`
- `backend/app/services/paper/performance.py`
- `backend/app/services/paper/smart_t.py`
- `backend/app/services/paper/smart_t_exit.py`
- `backend/app/services/market/*`
- `backend/app/services/etf/*`
- `backend/app/services/finance/rust_math.py`

建议新增模块：

- `backend/app/services/paper/exit_model_schema.py`：模型输入输出 schema。
- `backend/app/services/paper/exit_model_features.py`：持仓、行情、市场、风控特征生成。
- `backend/app/services/paper/exit_model_advisor.py`：模型加载、预测、fallback。
- `backend/app/services/paper/exit_model_shadow.py`：Shadow 记录和后验结果回填。
- `backend/app/services/paper/exit_model_dataset.py`：训练样本和标签生成。
- `research/scripts/train_exit_model.py`：CPU 训练脚本。
- `research/scripts/evaluate_exit_model_shadow.py`：Shadow 效果评估脚本。
- `backend/tests/test_paper_exit_model_features.py`
- `backend/tests/test_paper_exit_model_advisor.py`
- `backend/tests/test_paper_exit_model_shadow.py`

前端展示建议：

- 模拟盘“今日动作”或持仓详情中展示“模型建议 / Shadow 观察”。
- 明确标注“仅建议，不替代止损规则”。
- 实时监控可以只展示汇总风险，不展示单票模型细节，避免和市场复盘主入口混淆。

### 5.9 训练、评估与上线门槛

训练流程：

1. 从模拟盘、回测和行情库抽取样本。
2. 生成特征快照和标签。
3. 按时间切分训练集、验证集、测试集。
4. 训练 LightGBM/XGBoost 模型。
5. 输出模型文件、特征版本、训练配置、评估报告。
6. 只以 Shadow 模式接入服务端。

评估指标：

| 指标 | 目标 |
|---|---|
| 胜率 | 不能低于规则系统同口径结果 |
| Profit Factor | 不能低于规则系统 |
| 平均回吐 | Shadow 阶段目标下降 10% 以上 |
| 最大回撤 | 不能高于规则系统 |
| 卖飞率 | 必须按强势票单独统计并可解释 |
| 止损执行率 | 不能低于规则系统，硬止损不能被拦截 |
| 样本覆盖 | 每个策略族和市场状态都要有分组报告 |

上线门槛：

- Shadow 连续运行至少 3 个月，推荐 6 个月。
- 至少覆盖弱市、震荡和强势轮动三类行情。
- 通过“硬止损不可覆盖”“模型失败可回退”“data_quality 不足不输出强建议”三类强制测试。
- 任何进入实盘接口的可能性必须重新做合规、权限、风控和人工确认评审。

### 5.10 验收标准

- 模型接入后，原止盈止损规则输出不变。
- 硬止损、日亏损暂停、最大持仓、单票仓位规则不被模型覆盖。
- 模型不可用时，服务端返回原规则系统建议并记录 fallback reason。
- Shadow 记录包含规则动作、模型建议、特征快照、模型版本和后验结果。
- 训练脚本可在 CPU 环境完成，并输出可复现的模型和评估报告。
- 测试覆盖特征生成、标签生成、预测 fallback、硬止损不可覆盖、Shadow 记录和效果评估。

## 6. 明确放弃迁移的内容

以下内容不迁移到 Go/Rust，继续保留 Python：

| 放弃迁移对象 | 保留 Python 的原因 |
|---|---|
| 低吸策略核心规则 | 规则复杂、变化快，需要和回测/模拟盘一致 |
| 候选排序真源 | Go 重写易造成口径漂移 |
| 策略评分语义 | 多策略权重、市场状态、板块判断需要统一真源 |
| 风控决策 | 交易安全优先，不能多语言漂移 |
| 模拟盘账本和撮合 | 金额、仓位、订单一致性比性能更重要 |
| 动态止盈止损决策 | 涉及策略语义、持仓状态和风险控制 |
| 回测策略语义 | 必须与生产 Python 策略一致 |
| ETF 做T最终交易决策 | 可以迁指标计算，不能迁交易决策真源 |
| 策略参数治理 | 保持 Python/DB 统一管理 |
| 自动交易执行约束 | 权限、风控、确认机制不迁移 |
| 登录、权限、用户会话 | 当前 FastAPI/Python 已承担完整认证边界 |
| 设置持久化和敏感字段处理 | 涉及安全和一致性，不为性能热点 |
| 模型直接交易执行 | 模型只能做建议和 Shadow 验证，不能替代权限、风控和确认机制 |
| 模型取消或放宽硬止损 | 硬止损是交易安全底线，不能被模型覆盖 |
| 模型补仓、开仓和账本修改 | 涉及真实交易状态和资金一致性，必须保留规则与人工确认边界 |

禁止事项：

- 禁止 Go 独立实现一套策略阈值。
- 禁止 Rust 返回买卖决策。
- 禁止 Go/Rust 启停导致策略结果变化。
- 禁止关闭 Python fallback 后上线新 Go/Rust 链路。
- 禁止把性能优化当成策略收益优化。
- 禁止把模型建议当成交易指令。
- 禁止模型输出覆盖硬止损、日亏损暂停、最大持仓和自动交易权限。

## 7. 分阶段开发路线图

### 阶段一：固化边界和验收

目标：先保证迁移边界清晰，避免策略漂移。

任务：

1. 在 `APP_API_SPEC.md` 中保持 Go/Rust 非策略主路径契约。
2. 为 Go 三服务补齐字段兼容测试。
3. 为 Rust wrapper 补齐 parity 测试。
4. 确认所有 Go/Rust 开关可关闭并回退 Python。

验收：

- Go 三服务 `go test ./...` 通过。
- Rust `cargo test`、wheel smoke、Python parity 通过。
- 关闭 Go/Rust 后主流程可用。

### 阶段二：Go 读服务和 BFF 深化

目标：提升页面和行情读取性能。

任务：

1. 扩展 BFF 聚合 coverage。
2. 优化 market-read-service 批量 quote、intraday latest、sector strength。
3. 补齐 Redis/MySQL 批量 fallback。
4. 增加 data_quality 聚合。
5. 增加 ETF 只读接口。

验收：

- monitor BFF、market pulse、priority board p95 达标。
- Redis hit、MySQL fallback、partial response 可观测。
- 前端页面没有 Go 字段兼容错误。

### 阶段三：Go 扫描编排强化

目标：让扫描入口稳定可观测，但不迁策略真源。

任务：

1. scan-worker 触发 Python reference。
2. 失败时不污染 latest。
3. 暴露扫描状态和 fallback reason。
4. 增加 scan task metrics。

验收：

- 响应标注 `strategy_engine=python_reference`。
- Go 编排失败时 latest 不变化。
- Python fallback 完整可用。

### 阶段四：Rust 指标内核扩大覆盖

目标：把纯计算热点迁到 Rust。

任务：

1. 扩展 rolling std、布林带、波动率、beta、相关性。
2. 接入回测指标计算。
3. 接入因子实验室。
4. 接入 ETF 分时指标。
5. 补齐 benchmark 和 parity。

验收：

- Rust hit 增加，fallback/error 为 0 或可解释。
- 指标误差达标。
- 策略明细不因 Rust 启停变化。

### 阶段五：止盈止损辅助模型 Shadow 层

目标：让模型先形成可验证的建议闭环，不改变现有交易动作。

任务：

1. 定义 exit model schema、特征快照和输出结构。
2. 接入动态退出、今日动作和 ETF 做T的 Shadow 记录点。
3. 生成训练样本、标签和按时间切分的数据集。
4. 实现 CPU LightGBM/XGBoost 训练脚本和评估脚本。
5. 输出规则系统与模型建议的后验对比报告。
6. 在模拟盘详情中展示只读模型建议，并明确“仅建议”。

验收：

- 模型接入后现有规则动作不变。
- 硬止损不可被模型覆盖。
- 模型不可用时原规则系统完整 fallback。
- Shadow 记录可用于 1/3/5/10 日后验评估。

### 阶段六：CI、部署和可观测性

目标：让 Go/Rust 迁移成为可持续工程能力。

任务：

1. CI 增加 Go test。
2. CI 增加 Rust test 和 wheel import smoke。
3. CI 增加 Python parity。
4. CI 增加 exit model schema、fallback、硬止损不可覆盖测试。
5. 部署脚本验证 Go/Rust 容器健康。
6. 线上性能脚本输出 Go/Rust 命中报告。
7. Shadow 报告输出模型建议命中、误判、卖飞和回吐改善指标。

验收：

- PR 自动拦截 Go/Rust 破坏。
- PR 自动拦截模型覆盖硬止损和交易权限。
- 云端 verify-only 包含 Go/Rust 健康。
- 性能报告包含 hits/fallbacks/errors。
- 模型报告包含 rule_action 与 model_action 的对照。

## 8. 测试计划

### Go 测试

```bash
cd go-services/bff-gateway && go test ./...
cd go-services/market-read-service && go test ./...
cd go-services/scan-worker && go test ./...
```

重点断言：

- token 校验。
- readyz。
- metrics。
- partial response。
- fallback reason。
- 字段兼容。
- scan-worker 标注 `python_reference`。

### Rust 测试

```bash
cd rust/tquant-rs && cargo test
```

重点断言：

- 空数组。
- 短数组。
- NaN。
- warmup None。
- ATR/RSI/VWAP/RankIC/rolling/max drawdown 精度。

### Python parity 测试

```bash
backend/.venv/bin/python -m pytest backend/tests/test_*rust* backend/tests/test_*go* -q
```

重点断言：

- Rust/Python 指标一致。
- Go 关闭时 Python fallback 可用。
- Go 启用时命中 Go 且字段兼容。

### 止盈止损辅助模型测试

```bash
backend/.venv/bin/python -m pytest \
  backend/tests/test_paper_exit_model_features.py \
  backend/tests/test_paper_exit_model_advisor.py \
  backend/tests/test_paper_exit_model_shadow.py \
  -q
```

重点断言：

- 特征生成能处理空行情、短数组、NaN、data_quality 非 fresh。
- 标签生成按时间窗口计算，不使用未来特征。
- 模型不可用时 fallback 到现有规则系统。
- 模型低置信度只记录 Shadow，不改变真实动作。
- 硬止损、日亏损暂停、最大持仓、单票仓位不可被模型覆盖。
- Shadow 记录包含 `rule_action`、`model_action`、`feature_snapshot`、`model_version` 和后验结果字段。

### 模型训练和评估 smoke

```bash
backend/.venv/bin/python research/scripts/train_exit_model.py --smoke --output /tmp/tquant-exit-model
backend/.venv/bin/python research/scripts/evaluate_exit_model_shadow.py --smoke --model /tmp/tquant-exit-model
```

重点断言：

- CPU 环境可完成训练 smoke。
- 输出模型文件、特征版本、训练配置和评估报告。
- 评估报告按策略族、市场状态、持仓天数分组。
- 报告能显示回吐改善、卖飞率、止损执行率和 fallback 比例。

### 云端验收

```bash
scripts/quick_cloud_deploy.sh --verify-only --performance-verify \
  --host 43.143.243.97 \
  --user ubuntu \
  --key /Users/j/Downloads/gupiao.pem \
  --port 18090
```

重点断言：

- Go 三服务 healthy。
- `/readyz` OK。
- 前端 OK。
- 受保护 API 返回 401。
- Go/Rust 性能报告 `ok=true`。
- Rust hits > 0，fallbacks/errors 为 0 或有明确原因。
- exit model Shadow 状态可见，且不影响原止盈止损规则。

## 9. 验收指标

| 类型 | 指标 | 目标 |
|---|---|---|
| Go BFF | p95 | 不高于 Python 路径，目标 < 500ms |
| Go market-read | 批量 quote 缺失率 | 可观测，缓存热路径缺失应逐步下降 |
| Go scan-worker | latest 防污染 | 失败不写 latest |
| Go fallback | fallback reason | 必须有结构化原因 |
| Rust parity | 指标误差 | 按指标设阈值，默认接近 Python reference |
| Rust fallback | fallbacks/errors | 正常生产应为 0 或可解释 |
| 启停一致性 | Go/Rust 关闭 | 策略结果不变，系统可用 |
| 可观测性 | metrics/logs | 能证明命中、fallback、partial、error |
| 退出模型边界 | 硬止损保护 | 模型不可取消、延后或放宽硬止损 |
| 退出模型 fallback | 模型不可用 | 返回原规则系统建议并记录 fallback reason |
| 退出模型 Shadow | 记录完整性 | 规则动作、模型建议、特征快照、模型版本、后验结果齐全 |
| 退出模型效果 | 回吐改善 | Shadow 阶段目标平均回吐下降 10% 以上，且最大回撤不高于规则系统 |
| 退出模型风险 | 卖飞率 | 强势票过早卖出必须单独统计并可解释 |
| 退出模型训练 | CPU smoke | 不依赖 GPU，训练和评估 smoke 可复现 |

## 10. 任务拆分

### Go 任务

| ID | 任务 | 文件/模块 | 优先级 |
|---|---|---|---|
| GO-001 | BFF 聚合字段兼容补齐 | `go-services/bff-gateway` | P1 |
| GO-002 | BFF partial source failure 分类 | `go-services/bff-gateway` | P1 |
| GO-003 | market-read Redis MGET 和 MySQL 批量 fallback | `go-services/market-read-service` | P1 |
| GO-004 | intraday latest batch data_quality 聚合 | `go-services/market-read-service` | P1 |
| GO-005 | ETF quote/universe 只读接口 | `go-services/market-read-service` | P2 |
| GO-006 | scan-worker fallback reason 和 latest 防污染测试 | `go-services/scan-worker` | P1 |
| GO-007 | traceparent 传播 | `go-services/bff-gateway`、Python middleware | P2 |
| GO-008 | Go metrics 告警字段规范化 | 三个 Go 服务 | P2 |

### Rust 任务

| ID | 任务 | 文件/模块 | 优先级 |
|---|---|---|---|
| RS-001 | rolling std / volatility / beta / correlation | `rust/tquant-rs` | P1 |
| RS-002 | 布林带指标 | `rust/tquant-rs` | P1 |
| RS-003 | 回测指标加速 wrapper | `backend/app/services/finance/rust_math.py` | P1 |
| RS-004 | 因子实验 RankIC/ICIR 加速 | `factor_mining` + Rust wrapper | P2 |
| RS-005 | ETF 分时指标加速 | `backend/app/services/etf/*` | P2 |
| RS-006 | benchmark gate | `scripts/check_rust_bench_baseline.py` | P2 |
| RS-007 | wheel 发布 smoke | Dockerfile / CI | P1 |

### Python 保留与接入任务

| ID | 任务 | 文件/模块 | 优先级 |
|---|---|---|---|
| PY-001 | 保持策略真源为 Python reference | `backend/app/services/low_buy/*` | P0 |
| PY-002 | Go scan-worker 调用 Python reference | `backend/app/api/routes/internal_scan_worker.py` | P0 |
| PY-003 | Rust wrapper fallback 和 metrics | `backend/app/services/finance/rust_math.py` | P0 |
| PY-004 | Go/Rust 开关回滚 | `backend/app/core/config.py` | P0 |
| PY-005 | 字段兼容测试 | backend tests | P1 |
| PY-006 | 退出模型接入点只做 Shadow，不改规则动作 | `backend/app/services/paper/*exit*` | P0 |

### 止盈止损辅助模型任务

| ID | 任务 | 文件/模块 | 优先级 |
|---|---|---|---|
| ML-001 | 定义模型输入输出 schema 和 fallback 状态 | `backend/app/services/paper/exit_model_schema.py` | P0 |
| ML-002 | 构建持仓、行情、市场、风控、ETF 特征快照 | `backend/app/services/paper/exit_model_features.py` | P0 |
| ML-003 | 在动态退出和今日动作流程记录 Shadow 建议 | `backend/app/services/paper/exit_model_shadow.py` | P0 |
| ML-004 | 模型加载、预测、低置信度降级和不可用 fallback | `backend/app/services/paper/exit_model_advisor.py` | P0 |
| ML-005 | 训练样本、标签生成和时间切分 | `backend/app/services/paper/exit_model_dataset.py` | P1 |
| ML-006 | CPU LightGBM/XGBoost 训练脚本 | `research/scripts/train_exit_model.py` | P1 |
| ML-007 | Shadow 后验评估报告 | `research/scripts/evaluate_exit_model_shadow.py` | P1 |
| ML-008 | 模拟盘只读展示模型建议和 Shadow 状态 | `frontend/src/features/paper/*` | P2 |
| ML-009 | 硬止损不可覆盖、fallback、Shadow 记录测试 | `backend/tests/test_paper_exit_model_*.py` | P0 |
| ML-010 | 训练配置、模型版本和特征版本审计 | `docs/model-governance/*` 或 `backend/app/services/paper/*` | P2 |

## 11. 风险与控制

| 风险 | 表现 | 控制措施 |
|---|---|---|
| 策略漂移 | Go/Rust 启用后候选、排序、交易结果变化 | 禁止迁移策略真源；只迁读服务和指标 |
| 多语言维护成本上升 | Python/Go/Rust 三套代码边界不清 | 文档和测试固定边界 |
| fallback 不可见 | 服务降级被当成正常结果 | metrics/logs 必须记录 fallback reason |
| Rust wheel 构建失败 | 镜像缺包或运行时现编译 | wheel 作为发布产物，CI smoke |
| Go 服务安全漏配 | token 为空也可访问 | production token 为空拒绝启动 |
| 数据质量误判 | stale 数据生成交易建议 | data_quality 非 fresh 禁止关键交易建议 |
| 模型覆盖风控 | 模型建议取消硬止损或放宽风险线 | 代码层强制硬止损优先，测试断言不可覆盖 |
| 模型过拟合 | 训练集表现好，实盘 Shadow 误判多 | 按时间切分、按市场状态分组、至少 3-6 个月 Shadow |
| 未来函数 | 标签或特征使用未来行情 | 特征生成和标签生成分层测试，禁止随机切分 |
| 卖飞强势票 | 模型过早建议止盈龙头或趋势票 | 强势票卖飞率单独统计，高置信建议仍需规则确认 |
| 模型不可解释 | 用户不知道为什么建议卖出 | 输出 reason、feature_snapshot、confidence 和模型版本 |
| 模型依赖失效 | 模型文件缺失、版本不匹配、特征缺失 | advisor fallback 到规则系统并记录 fallback reason |

## 12. 最终结论

本项目后续迁移和模型增强只保留三类方向：

1. **Go：高并发读服务 + 编排 + 缓存 + 可观测。**
2. **Rust：纯数值指标计算。**
3. **止盈止损辅助模型：CPU 表格模型 + Shadow 建议 + 规则系统融合。**

其余与策略语义、风控决策、模拟盘账本、回测语义、自动交易约束相关的 Go/Rust 迁移全部放弃，继续保留 Python reference。模型也不能替代 Python reference，只能在规则系统旁边提供可观测、可回测、可回退的止盈止损辅助建议。

这是当前平台风险最低、收益最高、最容易验收和回滚的工程演进路线：Go 提升读服务和编排，Rust 提升指标计算，退出模型在不破坏硬风控的前提下逐步验证收益改善。
