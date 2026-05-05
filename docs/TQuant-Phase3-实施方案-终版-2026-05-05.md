# TQuant Phase 3 实施方案（终版）

**日期**: 2026-05-05
**前置**: [全系统 UX 与回测优化方案](./TQuant-Phase3-全系统UX与回测优化方案-最终版-2026-05-05.md)（纲领）→ [Codex 核查反馈](./Codex-Phase3-核查结论-2026-05-05.md)（纠偏）→ 本文（可执行的路线图）
**定位**: 综合原始方案和 Codex 反馈后，按优先级分层的渐进式实施计划。每阶段独立可交付、独立可验收，不依赖后续阶段。

---

## 一、核查确认：哪些对、哪些错、哪些已经做好了

Codex 的核查结论整体方向正确，但存在几处事实偏差。以下是逐条核验：

### 1.1 Codex 正确的判断

| Codex 判断 | 核验结果 |
|-----------|---------|
| `/api/strategies/meta` 不存在 | ✅ 确认。后端无此端点，路由中无任何 `strategies/meta` |
| `/api/symbols/search` 不存在 | ✅ 确认。搜索接口缺失，解析页、Monitor 页标的输入均为裸文本框 |
| `/ws/strategy` 不存在 | ✅ 确认。后端无任何 WebSocket 端点 |
| `strategy_metadata` 表不存在 | ✅ 确认。SQLAlchemy models 中无此实体 |
| `strategy_presets` 表不存在 | ✅ 确认 |
| `/strategy` 统一入口不存在 | ✅ 确认。前端无 `StrategyHubPage` 组件，回测和研究仍是两个独立页面 |
| 无全局 ToastContainer | ✅ 确认。仅移动端有 `signalToastVisible` 局部实现，无统一通知系统 |
| 策略选项硬编码 | ✅ 确认。`BACKTEST_STRATEGY_OPTIONS` 定义在 `backtestDisplay.ts:3-9`，`MOBILE_STRATEGY_TABS` 定义在 `MobileDesignCards.tsx:20`，均为硬编码常量数组 |

### 1.2 Codex 不准确或已过时的判断

| Codex 判断 | 实际情况 |
|-----------|---------|
| "回测、移动端、模拟盘仍存在局部格式化和局部展示逻辑" | ❌ 此问题已修复。`BacktestDashboard.tsx`、`BacktestResearchPanel.tsx`、`PaperTradingPanel.tsx` 全部 import 自 `workspaceFormatters.ts`。移动端文件（mobile/ 目录下）经 grep 确认无本地 `formatPct`/`formatNumber` 定义。格式化函数去重**已在 Phase 2 完成**，Phase 3 无需重复修复 |
| "Settings 页开放暂停/启用策略有风险" | 原始方案的 "策略治理增加操作" 仅指前端治理列表增加开关和跳转链接，并非直接修改策略逻辑。但 Codex 的警惕是对的——需要在 API 层加 admin 鉴权 |

### 1.3 Codex 建议中需要讨论的部分

| Codex 建议 | 分析 |
|-----------|------|
| "不要做响应式桌面端，这点我不认同" | 原始方案写的是 "不做响应式桌面端——固定宽度布局不变"，意图是：不引入 breakpoint 驱动的响应式重构（桌面→平板→手机）。这意味着保持当前流式布局，不固化死宽度。与 Codex 方向一致，原文表述应修正为 "不做断点式响应式重构，保持流式自适应" |
| "strategy_metadata 不建议第一版作为策略真源" | 合理。`strategy_metadata` 表不应替代后端策略注册逻辑，只承担展示层职责：中文名、描述、分类、排序。策略的存在性由代码注册表决定，名称/描述从 DB 读取——DB 是展示源，代码是真源 |
| "ECharts 不应全系统铺开" | 与原始方案一致。原始方案明确 "仅在回测净值曲线和新增图表使用 ECharts，Performance 页 SVG 保留" |
| "WebSocket 不要阻塞整体上线" | 合理。WebSocket 作为优化而非必要条件，第一版用轮询即可 |

---

## 二、核心原则

基于 Codex 反馈修正后的实施原则：

1. **渐进交付**：每阶段独立可发布，不依赖后续阶段。可以先上线阶段一改善体验，阶段二三在后续版本迭代
2. **展示与逻辑分离**：`strategy_metadata` 是展示层，策略注册表是逻辑层。元数据表只存中文名/描述/排序，不存策略逻辑配置
3. **旧路由不删除**：`/backtests` 和 `/research` 保留为 301 redirect，不在本次删除
4. **ECharts 按需加载**：仅在回测图表使用，动态 import，不增主包体积
5. **WebSocket 后置**：先用轮询 + toast 打通流程，WebSocket 作为阶段三的增强
6. **Admin 鉴权**：Settings 页策略治理操作（暂停/启用）必须走 admin API 鉴权

---

## 三、分阶段实施方案

### 阶段一：共享基础设施 + 回测快速入口（2 周，P0）

目标：统一输入/显示层，让用户 1 分钟内完成一次回测。不碰任何现有页面的业务逻辑。

#### 3.1.1 后端新增

```
# 策略元数据 API（从后端策略注册表生成，非数据库驱动）
GET  /api/strategies/meta
  → 返回策略列表：key, name, description, category, risk_level, typical_holding_days
  → 数据来源：
     1. 优先从 strategy_metadata 表读展示文案（如有）
     2. fallback 到后端策略注册表的默认名称
     3. 仅返回当前已注册的活跃策略（注册表为准）

# 标的搜索 API
GET  /api/symbols/search?q=东方
  → 返回匹配的标的列表：symbol, name, latest_price（可选）
  → 数据来源：daily_bar_snapshots 最近交易日的 DISTINCT symbol + name
  → 匹配方式：symbol 前缀匹配 + name 模糊匹配（LIKE）

# 预设场景 API
GET  /api/strategy/presets
  → 返回预设场景列表：name, description, config_json
  → 数据来源：strategy_presets 表
```

新增表（SQLite）：

```sql
-- 策略展示元数据（展示层，非逻辑源）
CREATE TABLE strategy_metadata (
    key TEXT PRIMARY KEY,           -- first_board（必须与代码注册表 key 一致）
    display_name TEXT NOT NULL,     -- 首板回调
    description TEXT DEFAULT '',    -- 策略说明
    category TEXT DEFAULT '',       -- 回调类 / 趋势类
    sort_order INTEGER DEFAULT 0,  -- 前端展示排序
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 预设回测场景
CREATE TABLE strategy_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,             -- 快速体检
    description TEXT DEFAULT '',
    config_json TEXT NOT NULL,      -- 完整 BacktestConfig JSON
    sort_order INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

种子数据（3 个预设场景 + 5 个策略元数据行）。

#### 3.1.2 前端新增

**新建文件**：

```
frontend/src/
├── components/shared/
│   ├── FormFields.tsx          ← 统一表单组件（TextField/SelectField/NumberField/SearchField/DateField）
│   ├── Feedback.tsx            ← 统一反馈组件（EmptyPlaceholder/LoadingSpinner/ErrorBanner/InlineValidation）
│   └── ToastContainer.tsx      ← 全局 toast 通知（自动消失 + 手动关闭 + 颜色编码）
├── features/strategy/          ← 新增：统一策略研究入口
│   ├── StrategyHubPage.tsx     ← 主页面（Tab 切换）
│   ├── QuickBacktestTab.tsx    ← 快速回测 Tab（3 字段 + 预设场景）
│   ├── BacktestPresets.tsx     ← 预设场景按钮组
│   ├── BacktestConfirmDialog.tsx ← 提交前确认卡片
│   └── hooks/
│       └── useStrategyHub.ts   ← 状态管理
└── api/
    └── strategies.ts           ← 新增 API 客户端（/strategies/meta, /symbols/search, /strategy/presets）
```

**改造文件**：

| 文件 | 改造内容 |
|------|---------|
| `backtestDisplay.ts` | `BACKTEST_STRATEGY_OPTIONS` 改为从 API 拉取（保留静态 fallback） |
| `MobileDesignCards.tsx` | `MOBILE_STRATEGY_TABS` 改为从 API 拉取 |
| `App.tsx` 或路由配置 | 新增 `/strategy` 路由 + `/backtests` → `/strategy?tab=backtest` redirect + `/research` → `/strategy?tab=replay` redirect |
| 所有使用裸 `<input>` 的地方 | 逐步替换为 `SearchField`（标的输入）、`NumberField`（数字输入） |

**不改造的文件**（阶段一不动）：

- BacktestDashboard.tsx（保留，旧入口 redirect 后仍可用）
- BacktestResearchPanel.tsx（保留）
- ResearchPage.tsx（保留）
- Monitor 页（阶段二改造）
- Analysis 页（阶段二改造）

#### 3.1.3 快速回测 Tab 的第一版

仅实现最核心路径：

1. **策略多选标签**（从 API 拉取中文名，默认全选）
2. **回测区间双日期选择器**（默认最近 1 年）
3. **初始资金数字输入**（默认 500,000 元）
4. **3 个预设场景按钮**（快速体检/年度回顾/完整检验）
5. **高级参数折叠**（点击"更多设置"展开：成交模型/仓位/止损止盈/基准）
6. **提交前确认卡片**（展示即将运行的配置摘要）
7. **任务列表**（复用现有轮询，暂不用 WebSocket）
8. **提交/完成 toast 通知**（toast 3 秒自动消失，完成 toast 含关键指标摘要）

**阶段一验收标准**：

1. `GET /api/strategies/meta` 返回 5 个策略的中文名和描述
2. `GET /api/symbols/search?q=东方` 返回 `300059 东方财富` 等匹配结果
3. `GET /api/strategy/presets` 返回 3 个预设场景
4. 新页面 `/strategy` 可访问，`/backtests` 和 `/research` 301 跳转正常
5. 快速回测 Tab：选择策略 → 点击预设场景 → 确认 → 提交 → 任务列表显示进度 → toast 通知完成
6. 全程无英文 key 暴露给用户
7. 旧页面（`/backtests`、`/research`）功能不受影响
8. 无控制台报错，无白屏


### 阶段二：全页面表单 + 回测增强（2 周，P1）

目标：所有页面用统一组件，回测系统参数优化/验证/对比傻瓜化。

#### 3.2.1 表单组件统一迁移

将以下页面的输入控件替换为 `FormFields` 组件：

| 页面 | 替换内容 |
|------|---------|
| Monitor | 持仓搜索改用 `SearchField`，数量输入改用 `NumberField` |
| Analysis | 标的搜索改用 `SearchField`，`prefer_strategy` 下拉改用 `SelectField`（中文标签） |
| Playbook | 策略 Tab 改为 API 驱动 |
| Research | `lookback_bars` → `NumberField` + "天"后缀，`bar_period` → `SelectField`（1/5/15 分钟） |
| Paper Trading | 委托弹窗精简为两步式（第一步 3 字段，第二步折叠） |
| Performance | 日期选择增加自定义选项 |
| Settings | `NumberField` + 单位后缀 + URL 格式校验 + 保存反馈 |

#### 3.2.2 统一反馈组件迁移

- 所有页面的空状态 → `EmptyPlaceholder`
- 所有页面的加载态 → `LoadingSpinner`（优先使用骨架屏的页面暂用 Spinner，阶段五上骨架屏）
- 所有页面的错误提示 → `ErrorBanner`（含重试按钮）
- 所有表单字段的内联校验 → `InlineValidation`

#### 3.2.3 回测增强

优化 Tab（基于 Phase 2 API）：
- 参数范围用滑块替代逗号分隔文本框
- 策略下拉中文标签（API 驱动）
- IS vs OOS 对比柱状图（ECharts，动态 import）

验证 Tab（基于 Phase 2 API）：
- 窗口卡片组（默认 4 窗口、75% 训练比例）
- 自然语言稳定性结论

对比 Tab：
- 多选复选框列表替代手动输入 run ID
- 指标对比表（可排序）
- 净值曲线叠加图（ECharts，动态 import）

#### 3.2.4 Settings 策略治理（Admin 保护）

Settings 页策略治理列表增加：
- "暂停"/"启用"开关（需 admin 鉴权，仅改治理标记，不改策略阈值）
- "编辑参数"链接（跳转 Playbook 对应 Tab）

**阶段二验收标准**：

1. Monitor/Analysis/Playbook/Research/Paper/Performance/Settings 共 7 页的输入控件使用统一组件
2. 空/加载/错误状态使用统一组件
3. 优化参数用滑块设置，不再手动输入逗号分隔
4. 对比 tab 用多选复选框选择已完成回测
5. Settings 保存后有反馈提示
6. 策略治理操作需 admin 鉴权


### 阶段三：ECharts 图表 + WebSocket（1.5 周，P2）

目标：净值曲线可交互，WebSocket 实时进度。

#### 3.3.1 ECharts 回测图表

- 净值曲线全面升级（缩放平移/tooltip/买卖点标记/回撤填充/多线叠加）
- 月度收益热力图
- 收益分布直方图（含正态拟合）
- 策略拆解对比表（可排序可筛选）

关键约束：
- 所有 ECharts 组件 `React.lazy(() => import(...))` 动态加载
- SVG 降级方案保留（loading 态 + 错误回退）
- Performance 页 SVG 保留不变
- 不引入 ECharts 到回测之外的页面

#### 3.3.2 WebSocket 实时进度

```
WS /ws/strategy/{task_type}/{task_id}
```

- engine/optimizer/validator 在关键节点推送进度
- 前端 WebSocket Provider：自动连接/断线重连/消息分发
- 任务列表进度条实时更新（替代轮询）
- 完成后 toast 自动弹出关键指标

降级策略：WebSocket 断线时自动回退到 15 秒轮询。

**阶段三验收标准**：

1. 净值曲线支持缩放平移，hover 显示 tooltip
2. 月度热力图红绿分明，单元格标注收益率
3. 收益分布直方图叠加正态曲线
4. WebSocket 推送进度，任务列表进度条实时更新
5. WebSocket 断线后自动回退轮询，不影响功能


### 阶段四：移动端补齐（1 周）

目标：移动端交互逻辑与桌面端一致。

- 格式化函数 + API 客户端共享（已基本完成）
- Monitor Tab：点击优先榜卡片 → 底部抽屉（快捷查看入场区+信号评分）
- Holdings Tab：搜索标的 → 自动带出最新价
- Playbook Tab：下拉快速跳转策略
- Paper Tab：右下角浮动"下单"按钮 → 简化委托弹窗（标的/方向/数量 3 字段）
- 所有移动端表单统一用 stepper + ActionSheet

**阶段四验收标准**：

1. 移动端策略标签与桌面端一致（从同一 API 拉取）
2. 移动端模拟盘可下单
3. 移动端持仓新增支持搜索+自动填充


### 阶段五：全局增强（0.5 周）

- Command+K 全局搜索
- 键盘快捷键（Cmd+1~8 切换页面）
- 全页面骨架屏（优先 Monitor/Analysis/Playbook/回测）
- 策略回测历史看板（`/strategy/history`）

---

## 四、优先级裁定

### P0（阶段一，必须首发）

| 条目 | 说明 |
|------|------|
| 策略元数据 API | `GET /api/strategies/meta` |
| 标的搜索 API | `GET /api/symbols/search` |
| 统一 FormFields 组件 | TextField/SelectField/NumberField/SearchField/DateField |
| 统一 Feedback 组件 | EmptyPlaceholder/LoadingSpinner/ErrorBanner |
| 全局 ToastContainer | 统一通知系统 |
| 回测快速入口 `/strategy` | 3 字段 + 预设场景 + 确认 + toast |
| 旧路由 redirect | `/backtests` → `/strategy?tab=backtest`，`/research` → `/strategy?tab=replay` |

### P1（阶段二）

| 条目 | 说明 |
|------|------|
| 全页面表单迁移 | 7 个页面统一使用 FormFields |
| 全页面反馈迁移 | 统一 EmptyPlaceholder/LoadingSpinner/ErrorBanner |
| 优化滑块化 | 参数范围用滑块，不再手动输逗号分隔 |
| 对比复选框 | 多选复选框替代文本输入 run ID |
| Playbook API 驱动 | 策略 Tab 从 API 拉取 |
| Research 术语中文化 | bar→自然日期 |
| Paper 委托两步式 | 3 字段默认 + 折叠选填 |
| Settings 治理操作 | admin 鉴权 |

### P2（阶段三）

| 条目 | 说明 |
|------|------|
| ECharts 净值曲线 | 缩放/tooltip/标记/回撤填充（动态 import） |
| ECharts 热力图 + 直方图 | 月度热力图 + 收益分布 |
| WebSocket 进度 | 实时进度条（保留轮询降级） |

### P3（阶段四-五）

| 条目 | 说明 |
|------|------|
| 移动端补齐 | 搜索持仓、下单入口、底部抽屉 |
| Command+K | 全局搜索 |
| 骨架屏 | 数据面板加载态 |
| 策略历史看板 | `/strategy/history` |

---

## 五、与原始方案的关键差异

| 原始方案 | 修正后方案 | 原因 |
|---------|-----------|------|
| 一次性全量重构，4 周 | 5 阶段渐进交付，5 周 | 降低风险，每阶段独立验证 |
| 策略元数据来自 DB 表 | 展示文案来自 DB，策略存在性来自代码注册表 | 代码是真源，DB 是展示层 |
| "不做响应式桌面端" | 保持流式自适应，不做断点式重构 | 表述修正，方向一致 |
| 格式化去重作为阶段一工作 | 已确认完成，无需重复 | BacktestDashboard/ResearchPanel/PaperTradingPanel 已 import workspaceFormatters |
| WebSocket 在回测专项（阶段二） | 推迟到阶段三，先用轮询 | 降低首发复杂度 |
| Settings 策略治理不加鉴权 | admin 鉴权 + 不改策略逻辑 | 安全 |
| 旧路由保留 redirect 未明确时限 | 长期保留，不删除 | 避免书签失效 |
| ECharts 全页面升级 | 仅回测页面使用，动态 import | 控制包体积 |

---

## 六、不做清单（追加）

在原始方案"不做清单"基础上追加：

11. **不删除旧页面**——`/backtests` 和 `/research` 保留为 301 redirect，至少保留一个大版本周期
12. **不让 DB 驱动策略存在性**——策略是否活跃由后端注册表决定，`strategy_metadata` 仅提供展示文案
13. **不在阶段一引入 WebSocket**——先跑通轮询 + toast 流程
14. **ECharts 不进入主包**——动态 import，仅在回测页面使用
15. **Settings 策略治理操作不绕过 admin 鉴权**——暂停/启用必须是 admin 操作

---

## 七、总工期与里程碑

| 阶段 | 工期 | 累计 | 可交付成果 |
|------|------|------|-----------|
| 一：基础设施 + 回测入口 | 2 周 | 2 周 | `/strategy` 上线，3 步回测可用，toast 通知，标的搜索 |
| 二：全页面迁移 + 回测增强 | 2 周 | 4 周 | 7 页面表单统一，优化/验证/对比傻瓜化，Settings 治理 |
| 三：ECharts + WebSocket | 1.5 周 | 5.5 周 | 交互图表，实时进度 |
| 四：移动端 | 1 周 | 6.5 周 | 移动端下单、搜索持仓、底部抽屉 |
| 五：全局增强 | 0.5 周 | 7 周 | Command+K、骨架屏、策略历史看板 |

阶段一完成后即可发布首个版本，后续阶段按节奏迭代。

---

## 八、技术约束

1. **ECharts 动态加载**：`const EquityChart = React.lazy(() => import('./EquityChart'))`，配置 webpack chunk name
2. **WebSocket 隔离**：Worker 进程通过共享状态（Redis/DB）与 Web 进程通信，不在 Web 进程中执行回测计算
3. **策略元数据一致性**：`GET /api/strategies/meta` 返回的策略列表以代码注册表为准，`strategy_metadata` 表只补充展示文案。如果某个策略在注册表中但未在 metadata 表中，返回 key 作为 display_name 的 fallback
4. **toast 组件设计**：支持叠加显示（最多 3 条），关键消息（OOS 降级）不自动消失
5. **流式布局**：桌面端不固化宽度，使用 `max-width` + 百分比布局，保持窗口自适应
