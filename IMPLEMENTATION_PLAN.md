# TQuant 策略与工作台优化方案 v9 执行计划

## 需求来源

- `/Users/j/Documents/gupiao/docs/TQuant-策略与工作台优化方案-终版-2026-05-06.md`
- 标题：`TQuant 策略与工作台优化方案（v9·开发执行版）`
- 本轮追加：用户列出的 P0/P1/P2 语义、权限、feature flag、迁移 backfill、fallback 校验和探针补齐问题。

## 执行状态

- [x] 定位需求文档并核对当前项目基线。
- [x] Phase 0：策略工作台 UX 清理、一键回测、预设卡片、结果摘要、懒加载。
- [x] Phase 1：做 T 成本闭环、`effective_action/is_actionable`、模拟盘过滤。
- [x] Phase 2：策略元数据 4 字段、治理表、resolver、权限过滤、默认预设过滤。
- [x] Phase 3：新增研究策略 `ma_channel_band` / `leader_pullback_band`、样本池、规则、fallback。
- [x] Phase 4：Feature Flag 服务/API/前端入口、弹性缓存与预热脚本。
- [x] 验证：后端测试、前端构建、生成文件同步。
- [x] P0：统一 `visibility` 语义，`hidden` 只允许 admin + `include_hidden=true` 查看。
- [x] P0：factor/backtest_only 策略增加后端回测权限阻断，不再只靠前端隐藏。
- [x] P0：明确 quick backtest 只由前端展开 preset 到现有 `strategies` 数组，不新增 `preset_key` 提交接口。
- [x] P0：补齐 `StrategySuggestion` 唯一字段表和新策略可用指标说明。
- [x] P0：迁移和 schema_compat 显式 backfill `enabled/probe_status/probe_summary/visibility`。
- [x] P1：feature flag 60 秒进程缓存、标准响应字段、operator_ip 审计和前端审计入口。
- [x] P1：fallback 由后端生成并新增 `--check` 校验脚本。
- [x] P1：弹性缓存质量统一为 `fresh/stale/estimated/unavailable`。
- [x] P1：`probe_leader_pullback_data.py` 扩展为四维 JSON 探针。

## 关键实现决策

- 不修改 `trade_levels()` 返回结构。
- 不把 DB session 注入 `strategy_policy.py`、`candidate_rules.py`、`base_strategy.py`。
- `visibility=hidden` 采用安全语义：普通用户不可见；admin 仅通过显式 `include_hidden=true` 可见。
- `visibility=backtest_only` 仅研究/优化/admin 可见和可回测。
- Factor 策略在 meta API 按角色隐藏，并在回测创建/优化/样本外验证接口做后端权限阻断。
- 新字段全部提供默认值，旧客户端继续兼容。

## 验证命令

- 后端：`cd backend && python -m pytest ...`
- 前端：`cd frontend && npm run build`
- 生成：`python scripts/sync_strategy_meta_fallback.py`

## 本轮验证结果

- `backend/.venv/bin/python -m py_compile ...`：通过。
- `backend/.venv/bin/python -m compileall backend/app scripts`：通过。
- `backend/.venv/bin/python -m pytest backend/tests/test_strategy_metadata_service.py backend/tests/test_strategy_meta_routes.py backend/tests/test_feature_flags_service.py`：13 passed，1 个 urllib3/OpenSSL 环境警告。
- `cd frontend && npm run build:web`：通过。
- `cd frontend && npm run check:strategy-meta`：通过，1 个 urllib3/OpenSSL 环境警告。
- `backend/.venv/bin/python scripts/probe_leader_pullback_data.py --dry-run --min-count 1 --output /tmp/leader_probe_report.json`：本地 MySQL 未启动，脚本按预期输出 failed JSON，不再抛出堆栈。

---

# TQuant 深度代码审查整改需求计划执行记录

## 需求来源

- `docs/TQuant-深度代码审查整改需求计划-2026-05-06.md`
- 来源报告：`/Users/j/Downloads/TQuant-深度代码审查报告.html`

## TODO 状态

- [x] 读取需求文档并核对当前项目实现。
- [x] R0-1 通知未配置不能返回假成功：当前已返回 `ok=false` 且不计数；本轮补充稳定错误码字段。
- [x] R0-2/R0-7 时间口径统一：主流程已使用北京时间；本轮修正认证 JWT/session 为 UTC 口径，并补关键服务时间工具。
- [x] R0-3 Android Release 明文 HTTP：主配置已禁用；本轮补发布检查脚本强约束。
- [x] R0-4 低吸物化重建事务边界：当前 `_rebuild_materialized_snapshot` 已不提交外部事务。
- [x] R0-5 策略元数据单一真源：当前前端 fallback 已由后端生成；动态策略 tab 已接入 metadata。
- [x] R0-6 模拟盘 API 错误语义统一：订单查询/撤单已按 LookupError=404、ValueError=400 处理。
- [x] R1-1/R1-2 策略权限和提升降级校验：当前已从 seed+DB 合并 metadata 校验。
- [x] R1-3 Feature flag 热路径优化：当前 `list_feature_flags` 不查询审计表。
- [x] R1-4 回测预设动态生成：当前根据实时 production strategy keys 生成。
- [x] R1-5 前端策略标签一致：Playbook 当前策略优先从动态 tabs 读取。
- [x] R2-1 量化评分魔法数治理：本轮提取评分常量并保留原规则不变。
- [x] R2-4 指标算法对齐：EMA/MACD 改为 SMA seed 初始化，并补基准测试。
- [x] R2-2 迁移治理：生产路径改为 Alembic 优先，`schema_compat` 默认只读漂移检查，写修复需显式开启。
- [x] R2-3 后台任务隔离：Web 默认关闭运行时后台任务，MySQL Compose 增加 `migration`、`runtime-worker`、`backtest-worker` 启动链路。
- [x] R2-5 全局单例治理：高频限流器改为配置驱动工厂，生产可切换 SQLite/内存后端；服务层保留兼容接口。
- [x] R2-6 多 worker 限流：新增 `GLOBAL_RATE_LIMIT_BACKEND/MAX_CALLS/WINDOW_SECONDS`，MySQL Compose 默认 Web 使用 SQLite 限流后端。
- [x] U1 实时监控操作更直观：持仓/榜单卡片改为“现在 / 原因 / 错了”三段式提示，降低专业术语理解成本。
- [x] U2/U3 数据质量和回测指标展示：实时监控和选股宝典补充快照日期、数据状态、样本量、1-5 日胜率/收益。
- [x] U5 移动端离线状态：App 监听 online/offline，离线时明确提示使用最近缓存数据，恢复网络后自动刷新当前页。
- [x] 新增/补充针对本轮改动的测试。

## 本轮修改区域

- 后端认证时间：`backend/app/core/timezone.py`、`backend/app/services/auth_service.py`
- Agent 通知返回结构：`backend/app/models/schema_defs/agent.py`、`backend/app/services/agent_notification_service.py`
- Android 发布检查：`scripts/native_release_check.py`
- 测试：通知、认证、原生发布检查相关用例

## 验证命令

- 已执行：`backend/.venv/bin/python -m py_compile ...`，通过。
- 已执行：`backend/.venv/bin/pytest backend/tests/test_notification_events.py backend/tests/test_auth_routes.py backend/tests/test_feature_flags_service.py backend/tests/test_strategy_metadata_service.py backend/tests/test_indicators.py -q`，19 passed，1 个 urllib3/OpenSSL 环境警告。
- 已执行：`backend/.venv/bin/pytest backend/tests/test_paper_performance_archive.py backend/tests/test_paper_routes.py -q`，23 passed，1 个 urllib3/OpenSSL 环境警告。
- 已执行：`python3 scripts/native_release_check.py`，通过。
- 已执行：`cd frontend && npm run check:strategy-meta`，通过。
- 已执行：`cd frontend && npm run build:web`，通过。
- 已执行：`backend/.venv/bin/pytest backend/tests/test_indicators.py backend/tests/test_feature_flags_service.py backend/tests/test_strategy_metadata_service.py backend/tests/test_notification_events.py backend/tests/test_auth_routes.py backend/tests/test_paper_performance_archive.py backend/tests/test_paper_routes.py -q`，46 passed，1 个 urllib3/OpenSSL 环境警告。

## 继续完成记录

- 新增 Alembic 查询索引迁移：`backend/alembic/versions/20260506_0002_query_indexes.py`。
- 生产 Docker MySQL 部署改为先跑 `migration`，成功后启动 Web/API 与两个独立 worker。
- `PRODUCTION_RUNBOOK.md` 已补充迁移容器、后台任务隔离、schema repair 和限流后端说明。
- 指标测试补齐 MA/RSI/ATR/VWAP 基线。

---

# High-Risk Optimization 执行记录

## 需求来源

- `/Users/j/Documents/gupiao/docs/superpowers/plans/2026-05-06-high-risk-optimization-plan.md`
- 目标：在不改变交易策略语义的前提下，完成 schema/index 迁移治理、legacy route 退役、CSS 模块化验收、市场数据 provider 质量契约与渐进式路由。

## TODO 状态

- [x] 定位需求文档并核对当前项目实现。
- [x] Schema/index 审计脚本、测试和 runbook。
- [x] 确认 hot index 已通过 Alembic 迁移承载，`schema_compat` 不再在默认路径创建索引。
- [x] legacy `/backtests`、`/research` 调用审计脚本和测试。
- [x] legacy 路由改为 `legacy_route_compat_enabled` 控制的兼容 301 或结构化 410。
- [x] CSS 域入口和 UI 回归 checklist。
- [x] 市场数据 provider 质量模型、适配器和路由测试。
- [x] `market_provider_router_enabled` feature flag 与低风险路径接入。
- [x] API 输出保留明确数据质量字段。
- [x] 执行后端测试、前端构建、审计脚本和必要 smoke。

## 关键约束

- 不直接改生产数据、不触碰密钥、不执行生产发布。
- 数据库 schema/index 变更必须走 Alembic；本轮只补审计和只读告警。
- CSS 拆分只移动/组织 import，不在同一任务重命名 selector。
- provider router 默认关闭，默认行为保持现有数据源链路。

## 本轮修改区域

- Schema/index：`scripts/schema_index_audit.py`、`backend/tests/test_schema_index_audit.py`、`docs/operations/schema-index-runbook.md`。
- Runtime schema：`backend/app/core/schema_compat.py` 移除默认路径索引创建，索引继续由 Alembic `20260506_0002_query_indexes.py` 承载。
- Legacy route：`backend/app/core/config.py`、`backend/app/main.py`、`scripts/audit_legacy_routes.py`、`backend/tests/test_legacy_routes.py`、`docs/operations/legacy-route-removal.md`。
- CSS：新增 `frontend/src/styles/workspace/index.css`、`frontend/src/styles/backtest/index.css`、`frontend/src/styles/mobile/index.css`，并更新全局入口 import。
- Market provider：新增 `providers/quality.py`、`eastmoney_provider.py`、`akshare_provider.py`、`openbb_provider.py`、`router.py`，新增 `market_provider_router_enabled` flag，默认关闭。
- Data quality：`QuoteSnapshot` 新增 `data_quality/data_quality_message`，provider router 路径会补充质量信息。

## 本轮验证结果

- `backend/.venv/bin/python -m py_compile ...`：通过。
- `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_schema_index_audit.py backend/tests/test_legacy_routes.py backend/tests/test_market_provider_contract.py backend/tests/test_market_provider_flag.py backend/tests/test_market_data_quality_fields.py -q`：9 passed，1 个 urllib3/OpenSSL 环境警告。
- `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_schema_index_audit.py backend/tests/test_legacy_routes.py backend/tests/test_market_provider_contract.py backend/tests/test_market_provider_flag.py backend/tests/test_market_data_quality_fields.py backend/tests/test_market_routers.py backend/tests/test_feature_flags_service.py -q`：16 passed，1 个 urllib3/OpenSSL 环境警告。
- `python3 scripts/audit_legacy_routes.py --strict`：通过，0 findings。
- `PYTHONPATH=backend:. backend/.venv/bin/python scripts/schema_index_audit.py --database-url sqlite:///backend/data/t_quant.db`：脚本可用；本地 seed 库未跑最新 Alembic，报告为 degraded。
- `PYTHONPATH=backend:. backend/.venv/bin/python scripts/schema_index_audit.py`：本地 `.env` 指向 MySQL 且 MySQL 未启动，脚本返回 `status=unavailable` 结构化结果，不再抛堆栈。
- `cd frontend && npm run build:web`：通过。
- `cd frontend && npm run analyze`：通过，生成 `frontend/dist/bundle-report.json`，最大 chunk 仍为 `echarts` 约 588 KB。
