# 维斯量化平台模块化架构升级执行方案

日期：2026-06-04
项目：`/Users/j/Documents/gupiao`
性质：架构升级最终方案与分阶段执行文档

## 1. 一句话结论

当前平台不建议直接拆成大量微服务。最合理的最终路线是：

> 模块化单体优先，长任务 Worker 化，分析层 DuckDB/Parquet 化，API 契约 OpenAPI 化，策略/回测/模拟盘逐步形成独立领域模块，最后实现 Web、Worker、Scheduler、分析任务的独立部署。

这样可以提升性能、稳定性、可维护性、可扩展性和部署解耦能力，同时避免过度架构导致开发和运维成本失控。

## 2. 最终目标

### 2.1 性能目标

1. Web 主进程只处理页面请求、轻量查询、任务提交和状态查询。
2. 24 个月回测、数据补齐、Parquet 导出、DuckDB 报告、批量策略验证全部由 Worker 执行。
3. 重分析不再反复扫描业务数据库，优先使用 Parquet + DuckDB。
4. 热点页面使用缓存、物化结果和异步任务结果，减少同步等待。

### 2.2 稳定性目标

1. 长任务失败不会拖垮 Web 服务。
2. Worker 任务有状态、心跳、进度、错误、重试和产物路径。
3. 数据不足、任务失败、依赖缺失必须显式展示，不能静默成功。
4. 每个核心服务具备健康检查和回滚路径。

### 2.3 可维护性目标

1. API 层、数据层、策略层、回测层、模拟盘层、分析层边界清晰。
2. 新策略、新数据源、新报告不再到处插代码。
3. 前后端字段以后端 OpenAPI 为事实源，减少手写 DTO 漂移。
4. 文档、报告、生成产物按目录归档，减少历史文档干扰。

### 2.4 可扩展性目标

1. 数据源可插拔。
2. 策略可注册、可分层、可单独回测。
3. Worker 可按队列扩展。
4. 分析报告可复用 Manifest、Parquet 和统一指标口径。

### 2.5 独立部署目标

1. Web、Runtime Worker、Analytics Worker、Backtest Worker、Scheduler 可以独立启动和重启。
2. 某个 Worker 故障不影响 Web 页面访问。
3. 支持只更新前端、只更新后端、只重启某类 Worker。
4. 支持按任务队列扩容，不要求一次性微服务化。

## 3. 最终架构

```text
React 前端
  ↓
OpenAPI 生成类型
  ↓
FastAPI Web 主服务
  ├─ 页面轻量查询
  ├─ 用户操作入口
  ├─ 任务提交
  └─ 任务状态查询

领域模块
  ├─ market_data        行情、板块、龙虎榜、数据源适配
  ├─ strategy_engine    策略信号、评分、排序、风控、观察池
  ├─ backtest_engine    回测、组合收益、样本外验证
  ├─ paper_trading      模拟盘、持仓、复盘、执行记录
  ├─ analytics          DuckDB、Parquet、Manifest、报告查询
  └─ task_runtime       任务队列、Worker、进度、产物、重试

独立 Worker
  ├─ data_worker        数据补齐、数据质量检查
  ├─ analytics_worker   Parquet 导出、DuckDB 报告
  ├─ backtest_worker    24 个月回测、walk-forward、组合回测
  └─ report_worker      Markdown/JSON 报告生成

存储
  ├─ MySQL/SQLite       业务事实源
  ├─ Redis              缓存、限流、热数据
  ├─ Parquet            分析数据集
  ├─ DuckDB             只读分析查询
  └─ artifacts          报告、Manifest、任务产物
```

## 4. 明确不做什么

1. 不一次性拆成大量微服务。
2. 不把 DuckDB 当生产交易事实源。
3. 不让 Web 主进程执行 24 个月回测、数据补齐、批量报告生成等重任务。
4. 不让研究策略绕过生产门控进入生产排序。
5. 不用前端手写类型替代后端 OpenAPI 契约。
6. 不为了架构升级重写现有核心业务。

## 5. 阶段拆解

## Phase 1：工程边界与契约收口

### 目标

先稳住工程边界，避免平台继续无序扩张。

### 主要任务

1. 梳理现有模块职责：
   - API route
   - service
   - repository
   - worker
   - script
   - report
   - frontend feature
2. 明确 Web 主进程禁止执行的重任务清单。
3. 导出 OpenAPI，并生成前端类型。
4. 将关键 API wrapper 逐步迁移到生成类型。
5. 建立架构边界文档。

### 推荐交付文件

1. `docs/architecture/current-boundary-map.md`
2. `docs/contracts/openapi.json`
3. `frontend/src/generated/api-types.ts`
4. `docs/reports/web-heavy-task-inventory-2026-06-04.md`

### 验收标准

1. OpenAPI 可以稳定导出。
2. 前端类型可以成功生成。
3. `npm run typecheck` 能发现契约漂移。
4. Web 主进程重任务清单完整。
5. 新增接口不再手写重复 DTO。

### 预期效果

1. 前后端字段漂移减少。
2. 后续拆模块有依据。
3. 长任务迁移范围清楚。

## Phase 2：数据分析层独立

### 目标

把策略分析、24 个月回测报告、数据质量检查从业务库重扫描中拆出来。

### 主要任务

1. 完善 `analytics` 模块：
   - config
   - manifest
   - quality
   - exporters
   - duckdb_repository
   - report_queries
   - schemas
2. 导出最近 24 个月 `daily_bars` Parquet。
3. 每次导出生成 Manifest。
4. DuckDB 基于 Manifest 和 Parquet 生成策略报告。
5. 数据不足 24 个月时，必须触发或明确创建补数据任务，不能静默回测。

### 推荐交付文件

1. `backend/app/services/analytics/`
2. `backend/scripts/export_analytics_parquet.py`
3. `backend/scripts/run_duckdb_strategy_report.py`
4. `backend/data/analytics/manifests/*.json`
5. `docs/reports/strategy_24m_duckdb_report.md`
6. `backend/data/analytics/reports/strategy_24m_duckdb_report.json`

### 验收标准

1. Parquet 导出成功。
2. Manifest 记录数据范围、样本数量、质量状态和文件路径。
3. DuckDB 报告能跑通。
4. 数据不足时报告明确阻断。
5. 报告明确区分：
   - 每日信号等权复利收益
   - 真实组合收益
   - 最大回撤
   - PF
   - 平均单笔
   - 最长无票天数

### 预期效果

1. 回测和报告查询更快。
2. 数据质量可追踪。
3. 报告产物可复现。

## Phase 3：长任务 Worker 化

### 目标

Web 只提交任务，Worker 执行任务，长任务具备可观测和可恢复能力。

### 主要任务

1. 复用现有 `RuntimeTaskQueue`。
2. 建立 task handler registry。
3. Worker 支持：
   - claim
   - heartbeat
   - progress
   - retry
   - artifact
   - failure
4. 接入任务类型：
   - `data_backfill_24m`
   - `analytics_export_daily_bars`
   - `analytics_quality_check`
   - `strategy_24m_duckdb_report`
   - `backtest_all_strategies_24m`
5. 前端或 API 能查看任务状态和产物路径。

### 推荐交付文件

1. `backend/app/services/tasks/handlers.py`
2. `backend/app/services/tasks/worker.py`
3. `backend/scripts/analytics_worker.py`
4. `docs/operations/worker-runbook.md`

### 验收标准

1. Worker 可以独立启动。
2. 任务执行中有心跳和进度。
3. 任务失败有错误信息。
4. Worker 重启后任务不会假成功。
5. 任务产物路径可查询。

### 预期效果

1. Web 服务稳定性提升。
2. 长任务失败可追踪、可重试。
3. 未来可以按队列独立部署和扩容。

## Phase 4：策略引擎解耦

### 目标

让策略、排序、风控、观察池、生产池拥有清晰统一的接口。

### 主要任务

1. 建立 `strategy_engine` 模块。
2. 每个策略统一输出：
   - strategy_key
   - strategy_family
   - strategy_variant
   - signal_state
   - production_score
   - watch_score
   - score_components
   - exclusion_reasons
   - warning_tags
   - production_allowed
   - research_only
3. 固化生产门控：
   - `near_entry` 只能 watch-only
   - `production_score` 只允许 `buy_now` / `soft_buy_now`
   - `front_row_only` 只能观察，不做生产硬过滤
   - `front_row_weighted` 未验证通过前只允许 Shadow/Paper
4. 策略结果统一服务：
   - 低吸优先榜
   - 策略跟踪
   - 回测
   - 模拟盘
   - 报告

### 推荐交付文件

1. `backend/app/services/strategy_engine/`
2. `backend/app/services/strategy_engine/registry.py`
3. `backend/app/services/strategy_engine/schemas.py`
4. `backend/app/services/strategy_engine/gates.py`
5. `backend/tests/test_strategy_engine_gates.py`

### 验收标准

1. 生产策略和观察策略不会混用。
2. 暂停生产策略不能生成生产分。
3. `near_entry.production_score` 必须为 null。
4. 低吸榜旧排序默认不变。
5. 新增策略只需注册，不需要改多个页面和多个回测入口。

### 预期效果

1. 策略扩展更容易。
2. 生产风险降低。
3. 回测、页面、模拟盘口径一致性提升。

## Phase 5：回测与模拟盘口径统一

### 目标

减少“回测表现好，但模拟盘不一致”的问题。

### 主要任务

1. 建立统一事件模型：
   - signal event
   - order event
   - fill event
   - position event
   - exit event
2. 回测和模拟盘共用核心成交、持仓、风控规则。
3. 真实组合回测至少支持：
   - max5
   - max10
   - 持仓占用资金
   - 同票持有中禁止重复买
   - 同一策略单日最多 2 只
   - 同一板块最多 2 只
   - 弱市总仓位限制
   - 退潮市场不新开仓
4. 每次策略调整输出策略建议：
   - 保留
   - 降权
   - 默认关闭
   - 删除候选

### 推荐交付文件

1. `backend/app/services/backtest_engine/`
2. `backend/app/services/backtest_engine/events.py`
3. `backend/app/services/backtest_engine/portfolio.py`
4. `backend/app/services/paper_trading/execution_rules.py`
5. `docs/reports/strategy-24m-portfolio-backtest-YYYY-MM-DD.md`

### 验收标准

1. 回测和模拟盘使用同一套关键执行规则。
2. 报告同时展示信号收益和真实组合收益。
3. 样本缩水、最长无票天数、弱市表现必须展示。
4. 策略建议必须有数据依据。

### 预期效果

1. 策略结果更接近真实执行。
2. 模拟盘可以成为生产前门禁。
3. 策略保留或关闭不再凭感觉。

## Phase 6：前端信息降噪与页面分工

### 目标

页面从“信息堆叠”变成“结论优先、原因清楚、明细可查”。

### 页面分工

| 页面 | 核心问题 | 主要展示 |
|---|---|---|
| 实时监控 | 今天看什么 | 市场状态、优先榜、持仓提醒、关键位 |
| 策略跟踪 | 信号后来怎么样 | 信号表现、风险、复盘、抗跌事实 |
| 模拟盘 | 执行结果如何 | 持仓、成交、收益、风险、复盘 |
| 数据控制台 | 数据是否可靠 | 数据源、覆盖率、补数任务、质量门禁 |
| 回测中心 | 策略是否值得保留 | 24 个月报告、样本外、组合收益 |

### 主要任务

1. 每页只保留首屏核心结论。
2. 重复指标合并。
3. 研究信息移到详情或报告。
4. 技术术语改成白话解释。
5. 表格和长列表继续使用 `DataTable` / `VirtualCardList`。
6. 避免卡片套卡片、布局挤压、内容互相遮挡。

### 推荐交付文件

1. `docs/reports/frontend-information-simplification-plan-YYYY-MM-DD.md`
2. `frontend/src/features/*`
3. `frontend/src/styles/workspace/*`

### 验收标准

1. 每个页面首屏能说清当前结论。
2. 关键指标不重复展示。
3. 桌面端和移动端不挤压、不重叠。
4. 关闭 feature flag 后页面无空洞。
5. 前端 typecheck 和相关组件测试通过。

### 预期效果

1. 页面更简洁。
2. 用户更容易知道下一步该看什么。
3. 不牺牲完整信息，只调整展示层级。

## Phase 7：独立部署与运行手册

### 目标

让 Web、Worker、Scheduler、分析能力可以独立部署、独立重启、独立观测。

### 主要任务

1. 部署结构支持：
   - web
   - runtime-worker
   - analytics-worker
   - backtest-worker
   - scheduler
   - mysql
   - redis
2. 健康检查分层：
   - `/readyz`
   - `/metrics`
   - worker heartbeat
   - analytics dependency check
   - DB connectivity
3. 部署脚本支持：
   - 只更新前端
   - 只更新后端
   - 只重启 Worker
   - 只跑数据任务
4. 建立故障恢复流程。

### 推荐交付文件

1. `docs/operations/deployment-topology-runbook.md`
2. `docs/operations/worker-runbook.md`
3. `scripts/quick_cloud_deploy.sh`
4. `scripts/one_click_cloud_deploy.sh`
5. `docker-compose*.yml`

### 验收标准

1. Web 重启不影响已入队任务状态。
2. Worker 重启后可以继续处理任务。
3. Analytics 依赖缺失时明确失败。
4. 部署后 readyz 正常。
5. 回滚步骤可执行。

### 预期效果

1. 部署风险降低。
2. 故障定位更快。
3. 后续扩容不需要重构。

## 6. 推荐执行顺序

```text
Phase 1：工程边界与契约收口
  ↓
Phase 2：数据分析层独立
  ↓
Phase 3：长任务 Worker 化
  ↓
Phase 4：策略引擎解耦
  ↓
Phase 5：回测与模拟盘口径统一
  ↓
Phase 6：前端信息降噪与页面分工
  ↓
Phase 7：独立部署与运行手册
```

## 7. 每阶段完成后必须检查

1. `git status`，确认没有误改无关文件。
2. 后端相关 pytest。
3. 前端 typecheck。
4. OpenAPI 生成类型检查。
5. 关键页面或接口冒烟。
6. 如涉及 Worker，必须跑一次真实任务。
7. 如涉及回测，必须输出 Markdown 和 JSON 报告。

## 8. 总验收标准

最终架构完成后，平台应满足：

1. Web 主服务不执行重型后台任务。
2. 24 个月回测和分析报告可由 Worker 独立生成。
3. 数据不足时不会静默产出误导报告。
4. 策略生产门控、观察池、研究策略边界清晰。
5. 回测和模拟盘口径一致性明显提升。
6. 前端页面按业务问题分工，信息不再堆叠。
7. OpenAPI 是前后端契约事实源。
8. Web、Worker、Scheduler 可独立部署和恢复。

## 9. 风险与控制

| 风险 | 表现 | 控制方式 |
|---|---|---|
| 过度微服务化 | 服务太多，运维复杂 | 先模块化单体，只独立 Worker |
| Web 继续跑长任务 | 页面卡顿、请求超时 | 重任务清单 + Worker 门禁 |
| 报告口径误导 | 信号收益被当真实收益 | 报告字段强制区分口径 |
| 策略误入生产 | 研究策略影响排序 | strategy gate + feature flag |
| 数据质量不足 | 24 个月不足仍回测 | Manifest + quality gate |
| 前端继续堆信息 | 页面复杂、难判断 | 页面分工 + 首屏结论优先 |
| 契约漂移 | 后端字段改了前端不知 | OpenAPI 生成 + typecheck |

## 10. 最终效果

完成后，平台会从“功能不断堆叠的量化工具”升级为：

> 可验证、可复现、可扩展、可独立运行重任务的 A 股量化交易辅助平台。

具体提升：

1. 性能提升：重查询和长回测从 Web 请求中移除。
2. 稳定性提升：Worker 故障不拖垮页面。
3. 可维护性提升：模块职责清楚，新功能落点明确。
4. 可扩展性提升：策略、数据源、报告都可插拔。
5. 可部署性提升：Web、Worker、Scheduler 可以独立部署。
6. 策略可信度提升：回测、样本外、模拟盘、报告口径统一。
7. 前端可读性提升：页面按问题组织，先结论后细节。

## 11. 执行提示词

后续如果要让 Codex 或 Claude 按本方案执行，可以使用以下提示词：

```text
你在 /Users/j/Documents/gupiao 项目中继续开发。

请严格按照以下文档分阶段执行，不要自行扩大范围：
/Users/j/Documents/gupiao/docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md

执行原则：
1. 先运行 git status，保护当前未提交改动。
2. 不要回滚、覆盖、删除用户或其他任务已有改动。
3. 不要直接拆成大量微服务。
4. 采用模块化单体 + 独立 Worker + DuckDB/Parquet 分析层 + OpenAPI 契约优先路线。
5. Web 主进程只负责轻量请求、任务提交、状态查询；重任务必须 Worker 化。
6. DuckDB 只做分析和报告，不作为生产交易事实源。
7. 策略生产门控必须保持：research-only、watch-only、near_entry 不得进入 production_score。
8. 每个阶段完成后必须运行相关测试和验收命令。
9. 不部署，除非用户明确要求。

请先执行 Phase 1：工程边界与契约收口。
最终回复必须说明：
- 改了哪些文件
- 新增了哪些文件
- 跑了哪些测试
- 是否发现 Web 主进程重任务
- OpenAPI 和前端类型是否通过
- 是否存在未完成事项和原因
```
