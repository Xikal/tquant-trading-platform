# Frontend Next Gap Audit - 2026-06-06

状态：superseded by 2026-06-07 cutover blocker remediation audit；旧 `frontend/` 与新 `frontend-next/` 功能差异审计
范围：静态代码、既有验收报告、路由/API/页面能力对照；未部署、未切流
结论：本报告保留为 2026-06-06 历史审计基线；当前准确信息以 `docs/frontend-next-cutover-blocker-remediation-plan-2026-06-07.md`、`docs/frontend-next-feature-parity-matrix-2026-06-05.md` 和 `docs/reports/frontend-next-acceptance-2026-06-05.md` 的 2026-06-07 更新为准。`frontend-next/` 已完成 shadow 页面、功能级 E2E、视觉一致性和两交易日 shadow aggregate；仍因安全写 production-ready、正式 admin/API 复验和 cutover 授权未完成，不具备 cutover 条件。

## 1. 当前 Git 状态

本次审计开始前执行：

```bash
cd /Users/j/Documents/gupiao
git status --short
```

输出：

```text
 M frontend/src/features/trading-workspace/TradingWorkspaceChrome.test.ts
?? docs/frontend-next-architecture-design-2026-06-05.md
?? docs/frontend-next-cutover-runbook-2026-06-05.md
?? docs/frontend-next-feature-parity-matrix-2026-06-05.md
?? docs/frontend-next/
?? docs/reports/frontend-next-acceptance-2026-06-05.md
?? docs/reports/frontend-next-baseline-2026-06-05.md
?? docs/reports/frontend-next-open-items-2026-06-05.md
?? docs/reports/frontend-next-screenshots-2026-06-05/
?? docs/reports/frontend-next-shadow-sample-2026-06-05.json
?? docs/reports/frontend-next-shadow-samples/
?? docs/reports/frontend-next-two-day-shadow-run-2026-06-05.json
?? docs/reports/frontend-next-visual-review-2026-06-05/
?? docs/reports/frontend-next-visual-signoff-2026-06-05.md
?? docs/reports/frontend-next-write-rollback-smoke-2026-06-05.json
?? docs/superpowers/plans/2026-06-05-rust-realtime-backtest-workers.md
?? frontend-next/
```

本次审计新增本报告；未修改后端，未修改 `strategy_policy.py`，未部署，未切流。

## 2. 总体差异

| 维度 | 旧 `frontend/` | 新 `frontend-next/` | 审计结论 |
|---|---|---|---|
| 功能模块规模 | `frontend/src/features` 下约 255 个文件，含完整工作台、分析、选股、监控、模拟盘、策略跟踪、回测、数据台、设置等 | `frontend-next/src/features` 下约 16 个文件，多数页面为单文件 shell | 新前端功能深度明显不足 |
| 路由 | `/monitor`、`/monitor/market`、`/analysis`、`/playbook`、`/strategy-tracking`、`/backtest`、`/paper`、`/data`、`/settings`，并含 `/emotion`、`/low-buy`、`/strategy`、`/performance` 兼容跳转 | 仅 `/next/monitor`、`/next/monitor/market`、`/next/paper`、`/next/strategy-tracking`、`/next/analysis`、`/next/playbook`、`/next/backtest`、`/next/data`、`/next/settings` | 主路由齐，但兼容跳转缺失 |
| API 能力 | `frontend/src/api/client.ts` 覆盖 watchlist、market、analysis、settings、strategy tracking、paper、backtest、data/admin 等完整接口 | `frontend-next/src/shared/api/client.ts` 只有 6 个读接口；`mutations.ts` 只有 paper order、backtest、feature flag 三类 guarded live 写，strategy/data 仍是 `shadow://` | API parity 未完成 |
| 全局工作台 | 登录/注册/刷新登录、MFA、权限守卫、Command Palette、快捷键、用户菜单、移动抽屉、AI 对话、股票详情弹窗、自动刷新 | 静态侧边栏 + 顶部时钟/交易时段/SSE 状态 | 全局产品能力缺失 |
| 测试覆盖 | 旧前端覆盖大量业务组件和页面逻辑 | 新前端当前主要覆盖 9 路由 smoke、机甲可见、no-write 交互、worker sync 和 mutation guard | 新测试不能证明功能复刻 |

## 3. P0 Cutover 阻断项

1. 认证与权限体系未复刻
   旧前端有 login/register/refresh/logout/getMe/TOTP 和 session restore；新前端只读取本地 token 并拼 header，没有登录页、刷新会话、退出、MFA、用户菜单、`can_paper_trade`/admin 页面守卫。
   证据：`frontend/src/api/appClient.ts:41-91`、`frontend/src/features/trading-workspace/TradingWorkspace.tsx:221-255`、`frontend-next/src/shared/api/auth.ts:1-36`。

2. 核心写操作没有完整业务流
   旧前端模拟盘、设置、数据台、策略复盘、回测都有真实表单、校验、提交和刷新链路；新前端多数是固定字段 `ShadowActionPanel`，默认不发真实写请求。
   证据：`frontend-next/src/shared/api/mutations.ts:24-80`、`frontend-next/tests/e2e/interaction-parity.spec.ts:51-69`。

3. 分析页和选股宝典基本是样式壳
   旧 `/analysis` 支持真实输入、开始分析、批量排序、关键位、盘中异常、K 线和模拟下单入口；新 `/next/analysis` 使用 readOnly/sample chart，没有 API 调用。旧 `/playbook` 支持策略 tabs、候选分层、绩效归因、刷新、分析/选中；新 `/next/playbook` 使用 samplePriorityItems。
   证据：`frontend/src/features/analysis/AnalysisPage.tsx:11-220` vs `frontend-next/src/features/analysis/AnalysisPage.tsx:7-27`；`frontend/src/features/playbook/PlaybookPage.tsx:24-165` vs `frontend-next/src/features/playbook/PlaybookPage.tsx:15-27`。

4. 模拟盘没有完整交易/复盘能力
   旧 `/paper` 有账户结论、持仓、委托录入弹窗、生产买入信号导入、买卖方向、数量快捷、暂停/恢复、风险、自动交易、成交/订单/绩效/标签/对账详情；新 `/next/paper` 只读账户和持仓，委托为固定字段 shadow 记录。机甲头像和粒子已显示，但只覆盖 display/review。
   证据：`frontend/src/features/paper/PaperTradingPage.tsx:55-229`、`frontend/src/features/paper/PaperOrderEntryModal.tsx:95-320` vs `frontend-next/src/features/paper/PaperPage.tsx:16-67`。

5. 策略跟踪缺少过滤、详情和复盘闭环
   旧 `/strategy-tracking` 有状态/模式切换、筛选抽屉、分页、详情抽屉、表现/持有/漂移/诊断/复盘中心 tabs、交易日志增删改；新 `/next/strategy-tracking` 只有概览指标、表格和固定字段复盘记录。
   证据：`frontend/src/features/strategy-tracking/StrategyTrackingPage.tsx:29-171`、`frontend/src/features/strategy-tracking/StrategyReviewWorkspacePanel.tsx:14-85` vs `frontend-next/src/features/strategy-tracking/StrategyTrackingPage.tsx:16-71`。

6. 回测研究闭环未复刻
   旧 `/backtest` 有提交任务、运行列表、结果概览、成交明细、ETF T0、研究闭环、策略验证/优化/对比/取消任务等；新 `/next/backtest` 只展示 run list、sample ECharts 曲线、shadow 提交。
   证据：`frontend/src/features/backtest/BacktestDashboard.tsx:53-225` vs `frontend-next/src/features/backtest/BacktestPage.tsx:15-59`。

7. 数据中心与设置页缺少 admin 运维功能
   旧 `/data` 有 admin 权限、数据健康、交易数据门禁、源健康、覆盖率、Worker 观测、管理令牌、同步标的、刷新收盘、补历史、修复 dry-run/apply、个股检查、ETF/股票池维护；新 `/next/data` 是待查询占位和 shadow 采集任务。旧 `/settings` 有账户安全、行业排除、风控、LLM、因子、量化参数、策略治理、feature flag 审计、操作审计；新 `/next/settings` 只有运行状态占位和单一 feature flag shadow 写入。
   证据：`frontend/src/features/data-console/DataConsolePage.tsx:20-225` vs `frontend-next/src/features/data-console/DataConsolePage.tsx:9-42`；`frontend/src/features/settings/SettingsPage.tsx:56-360` vs `frontend-next/src/features/settings/SettingsPage.tsx:13-60`。

## 4. 页面级缺失矩阵

| 页面 | 新前端当前状态 | 缺少的旧前端能力 | 阻断等级 |
|---|---|---|---|
| `/next/monitor` | 接 monitor BFF，展示优先榜/持仓/风险摘要 | 持仓录入抽屉、观察池增删改、策略 lane 切换、AI 榜单解读、去分析/选股动作、关键位/量价标签独立查询、风险过滤 badges 完整展示 | P0 |
| `/next/monitor/market` | 接 monitor market BFF，展示市场总闸/宽度/ETF/复盘摘要 | 大盘关键位、板块龙头确认、MarketReviewPanel 完整报告、InstrumentSyncProgress 交互和刷新链路 | P1 |
| `/next/paper` | 账户/持仓只读、机甲 HUD、固定 shadow 委托 | 订单弹窗真实表单、推荐导入、买卖/数量快捷、暂停恢复、自动交易状态、风险事件、绩效详情、标签、对账修复、详情 tabs | P0 |
| `/next/strategy-tracking` | BFF 表格 + 固定 shadow 复盘 | 筛选抽屉、分页/排序、详情抽屉、模式切换、表现/持有/漂移/诊断/复盘中心、交易日志 CRUD、relative strength | P0 |
| `/next/analysis` | readOnly 输入、sample K 线 | `/analyze`、`/analyze/batch`、关键位、盘中异常、AI 补充、模拟下单入口、批量排序 | P0 |
| `/next/playbook` | sample 候选池 | 真实 screener API、生产/观察策略 tabs、候选分层、绩效归因、刷新、分析/选中联动、仪式 UI | P0 |
| `/next/backtest` | run list + sample 曲线 + shadow 提交 | submit panel 完整参数、run detail/equity/trades、cancel、ETF T0、validation、optimization、compare、research tabs | P1 |
| `/next/data` | 占位 + shadow 采集任务 | admin guard、SLA/gate/source/coverage/tasks/worker/repair/inspector/ETF universe 全链路 | P1 |
| `/next/settings` | 占位 + shadow feature flag | auth security、MFA、sector exclusions、risk/LLM/data/factor/quant params、strategy governance、audit、latest data refresh | P1 |

## 5. 已有验收报告的真实含义

`docs/reports/frontend-next-acceptance-2026-06-05.md` 已记录：

- 新前端工程命令、截图采样、API smoke、请求/SSE trace、no-write shadow interaction 通过。
- 两交易日 shadow run 仍是 1/2。
- strategy review/data job 仍缺明确安全写 API。
- 视觉人工签收仍未完成。
- cutover/部署未执行。

这些结果证明新前端作为 `/next/*` shadow 预览是安全的，但不能证明旧前端功能已经完整复刻。

## 6. 不影响平台功能的原因

当前结论：不影响现有平台功能。

原因：

- 本次审计只新增报告。
- 旧 `frontend/` 生产代码未在本次审计中修改。
- 后端未修改。
- `strategy_policy.py` 未修改。
- 未部署、未切流。
- 新前端仍挂在 `/next/*`，且写入默认关闭。

## 7. 建议补齐顺序

1. P0-A：补认证/用户/权限/全局工作台能力，包括 LoginPage、session restore、logout、paper/admin guard、Command Palette、移动导航。
2. P0-B：补 `/next/analysis` 和 `/next/playbook` 真实 API 与联动，这是当前最明显的“页面存在但功能不存在”缺口。
3. P0-C：补 `/next/paper` 完整订单弹窗、暂停/恢复、详情 tabs、绩效/风险/标签/对账。
4. P0-D：补 `/next/strategy-tracking` 筛选、详情、复盘中心和日志 CRUD。
5. P1：补 `/next/backtest`、`/next/data`、`/next/settings` 的研究/运维/配置完整链路。
6. 验收：补功能级 E2E，而不是只验证 smoke/no-write；随后再做两交易日 shadow、视觉人工签收和 cutover 评审。

## 8. Cutover 判断

当前不建议 cutover。

原因不是视觉，而是功能 parity 缺失：新前端现有页面能展示部分数据，但无法替代旧前端完成日常分析、选股、模拟盘、策略复盘、回测研究、数据维护和系统配置工作流。
