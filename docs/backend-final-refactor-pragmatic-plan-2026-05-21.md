# TQuant 后端最终重构方案（务实版）

生成日期：2026-05-21
定位：最终开发执行版，不做过度架构，不推倒重写。

## 1. 最终结论

当前后端需要重构，但不需要大改架构。

最终选择：

- 保留 `FastAPI + SQLAlchemy + Alembic + MySQL + Redis + Docker Compose`。
- 保留当前单体后端，不拆微服务。
- 保留现有 `app / runtime-worker / backtest-worker / migration` 进程结构。
- 保留现有 DB-backed `RuntimeTaskQueue`，先增强，不急着换 ARQ/Celery。
- 保留现有 BFF，优先让前端只读稳定 BFF。
- 重构重点放在：数据库配置、缓存、任务稳定性、核心模块分层、慢接口优化、测试兜底。

不做：

- 不上微服务。
- 不拆数据库。
- 不引入 InfluxDB/TDengine。
- 不引入读写分离。
- 不引入 OpenTelemetry。
- 不把所有同步代码改 async。
- 不大规模迁移所有 Float 字段。
- 不把任务队列马上换成 ARQ/Celery。

理由：

- 当前项目主要是单用户/小规模交易辅助平台，现阶段瓶颈不是架构不够“大”，而是核心链路缺少统一缓存、任务隔离、配置化和模块边界。
- 过度引入新基础设施会增加维护成本，反而拖慢落地。
- 先把现有系统整理稳定，比追求“金融级全套架构”更适合当前阶段。

## 2. 当前最值得修的 8 件事

### 2.1 MySQL 和 Redis 生产配置补齐

问题：

- MySQL 连接池参数硬编码。
- MySQL 缺少可配置的 InnoDB 参数、慢查询日志。
- Redis 只有 `appendonly yes`，持久化和重写策略不完整。
- 缺少数据库自动备份。

处理：

- 将 DB 连接池配置移到环境变量。
- `docker-compose.mysql.yml` 增加可配置 MySQL 参数。
- Redis 增加 AOF/RDB 配置。
- 增加每日 MySQL 备份服务。
- 开启慢查询日志。

不做：

- 不做 MySQL 主从。
- 不做读写分离。
- 不做自动切主。

验收：

- 生产可通过环境变量调整连接池和 MySQL 参数。
- 慢查询日志可见。
- 每天有备份文件。
- Redis 重启后能按预期恢复。

### 2.2 核心接口缓存标准化

优先接口：

- `/api/bff/v1/workspace/monitor`
- `/api/app/home`
- `/api/screeners/low-buy/priority-board`
- `/api/watchlist/signals`

处理：

- 统一 Redis 缓存层。
- 统一 cache key 命名。
- 持仓新增/编辑/删除后主动失效相关缓存。
- 策略参数变更后主动失效榜单缓存。
- BFF 返回 `generated_at`、`data_quality`、`partial_errors`。

不做：

- 不让 BFF 重算策略。
- 不让前端触发全量扫描。

验收：

- priority-board warm p95 小于 500ms。
- app/home warm p95 小于 500ms。
- 删除/编辑持仓后 App/Web 数据能及时更新。

### 2.3 长任务全部留在 worker，不进 API 进程

长任务包括：

- 全量筛选。
- 回测。
- 因子挖掘。
- ML 训练。
- Agent 深度分析。
- 飞书日报/通知扫描。

处理：

- 继续使用现有 `RuntimeTaskQueue`。
- 强化任务状态、重试、失败原因、心跳。
- API 进程只提交任务和查询状态。
- runtime-worker/backtest-worker 执行任务。

暂不做：

- 不马上换 ARQ/Celery。
- 不新增任务基础设施。

触发升级条件：

- 单机 DB 队列成为瓶颈。
- 任务并发明显增加。
- 需要多机器 worker。

验收：

- API 提交任务小于 300ms。
- 任务失败可见。
- Worker 重启后不会长期卡住 running 状态。

### 2.4 替换 fcntl leader lock

问题：

- `fcntl` 文件锁跨平台和容器场景不稳定。

处理：

- 用 Redis `SET NX EX` 做 leader lock。
- Redis 不可用时，生产环境不运行 leader 任务，避免双主。
- 本地开发可以 fallback 文件锁。

验收：

- 多 worker 同时启动只会有一个 leader。
- leader 异常退出后，锁过期可接管。

### 2.5 Repository / UseCase 只先改核心链路

不做全项目大搬迁。

先改 3 条链路：

1. 持仓新增/编辑/删除。
2. 实时监控 BFF。
3. 选股宝典 priority-board。

目标结构：

```text
route
  -> use_case
  -> repository
  -> db/cache/provider
```

处理：

- route 只做参数、鉴权、调用 use case。
- use case 负责业务编排和缓存失效。
- repository 负责 DB。

暂不做：

- 不把所有 service 迁移到 repository。
- 不机械搬目录。

验收：

- 核心 route 明显变薄。
- 持仓保存、榜单读取、监控 BFF 有单测。
- 旧接口响应结构不变。

### 2.6 修复最明显的慢查询和批量写入

优先：

- `daily_bar_snapshots(symbol, trade_date)` 索引。
- priority-board / low-buy 快照查询索引。
- paper trades 大列表改分页或 keyset pagination。
- low-buy 扫描结果批量写入。

处理：

- 增加缺失索引。
- 全量扫描保存结果用 bulk insert / upsert。
- 列表接口只查需要字段。
- 大响应 summary/detail 分离。

暂不做：

- 不做全库字段类型大迁移。
- 不做分区表。
- 不做时序数据库。

验收：

- 慢查询日志中核心接口明显减少。
- 全量扫描写入速度提升。
- 回测列表和交易流水不会一次返回超大 JSON。

### 2.7 金额和交易相关字段优先 Decimal，行情字段暂不大迁移

务实判断：

- 模拟盘账户、订单、成交、手续费、现金、持仓成本必须用 `Numeric/Decimal`。
- 当前 `paper_entities.py` 已经大部分做对了。
- 日线/分钟线 OHLCV 用 Float 会有精度问题，但短期不是最大风险；全量迁移成本高，容易影响策略、回测、缓存和前端序列化。

处理：

- 先审查 paper/backtest 中金额、手续费、现金、成本价字段。
- 交易账本相关字段必须 Decimal。
- 后续如果回测精度确实受影响，再对行情表做分阶段迁移。

暂不做：

- 不在第一阶段迁移所有 OHLCV Float。
- 不在第一阶段迁移所有 String 日期。

验收：

- 模拟盘资金、手续费、成本价计算无浮点误差。
- 回测结果序列化保持兼容。

### 2.8 日志和指标补齐，不上复杂链路追踪

处理：

- 生产开启 `STRUCTURED_LOGS=true`。
- 日志增加 `request_id`、`user_id`、`route`、`duration_ms`、`task_id`、`symbol`、`strategy_key`。
- BFF 远端调用透传 `X-Request-ID`。
- Prometheus 增加 BFF 耗时、缓存命中、任务失败、Provider 失败、策略扫描耗时。

暂不做：

- 不上 OpenTelemetry。
- 不上 Jaeger/Tempo。
- 不上 ELK/Loki 强依赖。

验收：

- 任一请求能通过 request_id 关联 API 日志。
- 慢接口能定位到 route。
- worker 失败能在 metrics 和日志里看到。

## 3. 最终目标架构

保持当前部署形态：

```text
Web / App / Agent
        |
        v
FastAPI App
  - Auth
  - BFF
  - Stable API
  - Audit
  - Metrics
        |
        v
UseCase Layer（逐步补）
        |
        v
Service / Domain Logic（保留现有）
        |
        v
Repository（只先覆盖核心链路）
        |
        v
MySQL / Redis / Provider Router

runtime-worker
  - 策略扫描
  - 通知
  - 缓存刷新

backtest-worker
  - 回测
  - 验证
```

目录演进：

```text
backend/app
├── api/routes              # 保留，逐步瘦身
├── application             # 新增，只放核心 use case
├── repositories            # 增强，只先覆盖核心链路
├── services                # 保留现有领域服务
├── adapters
│   ├── cache               # Redis cache adapter
│   └── lock                # Redis leader lock
├── workers                 # 保留现有 worker
├── models
└── core
```

## 4. 实施路线

### Phase 0：低风险生产加固，1 周

目标：不改业务逻辑，先增强生产稳定性。

任务：

- DB 连接池配置化。
- MySQL 参数环境变量化。
- Redis 持久化参数补齐。
- MySQL 自动备份。
- BFF 远端调用透传 `X-Request-ID`。
- 结构化日志字段增强。
- 核心接口性能基线记录。

验收：

- 后端测试通过。
- Alembic 空库升级通过。
- Docker Compose 能启动。
- `/readyz` 正常。
- 慢查询日志和备份可用。

### Phase 1：核心缓存与持仓链路，1-2 周

目标：提升 App/Web 最常用页面速度。

任务：

- 新增 Redis cache adapter。
- monitor BFF 加缓存。
- app/home 加缓存。
- priority-board 加缓存。
- watchlist/signals 加缓存。
- 持仓新增/编辑/删除后统一失效缓存。
- 新增 HoldingsUseCase + WatchlistRepository。

验收：

- app/home warm p95 < 500ms。
- priority-board warm p95 < 500ms。
- 持仓保存 p95 < 300ms。
- Web/App 数据一致。

### Phase 2：任务与锁稳定化，1-2 周

目标：后台任务不乱跑、不重复跑、失败可见。

任务：

- Redis leader lock 替换 fcntl。
- RuntimeTaskQueue 增强 stale recovery。
- 任务失败原因标准化。
- worker 心跳和 metrics。
- 全量扫描、通知、缓存刷新都走 worker。

验收：

- 多 worker 无重复 leader。
- running 卡死任务能恢复或失败。
- 任务失败有原因。

### Phase 3：慢查询与批量写入，2-3 周

目标：降低数据库压力。

任务：

- 补关键索引。
- low-buy 扫描结果批量 upsert。
- 回测/交易流水列表分页优化。
- Paper 关键路径 N+1 修复。
- 大响应 summary/detail 分离。

验收：

- 慢查询明显减少。
- 扫描结果写入速度提升。
- 大列表接口不会返回超大 JSON。

### Phase 4：核心模块瘦身，持续做

目标：降低维护成本，不做全量重构。

优先拆：

- `paper/scheduler.py`
- `backtests.py`
- `agent.py`
- `ml_signal/service.py`

拆分原则：

- 只拆正在频繁修改或容易出 bug 的文件。
- 不为了目录好看而搬代码。
- 每次拆分必须有测试。

验收：

- 核心文件行数下降。
- 行为不变。
- 测试覆盖不降低。

## 5. 明确不纳入当前最终方案的内容

这些不是现在不重要，而是当前阶段不划算：

- 微服务拆分。
- MySQL 读写分离。
- InfluxDB/TDengine。
- OpenTelemetry/Jaeger。
- ARQ/Celery 替换现有任务队列。
- 全库 Float → Decimal。
- 全库 String 日期 → Date。
- 全面 async SQLAlchemy。
- 多租户架构。
- 真实券商交易。

触发条件：

- 日活用户明显上升。
- 多机器 worker 变成刚需。
- MySQL 单库成为明确瓶颈。
- 分钟线数据量真的达到千万级以上。
- 因子/回测任务并发显著增加。

到那时再单独做二期架构升级。

## 6. 验收指标

| 指标 | 目标 |
|---|---:|
| `/readyz` | < 300ms |
| monitor BFF warm p95 | < 500ms |
| app/home warm p95 | < 500ms |
| priority-board warm p95 | < 500ms |
| 持仓保存 p95 | < 300ms |
| 任务提交 p95 | < 300ms |
| API 进程长任务 | 0 |
| MySQL 自动备份 | 每天 1 次 |
| 失败任务可追踪 | 100% |
| 结构化日志核心链路覆盖 | 100% |

## 7. 给 Codex 的最终执行提示词

```text
你是 TQuant 项目的资深后端工程师和性能优化工程师。请按 docs/backend-final-refactor-pragmatic-plan-2026-05-21.md 执行后端务实重构。

要求：
1. 不推倒重写。
2. 不拆微服务。
3. 不引入 InfluxDB、读写分离、OpenTelemetry、ARQ/Celery。
4. 不改现有 Web/App API 响应结构。
5. 不接真实券商交易。
6. 不让 API 进程执行全量扫描、回测、ML 训练、Agent 深度分析。
7. 先做低风险生产加固，再做核心缓存，再做任务稳定，再做慢查询和局部模块瘦身。
8. 每次只改一个阶段，改完必须跑测试。

第一阶段先做 Phase 0：
- DB 连接池配置化。
- MySQL 参数环境变量化。
- Redis 持久化参数补齐。
- MySQL 自动备份。
- BFF 远端调用透传 X-Request-ID。
- 结构化日志字段增强。
- 核心接口性能基线记录。

验证：
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
DATABASE_URL=sqlite:////tmp/tquant_migration_check.db PYTHONPATH=backend:. backend/.venv/bin/alembic -c backend/alembic.ini upgrade head

输出：
- 完成项
- 修改文件
- 接口是否兼容
- 部署影响
- 测试结果
- 未完成风险
```

## 8. 最终一句话

后端最终方案不是“上大架构”，而是把现有 FastAPI 单体做扎实：配置可控、缓存统一、长任务隔离、核心链路分层、慢查询可见、失败可追踪。这样最适合当前 TQuant 项目的阶段，也最容易落地。
