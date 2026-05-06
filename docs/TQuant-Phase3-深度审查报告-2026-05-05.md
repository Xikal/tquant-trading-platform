# TQuant Phase 3 深度审查报告（全面审计）

**日期**: 2026-05-05
**审查方法**: 逐文件深度审查 — 后端 6 文件 + 前端 11 文件，逻辑正确性、代码质量、UX 完成度、性能、可访问性五维扫描
**审查范围**: Phase 3 全部新增/改造文件，逐功能模块验证

---

## 一、总体评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 后端 API 功能 | A | 3 端点全部可用，搜索双源 fallback，策略种子+overlay 设计正确 |
| 后端 WebSocket | C | 端点可用但本质是 DB 轮询，非 push。缺 keepalive、连接管理 |
| 后端代码质量 | B+ | 结构清晰，但缺日志、token 消费语义有误导、分页 total 字段错误 |
| 前端共享组件 | A- | FormFields/Feedback/Toast 设计优秀，但 SearchField 静默吞错 |
| 前端 /strategy 页面 | B | 快速回测 Tab 完成度高，但 3 个 Tab 是占位、路由 redirect 有 bug |
| 前端逐页迁移 | C | Monitor/Analysis 完成，余 5 页（含移动端）动 |
| 前端代码质量 | B+ | 状态管理基本正确，缺少请求序列号、useToast 静默吞错 |
| 可访问性 | D | 多处缺 focus trap、aria role、screen reader 支持 |
| 性能 | B- | ECharts 进主包（名实不符）、WS 过多 DB 连接、Promise.all 失败全丢 |
| 测试覆盖 | 未查 | Phase 2 已有测试文件存在，Phase 3 新增测试未深度审计 |

**加权总分: C+ (约 68% 完成度，可行路径覆盖完整，细节目录约 40%)**

---

## 二、发现的所有问题（共 42 条）

### 2.1 Critical — 影响功能正确性或数据隔离

**#1 WebSocket 本质是轮询而非 push**

`strategy_stream.py:42-62`。`stream_strategy_task_progress` 每隔 `interval_seconds` 打开新 DB 会话查询一次任务状态，然后 send_json。这不是 push——engine/optimizer/validator 无任何主动通知机制。一个 5 分钟完成的任务，ws 仅轮询 DB 后转发。如果 `interval_seconds=3`，WS 产生约 100 次 DB 查询，99% 返回相同数据。

**#2 WebSocket 连接无 keepalive**

`strategy_stream.py:42-62`。循环中只有 `send_json`，无 `receive()`。客户端断开后，服务端最多等 `interval_seconds`（最大 30 秒）才发现。反向代理可能静默关闭空闲 WS 连接。

**#3 旧路由 `/backtests` → `/strategy?tab=backtest` 跳转 Bug**

前端 `useStrategyHub.ts:185-193`。`initialTabFromLocation` 不识别 `?tab=backtest`（只识别 `quick/signals/optimize/validate/compare/history`），fallthrough 到 `"quick"` Tab。从旧 `"/backtests"` 跳转过来的用户看到的是快速回测表单而非期望的视图。

**#4 Null owner_user_id 数据隔离 Bug**

`strategy_stream.py:98-100`。`_user_can_view` 中 `owner is None` 对所有用户放行。任何 `owner_user_id=NULL` 的任务对所有登录用户可见。

**#5 SymbolSearchResponse.total 字段永远等于 items.length**

`strategy_metadata_service.py:163`。`total=len(items)` 使前端无法判断是否还有更多结果。搜索 `"600"` 返回 10 条时 `total=10`，无论实际有 10 条还是 1000 条。

### 2.2 High — 用户可感知的功能缺陷

**#6 3 个 Tab（优化/验证/对比）是空桥接**

`StrategyHubPage.tsx:231-249`。`StrategyBridge` 组件只渲染"后续迁移"说明文字 + 旧 `BacktestPage`。用户点击"参数优化"Tab 看到的是旧版回测仪表盘的全量界面，不是滑块参数网格。点"结果对比"看到的是手动输入 run ID 的文本框，不是多选复选框。

**#7 信号复盘 Tab 仅有占位面板**

`StrategyHubPage.tsx` 中 `StrategySignalReplayPanel` 存在但仅显示筛选器和空表格，无 SearchField 标的搜索、无 K 线周期选择器、无自然日期换算。

**#8 LazyBacktestEquityChart 名实不符——非 lazy**

`LazyBacktestEquityChart.tsx` 被 `BacktestDashboard.tsx:29` 用 `React.lazy` 包装，但在新 /strategy 页面的 `StrategyBridge` 中 `BacktestPage` 是直接 import，因此这里反而是 lazy 的。不过该文件本身缺少 `React.lazy` 包装——依赖调用方决定是否 lazy。文件名暗示懒加载但实现不强制。

**#9 Promise.all 导致单 API 失败全盘崩溃**

`useStrategyHub.ts:69-73`。`load()` 用 `Promise.all` 并行请求 meta/presets/runs 三个端点。任一端点失败，所有数据都不显示。应改用 `Promise.allSettled` 部分成功部分展示。

**#10 策略列表三重硬编码**

`workspaceConstants.ts` 定义 `CORE_PLAYBOOK_TABS`/`AUXILIARY_PLAYBOOK_TABS`，`backtestDisplay.ts` 定义 `BACKTEST_STRATEGY_OPTIONS`，`strategy_metadata_service.py` 定义 `DEFAULT_STRATEGY_META` 种子数据。三份独立维护，增加策略或改名称需同步三处。

### 2.3 Medium — 代码或设计问题

**#11 SearchField 搜索 API 失败静默吞错**

`FormFields.tsx:135-139`。`.catch(() => setItems([]))` 无任何错误提示，用户搜索无结果时不知道是"无匹配"还是"网络错误"。

**#12 useToast 在 Provider 外调用静默失效**

`ToastContainer.tsx:54-60`。`useToast()` 在 `ToastContext` 缺失时返回空操作函数，无 warning。调试困难。

**#13 useStrategyHub.load() 无请求序列号**

`useStrategyHub.ts:65-87`。快速双击"刷新"按钮，两次 `load()` 调用竞速。后发先至的响应可能被先发后至的数据覆盖。

**#14 parsePositive 同一字段调用两次**

`useStrategyHub.ts:200-201,138-139`。`submit` 中先调用 `parsePositive(form.initial_capital)` 做验证（返回值丢弃），再调用 `parsePositive(form.initial_capital)` 构造 payload。每个数字字段计算两次。

**#15 硬编码 risk_limits**

`useStrategyHub.ts:142-148`。`max_daily_loss_pct: 5` 和 `min_cash_reserve: 5000` 无表单控件、无预设覆盖。

**#16 SSETokenService.consume 非一次性消费**

`sse_token_service.py:45-57`。方法名 "consume" 暗示一次性使用，但实现只是解码验证。同一 token 在 60 秒 TTL 内可无限次使用。

**#17 分页 broken — total=len(items)**

同 #5，此处为后端接口设计问题。

**#18 WebSocket 每次轮询新建 DB session**

`strategy_stream.py:69`。`_load_task_progress` 每次轮询 `with SessionLocal() as db`。5 分钟任务、3 秒间隔 = 100 个 DB 会话。

**#19 SQL LIKE 通配符未转义**

`strategy_metadata_service.py:183,203`。用户搜索 `_` 或 `%` 时，这些字符在 SQL LIKE 中作为通配符生效。搜索 `%` 会匹配任意股票。

**#20 DB preset key 丢失语义**

`strategy_metadata_service.py:249`。`key=str(row.id)` 使得 DB 中的预设使用数字字符串作 key（如 "1"），种子预设使用语义 key（如 "quick_check"）。前端如果用 key 做预设识别会失败。

**#21 种子数据 preset key 缺失**

`strategy_metadata_service.py:42-93`。`DEFAULT_PRESETS` 种子数据中预设带 `key` 字段，但 `_preset_from_seed` 用 `item["key"]` 取值，类型不佳。

**#22 全区日志缺失**

所有 6 个后端新文件均无 `logger` 实例。DB 查询失败时直接返回空列表，无任何服务端日志。生产环境排错困难。

**#23 SessionLocal() 绕过 FastAPI DI**

`strategy_stream.py:69`。WebSocket handler 直接用 `SessionLocal()` 不通过 FastAPI 的 `get_db` 依赖注入。切换数据库配置需单独修改此处。

**#24 无 clock skew 容差**

`sse_token_service.py:51-53`。token 过期判断 `expires_at < time.time()` 无宽限期。服务器时钟跳 1 秒，所有 token 立即失效。

**#25 `_json_dict` 异常范围过宽**

`strategy_meta.py:151-155`。`except Exception` 捕获 `MemoryError`、`KeyboardInterrupt` 等不应吞没的异常。

**#26 StrategyResearchFocus 创建独立 hook 实例**

`StrategyHubPage.tsx:389-397`。桥接模式下每个 Research 子面板创建一个新的 `useBacktestDashboard()` 实例，与主页面状态完全隔离。用户看不到之前提交的任务。

**#27 max_daily_loss_pct 硬编码 + max_single_order_pct 与 max_position_pct 重复**

`useStrategyHub.ts:142-147`。两者语义不同（日亏损上限 vs 单票最大仓位），却被设为相同值。

**#28 rangeStart 只认 "6m"/"12m"/"24m"**

`useStrategyHub.ts:225-229`。任何其他字符串如 "3m" 落默认 365 天。无容错 fallback。

**#29 initialTabFromLocation 缺少 backtest→history 映射**

`useStrategyHub.ts:185-193`。同 #3。

**#30 lookback_days 参数名误导**

`strategy_meta.py:96`。`_recent_result_dates` 的 `lookback_days` 参数被用作 SQL `LIMIT`，非日历天数筛选。

**#31 float("inf") 可穿透 NaN 过滤**

`strategy_meta.py:161-163`。`parsed == parsed` 对 inf 返回 True。若数据中出现 inf，JSON 序列化会出错。

### 2.4 Low — 体验或规范问题

**#32 ConfirmDialog 缺 focus trap**

`StrategyHubPage.tsx:413-427`。键盘 Tab 可穿透弹窗到达背后页面元素。

**#33 ConfirmDialog 打开时无自动聚焦**

弹窗打开后，焦点停留在触发按钮上，Cancel/Confirm 按钮未获焦。

**#34 Toast 无 screen reader 声明**

`ToastContainer.tsx:42-48`。缺少 `role="alert"` 或 `aria-live`。

**#35 SkeletonBlock 缺 role 属性**

`Feedback.tsx:19`。有 `aria-label` 但无 `role="status"`。

**#36 ConfirmDialog id 硬编码可能冲突**

`StrategyHubPage.tsx:415`。`id="strategy-confirm-title"` 是字符串字面量，如果页面有两个 ConfirmDialog 则 id 重复。

**#37 Backdrop 点击不关闭弹窗**

`StrategyHubPage.tsx:414`。角色 `presentation` 但无 `onClick` 关闭逻辑，用户期望点遮罩层关闭。

**#38 Toast 超时时未清理 useEffect**

`ToastContainer.tsx:32`。`setTimeout` 回调中调用 `removeToast`，组件卸载后仍会执行。React 18 可能警告。

**#39 formatPct 调用风格不一致**

`StrategyHubPage.tsx:187-189`。收益/胜率用可选链 `summary?.total_return_pct`，资产直接用 `run.final_equity` 无可选链。虽都安全但不一致。

**#40 StrategyPreset 表缺 updated_at 列**

`market_entities.py:57-65`。与其他实体（StrategyMetadata 等）不一致。

**#41 种子数据 preset 无 DB 持久化**

种子 `DEFAULT_PRESETS` 是代码常量，仅在 DB 无数据时返回。无 migration 将其写入 DB。如果 DB 表存在但为空，API 返回种子数据；如果表不存在，代码 crash。需检查 migration。

**#42 `_task_model` 函数不支持别名回退时的歧义**

`strategy_stream.py:88-95`。同时接受 `"optimize"` 和 `"optimization"` 两者（以及 `"validate"`/`"validation"`），但无文档说明哪个是规范形式。

---

## 三、逐功能模块深度评估

### 3.1 `/strategy` 快速回测 Tab

| 检查项 | 状态 | 评分 |
|--------|------|------|
| 3 核心字段（区间/策略/资金） | ✅ 有，且更多字段暴露 | B |
| 预设场景按钮（3 个） | ✅ 一键填充 | A |
| 策略卡片（中文名+描述+分类） | ✅ API 驱动 | A |
| 提交前确认对话框 | ✅ 含预计参数摘要 | B+ |
| Toast 提交/完成通知 | ✅ tone/auto-dismiss | A |
| 高级参数折叠 | ❌ 所有字段平铺展示 | D |
| 表单校验（行内提示） | ⚠️ 提交时一次性校验 | C |
| 预计耗时提示 | ❌ 确认框无运行时间预估 | D |
| 傻瓜式达标 | ⚠️ 表单字段偏多，未折叠 | C |

### 3.2 `/strategy` 信号复盘 Tab

| 检查项 | 状态 | 评分 |
|--------|------|------|
| SearchField 标的搜索 | ❌ 仅筛选器面板 | F |
| K 线周期选择 | ❌ 无 | F |
| 自然日期 → bar 换算 | ❌ 无 | F |
| 策略验证进度 | ❌ 无 | F |
| 整体评价 | 仅占位文字 + 旧 BacktestDashboard | D |

### 3.3 `/strategy` 参数优化 Tab

| 检查项 | 状态 | 评分 |
|--------|------|------|
| 滑块参数网格 | ❌ 桥接旧页面 | F |
| 中文标签下拉 | ⚠️ 旧页面已有中文 | C |
| IS vs OOS 对比 | ❌ 无 | F |
| 整体评价 | 桥接模式，旧功能可用但未傻瓜化 | D |

### 3.4 `/strategy` 样本外验证 Tab

| 检查项 | 状态 | 评分 |
|--------|------|------|
| 窗口卡片组 | ❌ 桥接旧页面 | F |
| 自然语言结论 | ❌ 无 | F |
| 整体评价 | 同优化 Tab | D |

### 3.5 `/strategy` 结果对比 Tab

| 检查项 | 状态 | 评分 |
|--------|------|------|
| 多选复选框 | ❌ 桥接旧页面 | F |
| 指标对比表 | ❌ 无 | F |
| ECharts 多线叠加 | ❌ 无 | F |
| 整体评价 | 同优化 Tab | D |

### 3.6 逐页面迁移

| 页面 | 表单组件 | 反馈组件 | 核心功能 | 傻瓜化 | 评分 |
|------|---------|---------|---------|--------|------|
| Monitor | ✅ SearchField+NumberField | ✅ | ⚠️ 4 按钮未简化为 2 | ⚠️ | B- |
| Analysis | ✅ SearchField+SelectField | ✅ | ❌ 结果未分层 | ⚠️ | B- |
| Playbook | ⚠️ Tab 仍硬编码 | ✅ | ❌ 无策略对比卡片 | ❌ | C |
| Research | ❌ lookback_bars 仍存在 | — | ❌ bar→日期未实现 | ❌ | D |
| Paper Trading | ❌ 委托弹窗未改 | — | ❌ 11 字段未两步化 | ❌ | D |
| Performance | ❌ 无自定义日期 | — | ❌ 无 hover 交互 | ❌ | D |
| Settings | ❌ 无校验反馈 | — | ❌ 无统一保存 | ❌ | D |

### 3.7 移动端

4 个 Tab 零改动。`MOBILE_STRATEGY_TABS` 仍硬编码，无下单按钮，无搜索持仓，无 stepper/ActionSheet。

### 3.8 全局增强

| 功能 | 状态 |
|------|------|
| Command+K | ❌ 不存在 |
| Cmd+1~8 | ❌ 不存在 |
| 骨架屏覆盖率 | ⚠️ 仅 StrategyHubPage 使用 |
| 策略历史看板 | ⚠️ 列表有，趋势图无 |
| ECharts 月度热力图 | ❌ 不存在 |
| ECharts 收益直方图 | ❌ 不存在 |

---

## 四、策略逻辑与选票结果复核

### 4.1 策略元数据正确性

`strategy_metadata_service.py` 种子数据中 5 个策略的 key/name/description 与 `backtestDisplay.ts` 硬编码一致。策略存在性由种子数据决定（间接由代码注册表决定），DB 仅覆盖展示文案——架构方向正确。

### 4.2 预设场景参数正确性

3 个预设的场景配置合理：
- "快速体检": 6 个月、开盘价成交 — 适合日常快速扫描 ✅
- "年度回顾": 12 个月、VWAP — 适合复盘策略全年表现 ✅
- "完整检验": 24 个月、开盘价 — 适合上线前严格验证 ✅

预设的 `strategies` 字段使用 `[seed.key for seed in DEFAULT_STRATEGY_META]` 动态生成，与策略注册表同步。

### 4.3 选票结果逻辑

Phase 3 未修改任何策略信号逻辑，选票结果与策略逻辑一致性无变化。Playbook 页虽从 API 拉取策略元数据，但选票计算仍使用原 `LowBuyScanSnapshot`/`LowBuyResultSnapshot` 表，数据路径未变。

---

## 五、性能评估

| 检查项 | 状态 | 详情 |
|--------|------|------|
| ECharts 包体积 | ⚠️ | LazyBacktestEquityChart 文件名含 Lazy 但靠消费者 `React.lazy` 实现。本文件是直接 import echarts，捆绑 `CanvasRenderer` 等 6 个模块。如果消费者未 lazy import，则全部进主包 |
| SearchField 防抖 | ✅ | 180ms debounce，减少 API 调用 |
| WebSocket 轮询效率 | ❌ | 3 秒间隔 × 每次新 DB session。对 5 分钟任务产生约 100 次重复查询 |
| Promise.all 失败代价 | ⚠️ | 单 API 失败导致 3 个 API 结果全部丢弃，需重新全部请求 |

---

## 六、修复建议（按优先级）

### P0 — 立即修复（阻塞验收）

1. **修复 `/backtests` 路由跳转**：`useStrategyHub.ts` `initialTabFromLocation` 增加 `"backtest"` → `"history"` 映射
2. **3 个占位 Tab 补核心功能**：
   - 优化 Tab：接入滑块范围组件（`SliderField`）→ 调用 Phase 2 API
   - 验证 Tab：窗口卡片组件 → 调用 Phase 2 API
   - 对比 Tab：多选复选框列表 → 调用 Phase 2 API
3. **修复 null owner 数据隔离**：`_user_can_view` 中 `owner is None` 改为拒绝或需 admin

### P1 — 本周修复

4. **WebSocket 增加 receive() + ping/pong**：循环中添加 `websocket.receive()` 检测断开；或至少增加 `try/except WebSocketDisconnect` 外层
5. **修复分页 total 字段**：`search_symbols` 中 `total = len(items)` → 返回真实匹配总数
6. **SearchField 错误提示**：`.catch` 中增加 `console.warn` 或 error state
7. **useStrategyHub.load 增加请求序列号**：仿 `SearchField` 的 seq pattern
8. **ECharts 确认 lazy**：检查 `BacktestPage` 是否 wrapper 引入 ECharts 路径，如果是直接 import 则加 `React.lazy`

### P2 — 两周修复

9. **Research 页迁移**：`lookback_bars` → 自然日期 + `SelectField` 周期
10. **Paper Trading 委托精简**：2 步式 + 去掉 `require_intraday_confirmation`
11. **Performance 自定义日期**：7/30/90/180 + "自定义"选项
12. **Settings 保存反馈**：InlineValidation + 按钮变绿 + "已保存"
13. **Playbook 策略对比卡片**
14. **后端全局日志**
15. **移动端下单入口 + 搜索持仓**
16. **Command+K 全局搜索**

---

## 七、结论

Phase 3 交付的基础设施（后端 API、共享组件、Toast、WebSocket 骨架）是正确的方向，`/strategy` 快速回测的快乐路径完整可用。但 14 个界面中 10 个处于未改造状态，优化/验证/对比 3 个 Tab 的桥接虽然诚实但体验断裂。

核心交付物——"让新用户 3 分钟完成回测"——通过快速回测 Tab 已基本实现。但原方案承诺的"每个页面 30 秒知道怎么用"在 10 个页面上尚未兑现。

**能否合并**: 基础设施（阶段一）可以合并。但 3 个占位 Tab 的桥接需明确——要么在合并前补核心功能，要么在 UI 上更明确地标注为"即将推出"而非可交互的 Tab。当前用户点击后看到旧页面的体验比明确的占位符更差。

**预计补工期**: P0 项 2-3 天，P1 项 3-4 天，P2 项 5-7 天。共计 **10-14 天**可达到 90%+ 完成度。
