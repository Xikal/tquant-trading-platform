# 数据中心（数据控制台）· 布局重排 + 文案直白化 方案

- 状态：优化方案 / 待评审（**仅方案，未改代码**）
- 适用范围：`frontend/src/features/data-console/*`（已实现的 `/data` 页面）
- 最后核验日期：2026-06-01
- 关联：建设计划 `docs/data-management-console-development-plan-2026-06-01.md`
- 后续动作：按 §6 分批；本方案聚焦"布局分层 + 文字说人话"，不改后端接口

---

## 0. 先说结论
现页面两大毛病，都让人看不懂：
1. **布局没有层次**：8 个面板等权平铺，还把开发编号「A/B/C…H」直接印在标题上，像一份内部文档；两个"结论性"面板（数据总览、能否交易）被拆在不同位置，重要信息不在一起。
2. **文字泄漏代码**：多处标签直接显示英文/内部代码——`red/yellow`、`degraded/stale/failed`、`fail/blocked_by_data`、`succeeded/queued`、`daily_bars`……普通用户根本看不懂。

**改造目标**：① 重排成"**能不能用 → 哪里不对 → 去更新/修复**"三段分层；② 所有状态码、英文、内部名一律换成大白话。

---

## 1. 现状问题（实测，带证据）

### 1.1 布局
| 问题 | 证据 |
|---|---|
| 8 个面板平铺、标题带字母编号 A–H | `DataConsolePage.tsx` 各 `Panel title="A 数据健康总览"… "H 实盘前数据门"` |
| 两个结论面板被拆开（A 在顶、H 在中部 grid 里） | A=L78、H=L97（和 B 同行） |
| 综合灯/阻断/缺失 在页眉 pills 和 A 面板重复显示 | 页眉 pills L63–67 vs `DataHealthOverview` 4 个 InfoPill L34–37 |
| 只读巡检（总览/源/完整度/门）与运维操作（任务/修复/单票/ETF）混排无分组 | A–H 全在一个纵向流里 |
| 管理令牌输入塞在页眉 action 角，容易忽略，却是所有操作的开关 | `Input.Password` L69 |

### 1.2 文案（"文字不清晰"的根：直接显示原始代码）
| 位置 | 现状（直接显示） | 文件 |
|---|---|---|
| 能否交易 检查项标签 | `red` / `yellow` / `green` | `TradeDataGateCard.tsx` L37 `<Tag>{item.severity}</Tag>` |
| 数据源 质量标签 | `ok / degraded / stale / failed` | `DataSourceHealthPanel.tsx` L37 `<Tag>{item.quality}</Tag>` |
| 完整度 状态标签 | `fail / blocked_by_data / unavailable / stale / ok` | `CoveragePanel.tsx` L120–123 `<Tag>{status}</Tag>` |
| 任务 状态标签 | `succeeded / failed / running / queued` | `CollectionJobsPanel.tsx` L90–93 |
| 数据集名 | `daily_bars / minute_bars / tick_trades` | `CoveragePanel` 表格、`CollectionJobsPanel` 下拉 |
| 列名 | `invalid`、`期望/实际` | `CoveragePanel.tsx` L79–82 |
| 标题 | `A 数据健康总览`…`H 实盘前数据门`（内部编号） | `DataConsolePage.tsx` |
| 术语 | 综合灯 / 探测 / 巡检 / 阻断 / 数据门 | 多处 |

---

## 2. 新布局（三段分层，before → after）

### 2.1 现状
```
页眉(标题+3 pills+令牌输入)
A 数据健康总览(full)
[B 数据源健康 | H 实盘前数据门]
C 覆盖率与新鲜度(full)
D 采集任务与调度(full)
[E 数据修复与对账 | F 单票数据巡检]
G ETF/股票池管理(full)
```
### 2.2 新结构
```
┌ 第一层 · 今日数据能不能用（结论区，合并 A + H，去重）──────────────┐
│  大状态：数据正常 / 部分偏旧 / 关键缺失（一句话）                     │
│  能否用于交易：可以 / 谨慎 / 暂停  + 不通过的检查项                    │
│  [数据集 N · 不可用 X · 待更新 Y · 待补 Z 天 · 最近检查 时间]  [刷新]   │
├ 第二层 · 日常巡检（只读，2 栏）───────────────┬───────────────────┤
│  数据来源是否正常（源列表 + 质量/延迟）        │  数据完整度（按数据集）  │
├ 第三层 · 数据维护（管理员，默认折叠）──────────┴───────────────────┤
│  ⚠ 先填「管理令牌」才能操作（明显的门，不再藏页眉）                  │
│  折叠组：① 数据更新任务  ② 数据修复  ③ 个股数据检查  ④ 交易标的范围    │
└──────────────────────────────────────────────────────────────────┘
```
**要点**
- **A + H 合并为顶部"能不能用"结论区**：用户第一眼就知道"数据正常吗、能不能交易"。删掉页眉与 A 面板重复的 pills（只保留一处）。
- **B + C 作为"日常巡检"两栏**：源是否正常、数据是否完整，看一眼即可。
- **D + E + F + G 收进"数据维护"折叠区**：都是管理员低频写操作；管理令牌升级为该区顶部明显的门（未填 → 下面全禁用 + 一句话提示）。
- 标题**全部去掉 A–H 编号**，换成大白话（见 §3.1）。

---

## 3. 文案直白化对照（全量 before → after）

### 3.1 面板 / 标题
| 现在 | 改为 |
|---|---|
| 数据控制台 | 数据中心 |
| A 数据健康总览 | 今日数据状态 |
| H 实盘前数据门 | 能否用于交易 |
| B 数据源健康 | 数据来源是否正常 |
| C 覆盖率与新鲜度 | 数据完整度 |
| D 采集任务与调度 | 数据更新任务 |
| E 数据修复与对账 | 数据修复 |
| F 单票数据巡检 | 个股数据检查 |
| G ETF / 股票池管理 | 交易标的范围（ETF / 股票池） |

### 3.2 状态码 → 中文（**代码级，建议在 `dataConsoleTypes.ts` 加共享映射函数，各 Tag 统一调用**）
```ts
// 数据集/完整度状态 status
ok→正常  stale→待更新  fail→异常  blocked_by_data→缺数据已停用  unavailable→取不到  missing→缺失  warn→注意
// 数据源质量 quality
ok/realtime→正常  degraded→质量下降  stale→偏旧  failed→不可用
// 检查项严重度 severity（能否交易/数据门）
green→通过  yellow→注意  red→不通过
// 任务状态 status
queued→排队中  running→进行中  succeeded→已完成  failed→失败
// 数据集名 dataset_key
daily_bars→日线  minute_bars→分钟线  tick_trades→逐笔成交  instruments→标的库
// 范围 scope
all→全市场  production_universe→交易标的池  watchlist→我的自选
```
> 现在这些都是 `<Tag>{原始值}</Tag>`，改为 `<Tag>{labelOf(原始值)}</Tag>`；颜色逻辑保留。

### 3.3 指标 / 列名 / 术语
| 现在 | 改为 |
|---|---|
| 综合灯 | 总体状态 |
| 阻断（X 个） | 不可用（X 个） |
| 过期（X 个） | 待更新（X 个） |
| 缺失（X 天） | 待补（X 天） |
| 探测 / 重新探测 | 检查 / 重新检查 |
| 巡检 | 检查 |
| 列「invalid」 | 异常行 |
| 列「期望 / 实际」 | 应有 / 实有 |
| 「查看阻断数据集」 | 查看不可用的数据 |
| 仅阻断 / 仅过期（筛选） | 仅看不可用 / 仅看待更新 |

### 3.4 按钮 / 提示 / 空态
| 现在 | 改为 |
|---|---|
| 标的库同步 | 更新标的库 |
| 当日收盘刷新 | 拉取今日收盘数据 |
| 区间回补 | 补历史数据 |
| 刷新任务 | 刷新 |
| 需填写管理令牌 | 先填管理令牌才能操作 |
| 所有采集、修复、回补只提交后台任务，Web 不执行重逻辑，不触发交易。 | 所有更新都交后台处理，不会动你的持仓和交易。 |
| 仅检查数据可信度，不触发交易。 | 只判断数据能不能用，不会下单。 |
| 该数据源暂时不可用，已自动切换，部分数据可能延迟 | 保留（已是大白话，✓） |
| 暂无数据质量快照 / 暂无采集任务 | 保留（✓） |

---

## 4. 组件改动点（逐文件，便于执行）
| 文件 | 改动 |
|---|---|
| `dataConsoleTypes.ts` | 新增 `statusLabel/qualityLabel/severityLabel/taskStatusLabel/datasetLabel/scopeLabel` 共享映射；`conclusionText` 已是大白话，保留 |
| `DataConsolePage.tsx` | 重排三层：合并顶部结论区（含 H）、中部巡检 2 栏、底部"数据维护"折叠（D/E/F/G）；管理令牌移到维护区顶部；删与页眉重复的 pills；所有 `Panel title` 去编号改大白话 |
| `TradeDataGateCard.tsx` | `Tag` 文案用 `severityLabel`；标题"能否用于交易" |
| `DataSourceHealthPanel.tsx` | `Tag` 用 `qualityLabel`；"重新探测"→"重新检查" |
| `CoveragePanel.tsx` | `StatusTag` 用 `statusLabel`；列名 invalid→异常行、期望/实际→应有/实有；数据集名用 `datasetLabel`；筛选项改大白话 |
| `CollectionJobsPanel.tsx` | `TaskStatusTag` 用 `taskStatusLabel`；数据集下拉用 `datasetLabel`；按钮文案改（§3.4） |
| `DataHealthOverview.tsx` | 指标文案：阻断→不可用、过期→待更新、缺失→待补；与顶部结论区合并后此组件作为结论区主体 |
| `DataConsolePage.module.css` | 基本不动（已用 token + 响应式）；维护区折叠样式可复用 `.grid` |

> 全部是**展示层文案 + JSX 重排**，不动取数逻辑、不动接口、不动 store 字段。

---

## 5. 移动端
- 三层均单列（`.grid` 已在 `<1200px` 转单列、`<576px` 行内单列，✓）。
- 顶部结论区：状态一句话 + "能否交易" + 指标 2 列。
- 维护区默认折叠，避免小屏一进来就是一堆操作表单。

---

## 6. 分批实施
- **P0（最见效，先做）**：§3.2 状态码中文映射（消灭所有裸英文 Tag）+ §3.1 标题去 A–H 编号。改动小、体感最强。
- **P1**：布局三层重排（合并 A+H 结论区、B+C 巡检、D/E/F/G 维护折叠 + 令牌门）。
- **P2**：§3.3/§3.4 指标列名、按钮、提示逐条替换；移动端复核。

---

## 7. 验收标准
- 页面**不再出现** `red/yellow/green`、`degraded/stale/failed`、`fail/blocked_by_data`、`succeeded/queued`、`daily_bars` 等原始代码（全中文）。
- 标题无 A–H 编号；进页第一屏先看到"数据能不能用 / 能不能交易"。
- 综合灯/结论只出现一处，不重复。
- 维护操作集中在折叠区，未填管理令牌时禁用并有一句话提示。
- `npm run lint` / `build:web` 通过；`smoke:responsive` 在 `/data` 375/768/1440 视口 0 横向溢出。
- 不改后端接口、不改取数逻辑、不触发交易。

## 8. 边界 / 不做
- 不改后端契约、不改采集/修复执行逻辑（仍只提交后台任务）。
- 不删任何功能模块（只是分层折叠 + 改文案）。
- 不引入新组件库；颜色/间距继续用 token（护栏不回升）。

## 9. 不改代码声明
- 本次仅输出方案文档，未修改任何代码 / 配置，未运行构建，未部署；仅新增本报告于 `docs/reports/`。
