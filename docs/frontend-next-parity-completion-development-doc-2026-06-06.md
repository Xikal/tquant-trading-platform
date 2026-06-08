# Frontend Next Parity Completion Development Doc - 2026-06-06

状态：可直接执行的开发文档，未部署，未切流
依据：

1. `docs/reports/frontend-next-gap-audit-2026-06-06.md`
2. `docs/frontend-next-parity-completion-requirements-2026-06-06.md`
3. `docs/frontend-next-feature-parity-matrix-2026-06-05.md`
4. `docs/frontend-next-architecture-design-2026-06-05.md`
5. `docs/frontend-next/style-specs/*.md`

## 1. 目标

在不改旧 `frontend/` 生产代码、不部署、不切流、不改生产策略语义的前提下，把 `frontend-next/` 从 shadow shell 补齐到可进入 cutover 评审的完整新前端。

完成后必须达到：

1. `/next/*` 覆盖旧前端 P0/P1 用户能力。
2. 新前端使用 SolidJS + TypeScript + Vite + TanStack Router/Query/Table/Virtual。
3. API 类型来自 `docs/contracts/openapi.json` 生成产物。
4. UI 通过 `frontend-next/src/shared/ui` wrapper 实现，不直接暴露第三方默认样式。
5. Worker 只做显示层纯计算，不参与生产策略判断。
6. 机甲头像和特效只用于 `/next/paper` display/review。
7. 旧实现不合理处可优化，但只能提升易用性、可用性和稳定性，不能改变业务口径。

## 2. 硬边界

1. 不部署。
2. 不切流。
3. 不修改 `strategy_policy.py`。
4. 不改变生产排序、`production_score`、`priority_board`、策略语义。
5. 不修改旧 `frontend/` 生产代码；旧前端只作为对照和验证对象。
6. 后端代码默认不动；缺安全写 API 时形成契约需求，前端保持 shadow-only。
7. 不伪造写入成功。
8. 不以动效或机甲结果影响生产信号。
9. 每个页面开发前必须确认已有 style spec 和样式图。

## 3. 当前缺口结论

`frontend-next/` 当前不可 cutover。阻断项：

1. 认证、权限、MFA、用户菜单、Command Palette、移动导航未完整复刻。
2. `/next/analysis` 与 `/next/playbook` 仍缺真实 API 与核心交互。
3. `/next/paper` 缺完整委托、暂停恢复、绩效、风险、标签、对账闭环。
4. `/next/strategy-tracking` 缺筛选、详情、复盘中心、交易日志。
5. `/next/backtest`、`/next/data`、`/next/settings` 缺研究、运维、配置闭环。
6. 缺字段级数据 parity、权限矩阵、异常矩阵、写入状态机和可执行追踪矩阵。

## 4. 交付目录

主要改动目录：

```text
frontend-next/
  src/
    app/
    generated/
    shared/
      api/
      ui/
      form/
      realtime/
      workers/
      charts/
      telemetry/
    features/
      auth/
      trading-workspace/
      monitor-action/
      monitor-market/
      analysis/
      playbook/
      paper/
      strategy-tracking/
      backtest/
      data-console/
      settings/
  tests/
    unit/
    component/
    e2e/
    parity/
docs/
  frontend-next/
    traceability-matrix-2026-06-06.md
    optimization-registry-2026-06-06.md
    permissions-matrix-2026-06-06.md
  reports/
    frontend-next-acceptance-2026-06-05.md
    frontend-next-open-items-2026-06-05.md
```

禁止新增旧前端生产代码改动；如旧 `frontend/` 测试文件已有脏改，保持不回退、不覆盖。

## 5. 基础架构任务

### 5.1 Auth 与权限

新增或完善：

1. `features/auth/LoginPage.tsx`
2. `features/auth/authQueries.ts`
3. `features/auth/authModel.ts`
4. `shared/api/auth.ts`
5. `app/guards.ts`
6. `features/trading-workspace/UserMenu.tsx`

能力：

1. login/register/refresh/logout/me/TOTP。
2. session restore。
3. `/next/*` route guard。
4. paper/admin/live-smoke guard。
5. 401 refresh，失败回登录。
6. 403 权限提示和只读替代路径。

验收：

1. 登录刷新页面不丢失用户。
2. 401 能 refresh 或回登录。
3. 非 admin 访问 `/next/data` 显示权限提示。
4. 无 `can_paper_trade` 不能打开委托表单。

### 5.2 工作台与导航

完善：

1. `AppShell.tsx`
2. `routeTree.tsx`
3. `keyboardShortcuts.ts`
4. `shared/ui/CommandPalette.tsx`
5. 移动端导航抽屉。

能力：

1. `Cmd/Ctrl+K` 打开命令面板。
2. 支持页面跳转、策略跳转、6 位股票代码进入分析。
3. `Cmd/Ctrl+1~8` 切换核心页面。
4. `/next/emotion`、`/next/low-buy`、`/next/strategy`、`/next/performance` 兼容跳转。

验收：

1. Command Palette E2E 覆盖三类命令。
2. 兼容跳转不丢 query。
3. 移动端 390x844 截图可用。

### 5.3 Shared UI Wrapper

必须通过 wrapper 使用：

1. `Button`
2. `DataTable`
3. `DataGrid`
4. `VirtualCardList`
5. `Modal`
6. `Drawer`
7. `ConfirmAction`
8. `Toast`
9. `FormField`
10. `StatusPill`
11. `Skeleton`
12. `Toolbar`
13. `Segmented`

规则：

1. 禁止页面内直接实现重复弹窗、确认框、表格。
2. 禁止直接使用第三方默认样式。
3. 所有图标按钮必须有 tooltip 或 `aria-label`。
4. Modal/Drawer 必须 focus trap、Esc 关闭、关闭后返回触发元素。

### 5.4 API、Query、Mutation

完善：

1. `shared/api/operations.ts`
2. `shared/api/queryKeys.ts`
3. `shared/api/client.ts`
4. `shared/api/mutations.ts`
5. feature-level `*Queries.ts`、`*Mutations.ts`。

规则：

1. 页面不拼 URL。
2. Query key 不写散落字符串。
3. Mutation 走统一状态机。
4. 缺安全写 API 标记 `blocked_contract_needed` 或 `shadow-only`。
5. stale time 按页面热度配置。
6. 成功后精准 invalidate。

验收：

1. `npm run api:check` 通过。
2. operation tests 覆盖 path、method、query、body。
3. request count 不超过旧前端同页。

## 6. 页面任务

### 6.1 `/next/analysis`

实现：

1. 单票分析输入：代码、底仓、可卖、成本、偏好策略。
2. `/analyze` 调用。
3. intraday anomaly 与 stock key levels。
4. 2-8 个代码批量分析。
5. Worker 排序和 sync fallback。
6. 决策摘要、执行计划、失效条件、风险、成本提示、AI 补充。
7. Lightweight Charts K 线。
8. 从分析结果打开模拟下单。

验收：

1. 非法代码、非法仓位、API 错误状态明确。
2. Worker 与 sync fallback 输出一致。
3. K 线输入变化不重建整页。
4. 截图 parity 通过。

### 6.2 `/next/playbook`

实现：

1. 策略 meta。
2. 生产/观察策略 tabs。
3. low-buy candidates。
4. buy_now、observe_confirmed、near_entry、watch/avoid 分层。
5. 绩效归因、样本、胜率、收益、尾部风险、市场归因。
6. 今日主看、主线轮动、热点板块。
7. 候选卡片详情、分析、选择。
8. 交易时段报价刷新只更新叶子字段。

验收：

1. research-only 不进入生产榜。
2. `near_entry` 只 watch-only。
3. 实时报价不触发整页重渲染。

### 6.3 `/next/paper`

实现：

1. 账户结论、持仓嵌入表、机甲 HUD。
2. 委托弹窗：推荐导入、搜索、买/卖、数量快捷、限价/市价、策略、理由、费用估算。
3. 暂停/恢复模拟盘。
4. 持仓、委托、成交、个股 PnL、绩效、风险、标签。
5. 自动交易状态和 runs。
6. 对账 dry-run/apply，admin only。
7. 持仓纪律、T 归因、ETF T0。

验收：

1. 默认写入 flag 关闭时不发真实写请求。
2. live-smoke 隔离订单可创建并回滚。
3. 无 `can_paper_trade` 不能进入委托。
4. 机甲只影响 display/review。

### 6.4 `/next/strategy-tracking`

实现：

1. snapshot/items、分页、排序、虚拟表格。
2. 筛选抽屉。
3. 视图模式切换。
4. 详情抽屉。
5. 表现、持有分析、漂移、诊断。
6. weekly report、promotion review。
7. 复盘中心、提醒、summary。
8. 交易日志 create/update/delete。
9. relative strength board。

验收：

1. 筛选参数与旧前端一致。
2. 缺安全写 API 时 shadow-only 并显示真实状态。
3. 分页状态可回退。

### 6.5 `/next/monitor` 与 `/next/monitor/market`

实现：

1. 生产优先榜服务端顺序展示。
2. strategy lane tabs。
3. risk filter badges。
4. 持仓/自选 VirtualCardList。
5. 持仓录入/编辑 drawer。
6. 观察池 add/edit/delete。
7. 关键位和量价标签。
8. AI 榜单解读。
9. market full gate、breadth、pulse、sector leader、ETF T0、review panel。
10. runtime、instrument sync、data quality。

验收：

1. `priority_board` 顺序 hash 一致。
2. 不新增重复 SSE。
3. 图表切页释放资源。

### 6.6 `/next/backtest`

实现：

1. 回测提交表单。
2. run list、状态图例、刷新。
3. run detail、metrics、attribution。
4. equity curve、monthly heatmap、return distribution。
5. trades table。
6. cancel run。
7. ETF T0、OOS、validation、optimization、compare、ML capacity。

验收：

1. 提交、取消、详情、图表 E2E。
2. downsample 后端点和关键指标一致。
3. 任务状态不能假成功。

### 6.7 `/next/data`

实现：

1. admin guard。
2. 今日数据状态、交易数据门禁。
3. 数据源健康、覆盖率、覆盖明细。
4. Worker observability。
5. 管理令牌。
6. 数据更新任务。
7. 数据修复 dry-run/apply/cancel。
8. 个股数据检查。
9. ETF/股票池维护入口。

验收：

1. 非 admin 只能看到权限提示。
2. 危险操作二次确认。
3. repair apply 有 dry-run 前置或明确确认。

### 6.8 `/next/settings`

实现：

1. 账户安全、MFA、权限、个人偏好。
2. 风控参数。
3. 行业排除。
4. LLM、factor weights、ML 参数。
5. 数据源配置、runtime diagnostics。
6. 量化参数。
7. 策略治理。
8. feature flags 和 audit。
9. operation audit。
10. admin token gate。

验收：

1. 非 admin tabs 不出现 admin 操作。
2. 保存前校验，保存后回显真实后端状态。
3. feature flag 支持 shadow、live-smoke 回滚。

## 7. 可执行矩阵与文档任务

必须新增或更新：

1. `docs/frontend-next/traceability-matrix-2026-06-06.md`
2. `docs/frontend-next/optimization-registry-2026-06-06.md`
3. `docs/frontend-next/permissions-matrix-2026-06-06.md`
4. `docs/frontend-next-feature-parity-matrix-2026-06-05.md`
5. `docs/reports/frontend-next-acceptance-2026-06-05.md`
6. `docs/reports/frontend-next-open-items-2026-06-05.md`

矩阵最低字段：

1. 旧入口。
2. 新入口。
3. 用户能力。
4. API operation。
5. 权限。
6. 数据 parity 口径。
7. UI 证据。
8. 测试证据。
9. 当前状态。

优化登记字段：

1. 旧实现问题。
2. 新前端优化方案。
3. 易用性收益。
4. 可用性收益。
5. 稳定性收益。
6. 保持不变口径。
7. 验收证据。

## 8. 异常、稳定性与安全任务

实现：

1. route-level error boundary。
2. API timeout 和取消过期请求。
3. 401 refresh 恢复。
4. 429 backoff。
5. SSE 指数退避重连，禁止重复 EventSource。
6. Worker crash 后 sync fallback。
7. 图表异常销毁和重试。
8. mutation 防重复提交。
9. 离线/断网 banner。
10. token、账号、密钥脱敏。

验收：

1. 异常矩阵 E2E 或 fixture 覆盖。
2. route failure 不拖垮 app shell。
3. 切路由后无残留 SSE、Worker、chart、timer、listener。
4. `perf:compare` 输出资源释放和请求/SSE 证据。

## 9. 响应式与可访问性任务

实现：

1. 1440x900、1280x800、768x1024、390x844 四档截图。
2. 移动端导航抽屉。
3. 大表移动端卡片或横向滚动降级。
4. Modal/Drawer focus trap。
5. Command Palette、tabs、分页、确认弹窗键盘可用。
6. 红绿涨跌有非颜色状态标识。
7. 图标按钮有 tooltip 或 `aria-label`。
8. `prefers-reduced-motion` 覆盖动效、机甲、图表动画。

## 10. 分阶段执行顺序

本任务允许多 Agent 并行开发，但必须遵守共享边界和串行合并门禁。默认由 `trading-platform-supervisor` 汇总状态、冲突和验收证据。

### 10.0 多 Agent 并行编排

| Agent | 主责 | 允许主要改动 | 需要协调 |
|---|---|---|---|
| A 架构/基础设施 | Auth、route guard、AppShell、Command Palette、error boundary、telemetry | `src/app/`、`src/features/auth/`、`src/shared/telemetry/` | 与 B 协调 `shared/api/auth.ts`；与 C 协调 shell 样式 |
| B 契约/API | OpenAPI generated types、operation adapters、query keys、mutation 状态机 | `src/generated/`、`src/shared/api/`、feature `*Queries.ts`、`*Mutations.ts` | 与所有页面 Agent 协调 operation 命名和 query key |
| C UI/样式系统 | shared/ui wrapper、表格、虚拟列表、表单、弹窗、响应式、a11y | `src/shared/ui/`、`src/shared/form/`、`src/shared/motion/`、style docs | 与所有页面 Agent 协调 wrapper API |
| D 实时/Worker/图表 | SSE、signals、Worker fallback、Lightweight Charts、ECharts adapter、资源释放 | `src/shared/realtime/`、`src/shared/workers/`、`src/shared/charts/` | 与 monitor、analysis、playbook、backtest 协调数据形态 |
| E 核心页面 | `/next/monitor`、`/next/monitor/market`、`/next/paper`、`/next/strategy-tracking` | 对应 `src/features/*` 页面和组件 | 与 B/C/D 协调 API、UI、实时能力 |
| F 次级页面 | `/next/analysis`、`/next/playbook`、`/next/backtest`、`/next/data`、`/next/settings` | 对应 `src/features/*` 页面和组件 | 与 B/C/D 协调 API、UI、图表能力 |
| G QA/验收 | parity matrix、traceability、E2E、截图、性能、acceptance/open items | `tests/`、`docs/frontend-next/`、`docs/reports/` | 等 A-F 提供证据后汇总 |

并行规则：

1. A、B、C、D 可以同时启动。
2. E、F 可以在 B 提供 operation 名称和 C 提供 wrapper API 后并行启动。
3. G 从第一天同步维护矩阵，但最终验收必须在 A-F 合并后执行。
4. 每个 Agent 每次提交前必须运行自己负责范围的最小测试，并更新自己的完成/阻塞项。
5. 修改共享文件前必须先查当前 diff，避免覆盖他人改动。

共享文件锁：

| 文件/目录 | 负责人 | 规则 |
|---|---|---|
| `src/shared/api/*` | B | 其他 Agent 只消费，不直接改；确需改先记录契约需求 |
| `src/shared/ui/*` | C | 页面 Agent 不复制 wrapper；缺能力提 wrapper 需求 |
| `src/shared/realtime/*`、`workers/*`、`charts/*` | D | 页面 Agent 只接 adapter |
| `src/app/routeTree.tsx` | A | 页面 Agent 新增路由需通过 A 合并 |
| `docs/frontend-next/*matrix*.md` | G | 其他 Agent 提供证据，G 统一落文档 |
| `docs/reports/frontend-next-acceptance-2026-06-05.md` | G | 阶段完成后统一更新 |

合并门禁：

1. B 的 `api:check`、operation tests 通过后，页面 Agent 才能标记 API ready。
2. C 的 wrapper component tests 通过后，页面 Agent 才能大规模接 UI。
3. D 的 Worker/chart disposal tests 通过后，图表和实时页才能进入 E2E。
4. 每个页面完成后必须同时提供功能 E2E、截图 parity、request trace。
5. 所有 Agent 合并后再运行全量新旧前端命令。

### Phase A：基础设施

1. Auth/guard/session restore。
2. AppShell/Command Palette/兼容跳转。
3. shared/ui wrapper。
4. API operations/queryKeys/mutation state machine。
5. telemetry、error boundary、request cancellation。

通过后运行：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
```

### Phase B：P0 业务页面

1. `/next/analysis`
2. `/next/playbook`
3. `/next/paper`
4. `/next/strategy-tracking`
5. `/next/monitor`

通过后运行：

```bash
cd /Users/j/Documents/gupiao/frontend-next
npm run build
npm run e2e
npm run screenshot:parity
```

### Phase C：P1/P2 页面

1. `/next/monitor/market`
2. `/next/backtest`
3. `/next/data`
4. `/next/settings`

通过后运行完整新前端命令。

### Phase D：Shadow 与验收

1. 数据/API parity。
2. request/SSE parity。
3. performance parity。
4. 两交易日 shadow。
5. write rollback smoke。
6. 更新 acceptance/open items/cutover runbook。

## 11. 全量验收命令

新前端：

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

旧前端：

```bash
cd /Users/j/Documents/gupiao/frontend
npm run api:check
npm run typecheck
npm run lint
npm test -- --run
npm run build
```

仓库：

```bash
cd /Users/j/Documents/gupiao
git diff --check
git status --short
```

## 12. 完成定义

允许进入 cutover 评审前必须同时满足：

1. P0/P1 页面功能完成。
2. 追踪矩阵无 P0/P1 missing。
3. 权限矩阵覆盖所有页面和危险操作。
4. 异常矩阵覆盖关键失败路径。
5. 数据 parity 通过。
6. 截图 parity 和人工视觉签收通过。
7. request/SSE count 不回归。
8. 性能不慢于旧前端，包体变化可解释。
9. write rollback smoke 通过。
10. 两交易日 shadow 通过。
11. 旧 `frontend/` 命令仍通过。
12. 用户明确授权 cutover。

## 13. 最终报告要求

更新 `docs/reports/frontend-next-acceptance-2026-06-05.md`，必须包含：

1. 初始和最终 git status。
2. 完成的阶段和页面。
3. 新旧功能 parity 矩阵摘要。
4. 每页样式图、截图 parity、响应式截图。
5. 数据/API parity 结果。
6. 权限、异常、写入状态机验收结果。
7. SSE/request 是否重复。
8. 性能对比。
9. 测试命令与结果。
10. 是否修改旧前端：目标为否。
11. 是否修改后端：目标为否；若有，列出契约原因。
12. 是否影响平台功能：明确回答“不影响”或说明风险。
13. 回滚方式。
14. 未完成项和需要用户确认项。
