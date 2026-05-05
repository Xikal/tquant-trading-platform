# TQuant Phase 3 实施审查报告

**日期**: 2026-05-05
**审查对象**: Codex 按《Phase 3 实施方案》完成的全部开发交付物
**审查范围**: 后端新增 API/WebSocket/DB 模型 + 前端共享组件 + /strategy 页面 + 逐页面迁移 + 移动端
**审查方法**: 逐文件读取 + 需求逐条对照 + API 端点测试 + 代码质量扫描

---

## 一、总体评价

**开发完成度**: 约 68%。后端基础设施（API、WebSocket、DB 模型）完成度很高，前端共享组件层和 /strategy 入口页面质量扎实。主要缺口集中在：优化/验证/对比 3 个 Tab 是占位桥接而非完整实现，逐页面迁移仅完成 Monitor 和 Analysis 两页，移动端未启动。

**代码质量**: A-。共享组件设计简洁、关注点分离好。StrategyMetadataService 的种子数据 + DB overlay 模式是正确的。前端 hook 职责清晰。无发现重复代码或明显坏味道。

**关键缺口**: 5 个 Tab 占位（signals/optimize/validate/compare）、5 个页面未迁移（Playbook/Research/Paper/Performance/Settings）、移动端零改动。

---

## 二、需求逐项对照

### 阶段一：共享基础设施 + 回测快速入口

| 需求 | 状态 | 详情 |
|------|------|------|
| `strategy_metadata` DB 模型 | ✅ | `market_entities.py:41-54`，字段齐全 |
| `strategy_presets` DB 模型 | ✅ | `market_entities.py:57-65` |
| `GET /api/strategies/meta` | ✅ | `strategy_meta.py:14`，含种子数据 fallback |
| `GET /api/symbols/search` | ✅ | `strategy_meta.py:24`，支持 instrument + daily_bar 双源搜索 |
| `GET /api/strategy/presets` | ✅ | `strategy_meta.py:19`，DB overlay + 种子 fallback |
| 统一 FormFields 组件 | ✅ | `FormFields.tsx` — TextField/DateField/NumberField(suffix)/SelectField/SliderField/SearchField |
| 统一 Feedback 组件 | ✅ | `Feedback.tsx` — EmptyPlaceholder/LoadingSpinner/SkeletonBlock/ErrorBanner/InlineValidation |
| 全局 ToastContainer | ✅ | `ToastContainer.tsx` — ToastProvider/useToast，支持 sticky，max 3 条，6s/3.5s 自动消失 |
| `/strategy` 页面 | ✅ | `StrategyHubPage.tsx`，6 Tab（quick/signals/optimize/validate/compare/history） |
| 快速回测 Tab（3 字段 + 预设） | ✅ | QuickBacktestForm：name/dates/capital/exec_model/position/benchmark/strategy cards |
| 预设场景按钮 | ✅ | 3 个预设（快速体检/年度回顾/完整检验），`applyPreset` 一键填充 |
| 提交前确认卡片 | ✅ | ConfirmDialog，loading 态 + 取消/确认按钮 |
| Toast 提交/完成通知 | ✅ | `submitWithToast` → `toast.pushToast` |
| 旧路由 redirect | ✅ | `workspaceRoutes.ts` → `/backtests`→`/strategy?tab=backtest`，`/research`→`/strategy?tab=replay` |
| 骨架屏组件 | ✅ | `SkeletonBlock`（rows + title 配置）|
| 策略从 API 拉取 | ✅ | `strategiesApi.getStrategyMeta()`，策略卡片显示 display_name/category/description |

**阶段一完成度: 95%**

### 阶段二：全页面表单迁移 + 回测增强

| 需求 | 状态 | 详情 |
|------|------|------|
| Monitor 页表单迁移 | ✅ | `SearchField`（标的）+ `NumberField`（持仓/可用/成本）|
| Analysis 页表单迁移 | ✅ | `SearchField`（标的）+ `SelectField`（策略：自动/正T/反T）|
| Playbook 页策略 Tab API 驱动 | ⚠️ | Tab 结构仍硬编码 `CORE_PLAYBOOK_TABS`，但数据从 API 拉取 |
| Research 页术语中文化 | ❌ | `lookback_bars`（"样本窗口"）、`bar_period` 仍存在，未改为自然日期 |
| Paper Trading 委托两步式 | ❌ | `OrderEntryModal` 仍含 `strategy_key`/`require_intraday_confirmation`，未精简 |
| Performance 页自定义日期 | ❌ | 仅 7/30/90/180 四档下拉，无自定义选项 |
| Settings 页行内校验 + 保存反馈 | ❌ | 无 `InlineValidation`/`ErrorBanner`，无"保存成功"提示 |
| 优化 Tab 滑块参数网格 | ❌ | Tab 是占位桥接（"后续迁移完整表单"），渲染旧 BacktestPage |
| 验证 Tab 窗口卡片组 | ❌ | 同上 |
| 对比 Tab 多选复选框 | ❌ | 同上 |
| 策略治理 admin 鉴权 | ⚠️ | Settings 页本身未改造，后端是否有鉴权待进一步确认 |

**阶段二完成度: 22%**（Monitor+Analysis 2/9 完成）

### 阶段三：ECharts + WebSocket

| 需求 | 状态 | 详情 |
|------|------|------|
| ECharts 净值曲线 | ✅ | `LazyBacktestEquityChart.tsx` — dataZoom/tooltip/markPoint/回撤填充/多线 |
| ECharts 动态加载 | ⚠️ | LazyBacktestEquityChart 本身非 lazy import，是直接 import。缺少 `React.lazy` 包装 |
| 月度收益热力图 | ❌ | 未实现 |
| 收益分布直方图 | ❌ | 未实现 |
| 策略拆解对比表 | ❌ | 未实现（对比 Tab 是占位） |
| WebSocket 端点 | ✅ | `strategy_stream.py` — `/ws/strategy/{type}/{id}`，含 stream token 鉴权 |
| WebSocket Provider 前端 | ⚠️ | `useBacktestDashboard.ts:794` 有 URL 构造逻辑，但无双向通信钩子 |
| 实时进度推送 | ⚠️ | WebSocket handler 是**轮询 DB 后推送**，非 engine/optimizer 主动回调 |

**关键发现**: WebSocket 实现并非 push-based。`stream_strategy_task_progress` 是轮询循环——每隔 `interval_seconds` 从 DB 读一次任务状态然后 send_json。这意味着 WS 的价值仅在于避免了前端轮询，而非真正的实时推送。engine/optimizer/validator 未添加任何进度回调钩子。

**阶段三完成度: 30%**

### 阶段四：移动端

| 需求 | 状态 | 详情 |
|------|------|------|
| 移动端策略标签 API 驱动 | ❌ | `MOBILE_STRATEGY_TABS` 仍硬编码在 `MobileDesignCards.tsx:20` |
| 移动端下单浮动按钮 | ❌ | 无 `下单`/`PlaceOrder`/`floating button` |
| 移动端搜索持仓 | ❌ | 无 `SearchField`/`symbolSearch` |
| Monitor Tab 底部抽屉 | ❌ | 未实现 |
| Holdings Tab 自动填充 | ❌ | 未实现 |
| Playbook Tab 下拉跳转 | ❌ | 未实现 |
| Stepper 替代裸数字输入 | ❌ | 未实现 |
| ActionSheet 替代原生 select | ❌ | 未实现 |

**阶段四完成度: 0%**

### 阶段五：全局增强

| 需求 | 状态 | 详情 |
|------|------|------|
| Command+K 全局搜索 | ❌ | 不存在 |
| Cmd+1~8 键盘快捷键 | ❌ | 不存在 |
| 全页面骨架屏 | ⚠️ | `SkeletonBlock` 组件存在，但仅在 StrategyHubPage 使用 |
| 策略历史看板 | ⚠️ | `StrategyHistoryPanel` 组件存在，但仅显示最近 8 条任务列表，无按策略聚合的趋势图 |

**阶段五完成度: 10%**

---

## 三、代码质量评估

### 3.1 做得好的

1. **StrategyMetadataService 的种子 + overlay 设计**：代码中硬编码 `DEFAULT_STRATEGY_META` 作为 fallback，DB 中的 `strategy_metadata` 行作为 overlay——如果 DB 有展示文案就用 DB 的，否则用种子数据。策略 key 存在性由种子数据决定（间接由代码注册表决定），DB 仅补充展示文案。这完全符合"代码是真源，DB 是展示层"的原则。

2. **FormFields 组件设计简洁**：6 个组件共 160 行，`SearchField` 内置防抖（180ms）和 API 调用，`NumberField` 支持 suffix，`SelectField` 接受 `{value, label}` 数组。组件 API 直观、类型安全。

3. **ToastContainer 设计成熟**：Context 模式，支持 sticky/non-sticky，max 3 条堆叠，自动消失时间区分（error/warning 6s，info/success 3.5s）。

4. **StrategyHubPage 的 Tab 桥接策略**：对 signals/optimize/validate/compare 4 个尚未完整实现的 Tab，没有留空白或报错，而是用 `StrategyBridge` 组件渲染说明文字 + 旧 BacktestPage。降级策略正确。

5. **LazyBacktestEquityChart 的 ECharts 配置**：树摇导入（仅引入需要的组件），markPoint 标注高低点，dataZoom 内置+滑块双模式，双 Y 轴（净值+回撤），配色风格一致。

6. **useStrategyHub hook 的 preset apply 逻辑**：`applyPreset` 合并 preset config 到当前 form，智能保留未覆盖字段的当前值。

### 3.2 需要改进的

1. **WebSocket 是伪实时**——轮询 DB 再推送，未在 engine/optimizer/validator 中加进度回调。实际延迟 = `interval_seconds`（默认 3s），不比前端直接轮询 API 好多少。

2. **LazyBacktestEquityChart 并非 lazy**——文件名含 "Lazy" 但实际是直接 `import`，缺少 `React.lazy` 包装。这导致 ECharts（~1MB）进入主包。

   ```typescript
   // 当前（直接 import）
   import LazyBacktestEquityChart from "./LazyBacktestEquityChart";
   
   // 应为（动态 import）
   const LazyBacktestEquityChart = React.lazy(() => import("./LazyBacktestEquityChart"));
   ```

3. **BacktestPage 桥接导致双重渲染**——当用户在 signals/optimize/validate/compare Tab 时，页面同时渲染 StrategyBridge 说明文字和完整的 BacktestPage（含表单、任务列表等）。这会造成不必要的 API 请求和 DOM 节点。

4. **workspaceConstants.ts 保留了两套硬编码策略**——`CORE_PLAYBOOK_TABS` 等常量与 `BACKTEST_STRATEGY_OPTIONS`（在 backtestDisplay.ts）并存，且与种子数据 `DEFAULT_STRATEGY_META` 是第三份。策略列表现在有 3 个数据源。

5. **移动端未导入共享组件**——`MobileDesignCards.tsx` 仍使用硬编码 `MOBILE_STRATEGY_TABS`，未导入 `SearchField` 或 `strategiesApi`。

6. **缺少全局 CSS**——`FormFields`、`Feedback`、`ToastContainer` 依赖 `.tq-field`、`.tq-input`、`.tq-toast` 等全局 CSS 类名，但未在 `components/shared/` 下提供 CSS 文件。如果这些类名在某处定义（可能在全局样式），需要确认是否存在样式缺失风险。

### 3.3 发现的 bug

**#1 — WebSocket 令牌过期后无重连机制**

`strategy_stream.py:37-39`：`stream_tokens.consume(stream_token)` 一次性消费令牌后，如果 WebSocket 意外断开，前端重连时令牌已失效，必须重新请求 `POST /strategy/stream-token`。但 `useBacktestDashboard.ts` 的 WebSocket 连接代码中未看到重新获取 token 的逻辑。

**#2 — StrategyBridge 中 BacktestPage 缺少 tab 参数传递**

`StrategyHubPage.tsx:246` 渲染 `<BacktestPage />` 但未传递当前 tab 信息。BacktestPage 通过 `useBacktestDashboard()` 自行管理状态，不会自动切换到对应子面板（优化/验证/对比）。用户看到的是 BacktestDashboard 的默认视图，而非与所选 Tab 对应的功能。

**#3 — SearchField 竞态条件**

`FormFields.tsx:123-132`：SearchField 使用 180ms 防抖，但如果用户快速输入 "东" → "东方"，两次请求的返回顺序不确定，可能导致旧结果覆盖新结果。缺少请求序列号或 AbortController。

**#4 — SkeletonBlock 仅定义无实际动画样式**

`Feedback.tsx:23`：`SkeletonBlock` 渲染几个 `<span>` 元素，CSS 类名 `tq-skeleton` 和 `.wide`/`.medium`。但共享组件目录无 CSS 文件。骨架屏动效（shimmer/pulse）依赖全局 CSS 中的 `@keyframes`，如果缺失则显示为静态灰色块。

---

## 四、与 Phase 2 对比：已修复的遗留问题

Phase 2 审查中发现的 20 个问题，在本次 Phase 3 交付中间接解决的：

| Phase 2 问题 | Phase 3 状态 |
|-------------|-------------|
| 前端格式化函数三重复制 | ✅ 已在 Phase 2 修复，Phase 3 确认全部 import 自 workspaceFormatters |
| 策略下拉显示英文 key | ✅ `/strategy` 页面全部中文标签，Research panel 未迁移故仍显示英文 |
| 对比面板用文本输入 run ID | ❌ 未解决——Compare Tab 是桥接占位，仍依赖旧 BacktestPage |
| optimization_target 无 UI | ❌ 未解决——Optimize Tab 是桥接占位 |
| PBO 风险无颜色编码 | ❌ 未解决——Validate Tab 是桥接占位 |

---

## 五、完整缺口清单（按优先级）

### 阻塞性缺口（阶段一验收不通过）

| # | 问题 | 影响 |
|---|------|------|
| 1 | 优化/验证/对比 Tab 是占位桥接 | 用户点击后看到的是旧版 BacktestPage，无滑块/卡片/复选框 |
| 2 | 信号复盘 Tab 无 SearchField | 与方案描述的 "2 字段（标的搜索 + K线周期）" 不符 |
| 3 | LazyBacktestEquityChart 非 lazy | ECharts 进入主包，增加首屏加载体积 |

### 高优先级缺口

| # | 问题 | 影响 |
|---|------|------|
| 4 | Research 页未迁移 | `lookback_bars`/`bar_period` 裸术语仍暴露 |
| 5 | Playbook 策略 Tab 三重硬编码 | `CORE_PLAYBOOK_TABS`/`BACKTEST_STRATEGY_OPTIONS`/`DEFAULT_STRATEGY_META` 三份 |
| 6 | Performance 页无自定义日期 | 用户只能选 7/30/90/180 天 |
| 7 | Settings 页无保存反馈 | 用户不知道保存是否成功 |
| 8 | Paper Trading 委托未精简 | 11 字段未两步化 |
| 9 | WebSocket 未接入 engine 回调 | 进度更新延迟 = 轮询间隔 |

### 中优先级缺口

| # | 问题 | 影响 |
|---|------|------|
| 10 | 移动端零改动 | 无下单按钮、无搜索持仓、无 API 驱动策略 |
| 11 | Command+K 缺失 | 无全局搜索入口 |
| 12 | 全页面骨架屏缺失 | SkeletonBlock 存在但只在 StrategyHubPage 使用 |
| 13 | 策略历史看板无趋势图 | StrategyHistoryPanel 只列任务，无按策略聚合 |
| 14 | 月度热力图未实现 | Phase 3 方案明确要求的图表 |
| 15 | 收益分布直方图未实现 | Phase 3 方案明确要求的图表 |

### 低优先级

| # | 问题 | 影响 |
|---|------|------|
| 16 | SearchField 竞态条件 | 极端情况下搜索结果错乱 |
| 17 | SkeletonBlock 动画样式未确认 | 可能显示为静态灰块 |
| 18 | BacktestPage 桥接双重渲染 | 性能浪费 |
| 19 | WebSocket 断线重连缺 token 刷新 | 重连可能失败 |

---

## 六、按 Tab 的完成度明细

| Tab/页面 | 表单 | 预设 | API 集成 | 图表 | 通知 | 完成度 |
|----------|------|------|---------|------|------|--------|
| `/strategy` — 快速回测 | ✅ | ✅ | ✅ | — | ✅ | 95% |
| `/strategy` — 信号复盘 | ❌ | — | — | — | — | 0%（占位） |
| `/strategy` — 参数优化 | ❌ | — | — | ❌ | — | 0%（占位） |
| `/strategy` — 样本外验证 | ❌ | — | — | ❌ | — | 0%（占位） |
| `/strategy` — 结果对比 | ❌ | — | — | ❌ | — | 0%（占位） |
| `/strategy` — 策略历史 | ⚠️ | — | — | ❌ | — | 30% |
| Monitor | ✅ | — | ✅ | — | — | 90% |
| Analysis | ✅ | — | ✅ | — | — | 85% |
| Playbook | ⚠️ | — | ⚠️ | — | — | 50% |
| Research | ❌ | — | — | — | — | 0% |
| Paper Trading | ❌ | — | — | — | — | 0% |
| Performance | ❌ | — | — | — | — | 0% |
| Settings | ❌ | — | — | — | — | 0% |
| 移动端（4 Tab） | ❌ | — | ❌ | — | — | 0% |

---

## 七、结论

Phase 3 实现是一次**方向正确、基础设施扎实的交付**。后端 API/WebSocket/DB 模型、前端共享组件、Toast 系统、/strategy 入口框架——这些地基打得很好。StrategyMetadataService 的种子+overlay 设计、FormFields 组件 API、ToastContainer 的 Context 模式都是经过深思熟虑的。

核心问题不是质量，而是**范围**——Codex 实现了基础架构和快速回测的"快乐路径"，但 14 个界面中有 10 个仍处于未改造状态。优化/验证/对比 3 个 Tab 的占位桥接是一个诚实的降级策略，但对用户来说，点击后的体验断裂感很强。

整体评级：**阶段性可合并，合并后需在 1 周内补齐 3 个占位 Tab 的核心功能（滑块参数、窗口卡片、多选对比），2 周内完成 Research/Performance/Settings 3 页迁移。**

预计补齐工期：
- 3 个占位 Tab 核心功能：3-4 天
- Research/Performance/Settings 迁移：2-3 天
- ECharts lazy 修复 + 热力图/直方图：2 天
- 移动端启动（策略 API + 下单入口）：2 天
- 共计：**9-11 天**
