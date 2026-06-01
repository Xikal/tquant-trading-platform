# 系统设置页 · 重构方案（美观整洁）

- 状态：重构方案 / 待评审（**仅方案，未改代码**）
- 适用范围：`frontend/src/features/settings/*`
- 最后核验日期：2026-06-01
- 关联：设计 token/原语见 `docs/frontend-ui-redesign-development-plan-2026-05-31.md`；数据中心见 `docs/data-management-console-development-plan-2026-06-01.md`
- 后续动作：按 §7 分批；只动展示层与布局，不改保存逻辑与接口

---

## 0. 先说结论
设置页**已经是 Tab 结构**（账户 / 交易参数 / 大模型与因子 / 数据库与诊断 / 策略治理），不是杂乱无章。但"不美观"的根在 5 点：
1. **硬编码颜色 + 内联字号**，和已统一的设计 token 脱节（横幅/Section/admin 金底/文字色全是写死的 hex）。
2. **卡中卡双层盒**：`SettingsSection` 带边框底色，里面再套 `SettingCard` → 双重边框背景，乱。
3. **表单全宽稀疏**：无内容最大宽度，字段 `auto-fit` 摊满整屏；Section 内又多列 `auto-fit`，大表格和小表单并排参差。
4. **管理令牌埋在「大模型」卡**，却拦着所有 admin 保存（风控/数据/因子）→ 跨 Tab 看不见却保存失败。
5. **和「数据中心」重复**：数据质量、ETF 池两处都在。

**重构目标**：左侧分区导航 + 右侧定宽内容窗格的**经典设置页布局**；卡片节奏统一、全量 token 化、管理令牌做成常驻门、去掉与数据中心的重复。

---

## 1. 现状结构与问题（实测，带证据）
**结构**（`SettingsPage.tsx`）：hero(`WorkspacePageIntro`) + 未保存横幅 → `SettingsPageTabs`(card 型 Tab) → 每个 Tab 一个 `SettingsSection`(带框盒) 内含多张 `SettingCard`。

| 问题 | 证据 |
|---|---|
| 横幅硬编码色 | `SettingsPage.tsx` `SETTINGS_UNSAVED_BANNER_STYLE` `#f3d08b/#fff8e6/#7c4a03` + `fontSize:12` |
| Section 硬编码 + 金底 | `SettingsSection.tsx` 边框 `rgba(148,163,184,.22)`、底 `rgba(248,250,252,.76)`、admin `#fff8e8`、文字 `#0f172a/#64748b`、`fontSize:12/13` |
| Tab 内联字号 | `SettingsPageTabs.tsx` `fontSize:13` |
| 卡中卡 | Section 盒 + 内部 SettingCard 双层边框 |
| 表单全宽稀疏 | `SETTINGS_FORM_GRID_STYLE` `repeat(auto-fit, minmax(180px,1fr))` + Section `minmax(320px,1fr)` 无内容最大宽度 |
| 管理令牌埋藏 | 仅 `llm` Tab 的「大模型配置」卡里有「管理令牌」输入，但 `adminTokenError` 拦截 risk/data/factor 保存 |
| 与数据中心重复 | `DataQualityPanel`（data Tab）、`EtfUniverseAdminCard`（trading Tab）已在 `/data` 数据中心 |
| 单 Tab 过载 | data Tab 5 张卡（数据源/最新数据/数据质量/运行诊断/快照） |
| hero 冗余 pill | "当前页签"pill 与 Tab 选中态重复 |

---

## 2. 新布局：左分区导航 + 右定宽内容窗格

### 2.1 现状
```
hero + 未保存横幅
[card 型横向 Tab：账户 | 交易参数 | 大模型与因子 | 数据库与诊断 | 策略治理]
└ 选中 Tab → 带框 Section 盒 → auto-fit 多列卡片（参差）
```
### 2.2 新结构（桌面 ≥lg）
```
┌ 顶部条：系统设置  ·  [未保存 N 项｜全部保存]（粘性）───────────────┐
├──────────────┬───────────────────────────────────────────────────┤
│ 左侧分区导航   │  右侧内容窗格（定宽 ~760–880px，单列卡片）           │
│ （粘性竖排）   │  ┌ 分区标题 + 一句话说明 ─────────────────────────┐ │
│  账户与安全 •  │  │  SettingCard（标题/说明/表单/底部保存条）        │ │
│  交易偏好      │  │  SettingCard …                                 │ │
│ ─ 管理员 ─     │  └────────────────────────────────────────────────┘ │
│  模型与因子    │                                                       │
│  数据与运行    │                                                       │
│  策略治理      │                                                       │
│  诊断与审计    │                                                       │
└──────────────┴───────────────────────────────────────────────────┘
管理员区顶部：⚠「管理令牌」常驻输入（未填→该区所有保存禁用 + 一句话）
```
**要点**
- **横向 card Tab → 左侧竖排分区导航**：5+ 分区竖排更清爽、可加图标、带未保存小圆点；移动端折叠成顶部下拉/Segmented。
- **右侧内容定宽单列**：表单不再摊满整屏，阅读舒适；字段网格最多 2 列。
- **拆掉 Section 外层框盒**：分区标题改"标题 + 说明"文字行，下面直接是单列卡片，**消除卡中卡**。
- **未保存条 + 全部保存做成顶部粘性**：滚动时始终可见。
- **管理员令牌门常驻**：进入任一管理员分区，顶部一条「管理令牌」输入；未填则该分区保存按钮禁用并提示，不再埋在某张卡里。

---

## 3. 信息架构（分区重排 + 去重）
| 分区（左导航） | 放哪些卡 | 变化 |
|---|---|---|
| 账户与安全 | AuthSecurityCard、RitualSettingsCard | 不变 |
| 交易偏好 | 风控参数、行业排除、模拟盘退出参数、行业 ETF 做T参数 | **移走 EtfUniverseAdminCard**（去数据中心） |
| 模型与因子（admin） | 大模型配置、因子权重、ML 参数 | **管理令牌移到分区顶部常驻门** |
| 数据与运行（admin） | 数据源配置、最新数据状态、运行快照 | **移走 DataQualityPanel**（去数据中心） |
| 诊断与审计（admin） | 运行诊断、功能开关、操作审计 | 从原 data/governance 拆出，单独成区，给重表格更多空间 |
| 策略治理（admin） | 策略治理（状态/开关） | 与诊断审计分开，避免单区过载 |

> 去重原则：数据质量、ETF 池的"家"在**数据中心**；设置页对应位置放一句「在数据中心管理 →」链接，不重复渲染。

---

## 4. 视觉与组件规范
- **统一卡片**：用 `Panel` 原语包 `SettingCard`，结构固定为「标题 + 一句话说明 + 表单体 + 底部保存条（保存按钮 + 已保存✓ + 脏标小圆点）」。
- **节奏**：卡片间距 `--sp-4`；卡内字段 `--sp-3`；右窗格上下留白 `--sp-5`。
- **字段网格**：`grid-template-columns: repeat(2, minmax(0,1fr))`（窄屏 1 列），不再 `auto-fit` 摊满。
- **全量 token 化（删硬编码）**：
  | 现写死 | 改 token |
  |---|---|
  | 横幅 `#fff8e6/#f3d08b/#7c4a03` | `background: color-mix(in srgb, var(--warning) 10%, var(--bg-elevated))`、边框 `var(--warning)`、字 `var(--warning)` |
  | Section 边框 `rgba(148,163,184,.22)` | `var(--border)` |
  | Section 底 `rgba(248,250,252,.76)` | `var(--bg-subtle)`（或去盒不要底） |
  | admin 金底 `#fff8e8` | **去金底**，改分区标题旁一个「管理员」`Chip` 标识 |
  | 文字 `#0f172a/#64748b` | `var(--text-1)/--text-2` |
  | 内联 `fontSize:12/13` | `var(--fs-micro)/--fs-sm` |
- **hero 精简**：去掉"当前页签"pill；hero 标题 + 一句话 + 关键状态（数据库/大模型已配置）即可。
- **保存交互统一**：脏标小圆点（已有 dirty 状态）、保存中 loading、已保存 3s 提示——抽到 `SettingCard` 统一处理。

---

## 5. 组件 / 文件改动点
| 文件 | 改动 |
|---|---|
| 新增 `SettingsLayout.tsx` | 左导航 + 右窗格两栏壳；粘性顶部条；移动端导航折叠 |
| 新增 `SettingsLayout.module.css` | 两栏栅格、定宽窗格、粘性、全部用 token |
| 新增 `AdminTokenGate.tsx` | 管理员分区顶部常驻令牌门（输入 + 未填提示 + 禁用联动） |
| `SettingsPage.tsx` | 用 `SettingsLayout` 替换 hero+Tab+Section 编排；删未保存横幅内联样式（移入 layout）；删 EtfUniverse/DataQuality 渲染改链接 |
| `SettingsPageTabs.tsx` | 改为左侧竖排导航（或保留并改造为 `Segmented`/`Menu`），去内联字号 |
| `SettingsSection.tsx` | **去外层框盒**：只渲染"分区标题 + 说明"，token 化；admin 用 Chip 不用金底 |
| `SettingsPagePanels.tsx` / 各 `*Card.tsx` | 统一走 `Panel`/SettingCard 规范；去硬编码 hex/内联字号（降护栏基线） |

> 全部为**布局与展示层**改动；保存逻辑（`saveSection/saveAllDirty/dirtyState`）、接口、store 字段不动。

---

## 6. 移动端
- 左导航 → 顶部 `Segmented` 或下拉选择分区；右窗格全宽单列。
- 字段网格 1 列；未保存条/令牌门粘顶。
- 重表格（诊断/审计/开关）横向可滑，不撑破。

---

## 7. 分批实施
- **P0（最见效）**：全量 token 化 + 拆卡中卡（去 Section 外框、删硬编码色/内联字号）+ hero 去冗余 pill。视觉立刻干净，且降护栏基线。
- **P1**：两栏布局（左分区导航 + 右定宽窗格）+ 管理令牌常驻门 + 未保存粘性条。
- **P2**：去重（移走 DataQuality/EtfUniverse 改链接）+ 分区重排（data 拆成"数据与运行 / 诊断与审计"）+ 移动端导航折叠。

建议先 P0（纯样式收敛，零逻辑风险）当样板。

---

## 8. 验收标准
- 页面**无硬编码 hex / 内联 `fontSize<12`**（`check:css` 棘轮通过且基线下降）。
- 无卡中卡双层边框；右窗格定宽、表单不再摊满整屏。
- 管理令牌常驻可见；未填时该分区保存禁用并有一句话提示。
- 数据质量、ETF 池不再在设置页重复渲染（改为指向数据中心链接）。
- `npm run lint` / `build:web` 通过；`smoke:responsive` 在 `/settings` 375/768/1440 视口 0 横向溢出。
- 保存/脏标/已保存交互行为与现状一致（仅外观变化）。

## 9. 边界 / 不做
- 不改保存逻辑、校验规则、接口与 store 字段。
- 不新增配置项；只重排现有项。
- 不引入新组件库；颜色/间距统一用 token。
- 重复模块只"挪家 + 链接"，不删功能。

## 10. 不改代码声明
- 本次仅输出方案文档，未修改任何代码 / 配置，未运行构建，未部署；仅新增本报告于 `docs/reports/`。
