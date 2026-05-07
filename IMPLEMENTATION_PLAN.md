# TQuant 策略与工作台优化方案 v9 执行计划

---

# 主线涨停缩量回调增强策略执行记录（2026-05-07）

## 需求来源

- 用户要求基于“只做涨停后下跌回调、不追高、等待主线板块首板/低位启动票缩量回调、多线合一或双底、再次站稳 5 日线”的方法，落地一个增强版策略。

## TODO 状态

- [x] 新增生产观察策略 `mainline_limitup_shrink_retrace_reclaim`。
- [x] 接入策略层级、主线板块过滤、策略池、策略家族、元数据和 feature flag。
- [x] 实现筛选规则：主线行业、涨停启动、3-8 日缩量回调、均线合一或双底支撑、站回 5 日线、禁止追高、风险阻断。
- [x] 实现买点区、执行说明、退出计划、仓位建议、市场状态调节和信号质量门槛。
- [x] 前端策略 metadata fallback、生产策略 tab 和回测验证策略列表同步。
- [x] 增加 Alembic 迁移，为已有库补策略元数据和默认预设。
- [x] 补充单测覆盖策略注册、筛选规则、双底入口、盘中确认和生产策略列表。

## 关键实现决策

- 作为 `auxiliary` 生产观察策略参与全策略优先榜，但默认仓位保守，不提升为 core。
- 只做主线热点行业，必须等待回调确认；涨停当天、高位追涨、放量下跌、假突破、冲高回落都不进入执行。
- “多线合一”和“双底支撑”二选一满足即可进入结构观察，但最终执行仍要求站回 5 日线和分时/VWAP 确认。
- 不改现有后端 API 结构，Web/App 通过原有策略榜单和 metadata 自动读取新策略。

## 验证结果

- `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_low_buy_strategy_replacement.py backend/tests/test_low_buy_recommendation_duration.py backend/tests/test_strategy_metadata_service.py -q`：20 passed。
- `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_low_buy_strategy_replacement.py backend/tests/test_low_buy_intraday_confirmation.py backend/tests/test_low_buy_recommendation_duration.py backend/tests/test_strategy_metadata_service.py -q`：27 passed。
- `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile backend/alembic/versions/20260507_0003_mainline_limitup_retrace_strategy.py backend/app/services/low_buy/candidate_rules.py backend/app/services/low_buy/intraday_confirmation.py`：通过。
- `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_low_buy_strategy_replacement.py backend/tests/test_low_buy_next_day_event_model.py backend/tests/test_low_buy_standardization.py backend/tests/test_low_buy_repositories.py backend/tests/test_low_buy_intraday_confirmation.py backend/tests/test_low_buy_simple_decision.py backend/tests/test_low_buy_mobile_read.py backend/tests/test_divergence_consensus_strategy.py backend/tests/test_low_buy_backtest_isolation.py backend/tests/test_low_buy_positioning.py backend/tests/test_low_buy_recommendation_duration.py backend/tests/test_strategy_metadata_service.py backend/tests/test_low_buy_trade_controls.py backend/tests/test_low_buy_read_paths.py -q`：89 passed。
- `npm --prefix frontend test -- workspaceConstants.test.ts --run`：1 passed。
- `npm --prefix frontend run check:strategy-meta`：通过。
- `npm --prefix frontend run build:web`：通过。

---

# TQuant 代码分析报告整改需求计划执行记录（2026-05-07）

## 需求来源

- `docs/TQuant-代码分析报告整改需求计划-2026-05-07.md`
- 来源报告：`/Users/j/Downloads/TQuant_代码分析报告.html`

## TODO 状态

- [x] 读取需求文档，核对当前项目实现和已有能力。
- [x] R-001 策略阈值参数版本化补齐：低吸 prefilter/execution 默认值集中到参数默认模块，运行时优先读取 active 参数；补参数 schema、导出、回滚、审计；回测持久化绑定参数 version/scope/hash。
- [x] R-002 AkShare 直连迁移 Provider Router：低吸扫描/历史、市场情绪、交易日历、涨跌停池、热点行业主路径迁到 provider/router；剩余 AkShare 调用限定在市场数据 provider/raw adapter 与可选外部因子 adapter 内。
- [x] R-003 priority cache JSON 序列化优化。
- [x] R-004 `paper.py` 路由拆分：保持 API 路径兼容，按账户/持仓/订单/绩效/自动交易/风控/日报拆出子路由。
- [x] R-005 ML 生产门槛提升到 accuracy>=0.60、AUC>=0.65，并加入 5-fold CV。
- [x] R-006 因子权重缓存加线程锁。
- [x] R-007 按场景拆分 HTTP timeout 配置。
- [x] R-008 策略自动治理增加恢复门槛。
- [x] R-009 ML artifact 远端备份/恢复接口和本地降级。
- [x] R-010 回测 Market Impact 执行模型。
- [x] R-011 热点行业最近有效缓存兜底。
- [x] R-012 回测归因前端增强：补行业/市场/质量归因、失败原因分布和 CSV 导出。
- [x] R-013/R-016 Roadmap：低风险接口/配置/文档边界已落地；外部资源依赖项按需配置验收。

## 实施原则

- 不改变当前生产策略默认阈值和买卖规则语义。
- 不触碰生产密钥、不执行破坏性数据库操作。
- 需要对象存储、Level2、真实推送等外部资源的需求只落接口、配置和安全降级。
- 每个切片用现有测试或编译/build 验证。

---

# Phase 4 / Phase 5 生产闭环补齐执行计划（2026-05-07）

## 需求来源

- 用户明确要求把以下现状补齐到生产可用闭环：
  - SSE 真 push 不能停留在轮询骨架，需要支持 Redis/pubsub 多实例推送。
  - 数据源 provider 已有抽象，但行情读取链路要统一迁移。
  - ML 信号模型不能只停留在研究骨架，要具备样本、训练、模型注册、生产推理闭环。
  - 量化参数版本化已建立，但策略阈值要从代码迁移到参数版本。
  - Prometheus/Grafana 已有配置，但必须云服务器实际部署验证。

## 角色顺序

- `trading-quant-lead`：确认 ML/参数版本化不直接越权影响生产交易，模型必须可回测、可审计、可降级。
- `stock-analysis-specialist`：确认策略阈值迁移后仍保留 A 股短线信号语义，不污染生产策略。
- `product-strategist`：保证新增能力走后端统一结果，前端/API 不重复实现交易判断。
- `ui-designer`：本轮无 UI 改造，仅保证返回信息可被后续 UI 稳定展示。
- `fullstack-builder`：落地 SSE、provider、ML、参数版本、监控部署脚本。
- `qa-tester`：补关键行为测试和 smoke 验证。
- `devops-operator`：完成 Prometheus/Grafana 云端部署验证和运行说明。

## TODO 状态

- [x] Redis/pubsub 级 SSE 真推送：运行时任务事件写入 DB 后同步发布到 Redis channel，多实例订阅 Redis；Redis 不可用时回退 DB polling。
- [x] 统一数据源 provider：报价、批量报价、分时、板块热力等关键行情读取优先走 provider router，并保留质量标记、失败降级和配置开关。
- [x] ML 信号模型：补训练接口、模型注册、artifact 持久化、生产模型选择、推理接口、研究/生产状态边界。
- [x] 量化参数版本化：低吸策略 prefilter、执行阈值、信号阈值默认进入参数版本，运行时读取 active 参数，历史回测继续绑定参数版本。
- [x] Prometheus/Grafana：补 compose/provisioning/部署脚本，在云服务器启动并验证 target/health。
- [x] 测试与部署：补后端测试、运行 frontend build/smoke，提交并部署云端。

## 关键实现决策

- 不接实盘交易，不把未验证 ML 模型直接用于真实交易动作。
- Redis/pubsub 是事件推送层，DB event log 仍作为审计与断线补偿来源。
- provider router 默认进入主路径，但保留配置开关和旧链路 fallback，避免单数据源故障拖垮平台。
- ML 模型 artifact 本地持久化，DB 只记录元数据、状态、指标与路径；生产模型必须显式 promote。
- 参数版本采用“默认参数深合并现有 active 参数”的方式 backfill，避免覆盖已有人工调整。
- 监控部署脚本不打印 token，不提交任何 secret。

## 验证计划

- 后端 targeted tests：SSE/pubsub、provider router、ML train/predict、参数版本 resolver。
- 后端 smoke：`PYTHONPATH=backend:. backend/.venv/bin/python -m pytest ...`
- 前端：如未改 UI，仅执行 `npm --prefix frontend run build:web`。
- 云端：主服务部署后，执行 Prometheus/Grafana compose 启动，验证 Prometheus target 和 Grafana health。

## 本轮验证结果

- `PYTHONPATH=backend:. backend/.venv/bin/python -m py_compile ...`：通过。
- `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_phase4_phase5_foundation.py backend/tests/test_market_provider_contract.py backend/tests/test_market_provider_flag.py -q`：12 passed。
- `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_low_buy_strategy_replacement.py backend/tests/test_strategy_metadata_service.py backend/tests/test_feature_flags_service.py backend/tests/test_market_data_quality_fields.py backend/tests/test_market_routers.py -q`：24 passed。
- `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q`：377 passed。
- `npm --prefix frontend run build:web`：通过。
- `CLOUD_SSH_KEY=/Users/j/Downloads/gupiao.pem RUN_FULL_TESTS=0 ./scripts/deploy_cloud_server.sh`：主服务部署成功，`readyz/protected_api/frontend` smoke 通过。
- `CLOUD_SSH_KEY=/Users/j/Downloads/gupiao.pem ./scripts/deploy_monitoring_stack.sh`：Prometheus/Grafana 部署成功。
- 云端 Prometheus target：`tquant-api up`。
- 云端容器：`tquant-app-mysql`、`tquant-runtime-worker-mysql`、`tquant-backtest-worker-mysql`、`tquant-redis`、`tquant-prometheus`、`tquant-grafana` 均运行。
- 云端 ML：已沉淀 310 条样本，并训练/注册过 `xgboost-production-v1`，`validation_accuracy=0.8871`、`validation_auc=0.9735`。最新安全门槛要求生产模型满足服务端最低样本量、accuracy、AUC 与 artifact hash 校验；样本不足模型会按研究信号降级，不允许绕过风控。

## 运行说明

- Grafana 默认绑定本机：`http://127.0.0.1:13000`，公网访问应走 Nginx HTTPS/鉴权或 SSH 隧道。
- Grafana 管理员密码已保存到云服务器：`/home/ubuntu/gupiao-upload/.runtime/grafana_admin_password`。
- Prometheus 默认绑定本机：`http://127.0.0.1:19090`，不要直接公网暴露。
- Prometheus scrape 使用 `/home/ubuntu/gupiao-upload/.runtime/prometheus/tquant_admin_token`，未在仓库保存密钥。

---

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

---

# TQuant 代码分析报告整改执行记录（2026-05-07）

## 需求来源

- `/Users/j/Documents/gupiao/docs/TQuant-代码分析报告整改需求计划-2026-05-07.md`
- 目标：修复代码分析报告中 P0/P1/P2 项，重点覆盖策略参数版本化、Provider Router、缓存性能、ML 生产门槛、回测执行模型、治理恢复闸门和模拟盘路由拆分。

## TODO 状态

- [x] 定位需求文档并核对当前项目实现。
- [x] R-003 优先级榜缓存从 `deepcopy` 改为 Pydantic JSON 序列化/反序列化。
- [x] R-006 因子权重缓存加锁，避免并发刷新读到半更新状态。
- [x] R-007 HTTP 超时按报价、批量行情、分钟K、AkShare、通知等场景拆分。
- [x] R-002 Provider Router 扩展到板块宽度、交易日历、涨跌停池、市场情绪池等关键 AkShare 路径；AkShare provider 不再通过 `service._load_board_breadth_frame()` 反调，避免递归。
- [x] R-011 热点行业在实时板块源失败时使用最近 5 分钟有效列表降级。
- [x] R-005 ML 生产阈值提升到 accuracy>=0.60、AUC>=0.65，并新增 5 折交叉验证准确率/AUC 门槛。
- [x] R-009 ML artifact 支持配置远端目录备份与本地缺失恢复，恢复前校验 SHA256。
- [x] R-010 回测新增 `market_impact` 执行模型，并在前端执行模型选项中展示“市场冲击成本”。
- [x] R-008 策略自动治理新增恢复闸门，暂停/观察策略需要满足更高健康度、样本量和止损率约束后才解除自动治理。
- [x] R-004 模拟盘路由完成职责拆分：`paper.py` 保留聚合入口，账户/持仓/风控、委托/成交、绩效、自动交易、共享辅助和响应序列化分别拆入独立模块。

## 本轮修改区域

- 配置：`backend/app/core/config.py`
- Provider Router：`backend/app/services/market/providers/*`、`backend/app/services/market/regime.py`、`backend/app/services/market/emotion.py`、`backend/app/services/low_buy/pool.py`
- 超时分层：`backend/app/services/market/quotes.py`、`backend/app/services/market/intraday.py`、`backend/app/services/market/sectors.py`、`backend/app/services/market/openbb_adapter.py`、`backend/app/services/low_buy/history.py`
- 缓存/因子：`backend/app/services/low_buy/priority_cache.py`、`backend/app/services/low_buy/factor_functions.py`
- ML：`backend/app/services/ml_signal/service.py`
- 回测：`backend/app/services/backtest/broker.py`、`frontend/src/api/backtests.ts`、`frontend/src/features/backtest/backtestDisplay.ts`
- 策略治理：`backend/app/services/low_buy/strategy_auto_governance.py`
- 模拟盘路由拆分：`backend/app/api/routes/paper.py`、`backend/app/api/routes/paper_account.py`、`backend/app/api/routes/paper_orders.py`、`backend/app/api/routes/paper_performance.py`、`backend/app/api/routes/paper_auto_trading.py`、`backend/app/api/routes/paper_shared.py`、`backend/app/api/routes/paper_serializers.py`
- 测试：`backend/tests/test_backtest_v2_engine_contract.py`

## 验证结果

- 已执行：`python3 -m compileall backend/app/services/market backend/app/services/ml_signal backend/app/services/backtest backend/app/services/low_buy backend/app/api/routes/paper.py backend/app/api/routes/paper_serializers.py backend/app/core/config.py`，通过。
- 已执行：`backend/.venv/bin/python -m pytest backend/tests/test_backtest_v2_engine_contract.py -q`，16 passed，1 个 urllib3/OpenSSL 环境警告。
- 已执行：`PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_market_provider_contract.py backend/tests/test_market_provider_flag.py backend/tests/test_market_data_quality_fields.py backend/tests/test_market_routers.py -q`，12 passed，1 个 urllib3/OpenSSL 环境警告。
- 已执行：`PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_phase4_phase5_foundation.py -q`，8 passed，1 个 urllib3/OpenSSL 环境警告。
- 已执行：`cd frontend && npm run build:web`，通过。
- 已执行：`python3 -m compileall backend/app/api/routes/paper.py backend/app/api/routes/paper_account.py backend/app/api/routes/paper_orders.py backend/app/api/routes/paper_performance.py backend/app/api/routes/paper_auto_trading.py backend/app/api/routes/paper_shared.py backend/app/api/routes/paper_serializers.py`，通过。
- 已执行：`PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_paper_routes.py -q`，20 passed，1 个 urllib3/OpenSSL 环境警告。
- 已执行：`PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_paper_performance_archive.py backend/tests/test_paper_auto_trading.py -q`，24 passed，1 个 urllib3/OpenSSL 环境警告。

## 继续完成记录（2026-05-07）

- R-001 补齐策略阈值参数化闭环：新增低吸策略默认参数模块，`candidate_rules` 只从 runtime 参数读取 prefilter/execution 阈值；量化参数导出、schema、回滚和审计接口已接入。
- R-002 补齐 Provider Router 主路径：低吸历史/扫描、交易日历、涨跌停池、市场情绪、热点行业和可选外部因子均不再直接调用 AkShare；AkShare 调用限定在 market provider/raw adapter。
- R-008 补齐策略治理恢复闸门：观察层需要连续 5 天达标，暂停层需要连续 10 天达标，未达标时只记录恢复进度，不自动恢复生产。
- R-009 补齐 ML artifact 元数据字段：模型记录和 API 响应包含远端 artifact URI 与 SHA256 校验，缺本地 artifact 时先尝试恢复并校验。
- R-012 补齐回测归因失败原因：后端输出 `failure_reasons`，前端归因面板和 CSV 导出展示拒单、止损、到期、回测结束清仓等失败分布。
- 收尾审查修复：量化参数 resolver 改为“精确 scope 优先，global 仅兜底”，避免较新的 global 参数覆盖 `low_buy` 专用策略阈值；回测参数绑定同样优先绑定 `low_buy` active 参数。

## 继续完成验证结果（2026-05-07）

- `python3 -m compileall backend/app/services/market/providers backend/app/services/market/emotion.py backend/app/services/market/regime.py backend/app/services/low_buy backend/app/services/quant backend/app/services/backtest backend/app/models/schema_defs/phase4.py backend/app/models/phase4_entities.py backend/app/api/routes/quant_config.py`：通过。
- `git diff --check`：通过。
- `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_market_provider_contract.py backend/tests/test_market_provider_flag.py backend/tests/test_feature_flags_service.py backend/tests/test_phase4_phase5_foundation.py backend/tests/test_backtest_phase2_research_tasks.py backend/tests/test_backtest_v2_api_contract.py backend/tests/test_backtest_v2_engine_contract.py backend/tests/test_low_buy_backtest_isolation.py -q`：61 passed，1 个 urllib3/OpenSSL 环境警告。
- `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_phase4_phase5_foundation.py -q`：9 passed，1 个 urllib3/OpenSSL 环境警告。
- `PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests/test_market_provider_contract.py backend/tests/test_market_provider_flag.py backend/tests/test_feature_flags_service.py backend/tests/test_phase4_phase5_foundation.py backend/tests/test_backtest_phase2_research_tasks.py backend/tests/test_backtest_v2_api_contract.py backend/tests/test_backtest_v2_engine_contract.py backend/tests/test_low_buy_backtest_isolation.py -q`：62 passed，1 个 urllib3/OpenSSL 环境警告。
- `cd frontend && npm run build`：通过。
