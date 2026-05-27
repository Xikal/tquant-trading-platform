# TQuant 后端重构最终实施方案：Python 稳定基本盘 + Go/Rust 定点增强

生成日期：2026-05-22
适用范围：TQuant 后端、BFF、任务队列、行情读取、全市场扫描、回测与指标计算

> 状态更新（2026-05-27）：本文记录 2026-05-22 的分阶段引入方案，其中 “shadow / 默认关闭” 是历史过渡口径。当前有效口径以 `APP_API_SPEC.md`、`PRODUCTION_RUNBOOK.md` 和 `docs/backend-refactor-runtime-runbook-2026-05-22.md` 为准：Go BFF / market-read-service / scan-worker 已作为非策略生产主路径组件治理；策略、筛选、风控、回测、模拟盘决策仍只依赖 Python reference；Rust `tquant_rs` 是 Python 调用的指标加速层，不作为策略真源。

依据报告：

- `/Users/j/Downloads/TQuant_后端重构技术选型全面审查报告.html`
- `/Users/j/Downloads/TQuant_后端全方位深度审查报告.html`
- 当前项目结构：`FastAPI + SQLAlchemy + Alembic + MySQL + Redis + runtime-worker + backtest-worker + BFF`

## 1. 最终裁定

TQuant 后端需要重构，但不应该做全量重写，也不应该一次性微服务化。

最终技术路线：

| 层级 | 技术 | 裁定 | 作用 |
|---|---|---|---|
| 核心业务 | Python / FastAPI | 保留 | 策略、回测、ML、因子挖掘、模拟盘账本、权限、参数治理 |
| 高并发读聚合 | Go | 分阶段引入 | BFF 聚合、行情快照读取、全市场扫描 Worker |
| 高性能计算 | Rust / PyO3 | 条件引入 | ATR、RSI、VWAP、滚动窗口、最大回撤、RankIC 等计算内核 |
| 数据库 | MySQL + Redis | 保留并加固 | MySQL 做交易与配置主库，Redis 做缓存、限流、锁、队列事件 |
| 时序库 | InfluxDB / TDengine | 暂不立即引入 | 仅当分钟级数据规模真实成为瓶颈后再做双写迁移 |
| 大型微服务 | Java / Node / C++ | 不引入 | 当前收益低，复杂度高 |

核心原则：

- 先修稳定性和数据库基本盘，再引入 Go/Rust。
- Go 解决吞吐，不承接复杂策略真源。
- Rust 解决计算，不承接 Web/API/账本。
- Python 继续作为策略语义、回测、ML 和账本一致性的主系统。
- 所有新服务先影子模式，验证通过后再切生产。

## 2. 当前后端真实问题分级

### P0：必须先修的基础稳定问题

| 编号 | 问题 | 最终处理 |
|---|---|---|
| P0-1 | 后台任务仍有线程循环、重复执行、无统一队列风险 | 新任务全部进入统一 RuntimeTaskQueue；历史线程任务逐步迁移；不立即全量换 ARQ |
| P0-2 | BFF workspace 串行查询、慢时拖垮请求 | 加 Redis 短缓存、整体超时、partial response、后续 Go BFF 承接 |
| P0-3 | 数据库连接池、MySQL/Redis 生产参数不足 | 连接池参数配置化，MySQL/Redis 参数通过 compose/env 控制 |
| P0-4 | 全局请求追踪不足 | 引入统一 Request-ID，日志和内部调用透传 |
| P0-5 | 全局异常返回可能暴露内部错误 | 统一异常处理，前端只返回 request_id 和简洁错误 |

### P1：影响性能和长期维护的问题

| 编号 | 问题 | 最终处理 |
|---|---|---|
| P1-1 | 全市场低吸扫描耗时长 | Go scan worker 影子模式，不直接替换 Python |
| P1-2 | 行情读取重复、页面等待慢 | Go market read service 只读 Redis/MySQL 快照 |
| P1-3 | 回测加载全市场数据占内存 | Python 先做分块/流式读取，后续再评估 Go/Rust 加速 |
| P1-4 | SQLAlchemy N+1 风险 | Paper、BFF、回测查询路径优先加 selectinload / 批量查询 |
| P1-5 | API 缺版本治理 | 新接口走 `/api/v2` 或 `/bff/v1`，旧接口兼容保留 |

### P2：中期演进问题

| 编号 | 问题 | 最终处理 |
|---|---|---|
| P2-1 | MinuteBar 长期 MySQL 单表膨胀 | 先做分区和归档，达到阈值后再引入 InfluxDB |
| P2-2 | OHLCV Float 精度问题 | 新链路优先 Decimal/Numeric，历史字段迁移需单独维护窗口 |
| P2-3 | Repository 模式不完整 | 先拆 Paper、Backtest、Market 热路径，不做全项目机械迁移 |
| P2-4 | OpenTelemetry / Grafana 不完整 | 先补 metrics 和结构化日志，再接完整 tracing |
| P2-5 | God Class 残留 | 只拆高风险文件，不做扫荡式重构 |

## 3. 不直接采纳的过度方案

以下建议有价值，但不作为当前立即落地项：

| 建议 | 不立即做的原因 | 替代方案 |
|---|---|---|
| 全量 ARQ 替换所有后台任务 | 当前已有 RuntimeTaskQueue 与 worker，全部替换风险大 | 新任务统一进 RuntimeTaskQueue，历史线程逐步迁移 |
| 立即 MySQL 主从读写分离 | 单机/小规模阶段运维复杂度高 | 先做缓存、索引、慢查询、只读查询规范 |
| 立即 InfluxDB 迁移 MinuteBar | 数据双写、校验、运维成本高 | 先 MySQL 分区和归档，达到阈值再双写 |
| 全量 Float→Numeric 迁移 | 表结构风险大，迁移窗口长 | 新写入路径和核心计算先 Decimal 化，历史表分批迁移 |
| Go 全量替换 FastAPI | 策略/ML/账本语义复杂，重写风险不可控 | Go 只做 BFF、读服务、扫描 Worker |
| Rust Web 服务 | 团队维护成本高，收益不明确 | Rust 只做 PyO3 计算内核 |
| 全面微服务化 | 当前核心问题不是服务数量不足 | 先 BFF seam + 领域模块边界 |

## 4. 目标后端架构

```text
Web / App
  ↓
Python FastAPI /api + /bff/v1
  ↓ 可配置远端适配
Go BFF Gateway
  ↓
Python Core Services
  - Auth / Settings / Paper Ledger
  - LowBuy Strategy / Backtest / ML
  - Factor Mining / Governance
  ↓
Go Market Read Service
  - Quote batch
  - Sector relative strength
  - Intraday key levels
  - Snapshot read cache
  ↓
Go Scan Worker
  - Shadow scan
  - Ranking acceleration
  - Snapshot write after parity
  ↓
Rust PyO3 tquant-rs
  - ATR / RSI / VWAP / rolling / max drawdown
  ↓
MySQL + Redis
```

## 5. 分阶段实施路线

### Phase 0：Python 基本盘加固，1-2 周

目标：不引入新语言，先把当前系统稳定性补齐。

实施项：

- DB 连接池参数配置化：`db_pool_size`、`db_max_overflow`、`db_pool_timeout`、`db_pool_recycle`。
- MySQL compose 增加 InnoDB 参数、慢查询日志、连接数参数。
- Redis compose 增加 AOF/RDB 持久化策略。
- 全局异常处理：客户端不返回 traceback。
- Request-ID middleware：所有 API、BFF、内部服务调用透传。
- Gzip middleware：压缩大 JSON 响应。
- BFF workspace 统一超时：超时返回 partial response。
- BFF workspace Redis 短缓存：monitor/paper/settings/strategy 分别配置 TTL。
- 后台任务入口收口：Web 进程不得直接跑全量扫描，统一入队。

验收：

- `make qa` 或等效后端测试通过。
- `/healthz`、`/readyz` 正常。
- BFF 超时返回结构稳定，不白屏。
- 大响应包含 gzip。
- 日志里能按 request_id 查完整链路。

### Phase 1：Go BFF 只读聚合，4-6 周

目标：用 Go 承接高并发读聚合，但前端路径不变。

实施项：

- 新建 `go-services/bff-gateway`。
- 提供 `/healthz`、`/readyz`、`/metrics`。
- 支持 `X-Internal-Service-Token` 和 `X-Request-ID`。
- 首批实现 workspace：
  - `/workspace/monitor`
  - `/workspace/settings`
- Python BFF 通过现有 remote adapter seam 调 Go。
- Go BFF 仅聚合只读数据，不写数据库。
- 增加 contract parity test：Go 响应与 Python 响应字段兼容。

不做：

- 不把登录、权限、模拟下单迁到 Go。
- 不让前端直接依赖 Go 服务。
- 不改现有 `/api/bff/v1` 前端调用路径。

验收：

- Go BFF shadow 模式可开关。
- Python/Go 同一用户、同一输入响应结构兼容。
- P95 目标先降到 `<800ms`，缓存稳定后 `<500ms`。
- 关闭 Go 开关后完全回退 Python。

### Phase 2：Go Market Read Service，6-10 周

目标：解决实时监控、全策略优先榜、选股宝典的数据读取慢和重复请求。

实施项：

- 新建 `go-services/market-read-service`。
- 只读 Redis/MySQL 快照，不直接写业务结果。
- 提供批量接口：
  - quote batch
  - intraday latest batch
  - sector relative strength
  - key levels snapshot
- Python Provider 继续负责外部数据采集。
- Go service 只做本地快照读取、聚合、轻量计算。
- 返回 data_quality：`fresh / stale / partial / unavailable`。

验收：

- 500-1000 个 symbol 批量读取稳定。
- 外部行情源失败时不拖垮页面。
- 监控页价格刷新不触发重复全量扫描。
- App/Web 展示字段一致。

### Phase 3：Go Scan Worker 影子模式，8-12 周

目标：加速全市场策略扫描，但不破坏策略语义。

实施项：

- 新建 `go-services/scan-worker`。
- 读取参数版本、物化日线、板块快照和候选池。
- 实现纯计算评分和排序。
- Go 结果写入 shadow snapshot。
- 每日与 Python LowBuy 结果做 diff。
- 通过后才允许写生产 snapshot。

约束：

- 策略公式仍以 Python/参数系统为真源。
- Go 不能手写一套不可追踪的策略阈值。
- 新策略必须先在 Python 回测和生产影子验证。

验收：

- 候选池一致率 `>=99.5%`。
- Top 100 排名相关性达标。
- 全市场扫描目标 `<90s`，稳定后 `<60s`。
- 连续 10 个交易日 shadow 对比通过后才可切生产。

### Phase 4：Rust PyO3 计算内核，按 Profiling 触发

目标：只加速确定的 CPU 热点。

实施项：

- 新建 `rust/tquant-rs`。
- 提供 PyO3 模块给 Python 调用。
- 首批函数：
  - ATR Wilder
  - RSI Wilder
  - VWAP 日内重置
  - rolling mean/std/max/min
  - max drawdown
  - RankIC batch
- Python 保留 reference implementation。
- feature flag 控制启用 Rust。

触发条件：

- Profiling 证明指标计算占 CPU `>20%`。
- Go scan 后仍被指标计算拖慢。
- Rust benchmark 至少比 Python 快 `5x`。

验收：

- Rust 与 Python reference 误差 `<1e-8`。
- 任一 Rust 调用失败自动 fallback Python。
- 不改变策略信号语义。

### Phase 5：时序存储升级，条件触发

目标：当分钟级数据规模真实达到瓶颈时，再引入时序库。

触发条件：

- `minute_bar_snapshots` 单表超过 3000 万行。
- 分钟级查询 P95 超过 2 秒。
- MySQL 分区与索引优化后仍不能满足回测/盘中分析。

实施项：

- Phase 5A：MySQL 月分区和归档。
- Phase 5B：InfluxDB/TDengine 双写。
- Phase 5C：回测/分时读取切时序库。
- Phase 5D：MySQL MinuteBar 降为备份或归档。

## 6. 数据库整改策略

### 6.1 近期必须做

- 连接池参数配置化。
- MySQL 慢查询日志打开。
- Redis AOF/RDB 参数补齐。
- 高频查询补索引：
  - `daily_bar_snapshots(symbol, trade_date)`
  - `operation_audit_log(action, created_at)`
  - `ml_signal_samples(strategy_key, signal_date, outcome)`
  - `paper_position_lots(account_id, available_date, remaining)`
  - `factor_eval_results(factor_key, status, created_at)`
- 大批量 upsert 使用批量写入，不再逐行 ORM commit。

### 6.2 需要维护窗口

- `trade_date` 从字符串迁移到 Date。
- `bar_timestamp` 从字符串迁移到 DateTime。
- 核心 OHLCV 新写入路径使用 Numeric/Decimal。
- Text JSON 字段逐步迁移到 MySQL JSON。
- MinuteBar 月分区。

### 6.3 暂不立即做

- 全库读写分离。
- 全量主从自动切换。
- 全量历史 Float 一次性迁移。
- 立即替换 MySQL 时序数据。

## 7. 任务队列与后台任务

最终原则：

- Web 进程只处理请求，不跑全量扫描。
- Runtime worker 负责定时、预热、刷新、扫描。
- Backtest worker 负责回测和优化。
- 所有长任务必须有状态、进度、重试、失败原因。

近期实现：

- 继续使用现有 RuntimeTaskQueue，并补硬幂等、锁和监控。
- 所有新增任务必须入队。
- 迁移现有 threading loop 到 RuntimeTaskQueue。
- 只有当现有队列无法满足重试/死信/优先级时，再引入 ARQ。

不建议：

- 不立即全量替换 ARQ。
- 不把 Go scan 直接接入生产写表。

## 8. BFF 与 API 版本治理

当前项目已有 `/bff/v1`，应继续强化，而不是重新设计前端调用。

执行规则：

- Web/App 优先调用 BFF。
- 业务 API 保持兼容。
- 新增稳定接口进入 `/api/v2` 或 `/bff/v1` 新字段。
- 破坏性字段变更必须新增版本，不直接改旧响应。
- BFF 返回统一结构：

```json
{
  "data": {},
  "partial_errors": [],
  "schema_version": "v1",
  "generated_at": "2026-05-22T15:00:00+08:00"
}
```

## 9. Go 服务边界

允许 Go 做：

- BFF read aggregation。
- Quote batch read。
- Sector relative strength read。
- Intraday key level read。
- Full-market scan shadow worker。
- SSE/WebSocket push aggregation。

禁止 Go 近期做：

- 登录认证真源。
- 模拟盘账本。
- 订单资金扣减。
- 策略治理写操作。
- ML 模型晋级。
- 参数版本审批。

## 10. Rust 服务边界

允许 Rust 做：

- PyO3 指标计算。
- 批量滚动窗口。
- RankIC/协方差/最大回撤。
- 未来 Level2 ingest 原型。

禁止 Rust 近期做：

- HTTP API。
- 数据库写入。
- 账户/订单/权限。
- 策略规则真源。

## 11. 质量与验收标准

| 维度 | 当前问题 | 目标 |
|---|---|---|
| BFF 响应 | 串行查询、可能慢 | P95 `<800ms`，后续 `<500ms` |
| 全市场扫描 | Python 串行链路慢 | Go shadow `<90s`，生产目标 `<60s` |
| 结果一致性 | 多语言易漂移 | Go/Python 候选一致率 `>=99.5%` |
| 指标精度 | Python/Rust 可能差异 | 误差 `<1e-8` |
| 后台任务 | 线程循环不稳定 | 入队、幂等、重试、失败可查 |
| 数据库 | 慢查询和连接池风险 | 慢查询可观测，连接池可配置 |
| 回滚 | 新服务切换风险 | 所有 Go/Rust 开关可关闭 |

## 12. 测试矩阵

每阶段必须执行：

- Python 单元测试。
- API smoke。
- BFF contract diff。
- Go 单元测试和 race test。
- Go BFF shadow response diff。
- Go scan shadow diff。
- Rust benchmark 和 reference comparison。
- Alembic dry-run。
- 云端 `/healthz`、`/readyz`。
- 关键页面 Playwright smoke。

上线前必须确认：

- 前端无字段缺失。
- App/Web 行情状态一致。
- 模拟盘账本不受影响。
- 策略信号与生产快照一致。
- Go/Rust 开关关闭后系统仍完整可用。

## 13. 角色分工

| 角色 | 职责 |
|---|---|
| trading-quant-lead | 确认 Go/Rust 加速不改变策略语义，审核 scan diff |
| stock-analysis-specialist | 确认行情、板块、龙头强度字段符合 A 股短线语境 |
| product-strategist | 确认 BFF 输出满足 Web/App 页面需求 |
| ui-designer | 确认 partial/stale/unavailable 状态可读 |
| fullstack-builder | 实施 Python 加固、Go BFF、Go scan、Rust PyO3 |
| qa-tester | 维护 contract、shadow、smoke、回归测试 |
| devops-operator | 负责 compose、metrics、回滚、云端验收 |

## 14. 风险与回滚

### 风险 1：Go 与 Python 策略结果漂移

处理：

- Go scan 只影子运行。
- 生产切换前连续 10 个交易日 diff 通过。
- 参数版本是唯一真源。

### 风险 2：服务数量增加导致运维复杂

处理：

- Go 服务最多先上两个：`bff-gateway`、`scan-worker`。
- `market-read-service` 只有在行情读取确认瓶颈后再上。
- Compose profile 默认关闭。

### 风险 3：Rust 扩展构建失败

处理：

- Rust 为 optional dependency。
- Python reference 永远保留。
- feature flag 控制启用。

### 风险 4：数据库迁移影响生产

处理：

- 所有 schema 改动走 Alembic。
- 大表迁移必须维护窗口。
- 先新增列/索引，后切代码，再清理旧列。

## 15. 最终落地顺序

推荐只按下面顺序执行，不并行推进过多架构改造：

1. Phase 0：Python + MySQL + Redis + BFF 稳定性加固。
2. Phase 1：Go BFF 只读聚合 shadow。
3. Phase 2：Go market read service。
4. Phase 3：Go scan worker shadow。
5. Phase 4：Rust PyO3 指标内核。
6. Phase 5：MinuteBar 时序存储升级。

## 16. 最终结论

TQuant 当前后端的主要问题不是“Python 不够高级”，而是数据库、任务、缓存、BFF、可观测性和扫描性能还没有完全工程化。

最终方案不是替换 Python，而是：

- 用 Python 保持业务正确性。
- 用 Go 承接高并发读聚合与扫描吞吐。
- 用 Rust 承接高性能指标计算。
- 用 MySQL/Redis 加固当前基本盘。
- 用影子模式和契约测试控制多语言风险。

这条路线能提升系统整体能力，同时不会把项目推入过度微服务化和多语言失控。
