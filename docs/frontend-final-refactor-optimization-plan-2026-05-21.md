# TQuant 前端最终重构优化落地方案

> 状态：执行中历史方案。当前完成度、保留项和验证结果以 `IMPLEMENTATION_PLAN.md` 为准；本文件保留原始目标，避免与实际分阶段交付口径混用。

生成日期：2026-05-21
适用项目：维斯量化 TQuant A 股短线交易辅助平台
目标读者：Codex / Claude Code / 前端开发 / QA / 产品验收

## 1. 总体结论

### 1.1 当前技术栈研判

当前前端位于 `frontend/`，核心栈为：

- React 18.3.1
- Vite 8
- TypeScript 5.6
- ECharts 5
- Capacitor 8
- 自研 API 请求层、缓存、离线兜底
- Web 入口：`frontend/src/main.tsx`
- Native 入口：`frontend/src/main-native.tsx`
- Web 工作台主入口：`frontend/src/features/trading-workspace/TradingWorkspace.tsx`
- App 主入口：`frontend/src/mobile/MobileApp.tsx`

当前主要问题不是 React/Vite 架构选错，而是 UI 工程层缺少成熟组件库与统一设计系统，导致：

- 基础组件大量手写：按钮、表单、弹窗、卡片、空态、加载态、Toast、Sheet、Tab、列表均有重复实现。
- 页面视觉不统一：Web 与 App 之间组件语言、间距、字号、状态表达不一致。
- 交互成本高：操作入口分散，主要动作和次要动作层级不清。
- 前端数据状态自管过多：存在自研 `requestCached`、手工 loading key、局部 refresh 逻辑，后续维护成本高。
- 路由仍为手写路径映射：`workspaceRoutes.ts` 只做路径到页面状态映射，不利于嵌套路由、错误页、权限页和页面级懒加载管理。

### 1.2 架构留用 or 替换结论

结论：保留 React + Vite + Capacitor，不整体替换为 Next.js / 微前端 / 重写 App；新增成熟 UI 组件库、React Router、TanStack Query，并按业务模块重构。

不建议整体更换架构：

- 当前项目是交易辅助工作台 + 原生 App WebView 壳，不需要 SSR。
- 后端已经托管 `frontend/dist`，Vite 静态产物适配现有云端部署。
- Capacitor 已经打通 Android/iOS 原生包流程，保留成本最低。
- React 18 满足 Ant Design 6、antd-mobile 5、TanStack Query 等主流库的 peer 依赖。
- 改为 Next.js 会引入服务端渲染、路由约束、部署改造和安全策略改造，不解决当前核心问题。

不建议微前端：

- 当前前端代码总量约 3.7 万行，仍处于单体可维护规模。
- 业务模块之间共享认证、行情、持仓、策略元数据和 BFF 响应，微前端会增加状态同步、构建部署复杂度。
- 微前端适合多团队、多子系统独立发布；当前更需要模块化单体和统一设计系统。

需要做的架构升级：

- 引入 PC 端 UI 组件库：`antd@6`。
- 引入移动端 UI 组件库：`antd-mobile@5`。
- 引入服务端状态管理：`@tanstack/react-query@5`。
- 引入标准路由：`react-router@7`。
- 对长列表引入虚拟列表：优先使用 Ant Design Table `virtual` 能力；移动端或自定义列表使用 `@tanstack/react-virtual`。
- 保留 ECharts，用统一 `ChartFrame` 封装，不强行替换全部图表。
- 建立 `src/ui` 设计系统层，禁止业务页面继续直接手写基础按钮、弹窗、表单、空态、加载态。

## 2. UI 组件库选型

### 2.1 PC 端最终选型

首选：Ant Design 6

适配原因：

- 企业级中后台场景成熟，适合交易工作台、策略设置、榜单表格、模拟盘、配置页。
- 官方支持 React、TypeScript、Vite、国际化。
- 组件覆盖完整：Layout、Menu、Table、Form、Modal、Drawer、Tabs、Segmented、Statistic、Tag、Badge、Alert、Result、Skeleton、Tooltip、Dropdown、DatePicker、InputNumber。
- 与 Ant Design Charts、ProComponents、Ant Design Mobile 生态一致。
- 当前官方版本 `antd@6.4.3` peer dependency 为 React `>=18.0.0`，与当前 React 18.3.1 匹配。

建议依赖：

```bash
cd frontend
npm install antd @ant-design/icons
```

建议按需补充：

```bash
npm install @ant-design/pro-components
```

ProComponents 使用边界：

- 可以用于设置页、策略治理页、回测任务列表、模拟交易流水等表格/表单密集场景。
- 不应用于 App 移动端。
- 不应用于需要高度定制的 K 线、分时、机甲指挥舱等品牌化区域。

备选但不采用：

- Arco Design：React 企业组件成熟，但移动端生态与本项目 App 统一性弱。
- TDesign React：腾讯生态完整，但当前项目更适合 Ant Design + antd-mobile 统一 PC/App 设计语言。
- shadcn/ui：视觉可塑性强，但基础组件需要在项目内维护源码，不符合“优先复用成熟组件库、降低维护成本”的目标。

### 2.2 移动端最终选型

首选：antd-mobile 5

适配原因：

- 专注移动 Web / WebView，适合 Capacitor App。
- 覆盖移动端高频组件：NavBar、TabBar、PullToRefresh、InfiniteScroll、List、Popup、Dialog、Form、Input、Stepper、Toast、SafeArea、Skeleton、SwipeAction。
- 与 Ant Design PC 生态保持一致。
- 当前官方包 `antd-mobile@5.42.3` 支持 React 16/17/18/19，兼容当前项目。

建议依赖：

```bash
cd frontend
npm install antd-mobile
```

移动端禁止继续大面积手写：

- Sheet / Popup
- Toast
- Dialog
- Input / Form
- TabBar
- List
- Pull refresh
- Skeleton
- Stepper

允许保留少量自定义：

- 股票信号卡片
- 机甲头像与交易动画
- 分时/K 线图表容器
- 金融行情价格涨跌颜色

### 2.3 数据状态与性能库

服务端状态：TanStack Query 5

用途：

- 替换大量手工 loading、重复请求、局部缓存、手工刷新。
- 管理 staleTime、refetchInterval、retry、mutation invalidation。
- 持仓新增/编辑可做 optimistic update，解决“保存慢”的感知问题。
- 行情、榜单、持仓、设置、模拟盘统一 query key。

建议依赖：

```bash
cd frontend
npm install @tanstack/react-query
```

虚拟列表：TanStack Virtual

用途：

- 全策略榜单、候选池、回测记录、交易流水、信号日志超过 80 行时启用。
- 移动端长列表避免一次性渲染全部卡片。

建议依赖：

```bash
cd frontend
npm install @tanstack/react-virtual
```

路由：React Router 7

用途：

- 替代 `page` state + `window.history` 手写路由。
- 支持嵌套路由、权限路由、错误页、懒加载、路由级 Suspense。
- Web 和 Native 可分别使用 BrowserRouter / MemoryRouter。

建议依赖：

```bash
cd frontend
npm install react-router
```

## 3. 最终前端架构方案

### 3.1 目标目录结构

```text
frontend/src
├── app
│   ├── AppProviders.tsx
│   ├── WebApp.tsx
│   ├── NativeApp.tsx
│   ├── router
│   │   ├── webRoutes.tsx
│   │   ├── nativeRoutes.tsx
│   │   └── routeGuards.tsx
│   └── query
│       ├── queryClient.ts
│       └── queryKeys.ts
├── api
│   ├── transport.ts
│   ├── authApi.ts
│   ├── monitorApi.ts
│   ├── playbookApi.ts
│   ├── holdingsApi.ts
│   ├── paperApi.ts
│   └── settingsApi.ts
	├── ui
	│   ├── theme
	│   │   └── antdTheme.ts
│   ├── layout
│   │   ├── WorkspaceShell.tsx
│   │   ├── MobileShell.tsx
│   │   └── PageHeader.tsx
│   ├── feedback
│   │   ├── EmptyState.tsx
│   │   ├── ErrorState.tsx
│   │   ├── LoadingState.tsx
│   │   └── ResultPage.tsx
│   ├── data
│   │   ├── DataTable.tsx
│   │   ├── VirtualList.tsx
│   │   ├── MetricStrip.tsx
│   │   └── StockIdentity.tsx
│   ├── forms
│   │   ├── NumberField.tsx
│   │   ├── SymbolSearchField.tsx
│   │   └── ConfirmAction.tsx
│   └── charts
│       ├── ChartFrame.tsx
│       ├── MiniKline.tsx
│       └── Sparkline.tsx
├── features
│   ├── auth
│   ├── monitor
│   ├── playbook
│   ├── holdings
│   ├── paper
│   ├── strategy
│   ├── backtest
│   ├── analysis
│   ├── settings
│   └── market-emotion
├── mobile
│   ├── monitor
│   ├── playbook
│   ├── holdings
│   └── shared
├── types
└── utils
```

### 3.2 模块边界

`app`：

- 只放应用装配、Provider、Router、全局错误边界。
- 不写业务 UI。

`api`：

- 只放请求函数、DTO 类型转换、错误标准化。
- `api/base.ts` 中认证、刷新 token、离线兜底可保留，但命名为 `transport.ts`。
- 禁止业务组件直接拼 URL。

`ui`：

- 只放跨业务可复用组件。
- 基础组件必须优先包 Ant Design / antd-mobile，不再重复造按钮、弹窗、输入框。
- 允许封装金融业务通用 UI，例如 `StockIdentity`、`PriceText`、`SignalBadge`、`MetricStrip`。

`features`：

- 每个业务模块独立维护 `api.ts`、`queries.ts`、`components/`、`pages/`。
- 禁止跨 feature 直接引用内部组件；需要复用则上移到 `ui` 或 `shared domain`。

`mobile`：

- 只保留 App 端特有的页面组合和小屏交互。
- 数据请求复用 `api` 和 `features/*/queries.ts`。

### 3.3 不再保留的旧模式

重构完成后应删除或停止新增：

- `workspaceConstants.ts` 中的手写页面路由状态。
- 手写通用 Button、Modal、Toast、Sheet、FormField。
- 业务页面直接维护多个 loading key。
- 页面内直接调用 `api.xxx` 并手工控制缓存。
- App 端重复实现 Web 已有的策略/持仓判断逻辑。

## 4. 统一视觉设计体系

### 4.1 视觉方向

视觉定位：专业、冷静、高信息密度、金融终端感，但不做廉价深色大屏。

关键词：

- 金融终端
- 高可读
- 紧凑
- 风险明确
- 数据可信
- 操作克制

### 4.2 全局配色

基础色：

- Brand Navy：`#0B1F3A`
- Brand Deep：`#071426`
- Brand Gold：`#CFA15A`
- Background：`#F4F6FA`
- Surface：`#FFFFFF`
- Surface Muted：`#F8FAFC`
- Border：`#E2E8F0`
- Text Primary：`#102033`
- Text Secondary：`#64748B`
- Text Tertiary：`#94A3B8`

A 股行情语义：

- Price Up / Red：`#D92D20`
- Price Down / Green：`#08875D`
- Flat：`#334155`
- Warning：`#B7791F`
- Blocked / Danger：`#B42318`
- Info Blue：`#2563EB`

注意：

- A 股中红色代表上涨，绿色代表下跌，所有 PC/App 必须统一。
- 风险、错误、上涨不能都用同一种红色，需要用语义规则区分。

### 4.3 字体与数字

正文：

中文字体建议使用系统中文字体栈。

数字：

数字字体建议使用等宽或表格数字字体，保证价格与金额便于纵向比较。

字号层级：

- Web 页面标题：24 / 28
- Web 区块标题：18 / 22
- Web 表格正文：13 / 20
- Web 辅助说明：12 / 18
- App 页面标题：20 / 24
- App 卡片标题：15 / 20
- App 数字价格：18 / 22
- App 辅助说明：11 / 16

### 4.4 间距、圆角、阴影

采用 4px 基准，8px 网格。

- 页面边距 Web：24px
- 页面边距 App：12px
- 模块间距 Web：16px / 24px
- 模块间距 App：8px / 12px
- 卡片圆角 Web：12px
- 卡片圆角 App：14px
- 表单控件高度 Web：32px / 40px
- 移动端点击区域：不低于 44px
- 阴影只用于浮层、Drawer、顶部悬浮导航，不用于普通数据卡片堆叠。

### 4.5 图标规范

- PC 使用 `@ant-design/icons`。
- App 优先使用 `antd-mobile` 内置图标或统一 SVG Icon wrapper。
- 禁止页面内散落 Unicode 图标、emoji、临时字符图标。
- 图标只承担识别功能，不做装饰堆砌。

### 4.6 通用状态标准

所有页面必须统一具备：

- Loading：Skeleton 优先，短操作用 Spin。
- Empty：说明无数据原因 + 一个主操作。
- Error：展示可读错误 + 重试按钮 + 诊断 ID 或请求时间。
- Offline：App 显示最近缓存时间和重新连接提示。
- No Permission：说明缺少权限，不展示空白页。
- Stale Data：行情/榜单数据过期时显示更新时间和降级提示。

## 5. 页面级重构方案

### 5.1 Web 工作台 Shell

目标：

- 从“页面堆叠”改为“专业交易工作台”。
- 左侧固定导航，顶部状态栏，内容区按业务模块展示。

推荐组件：

- `Layout`
- `Menu`
- `Breadcrumb`
- `Dropdown`
- `Badge`
- `Button`
- `Typography`
- `App`
- `ConfigProvider`

导航结构：

- 实时监控
- 市场情绪
- 选股宝典
- 持仓/模拟交易
- 策略验证
- 回测研究
- 个股分析
- 系统设置

顶部状态栏：

- 用户账号
- 行情刷新状态
- 数据源质量
- 当前交易时段
- 全局搜索 / Command Palette
- 通知与风险提示

验收标准：

- 页面切换不刷新整页。
- 当前页在左侧导航和 URL 中一致。
- 任一页面请求失败不影响 Shell。

### 5.2 实时监控页

当前问题：

- 卡片和状态信息自写，视觉密度不稳定。
- 添加、编辑、移除持仓动作层级不清。
- 行情刷新、信号提示、数据过期状态不统一。

重构方案：

- 顶部：市场总览 `MetricStrip`，展示指数、涨跌停、板块热度、更新时间。
- 主区：持仓/自选股票列表，PC 使用 `Table` 或 `List + Card`，App 使用紧凑 `List`。
- 右侧：当前选中股票详情 Drawer，展示 T 信号、买入区间、止损、失效条件。
- 操作：新增持仓、编辑持仓、移除持仓统一用 Modal/Drawer。
- 信号：用 `Badge`、`Tag`、`Alert`，不要用大段文字。

推荐组件：

- PC：`Table`、`Drawer`、`Modal`、`Form`、`InputNumber`、`Popconfirm`、`Tag`、`Alert`、`Statistic`
- App：`List`、`SwipeAction`、`Popup`、`Dialog`、`Form`、`Stepper`、`Toast`、`PullToRefresh`

关键交互：

- 新增持仓只填股票代码，名称和最新价由后端/搜索接口补齐。
- 编辑数量必须使用 Stepper，按 100 股递增/递减。
- 删除必须二次确认。
- 做 T 信号出现时：顶部 3 秒 Toast + 对应股票卡片呼吸高亮，直到价格离开买入区间或信号失效。

### 5.3 选股宝典页

当前问题：

- 策略标签、榜单、买点、止损、评分、已买入动作混在一起。
- Web/App 榜单一致性容易被前端筛选逻辑影响。

重构方案：

- 所有榜单数据必须来自后端统一接口，不允许前端自行重算策略排名。
- 策略筛选用 `Tabs` 或 `Segmented`。
- PC 使用 ProTable 展示全策略优先级榜。
- App 卡片压缩为三行：
  - 第一行：名称 + 代码 + 实时价 + 评分 + 策略简称
  - 第二行：买点 + 止损 + 买入信号
  - 第三行：已买入 / 加入持仓 / 查看详情
- 股票详情用 Drawer/Popup 展示，不挤占列表空间。

推荐组件：

- PC：`Tabs`、`Segmented`、`Table`、`Drawer`、`Tag`、`Tooltip`
- App：`Tabs`、`List`、`Popup`、`PullToRefresh`、`InfiniteScroll`

验收标准：

- 同一账号、同一后端、同一策略下，Web/App 榜单顺序一致。
- 策略筛选只改变后端请求参数，不在前端重排生产榜单。
- 12 条候选列表滚动流畅，无文字重叠。

### 5.4 持仓与模拟交易页

当前问题：

- 持仓、模拟资产、交易动作、流水、做 T 信号容易混在一起。
- 保存持仓感知慢。

重构方案：

- PC 分为四个 Tab：
  - 持仓
  - 今日信号
  - 模拟委托
  - 交易流水
- App 只保留高频能力：
  - 持仓列表
  - 编辑持仓
  - 做 T 信号提示
- 保存持仓使用 TanStack Query mutation + optimistic update。
- 模拟交易动作必须明确“模拟”，不可与真实交易混淆。

推荐组件：

- PC：`Tabs`、`Table`、`Statistic`、`Modal`、`Form`、`InputNumber`、`Timeline`
- App：`List`、`SwipeAction`、`Popup`、`Stepper`、`Dialog`

验收标准：

- 保存持仓后列表立即更新，失败再回滚并提示。
- T+1 可用数转换逻辑只读后端结果，前端不自行推断交易制度。
- 删除持仓能立即从列表消失，失败恢复。

### 5.5 策略验证 / 回测研究页

重构方案：

- 使用 Stepper/Steps 拆分“选择策略、设置范围、运行验证、查看结果”。
- 任务状态用进度条和 SSE/轮询兜底。
- 结果页统一用 `Statistic` + `Table` + ChartFrame。
- 风险指标必须有解释：胜率、平均收益、最大回撤、止损率、样本量。

推荐组件：

- `Steps`
- `Form`
- `Progress`
- `Table`
- `Alert`
- `Collapse`
- `Result`

### 5.6 系统设置页

重构方案：

- 拆分为清晰 Tab：
  - 账号与安全
  - 数据源
  - 策略参数
  - 因子权重
  - Agent/Hermes
  - 通知
  - 运维诊断
- 所有表单统一使用 Ant Design Form / ProForm。
- 敏感字段必须使用 Password Input，默认不回显完整值。
- 保存后展示“已保存 / 重启后生效 / 保存失败”的明确状态。

### 5.7 登录页

重构方案：

- 使用 Ant Design Form。
- 保留金融品牌视觉，但避免动效与表单重叠。
- 登录、注册、记住设备、错误提示统一。
- App 登录使用 antd-mobile Form。

验收标准：

- 移动端键盘弹出不遮挡输入框和主按钮。
- 错误信息展示在表单内，不用浏览器 alert。

## 6. 交互体验全量优化

### 6.1 操作流程简化

原则：

- 每个页面只保留一个主操作。
- 高频动作直接展示，低频动作收进 Dropdown/More。
- 删除、重置、清空必须确认。
- 成功提示不超过 3 秒。
- 失败提示必须告诉用户能做什么。

示例：

- 实时监控主操作：新增持仓。
- 选股宝典主操作：加入持仓 / 已买入。
- 持仓页主操作：编辑持仓。
- 设置页主操作：保存当前 Tab。
- 回测页主操作：运行验证。

### 6.2 表单交互

标准：

- 数字输入统一 `InputNumber` / `Stepper`。
- 股票代码输入统一 `SymbolSearchField`，支持代码、名称、拼音缩写。
- 成本价保留 2 位，小数输入不自动吞掉用户正在输入的 `.`。
- 持仓数和可用数必须是 100 的倍数。
- 表单提交中禁用按钮并显示 loading。
- 保存成功后关闭弹窗，失败不关闭。

### 6.3 数据刷新

标准：

- 行情类：显示更新时间、数据源、是否过期。
- 用户手动刷新：只显示图标按钮，hover/tap 显示“刷新”。
- 自动刷新：页面级小状态，不用大 loading 遮挡页面。
- App：PullToRefresh + 顶部更新时间。

### 6.4 权限与登录态

标准：

- 未登录进入工作台：跳转登录页。
- 登录过期：清除 token，弹出“登录已过期，请重新登录”。
- 无权限：使用 Result 组件，不显示空白页。
- 管理员能力：隐藏不可用入口，而不是点进去报错。

### 6.5 移动端适配

标准：

- 底部 TabBar 高度控制在 52-58px。
- 内容区加 `SafeArea`。
- 卡片不使用过多阴影，避免小屏拥挤。
- 所有横向指标必须能在 360px 宽度下完整展示。
- 长文本用 1-2 行截断，详情进入 Popup。
- 删除/编辑用 SwipeAction 或右侧小按钮，避免卡片内部按钮过多。

## 7. 代码重构规范

### 7.1 组件封装规则

必须抽取：

- `StockIdentity`：股票名称 + 代码。
- `PriceText`：价格 + 涨跌色。
- `SignalBadge`：正 T / 反 T / 观望 / 阻断。
- `MetricStrip`：顶部指标条。
- `DataFreshness`：更新时间 + 过期状态。
- `ActionMenu`：行级更多操作。
- `ConfirmAction`：危险动作确认。
- `EmptyState` / `ErrorState` / `LoadingState`。
- `ChartFrame`：图表统一容器。

禁止：

- 页面里散写 `<button className="xxx">` 实现基础按钮。
- 页面里散写 `<input>` 实现业务表单。
- 页面里散写 Toast、Modal、Drawer。
- 同一个字段格式化在多个文件重复实现。

### 7.2 接口请求与状态管理

保留：

- `fetchWithTimeout`
- token refresh
- native http adapter
- offline cache

新增：

- `queryKeys.ts`
- `useMonitorQuery`
- `usePriorityBoardQuery`
- `useHoldingsQuery`
- `useSaveHoldingMutation`
- `useRemoveHoldingMutation`
- `usePaperSummaryQuery`
- `useSettingsQuery`

标准 query key：

```ts
export const queryKeys = {
  monitor: ["monitor"] as const,
  monitorWorkspace: (priorityLimit: number) => ["monitor", "workspace", priorityLimit] as const,
  holdings: ["holdings"] as const,
  priorityBoard: (strategy: string, limit: number) => ["playbook", "priority", strategy, limit] as const,
  paper: ["paper"] as const,
  settings: ["settings"] as const,
}
```

mutation 后必须 invalidate 相关 query：

- 新增/编辑/删除持仓：`holdings`、`monitor`、`paper`
- 策略参数变更：`priorityBoard`、`monitor`
- 设置变更：`settings`

### 7.3 文件大小约束

硬性约束：

- 页面文件建议不超过 220 行。
- 业务组件文件建议不超过 180 行。
- Hook 文件建议不超过 220 行。
- 超过上限必须拆分为组件、hook、formatter、view model。

优先拆分当前大文件：

- `frontend/src/features/trading-workspace/SettingsPage.tsx`
- `frontend/src/mobile/MobileDesignCards.tsx`
- `frontend/src/features/trading-workspace/TradingWorkspace.tsx`
- `frontend/src/mobile/MobileApp.tsx`
- `frontend/src/features/trading-workspace/MonitorPage.tsx`
- `frontend/src/features/trading-workspace/PaperDetailTabs.tsx`
- `frontend/src/features/trading-workspace/WorkspaceComponents.tsx`

## 8. 性能优化方案

### 8.1 首屏加载

措施：

- Web 按路由懒加载页面。
- Native 只打包 App 所需页面，不引入完整 Web 工作台。
- ECharts 相关组件动态 import。
- Ant Design 图标按需引入。
- `ConfigProvider`、QueryClientProvider、RouterProvider 放在顶层，避免重复创建。

验收：

- `npm run analyze` 检查 bundle。
- 首屏 chunk 不包含回测、策略医生、设置等非首屏页面。

### 8.2 数据请求

措施：

- TanStack Query 去重同一接口并发请求。
- 行情类配置 `refetchInterval`，不要组件各自 setInterval。
- 页面切换保留缓存，减少重复 loading。
- 持仓保存使用 optimistic update。
- 后端 BFF 已有的页面聚合接口优先使用，减少瀑布请求。

### 8.3 长列表

措施：

- PC 榜单和流水使用 Table pagination 或 virtual。
- App 卡片超过 80 条启用虚拟列表。
- 搜索结果分页，不一次性渲染全部。

### 8.4 资源

措施：

- 统一图标库，删除散落 SVG/字符图标。
- 图片资源压缩，App 机甲头像使用 WebP/PNG 双格式。
- 登录页动效避免大面积滤镜动画。

## 9. 实施流程与优先级

说明：这是最终架构落地，不做长期双 UI 过渡。允许在开发分支短期保留 legacy adapter，但验收前必须删除旧组件。

### P0：基础架构与设计系统

目标：

- 引入 Ant Design、antd-mobile、React Router、TanStack Query。
- 建立 `src/app`、`src/ui`、`src/features` 新结构。
- 接入全局 Theme、QueryClient、Router。

修改范围：

- `frontend/package.json`
- `frontend/src/main.tsx`
- `frontend/src/main-native.tsx`
- `frontend/src/app/**`
- `frontend/src/ui/**`

验收标准：

- `npm run build:web` 通过。
- `npm run build:native` 通过。
- 登录页、工作台 Shell、App Shell 能正常打开。
- 新增主题配置生效。

### P1：Web 核心页面重构

目标：

- 重构实时监控、选股宝典、持仓/模拟交易三大核心页面。

修改范围：

- `frontend/src/features/monitor/**`
- `frontend/src/features/playbook/**`
- `frontend/src/features/holdings/**`
- `frontend/src/features/paper/**`

验收标准：

- Web 三大页面全部使用 Ant Design 基础组件。
- Web/App 榜单数据一致。
- 持仓新增、编辑、删除、刷新全链路可用。
- 无文字重叠、无按钮挤压、无空白错误页。

### P2：App 核心页面重构

目标：

- 使用 antd-mobile 重构实时监控、持仓、选股宝典。

修改范围：

- `frontend/src/mobile/**`
- `frontend/src/ui/mobile/**`

验收标准：

- 360px 宽度下信息完整。
- 底部 TabBar 不遮挡内容。
- 新增持仓弹窗居中/Popup 规范。
- PullToRefresh 可用。
- 删除、编辑、详情、已买入按钮可用。

### P3：设置、策略、回测、分析页重构

目标：

- 统一低频但复杂的表单、任务、报表页面。

修改范围：

- `frontend/src/features/settings/**`
- `frontend/src/features/strategy/**`
- `frontend/src/features/backtest/**`
- `frontend/src/features/analysis/**`

验收标准：

- 设置页所有表单统一 Ant Design Form。
- 回测任务状态展示清晰。
- 策略结果表格可排序、可筛选、可查看详情。

### P4：删除旧代码与性能验收

目标：

- 删除旧通用组件、重复 formatter。
- 完成 bundle、E2E、UI smoke 验收。

验收标准：

- 无未使用组件和死代码。
- `npm run build:web`、`npm run build:native`、`npm test` 通过。
- UI smoke 覆盖核心页面。

## 10. 新旧兼容方式

允许保留：

- 后端接口不变。
- API DTO 类型不变。
- Native/Web 构建脚本不变。
- 认证、token refresh、offline cache 传输层不变。

不允许长期保留：

- 同一个页面同时存在新旧两套 UI。
- 新 UI 调新接口，旧 UI 调旧接口。
- 业务逻辑在新旧 UI 中重复实现。

开发期兼容策略：

- 每个页面按模块替换，替换完成后删除该页面旧组件。
- 旧数据 hook 可短期包成 Query 的 `queryFn`，但最终迁移到 `features/*/queries.ts`。
- 旧 formatter 如果有复用价值，迁移到 `ui` 或 `utils` 后删除原文件。

## 11. 测试验收标准

### 11.1 自动化测试

必须通过：

```bash
cd frontend
npm run build:web
npm run build:native
npm test
```

建议新增：

```bash
npm install -D @axe-core/playwright
```

覆盖：

- 登录/退出
- 实时监控新增持仓
- 编辑持仓数量和成本
- 删除持仓
- 选股宝典策略切换
- 已买入加入持仓
- 模拟交易查看持仓与流水
- 设置页保存
- 移动端 Tab 切换
- 移动端新增持仓

### 11.2 UI 验收

Web：

- 1440x900、1280x720、1024x768 三档宽度无横向溢出。
- 表格列不挤压，重要字段固定或可横向滚动。
- 所有页面都有 loading、empty、error。

App：

- 360x800、390x844、430x932 三档尺寸无重叠。
- 底部 TabBar 不遮挡内容。
- 弹窗不贴边、不超屏。
- 键盘弹出时表单主按钮可达。

### 11.3 性能验收

目标：

- 首屏不加载所有业务页面。
- 页面切换不出现长时间白屏。
- 榜单 100 条滚动流畅。
- 持仓保存感知响应小于 300ms，真实失败时回滚。
- 自动刷新不造成重复请求风暴。

验证方式：

- `npm run analyze`
- Chrome Performance 录制核心页面。
- 网络面板检查重复请求。

## 12. 给 Codex 的执行需求文档

### 12.1 角色

你是 TQuant 项目的资深前端架构师、UI 工程负责人和全栈开发。请基于当前仓库完成前端最终重构优化，目标是用成熟主流 UI 组件库重构 Web 和 App 核心页面，提升视觉质量、交互效率、代码可维护性和性能。

### 12.2 强制约束

1. 不要替换后端接口。
2. 不要大面积原生手写基础 UI 组件。
3. PC 端优先使用 Ant Design。
4. 移动端优先使用 antd-mobile。
5. 服务端状态优先使用 TanStack Query。
6. 路由使用 React Router。
7. 不采用微前端。
8. 不重写为 Next.js。
9. 不破坏现有 Web/Native 构建命令。
10. 不长期保留新旧两套 UI。
11. 单文件不得继续膨胀，页面、组件、hook 必须拆分。
12. 保留 A 股红涨绿跌语义。
13. App 端所有信息必须紧凑但完整，禁止重叠。
14. 所有删除、重置、移除类动作必须二次确认。
15. 持仓保存必须做乐观更新或明确 loading，不允许用户感知“卡死”。

### 12.3 第一批开发任务

1. 安装依赖：
   - `antd`
   - `@ant-design/icons`
   - `antd-mobile`
   - `@tanstack/react-query`
   - `@tanstack/react-virtual`
   - `react-router`

2. 新增应用基础层：
   - `frontend/src/app/AppProviders.tsx`
   - `frontend/src/app/query/queryClient.ts`
   - `frontend/src/app/query/queryKeys.ts`
   - `frontend/src/app/router/webRoutes.tsx`
   - `frontend/src/app/router/nativeRoutes.tsx`
   - `frontend/src/ui/theme/antdTheme.ts`

3. 重构入口：
   - `frontend/src/main.tsx` 使用 `AppProviders` + Web Router。
   - `frontend/src/main-native.tsx` 使用 `AppProviders` + Native Router。

4. 建立通用 UI：
   - `PageHeader`
   - `WorkspaceShell`
   - `MobileShell`
   - `EmptyState`
   - `ErrorState`
   - `LoadingState`
   - `MetricStrip`
   - `StockIdentity`
   - `PriceText`
   - `SignalBadge`
   - `ConfirmAction`
   - `ChartFrame`

5. 先重构三大核心页面：
   - Web 实时监控
   - Web 选股宝典
   - Web 持仓/模拟交易
   - App 实时监控
   - App 持仓
   - App 选股宝典

6. 删除对应旧页面组件，不保留重复实现。

### 12.4 第二批开发任务

1. 重构系统设置页。
2. 重构策略验证页。
3. 重构回测研究页。
4. 重构个股分析页。
5. 重构登录页。
6. 将旧 `requestCached` 逐步迁移为 Query 缓存。

### 12.5 验收命令

每完成一个批次必须运行：

```bash
cd frontend
npm run build:web
npm run build:native
npm test
```

如涉及后端契约：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest backend/tests -q
```

### 12.6 输出要求

每次完成后输出：

- 已重构页面
- 新增依赖
- 删除旧组件
- 仍保留的 legacy 文件和原因
- 测试结果
- 未完成风险
- 下一步建议

## 13. 参考来源

- Ant Design React 官方文档：`https://ant.design/docs/react/introduce/`
- Ant Design Mobile 官方仓库说明：`https://github.com/ant-design/ant-design-mobile`
- TanStack Query 官方文档：`https://tanstack.com/query/latest/docs/framework/react/overview`
- TanStack Virtual 官方文档：`https://tanstack.com/virtual/latest/docs/introduction`
- React Router 官方文档：`https://reactrouter.com/start/declarative/routing`
