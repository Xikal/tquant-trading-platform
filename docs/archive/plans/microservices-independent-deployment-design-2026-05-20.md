# TQuant 独立部署与微服务拆分设计

## 目标

在不破坏 Web/App 现有调用的前提下，将当前 FastAPI 单体逐步演进为“同源 BFF + 领域 service seam + 可独立部署服务”的架构。第一阶段不直接拆数据库和进程，先把接口契约和领域 seam 固定下来。

## 当前已落地 seam

| Seam | 当前 Adapter | 调用方 | 后续可抽离服务 |
|---|---|---|---|
| `MonitorWorkspaceBFF` | 远程 HTTP adapter + 本地 route 聚合 fallback | Web 实时监控 | `market-service` + `strategy-service` |
| `PaperWorkspaceBFF` | 远程 HTTP adapter + `services/bff/paper_workspace.py` fallback | Web 模拟盘 / App 可复用 | `trade-service` |
| `StrategyWorkspaceBFF` | 远程 HTTP adapter + `services/bff/strategy_workspace.py` fallback | 策略工作台 | `strategy-service` + `backtest-service` |
| `SettingsWorkspaceBFF` | 远程 HTTP adapter + `services/bff/settings_workspace.py` fallback | 系统配置页 | `config-service` + `admin-service` |
| `SettingsRuntimeDiagnosticsService` | 本地 DB + env 诊断 | 设置页 / 运行诊断 | `admin-service` |
| `SettingsFactorWeightsService` | 因子权重注册表 | 设置页 / 策略评分 | `factor-service` |

## 拆分原则

- Web/App 只调用 `/api/bff/v1/workspace/*` 或稳定的领域 API，不直接依赖多个底层接口的组合顺序。
- 每个领域 service 先在单体内拥有清晰 interface，再替换为 HTTP/gRPC adapter。
- 独立服务不得直接读写其他领域表，只能通过契约 API 或事件同步。
- BFF 负责响应体裁剪和 partial error，不把某个领域失败扩散成整页失败。
- 所有跨服务写操作必须保留操作审计和幂等键。

## 推荐服务边界

### `auth-service`

职责：登录、刷新 token、MFA、用户角色、Agent token。

第一阶段 seam：`AuthService`、`role_permissions`、`agent_auth`。

### `market-service`

职责：行情、日线、分时、市场情绪、板块、Provider Router、数据质量。

第一阶段 seam：`MarketDataService`、`ProviderRouter`、`latest_data_status`。

### `strategy-service`

职责：低吸策略、全策略优先级榜、选股宝典、策略元数据、策略治理。

第一阶段 seam：`LowBuyScreenerService`、`StrategyMetadataService`、`StrategyWorkspaceBFF`。

### `backtest-service`

职责：回测任务、优化、样本外验证、任务进度、结果归档。

第一阶段 seam：`BacktestJobService`、`BacktestOptimizationService`、`RuntimeTaskQueue`。

### `trade-service`

职责：模拟盘账户、订单、成交、持仓、风控、自动委托、账本对账。

第一阶段 seam：`PaperWorkspaceBFF`、`paper/*` services。

### `factor-service`

职责：因子实验室、因子评估、生产因子激活、因子值缓存、ML 信号模型。

第一阶段 seam：`factor_mining/*`、`SettingsFactorWeightsService`、`ml_signal/*`。

### `admin-service`

职责：运行诊断、后台任务、数据源探针、配置、审计、部署预检。

第一阶段 seam：`SettingsRuntimeDiagnosticsService`、`settings_admin_snapshot`。

## 部署阶段

### Phase 0：单体内 seam 固化

- BFF endpoint 覆盖主要页面：monitor / paper / strategy / settings。
- 前端优先读取 BFF，失败时保留旧接口 fallback。
- 领域 service 不再直接写在 route 内。

验收：

- 前端构建通过。
- BFF route 单测通过。
- 旧接口仍可调用。

### Phase 1：独立 worker 先拆

- `runtime-worker` 独立运行回测、全量扫描、日线刷新、策略自进化。
- Web 进程只读缓存和提交任务，不执行重计算。

验收：

- 多 worker 下不会重复跑预热/扫描。
- runtime task 有进度和失败原因。

### Phase 2：只读服务抽离

优先抽离 `market-service` 和 `strategy-service` 的只读接口：

- `GET /market/breadth`
- `GET /market/quotes`
- `GET /strategy/priority-board`
- `GET /strategy/playbook`

BFF 增加 HTTP adapter，保留本地 adapter 作为 fallback。

验收：

- BFF adapter 切换不影响前端响应结构。
- 单个服务失败只产生 partial error。

当前状态：

- `services/bff/remote_client.py` 已提供统一 HTTP 调用、内部 token 和用户鉴权 header 转发。
- `services/bff/remote_adapters.py` 已覆盖 monitor / paper / strategy / settings 四个 workspace。
- 远端服务未配置或请求失败时，BFF 自动回退到单体内本地 adapter，保持前端接口稳定。

### Phase 3：写服务抽离

抽离 `trade-service` 和 `config-service` 写接口：

- 模拟盘下单、撤单、对账修复。
- 设置保存、因子权重、策略治理。

验收：

- 写操作全链路审计。
- 幂等键和事务边界明确。
- 失败不会产生半更新状态。

## API Gateway 契约

对外稳定入口仍为：

- `/api/bff/v1/workspace/monitor`
- `/api/bff/v1/workspace/paper`
- `/api/bff/v1/workspace/strategy`
- `/api/bff/v1/workspace/settings`

内部服务可演进为：

- `/internal/market/v1/*`
- `/internal/strategy/v1/*`
- `/internal/backtest/v1/*`
- `/internal/trade/v1/*`
- `/internal/factor/v1/*`
- `/internal/admin/v1/*`

## 配置与部署

已纳入 `AppSettings` 的环境变量：

```env
TQUANT_MARKET_SERVICE_URL=
TQUANT_STRATEGY_SERVICE_URL=
TQUANT_BACKTEST_SERVICE_URL=
TQUANT_TRADE_SERVICE_URL=
TQUANT_FACTOR_SERVICE_URL=
TQUANT_ADMIN_SERVICE_URL=
TQUANT_INTERNAL_SERVICE_TOKEN=
TQUANT_SERVICE_CALL_TIMEOUT_SECONDS=5
```

当 URL 为空时使用本地 adapter；配置 URL 后 BFF 使用远程 adapter。

## 风险控制

- 不先拆数据库。先通过 service interface 限制跨域访问，再决定表归属。
- 不一次性替换所有前端调用。BFF 优先，旧接口 fallback。
- 不把研究能力直接暴露到生产交易链路。factor/ML 必须保留激活开关和审计。
- 不让 BFF 做重计算。BFF 只聚合、裁剪、降级。

## 下一步

1. 将 runtime-worker 从 Compose 层与 Web 进程明确隔离。
2. 抽离 `market-service` 只读远程 adapter 做第一条真实微服务试点。
3. 为远端服务增加 `/internal/healthz` 和契约测试。
4. 在生产维护窗口逐步配置各 `TQUANT_*_SERVICE_URL`，观察 fallback 命中率和延迟。
