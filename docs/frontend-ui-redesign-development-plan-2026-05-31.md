# 前端 UI 视觉重构 · 开发文档（Web 端态，非过渡）

> 范围：仅 Web（`frontend/`，AntD 6 单组件库）。native 已从 `src/` 移除，本方案不涉及。
> 目标读者：执行重构的工程师 / Agent。按 Phase 顺序逐个可独立合并的变更集推进。
> 日期：2026-05-31。

---

## 0. 先说结论

- **根因不是"某个页面丑"，而是没有设计系统**：色值/字号/间距/圆角散落在多处且互相冲突，再叠加一套偏过时的"深色终端"外壳。
- **端态目标**：建立**唯一设计 Token 源**（`tokens.ts` → antd CSS 变量 + 一份 `tokens.css`），全站组件与手写 CSS 同源；浅色为主、单一品牌交互色、行情色只用于数据；侧边栏导航；可选暗色模式。
- **决策表（已定默认，可改的只有"品牌色相"一项）**：

| 决策点 | 端态选定 | 说明 |
|---|---|---|
| 组件库 | 维持 **AntD 6**，不引入 Tailwind/无样式库 | 已深度使用，AntD 主题能力足够；引入第二套是倒退 |
| 主题机制 | **`tokens.ts` 单源 + antd `cssVar`** | 组件与手写 CSS 共用 `--ant-*`，根除"对不上" |
| 风格 | 浅色为主，**品牌锚定深蓝 ink + 交互蓝**，金色降级为点睛 | 保留"维斯量化"既有识别度，去多色乱斗 |
| 行情色 | **红涨绿跌（A 股惯例）保留**，仅用于数据 | 不再用于外壳/装饰 |
| 导航 | **左侧可折叠侧边栏** | 7 个一级页 + 后续扩展，横排会越来越挤 |
| 仪式感（红运/抽奖） | 保留但**收进用户菜单**，移出一级导航 | 不抢主视觉 |
| 暗色模式 | Phase 5 落地（单源后近乎"再给一套值"） | 量化工具刚需 |

---

## 1. 现状审计（基于最新代码，2026-05-31 实测）

| 维度 | 实测 | 问题 |
|---|---|---|
| Token 源 | `frontend/src/styles/workspace/workspace.css` 的 `:root`（**生效**）+ `frontend/src/ui/theme/antdTheme.ts`（**生效**）+ `frontend/src/styles/foundation/tokens.css`（**未被任何文件 import，死文件**） | 两套生效值冲突，一套死值误导 |
| 主色冲突 | CSS `--accent: #d6a55c`（金） vs antd `colorPrimary: #0B1F3A`（藏青） | 金/藏青混用，无单一主色 |
| 背景/文字 | CSS `--bg: #eef2f7`、`--text: #162235` vs antd `colorBgLayout: #F4F6FA`、`colorText: #102033` | 组件与手写 CSS 差一点点 → 脏感 |
| 字号 | live 基准 **13px**；内联 `fontSize:11` ×103、`:12` ×72、`:10` ×41、`:9` ×1 | 满屏 10–11px，拥挤廉价 |
| 内联样式 | **44** 个文件用 `CSSProperties` 常量、**182** 处 `style={{}}` | 每个组件各写各的硬编码，必然不一致 |
| 外壳 | `workspaceShellStyles.ts` 顶栏 `linear-gradient(135deg,#07111f…)` + `boxShadow:0 12px 28px` + 金色选中态 | 重渐变重投影，偏过时 |
| 暗色模式 | 无（`grep prefers-color-scheme/darkAlgorithm/data-theme` 全空） | 但 `theme-color` 元标签是深色，割裂 |
| 死代码残留 | `tokens.css` 内含已卸载的 antd-mobile `--adm-*` 变量与 `.adm-*` 规则；`package.json` 残留 capacitor 依赖；`src/app/responsiveSingleCodebase.test.tsx` | native 已移除但清理未尽 |
| 文件规模 | `workspace.css` **1261 行**，超单文件阈值 | 需拆分 |
| 已有资产（复用，勿破坏） | `ui/table/DataTable.tsx`、`ui/list/VirtualCardList.tsx`、`ui/forms/{AppForm,NumberField}`、`ui/feedback/StateViews`、`ui/charts/*`、`ui/data/StockIdentity`、`ui/realtime/LiveCell` | 视觉重构只换皮，不动虚拟化/渲染隔离架构 |

> 一级页面（真实路由，redirect 不计）：`monitor / analysis / playbook / strategy-tracking / backtest / paper / settings`。

---

## 2. 设计原则（端态）

1. **单一真相源**：任何颜色/字号/间距/圆角/阴影/动效只能来自 `tokens.ts`，CSS 只引用变量，TSX 不出现裸 hex / 裸 px。
2. **克制配色**：中性底 + 单一品牌交互色；**行情色（红涨绿跌）只用于数字与图表**，绝不用于外壳/导航/装饰。底越素，涨跌越跳。
3. **可读优先**：正文下限 14px，10–11px 仅留给真·元信息；所有数字 `tabular-nums` 对齐。
4. **层级清晰**：用阴影/留白表达层级，而非渐变/重边框；圆角收敛 2–3 档。
5. **不破坏既有架构**：表格走 `DataTable`、长列表走虚拟化、渲染隔离规则不变——本次只换视觉皮肤。
6. **护栏固化端态**：用脚本守卫禁止回退到硬编码样式。

---

## 3. 设计 Token 规范（核心）

### 3.1 架构与数据流

```
frontend/src/ui/theme/tokens.ts        ← 唯一数值源（TS 常量）
        │
        ├─► antdTheme.ts                 ← 从 tokens 取值，喂 ConfigProvider（开 cssVar）
        │        └─► antd 运行时输出 --ant-color-* 等 CSS 变量
        │
        └─► foundation/tokens.css        ← 只定义 antd 没有的扩展变量
                 （间距/字号阶梯/行情色/阴影/动效/z-index）
                 其余一律引用 --ant-*
```

- `tokens.ts` 是 TS/JS 唯一源；antd 负责把"组件相关"那半输出成 `--ant-*` CSS 变量；`tokens.css` 只补"扩展"那半。**两半都以 `tokens.ts` 为准**（`tokens.css` 由 `tokens.ts` 派生或人工保持一致，见 §4.1 护栏）。
- 删除 / 改造 `workspace.css` 的 `:root`，删除死文件 `foundation/tokens.css` 旧内容（重写为派生变量）。

### 3.2 颜色

**中性（浅色）**

| 变量 | 值 | 用途 |
|---|---|---|
| `--bg-base` | `#F4F6FA` | 应用底（对齐 antd colorBgLayout） |
| `--bg-elevated` | `#FFFFFF` | 卡片/面板/弹层 |
| `--bg-subtle` | `#EEF1F6` | inset / hover / 斑马行 |
| `--border` | `#E2E8F0` | 常规描边（对齐 antd colorBorder） |
| `--border-strong` | `#CBD5E1` | 强调描边/分隔 |
| `--text-1` | `#0F1B2D` | 主文 |
| `--text-2` | `#5A6A7E` | 次要 |
| `--text-3` | `#94A3B8` | 元信息/占位/坐标轴 |

**品牌（锚定既有识别度，消解金/藏青混用）**

| 变量 | 值 | 用途 |
|---|---|---|
| `--brand-ink` | `#0B1F3A` | 品牌深色：侧栏底、品牌区、深色块 |
| `--brand` | `#2563EB` | **唯一交互色**：主按钮、选中、链接、聚焦（= antd colorPrimary） |
| `--brand-hover` | `#1D4ED8` | hover/active |
| `--brand-soft` | `rgba(37,99,235,.10)` | 选中底、标签底 |
| `--accent-gold` | `#C8922F` | **降级**：仅 AI 洞察/仪式感等点睛，禁止做主色 |

> 关键变更：antd `colorPrimary` 由藏青 `#0B1F3A` 改为蓝 `#2563EB`（主按钮变蓝，更现代）；藏青转为 `--brand-ink` 仅用于侧栏/品牌面。

**行情（仅用于数据，红涨绿跌，保留既有色相）**

| 变量 | 值 | 用途 |
|---|---|---|
| `--mkt-up` | `#C62828` | 涨（红） |
| `--mkt-down` | `#1F8B4C` | 跌（绿） |
| `--mkt-flat` | `#5A6A7E` | 平 |
| `--mkt-up-soft` | `rgba(198,40,40,.10)` | 涨幅淡底/标签 |
| `--mkt-down-soft` | `rgba(31,139,76,.10)` | 跌幅淡底/标签 |

**反馈（UI 状态，与行情解耦；沿用现值减少 churn）**

| 变量 | 值 | antd 映射 |
|---|---|---|
| `--success` | `#08875D` | colorSuccess |
| `--warning` | `#B7791F` | colorWarning |
| `--error` | `#B42318` | colorError |
| `--info` | `#2563EB` | colorInfo（= brand） |

> 说明：`--error` 与 `--mkt-up` 同属红系可接受（不会同元素共现）；`--success` 用青绿、与"跌=绿"语义不同上下文，可接受。

### 3.3 字号阶梯（下限 10 → 12，基准 13 → 14）

| 变量 | 值 | 用途 |
|---|---|---|
| `--fs-micro` | `12px` | 元信息（下限，禁止再小） |
| `--fs-sm` | `13px` | 次要正文/表格内 |
| `--fs-base` | `14px` | 正文基准（`html`/`body`） |
| `--fs-md` | `16px` | 小标题 |
| `--fs-lg` | `20px` | 区块标题 |
| `--fs-xl` | `24px` | 页面标题 |
| `--lh-tight` | `1.3` | 数据/紧凑 |
| `--lh-base` | `1.5` | 正文/阅读 |

- 字重仅 `400/500/600/700`，**废弃现 chip 的 800/900**。
- 数字统一 `font-variant-numeric: tabular-nums`（提供 `.num` 工具类与 `PriceText` 原语，见 §5）。

### 3.4 间距（4px 栅格）

| 变量 | 值 | | 变量 | 值 |
|---|---|---|---|---|
| `--sp-1` | `4px` | | `--sp-4` | `16px`（卡片默认内边距） |
| `--sp-2` | `8px` | | `--sp-5` | `24px`（区块/内容 gutter） |
| `--sp-3` | `12px` | | `--sp-6` | `32px` |
| | | | `--sp-7` | `48px` |

### 3.5 圆角（5 种 → 3 种）

| 变量 | 值 | 用途 |
|---|---|---|
| `--radius-sm` | `6px` | 按钮/输入/控件 |
| `--radius-md` | `10px` | 卡片/面板/下拉 |
| `--radius-lg` | `14px` | 弹窗 |
| `--radius-pill` | `999px` | 胶囊标签 |

### 3.6 阴影与动效

| 变量 | 值 | 用途 |
|---|---|---|
| `--shadow-1` | `0 1px 2px rgba(16,27,45,.06)` | 卡片 |
| `--shadow-2` | `0 4px 12px rgba(16,27,45,.08)` | 下拉/气泡 |
| `--shadow-3` | `0 12px 32px rgba(16,27,45,.12)` | 弹窗 |
| `--ease` | `cubic-bezier(.2,.8,.2,1)` | 标准缓动 |
| `--dur-fast` | `120ms` | 微交互 |
| `--dur-base` | `200ms` | 常规 |

> 删除顶栏 `0 12px 28px` 重投影，统一走 `--shadow-1/2/3`。

### 3.7 z-index 阶梯（消除散落 magic number）

`--z-base:0 / --z-sticky:100 / --z-dropdown:1000 / --z-modal:1100 / --z-toast:1200`

### 3.8 命名约定

- 语义命名（`--text-1`、`--mkt-up`），不用具体色名（禁止 `--gold`）。
- TSX 一律 `var(--token)`，禁止裸 hex / 裸 px（护栏强制，见 §4.1、§9）。

---

## 4. 落地改动点（按 Phase，每个 Phase 一个可独立合并的变更集）

### Phase 1 — Token 单源 + cssVar + 死代码清理 + 护栏（地基，收益最大）

**目标**：消灭多源冲突，全站同源。

**改动文件**
- 新建 `frontend/src/ui/theme/tokens.ts`：导出全部 §3 数值。
- 改 `frontend/src/ui/theme/antdTheme.ts`：`token`/`components` 从 `tokens.ts` 取值；`colorPrimary` → `--brand`(#2563EB)；圆角对齐 §3.5。
- 改 `frontend/src/app/WebUiProviders.tsx`：开启 `cssVar`。
- 重写 `frontend/src/styles/foundation/tokens.css`：仅保留 §3.3–3.7 扩展变量（删除 antd-mobile `--adm-*` 死规则），并在 `frontend/src/main.tsx` 中**导入它**（顺序：`antd reset` → `foundation/tokens.css` → `workspace.css`）。
- 改 `frontend/src/styles/workspace/workspace.css`：删除自带 `:root` 颜色/字号块，全部改引用变量。
- 清理：移除 `package.json` 中 capacitor 依赖与 `src/app/responsiveSingleCodebase.test.tsx` 等 native 残留（确认无引用后）。

**关键骨架**
```ts
// ui/theme/tokens.ts
export const tokens = {
  color: { bgBase:"#F4F6FA", bgElevated:"#FFFFFF", border:"#E2E8F0",
    text1:"#0F1B2D", text2:"#5A6A7E", text3:"#94A3B8",
    brandInk:"#0B1F3A", brand:"#2563EB", brandHover:"#1D4ED8",
    mktUp:"#C62828", mktDown:"#1F8B4C", mktFlat:"#5A6A7E",
    success:"#08875D", warning:"#B7791F", error:"#B42318" },
  radius: { sm:6, md:10, lg:14 },
  font: { base:14, family:'"PingFang SC","Microsoft YaHei","Noto Sans SC",sans-serif' },
} as const;
```
```tsx
// app/WebUiProviders.tsx
<ConfigProvider locale={zhCN} theme={{ ...antdTheme, cssVar: true, hashed: false }}>
```

**验收**
- `grep -rn ":root" frontend/src/styles` 仅剩 `foundation/tokens.css` 一处颜色定义；`workspace.css` 无颜色 `:root`。
- `foundation/tokens.css` 已被 `main.tsx` 引用（不再是死文件）。
- antd 组件与手写 CSS 颜色一致。
- `npm run lint && npm run build:web` 通过。

---

### Phase 2 — 排版 / 间距 / 圆角统一

**目标**：把 §3.3–3.5 阶梯落到现有代码。

**改动**
- `workspaceShellStyles.ts` 及内联样式集中文件：`fontSize/padding/borderRadius` 数字 → `var(--…)`。
- 全站清除 `fontSize:10/9`（共 ~42 处）、`font-weight:700/800/900` 滥用（表头统一 600）。
- `antdTheme.ts` 的 `Table.fontSize` 13 → 用 `--fs-sm`；正文基准 14。
- 数字展示接入 `tabular-nums`。

**验收**
- 抽查 5 页无 <12px 文本；圆角仅 6/10/14；间距均为 4 的倍数。
- 新增护栏 `fontSize < 12` 报错（§9）通过。

---

### Phase 3 — 外壳与导航重做（观感拐点）

**目标**：去过时外壳，立专业骨架。

**改动文件**：`TradingWorkspaceChrome.tsx`、`Topbar.tsx`、`workspaceShellStyles.ts`（+ 新增 `AppSidebar.tsx`）。

- **左侧栏**（新增 `features/trading-workspace/AppSidebar.tsx`）：AntD `Layout.Sider` + `Menu`，图标用 `@ant-design/icons`；展开 220px / 折叠 64px；底 `--brand-ink`；选中态 `--brand-soft` 底 + `--brand` 字（去金色描边）；顶部品牌、底部用户+系统配置。
- **顶栏瘦身**：去渐变去重投影，改 `--bg-elevated` + 底部 1px `--border` + `--shadow-1`；左=页标题/面包屑，右=统一中性 chip（机会/风险/脉冲，数字+状态点）、刷新、用户菜单。
- **仪式感**：`RitualFortuneStrip / RitualLuckyDraw` 移入用户菜单或右上角独立入口。
- **内容区**：保留 `max-width≈1440` 居中，gutter 放宽到 `--sp-5`。

**验收**：首屏无深色重渐变；侧栏可折叠且键盘可达；娱乐元素不在一级视觉层；`smoke:responsive` 通过。

---

### Phase 4 — 组件原语 + 表格/表单/ECharts 统一

**目标**：用原语收编 182 处内联样式（分批，不 big-bang）。

**改动**
- 新增原语于 `frontend/src/ui/`（见 §5）：`Panel`、`SectionHeader`、`StatTile`、`PriceText`、`Chip`、`Toolbar`。
- 逐 feature 用原语替换 `style={{}}`，内联计数走棘轮护栏（§9）只降不升。
- 表格：基于现有 `ui/table/DataTable.tsx` 统一表头（600）、行高、数字右对齐 + `tabular-nums`、sticky 表头——**不改其虚拟化实现**。
- ECharts：新增 `ui/charts/echartsTheme.ts`，从 `tokens.ts` 生成主题，全站注册（§7）。

**验收**：随机 3 页卡片/表格/图表风格一致；`style={{` 计数较 Phase 4 起点基线下降 ≥60%。

---

### Phase 5 — 暗色模式

**目标**：补暗色（单源后成本低）。

**改动**
- `antdTheme.ts` 增 `theme.darkAlgorithm` 分支；`tokens.css` 增 `[data-theme="dark"]` 覆盖块（仅改扩展变量值）。
- 切换入口在用户菜单，状态存 Zustand 并持久化；首次默认跟随 `prefers-color-scheme`。
- ECharts 主题随 `data-theme` 切换。

**验收**：浅/深切换无闪烁、无对比度不足；行情红绿在深色下仍可辨。

---

## 5. 组件原语规范（`frontend/src/ui/`）

| 原语 | 文件 | API（要点） | 职责 |
|---|---|---|---|
| `Panel` | `ui/surfaces/Panel.tsx` | `title?, extra?, padding?, bordered?` | 统一卡片：`--bg-elevated`/`--radius-md`/`--shadow-1`/`--sp-4` |
| `SectionHeader` | `ui/surfaces/SectionHeader.tsx` | `title, desc?, actions?` | 区块标题，`--fs-lg`/600 |
| `StatTile` | `ui/data/StatTile.tsx` | `label, value, delta?, tone?` | KPI 卡，数字 `tabular-nums` |
| `PriceText` | `ui/data/PriceText.tsx` | `value, base?, showSign?` | **唯一**涨跌着色入口，自动套 `--mkt-*` + `tabular-nums` |
| `Chip` | `ui/data/Chip.tsx` | `tone, dot?, children` | 中性标签（替代顶栏多色 chip） |
| `Toolbar` | `ui/surfaces/Toolbar.tsx` | `left?, right?` | 页内操作条统一间距 |

> 涨跌色**只允许**经 `PriceText` / `--mkt-*` 出现；护栏禁止其它地方直接用行情色（§9）。

---

## 6. 导航与布局规范

- **断点**：`<lg(992)` 侧栏转抽屉；`xl(1200)+` 顶栏显示完整 chip。
- **侧栏**：展开 220 / 折叠 64；项 = 图标 + 文案，高 40，选中 `--brand-soft`。
- **顶栏**：高 56，sticky，`--shadow-1`。
- **内容**：居中 `min(1440px, 100vw - 侧栏)`，padding `--sp-5`。
- 焦点可见（`--brand` 2px outline），键盘可达，`aria-current` 标注当前页。

---

## 7. ECharts 主题规范

- 新增 `frontend/src/ui/charts/echartsTheme.ts`，从 `tokens.ts` 派生：
  - 轴线/刻度 `--text-3`，分割线 `--border`，文本 `--text-2`，字体同站点。
  - 涨/跌序列 `--mkt-up`/`--mkt-down`；常规序列用 `--brand` 渐变。
  - tooltip 背景 `--bg-elevated` + `--shadow-2` + `--radius-md`。
- `echarts.registerTheme("tquant", …)`，`ui/charts/*`（`MiniKline`/`ChartIsland`/`LazyKlineChart`）统一传 `theme="tquant"`。
- 暗色：导出 `tquantDark`，随 `data-theme` 切换。

---

## 8. 暗色模式规范（Phase 5 细化）

- 扩展变量在 `:root`（浅）与 `[data-theme="dark"]`（深）各一套；组件侧 antd `darkAlgorithm` 自动出 `--ant-*` 深色值。
- 深色参考：`--bg-base #0E1626 / --bg-elevated #15203450 / --border #24324A / --text-1 #E6ECF5`。
- 切换：`document.documentElement.dataset.theme = "dark" | "light"`，持久化到 store。

---

## 9. 内联样式迁移与护栏（棘轮）

**迁移策略**：先收编中枢（`workspaceShellStyles.ts`），再按 feature 逐个把 `style={{}}` 迁到原语/CSS Module/变量；每步降基线。

**扩展 `frontend/scripts/check-css-guard.mjs`（沿用现有守卫风格）**：
1. 扫描 `src/**/*.{ts,tsx}`，**禁止裸 hex**（白名单仅 `ui/theme/tokens.ts`）。
2. **禁止 `fontSize:` 字面量 < 12**。
3. **行情色相**（`#C62828`/`#1F8B4C` 等）只允许出现在 `tokens.ts` 与 `PriceText`。
4. **棘轮**：记录 `style={{` 与 `CSSProperties` 当前计数为基线（起点 182/44），CI 中只许降不许升。

```js
// check-css-guard.mjs 增量伪代码
const HEX = /#[0-9a-fA-F]{3,8}\b/;
const SMALL_FONT = /fontSize:\s*([0-9]+)/g;
// 遍历 .ts/.tsx：命中 HEX(非 tokens.ts) 或 fontSize<12 → 收集 violations
// 读取基线 json，若 style={{ 计数 > 基线 → fail
```

> 接入 `package.json` 现有 `lint` 链（`lint:state && check:refactor && check:state-separation && check:css`），零新增命令。

---

## 10. 明确不做（端态取舍）

- 不引入 Tailwind / CSS-in-JS / 第二套组件库。
- 不重写虚拟化与渲染隔离架构（`DataTable` / `VirtualCardList` / ChartIsland 保持）。
- 不改后端契约、不改路由结构、不改业务逻辑。
- 不做 native（已移除）；不追求像素级复刻任何外部产品。
- 不保留过渡期双 token：Phase 1 一次性切到单源。

---

## 11. 验收（命令分层，可回归）

| 层 | 命令 | 通过标准 |
|---|---|---|
| 静态 | `npm run lint` | 含新增 CSS 护栏全绿；内联计数 ≤ 基线 |
| 类型/构建 | `npm run build:web`（含 `tsc -b`） | 通过 |
| 单测 | `npm run test` | 通过 |
| 响应式 | `npm run smoke:responsive` | 7 页无横向溢出/错位 |
| 视觉回归 | Playwright 截图（monitor/analysis/paper 三页，重构前后比对） | 仅预期差异 |
| 体积 | `npm run analyze` | 不显著回退 |

**每 Phase 额外验收**见 §4 各节。

---

## 12. 风险与处置

| 风险 | 处置 |
|---|---|
| `cssVar` 开启后局部样式错位 | Phase 1 仅 monitor 页灰度验证后再全量；保留一次性回滚点 |
| 主色由藏青改蓝引发观感争议 | 品牌色相是唯一可调旋钮，集中在 `tokens.ts` 一处，改动成本 1 行 |
| 内联迁移量大（182 处） | 棘轮护栏 + 分 feature 推进，不阻塞主线 |
| `workspace.css` 1261 行超阈值 | 拆为 `base/components/<feature>` 或迁 CSS Module，纳入 Phase 2/4 |
| 行情红绿被误用到外壳 | 护栏限制行情色相只在 `tokens.ts`/`PriceText` |

---

## 13. 落地顺序与里程碑

| Phase | 内容 | 风险 | 粗估 | 产出 |
|---|---|---|---|---|
| 1 | Token 单源 + cssVar + 清死代码 + 护栏 | 低 | 1–2d | 可独立合并 PR |
| 2 | 字号/间距/圆角统一 | 低 | 1d | PR |
| 3 | 侧边栏 + 顶栏重做 | 中 | 2–3d | PR |
| 4 | 原语 + 表格/表单/ECharts | 中 | 3–5d（分批） | 多 PR |
| 5 | 暗色模式 | 低 | 1d | PR |

**试点页**：`features/monitor/MonitorPage.tsx`（最大最核心），先跑 Phase 1+2+部分 3 验证方向。
**分支/提交**：遵循 `docs/engineering-conventions.md` §6.1。

---

## 14. 一句话总结

先把"颜色/字号/间距/圆角"收敛到 `tokens.ts` 单一真相源并开 antd `cssVar`，再用侧边栏 + 素净顶栏 + 一套组件原语换皮，行情红绿只留给数据——丑的根因（无设计系统）即根除，且用护栏锁死不回退。

---

## 附录 A · Token 速查

```
中性  --bg-base #F4F6FA  --bg-elevated #FFF  --bg-subtle #EEF1F6
      --border #E2E8F0   --border-strong #CBD5E1
      --text-1 #0F1B2D   --text-2 #5A6A7E    --text-3 #94A3B8
品牌  --brand-ink #0B1F3A  --brand #2563EB  --brand-hover #1D4ED8
      --brand-soft rgba(37,99,235,.10)  --accent-gold #C8922F(点睛)
行情  --mkt-up #C62828  --mkt-down #1F8B4C  --mkt-flat #5A6A7E (仅数据)
反馈  --success #08875D  --warning #B7791F  --error #B42318  --info #2563EB
字号  12/13/14/16/20/24   行高 1.3 / 1.5   数字 tabular-nums   字重 400-700
间距  4/8/12/16/24/32/48   圆角 6/10/14/pill   阴影 1/2/3
```

## 附录 B · Do / Don't

| Do | Don't |
|---|---|
| `var(--brand)` / `var(--sp-4)` | 裸 `#2563EB` / `padding:16` |
| 涨跌经 `PriceText` / `--mkt-*` | 行情色用于按钮/边框/背景 |
| 正文 ≥14、元信息 ≥12 | `fontSize:10/11` |
| 字重 400–700 | `fontWeight:800/900` |
| 圆角 6/10/14 | 8/9/12 混用 |
| `--shadow-1/2/3` | `0 12px 28px` 自定义重投影 |
| 表格走 `DataTable` 换皮 | 重写虚拟化 |
