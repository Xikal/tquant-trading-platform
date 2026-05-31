# TQuant 后端最终重构总方案

> 状态：已归档。当前后端执行口径以 `docs/backend-go-rust-refactor-final-plan-2026-05-22.md` 和 `IMPLEMENTATION_PLAN.md` 为准，本文件仅作历史审查材料保留。

生成日期：2026-05-21
输入材料：

- `/Users/j/Downloads/TQuant_后端全方位深度审查报告.html`
- `docs/archive/plans/backend-final-refactor-optimization-plan-2026-05-21.md`

目标：形成一份最终可执行的后端重构方案，解决扩展性、性能、可靠性、数据库精度、任务队列、缓存一致性、可观测性和长期演进问题。

## 1. 最终结论

### 1.1 是否需要重构

需要重构，但不推倒重写。

最终路线：

```text
FastAPI 单体
  -> 模块化单体
  -> BFF + Application UseCase + Repository/UnitOfWork
  -> Redis 缓存/事件/分布式锁
  -> ARQ Worker 任务队列
  -> 可替换领域 Adapter
  -> 条件成熟后按领域拆独立服务
```

不建议现在直接微服务化：

- 当前核心问题是数据库精度、任务队列、缓存、分层、慢查询和可观测，不是服务数量不够。
- 贸然拆微服务会先放大分布式事务、鉴权、部署、链路追踪和数据一致性成本。
- 现有 BFF 骨架已具备渐进拆服务能力，应先把领域接口、Repository、任务和缓存标准化。

### 1.2 技术栈最终决策

保留：

- `FastAPI`：继续作为 API Gateway、BFF、领域 API 框架。
- `SQLAlchemy 2`：继续作为 ORM 和事务层。
- `Alembic`：生产唯一迁移机制。
- `MySQL 8.4`：生产主库。
- `Redis 7`：缓存、Pub/Sub、限流、分布式锁、任务队列。
- `Pydantic v2`：请求/响应 schema。
- `Docker Compose`：当前云服务器部署基线。
- `Prometheus + Grafana`：生产监控基线。

新增或强化：

- `ARQ`：最终任务队列首选，基于 Redis，轻量，适合当前 Python/FastAPI 项目。
- `TaskQueueAdapter`：保留可替换 seam，未来可以切到 Celery/RQ，不影响 API。
- `UnitOfWork + Repository`：统一事务和数据访问。
- `Redis distributed lock`：替代 `fcntl` leader lock。
- `OpenTelemetry`：中长期接入链路追踪。
- `structlog` 或增强 JSON logger：生产结构化日志。

不采用：

- 不把后端整体改成 Next.js/Node。
- 不把所有 SQLAlchemy sync 代码一次性改 async。
- 不立即拆数据库。
- 不立即接真实券商实盘交易。
- 不让 Agent/ML 绕过确定性风控。

### 1.3 与现有代码状态的校准

审查报告中部分问题在当前代码中已经具备基础能力，最终执行时不要重复造轮子：

- `GZipMiddleware` 当前已存在于 `backend/app/main.py`。
- 全局异常处理当前已存在于 `backend/app/main.py`。
- `X-Request-ID` 当前已在响应中写回。
- BFF remote adapter 当前已具备远端失败 fallback 和 circuit breaker。
- MySQL + Redis + app + runtime-worker + backtest-worker + migration 容器已具备。

但仍需要强化：

- `X-Request-ID` 需要透传到远端 BFF/内部服务。
- 结构化日志默认仍是 `false`，且 JSON 字段较少。
- DB 连接池参数仍硬编码。
- MySQL InnoDB 生产参数仍不足。
- Redis 持久化参数仍较弱。
- `fcntl` leader lock 仍存在。
- 后台任务仍有 thread-based loop。
- 行情/回测/策略相关表仍存在 Float/String 日期等数据库设计问题。
- Repository 覆盖仍不足。

## 2. 最终目标架构

```text
Web / App / Agent / Hermes
        |
        v
FastAPI Gateway
  - Auth
  - Request ID
  - Rate Limit
  - Security Headers
  - Error Envelope
  - Operation Audit
        |
        v
BFF Layer
  - /api/bff/v1/workspace/monitor
  - /api/bff/v1/workspace/playbook
  - /api/bff/v1/workspace/holdings
  - /api/bff/v1/workspace/paper
  - /api/bff/v1/workspace/settings
        |
        v
Application UseCases
  - MonitorUseCase
  - PlaybookUseCase
  - HoldingsUseCase
  - PaperTradingUseCase
  - BacktestUseCase
  - FactorMiningUseCase
  - AgentUseCase
        |
        v
Domain Modules
  - auth
  - market
  - strategy
  - holdings
  - paper
  - backtest
  - factor
  - agent
  - settings
        |
        v
Adapters
  - SQLAlchemy Repository
  - Redis Cache
  - ARQ TaskQueue
  - Market Provider Router
  - Feishu Adapter
  - Hermes/Agent Adapter
  - ML Artifact Store
        |
        v
MySQL / Redis / External Market Data / Agent Runtime
```

架构原则：

- API 层只做鉴权、参数校验、错误映射和调用 use case。
- BFF 只聚合、裁剪、降级，不做重计算。
- Application 层负责业务编排、事务边界、缓存策略和任务提交。
- Domain 层负责交易制度、策略、风控、撮合、信号、模型晋级等确定性规则。
- Repository 负责数据访问。
- Adapter 负责外部系统。
- Worker 负责长任务。
- Redis 负责跨进程缓存、事件、锁和任务。
- MySQL 负责交易、账户、配置、任务、策略结果和近线数据。

## 3. 必须优先解决的 10 个问题

### 3.1 P0 必修

1. 数据库金融精度问题
   `DailyBarSnapshot`、`MinuteBarSnapshot`、部分回测/策略结果仍使用 `Float`。价格、金额、成交量、手续费、收益金额必须迁移到 `Numeric/Decimal`。

2. 日期类型问题
   `trade_date`、`bar_timestamp` 大量使用 `String`。必须迁移到 `Date/DateTime`，否则分区、日期函数和索引优化都受限。

3. MySQL 生产参数不足
   `docker-compose.mysql.yml` 需要补齐 InnoDB buffer pool、slow query log、连接数、IO threads、log file size 等参数。

4. DB 连接池硬编码
   `pool_size=12`、`max_overflow=24` 等必须配置化，避免 app/runtime/backtest 多进程耗尽连接。

5. 后台任务体系混乱
   thread loop、DB queue、worker 并存。必须建立统一 `TaskQueueAdapter`，生产用 `ARQ`，DB queue 只做本地/降级。

6. `fcntl` leader lock 不适合生产
   替换为 Redis `SET NX EX` 分布式锁，带 TTL 和续期。

7. BFF 和核心页面接口必须缓存化
   `monitor`、`app/home`、`priority-board`、`watchlist/signals` 必须走 Redis 缓存或物化快照。

8. 回测和全量扫描必须进入 worker
   API 进程只提交任务和读取状态，不做全量扫描、回测、ML 训练、Agent 深度分析。

9. Repository/UnitOfWork 必须补齐
   `paper`、`watchlist/holdings`、`strategy`、`runtime_task`、`factor` 必须逐步从 service 内联 SQL 迁出。

10. 结构化日志与追踪必须补齐
   生产必须开启 JSON 日志，并透传 request id 到 BFF 远端服务和 worker task。

### 3.2 已有基础但需验收

- GZip：已有，需确认生产响应头和压缩率。
- 全局异常处理：已有，需确认不泄露 traceback。
- Request ID：已有响应写回，需补远端传播和日志上下文。
- Provider Router：已有，需确认所有行情路径都走 router。
- Prometheus：已有，需补 DB/ARQ/缓存/策略耗时指标。

## 4. 数据库最终整改方案

### 4.1 金融精度迁移

目标字段：

- 价格：`Numeric(18, 4)`
- 金额：`Numeric(20, 2)`
- 成交量：`Numeric(20, 0)` 或按实际单位确定
- 百分比：`Numeric(10, 4)`
- 分数/概率：可保留 Float，但生产策略阈值建议 Numeric 或 Decimal 计算后转出

重点表：

- `daily_bar_snapshots`
- `minute_bar_snapshots`
- `backtest_orders`
- `backtest_trades`
- `backtest_daily_snapshots`
- `low_buy_*_snapshots`
- `watchlist.cost_basis`
- `user_watchlists.cost_basis`
- `market_model_observations`

落地方式：

1. 新增 Alembic 迁移。
2. 对大表优先采用低风险双列迁移：
   - 新增 `*_decimal` 或新类型字段。
   - 批量回填。
   - 代码双读/双写。
   - 验证一致性。
   - 切换读取。
   - 删除旧字段或后续重命名。
3. 小表可直接 `ALTER COLUMN`。
4. Python 端计算统一使用 `Decimal` 或明确的 `to_decimal()`。

验收：

- 回测、模拟盘、策略计算不再因浮点误差出现异常小数。
- 价格字段序列化仍保持前端需要的小数位。
- 迁移前后核心回测结果在允许误差范围内一致。

### 4.2 日期类型迁移

目标：

- `trade_date` → `Date`
- `signal_trade_date`、`entry_trade_date`、`exit_trade_date` → `Date`
- `bar_timestamp` → `DateTime`
- schema 输出层仍可格式化成 `YYYY-MM-DD` 或 `YYYY-MM-DD HH:mm:ss`

重点表：

- `daily_bar_snapshots`
- `minute_bar_snapshots`
- `low_buy_*`
- `backtest_*`
- `market_model_observations`
- `phase4_entities` 中日期字段

落地方式：

1. 新增日期类型字段。
2. `STR_TO_DATE()` 回填。
3. 新写入双写。
4. 查询先兼容新旧字段。
5. 所有查询切到 Date/DateTime。
6. 最后清理旧字符串字段。

验收：

- 可使用 MySQL 日期函数查询最近 N 天。
- 可做按月分区。
- `(symbol, trade_date)` 索引可稳定命中。

### 4.3 索引与查询优化

必须新增或确认：

```sql
CREATE INDEX ix_daily_symbol_date
  ON daily_bar_snapshots(symbol, trade_date);

CREATE INDEX ix_factor_eval_key_status_created
  ON factor_eval_results(factor_key, status, created_at DESC);

CREATE INDEX ix_op_audit_action_created
  ON operation_audit_log(action, created_at DESC);

CREATE INDEX ix_ml_sample_strategy_date
  ON ml_signal_samples(strategy_key, signal_date DESC, outcome);

CREATE INDEX ix_lots_account_available_date
  ON paper_position_lots(account_id, available_date, remaining);
```

Instrument 搜索：

- 4500 只 A 股标的规模下，优先做内存字典 + Redis 缓存。
- 若后续标的扩展，再上 MySQL FULLTEXT。

查询规则：

- 列表接口必须分页。
- 大页码使用 keyset pagination，避免大 OFFSET。
- 回测/流水/策略详情必须 summary/detail 分离。
- 大 JSON 字段不得出现在列表接口。
- 关键关联查询必须使用 `selectinload` 或显式 JOIN，禁止 N+1。

### 4.4 MySQL 生产参数

`docker-compose.mysql.yml` 建议：

```yaml
command:
  - --character-set-server=utf8mb4
  - --collation-server=utf8mb4_unicode_ci
  - --innodb-buffer-pool-size=${MYSQL_INNODB_BUFFER_POOL_SIZE:-2G}
  - --innodb-log-file-size=${MYSQL_INNODB_LOG_FILE_SIZE:-512M}
  - --innodb-flush-log-at-trx-commit=${MYSQL_INNODB_FLUSH_LOG_AT_TRX_COMMIT:-2}
  - --slow-query-log=ON
  - --slow-query-log-file=/var/log/mysql/slow.log
  - --long-query-time=${MYSQL_LONG_QUERY_TIME:-1}
  - --log-queries-not-using-indexes=ON
  - --max-connections=${MYSQL_MAX_CONNECTIONS:-300}
  - --innodb-read-io-threads=8
  - --innodb-write-io-threads=8
```

注意：

- 参数必须环境变量化。
- 低配云服务器不能硬写 2G。
- 调整前先确认服务器内存。

### 4.5 连接池配置化

新增配置：

```python
db_pool_size: int = 12
db_max_overflow: int = 24
db_pool_recycle: int = 1800
db_pool_timeout: int = 30
database_read_url: str = ""
```

执行：

- app、runtime-worker、backtest-worker 可分别通过 env 设置连接池。
- 长任务 worker 连接池应小于 API 进程，避免拖垮 MySQL。

### 4.6 备份与归档

必须新增：

- MySQL 每日备份。
- 备份保留 7-14 天。
- 每月至少一次恢复演练。
- 低吸快照、回测大结果、操作审计按保留期清理。

建议保留期：

- 低吸 scan snapshot：30 天。
- 低吸 result snapshot：90 天。
- 回测结果：365 天。
- 操作审计：至少 365 天。
- 分钟线：热数据 90 天，冷数据归档。

## 5. 任务系统最终方案

### 5.1 最终选型：ARQ + Redis

最终采用：

```text
RuntimeTask API
  -> TaskQueueAdapter
     -> ArqTaskQueueAdapter   生产
     -> DbTaskQueueAdapter    本地/降级/测试
```

选择 ARQ 的原因：

- Redis 已经是项目基础设施。
- 比 Celery 轻，部署成本低。
- 适合当前单机/小团队/模块化单体阶段。
- 支持 async 任务、超时、重试、结果保留。
- 通过 Adapter 保留未来换 Celery/RQ 的能力。

### 5.2 队列划分

```text
queue:market-refresh
  - 行情缓存刷新
  - 日线增量
  - 市场情绪

queue:strategy-scan
  - 全策略扫描
  - priority-board 物化
  - 策略治理

queue:backtest
  - 回测
  - Walk-forward
  - 参数优化

queue:factor-ml
  - 因子计算
  - 因子评估
  - ML 样本构建
  - 模型训练

queue:agent-notification
  - Agent 深度分析
  - 飞书通知
  - 日报
```

### 5.3 APScheduler 与 ARQ 分工

- APScheduler 只负责“什么时候触发”。
- ARQ 负责“实际执行、重试、超时、状态、结果”。
- API 负责“提交任务、查询任务、读取事件”。

### 5.4 `fcntl` 替换

新增：

```text
backend/app/core/leader_lock.py
```

能力：

- Redis `SET key value NX EX ttl`。
- 持锁进程定期续期。
- 退出时释放。
- Redis 不可用时，生产环境直接降级为“不运行 leader 任务”，避免双主；本地开发可 fallback 文件锁。

验收：

- 多 worker 同时启动只会有一个 leader。
- leader 被 kill 后 TTL 到期，其他 worker 能接管。

## 6. 缓存与性能最终方案

### 6.1 缓存分层

L1：进程内短 TTL

- 仅用于 1-30 秒局部热点。
- 不作为生产一致性基础。

L2：Redis

- BFF 响应。
- priority-board。
- app/home。
- watchlist/signals。
- market regime。
- quote snapshot。
- settings runtime。
- Provider health。

L3：MySQL 物化结果

- full scan 结果。
- 回测结果。
- 因子结果。
- ML 样本。

### 6.2 缓存策略

Cache-Aside：

- 读缓存。
- miss 读 DB/物化结果。
- 写入 Redis。

Write-Through / Invalidate：

- 持仓新增、编辑、删除后立即删除相关缓存。
- 策略参数变更后删除榜单缓存。
- full scan 完成后写 MySQL 并刷新 Redis。

防缓存穿透：

- instrument 查无结果缓存空值，TTL 60-300 秒。

### 6.3 性能预算

| 场景 | warm p95 | cold p95 | 处理原则 |
|---|---:|---:|---|
| `/readyz` | 100ms | 300ms | 轻量检查 |
| `/api/bff/v1/workspace/monitor` | 500ms | 1500ms | Redis/BFF partial error |
| `/api/app/home` | 500ms | 1200ms | 快照优先 |
| `/api/screeners/low-buy/priority-board` | 500ms | 2000ms | 不触发 full scan |
| `/api/watchlist/signals` | 600ms | 1500ms | 读快照 |
| 新增/编辑持仓 | 300ms | 800ms | 不等待慢行情 |
| 回测提交 | 300ms | 800ms | 只入队 |
| 因子实验提交 | 300ms | 800ms | 只入队 |

### 6.4 回测性能

整改：

- 按 symbol batch 流式加载。
- `pd.read_sql(..., chunksize=10000)`。
- 只 SELECT 必需列。
- 大结果 summary/detail 分离。
- 相同参数 hash 命中缓存。
- 全市场回测只进 `queue:backtest`。

验收：

- 全市场 K 线加载不一次性占用 2GB 内存。
- 回测任务峰值内存可观测。
- 同参数重复回测可复用结果。

### 6.5 全策略扫描性能

整改：

- 每个策略一个 ARQ task。
- 每批 100-500 个 symbol。
- 行情数据 batch 获取。
- 评分结果批量写入。
- MySQL `INSERT ... ON DUPLICATE KEY UPDATE`。
- Redis 写入榜单摘要。

验收：

- full scan 不阻塞 API。
- 扫描失败可重试。
- API 只读物化结果。

## 7. API 与 BFF 最终方案

### 7.1 API 版本

保持兼容：

- 现有 `/api/*` 不破坏。
- 现有 `/api/bff/v1/*` 保持。

新增规范：

- 新业务接口优先进入 `/api/v2/*`。
- BFF 响应增加 `api_version`。
- 响应头增加 `API-Version`。
- 破坏性变更只允许在 v2。

### 7.2 BFF 标准响应

统一：

```json
{
  "api_version": "bff-v1",
  "generated_at": "2026-05-21 10:00:00",
  "data_quality": {
    "is_stale": false,
    "source": "redis|mysql|provider",
    "warning": ""
  },
  "partial_errors": [],
  "data": {}
}
```

### 7.3 BFF 性能与降级

要求：

- BFF 不重算策略。
- BFF 不跑外部慢行情。
- BFF 只读缓存/物化结果。
- 单个子模块失败时返回 `partial_errors`。
- 远端 service 失败时 fallback 本地 adapter。
- 整体 timeout 默认 8 秒。

### 7.4 Request ID 传播

需要补齐：

- Remote BFF 调用转发 `X-Request-ID`。
- ARQ task payload 记录 request id。
- Worker 日志带 task id 和 request id。
- 外部 Agent 调用带 trace id。

## 8. 分层与代码质量最终方案

### 8.1 目标目录

```text
backend/app
├── api
│   ├── gateway
│   ├── bff
│   └── v1 / v2
├── application
├── domains
├── repositories
├── adapters
│   ├── cache
│   ├── task_queue
│   ├── market_data
│   ├── notification
│   ├── agent_runtime
│   └── object_store
├── workers
├── models
├── schemas
└── core
```

不要求一次性搬目录。优先按高频链路迁移。

### 8.2 第一批必须拆的 Module

1. `paper/scheduler.py`

目标拆分：

```text
AutoTradingOrchestrator
SignalSelectionService
OrderPlanBuilder
PaperTradingExecutor
PostTradeNotifier
```

`scheduler.py` 最终只保留入口与协调，目标 ≤ 80 行。

2. `backtests.py`

拆分：

```text
BacktestRunRoutes
BacktestTaskRoutes
BacktestResultRoutes
BacktestResearchRoutes
```

3. `agent.py` / `agent_helpers.py`

拆分：

```text
AgentContextRoutes
AgentWorkflowRoutes
AgentQualityRoutes
AgentNotificationRoutes
AgentAuditRoutes
```

4. `ml_signal/service.py`

拆分：

```text
SampleBuilder
ModelTrainer
ArtifactManager
PromotionGate
InferenceService
```

5. `low_buy` 大模块

按职责稳定：

```text
PoolLoader
CandidateBuilder
FactorCalculator
StrategyScorer
RiskFilter
ResultMaterializer
PriorityBoardProjector
```

### 8.3 Repository 补齐顺序

P0/P1：

- `WatchlistRepository`
- `UserWatchlistRepository`
- `HoldingRepository`
- `LowBuyResultRepository` 增强
- `RuntimeTaskRepository`
- `PaperAccountRepository`
- `PaperPositionRepository`
- `PaperOrderRepository`

P2：

- `BacktestRepository`
- `FactorRepository`
- `MLSignalRepository`
- `AgentAuditRepository`
- `SettingsRepository`

### 8.4 文件大小约束

- route 文件 ≤ 220 行。
- use case ≤ 260 行。
- domain service ≤ 260 行。
- repository ≤ 260 行。
- worker task ≤ 180 行。
- schema 单文件 ≤ 300 行。

## 9. 可观测性最终方案

### 9.1 结构化日志

生产默认：

```env
STRUCTURED_LOGS=true
```

字段：

- `timestamp`
- `level`
- `message`
- `request_id`
- `user_id`
- `route`
- `duration_ms`
- `domain`
- `operation`
- `symbol`
- `strategy_key`
- `task_id`
- `provider`
- `cache_hit`

禁止：

- token。
- secret。
- cookie。
- Agent 完整未脱敏输入输出。

### 9.2 Metrics

必须补：

- `tquant_http_request_duration_ms`
- `tquant_bff_workspace_duration_ms`
- `tquant_cache_hits_total`
- `tquant_cache_misses_total`
- `tquant_db_query_duration_ms`
- `tquant_arq_jobs_queued`
- `tquant_arq_jobs_failed`
- `tquant_strategy_scan_duration_ms`
- `tquant_provider_calls_total`
- `tquant_provider_failures_total`
- `tquant_paper_order_failures_total`
- `tquant_agent_quality_blocked_total`
- `tquant_ml_promotion_blocked_total`

### 9.3 告警

P0 告警：

- `/readyz` 失败。
- MySQL 连接失败。
- Redis 连接失败。
- ARQ worker 无心跳。
- Provider 全部不可用。
- 持仓保存错误率 > 5%。
- paper order 失败率异常。

P1 告警：

- BFF p95 > 800ms。
- priority-board p95 > 2s。
- App home p95 > 1.2s。
- cache hit rate < 60%。
- 回测任务失败连续增加。

## 10. 安全最终方案

### 10.1 已有安全能力保留

- Security headers。
- CORS 白名单。
- body size limit。
- admin token。
- auth secret 强校验。
- settings encryption key。
- operation audit。
- Agent token。

### 10.2 必须增强

- 内部服务调用必须 `X-Internal-Service-Token`。
- BFF remote adapter 必须转发 request id，但只向可信目标转发认证信息。
- ARQ task 类型必须白名单。
- Agent write tools 默认关闭。
- ML artifact 路径必须限制在允许目录并校验 hash。
- 文件路径、subprocess、外部命令必须最小权限。
- 模拟交易也必须经过风控，不允许 Agent 直接写订单表。

## 11. 最终实施路线图

### Phase 0：生产安全与低风险性能修复，1-2 周

目标：不改核心表结构，先提升稳定性。

任务：

- 验证 GZip、全局异常处理、Request ID 已生效。
- `X-Request-ID` 透传到 remote BFF 和 worker task。
- `STRUCTURED_LOGS=true`，增强 JSON 字段。
- MySQL InnoDB 参数环境变量化。
- DB 连接池参数环境变量化。
- Redis AOF/RDB 持久化参数补齐。
- MySQL 自动备份 service。
- Prometheus 增加缓存、DB、Provider、BFF 指标。
- 核心接口建立性能基线。

验收：

- `/readyz` 正常。
- 核心接口有 request id。
- 慢查询日志可用。
- 每日备份文件可恢复。
- BFF warm p95 有数据。

### Phase 1：数据库精度与索引整改，2-4 周

目标：解决金融系统最核心的数据质量问题。

任务：

- Float → Numeric 迁移设计。
- String 日期 → Date/DateTime 迁移设计。
- 先小表直接改，大表双列迁移。
- 增加 `(symbol, trade_date)` 等关键索引。
- Text JSON → JSON 列，优先 signal_snapshot / strategy_sources / factor weights。
- Paper N+1 查询修复。
- 批量写入改为 bulk insert / upsert。

验收：

- Alembic 空库升级通过。
- 现有库迁移前有备份。
- 核心回测结果不因迁移异常漂移。
- 慢查询数量下降。

### Phase 2：任务队列与缓存体系，4-8 周

目标：API 进程彻底脱离长任务。

任务：

- 新增 `TaskQueueAdapter`。
- 新增 `ArqTaskQueueAdapter`。
- 保留 `DbTaskQueueAdapter`。
- `fcntl` 替换 Redis leader lock。
- full scan、回测、因子、Agent 深度分析迁移到 ARQ。
- RuntimeTask API 不变。
- Redis Pub/Sub 推送任务事件。
- BFF、priority-board、app/home、watchlist/signals 缓存标准化。

验收：

- API 提交任务 < 300ms。
- worker kill 后任务可恢复/失败可见。
- priority-board warm p95 < 500ms。
- app/home warm p95 < 500ms。

### Phase 3：Application / Repository 分层，4-8 周

目标：降低复杂度，提升可测试性和扩展性。

任务：

- 新增 `application/`。
- 新增 `repositories/unit_of_work.py`。
- 迁移 holdings/watchlist。
- 迁移 monitor BFF。
- 迁移 playbook priority-board。
- 迁移 paper 核心账户/订单/持仓。
- 拆 `paper/scheduler.py`。

验收：

- route 文件明显变薄。
- use case 可用 fake repository 单测。
- paper 下单事务一致。
- 持仓保存 p95 < 300ms。

### Phase 4：存储架构升级，2-3 个月

目标：解决行情时序数据长期增长问题。

任务：

- MinuteBar 按月分区。
- 快照表归档策略。
- 读写分离设计与只读 Session。
- InfluxDB/TDengine 试点，不立即替换主链路。
- MinuteBar 双写验证。

验收：

- 分区裁剪生效。
- 历史查询性能提升。
- 归档任务可回放。
- 不影响生产策略。

### Phase 5：可独立服务演进，长期

触发条件：

- 多用户/多团队协作明显增加。
- 单体部署已成为瓶颈。
- market/backtest/factor 某个模块有独立扩容需求。

顺序：

1. `factor-service`
2. `backtest-service`
3. `market-service`
4. `strategy-service`
5. `trade-service`
6. `auth-service` 最后拆

原则：

- 先拆只读、低风险服务。
- 不先拆数据库。
- BFF remote adapter 已稳定后再拆。
- 远程失败必须 fallback。

## 12. 最终验收标准

### 12.1 功能稳定

- Web/App 核心接口响应结构不破坏。
- 持仓、选股宝典、模拟盘、回测、Agent 功能可用。
- 研究策略不会混入生产策略。
- Agent/ML 不绕过风控。

### 12.2 性能

| 指标 | 目标 |
|---|---:|
| BFF workspace p95 | ≤ 800ms |
| priority-board warm p95 | ≤ 500ms |
| app/home warm p95 | ≤ 500ms |
| 新增/编辑持仓 p95 | ≤ 300ms |
| 回测提交 p95 | ≤ 300ms |
| 全市场回测 K 线加载 | ≤ 10s，且流式/分块 |
| API 读接口 QPS | ≥ 200 QPS，读写分离后 |

### 12.3 数据库

- OHLCV 不再使用 Float 存储金融价格。
- 日期字段支持原生 Date/DateTime 查询。
- 慢查询日志开启。
- 每日自动备份。
- 关键索引完整。
- 快照表有归档策略。

### 12.4 可靠性

- 后台任务 3 次重试。
- 失败任务进入可观测状态。
- Redis lock 防双主。
- Provider 全部失败时有降级提示。
- Worker 无心跳会告警。

### 12.5 代码质量

- route 不做复杂业务。
- 核心链路有 use case。
- 数据访问通过 repository。
- `paper/scheduler.py` ≤ 80 行。
- 核心文件不继续膨胀。

## 13. 给 Codex 的最终执行提示词

```text
你是 TQuant 项目的资深后端架构师、性能优化工程师、量化交易系统工程师和 DevOps 负责人。请基于当前仓库，按照 docs/archive/plans/backend-final-refactor-master-plan-2026-05-21.md 执行后端最终重构。

强制要求：
1. 不推倒重写。
2. 不破坏现有 Web/App/API 响应结构。
3. 不接真实券商实盘交易。
4. 不允许 API 进程执行全量扫描、回测、ML 训练、Agent 深度分析。
5. 不允许生产启动依赖 schema_compat 自动修表。
6. 不允许策略/业务模块直接调用 AkShare 或 requests 绕过 Provider Router。
7. 不允许 Agent/ML 绕过后端确定性风控。
8. 不允许日志泄露 token、secret、cookie。
9. 所有核心改动必须有测试或契约验证。

第一阶段只做 Phase 0：
- 校验已有 GZip、全局异常处理、Request ID。
- 补 Request ID 远端传播和 worker task 传播。
- 开启并增强结构化日志。
- DB 连接池配置化。
- MySQL InnoDB 参数环境变量化。
- Redis 持久化参数补齐。
- MySQL 自动备份 service。
- 补 BFF/cache/provider/task 指标。
- 给核心接口输出性能基线。

完成后运行：
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
DATABASE_URL=sqlite:////tmp/tquant_migration_check.db PYTHONPATH=backend:. backend/.venv/bin/alembic -c backend/alembic.ini upgrade head

输出：
- 已完成项
- 修改文件
- 是否影响接口
- 数据库影响
- 部署影响
- 测试结果
- 未完成风险
- 下一阶段建议
```

## 14. 最终判断

TQuant 后端技术路线本身正确，当前最需要的是工程化补强，而不是换栈。最终优先级应按资金安全和生产稳定性排序：

1. 先修数据库精度、日期类型、索引、备份。
2. 再把长任务迁移到 ARQ Worker。
3. 再把 BFF、榜单、持仓、行情快照缓存标准化。
4. 再补 Repository/UnitOfWork 和 Application UseCase。
5. 最后再考虑 InfluxDB、读写分离和独立服务。

这样可以在不破坏当前平台可用性的前提下，把后端提升到具备扩展性、性能优秀、可长期演进的状态。
