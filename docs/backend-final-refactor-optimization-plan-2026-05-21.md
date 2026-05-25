# TQuant 后端服务最终重构优化落地方案

> 状态：已归档。当前后端执行口径以 `docs/backend-go-rust-refactor-final-plan-2026-05-22.md` 和 `IMPLEMENTATION_PLAN.md` 为准，本文件仅作历史审查材料保留。

生成日期：2026-05-21
适用项目：维斯量化 TQuant A 股短线交易辅助平台
目标读者：Codex / Claude Code / 后端开发 / DevOps / QA / 量化策略负责人

## 1. 总体结论

### 1.1 是否需要后端重构

结论：需要重构，但不需要推倒重写；应采用“模块化单体优先、BFF 稳定前端契约、Worker 解耦重任务、Redis 强化缓存与事件、领域 Adapter 预留微服务拆分”的最终架构。

当前后端的主要问题不是 FastAPI / SQLAlchemy 选型错误，而是业务增长后模块边界和性能责任不够清晰：

- `backend/app/services` 已达到 405 个 Python 文件、约 6.49 万行，承担了路由编排、领域逻辑、数据访问、缓存、外部 API、任务、策略计算等多种职责。
- `backend/app/api/routes` 有 38 个 route 文件、约 242 个接口、约 6165 行，部分 route 仍承担较多应用编排。
- `backend/app/repositories` 只有 11 个文件、约 1097 行，说明大量数据库访问仍散落在 service、runtime、route 中。
- `SessionLocal()` 在 service/runtime/worker 中直接使用较多，测试隔离、事务边界和后续拆服务会变难。
- 已有 BFF、RuntimeTaskQueue、Provider Router、Prometheus、Redis、Alembic、Worker 雏形，但缺少统一的后端工程规范和最终分层。
- 有多个线程型后台任务、DB-backed queue、独立 worker、APScheduler 风格逻辑并存，任务执行责任需要收口。
- 行情、策略、模拟盘、因子、Agent、通知、设置等模块已经足够复杂，必须明确领域边界，否则继续迭代会越来越慢。

### 1.2 保留 or 替换

保留：

- FastAPI：继续作为 API Gateway / BFF / 领域 API 框架。
- SQLAlchemy 2：继续作为 ORM 和事务层。
- Alembic：继续作为唯一生产数据库迁移机制。
- MySQL 8.4：作为生产主数据库。
- Redis 7：作为缓存、事件、限流、任务队列基础设施。
- Pydantic v2：继续作为请求/响应 schema。
- Docker Compose：继续作为当前云服务器部署基线。
- Prometheus / Grafana：继续作为监控基线。

替换或收口：

- `schema_compat`：只能作为本地/历史兼容工具，生产启动路径必须完全依赖 Alembic。
- 进程内全局缓存：生产关键缓存统一走 Redis，本地内存缓存只作为 L1 cache。
- 线程型长任务：逐步收口到统一任务系统，Web API 进程不直接执行 CPU 密集或长 I/O 任务。
- route 直接编排复杂业务：迁移到 application service / use case。
- service 内直接访问 `SessionLocal()`：迁移到 repository + UnitOfWork。
- BFF 内重计算：BFF 只做聚合、裁剪、降级，不做策略扫描、回测、行情全量计算。

暂不采用：

- 暂不整体微服务化。
- 暂不拆数据库。
- 暂不引入 gRPC。
- 暂不把所有接口改为 async。
- 暂不接真实券商实盘交易。

### 1.3 最终后端架构目标

目标形态：

```text
Web / App / Agent / Hermes
        |
        v
FastAPI Gateway
  - Auth / Rate Limit / Audit / Security Headers
  - BFF /api/bff/v1/*
  - Stable Domain API /api/v1/*
        |
        v
Application Layer
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
  - Market Provider Router
  - Redis Cache / PubSub
  - Celery Worker Adapter
  - Feishu / Hermes / LLM Adapter
        |
        v
MySQL / Redis / External Market Data / Agent Runtime
```

核心原则：

- API 层稳定。
- 应用层编排。
- 领域层负责业务规则。
- Repository 负责数据访问。
- Adapter 负责外部系统。
- Worker 负责长任务。
- Redis 负责跨进程缓存和事件。
- Prometheus 负责可观测。

## 2. 当前后端技术栈与现状

### 2.1 当前依赖

生产核心依赖：

- `fastapi`
- `uvicorn`
- `gunicorn`
- `sqlalchemy`
- `pydantic-settings`
- `httpx`
- `requests`
- `akshare`
- `pandas`
- `numpy`
- `pymysql`
- `cryptography`
- `PyJWT`
- `alembic`
- `redis`
- `scikit-learn`
- `lightgbm`
- `apscheduler`

当前部署已经具备：

- `app` Web API 容器。
- `runtime-worker` 运行时任务容器。
- `backtest-worker` 回测任务容器。
- `mysql` 数据库。
- `redis` 缓存/事件。
- `migration` Alembic 迁移容器。
- Prometheus/Grafana 配置。

### 2.2 已有优势

当前后端不是从零开始，已有不少正确方向：

- 已有 `/api/bff/v1/workspace/*`，适合支撑前端重构。
- 已有 `RuntimeTaskQueue`，具备任务状态、重试、事件流基础。
- 已有 `MarketProviderRouter`，支持多行情源降级、熔断、超时和质量标记。
- 已有 `Redis`，可支撑全局限流、缓存、SSE/PubSub、任务。
- 已有 Alembic 迁移和 migration 容器。
- 已有 `/metrics`、Prometheus 告警和 Grafana dashboard 初稿。
- 已有 Agent 质量评分、ML 生产门槛、参数版本化、模拟盘、回测、因子挖掘骨架。

### 2.3 主要风险

最大风险 1：服务层过大，领域边界不稳

- `services` 下模块数量多，但并非全部是深模块。
- 部分 service 既做数据加载，又做策略计算，又做格式化输出。
- 后续多人/多 Agent 协作时容易互相改坏。

最大风险 2：数据访问分散

- repository 层覆盖不足。
- 大量逻辑直接持有 DB session 或自行创建 `SessionLocal()`。
- 事务边界不统一，后续拆服务和测试 mock 难度高。

最大风险 3：任务系统并存

- 有 DB-backed RuntimeTaskQueue。
- 有 in-process TaskManager。
- 有 thread-based scheduler。
- 有独立 worker。
- 有 backtest queue worker。
- 需要统一“什么能在 API 进程跑，什么必须进 worker”。

最大风险 4：性能路径复杂

- 选股全量扫描、行情、市场情绪、持仓信号、回测、因子挖掘都是潜在慢路径。
- 当前已有缓存，但缓存层级、TTL、失效机制不够统一。
- 如果前端重构后请求更集中，后端需要更明确的 fast path。

最大风险 5：生产数据一致性与可观测不足

- 部分缓存是内存级，跨进程一致性弱。
- 部分后台线程失败只写日志，不一定进入统一任务状态。
- 监控已有基础，但缺少接口级 p95、任务耗时、缓存命中率、数据源质量、策略扫描耗时的统一 SLO。

## 3. 后端最终分层规范

### 3.1 推荐目录结构

```text
backend/app
├── api
│   ├── gateway
│   │   ├── middleware.py
│   │   ├── errors.py
│   │   └── responses.py
│   ├── bff
│   │   ├── monitor.py
│   │   ├── playbook.py
│   │   ├── holdings.py
│   │   ├── paper.py
│   │   └── settings.py
│   └── v1
│       ├── auth.py
│       ├── market.py
│       ├── strategy.py
│       ├── holdings.py
│       ├── paper.py
│       ├── backtest.py
│       ├── factor.py
│       ├── agent.py
│       └── admin.py
├── application
│   ├── monitor_use_case.py
│   ├── playbook_use_case.py
│   ├── holdings_use_case.py
│   ├── paper_trading_use_case.py
│   ├── backtest_use_case.py
│   ├── factor_mining_use_case.py
│   └── agent_use_case.py
├── domains
│   ├── auth
│   ├── market
│   ├── strategy
│   ├── holdings
│   ├── paper
│   ├── backtest
│   ├── factor
│   ├── agent
│   └── settings
├── repositories
│   ├── auth_repository.py
│   ├── market_repository.py
│   ├── strategy_repository.py
│   ├── holdings_repository.py
│   ├── paper_repository.py
│   ├── backtest_repository.py
│   ├── factor_repository.py
│   └── unit_of_work.py
├── adapters
│   ├── market_data
│   ├── cache
│   ├── task_queue
│   ├── notification
│   ├── agent_runtime
│   └── object_store
├── workers
├── models
├── schemas
├── core
└── main.py
```

说明：

- 不要求一次性搬目录。
- 第一阶段可以在现有 `services/*` 内先建立清晰 interface。
- 迁移时按模块完成，不做全仓库机械移动。

### 3.2 API 层规范

API 层只做：

- 鉴权与权限依赖。
- 参数校验。
- 调用 use case。
- 返回 schema。
- 错误映射。

API 层禁止：

- 直接扫描行情。
- 直接跑回测。
- 直接计算策略排名。
- 直接创建 `SessionLocal()`。
- 直接拼外部数据源请求。
- 直接写复杂 JSON 拼装逻辑。

目标：

- route 文件不超过 220 行。
- 单个接口函数不超过 40 行。
- 超过即迁移到 use case。

### 3.3 Application 层规范

Application layer 是业务编排层，负责：

- 串联多个领域模块。
- 决定是否读缓存、是否提交任务、是否返回 partial error。
- 控制事务边界。
- 对前端 BFF 返回数据做裁剪。

示例：

- `MonitorUseCase.get_workspace()`
- `PlaybookUseCase.get_priority_board()`
- `HoldingsUseCase.save_holding()`
- `PaperTradingUseCase.submit_order()`
- `BacktestUseCase.enqueue_validation()`
- `FactorMiningUseCase.run_factor_experiment()`
- `AgentUseCase.score_and_publish_result()`

### 3.4 Domain 层规范

Domain 层负责核心业务规则：

- A 股 T+1。
- 持仓可用数。
- 正 T / 反 T 信号。
- 低吸策略。
- 主线涨停回调。
- 模拟交易撮合。
- 风控阻断。
- ML 生产晋级门槛。
- Agent 返回质量校验。

Domain 层禁止：

- 直接依赖 FastAPI。
- 直接返回前端 BFF 大对象。
- 直接读取环境变量。
- 随意创建 DB session。

### 3.5 Repository 与 UnitOfWork

必须补齐 repository：

- `AuthRepository`
- `UserSessionRepository`
- `WatchlistRepository`
- `HoldingRepository`
- `MarketSnapshotRepository`
- `LowBuyResultRepository`
- `StrategyMetadataRepository`
- `PaperAccountRepository`
- `PaperOrderRepository`
- `PaperPositionRepository`
- `BacktestRepository`
- `RuntimeTaskRepository`
- `FactorMiningRepository`
- `AgentAuditRepository`
- `SettingsRepository`

UnitOfWork 目标接口：

```python
with uow_factory() as uow:
    holdings = uow.holdings.list_by_user(user_id)
    result = domain_service.calculate(holdings)
    uow.holdings.save(result)
    uow.commit()
```

收益：

- 事务边界集中。
- 测试可以注入 fake repository。
- 后续拆服务时知道表归属。
- route/use case 不关心 SQLAlchemy 细节。

## 4. 领域模块最终拆分方案

### 4.1 Auth / User 模块

职责：

- 登录、注册、刷新 token。
- MFA。
- 用户角色。
- Session 撤销。
- Agent token。
- 管理员权限。

保留接口：

- `/api/auth/*`
- `/api/admin/users/*`

重构重点：

- token、cookie、MFA、Agent token 统一进入 `auth` domain。
- 高风险操作统一 `require_permission()`。
- 登录失败、锁定、异常登录进入审计。

性能要求：

- 登录接口不依赖外部服务。
- token 校验只做必要 DB 查询，优先 session hash / cache。

### 4.2 Market 模块

职责：

- 实时行情。
- 分时/K 线。
- 日线历史。
- 板块热度。
- 市场情绪。
- 涨跌停池。
- 数据源健康。
- Provider Router。

保留接口：

- `/api/market/*`
- `/api/quote/*`
- `/api/kline/*`
- `/api/instruments/*`

重构重点：

- 所有外部行情读取必须通过 `MarketDataProvider` interface。
- 禁止业务策略直接调用 `akshare`、`requests`、`subprocess`。
- `ProviderResult` 必须携带 `source`、`quality`、`latency_ms`、`stale`。
- quote、daily history、sector heatmap 分别建立缓存策略。

性能方案：

- 实时行情使用 batch API 优先。
- 热门股票池预热到 Redis。
- 分时/K 线按 symbol + period 缓存。
- 市场情绪 60-300 秒 TTL。
- 日线历史按交易日增量更新。

验收：

- 单个数据源失败不影响页面整体。
- Provider fallback 有指标。
- 同一批股票行情不出现 N 次重复外部请求。

### 4.3 Strategy / Low Buy 模块

职责：

- 低吸策略。
- 全策略优先级榜。
- 主线涨停回调。
- 策略参数版本。
- 策略治理。
- 生产/研究策略隔离。

保留接口：

- `/api/screeners/low-buy/*`
- `/api/strategy-meta/*`
- `/api/quant/parameters/*`

重构重点：

- 生产策略、研究策略、辅助因子强隔离。
- 策略参数全部从参数版本系统读取。
- 策略扫描分 fast path 和 full scan。
- 策略结果 materialized 到 DB/Redis。
- 前端榜单只读已物化结果，不触发重扫描。

性能方案：

- `priority-board` 默认读缓存。
- full scan 进入 worker。
- quote refresh 只刷新价格字段，不重算全部策略。
- 每个策略输出耗时、样本数、过滤数量、缓存命中。

验收：

- `/api/screeners/low-buy/priority-board?limit=12` warm path p95 < 500ms。
- full scan 不阻塞 API worker。
- Web/App 同一策略榜单一致。

### 4.4 Holdings / Watchlist 模块

职责：

- 自选股。
- 持仓。
- 成本价。
- 持仓数。
- 可用数。
- A 股 T+1 转换。
- 持仓做 T 信号。

保留接口：

- `/api/watchlist/*`
- `/api/app/home`

重构重点：

- 持仓写入必须通过 `HoldingsUseCase`。
- T+1 可用数转换由后端确定性任务完成。
- 保存持仓后统一失效缓存。
- App/Web 不再自行推断股票名称、可用数转换。

性能方案：

- 用户持仓列表 10-15 秒 Redis cache。
- 写操作乐观返回 + 异步补全行情/名称。
- 持仓信号定时刷新，页面读取快照。

验收：

- 新增持仓接口 p95 < 300ms，不等待慢行情。
- 第二个交易日自动可用数转换有测试。
- 删除持仓后 monitor/app 缓存立即失效。

### 4.5 Paper Trading 模块

职责：

- 模拟账户。
- 模拟订单。
- 撮合。
- 持仓。
- 手续费。
- 风控。
- 自动交易。
- 绩效归档。
- 回测 vs 模拟盘对比。

保留接口：

- `/api/paper/*`

重构重点：

- `paper/*` service 已经较多，需按 use case 收口。
- 下单、撤单、撮合、持仓更新必须同一个事务。
- 风控前置，不允许绕过。
- 自动交易只允许模拟盘。
- 所有订单必须有审计与幂等键。

性能方案：

- 账户摘要、持仓、流水分开缓存。
- 流水分页。
- 日终归档进 worker。
- 自动交易每轮限制扫描数量和订单数量。

验收：

- 下单失败不会产生半持仓。
- 费用计算有单测。
- 自动交易可暂停、可追踪、可回放。

### 4.6 Backtest / Research 模块

职责：

- 回测任务。
- Walk-forward。
- 样本外验证。
- 策略对比。
- 优化器。
- 结果归档。

保留接口：

- `/api/backtests/*`
- `/api/strategy-validation`

重构重点：

- 回测必须异步提交任务。
- API 只提交任务和读取状态。
- 回测结果与参数版本绑定。
- 大结果分 summary/detail，不在列表返回全量曲线。

性能方案：

- backtest worker 专用队列。
- 结果缓存和分页。
- 大图表数据按需加载。
- 重复参数 hash 命中缓存。

验收：

- 长回测不会阻塞 Web API。
- 任务状态可 SSE 推送。
- 相同参数可复用结果。

### 4.7 Factor / ML 模块

职责：

- 因子挖掘。
- 因子计算。
- 因子评价。
- 因子组合。
- ML 样本构建。
- LightGBM / Logistic 研究模型。
- 生产晋级门槛。

保留接口：

- `/api/factor-mining/*`
- `/api/ml/signals/*`

重构重点：

- 因子实验、研究模型、生产策略强隔离。
- 未验证模型不得进入生产建议。
- artifact 必须校验路径、hash、签名。
- 训练与推理必须记录数据版本和特征 schema hash。

性能方案：

- 因子计算进 worker。
- 因子值按 symbol/date/factor_version 缓存。
- 训练数据导出异步。
- ML 推理只读已训练 artifact。

验收：

- 低质量模型不能晋级 production。
- K-fold / time-series split 有测试。
- 因子实验失败不影响生产策略。

### 4.8 Agent / Hermes 模块

职责：

- Agent 上下文。
- Hermes/OpenClaw/其他 agent adapter。
- Agent 质量评分。
- Agent 审计。
- 飞书通知。
- 只读分析。

保留接口：

- `/api/agent/*`
- `/api/agent/quality/*`
- `/api/feishu/*`

重构重点：

- Agent 只能分析和解释，不能越权写交易。
- 所有 Agent 调用必须有输入摘要、输出摘要、耗时、质量分、失败原因。
- 外部 Agent 调用必须超时、降级、限流。
- Agent adapter 可替换。

性能方案：

- Agent 调用进入任务队列。
- 结果缓存。
- 低质量结果不推送。
- 飞书通知去重与冷却。

验收：

- Hermes 不可用时系统仍返回规则化 fallback。
- Agent 输出 schema 校验失败会被拦截。
- 所有 Agent 写能力默认关闭。

### 4.9 Settings / Admin / Ops 模块

职责：

- 运行时设置。
- 数据源配置。
- 因子权重。
- 诊断快照。
- 任务状态。
- 审计。
- 指标。

保留接口：

- `/api/settings/*`
- `/api/admin/*`
- `/metrics`

重构重点：

- 敏感配置统一加密。
- 运行时设置读取要有缓存和失效。
- `/metrics` 继续 admin token 保护。
- 生产设置变更必须有审计。

性能方案：

- 设置读取 Redis/local cache。
- 诊断慢检查异步。
- admin dashboard 不触发重任务。

## 5. 任务系统最终方案

### 5.1 最终选型

生产任务系统最终采用 Redis + Celery；现有 DB-backed `RuntimeTaskQueue` 保留为接口契约和本地 fallback。

选择理由：

- 项目已经有 Redis。
- Celery 是 Python 生态最成熟的任务队列之一，适合长任务、重试、定时任务、并发 worker、任务路由。
- 当前任务类型已经复杂：回测、全量扫描、日线刷新、Agent 分析、因子计算、ML 训练、飞书通知。
- DB queue 适合作为最小可行实现，但高频任务和多 worker 场景下会增加数据库写压力。

最终结构：

```text
RuntimeTask API
  -> TaskQueue Interface
     -> CeleryTaskQueueAdapter 生产
     -> DbTaskQueueAdapter 本地/降级

Celery Workers
  - market-refresh
  - strategy-scan
  - backtest
  - factor-ml
  - agent-notification
```

### 5.2 队列划分

`market-refresh`：

- 行情缓存刷新。
- 日线增量刷新。
- 市场情绪刷新。

`strategy-scan`：

- 全策略优先级榜 full scan。
- 策略物化结果更新。
- 策略治理。

`backtest`：

- 回测。
- 样本外验证。
- 参数优化。

`factor-ml`：

- 因子计算。
- 因子评价。
- 训练数据构建。
- ML 训练。

`agent-notification`：

- Agent 分析。
- 日报。
- 飞书推送。

### 5.3 API 与前端契约

保持现有 `/api/runtime-tasks` 形态：

- `POST /api/runtime-tasks`
- `GET /api/runtime-tasks`
- `GET /api/runtime-tasks/{id}`
- `GET /api/runtime-tasks/{id}/events`
- `GET /api/runtime-tasks/{id}/stream`

无论底层 DB queue 还是 Celery，前端只看 RuntimeTask 状态。

### 5.4 任务验收标准

- API 进程不执行全量扫描、回测、ML 训练。
- 任务失败有错误原因。
- 任务可重试。
- 任务有进度。
- 任务事件可 SSE 推送。
- worker crash 后任务能恢复或标记失败。

## 6. 缓存与性能方案

### 6.1 缓存分层

L1：进程内短 TTL cache

- 只用于极短时间内重复读取。
- TTL 1-30 秒。
- 不作为跨 worker 一致性依据。

L2：Redis cache

- 生产主缓存。
- 用于行情、榜单、BFF、设置、持仓快照、任务事件。

L3：MySQL materialized snapshot

- 用于全量策略结果、历史回测结果、因子值、模型样本。
- 可重建。
- 必须有版本和更新时间。

### 6.2 核心接口性能预算

建议 SLO：

| 接口/场景 | warm p95 | cold p95 | 说明 |
|---|---:|---:|---|
| `/readyz` | 100ms | 300ms | 只检查轻量依赖 |
| `/api/bff/v1/workspace/monitor` | 500ms | 1500ms | 读缓存 + partial error |
| `/api/app/home` | 500ms | 1200ms | App 首屏 |
| `/api/screeners/low-buy/priority-board` | 500ms | 2000ms | 不触发 full scan |
| `/api/watchlist/signals` | 600ms | 1500ms | 读快照优先 |
| 新增/编辑持仓 | 300ms | 800ms | 不等待慢行情 |
| 回测提交 | 300ms | 800ms | 只入队 |
| 因子实验提交 | 300ms | 800ms | 只入队 |

### 6.3 Fast path / Deep path

必须区分：

Fast path：

- 页面直接读取。
- 只读缓存/物化结果。
- 快速返回。
- 允许 `partial_errors`。

Deep path：

- 全量扫描。
- 历史回测。
- 因子评估。
- ML 训练。
- Agent 深度分析。
- 全部进入 worker。

### 6.4 数据库优化

必须建立索引审查清单：

- 用户维度：`user_id`。
- 标的维度：`symbol`。
- 时间维度：`trade_date`、`created_at`、`updated_at`。
- 任务维度：`status`、`task_type`、`run_after`、`active_idempotency_key`。
- 策略结果：`strategy_key`、`trade_date`、`rank`。
- 模拟盘：`account_id`、`symbol`、`order_status`、`trade_date`。
- 因子值：`factor_key`、`factor_version`、`symbol`、`trade_date`。
- Agent 审计：`agent_id`、`created_at`、`status`。

查询规范：

- 列表接口必须分页。
- 大 JSON 字段不进入列表接口。
- summary/detail 分离。
- 禁止 N+1 查询。
- 聚合统计优先预计算。

### 6.5 外部数据源优化

要求：

- 所有行情读取统一 Provider Router。
- 优先 batch。
- 单 provider 超时不超过 4 秒。
- 慢 provider 进入 slow executor。
- 失败触发 circuit breaker。
- 返回数据质量。

降级顺序：

1. Redis 最近快照。
2. 主数据源 fresh。
3. 备用数据源 fresh。
4. 本地缓存 stale。
5. 返回 unavailable + partial error。

## 7. 可观测与稳定性方案

### 7.1 日志

统一结构化字段：

- `request_id`
- `user_id`
- `route`
- `duration_ms`
- `status_code`
- `domain`
- `operation`
- `data_source`
- `cache_hit`
- `task_id`
- `agent_id`

禁止：

- 日志输出 token、API key、secret、cookie。
- 大量打印完整行情列表。
- Agent 原始完整输入输出无脱敏落日志。

### 7.2 Metrics

必须补齐指标：

- API 请求数、错误数、p50/p95/p99。
- 每个 BFF 接口耗时。
- Provider 调用数、失败数、熔断数、慢调用数。
- Redis cache hit/miss。
- Runtime task queued/running/failed/succeeded。
- Worker 任务耗时。
- 策略扫描耗时、候选数量、过滤数量。
- 持仓保存耗时。
- 模拟盘下单失败率。
- Agent 调用成功率、质量拦截数。
- ML 模型晋级拦截数。

### 7.3 告警

P0 告警：

- `/readyz` 失败。
- MySQL 不可用。
- Redis 不可用。
- Runtime worker 超过 10 分钟无心跳。
- 任务失败数 5 分钟内突增。
- Provider 全部不可用。
- 持仓保存错误率 > 5%。

P1 告警：

- priority-board p95 > 2s。
- App home p95 > 1.5s。
- 缓存命中率低于 60%。
- Agent 质量拦截率异常升高。
- 回测 vs 模拟盘偏差 > 20%。

## 8. 安全与权限方案

### 8.1 API 安全

必须保持：

- HTTP 安全头。
- CORS 白名单。
- request body limit。
- admin token。
- auth secret 强校验。
- settings encryption key。
- Agent token。
- 操作审计。

需要加强：

- 所有内部服务调用必须 `X-Internal-Service-Token`。
- BFF 不允许绕过权限。
- Agent write tools 默认关闭。
- 任务提交接口必须做类型白名单和权限校验。
- 文件路径类字段必须 resolve 到允许目录。
- 模型 artifact 必须 hash 校验。

### 8.2 资金安全边界

当前项目只做模拟盘，不接真实交易。

原则：

- 任何 Agent/ML/策略输出都只能生成建议或模拟盘动作。
- 模拟交易也必须经过后端风控。
- 不允许前端构造绕过风控的订单。
- 不允许外部 Agent 直接写 paper order 表。

## 9. 代码质量重构规范

### 9.1 文件大小约束

建议上限：

- route 文件：220 行。
- application use case：260 行。
- domain service：260 行。
- repository：260 行。
- worker task：180 行。
- schema 文件：按领域拆分，单文件不超过 300 行。

优先拆分当前大文件：

- `backend/app/api/routes/backtests.py`
- `backend/app/api/routes/agent.py`
- `backend/app/api/routes/agent_helpers.py`
- `backend/app/main.py`
- `backend/app/services/ml_signal/service.py`
- `backend/app/services/quant/parameter_version_service.py`
- `backend/app/services/paper/scheduler.py`
- `backend/app/runtime/background_jobs.py`
- `backend/app/services/market/intraday.py`
- `backend/app/services/market/quotes.py`
- `backend/app/services/low_buy/*` 中超过 350 行且职责混合的模块。

### 9.2 模块深度要求

每个 Module 必须有明确 Interface：

- 输入。
- 输出。
- 错误模式。
- 缓存语义。
- 事务语义。
- 超时语义。
- 降级语义。

删除测试：

- 如果删除某个 Module 后复杂度只是散落到调用方，说明它是深模块，应保留。
- 如果删除某个 Module 后复杂度也消失，说明它是浅模块，应合并。

### 9.3 公共能力抽取

必须统一：

- 错误响应。
- 分页参数。
- `partial_errors`。
- `data_quality`。
- `request_id`。
- `idempotency_key`。
- cache key 命名。
- task event 格式。
- user permission 校验。
- datetime/timezone。
- price/amount/percent 格式化。

## 10. 实施路线图

### P0：稳定现有生产路径

目标：

- 不改变接口行为，先收口性能和稳定性。

任务：

- 建立后端重构 ADR 或实施说明。
- 明确 Web API 进程禁止执行长任务。
- 给 priority-board、app/home、watchlist/signals 建立性能基线。
- 补齐 cache key 规范。
- 补齐 request timing 指标。
- 统一 BFF 响应 `generated_at`、`partial_errors`、`data_quality`。

验收：

- 当前测试通过。
- 核心接口 warm path 有耗时记录。
- 生产部署不变。

### P1：Application Layer 与 Repository 补齐

目标：

- route 不再直接编排复杂业务。
- 数据访问集中。

任务：

- 新增 `application/*_use_case.py`。
- 新增 `repositories/unit_of_work.py`。
- 先迁移 holdings/watchlist、monitor、playbook 三条高频链路。
- 把 route 中复杂逻辑迁移到 use case。
- 保存持仓、删除持仓、榜单读取、监控 BFF 完成 repository 化。

验收：

- route 文件明显变薄。
- 相关 use case 可用 fake repository 单测。
- Web/App 行为不变。

### P2：任务系统生产化

目标：

- 长任务与 API 进程彻底解耦。

任务：

- 定义 `TaskQueueAdapter` interface。
- 保留 `DbTaskQueueAdapter`。
- 新增 `CeleryTaskQueueAdapter`。
- 将 full scan、回测、因子挖掘、Agent 深度分析迁移到 Celery 队列。
- RuntimeTask 状态仍写回 MySQL。
- SSE/Redis PubSub 继续提供任务事件。

验收：

- API 提交任务 < 300ms。
- worker crash 后任务可恢复。
- 任务进度前端可见。

### P3：缓存与物化结果标准化

目标：

- 页面读缓存，重计算进 worker。

任务：

- 建立 `CacheAdapter` interface。
- L1 memory + L2 Redis。
- priority-board、market regime、watchlist signals、app home、settings runtime 使用统一 cache。
- 全策略 full scan 结果物化。
- Redis 缓存失效由 mutation 统一触发。

验收：

- priority-board warm p95 < 500ms。
- App home warm p95 < 500ms。
- 删除/编辑持仓后缓存立即失效。

### P4：领域模块瘦身

目标：

- 拆分过大 service，形成稳定领域接口。

任务：

- `low_buy` 拆成 strategy config、candidate loading、scoring、risk、materialization、response projection。
- `paper` 拆成 account/order/matching/position/risk/performance/scheduler。
- `market` 拆成 provider、cache、quote、history、regime、sector。
- `agent` 拆成 context、runtime adapter、quality、audit、notification。
- `ml_signal` 拆成 sample、training、artifact、promotion、inference。

验收：

- 超 400 行核心文件减少。
- 新增测试只测 interface，不测内部实现细节。

### P5：可独立部署服务准备

目标：

- 不立即拆服务，但具备一键替换 adapter 能力。

任务：

- 固化 `market-service`、`strategy-service`、`trade-service`、`factor-service` 内部契约。
- BFF remote adapter 覆盖核心 workspace。
- 内部服务统一 `/internal/*` 契约。
- 服务 token、超时、熔断、partial error 标准化。

验收：

- URL 配置为空时本地 adapter。
- URL 配置后远程 adapter。
- 远程失败自动 fallback。
- 前端响应结构不变。

## 11. 测试策略

### 11.1 必补单测

- Holdings T+1 可用数转换。
- Holdings 保存/删除缓存失效。
- Strategy priority-board cache hit/miss。
- Provider Router fallback。
- RuntimeTask 状态流转。
- Paper order 事务一致性。
- Agent quality block。
- ML promotion block。

### 11.2 集成测试

- `/api/bff/v1/workspace/monitor`
- `/api/app/home`
- `/api/screeners/low-buy/priority-board`
- `/api/watchlist/signals`
- `/api/paper/*`
- `/api/runtime-tasks/*`
- `/api/factor-mining/*`

### 11.3 性能测试

必须记录：

- cold latency。
- warm latency。
- cache hit rate。
- DB query count。
- external provider fan-out。
- worker queue time。

### 11.4 回归命令

后端：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
```

迁移：

```bash
DATABASE_URL=sqlite:////tmp/tquant_migration_check.db PYTHONPATH=backend:. backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
```

生产镜像：

```bash
docker compose -f docker-compose.mysql.yml build
docker compose -f docker-compose.mysql.yml up -d migration app runtime-worker backtest-worker
```

Smoke：

```bash
curl -i http://127.0.0.1:18090/readyz
curl -i http://127.0.0.1:18090/api/bff/v1/manifest
```

## 12. 给 Codex 的执行需求文档

### 12.1 角色

你是 TQuant 项目的资深后端架构师、性能优化工程师、量化交易系统工程师和 DevOps 负责人。请基于当前仓库完成后端服务最终重构优化，目标是在不破坏现有 Web/App/API 的前提下，把当前 FastAPI 后端升级为可扩展、高性能、易测试、可观测、可渐进拆服务的模块化架构。

### 12.2 强制约束

1. 不允许推倒重写。
2. 不允许破坏现有接口响应结构。
3. 不允许绕过现有风控。
4. 不允许接真实券商实盘交易。
5. 不允许让 API 进程执行全量扫描、回测、ML 训练、Agent 深度分析等长任务。
6. 不允许生产启动依赖 `schema_compat` 自动修表。
7. 不允许业务策略直接调用 AkShare、requests 或外部数据源。
8. 不允许 route 直接写复杂业务逻辑。
9. 不允许新增无测试的核心交易/策略/任务逻辑。
10. 不允许日志泄露 token、secret、cookie、Agent key。
11. 不允许前端直接访问内部领域服务。
12. 不允许研究策略或未验证 ML 模型进入生产交易建议。

### 12.3 第一批任务

1. 建立后端分层骨架：
   - `backend/app/application/`
   - `backend/app/repositories/unit_of_work.py`
   - `backend/app/adapters/cache/`
   - `backend/app/adapters/task_queue/`

2. 先迁移三条高频链路：
   - 实时监控 BFF。
   - 选股宝典 priority-board。
   - 持仓新增/编辑/删除。

3. 对这三条链路做到：
   - route 只调 use case。
   - use case 负责编排。
   - repository 负责 DB。
   - cache adapter 负责 Redis/内存缓存。
   - mutation 统一失效缓存。

4. 补充性能指标：
   - 接口耗时。
   - cache hit/miss。
   - provider fan-out。
   - priority-board 计算耗时。

5. 补充测试：
   - use case 单测。
   - BFF 契约测试。
   - cache invalidation 测试。
   - T+1 持仓测试。

### 12.4 第二批任务

1. 定义 `TaskQueueAdapter`。
2. 保留 DB queue adapter。
3. 引入 Celery + Redis production adapter。
4. 迁移 full scan、backtest、factor mining、Agent deep analysis。
5. RuntimeTask API 保持不变。
6. Redis PubSub / SSE 继续推送任务进度。

### 12.5 第三批任务

1. 统一 Market Provider Router 调用。
2. 禁止策略/服务直接访问 AkShare。
3. 拆分 `low_buy`、`paper`、`market`、`ml_signal` 中过大的文件。
4. 补齐 repository 覆盖。
5. 删除或下沉浅模块。
6. 建立领域接口文档。

### 12.6 验收标准

必须满足：

- 现有后端测试通过。
- Alembic 空库升级通过。
- Web/App 当前核心接口不破坏。
- API 进程不跑长任务。
- priority-board warm path p95 < 500ms。
- App home warm path p95 < 500ms。
- 持仓保存 p95 < 300ms。
- 任务失败可追踪。
- Provider 失败可降级。
- Redis 不可用时有明确降级或错误。
- Prometheus 能看到核心指标。

### 12.7 输出要求

每个阶段完成后输出：

- 已完成模块。
- 修改文件。
- 删除旧逻辑。
- 接口兼容性说明。
- 数据库迁移说明。
- 性能数据。
- 测试结果。
- 未完成风险。
- 下一步建议。

## 13. 最终判断

后端服务需要重构，但正确路线不是更换技术栈，而是对现有 FastAPI 单体做工程化升级：

- 短期：稳定核心接口、压缩慢路径、补齐 BFF/use case/repository/cache。
- 中期：长任务进入 Celery/Redis worker，策略结果物化，行情和榜单进入统一缓存。
- 长期：在单体内固定领域 interface 后，再按市场、策略、交易、因子、Agent 拆成可独立部署服务。

这样可以同时满足：

- Web/App 前端重构需要的稳定 BFF。
- A 股策略迭代需要的高性能数据链路。
- 模拟盘、回测、Agent、因子挖掘需要的异步能力。
- 云服务器长期运行需要的可观测、可恢复和可扩展性。
