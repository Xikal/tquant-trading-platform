# TQuant 前后端架构拆分实施记录

## 目标

将当前单体后端逐步演进为 `React SPA + BFF + 领域服务` 的三层架构。迁移必须保持现有 Web/App/API 兼容，不直接拆库、不绕过现有风控、不影响模拟盘与策略链路。

## 本轮已落地

1. 新增 BFF seam：`/api/bff/v1`。
2. 新增 BFF manifest：`GET /api/bff/v1/manifest`，明确 BFF 版本、API Gateway 前缀和领域模块。
3. 新增监控页聚合接口：`GET /api/bff/v1/workspace/monitor`。
4. 新增模拟盘首屏聚合接口：`GET /api/bff/v1/workspace/paper`。
5. 新增策略工作台首屏聚合接口：`GET /api/bff/v1/workspace/strategy`。
6. 前端实时监控、模拟盘初始加载、策略工作台初始加载改为优先调用 BFF 聚合接口，减少多路并发请求。
7. 保留原 `/api/monitor/*`、`/api/market/*`、`/api/paper/*`、`/api/backtests/*`、`/api/v1/*`，避免破坏 App/Web 旧调用。

## 当前分层

```text
React SPA / App
  -> /api/bff/v1/*        前端专属聚合接口
  -> /api/v1/*            稳定业务 API
  -> /api/*               兼容旧接口
FastAPI Gateway
  -> auth / market / strategy / trade / factor 领域模块
DB / Provider Router / Runtime Workers
```

## 后续拆分顺序

### Phase 1：BFF 完整化

1. 监控页、模拟盘首页、策略工作台首页已增加 BFF 聚合接口。
2. 下一步将设置页首屏增加 BFF 聚合接口。
2. 所有 BFF 响应增加 `api_version`、`generated_at`、`partial_errors`。
3. 前端页面优先读 BFF，旧 API 只保留为细节页和兼容路径。

### Phase 2：领域服务 seam

1. `auth-service`：抽出用户、会话、MFA、权限校验模块接口。
2. `market-service`：抽出行情、K 线、分时、板块、情绪接口。
3. `strategy-service`：抽出低吸、优先榜、回测、策略治理接口。
4. `trade-service`：抽出模拟账户、委托、持仓、成交、风控接口。
5. `factor-service`：抽出因子挖掘、因子评估、模型晋级接口。

### Phase 3：独立部署

1. 先拆无状态、低风险服务：`factor-service`、`market-service`。
2. 再拆状态一致性要求高的服务：`strategy-service`、`trade-service`。
3. 最后拆 `auth-service`，前提是统一 token introspection 和 session revocation 已稳定。

## 禁止事项

1. 不允许一次性把交易、策略、账户表拆到多个库。
2. 不允许 BFF 绕过后端风控或权限。
3. 不允许前端直接访问领域服务公网地址。
4. 不允许研究策略或未验证 ML 模型通过 BFF 混入生产建议。

## 验收标准

1. BFF 接口任一子数据源失败时，返回 `partial_errors`，页面不白屏。
2. 原 API 路径仍可用。
3. 前端构建通过。
4. 后端编译和 BFF 路由测试通过。
5. `qa_smoke.sh` 通过。
