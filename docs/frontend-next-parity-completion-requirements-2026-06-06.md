# Frontend Next Parity Completion Requirements - 2026-06-06

状态：需求与系统设计文档，未实施
依据：`docs/reports/frontend-next-gap-audit-2026-06-06.md`
范围：补齐 `frontend-next/` 相对旧 `frontend/` 的功能 parity；旧前端实现不合理处可在新架构中直接优化，优化原则是提升易用性、可用性和稳定性，同时保持当前视觉风格、生产口径和可回滚边界

## 1. 背景与问题

`frontend-next/` 已完成独立 SolidJS/Vite shadow 应用、基础路由、部分 BFF 读取、截图采样、no-write 交互和机甲展示。但 gap audit 证明它仍不是完整复刻：认证、分析、选股、模拟盘、策略跟踪、回测、数据中心、设置等旧前端核心工作流存在明显缺口。

本需求文档的目标是把这些缺口转成可实施的系统设计，避免后续只补页面外观、继续形成单文件页面或临时 API wrapper。

## 2. 目标

1. 在 `frontend-next/` 中完整补齐旧 `frontend/` 当前核心功能。
2. 继续使用 SolidJS + TypeScript + Vite + TanStack Router/Query/Table/Virtual。
3. API 类型只来自 `docs/contracts/openapi.json` 生成产物，不手写重复 DTO。
4. 页面视觉、密度、文案语气沿用旧前端，不做视觉重设计。
5. 使用成熟组件和本地 wrapper，禁止直接暴露第三方默认样式。
6. Worker 只做显示层排序、过滤、派生、downsample，不参与生产策略判断。
7. 保持 `/next/*` shadow 验证，满足功能/数据/截图/性能 gate 后再讨论 cutover。
8. 功能 parity 以用户能力、数据口径、权限边界和验收结果为准，不要求复制旧前端内部实现；旧实现若降低易用性、可用性或稳定性，新前端应直接优化。

## 3. 非目标与硬边界

1. 不部署。
2. 不切流。
3. 不修改 `strategy_policy.py`。
4. 不改变生产策略语义、生产排序、`production_score`、`priority_board` 口径。
5. 不把策略判断迁移到前端。
6. 不让前端 Worker/WASM 成为唯一实现路径，必须保留同步 fallback。
7. 不把机甲头像、执行日志、动效结果接入生产排序或信号计算。
8. 不为了新前端修改旧 `frontend/` 生产代码。
9. 后端代码默认不动；若缺明确安全写 API，先保留 shadow-only 并形成后端契约需求，不在前端伪造写入。

## 3.1 旧实现优化授权

如果旧前端存在明显不合理实现，新前端可以直接优化，不需要机械复刻旧代码结构或旧交互缺陷。优化目标只允许围绕“易用性”、“可用性”和“稳定性”展开。

易用性优化包括：

1. 减少完成核心任务的点击、跳转和重复输入。
2. 把高频操作放在用户当前上下文内，例如从分析结果直接打开模拟委托、从候选卡片直接进入详情或分析。
3. 统一表单、抽屉、弹窗、二次确认、成功/失败反馈，降低学习成本。
4. 改善空态、错误态、加载态，让用户知道下一步能做什么。
5. 优化筛选、搜索、分页、快捷键和 Command Palette，减少找功能的成本。
6. 保留旧前端中文文案语气，但可以删掉多余解释，优先展示可执行信息。

可用性优化包括：

1. 避免重复请求、重复 SSE、页面不可见时继续刷新图表或重计算。
2. 大表和长列表默认虚拟化，避免数据量上来后卡顿。
3. 表单字段有明确校验和禁用态，危险操作有二次确认。
4. API partial error、权限不足、数据缺失、任务失败必须可见，不能静默成功。
5. 写入默认 shadow，live-smoke 必须可回滚；缺安全写 API 时不伪造成功。
6. 支持 `prefers-reduced-motion`，动效不能影响交易判断和可读性。

稳定性优化包括：

1. 所有页面必须有 route-level error boundary，单个页面失败不能拖垮整个 app shell。
2. API 请求支持超时、取消过期请求、认证过期恢复和明确错误提示。
3. TanStack Query 缓存、invalidate 和 optimistic/rollback 策略必须按 feature 管理，避免脏数据跨页污染。
4. mutation 必须防重复提交；危险写操作必须有二次确认、提交中禁用和失败恢复。
5. SSE、Worker、图表实例、定时器和事件监听必须在路由离开或组件销毁时释放。
6. BFF partial error、后端 5xx、网络断开、空数据和权限不足必须可降级展示，不能白屏。
7. 对关键页面保留 shadow/sample/replay 验证，避免只在本地 mock 数据下通过。
8. 新增动效、机甲 Canvas 和图表更新不得造成内存泄漏或持续 CPU 占用。

允许直接优化的旧实现问题：

1. 单文件过大、页面同时承担拉取/状态/布局/表格/图表/表单。
2. 宽 props、全局 store 耦合、高频行情触发整页刷新。
3. 非业务性 `.slice(0, N)` 截断、未虚拟化列表、未分页大表。
4. 表单校验、错误态、确认弹窗散落各处。
5. 图表初始化/销毁不规范，不可见图表仍占资源。
6. 旧交互路径绕路、重复点击多、反馈不清晰。
7. 旧实现中仅为 React/AntD 历史包袱存在的结构。

必须保持不变：

1. 用户最终能完成的业务能力。
2. 生产优先榜顺序、`priority_board`、`production_score` 和策略语义。
3. API 字段口径、收益/评分/状态解释。
4. 权限、feature flag、研究/生产/模拟盘边界。
5. 页面视觉风格、密度、颜色、字号、文案语气。

每个优化项必须记录：

1. 旧实现问题。
2. 新前端优化方案。
3. 对易用性或可用性的具体收益。
4. 对稳定性的具体收益或无风险说明。
5. 保持不变的业务口径。
6. 验收证据：测试、截图、request trace、error recovery 或 perf compare。

## 4. 目标用户与核心场景

1. 交易操作者：每天进入实时行动台，判断是否有可执行标的、持仓是否需要处理、模拟盘是否需要操作。
2. 市场复盘者：查看市场总闸、宽度、板块、ETF、复盘报告，判断环境是否支持策略执行。
3. 策略研究者：使用分析、选股宝典、策略跟踪、回测，验证策略表现和样本外状态。
4. 运维/管理员：查看数据健康、任务状态、数据修复、设置、功能开关、审计记录。
5. 普通观察用户：可查看行情、策略和复盘，但受权限限制不能进入模拟盘写入或 admin 操作。

## 5. 信息架构

`frontend-next` 继续保持以下正式目标路由：

| 新路由 | 目标能力 |
|---|---|
| `/next/monitor` | 实时行动台、生产优先榜、持仓/自选、关键位、策略分层、AI 榜单解读入口 |
| `/next/monitor/market` | 市场总闸、市场宽度、日内脉冲、板块轮动、ETF T0、市场复盘、运行时状态 |
| `/next/analysis` | 单票量化分析、批量分析、关键位、异常提醒、K 线、模拟下单联动 |
| `/next/playbook` | 生产/观察策略页签、候选分层、绩效归因、实时报价刷新、分析/选中联动 |
| `/next/paper` | 模拟盘账户、委托录入、持仓、订单、成交、绩效、风险、标签、对账、机甲 display/review |
| `/next/strategy-tracking` | 策略跟踪、筛选、详情、表现、持有分析、漂移、诊断、复盘中心、交易日志 |
| `/next/backtest` | 回测提交、任务列表、详情、收益曲线、成交明细、ETF T0、验证、优化、对比 |
| `/next/data` | 数据健康、交易数据门禁、源健康、覆盖率、Worker 观测、数据任务、修复、个股检查 |
| `/next/settings` | 账户安全、风控、行业排除、LLM、因子、量化参数、策略治理、功能开关、审计 |

兼容跳转要求：

| 旧兼容入口 | 新兼容入口 |
|---|---|
| `/emotion -> /monitor` | `/next/emotion -> /next/monitor` |
| `/low-buy -> /playbook` | `/next/low-buy -> /next/playbook` |
| `/strategy -> /backtest` | `/next/strategy -> /next/backtest` |
| `/performance -> /paper` | `/next/performance -> /next/paper` |

## 6. 端态架构

```text
FastAPI / BFF / OpenAPI
  -> generated api-types
  -> shared/api operation adapters
  -> feature query/mutation modules
  -> TanStack Query screen-model cache
  -> Solid signals realtime store
  -> Worker display compute with sync fallback
  -> shared/ui wrappers
  -> feature pages and route-level chunks
```

关键原则：

1. 页面不直接拼 URL；所有请求经过 `shared/api` 或 feature-level typed operation。
2. Query key 按 feature 统一声明，禁止散落字符串。
3. 写入操作必须经过 `shared/api/mutations` 的 guarded adapter，并区分 `shadow`、`isolated-live-smoke`、`live`。
4. 页面组件只负责布局和交互，业务数据组装放到 feature model/query/mutation 文件。
5. 表格、虚拟列表、弹窗、抽屉、表单、状态条、确认动作都通过 `shared/ui` wrapper。

## 7. 目录设计

新增和收敛后的建议结构：

```text
frontend-next/src/
  app/
    AppShell.tsx
    routeTree.tsx
    guards.ts
    keyboardShortcuts.ts
  shared/
    api/
      operations.ts
      auth.ts
      client.ts
      mutations.ts
      queryKeys.ts
    form/
      fields.tsx
      validators.ts
    motion/
      motionTokens.ts
      useReducedMotion.ts
      LiveFlash.tsx
    ui/
      Button.tsx
      DataGrid.tsx
      DataTable.tsx
      VirtualList.tsx
      VirtualCardList.tsx
      Modal.tsx
      Drawer.tsx
      ConfirmAction.tsx
      Toast.tsx
      CommandPalette.tsx
      Toolbar.tsx
      Segmented.tsx
      StatusPill.tsx
      Skeleton.tsx
    realtime/
    workers/
    charts/
  features/
    auth/
      LoginPage.tsx
      authQueries.ts
      authModel.ts
    trading-workspace/
      WorkspaceShell.tsx
      UserMenu.tsx
      StockDetailDialog.tsx
      AiInsightDialog.tsx
    monitor-action/
      MonitorActionPage.tsx
      monitorActionQueries.ts
      monitorActionModel.ts
      components/
    monitor-market/
    analysis/
      AnalysisPage.tsx
      analysisQueries.ts
      analysisModel.ts
      components/
    playbook/
    paper/
    strategy-tracking/
    backtest/
    data-console/
    settings/
```

单文件规模要求遵循 `docs/engineering-conventions.md`：页面文件目标不超过 300 行；新增复杂页面必须拆成 page、query、model、panel/table/form。

## 8. 成熟组件策略

优先使用当前已安装且成熟的库：

| 能力 | 组件/库 | 使用方式 |
|---|---|---|
| 路由 | TanStack Router | typed route、lazy route、route guard |
| 服务端状态 | TanStack Query for Solid | query cache、mutation state、失效刷新 |
| 表格 | TanStack Table | 封装到 `shared/ui/DataTable`，支持列定义、排序、筛选、分页、空态 |
| 长列表 | TanStack Virtual | 封装到 `VirtualCardList`，用于优先榜、候选池、复盘队列 |
| K 线 | Lightweight Charts | 用 `KlineChart` adapter，增量更新、crosshair、稳定尺寸 |
| 低频图表 | ECharts adapter | 仅低频图表 lazy import，避免污染首屏 |
| 高频状态 | Solid signals | 行情、时钟、连接态、局部 PnL |
| 显示层计算 | Web Worker | sort/filter/derive/downsample，带 sync fallback |

不新增大型 UI 组件库。若后续确需引入表单/浮层辅助库，必须先写 ADR，证明它比本地 wrapper 更少返工且不会引入默认视觉。

## 9. 交互与动效策略

动效目标是帮助读状态和确认操作，不做装饰性重设计。

全局动效：

1. 面板进入：100-140ms opacity + 4px translate，路由切换只作用于内容区。
2. 行情变化：价格/浮盈亏 leaf cell 使用 600ms 红绿轻闪，不能触发整表重排。
3. 表格/列表 hover：150ms 背景和边框过渡。
4. 筛选/搜索：列表结果使用稳定高度与轻量交错，不改变滚动位置。
5. 加载态：数据区用 skeleton，不用大面积 spinner。
6. 写入确认：统一二次确认、提交中、成功、失败四态。
7. 机甲特效：只在 `/next/paper` display/review 区域，Canvas 粒子与日志流尊重 `prefers-reduced-motion`。

页面动效：

| 页面 | 允许动效 | 禁止 |
|---|---|---|
| monitor | 新入榜行轻闪、风险标签 hover、市场状态变化提示 | 生产榜本地重排动画 |
| market | 宽度/脉冲图表 crosshair、数据质量状态过渡 | 自动播放式炫技动画 |
| analysis | 分析完成结果区聚焦、K 线 crosshair、批量排序完成高亮 | AI/策略结果夸张动效 |
| playbook | 切换策略页签保留滚动边界、候选状态高亮 | 把观察票动画成买入信号 |
| paper | 机甲状态、委托确认、成交/拒单状态反馈 | 机甲影响策略或排序 |
| strategy-tracking | 筛选抽屉、详情抽屉、复盘日志提交反馈 | 隐藏过滤条件或结果漂移 |
| backtest | 任务状态进度、图表 crosshair | 假进度、假成功 |
| data/settings | 危险操作确认、保存成功轻提示 | 自动执行或静默提交 |

所有动效必须支持 `prefers-reduced-motion: reduce`。

## 10. 功能需求

### 10.1 全局工作台与认证

必须实现：

1. 登录、注册、刷新会话、退出。
2. 认证恢复：优先本地 access token，再尝试 httpOnly refresh cookie。
3. MFA/TOTP 设置、启用、停用。
4. 用户菜单：进入设置、退出登录。
5. 权限守卫：
   - 未登录显示登录页。
   - 无 `can_paper_trade` 显示模拟盘白名单提示。
   - 非 admin 访问数据中心/管理设置时显示权限提示。
6. Command Palette：
   - `Cmd/Ctrl+K` 打开。
   - 支持页面跳转、策略跳转、6 位股票代码进入分析。
   - `Esc` 关闭，`Enter` 执行。
7. 页面快捷键：`Cmd/Ctrl+1~8` 切换核心页面。
8. 移动端导航抽屉。
9. 全局 notice/error/toast，不使用浏览器 alert。

验收：

1. 登录态刷新页面不丢失用户。
2. 401 后能触发刷新或回到登录页。
3. paper/admin guard E2E 覆盖。
4. Command Palette E2E 覆盖页面、策略、股票代码三类命令。

### 10.2 API 与数据层

必须补齐 typed operation：

1. `auth`：login/register/refresh/logout/me/TOTP。
2. `monitor`：workspace BFF、key levels、watchlist add/edit/delete、AI decision support、instrument sync。
3. `analysis`：analyze、analyzeBatch、intraday anomaly、stock key levels。
4. `playbook`：low-buy candidates、strategy meta、quote refresh、priority board。
5. `paper`：workspace、positions refresh、orders/trades、performance、risk、auto trading、ledger repair、trade tags、order create。
6. `strategy-tracking`：snapshot/items/detail/review/holding/drift/report/promotion/review workspace/trade journal/relative strength。
7. `backtest`：runs/detail/equity/trades/create/cancel/validation/optimization/compare/ETF T0。
8. `data-console`：SLA、gate、source health、coverage、tasks、workers、repair、inspector、ETF universe。
9. `settings`：settings workspace、save sections、factor weights、sector exclusions、strategy governance、feature flags、audit、operation audit、latest data refresh、quant parameters。

规则：

1. 优先复用现有后端契约。
2. 缺安全写 API 时标记为 backend-contract-needed，不在前端伪造成功。
3. Query stale time 按页面热度配置，禁止所有页面同一默认值。
4. mutation 成功后必须精准 invalidate，不全量刷新无关页面。

### 10.3 `/next/monitor`

必须实现：

1. `MonitorConclusionBar` parity。
2. 生产优先榜按后端顺序展示，不前端重排。
3. Strategy lane tabs/status。
4. Risk filter badges、MarketStateGate compact、FamilyStrip。
5. 持仓/自选 VirtualCardList。
6. 持仓录入/编辑 drawer。
7. 观察池 add/edit/delete。
8. 卡片详情、进入分析、移除、选择股票。
9. 关键位 panel 与 VolumePositionTagStrip。
10. AI 榜单解读弹窗。

验收：

1. 与旧 `priority_board` 顺序 hash 一致。
2. 添加/编辑/删除自选可在 shadow 和 live-smoke 模式下验证。
3. 不新增重复 SSE。

### 10.4 `/next/monitor/market`

必须实现：

1. MarketStateGate full。
2. MarketBreadthStrip。
3. HourlyAllMarketPulse。
4. Market key levels。
5. SectorLeaderGatePanel。
6. ETF T0 与 paired hedge context。
7. MonitorReviewPanel。
8. runtime、instrument sync、data quality。

验收：

1. BFF view=market 数据与旧页字段一致。
2. 图表只在可见时初始化，切页释放资源。

### 10.5 `/next/analysis`

必须实现：

1. 单票分析输入：代码、底仓、可卖、成本、偏好策略。
2. `开始分析` 调用 `/analyze`。
3. 同时拉取 intraday anomaly 和 stock key levels。
4. 批量分析：2-8 个代码，调用 `/analyze/batch`。
5. 批量排序走 Worker，fallback 同步排序。
6. 决策摘要、执行计划、失效条件、风险、成本提示、AI 补充。
7. K 线使用 Lightweight Charts，低频指标可用 ECharts adapter。
8. 从分析结果打开模拟下单。

验收：

1. 空代码、非法仓位、API 错误都有明确状态。
2. 批量排序结果与旧 worker 输出一致。
3. K 线组件不因输入变更重建整页。

### 10.6 `/next/playbook`

必须实现：

1. 策略 meta 加载，生产/观察策略 tabs 与旧前端一致。
2. 调用 low-buy candidates。
3. 候选按 buy_now、observe_confirmed、near_entry、watch/avoid 分层。
4. 最近表现、样本、胜率、收益、尾部风险、市场归因。
5. 今日主看、主线轮动、热点板块。
6. 候选卡片支持详情、分析、选择。
7. 交易时段报价刷新，刷新只更新叶子字段。

验收：

1. research-only 策略不进入生产榜。
2. `near_entry` 只 watch-only 展示。
3. 实时报价刷新不触发整页重渲染。

### 10.7 `/next/paper`

必须实现：

1. 账户结论、持仓嵌入表、机甲 HUD。
2. 委托弹窗：
   - 生产买入信号导入。
   - 标的搜索。
   - 买入/卖出。
   - 数量快捷：全部、半仓、1/4 仓。
   - 限价/市价、价格、策略、理由。
   - 手续费/金额预估。
3. 暂停/恢复模拟盘。
4. 持仓、委托、成交、个股 PnL、绩效、策略/市场/标签表现。
5. 风险事件、自动交易状态、自动交易 runs。
6. 交易标签新增/删除。
7. 对账 dry-run/apply，仅 admin 可见。
8. 持仓纪律、T 归因、ETF T0 表现。

验收：

1. 默认写入 flag 关闭时不发后端写请求。
2. live-smoke 模式能创建并回滚测试订单。
3. 无 `can_paper_trade` 时不可进入委托表单。
4. 机甲与日志只影响 display/review。

### 10.8 `/next/strategy-tracking`

必须实现：

1. 列表 snapshot/items、分页、排序。
2. 筛选抽屉：range、strategy、variant、family、signal、status、data quality、hit entry、stopped、user status、board filter。
3. 视图模式切换。
4. 详情抽屉。
5. 表现表。
6. 持有分析。
7. 战绩漂移。
8. 复盘诊断、weekly report、promotion review。
9. 复盘中心：队列、详情、提醒、绩效状态、summary。
10. 交易日志 create/update/delete。
11. relative strength board。

验收：

1. 筛选参数与旧前端 query params 一致。
2. 复盘日志写入需要安全 API；缺 API 时仍 shadow-only 并显示真实状态。
3. 策略跟踪表虚拟化，分页状态可回退。

### 10.9 `/next/backtest`

必须实现：

1. 回测提交表单：策略、时间、资金、参数、模式。
2. run list、状态图例、刷新。
3. run detail、metrics、attribution。
4. equity curve、monthly heatmap、return distribution。
5. trades table。
6. cancel run。
7. ETF T0、OOS、validation、optimization、compare、ML capacity。
8. 研究闭环 tabs。

验收：

1. 提交、取消、详情、图表均有 E2E。
2. 长序列图表 downsample 后口径一致。
3. 任务状态不能假成功。

### 10.10 `/next/data`

必须实现：

1. admin guard。
2. 今日数据状态、交易数据门禁、runtime fallback。
3. 数据源健康、覆盖率、覆盖率明细。
4. Worker observability：summary、workers、failures、artifacts、analytics reports。
5. 管理令牌。
6. 数据更新任务：sync instruments、refresh close data、backfill、refresh tasks。
7. 数据修复：dry-run、confirm apply、cancel。
8. 个股数据检查。
9. ETF/股票池维护入口。

验收：

1. 非 admin 只能看到权限提示。
2. 危险操作必须二次确认。
3. repair apply 必须有 dry-run 前置或明确确认。

### 10.11 `/next/settings`

必须实现：

1. 账户与安全：MFA、权限、个人偏好。
2. 风控参数保存。
3. 行业排除保存。
4. 模型与因子：LLM、factor weights、ML 参数。
5. 数据与运行：数据源配置、runtime diagnostics、latest data refresh。
6. 量化参数：模拟盘退出、行业 ETF T0、ML。
7. 策略治理：active/watch/paused。
8. feature flags、feature flag audit。
9. operation audit。
10. admin token gate。

验收：

1. 非 admin tabs 不出现 admin 操作。
2. 保存前有字段校验，保存后回显真实后端状态。
3. feature flag 更新支持默认 shadow、live-smoke 回滚。

## 11. 性能设计

预算：

1. entry gzip 保持小于旧前端首屏主包；ECharts 必须 lazy chunk。
2. P0 页面业务 chunk gzip 目标小于 80KB，超过需说明。
3. 长列表超过 80 项必须虚拟化。
4. 表格超过 100 行必须支持虚拟滚动或分页。
5. 图表超过 1000 点必须 downsample。
6. 一次行情 tick 只能更新相关 leaf cell。
7. 页面切换不保留不可见图表实例。
8. 同一路由不得创建重复 SSE。
9. Worker 往返超过同步路径时，小数据自动使用 sync fallback。

观测：

1. 保留 `npm run perf:compare`。
2. 扩展 request trace，记录 API count、unique endpoint、EventSource count。
3. 为 Worker 增加 transform timing。
4. 为图表增加 init/update/dispose timing。

## 12. 可扩展性设计

1. 每个 feature 定义自己的 query/mutation/model/component，不把所有逻辑放进 `shared`。
2. `shared/ui` 只放纯 UI wrapper，不放股票策略规则。
3. 页面级 screen model 与后端 response 分离：后端字段通过 model adapter 转为展示结构，但原始生产字段不得被改写。
4. 新策略、新图表、新数据任务通过 registry 或 config 扩展，不在页面写死分支。
5. 写入操作统一走 mutation adapter，后续切 live 不改页面。
6. 所有危险操作统一 ConfirmAction，避免每页重新写确认流。
7. 功能迁移时优先做深模块，不复制旧前端大页面结构；旧实现中影响易用性、可用性或稳定性的问题应在新前端一次性修正。

## 13. 测试策略

单元测试：

1. API operation path、method、query、body。
2. model adapter：缺字段、空数据、partial error、权限关闭。
3. Worker output 与 sync fallback 一致。
4. form validators。
5. production board order guard。

组件测试：

1. DataTable/VirtualCardList 空态、错误态、长列表。
2. Modal/Drawer focus 与关闭。
3. Command Palette 搜索和执行。
4. KlineChart mount/update/dispose。
5. motion reduced 模式。

E2E：

1. auth login/restore/logout。
2. 每个核心页面加载态、空态、错误态。
3. monitor 自选增删改 shadow/live-smoke。
4. analysis 单票/批量/模拟下单联动。
5. playbook 策略切换和候选分析。
6. paper 委托、暂停恢复、标签、对账权限。
7. strategy tracking 筛选、详情、复盘中心、日志。
8. backtest 提交/取消/详情。
9. data admin guard、任务、repair confirm。
10. settings 保存、feature flag、MFA。

回归命令：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
npm run e2e
npm run perf:compare
npm run screenshot:parity
```

旧前端仍需保持：

```bash
cd /Users/j/Documents/gupiao/frontend
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
```

## 13.1 可执行追踪矩阵

后续开发必须维护一张可执行追踪矩阵，不能只按页面口头判断完成度。矩阵建议落在 `docs/frontend-next/traceability-matrix-2026-06-06.md`，每个旧前端能力至少记录：

| 字段 | 要求 |
|---|---|
| 旧入口 | 旧 `frontend/` 路由、组件或交互入口 |
| 新入口 | `/next/*` 路由、组件、弹窗、抽屉或快捷命令 |
| 用户能力 | 用户最终要完成的业务动作 |
| API operation | `shared/api/operations` 或 feature query/mutation 名称 |
| 权限 | anonymous、authenticated、`can_paper_trade`、admin、live-smoke operator |
| 数据口径 | exact、tolerance、format-only 或 shadow-only |
| UI 证据 | style spec、样式图、截图 parity 路径 |
| 测试证据 | unit、component、E2E、request trace、shadow sample |
| 状态 | missing、in-progress、shadow-ready、parity-ready、blocked |

完成定义：

1. P0/P1 能力必须有矩阵行。
2. 没有 API 或安全写契约的能力必须标为 `blocked` 或 `shadow-only`，不能标为完成。
3. 每个优化项必须能反查到旧实现问题和新验收证据。
4. cutover 评审时矩阵中不得存在 P0/P1 `missing`、`in-progress` 或未解释的 `blocked`。

## 13.2 角色与权限矩阵

新前端必须显式维护 RBAC/能力矩阵，页面隐藏不是权限控制的唯一依据。

| 角色/模式 | 可见范围 | 可写范围 | 禁止 |
|---|---|---|---|
| anonymous | 登录页、公开错误页 | 无 | 访问 `/next/*` 业务页 |
| authenticated observer | monitor、market、analysis、playbook、strategy tracking 只读能力 | 自选/观察类 shadow 写入，按后端权限决定 | paper 委托、admin 数据修复、feature flag 写入 |
| `can_paper_trade` | paper 页面、模拟盘 display/review | paper shadow 写入；live-smoke 需额外模式 | 真实交易、生产排序、admin 操作 |
| admin | data、settings admin tabs、审计、数据任务 | data/settings 安全写入；默认 shadow | 未确认危险操作、绕过 dry-run |
| live-smoke operator | 隔离账号或隔离标记下的 live-smoke | 可回滚测试写入 | 影响真实生产数据 |

页面规则：

1. `/next/data` 与 settings admin tabs 必须有 admin guard。
2. `/next/paper` 委托表单必须同时检查登录态、`can_paper_trade` 和写入模式。
3. feature flag、数据修复、对账 apply、任务提交、回测取消等危险操作必须经过 `ConfirmAction`。
4. 所有 403 都要展示权限原因和可用替代路径，不能白屏或静默隐藏失败。

## 13.3 数据 Parity 口径

数据 parity 必须字段级定义，禁止只看页面截图。

| 类型 | 判定规则 |
|---|---|
| exact | 字段值、排序、数量、状态码完全一致；用于 `priority_board`、`production_score`、策略状态、权限状态 |
| tolerance | 数值允许约定误差；必须写明精度，例如收益率、PnL、图表 downsample 后曲线端点 |
| format-only | 展示格式可不同，但原始字段必须一致，例如时间格式、百分比显示、颜色标签 |
| shadow-only | 没有安全写 API 或未授权 live；只验证请求未发出或 shadow 记录正确 |

统一规则：

1. 交易日、时区、非交易日、停牌、空值和缺数据必须有固定显示规则。
2. 百分比、金额、股数、价格、评分、收益率必须定义小数位和舍入方式。
3. 分页、虚拟滚动和前端筛选不能改变后端生产排序。
4. 旧新对比必须保留 payload hash、排序 hash、request trace 和截图路径。
5. `priority_board`、`production_score`、`near_entry`、research-only 策略必须有独立 guard 测试。

## 13.4 写入状态机

所有 mutation 必须通过统一状态机，不允许页面各自临时处理。

```text
idle
  -> validating
  -> confirming
  -> submitting
  -> success
  -> failed
  -> rollback_needed
  -> rollback_submitting
  -> rollback_success | rollback_failed
```

状态要求：

1. `validating` 期间展示字段错误，禁止提交。
2. `confirming` 使用统一 `ConfirmAction`，危险操作必须展示影响范围。
3. `submitting` 期间禁用重复提交，并带幂等键或前端提交锁。
4. `success` 必须精准 invalidate 相关 query，不能全局刷新。
5. `failed` 必须保留用户输入，并显示可重试或取消路径。
6. `rollback_needed` 只用于 live-smoke 或明确可补偿操作。
7. 缺后端安全写 API 时只能停在 `shadow_recorded` 或 `blocked_contract_needed`，不能伪造成功。

## 13.5 异常与恢复矩阵

| 异常 | 展示 | 恢复 |
|---|---|---|
| 401 | 会话过期提示 | 尝试 refresh；失败回登录 |
| 403 | 权限不足说明 | 显示只读替代路径或申请权限说明 |
| 404 | 数据不存在或路由不存在 | 返回列表/工作台 |
| 409 | 数据版本冲突 | 重新拉取并提示用户确认 |
| 422 | 字段校验错误 | 聚焦首个错误字段 |
| 429 | 请求过快 | backoff 倒计时，禁止继续刷请求 |
| 5xx | 服务异常 | 保留旧缓存，显示重试 |
| 网络断开 | 离线/断连 banner | 自动重连，恢复后刷新热数据 |
| SSE 断连 | 连接状态降级 | 指数退避重连，避免重复 EventSource |
| Worker crash | 显示 fallback 标记 | 切 sync fallback 并记录 telemetry |
| 图表异常 | 图表区错误态 | 销毁实例，允许重试 |
| OpenAPI schema mismatch | contract error | 阻断 api:check 或标记 blocked |

## 13.6 响应式、可访问性、安全与可观测性

响应式最低要求：

1. `1440x900`、`1280x800`、`768x1024`、`390x844` 四档截图验收。
2. 移动端使用导航抽屉，核心操作不被表格横向滚动遮挡。
3. 大表移动端优先降级为卡片或横向滚动表，关键字段不可被隐藏。
4. 图表必须有最小高度、最大点数和可读空态。

可访问性最低要求：

1. 弹窗和抽屉支持 focus trap、Esc 关闭和焦点回到触发按钮。
2. Command Palette、表单、分页、tab、确认弹窗支持键盘操作。
3. 红绿涨跌必须同时有文字、符号或状态标签，不能只靠颜色。
4. 所有图标按钮必须有 `aria-label` 或 wrapper tooltip。

安全要求：

1. access token 存储、刷新和过期处理必须集中在 auth adapter。
2. admin token 和敏感参数不得写入持久化 localStorage。
3. 日志、telemetry、错误提示必须脱敏 token、手机号、账号、密钥。
4. 后端错误信息不能原样展示敏感堆栈。
5. 所有写操作必须校验当前模式：shadow、isolated-live-smoke 或 live。

可观测性要求：

1. 记录 route load timing、query error、mutation lifecycle、request count、EventSource count。
2. 记录 SSE reconnect 次数、Worker fallback 次数、chart init/update/dispose 耗时。
3. `perf:compare` 必须输出 request/SSE/chunk/long task/DOM nodes 对比。
4. 关键页面保留 shadow sample 与 replay 脚本，避免只在 mock 数据下验收。

运行时资源预算：

| 资源 | 预算 |
|---|---|
| 同一路由 EventSource | 0 或 1，禁止重复 |
| 单页首屏并发请求 | P0 页面目标不超过旧前端同页请求数 |
| Worker transform | 小数据慢于 sync 时自动 fallback |
| 图表点数 | 超过 1000 点 downsample |
| long task | 核心交互不得新增明显长任务回归 |
| 资源释放 | 路由离开后 SSE、Worker、chart、timer、listener 必须释放 |

## 14. 验收 Gate

功能 gate：

1. 9 个页面所有 P0/P1 缺失能力完成。
2. 兼容跳转完成。
3. auth/paper/admin guard 完成。
4. 所有旧前端核心用户路径有新前端 E2E。
5. 所有“旧实现优化”都有登记、验收证据、稳定性说明和业务口径不变证明。

数据 gate：

1. API parity endpoint 全部 200。
2. 关键字段 shape 与旧前端一致。
3. `priority_board` 顺序一致。
4. `production_score` 只展示后端字段。
5. request/SSE count 不回归。

视觉 gate：

1. 每页 style spec 与 style image 更新。
2. screenshot parity 通过。
3. 人工 visual signoff 通过。
4. 新增动效不破坏旧前端密度和文案语气。

性能 gate：

1. P0 页面加载不慢于旧前端。
2. long task、DOM nodes、request count 无明显回归。
3. ECharts lazy、Kline dispose、Worker fallback 有证据。

上线前 gate：

1. 两个真实交易日 shadow run 通过。
2. write rollback smoke 通过。
3. cutover runbook 更新。
4. 用户明确授权 cutover。

## 15. 分阶段实施计划

### Phase 0：需求冻结与样式核准

1. 本需求文档作为实施基线。
2. 更新 feature parity matrix。
3. 按新功能范围补 style spec 和截图参考。
4. 建立 P0/P1 功能清单 checklist。
5. 建立旧实现优化登记表，字段为：旧问题、优化方案、易用性收益、可用性收益、稳定性收益、保持不变口径、验收证据。

### Phase 1：基础架构补齐

1. Auth feature。
2. Workspace shell。
3. Command Palette。
4. UI wrapper：Modal、Drawer、Form、Toast、ConfirmAction、DataTable、VirtualCardList。
5. API operation adapters。

### Phase 2：分析与选股

1. `/next/analysis` 全功能。
2. `/next/playbook` 全功能。
3. analysis/playbook E2E 与 screenshot parity。

### Phase 3：监控与模拟盘

1. `/next/monitor` 全功能。
2. `/next/monitor/market` 全功能。
3. `/next/paper` 全功能。
4. no-write、live-smoke、机甲 display/review 验收。

### Phase 4：策略跟踪

1. 筛选、详情、tabs。
2. 复盘中心和日志。
3. 缺安全写 API 的部分形成 backend contract request，保持 shadow-only。

### Phase 5：回测、数据、设置

1. `/next/backtest` 研究闭环。
2. `/next/data` admin 运维闭环。
3. `/next/settings` 配置闭环。

### Phase 6：Shadow 验收与 cutover 准备

1. 补完整功能级 E2E。
2. 两交易日 shadow。
3. 数据/API/截图/性能 parity。
4. 更新 acceptance、open items、cutover runbook。
5. 等用户明确授权 cutover。

## 16. 后端契约需求候选

默认不改后端。若实现中发现以下能力缺少安全写 API，应单独形成后端契约任务：

1. strategy review 真实写入、更新、删除和回滚。
2. data job submit 的可回滚测试路径。
3. feature flag live-smoke 的隔离账号与审计标记。
4. paper order live-smoke 的隔离账户 reset API。
5. backtest create/delete 的测试 run 标记。

所有后端契约变更必须先更新 OpenAPI，再生成 `frontend-next/src/generated/api-types.ts`。

## 17. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 页面一次性补太大，形成新单体 | 按 feature 拆 query/model/component，每阶段必须过行数检查 |
| 为追求性能改变生产排序 | 增加 production board order guard，Worker 禁止处理生产排序 |
| 动效干扰交易判断 | 动效只表达状态，使用 reduced motion，禁止信号语义动画 |
| 写入切换不安全 | 默认 shadow，live-smoke 隔离数据，真实 live 需要单独授权 |
| API wrapper 漂移 | OpenAPI 生成类型 + operation tests |
| 截图像但功能空 | 功能级 E2E 和数据 parity 必须作为 cutover gate |
| ECharts 包体拖累首屏 | 低频图表 lazy import，K 线走 Lightweight Charts |
| 以优化为名改变业务行为 | 优化登记表 + 用户行为 E2E + 数据口径 parity |
| 机械复刻旧前端不合理结构 | 阶段评审检查 query/model/component 拆分、请求数和可用性证据 |
| 新前端功能变多后运行不稳 | error boundary、请求取消、资源释放、重复提交防护、降级态和稳定性 E2E |

## 18. 交付物

每个阶段至少交付：

1. 代码：仅 `frontend-next/` 和必要文档；后端改动需单独说明。
2. 测试：单测、组件测试、E2E。
3. 样式：style spec、截图 parity。
4. 报告：更新 acceptance、open items、parity matrix。
5. 证据：命令输出摘要、性能/request/SSE 对比、未完成项。
6. 优化登记：旧实现问题、优化方案、易用性/可用性/稳定性收益、口径不变证明。

## 19. Cutover 判断

本需求完成前不允许 cutover。

允许进入 cutover 评审的最低条件：

1. 本文 P0/P1 功能全部完成。
2. 新旧功能 parity matrix 无 P0/P1 缺口。
3. 两交易日 shadow run 通过。
4. API/request/SSE/screenshot/performance parity 通过。
5. write rollback smoke 通过。
6. 旧 `frontend/` 全命令仍通过。
7. 用户明确授权切流。
