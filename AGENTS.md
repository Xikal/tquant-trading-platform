# 多 Agent 协作编排（优化版）

## 总控角色

### `trading-platform-supervisor`

- 负责全局排期、风险升级与跨角色决策。
- 对里程碑负责：策略可用、产品可用、工程可用、部署可用。

## 执行顺序（已调整）

1. `trading-quant-lead`（新增，排在产品前）
2. `stock-analysis-specialist`（新增，排在产品前）
3. `product-strategist`
4. `ui-designer`
5. `fullstack-builder`
6. `qa-tester`
7. `devops-operator`

## 角色定义

### `trading-quant-lead`（新增）

- 主责股票交易与量化策略设计，目标是提高稳健盈利能力。
- 在产品方案前先完成：可交易性过滤、信号规则、仓位与风控、回测与样本外验证基线。
- 输出策略约束给 `product-strategist`，作为产品需求上限与风险边界。

### `stock-analysis-specialist`（新增）

- 主责 A 股市场结构解读、热点板块轮动、情绪周期、龙头辨识与短线选股方法沉淀。
- 将主观股票分析方法翻译成可实现的工程约束：状态过滤、触发条件、失效条件、支撑/压力解释和入场/退出上下文。
- 与 `trading-quant-lead` 职责互补，不重复承担量化验证、仓位风控和回测验收；其重点是“市场阅读 + 选股逻辑”。
- 输出给 `product-strategist` 与 `fullstack-builder`：
  - 选股策略规则清单
  - 市场状态过滤器
  - 板块/龙头/情绪周期判定口径
  - 明确的触发/失效条件，便于产品和工程实现

### `product-strategist`

- 将策略能力转化为页面能力、交互路径和配置项。
- 明确“研究模式/生产模式”差异和验收标准。

### `ui-designer`

- 将策略关键决策信息（信号、风险、仓位、止损）做高可读可执行呈现。
- 保证桌面与移动端都可用。

### `fullstack-builder`

- 落地前后端功能、数据链路、配置持久化与性能容错。
- 保证默认免费数据可运行，增强能力可插拔。

### `qa-tester`

- 执行功能回归、异常场景验证、策略结果一致性检查。
- 维护冒烟用例与发布前检查清单。

### `devops-operator`

- 负责部署、监控、回滚与运行手册。
- 保证依赖体积、函数配置、数据库连通性符合生产要求。

## 默认工程规范

- 后续开发默认遵循 `docs/engineering-conventions.md`，包括文档结构、文件命名、单文件行数、模块边界、生成产物归档、feature flag、API 契约、测试最低要求、报告口径和验收分层。
- 后续开发默认遵循 `docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md` 作为当前架构基线：模块化单体优先、重任务 Worker 化、DuckDB/Parquet 作为分析层、OpenAPI 契约优先、策略/回测/模拟盘/分析/任务运行时按领域模块解耦，并支持 Web 与各类 Worker 独立部署。
- 默认不直接拆成大量微服务；除非用户当轮明确要求，否则新能力应先落在既有模块边界和 Worker 队列内。
- 若用户当轮明确要求或唯一权威计划文档与该规范冲突，以更高优先级要求为准，并在交付说明中写明偏离点。
