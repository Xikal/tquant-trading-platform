# TQuant Phase 3 差距修复需求（终版）

**日期**: 2026-05-05
**版本**: v3.0 — 经 Codex 深度复核修正
**基线**: 当前项目 Phase 3 已实现约 80%，本文列出差距与修复要求，而非从零建设
**前置**: [Phase 3 实施方案](./TQuant-Phase3-实施方案-终版-2026-05-05.md)（纲领）→ [深度审查报告](./TQuant-Phase3-深度审查报告-2026-05-05.md)（审计）→ [Codex 复核反馈](#)（纠偏）→ 本文（可执行差距清单）

---

## 一、已实现基线确认

以下功能已在当前代码中实现，**不再作为 Phase 3 开发任务**：

| 已实现 | 位置 | 说明 |
|--------|------|------|
| `/api/strategies/meta` | `strategy_meta.py:14` | 策略元数据 API，种子+DB overlay |
| `/api/strategy/presets` | `strategy_meta.py:19` | 3 个系统预设场景 |
| `/api/symbols/search` | `strategy_meta.py:24` | 标的搜索，双源 fallback |
| `/api/strategy/signals/replay` | `strategy_meta.py` | 信号回放查询接口 |
| `WS /ws/strategy/{type}/{id}` | `strategy_stream.py:29` | 进度流端点 |
| `POST /api/strategy/stream-token` | `strategy_stream.py:23` | 流令牌签发 |
| `FormFields.tsx` 6 组件 | `components/shared/` | TextField/DateField/NumberField/SelectField/SliderField/SearchField |
| `Feedback.tsx` 5 组件 | `components/shared/` | EmptyPlaceholder/LoadingSpinner/SkeletonBlock/ErrorBanner/InlineValidation |
| `ToastContainer.tsx` | `components/shared/` | ToastProvider/useToast，支持 sticky，max 3，自动消失 |
| `/strategy` 页面（6 Tab） | `features/strategy/` | 快速回测/信号回放/参数优化/样本外验证/结果对比/历史 |
| 快速回测 Tab（完整） | `StrategyHubPage.tsx` | 多字段表单+预设场景+策略卡片+确认对话框+toast |
| 信号回放面板 | `StrategyHubPage.tsx` | 策略选择+关键词过滤+请求序列保护+结果表格 |
| 优化/验证/对比桥接 | `StrategyHubPage.tsx` | 复用 BacktestResearchPanel 聚焦模块 |
| Monitor 页迁移 | `MonitorPage.tsx` | SearchField+NumberField |
| Analysis 页迁移 | `AnalysisPage.tsx` | SearchField+SelectField 中文标签 |
| Command+K 命令面板 | `TradingWorkspace.tsx:140` | Cmd/Ctrl+K 打开 |
| Cmd/Ctrl+数字快捷键 | `TradingWorkspace.tsx:425-434` | 1=监控 2=分析 3=选股 4=策略 5=模拟 6=绩效 7=设置 |
| ECharts 净值曲线 | `LazyBacktestEquityChart.tsx` | dataZoom/tooltip/markPoint/回撤填充/双 Y 轴，通过 BacktestDashboard lazy import |
| 旧路由映射 | `workspaceConstants.ts:54-55` | /research→strategy, /backtests→strategy |
| 移动端基础适配 | `mobile/` | 策略 tabs、模拟盘面板、ActionSheet 组件 |

---

## 二、P0 — 阻断项（合并前必须修复）

### P0-1: 修复 `/backtests` 老路由跳转目标

**当前问题**: `workspaceRoutes.ts:17` 设置 `?tab=backtest`，但 `useStrategyHub.ts:185-193` 的 `initialTabFromLocation` 不识别 `"backtest"` 值，fallthrough 到 `"quick"` Tab。

**修复要求**:
1. `useStrategyHub.ts` 的 `initialTabFromLocation` 增加 `"backtest"` → `"history"` 的映射（历史 Tab 展示最近回测任务，最接近旧页面功能）
2. `workspaceRoutes.ts:17` 确认跳转目标与上述映射一致

**验收标准**:
- 浏览器访问 `/backtests` → URL 变为 `/strategy?tab=backtest` → 页面显示"历史"Tab（最近回测任务列表）
- 浏览器访问 `/research` → URL 变为 `/strategy?tab=replay` → 页面显示"信号回放"Tab
- 直接访问 `/strategy`（无参数）→ 默认显示"快速回测"Tab

---

### P0-2: 修复 `owner_user_id IS NULL` 数据隔离

**当前问题**: `strategy_stream.py:98-100` 的 `_user_can_view` 对 `owner is None` 返回 True，所有用户可查看无主任务。`backtest_optimization_service.py` 和 `backtest_validation_service.py` 的 `_visibility_filters` 对非 admin 用户使用 `owner_user_id == owner_user_id` 过滤——如果 owner_user_id 是 NULL，SQL 的 `NULL == NULL` 返回 NULL（假），这些任务对非 admin 不可见。但 `_get_visible_task` 的单任务查询和 WebSocket 的 `_user_can_view` 仍存在 NULL 放行问题。

**修复要求**:
1. **历史数据迁移**：编写 migration 脚本，将 `owner_user_id IS NULL` 的历史任务（`backtest_runs`、`backtest_optimizations`、`backtest_validations`）的 owner 设为系统管理员用户（`id=1`，如不存在则创建 `system` 用户，`username="system"`, `role="admin"`）。migration 需记录影响行数
2. **新增约束**（可选，非阻塞）：为新任务强制要求 `owner_user_id NOT NULL`
3. **兜底逻辑**：`_user_can_view` 改为 fail-closed——`owner is None` 时返回 False（拒绝访问）

**验收标准**:
- migration 执行后，`SELECT COUNT(*) FROM backtest_runs WHERE owner_user_id IS NULL` 返回 0
- 普通用户登录后，API 返回的任务列表不包含无主历史任务
- 系统管理员可查看所有任务（包括迁移后的历史任务）

---

### P0-3: 改造 WebSocket 进度流

**当前问题**: `strategy_stream.py:42-62` 是轮询循环——每 `interval_seconds` 新建 DB session 查询一次状态再 send_json。无 keepalive、无断线检测、无最终态立即返回。代码命名含 "stream" 但本质是 polling over WS。

**修复要求**（Phase 3 范围——不引入事件队列，做可靠性加固）:
1. **增加连接保活**：循环中增加 `try: await asyncio.wait_for(websocket.receive(), timeout=interval_seconds) except TimeoutError: pass` 以检测客户端断开，同时在无消息时发送 ping
2. **增加断线恢复**：前端 WebSocket 连接断开后，自动重连（exponential backoff: 1s, 2s, 4s, 8s, max 16s），最多重试 5 次。重连时重新获取 stream token
3. **最终态立即返回**：任务状态变为 `succeeded/failed/cancelled/deleted/timeout` 时，立即 send_json 最终消息并关闭连接（不再等待 interval_seconds）
4. **单一 DB session**：整个 WS 生命周期共用同一个 `SessionLocal()` 实例，而非每次轮询新建
5. **重命名或注释**：在代码注释中明确说明当前实现为 "polling-based progress stream over WebSocket"，避免未来维护者误以为是事件驱动

**验收标准**:
- WS 连接建立后，客户端断开（关闭浏览器 Tab），服务端在 `interval_seconds` 内检测到并释放资源
- 任务完成后，WS 在 1 秒内推送最终消息并关闭
- 前端 WS 断开后，5 秒内自动重连成功（若服务正常）
- 5 次重连均失败后，前端降级为 HTTP 轮询（3 秒间隔），不再尝试 WS
- 一次完整回测任务（约 2 分钟）的 WS 连接不超过 1 个 DB session

---

### P0-4: 权限边界明确化

**当前问题**: 优化和验证接口的权限检查使用 `_require_optimizer_access`（允许 admin/can_paper_trade/backtest_optimizer），比需求文档略宽松。对比接口无额外权限要求。普通用户能否查看公共回测结果未明确定义。

**修复要求**:
1. **明确权限矩阵**:

| 操作 | 普通用户 | 研究员（backtest_research） | 优化者（backtest_optimizer） | 管理员 |
|------|---------|---------------------------|---------------------------|--------|
| 创建回测 | ✅ | ✅ | ✅ | ✅ |
| 查看自己的回测 | ✅ | ✅ | ✅ | ✅ |
| 查看他人的回测 | ❌ | ❌ | ❌ | ✅ |
| 查看策略信号回放 | ✅ | ✅ | ✅ | ✅ |
| 创建参数优化 | ❌ | ❌ | ✅ | ✅ |
| 创建样本外验证 | ❌ | ✅ | ✅ | ✅ |
| 查看他人的优化/验证 | ❌ | ❌ | ❌ | ✅ |
| 查看策略元数据 | ✅ | ✅ | ✅ | ✅ |
| 策略治理（暂停/启用） | ❌ | ❌ | ❌ | ✅ |

2. **前端根据权限隐藏操作**: 普通用户看不到"参数优化"和"样本外验证"的提交按钮（Tab 仍可见但内容显示"需要研究员权限"提示）。管理员在 Settings 页可看到策略治理开关

**验收标准**:
- 普通用户：可创建/查看回测，可查看信号回放，优化/验证 Tab 显示权限提示而非表单
- 研究员：可创建回测/验证，可查看信号回放，优化 Tab 显示权限提示
- 管理员：全部操作可用
- API 层权限校验与前端一致（前端隐藏 + 后端拒绝）

---

## 三、P1 — 体验闭环（合并后 1 周内完成）

### P1-1: 策略工作台 5 个 Tab 状态流统一

**当前问题**: 优化/验证/对比 Tab 的桥接模式虽然功能可用，但存在状态不一致（独立的 BacktestPage hook 实例）、bridge 说明文字造成"未完成"印象、loading/empty/error 状态不全。

**修复要求**:

每个 Tab 必须覆盖以下 5 种状态：

| 状态 | 优化 Tab | 验证 Tab | 对比 Tab | 信号回放 Tab |
|------|---------|---------|---------|------------|
| **loading** | 骨架屏 | 骨架屏 | 骨架屏 | 骨架屏 |
| **empty** | "暂无优化任务，提交参数优化即可开始" + 跳转按钮 | "暂无验证任务" + 跳转按钮 | "至少选择 2 个已完成回测进行对比" | "未找到匹配信号，尝试调整筛选条件" |
| **error** | ErrorBanner + 重试 | ErrorBanner + 重试 | ErrorBanner + 重试 | ErrorBanner + 重试 |
| **permission_denied** | "需要优化者权限" | "需要研究员权限" | （所有人可见） | （所有人可见） |
| **success** | 优化结果表格+IS/OOS 对比 | 窗口卡片+稳定性结论 | 多选列表+对比表 | 信号表格+策略筛选 |

2. **去掉"桥接说明"文案**: 删除 `StrategyBridge` 组件中的"下方桥接现有完整回测闭环模块..."等说明文字。直接渲染功能内容
3. **共享 hook 上下文**: 优化/验证/对比 Tab 复用同一个 `useBacktestDashboard()` hook 实例（从 StrategyHubPage 层级传入），而非各自创建独立实例

**验收标准**:
- 优化/验证/对比 Tab 无"桥接""后续迁移"等占位文案
- 任一 Tab 的 5 种状态均可手动触发并正确展示
- 在优化 Tab 提交任务后，切换到验证 Tab 再切回优化 Tab，任务列表保持同步（共享 hook 上下文）
- toast 通知在任一 Tab 下均正常弹出

---

### P1-2: 信号回放增强

**当前问题**: 策略筛选和关键词过滤已有，但缺少 K 线周期选择、交易日窗口设置、空态解释和错误提示。

**修复要求**:
1. **增加交易日窗口选择器**: NumberField + "个交易日"后缀，默认 60。后端 `_recent_result_dates` 使用该值作为 `LIMIT`（取最近 N 个 scan snapshot 日期，而非自然日）
2. **增加回放粒度选择**: SelectField（"按信号"/"按交易日"），默认"按信号"。当前实现为"按信号"（每条信号一行）
3. **空态完善**: 当某策略在选定窗口内无信号时，显示 `EmptyPlaceholder`："该策略在最近 60 个交易日内无信号记录，可扩大窗口或切换策略"
4. **错误态强化**: API 调用失败时，显示 ErrorBanner 含重试按钮，不静默失败
5. **请求竞态保护**: 已有的 `requestSeqRef` 模式需确认覆盖所有 API 调用路径

**验收标准**:
- 用户可以调整交易日窗口（10/30/60/120 或自定义数字）
- 选择无信号的策略时，页面显示明确空态而非空白表格
- API 调用失败时，页面显示 ErrorBanner 含重试按钮
- 连续快速切换策略不会出现结果错乱（竞态保护生效）

---

### P1-3: symbol search 修复

**当前问题**: `total` 字段等于当前页数量而非全量匹配数；SQL LIKE 通配符 `%` 和 `_` 未转义；搜索失败静默吞错。

**修复要求**:
1. **修复 total 字段**: `search_symbols` 返回前先执行 COUNT 查询获取全量匹配数。COUNT 与主查询使用相同 WHERE 条件
2. **转义 LIKE 通配符**: 用户输入中的 `%`、`_`、`\` 在传入 SQL LIKE 前转义（`\%`、`\_`、`\\`）
3. **前端错误提示**: SearchField 的 `.catch` 分支设置 error state，在下拉区域显示"搜索失败，请重试"文字（而非静默关闭下拉）
4. **性能预算**: COUNT 查询 + 主查询总耗时 < 200ms（P95）

**验收标准**:
- 搜索 `"600"` 返回 ≤10 条结果，`total` 显示实际匹配总数（如 248）
- 前端根据 `total > items.length` 显示"还有 N 条结果，请细化搜索"
- 搜索 `"60%"` 时，`%` 被转义为字面字符，不匹配所有结果
- 断开网络后搜索，下拉区域显示"搜索失败，请重试"

---

### P1-4: useStrategyHub 初始化解耦

**当前问题**: `load()` 使用 `Promise.all` 并行请求 3 个接口，任一个失败则全部数据不显示。

**修复要求**:
1. 改用 `Promise.allSettled`
2. 对每个成功的接口，设置对应 state
3. 对每个失败的接口，保留已有 state 不变（首次加载则留空），并在 notice 中显示"部分数据加载失败"
4. 增加请求序列号：`load()` 调用时递增 seq，响应时检查 seq 匹配

**验收标准**:
- `/api/strategies/meta` 正常但 `/api/backtests` 超时时，策略列表正常显示，任务列表显示"加载失败"占位 + 重试按钮
- 快速双击"刷新"，两次请求不竞速（后发请求的结果不覆盖先发但后到的响应）

---

### P1-5: 前端硬编码风控参数迁移

**当前问题**: `useStrategyHub.ts:142-148` 中 `max_daily_loss_pct: 5`、`min_cash_reserve: 5000` 硬编码在前端，用户不可见不可改。`max_single_order_pct` 与 `max_position_pct` 语义不同却被设为相同值。

**修复要求**:
1. 将 `max_daily_loss_pct`、`min_cash_reserve` 加入预设场景的 `config` 字段（后端种子数据 `DEFAULT_PRESETS`）
2. 将 `max_single_order_pct` 从 `max_position_pct` 独立出来，默认设为 `max_position_pct` 的 50%（单笔下单不应占满全部仓位）
3. 高级参数折叠区增加 `max_daily_loss_pct` 和 `min_cash_reserve` 的可选输入（默认隐藏，随预设填充）
4. 前端 `submit` 中不再硬编码这些值——从 preset config 或 form state 读取

**验收标准**:
- 选择"快速体检"预设后，`max_daily_loss_pct=5`、`min_cash_reserve=5000` 自动填充（从后端 preset config 读取）
- 用户展开高级参数后，可手动修改这两个值
- 提交的 payload 中 `max_single_order_pct` ≠ `max_position_pct`（前者为后者的约 50%）

---

### P1-6: preset key 标准化

**当前问题**: 种子预设使用语义 key（`quick_check`/`annual_review`/`full_validation`），但 DB 预设的 `key` 用 `str(row.id)` 的数字字符串。前端如果用 key 做逻辑判断会混乱。

**修复要求**:
1. 给 `StrategyPreset` 模型增加 `preset_key` 列（`String(40), nullable=True, unique=True`），DB 预设可用此列存语义 key
2. 种子预设的 key 保持不变
3. 前端 `preset.key` 用于展示（不依赖其值做逻辑），`preset.id` 用于标识（DB 预设用 id，种子预设 id 为 null 时用 key）
4. `applyPreset` 函数不依赖 preset.key 做分支逻辑，仅读取 `preset.config` 字段

**验收标准**:
- 3 个系统预设的 key 为 `"quick_check"`/`"annual_review"`/`"full_validation"`
- 前端 applyPreset 对种子预设和 DB 预设行为一致
- DB migration 不影响已有数据

---

## 四、P1 — 逐页面补齐

### P1-7: Research 页术语中文化

**当前状态**: Monitor/Analysis 已迁移 FormFields，Research 页未迁移。

**修复要求**:
1. `lookback_bars` 字段 → 改为 NumberField + "天"后缀（标签"回看天数"），默认 60
2. `bar_period` 下拉 → 改为 SelectField，选项 `[{value:"1m", label:"1分钟"},{value:"5m", label:"5分钟"},{value:"15m", label:"15分钟"}]`
3. `initial_position` 字段 → 改为 NumberField + "股"后缀（标签"初始仓位"）
4. 所有标签去掉"样本窗口""底仓数量"等术语，使用上述中文标签

**验收标准**:
- Research 页无 `lookback_bars`/`bar_period`（key 仅存在于 API 调用中）
- 回看天数输入 60，API 调用中自动换算为对应的 bar 数
- 加载/空/错误状态使用 Feedback 组件

---

### P1-8: Paper Trading 委托两步式

**当前状态**: 桌面端委托弹窗仍含 11 个字段。

**修复要求**:
1. **第一步（默认可见，3 字段）**: SearchField（标的，自动填充当前分析页标的）+ 买/卖大按钮切换 + NumberField（数量，含"全部/半仓/1/4仓"快捷按钮）
2. **第二步（折叠，"更多设置"展开）**: 价格类型（限价/市价 SelectField）+ 委托价 NumberField + 策略归属 SelectField（中文标签，API 驱动）+ 备注 TextField
3. 去掉 `require_intraday_confirmation` 字段（默认开启，不暴露给用户）
4. SearchField 选择标的后自动填充最新价作为委托价参考

**验收标准**:
- 打开委托弹窗，默认仅显示 3 个字段
- 点击"更多设置"展开剩余字段
- 不显示 `require_intraday_confirmation` 相关 UI
- 从 Analysis 页点击"下单"跳转到模拟盘时，标的字段自动填充

---

### P1-9: Settings 页保存反馈

**修复要求**:
1. 所有 SettingCard 的保存按钮点击后，按钮短暂变绿（2 秒）+ 显示"已保存"文字（3 秒消失）
2. 必填字段增加 InlineValidation（API Key 非空、URL 格式校验、百分比 0-100 范围）
3. 顶部统一显示"有 N 项未保存的更改 [全部保存]"（当存在多个 card 的修改时）

**验收标准**:
- 修改 API Key 后点击保存，按钮变绿 2 秒，显示"已保存"
- 输入非法 URL（如 "not-a-url"）并失焦，字段下方显示红色错误提示
- 同时修改 3 个 SettingCard 后，顶部显示"有 3 项未保存的更改 [全部保存]"

---

## 五、P2 — 移动端与可访问性

### P2-1: 移动端策略工作台关键路径

**当前状态**: 移动端有策略 tabs 和模拟盘面板，但未对齐桌面端核心路径。

**修复要求**:
1. **策略检索**：移动端策略 tabs 改为从 `GET /api/strategies/meta` 拉取（替换硬编码 `MOBILE_STRATEGY_TABS`）
2. **回测结果摘要**：在移动端策略页增加"最近回测"卡片（复用桌面端 `/strategy` 的 `RecentRuns` 组件逻辑，移动端独立 UI）
3. **模拟盘下单**：右下角增加浮动"下单"按钮 → 弹出简化委托表单（标的搜索 + 买/卖 + 数量 + 限价/市价，4 字段）
4. **持仓搜索**：移动端持仓列表顶部增加 SearchField（搜索标的代码/名称）

**验收标准**:
- 移动端策略 Tab 列表与桌面端一致（从同一 API 拉取）
- 移动端可查看最近 5 条回测结果摘要
- 移动端可完成一笔模拟盘委托（从点击"下单"到提交成功）
- 移动端持仓支持按标的搜索过滤

---

### P2-2: 可访问性补齐

**修复要求**:
1. **ConfirmDialog**: 增加 focus trap（Tab 循环在 Cancel/Confirm 按钮之间）、ESC 关闭、打开时自动聚焦 Cancel 按钮
2. **ToastContainer**: 每个 toast 增加 `role="alert" aria-live="polite"`
3. **SkeletonBlock**: 增加 `role="status" aria-label="加载中"`
4. **ErrorBanner**: 重试按钮增加 `aria-label="重试加载"`
5. **SearchField**: 下拉搜索结果列表增加 `role="listbox"`，每个选项增加 `role="option"`
6. **ConfirmDialog**: `aria-labelledby` 的 id 使用 `useId()` 生成唯一值

**验收标准**:
- 使用屏幕阅读器（VoiceOver/NVDA）可正确朗读 toast 通知内容
- 键盘 Tab 不会穿透 ConfirmDialog 到达背景元素
- 按 ESC 可关闭 ConfirmDialog

---

## 六、数据迁移

### 6.1 历史 NULL owner 迁移

```sql
-- 1. 确保存在 system 用户
INSERT OR IGNORE INTO users (id, username, role, created_at)
VALUES (1, 'system', 'admin', datetime('now'));

-- 2. 迁移 NULL owner 任务
UPDATE backtest_runs
SET owner_user_id = 1
WHERE owner_user_id IS NULL;

UPDATE backtest_optimizations
SET owner_user_id = 1
WHERE owner_user_id IS NULL;

UPDATE backtest_validations
SET owner_user_id = 1
WHERE owner_user_id IS NULL;
```

迁移后需验证：上述 3 表的 `SELECT COUNT(*) WHERE owner_user_id IS NULL` 均返回 0。

### 6.2 preset_key 列增加

```sql
ALTER TABLE strategy_presets ADD COLUMN preset_key VARCHAR(40);
CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_presets_key ON strategy_presets(preset_key);
```

迁移后，3 个种子预设的 DB 行（如已存在）无需更新——种子预设由代码提供，不依赖 DB 行。

### 6.3 无需迁移的项

- `backtest_runs.optimization_id` 和 `validation_id`：Phase 2 审查中标记为需要独立列，但当前通过 `request_json` 关联已能满足查询需求，Phase 3 不做 schema 变更
- `strategy_presets.updated_at`：`market_entities.py` 未定义该列，但预设数据为只读系统配置，不需要更新时间追踪

---

## 七、性能预算

| 接口/操作 | 指标 | 预算 |
|----------|------|------|
| `GET /api/symbols/search` | P95 延迟 | < 200ms |
| `GET /api/strategies/meta` | P95 延迟 | < 50ms（缓存 60s） |
| `GET /api/strategy/signals/replay` | P95 延迟 | < 500ms |
| `POST /api/backtests/compare` | P95 延迟 | < 2s（≤5 组回测） |
| WS progress stream | 轮询间隔 | 3-5 秒，不支持 < 2 秒 |
| `/strategy` 页面首屏 | P95 加载时间 | < 2s（含 3 个 API 并行请求） |
| ECharts 图表渲染 | 首屏阻塞 | 否（lazy import） |

---

## 八、UX 完整路径验证

以下 5 条用户路径必须在修复后能走通：

**路径 1: 从零到回测结果**
1. 打开 `/strategy` → 看到"快速回测"Tab（默认）
2. 点击"快速体检"预设 → 看到表单自动填充
3. 点击"提交快速回测" → 看到确认对话框（含策略/区间/资金摘要）
4. 点击"确认提交" → toast "回测任务已提交" → 最近任务列表出现 running 任务
5. 等待任务完成 → toast "回测完成！总收益 +X%" → 可在历史 Tab 查看

**路径 2: 从回测结果到参数优化**
1. 在历史 Tab 看到一条完成的回测 → 点击该任务
2. 查看回测详情（收益/胜率/交易列表）
3. 点击"优化参数"按钮 → 切换到优化 Tab，自动填入该回测的策略和日期范围
4. 调整参数滑块 → 提交优化任务

**路径 3: 从优化到样本外验证**
1. 优化任务完成 → 查看最优参数和 IS/OOS 对比
2. 点击"样本外验证"按钮 → 切换到验证 Tab，自动填入最优参数
3. 提交验证任务 → 查看窗口卡片和稳定性结论

**路径 4: 从信号回放到下单**
1. 在信号回放 Tab，选择"首板回调"策略 → 看到信号列表
2. 点击某条信号的标的 → 跳转到 Analysis 页（携带标的代码）
3. 在 Analysis 页查看 K 线图和分析建议
4. 点击"模拟下单" → 跳转到模拟盘页，标的自动填充

**路径 5: 移动端从监控到下单**
1. 打开移动端 → 看到优先榜
2. 点击某标的 → 底部抽屉显示入场区+信号评分
3. 点击"下单"浮动按钮 → 弹出简化委托表单（标的已填充）
4. 选择买/卖 + 输入数量 → 提交 → toast "委托已提交"

---

## 九、不做清单（本次 Phase 3 不包含）

1. **不引入后端事件队列**（Redis/Kafka/RabbitMQ）——WebSocket 保持轮询模式，只做可靠性加固
2. **不新增用户自定义预设**——仅系统预设 3 个
3. **不增加 backtest result 分享/公开/私有状态**——所有结果仅创建者可见
4. **不完整实现移动端参数优化和验证**——移动端仅支持查看回测摘要和模拟盘下单
5. **不做 ECharts 热力图和直方图**——推迟到后续版本
6. **不删除旧页面路由**——`/backtests` 和 `/research` 保持 301 redirect
7. **不引入新 UI 框架**——保持零外部 UI 依赖
8. **不做暗色模式和国际化**——仅中文

---

## 十、验收汇总

| 类别 | 验收项数量 | 关键指标 |
|------|----------|---------|
| P0 阻断项 | 4 | 路由跳转正确、null owner 迁移完成、WS 保活+断线恢复、权限矩阵生效 |
| P1 体验闭环 | 9 | 5 Tab 状态流完整、信号回放含窗口选择、symbol search total 正确、初始化解耦、风控参数可配、preset key 标准化、Research 中文化、委托两步式、Settings 保存反馈 |
| P2 移动端与 a11y | 2 | 移动端下单+搜索持仓、ConfirmDialog focus trap + Toast aria |
| 数据迁移 | 2 | null owner 清零、preset_key 列添加 |
| 性能 | 6 | 接口 P95 延迟全部达标 |
| UX 路径 | 5 | 5 条端到端路径可走通 |

**全部修复完成后，Phase 3 完成度可达 95%+，达到"功能可用 + P0/P1 全部闭合"标准。**
