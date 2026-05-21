# TQuant 实施计划

## 前端最终重构优化基础层

需求来源：`docs/frontend-final-refactor-optimization-plan-2026-05-21.md`

### 本轮执行范围

- [x] 安装第一批基础依赖：Ant Design、Ant Design Icons、antd-mobile、TanStack Query、TanStack Virtual、React Router。
- [x] 新增 `frontend/src/app` 基础层：通用 Providers、Web/Native Router、QueryClient、Query Keys、权限 Guard。
- [x] 新增 `frontend/src/ui` 设计系统基础层：主题 token、AntD 主题、移动端 CSS variables、Shell、反馈态、数据展示、表单、图表容器。
- [x] 重构 Web 入口：`main.tsx` 接入 AppProviders、WebUiProviders、React Router。
- [x] 重构 Native 入口：`main-native.tsx` 接入 AppProviders、Memory Router，并避免引入桌面 AntD Provider。
- [x] 新增 Query seam：monitor / playbook / holdings / paper / settings 查询或 mutation 包装，供后续页面迁移复用。
- [x] Web 工作台顶部 Shell 导航迁移到 Ant Design `Menu` / `Badge` / `Dropdown`，保留现有页面状态和权限逻辑。
- [x] Web 核心页面第一批控件迁移：系统配置分类、选股宝典策略切换、模拟盘详情切换统一改为 Ant Design `Tabs`。
- [x] 交易工作台共享动作控件迁移：股票卡片操作、设置卡保存、错误弹窗、股票详情弹窗改用 Ant Design `Button` / `Modal`。
- [x] 实时监控和系统配置主操作按钮改用 Ant Design `Button`，保留原有回调和 loading 语义。
- [x] App 壳层第一批迁移：底部导航改用 `antd-mobile` `TabBar`，状态提示改用 `NoticeBar`。
- [x] 回测页面大文件拆分：`BacktestDashboard.tsx` 降到 471 行，新增纯 helper 文件；`api/backtests.ts` 降到 496 行，新增 API helper 文件。
- [x] 系统配置页继续拆分：校验/dirty state helper 独立，页面降到 396 行；修复旧 `.settings-tabs button` 规则误伤 AntD Tabs 的风险。
- [x] 系统配置管理操作继续迁移 Ant Design：板块过滤清空、策略治理操作、功能开关切换改用 `Button` / `Switch`。
- [x] App 端继续拆分：`MobileDesignCards.tsx` 格式化逻辑独立，策略切换改用 `antd-mobile` `CapsuleTabs`，板块偏好逻辑独立为 hook。
- [x] 实时监控页继续拆分：盘面摘要、今日动作、数据质量、榜单提示等纯逻辑抽入 helper，页面降到 320 行。
- [x] 回测页面继续拆分：任务进度、PanelHeader、Metric、EmptyLine 独立组件化，页面保持 437 行。
- [x] 回测 API 层继续拆分：响应归一化逻辑独立到 `backtests.normalizers.ts`，`api/backtests.ts` 降到 219 行。
- [x] 回测表单样式继续拆分：新增 `backtest-form.css`，`backtest.css` 降到 370 行。
- [x] 回测页面常用控件继续迁移 Ant Design：刷新、快速/专家切换、策略多选、提交、取消任务改用 `Button` / `Segmented` / `Checkbox`。
- [x] 策略工作台继续迁移 Ant Design：刷新、一键体检、策略确认弹窗和确认摘要按钮改用 `Button` / `Modal`。
- [x] 因子实验室继续迁移 Ant Design：刷新、生成假设、合成代码、保存草稿、评估、晋级和激活开关改用 `Button` / `Input` / `Checkbox` / `Switch`。
- [x] 系统配置继续迁移 Ant Design：板块过滤多选改用 `Checkbox`，因子权重输入改用 `InputNumber`。
- [x] 模拟盘盘中确认弹窗按钮改用 Ant Design `Button`。
- [x] 回测研究区剩余控件迁移 Ant Design：优化、样本外验证、对比、归因导出、ML/容量面板和任务列表统一改用 `Button` / `Checkbox`。
- [x] 策略工作台剩余控件迁移 Ant Design：健康摘要、流程步骤、预设选择、因子库列表统一改用 `Button`。
- [x] 工作台剩余通用控件迁移 Ant Design：命令面板、账本修复、个股详情切换、ETF 参数开关、页面错误重试、成交标签、机甲委托入口统一改用 `Button` / `Input` / `Checkbox`。
- [x] App / App Preview 剩余控件迁移 antd-mobile：账户菜单、候选详情、更新弹窗、行业偏好、持仓搜索、持仓编辑、候选/持仓操作统一改用 `Button` / `Input`。
- [x] App 壳层补齐 `PullToRefresh`：按当前 Tab 触发对应刷新，低吸 Tab 支持强制刷新候选池。
- [x] App 持仓编辑 Sheet 改为 `antd-mobile` `Popup`，保留原有表单语义和样式入口。
- [x] Vitest 增加 `antd-mobile` 测试轻量 mock，解决 SSR 测试解析移动端组件 CSS 的问题；生产和 Native 构建仍使用真实 `antd-mobile`。
- [x] Web/Native 根路由改为 `React.lazy`：`TradingWorkspace` 和 `MobileApp` 从入口同步包中拆出，降低首屏同步加载压力。
- [x] 核心页面新增 feature 入口并完成真实实现搬迁：`analysis`、`market-emotion`、`playbook`、`paper`、`monitor`、`settings` 页面实现已在对应 feature 目录，`trading-workspace` 旧兼容 re-export 已删除。
- [x] 删除根路由懒加载后不再被引用的旧 `frontend/src/App.tsx`。
- [x] 删除前端可确认无引用的占位/废弃组件、旧策略交通灯组件、空目录和对应无用样式；保留 `vite-env.d.ts`、测试 mock 等必要基础文件。
- [x] 目标范围内不再存在原生 `button` / checkbox / select / textarea 残留：`frontend/src/features/backtest`、`strategy`、`factor-mining`、`trading-workspace`、`mobile`、`app-preview` 扫描为 0。
- [x] 保留现有页面业务行为，不在本批次直接替换核心交易页面，避免影响策略与模拟盘逻辑。

### 已验证

- [x] `cd frontend && npm run build:web` 通过。
- [x] `cd frontend && npm run build:native` 通过；Native 构建未引入桌面 AntD 大包，根路由懒加载后 `MobileApp` 独立 chunk gzip 约 21.36 kB，`antd-mobile` 独立 chunk gzip 约 83.33 kB。
- [x] `cd frontend && npm run analyze` 通过，并生成 `frontend/dist/bundle-report.json`；最大动态 chunk 为 `antd` 与 `echarts`，均已从通用 vendor 拆出。
- [x] `cd frontend && npm test` 通过，12 files / 33 tests。
- [x] `cd frontend && npm audit --audit-level=moderate` 通过，0 vulnerabilities；曾发现的 `brace-expansion` moderate 已通过 `npm audit fix` 修复。
- [x] `git diff --check` 通过。
- [x] `rg -n "<button|<input\\s+type=\\\"checkbox\\\"|<select|<textarea" frontend/src/features/backtest frontend/src/features/strategy frontend/src/features/factor-mining frontend/src/features/trading-workspace frontend/src/mobile frontend/src/features/app-preview` 无结果。
- [x] 新增 `frontend/src/app` / `frontend/src/ui` 文件均小于 500 行；新增最大文件为 `tokens.css` 85 行。
- [x] 本轮新增/拆分文件均小于 500 行；搬迁后的 `features/settings/SettingsPage.tsx` 400 行、`features/monitor/MonitorPage.tsx` 320 行、`features/paper/PaperTradingPage.tsx` 288 行、`features/playbook/PlaybookPage.tsx` 241 行。
- [x] `api/backtests.ts` 从 496 行降到 219 行，归一化文件 305 行。
- [x] `backtest.css` 从 476 行降到 370 行，新增 `backtest-form.css` 105 行。
- [x] 样式文件按规则边界继续拆分，`frontend/src` 下 CSS 单文件已控制在 250 行以内；原入口文件保留顺序 `@import` 以降低视觉回归风险。
- [x] Vite vendor chunk 继续拆分为 `antd` / `antd-mobile` / `tanstack` / `react-vendor` / `echarts` / `native`，避免通用 vendor 单包过大。
- [x] `trading-workspace` 旧 re-export wrappers 已清理，测试与业务引用改为直接指向目标 feature / shared 模块。
- [x] 前端无引用文件启发式扫描仅剩 `vite-env.d.ts`，该文件为 Vite 类型声明，需保留。

### 保留项与原因

- [x] 页面 class 命名已完成阻塞项核查：剩余 class 是布局/状态语义和既有样式锚点，不再作为未完成项处理；进一步命名精简需要配合视觉回归单独小步推进。
- [x] 第一批核心页面实现已从 `trading-workspace` 搬迁到业务 feature 目录；旧兼容 re-export wrappers 已删除，避免继续扩大 shell 目录职责。
- [x] 共享业务 UI 组件 `WorkspaceComponents` 搬迁到 `features/workspace-shared`，旧路径兼容 re-export 已删除。
- [x] 共享格式化、类型、视图模型和工作台常量 `workspaceFormatters` / `workspaceTypes` / `workspaceViewModels` / `workspaceConstants` 搬迁到 `features/workspace-shared`。
- [x] 模拟盘主要子组件 `PaperDetailTabs`、`PaperTradingSections`、`PaperTradingSummaryBar`、`PaperTodayActionPanel` 搬迁到 `features/paper`。
- [x] 模拟盘详情与委托组件 `PaperTradingPerformance`、`PaperLedgerRepairPanel`、`PaperPositionDetailsPanel`、`PaperOrderEntryModal` 搬迁到 `features/paper`，旧路径兼容 re-export 已删除。
- [x] 模拟盘日期/状态工具与机甲舱组件、动画资产搬迁到 `features/paper`，旧路径兼容 re-export / CSS import 已删除。
- [x] 设置页主要子组件 `SettingsPagePanels`、`SettingsPageTabs`、`AuthSecurityCard`、`LatestDataStatusCard` 搬迁到 `features/settings`。
- [x] 设置页量化参数卡片 `QuantParameter*` 与 `quantParameterCardUtils` 搬迁到 `features/settings`，旧路径兼容 re-export 已删除。
- [x] 监控页小组件 `InstrumentSyncProgress`、`MonitorHoldingWizard` 搬迁到 `features/monitor`，旧路径兼容 re-export 已删除。
- [x] K 线通用 ECharts 渲染器搬迁到 `ui/charts`，工作台业务包装搬迁到 `features/workspace-shared`，旧路径兼容 re-export 已删除。
- [x] `requestCached` 保留兼容函数名，但底层已迁移为 TanStack Query `fetchQuery`，鉴权/管理令牌变化和显式 invalidation 会清理 Query cache。
- [x] ECharts 与专家面板已按动态 chunk 加载；`antd` 和 `echarts` 仍是最大生产依赖，但已从通用 vendor 拆出，后续优化应基于真实首屏 profiling 决定是否进一步替换组件。

## Auth 安全整改核验与补强

需求来源：用户 2026-05-20 直接给出的 AUTH-C/AUTH-H 安全问题清单。

### 核验结论

- [x] `JWT_SECRET` 硬编码/弱默认：当前后端使用 `AUTH_SECRET_KEY`，无源码默认密钥；启动期 `main.py` 调用 `ensure_auth_secret_configured()`，生产安全配置拒绝弱密钥。
- [x] Token 吊销：access token 带 `sid` 和 `token_version`；logout、refresh replay、管理员禁用/降权都会吊销 session 或提升 token_version。
- [x] API Key/敏感配置明文：系统配置中的 `llm_api_key`、`database_url` 走 Fernet 派生加密，公开响应只返回脱敏值；审计日志会脱敏 token/secret/api_key；运行时配置不再把 `LLM_API_KEY` 写入 `runtime.env`。
- [x] 登录/注册暴力破解：登录 IP + 账号维度限流、账号失败锁定和注册限流均已存在。
- [x] RBAC/归属：策略治理、参数、回测/优化/验证、模拟盘、Agent 写工具均有登录、角色或管理员校验；正式回测任务和旧兼容研究回测列表/详情均按 owner_user_id 隔离。
- [x] 密码哈希：当前为 `scrypt_sha256`，旧 `pbkdf2_sha256` 登录时自动升级；未发现 MD5 密码哈希。
- [x] Refresh Token：httpOnly Cookie、7 天有效期、每次 refresh 轮换，旧 token 重放会吊销用户全部会话。
- [x] MFA：模拟盘下单默认要求 TOTP；本轮补齐 Agent 模拟盘下单同样必须使用已登录用户会话并通过 paper_trade/MFA 门禁，Agent token 不能直接下单。

### 本轮修改

- [x] `/api/agent/paper/order` 在工具写权限之外追加用户会话、模拟盘权限和 MFA 校验。
- [x] 增加回归测试：Agent scoped token 即使有 write_paper scope 也不能直接创建模拟盘委托；写工具打开时未开启 MFA 的用户会被拒绝。
- [x] 旧兼容 `/api/backtests/runs` 和 `/api/backtests/runs/{id}` 增加 owner_user_id 过滤；旧 `/api/backtests` 创建的回测记录写入当前用户 ID。
- [x] 系统设置保存时清理历史 `runtime.env` 中的 `LLM_API_KEY`，后续只允许从数据库加密字段读取/更新 API Key；保留旧环境变量读取兼容但不再持久化。

### 验证结果

- [x] `backend/.venv/bin/python -m compileall backend/app backend/tests/test_agent_routes.py backend/tests/test_research_route_ownership.py -q` 通过。
- [x] `backend/.venv/bin/python -m compileall backend/app/services/settings_service.py backend/tests/test_low_buy_trade_controls.py -q` 通过。
- [x] `PYTHONPATH=. backend/.venv/bin/python -m pytest backend/tests/test_low_buy_trade_controls.py::LowBuyTradeControlTests::test_settings_public_payload_masks_secrets_and_preserves_masked_updates -q` 通过，1 passed。
- [x] `cd backend && .venv/bin/python -m pytest tests/test_auth_routes.py tests/test_auth_hardening.py tests/test_auth_cookie_security.py tests/test_login_lockout.py tests/test_agent_routes.py tests/test_paper_routes.py tests/test_research_route_ownership.py -q` 通过，55 passed。
- [x] `PYTHONPATH=. backend/.venv/bin/python -m pytest backend/tests/test_low_buy_trade_controls.py::LowBuyTradeControlTests::test_settings_public_payload_masks_secrets_and_preserves_masked_updates backend/tests/test_security_quant_extensions.py backend/tests/test_totp_secret_crypto.py backend/tests/test_security_hardening.py -q` 通过，9 passed。

## 量化增强闭环：Kelly+ATR、Regime、实盘回测监控、BL、另类数据、在线学习、执行算法、套利研究

需求来源：用户 2026-05-20 直接需求。

### 执行口径

- 不接真实券商和真实交易所下单。
- 现有 Kelly+ATR、市场状态、Markowitz、在线学习、真实撮合滑点已有基础实现，本轮只补缺口和生产接入。
- “多交易所套利”在 A 股平台中按研究/诊断能力落地，不进入自动交易。
- 新增文件保持 500 行以内，不改变现有策略买卖语义。

### TODO

- [x] P0：核实并补强 Kelly+ATR 仓位管理在模拟盘自动下单链路中的结构化输出与测试。
- [x] P0：核实并补强市场状态识别对策略参数/仓位缩放的生产链路。
- [x] P0：新增实盘/模拟盘 vs 回测表现对比监控，输出策略失效和滑点损耗告警。
- [x] P1：补齐 Black-Litterman 组合优化方法，并接入现有 portfolio-optimization API。
- [x] P1：新增另类数据情绪/事件评分服务，作为研究信号和候选加权输入，不直接自动交易。
- [x] P1：核实在线学习闭环已由 paper trade 样本、warm_start、人工审批构成，并补测试/报告字段。
- [x] P1：扩展回测执行算法：TWAP、VWAP、Implementation Shortfall 语义明确，成交假设写入输出。
- [x] P1：新增多市场/多交易所套利研究诊断接口，默认只报告不可交易/需人工确认。
- [x] 最终运行编译、针对性测试和前端构建。

### 当前发现

- `PositionSizer` 已读取 `kelly_position`、`final_position_cap_pct`、`volatility_position_pct`、`validation_position_scale`、`portfolio_weight_scale`。
- 市场状态、分市场参数晋级和自进化调度已有实现。
- Markowitz 已用共同成交日和 NaN 协方差，缺 Black-Litterman。
- ML 在线学习已有 paper sample、warm_start、时序验证、artifact hash 和人工审批。
- Backtest broker 已支持 VWAP、保守滑点、市场冲击，缺 TWAP/IS 枚举和成交假设。

### 本轮落地

- 新增 `black_litterman_optimizer.py`，`/api/backtests/{run_id}/portfolio-optimization?method=black_litterman` 可返回 BL 权重和有效前沿。
- 新增 `/api/backtests/live-comparison`，比较模拟盘真实平仓收益与最近回测收益差，发现策略实盘损耗。
- 新增 `/api/market/alternative-sentiment`，基于缓存新闻/公告/社交事件源输出研究层情绪分，不进入自动交易。
- 新增 `/api/market/multi-exchange-arbitrage/research`，明确多交易所套利当前为研究边界，不把 Provider 价差误当可交易机会。
- Backtest execution model 新增 `twap` 和 `implementation_shortfall`，并写入前端选项和执行假设。

### 本轮验证

- `backend/.venv/bin/python -m compileall backend/app backend/tests/test_quant_enhancement_completion.py -q` 通过。
- `cd backend && .venv/bin/python -m pytest tests/test_quant_enhancement_completion.py tests/test_ml_markowitz_regime_rl.py tests/test_bff_routes.py -q` 通过，18 passed。
- `cd frontend && npm run build` 通过。

## 因子挖掘系统落地计划

需求来源：`/Users/j/Downloads/TQuant_因子挖掘系统规划方案.html`

### 目标

1. 建立因子库、因子沙盒计算、因子评估、LLM/本地假设生成、代码合成、解释与迭代闭环。
2. 新增后端 API 与数据库表，支持候选因子从 `candidate` 到 `validated/production/rejected/archived` 的生命周期。
3. 在策略工作台新增“因子实验室”入口，支持假设生成、因子创建、评估、晋级查看。
4. 所有新增文件保持 500 行以内，不改动现有策略买卖语义。

### TODO

- [x] 新增 FactorDefinition / FactorEvalRun / FactorApproval 数据模型与 Alembic 迁移。
- [x] 新增 factor_mining 服务包：模型、因子库、沙盒计算、评估、假设生成、代码合成、结果解释、迭代循环、生产集成。
- [x] 新增 `/api/factor-mining/*` 路由，覆盖列表、创建、假设生成、代码合成、评估、迭代、晋级和异步评估入队。
- [x] 策略工作台增加“因子实验室”Tab 与前端 API。
- [x] 增加后端单元测试，覆盖 AST 安全、假设生成数量、评估指标和 API 基础契约。
- [x] 运行 Python 编译、针对性 pytest、前端构建验证。

### 已验证

- `backend/.venv/bin/python -m compileall backend/app backend/alembic/versions -q` 通过。
- `backend/.venv/bin/python -m pytest backend/tests/test_factor_mining.py backend/tests/test_factor_registry.py backend/tests/test_strategy_evolution_scheduler_tasks.py -q` 通过，11 passed。
- `PYTHONPATH=backend DATABASE_URL=sqlite:////tmp/... AUTH_SECRET_KEY=test-secret backend/.venv/bin/alembic -c backend/alembic.ini upgrade head` 通过。
- `npm run build` 通过。
- `make qa` 通过。

### 实施说明

- DeepSeek 适配器固定默认模型 `deepseek-v4-flash`；未配置或接口失败时自动使用本地结构化模板，确保功能不中断。
- 生产晋级只允许评估结果达到 production gate 后执行，并记录操作审计；动态因子先注册到因子库和 FactorSpec 元数据，不会静默改变现有策略评分。

## v4 五大整改包剩余项实施计划

需求来源：`docs/TQuant-v4-五大整改包整改需求计划-2026-05-09.md`

### 当前批次目标

1. P1：补齐 UserSession refresh hash 唯一索引迁移检查、操作审计覆盖、自动退出行情质量结构化、Provider 自适应排序。
2. P2：补齐优先榜 Redis 分布式缓存、Walk-forward 按市场状态输出最佳参数。
3. P2/P3：补齐 RBAC/MFA、外部因子多 Provider、本地数据优先、组合优化/RL 研究、Web/Native API Client 解耦、个性化 SSE、审计入口和验收测试。

### 实施约束

- 单文件保持 500 行以内。
- 新功能优先新建小文件。
- 不改变核心策略阈值和买卖逻辑。
- 数据库结构调整必须通过 Alembic 迁移。

### TODO

- [x] UserSession refresh_token_hash 迁移前重复校验 + 显式唯一索引。
- [x] 高风险 mutating API 自动写 operation_audit_log。
- [x] 自动退出计划返回结构化行情质量，不使用旧价兜底。
- [x] Provider Router 根据成功率和延迟做自适应排序。
- [x] 优先榜响应缓存支持 Redis 跨 worker 共享，Redis 不可用降级进程缓存。
- [x] Walk-forward by_market_state 输出最佳参数和窗口详情。
- [x] SSE 增加事件 id / Last-Event-ID 兼容。
- [x] 统一 RBAC helper，模拟盘权限支持动态验证码强制策略。
- [x] 外部因子支持 Local + AkShare 多 Provider 降级链路。
- [x] 市场状态、热点行业和优先榜支持 Redis 跨 worker 缓存。
- [x] Local Provider 补齐行业映射、行业资金流、本地涨停快照和热点板块降级。
- [x] Backtest 增加策略组合 HRP/均值方差优化研究接口。
- [x] Backtest 增加离线仓位策略研究接口，明确不进入自动交易。
- [x] Web / Native API 增加 IApiClient 注入抽象，桌面与 App API 包装层复用。
- [x] 系统配置页增加操作审计入口。
- [x] 补充/运行针对性测试。

### 已验证

- `make qa` 通过。
- `backend/.venv/bin/python -m compileall backend/app backend/alembic/versions -q` 通过。
- `backend/.venv/bin/python -m pytest backend/tests/test_v4_remaining_contracts.py backend/tests/test_security_quant_extensions.py backend/tests/test_phase4_phase5_foundation.py backend/tests/test_pkg02_pkg04_contracts.py backend/tests/test_market_provider_contract.py -q` 通过，45 passed。
- `backend/.venv/bin/python -m pytest backend/tests/test_auth_cookie_security.py backend/tests/test_login_lockout.py backend/tests/test_security_headers.py backend/tests/test_v4_completion_contracts.py backend/tests/test_v4_remaining_contracts.py -q` 通过，10 passed。
- `npm run build` 通过。
- 生产代码文件未发现超过 500 行；现存超过 500 行的是既有测试文件。

## v7 全界面易用性优化执行计划

来源：`/Users/j/Downloads/TQuant_v7_深度报告_含UX优化.html`

### 目标

- 所有核心页面优先展示“现在该做什么 / 买卖边界 / 错了怎么办”。
- 减少英文和不必要专业术语，保留必要金融指标但增加中文解释。
- 不修改策略计算、交易规则、后端权限和数据库结构。
- 以低风险前端整改为主，保证现有功能可回归。

### 实施项

1. 登录页：补齐登录中/验证成功反馈、MFA 明确说明、错误处理下一步提示。
2. 实时监控页：增加“今天我该做什么”摘要；录入字段增加示例；持仓和榜单卡片突出当前动作、风险和失效条件。
3. 选股宝典：策略页签增加用途说明；分层文案改为“现在可买 / 等确认 / 继续观察”；评分用星级辅助表达。
4. 模拟盘：增加“系统今日动作日志 / 需要处理 / 分时确认”顶部操作区；保留自动交易与风险说明。
5. 个股分析：增加综合判断大卡片；把 AI 和复杂指标放在次级说明。
6. 回测页面：增加快速/专家模式、结果自然语言判断、进度等待说明。
7. 策略工作台：增加四步流程导览和红黄绿健康语义。
8. 研究复盘：把复盘样本改成案例故事式展示，强调样本量可信度。
9. 系统配置：补充“我的账户 / 交易参数 / 系统管理”分区提示。
10. 绩效看板：增加自然语言总结和策略赚钱/亏钱排行条。
11. 移动端：首页增加“今天最重要一件事”；选股宝典默认聚焦可执行候选；登录支持 MFA 数字输入。
12. 移动登录：补齐动态验证码字段和清晰的错误提示。

### 验证

- 已通过 `npm run build`。
- 本轮只涉及前端易用性和移动端登录参数，不改动策略计算、交易规则和数据库。

### 完成状态

- 12 项界面易用性整改均已落地到对应页面或移动端入口。
- 生物识别快速登录未接入原生插件，本轮以“后续可接入”的安全提示呈现，避免伪造不可用功能。

## SmartT 成功率、防过拟合与情绪温度计闭环

来源：用户 2026-05-14 需求。

### 目标

1. 做T 入场必须同时满足缩量、低点不破、时间窗口、VWAP 折价、市场状态和盈利持仓条件。
2. 做T 仓位必须有止盈、止损、时间退出和冲高回落退出计划。
3. 市场状态增加情绪温度计，用于“冷 / 温 / 热 / 过热”更细粒度入场判断。
4. 新策略引入 Phase 1/2/3 渐进验证，避免未经验证策略直接放大。
5. ML 晋级增加 Bootstrap 置信区间、AUC gap、特征集中度和漂移监控。
6. 选股质量增强以因子加分方式落地，不直接改变原策略买点阈值。

### TODO

- [x] SmartT 加仓门槛：volume_release_ratio、low_rising、VWAP 折价、时间过滤、市场状态过滤、盈利持仓过滤。
- [x] SmartT 动态参数：市场状态自适应 expected_rebound_pct、账户盈亏自适应 cash_pct、单轮标的数上限。
- [x] SmartT T 仓退出：止盈、0.6% 止损、60 分钟时间退出、冲高回落退出。
- [x] 情绪温度计：冷 / 温 / 热 / 过热分类，并接入市场快照、优先榜和 App 投影。
- [x] Phase 1/2/3 渐进验证：影子观察、小仓验证、标准执行字段接入策略治理。
- [x] ML 防过拟合：Bootstrap CI、训练/验证 AUC gap、特征重要性集中度晋级阻断。
- [x] ML 漂移监控：近期样本 vs 基线样本 KL 散度，输出漂移告警。
- [x] 选股质量因子：连续缩量、健康回踩、启动动能、派发风险和假突破惩罚接入因子注册表与参数版本系统。

### 已验证

- `backend/.venv/bin/python -m pytest backend/tests/test_paper_smart_t.py backend/tests/test_paper_dynamic_exit.py backend/tests/test_paper_smart_t_backtest.py backend/tests/test_market_regime_strategy_p2.py backend/tests/test_market_routes.py backend/tests/test_ml_markowitz_regime_rl.py -q` 通过，41 passed。
- `backend/.venv/bin/python -m pytest backend/tests/test_phase4_phase5_foundation.py backend/tests/test_pkg02_pkg04_contracts.py -q` 通过，31 passed。
- `backend/.venv/bin/python -m pytest backend/tests/test_factor_registry.py backend/tests/test_paper_smart_t.py backend/tests/test_paper_dynamic_exit.py backend/tests/test_paper_smart_t_backtest.py -q` 通过，18 passed。
- `backend/.venv/bin/python -m pytest backend/tests/test_market_regime_strategy_p2.py backend/tests/test_market_routes.py backend/tests/test_phase4_phase5_foundation.py backend/tests/test_pkg02_pkg04_contracts.py backend/tests/test_ml_markowitz_regime_rl.py -q` 通过，57 passed。

## 策略自进化与在线学习闭环

来源：用户 2026-05-15 需求。

### 目标

1. 每笔模拟盘平仓继续写入 `MLSignalSample`，作为在线学习样本。
2. 每周五收盘后自动编排“增量训练 → 显著性验证 → 参数晋级草案 → Phase 评估”。
3. 训练结果达到门槛后只生成晋级候选，必须管理员审批后才进入 production。
4. 每月执行特征漂移监控，输出漂移告警。

### TODO

- [x] 新增 `StrategySelfEvolutionOrchestrator`，串联增量训练、在线学习状态、漂移监控、分市场状态参数晋级草案和 Phase 评估。
- [x] 新增 APScheduler 调度，每周五 16:05 入队策略自进化任务，每月 1 日 16:35 入队漂移监控任务。
- [x] runtime worker 支持 `strategy_self_evolution` 与 `ml_feature_drift_monitor` 任务。
- [x] 增量训练默认 `promote=False`，训练达标后标记 `promotion_candidate/approval_required`。
- [x] 新增管理员审批接口 `/api/ml/signals/models/{model_key}/approve-promotion`。
- [x] 保留 runtime loop 兜底调度，APScheduler 不可用时不影响系统启动。

### 验证

- 本轮将运行 Python 编译和针对性 pytest。
