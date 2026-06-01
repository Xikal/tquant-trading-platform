# 数据采集与管理控制台 · 前端开发文档

- 状态：开发计划 / 待评审
- 适用范围：Web 前端新增「数据」控制台页面 + 少量薄后端端点；管理（admin）能力
- 最后核验日期：2026-06-01
- 结论/执行入口：见 §0；按 §8 分 M1–M5 分批落地，每批可独立合并
- 硬边界 / 分批范围 / 验收命令 / 回退方式 / 不做什么：见 §2 / §8 / §9 / §10 / §11

---

## 0. 先说结论

- **可行性高**：后端 ~80% 端点已就绪（SLA、修复、数据源健康、标的同步、runtime-task 队列、单票查询、ETF universe 全套 CRUD）；前端已有可复用件（`dataQualityApi`、`DataQualityPanel`、`InstrumentSyncProgress`、`EtfUniverseAdminCard`、`VirtualGrid`、`isAdmin/adminToken` 门控）。本项目是**"把散件聚成一个控制台页 + 补 4 个薄端点"**，不是造新引擎（符合 `engineering-conventions §9`）。
- **最高价值模块是 H「实盘前数据门」**：数据不可信时禁止自动下单，是实盘对接的安全前置；其余 A–G 是把已有运维能力收口、提升可信度与效率。
- **重任务一律走 worker**：所有采集/修复/回补只在前端**触发 runtime-task**，由 worker 执行，前端只展示状态——延续 `DataQualityPanel`「Web 不执行修复 / analytics-worker 消费」既有约定（`§5.3`）。
- **任务进度用轮询**：前端当前未消费 SSE（仅 `useQuoteStream` 自有通道），MVP **沿用轮询** runtime-task 状态（同 `InstrumentSyncProgress` 模式），SSE 留作后续可选优化——**避免新增 SSE 管线返工**。

---

## 1. 目标与非目标

**目标**
1. 一页看清"今天数据能不能信"：覆盖率 / 新鲜度 / 缺口 / 源在线 / 复权一致。
2. 把分散的运维操作（同步、修复、回补、ETF 池管理）收口到一处，全部 admin 门控。
3. 提供"实盘前数据门"聚合判定，作为自动下单放行条件。

**非目标（防过度设计，见 §11）**
- 不做企业级数据中台（血缘 lineage、数据目录 catalog、多租户权限、可视化 ETL 编排）。
- 不在 Web 端执行任何重计算/采集/修复逻辑。
- 不替换或重写既有 provider / data_quality / runtime-task 引擎。

---

## 2. 硬边界（必须遵守）

| 边界 | 要求 | 依据 |
|---|---|---|
| 管理门控 | 同步/回补/修复/apply/rollback 等写操作必须 `isAdmin` 且携带 `X-Admin-Token`；普通用户只读或隐藏 | §6.3 |
| 重任务隔离 | Web 仅触发 runtime-task，worker 消费；**禁止 Web 新增后台 loop** | §5.3 |
| 缺数据显式 | 一律展示 `ok/stale/missing/blocked_by_data/unavailable`，**禁止造假绿灯/假分** | §6.6/§6.9 |
| 复用优先 | 复用 `dataQualityApi / VirtualGrid / SettingCard / etfUniverseAdmin / isAdmin`，不新建并行实现 | §9 |
| 文件规模 | 页面 ≤300 行、组件 ≤220 行、hook/store ≤220 行；超限先拆 | §4.1 |
| 命名落位 | 新 feature 目录 `features/data-console/`，组件 `PascalCase.tsx`，页面 `DataConsolePage.tsx`，hook `use*.ts` | §3.3 |

---

## 3. 复用清单（现有资产，精确到文件）

| 复用件 | 路径 | 用于模块 |
|---|---|---|
| 数据质量 API（sla / repairDryRun + 类型） | `frontend/src/api/dataQuality.ts` | A / C / E |
| 数据质量面板（SLA 快照 + 修复审计 表格逻辑） | `frontend/src/features/settings/DataQualityPanel.tsx` | A / C / E（抽为共享） |
| 标的同步进度条 | `frontend/src/features/monitor/InstrumentSyncProgress.tsx` | D |
| ETF universe 管理（草稿/校验/应用/回滚） | `frontend/src/features/settings/EtfUniverseAdminCard.tsx` + `frontend/src/api/etfUniverseAdmin.ts` | G |
| 虚拟表格 | `frontend/src/ui/grid/VirtualGrid.tsx`（或 `ui/table/DataTable`） | 所有表格 |
| 卡片容器/指标 | `WorkspaceComponents`（`SettingCard`/`InfoPill`）+ 新原语 `ui/surfaces/Panel` | 所有面板 |
| 管理门控 | `SettingsPage.tsx` 的 `isAdmin = roles.includes(admin)` + `adminToken` | 全页写操作 |
| 服务端状态缓存 | `state/serverState`（`useServerState`） | 全页数据 |

---

## 4. 接口契约

### 4.1 已就绪端点（直接调用）
| 能力 | 方法 路径 | 响应类型 |
|---|---|---|
| SLA 快照 + 修复审计 | `GET /data-quality/sla` | `DataQualitySlaResponse`（items[] + latest_repair_audits[] + total） |
| 修复（dry-run / 执行） | `POST /data-quality/repair` `{dataset_key, dry_run}` | `RuntimeTaskOut` |
| 数据源健康 | `GET /market/data-sources/health` | `DataSourceProbeResponse` |
| 标的库同步 | `POST /instruments/sync` / `GET /instruments/sync/status` | `InstrumentSyncStatus` |
| 任务队列 | `GET /runtime-tasks`、`GET /runtime-tasks/{id}`、`/{id}/events`、`/{id}/stream` | `RuntimeTaskOut(List)` |
| 单票巡检 | `GET /quote/{symbol}`、`/kline/{symbol}`、`/instruments/{symbol}/rules\|sector\|events` | 各自类型 |
| ETF universe 管理 | `/market/etf-universe/admin` + `validate`/`repair-draft`/`apply`/`rollback` | `EtfUniverseAdmin*` |

> 字段已知（来自 `dataQuality.ts`）：`DataQualitySnapshotItem{dataset_key, as_of_date, scope, expected_days, actual_days, missing_days, invalid_rows, duplicate_rows, stale, coverage_pct, status, blockers[], checked_at}`；`DataRepairAuditItem{repair_id, dataset_key, reason, backup_path, refetch_result, deleted_rows_count, fabricated, operator, created_at}`。

### 4.2 需新增的薄端点（4 个，后端各 ≤1 个 service+route）
| # | 方法 路径 | 入参 | 出参（建议 schema） | 用于 | 批次 |
|---|---|---|---|---|---|
| N1 | `GET /data-quality/coverage` | `dataset_key, scope` | `{dataset_key, scope, missing_symbols:[{symbol,name,missing_days}], missing_dates:[date]}` | C 钻取明细 | M3 |
| N2 | `POST /data-quality/backfill` | `{dataset_key, scope, start_date, end_date}`（admin） | `RuntimeTaskOut` | D 区间回补 | M2 |
| N3 | `GET /data-quality/trade-gate` | — | `{ok:boolean, checks:[{key,label,ok,severity,detail}]}` 聚合 freshness/gap/adjust/source | H 实盘前门 | M4 |
| N4 | （可选）源故障告警钩子 | 复用通知服务 | — | B 源失效推送（接通知功能） | M4 |

> N1 若 `sla.blockers` 已含足够明细可降级为前端展开，不必新增；以实际 `blockers` 内容为准评估。

---

## 5. 前端信息架构（详细）

### 5.1 入口 / 路由 / 门控
- **导航**：侧边栏新增一级项「数据」，图标 `DatabaseOutlined`，**仅 `isAdmin` 可见**（非管理员隐藏整页）。
- **路由**：`/data`，`lazy` 加载，错误用 `TqErrorResult` 兜底。
- **页面**：`features/data-console/DataConsolePage.tsx`（仅做布局 + 取数编排，≤300 行）。
- **写操作门**：未填 `adminToken` 时，所有"触发任务/修复/应用/回滚"按钮 `disabled` 并提示"需填写管理令牌"。

### 5.2 页面整体布局
```
┌─ DataConsolePage ───────────────────────────────────────────┐
│ A 数据健康总览（顶部横条，红绿灯 + 关键数字 + 刷新）            │
├──────────────────────────┬──────────────────────────────────┤
│ B 数据源健康             │ H 实盘前数据门（醒目，绿/黄/红）   │
├──────────────────────────┴──────────────────────────────────┤
│ C 覆盖率与新鲜度（数据集×范围 表 + 钻取）                      │
├──────────────────────────────────────────────────────────────┤
│ D 采集任务与调度（队列表 + 进度 + 触发区）                     │
├──────────────────────────┬──────────────────────────────────┤
│ E 数据修复与对账         │ F 单票数据巡检（输入代码即查）     │
├──────────────────────────┴──────────────────────────────────┤
│ G ETF / 股票池管理（折叠，admin）                             │
└──────────────────────────────────────────────────────────────┘
```
- 桌面 ≥xl 两栏，<lg 单列；区块用 `Panel` 原语，统一 `--sp-*` 间距；表格统一右对齐数字 + `tabular-nums`。
- 每个区块独立取数、独立加载/空/错误态，互不阻塞（一个源失败不拖垮整页）。

### 5.3 模块逐项详述

#### 模块 A · 数据健康总览
- **作用**：一眼回答"今天数据能不能信"。
- **布局**：顶部横条；左红绿灯（综合状态 ok/warn/blocked）+ 一句话结论；右 4 个 `InfoPill`。
- **字段/指标**：数据集总数、阻断(fail/unavailable)数、过期(stale)数、缺失合计、最近检查时间 `checked_at`。
- **数据来源**：`dataQualityApi.sla()`（已有）。综合灯 = 有 fail/blocked→红，有 stale/warn→黄，否则绿。
- **交互**：「刷新」按钮；点阻断数跳到模块 C 过滤 fail。
- **状态**：加载=骨架横条；空=「暂无数据质量快照」；错误=红字 + 重试，不影响其他模块。
- **复用**：`DataQualityPanel` 的 sla 取数逻辑抽到 `useDataQuality()` hook 共享。

#### 模块 B · 数据源健康
- **作用**：盯住易崩的免费源。
- **布局**：每个源一行（provider 名 + 状态点 + 延迟 + 最近探测时间 + 当前是否主路由）。
- **字段**：来自 `DataSourceProbeResponse`（probe 列表：provider/status/latency/reachable/checked_at；具体字段以 `schema_defs/phase4.py` 为准）。
- **数据来源**：`GET /market/data-sources/health`（已有）。
- **交互**：「重新探测」；源异常行标红 + 文案"该源不可用，已自动切换/部分数据可能缺失"。
- **告警（M4）**：源失效经 N4 接通知服务（飞书 + 后续多渠道）。
- **状态**：加载=行骨架；错误=「数据源探测失败」。

#### 模块 C · 覆盖率与新鲜度
- **作用**：缺哪些、停哪些、过期哪些（显式标记）。
- **布局**：`VirtualGrid` 表，行=数据集×范围。
- **列**：数据集(`dataset_key`+`scope`/`as_of_date` 副标) · 覆盖率(`coverage_pct`%) · 期望/实际(`expected_days`/`actual_days`) · 缺失(`missing_days`) · invalid(`invalid_rows`) · 重复(`duplicate_rows`) · 状态(`status` Tag) · 原因(`blockers` 合并)。
- **钻取**：点行展开/抽屉 → 缺失标的/日期明细（N1，或展开 `blockers`）。
- **数据来源**：`dataQualityApi.sla().items`（已有）+ N1（明细）。
- **筛选**：按状态(全部/仅阻断/仅过期)、按 scope(全市场/自选/策略池)。
- **状态**：空=「所有数据集覆盖正常」；过期行黄、阻断行红。

#### 模块 D · 采集任务与调度
- **作用**：手动补数 + 看进度。
- **布局**：上=触发区（按钮组），下=任务队列表 + 运行中进度条。
- **触发区（admin）**：标的库同步(`/instruments/sync`)、当日收盘刷新(runtime-task)、**按区间回补**(N2：数据集 + 起止日期 + 范围)。
- **队列列**：任务类型 · 状态(queued/running/succeeded/failed) · 进度% · 耗时 · 触发时间 · 失败原因。
- **进度**：复用 `InstrumentSyncProgress` 进度条；运行中任务**轮询** `GET /runtime-tasks/{id}`（2–3s，页面可见时；不可见暂停）。
- **数据来源**：`GET /runtime-tasks`（已有）、`/instruments/sync`、N2。
- **状态**：空=「暂无采集任务」；失败行红 + 原因 + 「重试」。

#### 模块 E · 数据修复与对账
- **作用**：一键修脏数据（带审计 + 备份）。
- **布局**：左=触发（选数据集 → dry-run 预览 → 确认执行）；右=最近修复审计表。
- **审计列**：`repair_id`(+`dataset_key`/`reason` 副标) · 删除行数 · 重抓结果(`refetch_result`) · fabricated(红/绿 Tag) · 备份路径(`backup_path`) · 操作人(`operator`)。
- **数据来源**：`dataQualityApi.repairDryRun()`（已有）、`POST /data-quality/repair {dry_run:false}`（执行，admin）、`sla().latest_repair_audits`。
- **安全**：执行需二次确认弹窗 + adminToken；展示「Web 不执行，worker 消费」标注（沿用既有）。
- **复用**：`DataQualityPanel` 修复审计表逻辑。

#### 模块 F · 单票数据巡检
- **作用**：怀疑某票数据就查它。
- **布局**：搜索框（代码/名称）→ 结果卡：行情质量、复权因子、停牌、交易规则、所属板块、事件覆盖。
- **数据来源**：`/quote/{symbol}`、`/kline/{symbol}`（最近 N 根 + 缺口标记）、`/instruments/{symbol}/rules|sector|events`（已有）。
- **交互**：MiniKline 复用 `ui/charts`；缺口/停牌/过期显式标。
- **状态**：未输入=引导文案；查无=「未找到该标的或暂无数据」。

#### 模块 G · ETF / 股票池管理（折叠，admin）
- **作用**：维护可交易范围。
- **复用**：整体迁移/内嵌 `EtfUniverseAdminCard` + `etfUniverseAdmin` API（草稿→校验→`repair-draft`→`apply`→`rollback`，含变更审计）。
- **状态**：保持其既有加载/错误态。

#### 模块 H · 实盘前数据门 ★
- **作用**：数据不可信 → 禁止自动下单。
- **布局**：醒目卡（绿/黄/红总灯）+ 检查清单（每项：名称 · 通过/不通过 · 说明）。
- **检查项**：行情新鲜度、无缺口、复权一致、关键数据集 SLA 达标、主数据源在线。
- **数据来源**：N3 `GET /data-quality/trade-gate`（聚合）；MVP 可先用 `sla` + `data-sources/health` 在前端聚合，N3 落地后切换。
- **联动**：红灯时，实盘自动下单入口（未来实盘对接）置灰 + 文案"数据未通过可信门，已暂停自动下单"。
- **状态**：永远显式给出**为什么不通过**，禁止只显示红灯无原因。

---

## 6. 状态管理与数据流
- 各模块取数走 `useServerState`（TanStack Query 缓存）；UI 态（展开/筛选/adminToken/确认弹窗）走新 `stores/dataConsoleUiStore.ts`（UI-only，符合 state-separation 守卫）。
- 运行中任务轮询：仅在 `document.visibilityState==='visible'` 且有 running 任务时启用，无任务即停（不新增常驻 loop）。
- 写操作统一经 `apiClient`，自动带 `X-Admin-Token`（`base.ts` 已支持）。
- 401 处理复用既有模式（按需 hook rethrow→`withLoading`，禁止 `allSettled` 静默吞错）。

### 6.1 后端采集频率（按数据类型 × 交易时段）
> A 股交易时段：集合竞价 9:15–9:25，连续竞价 9:30–11:30 / 13:00–15:00。用既有 `services/market/trading_session.py` 判定，非交易日（周末/节假日）不拉盘中数据。

| 数据类型 | 交易时段内 | 非交易时段 | 理由 |
|---|---|---|---|
| 实时行情（报价） | 实时(SSE)/3–5s 快照 | 不拉 | 已有 quote stream + quote cache 刷新；盘后无意义 |
| 分钟 K 线 / 盘中快照 | **1 分钟** | 不拉 | 盘中分钟级即可 |
| 盘中宽度 / Pulse / 情绪 | **30–60 分钟**（整点） | 不拉 | 已有"盘中 Pulse"小时级 |
| 日线 daily bars | **不在盘中拉** | **收盘后一次**（约 15:10–15:40，带重试/回补） | 盘中日线未收完=未来函数风险；收盘后增量 |
| 复权因子 | 不拉 | 跟随日线 / 有除权事件时 | 与日线一致，避免信号漂移 |
| 标的库 instrument sync | 不拉 | **每日盘前一次**（约 9:00）或每周 + on-demand 兜底 | 新股/退市/改名低频 |
| 财务 / 基本面 | 不拉 | **每日 1 次查新披露**（财报季加密）；数据本身季度更新 | 公告驱动，低频 |
| 公司事件 / 公告 / 解禁 / 龙虎榜 | 盘后 | **每日 1 次**（盘后） | 事件类日度 |
| ETF universe | 不拉 | 每周 / 有变更时 | 低频 |
| 数据质量 SLA 自检 | — | **每次采集任务结束后**自动跑 | 跟随采集，及时暴露缺口 |

**采集频率原则**
- **收盘后做重活**（日线/财务/事件/全量回补放夜间或周末），盘中只做轻量实时+分钟快照——避免与交易抢资源、避免拉未完成 K 线。
- **增量优先**；全量回补分批 + 限流 + 断点续传（已有 `daily_bar_refresh_checkpoint`），重复触发幂等不重拉。
- **免费源限流**：akshare/eastmoney 易被限/封 → 并发上限 + 退避重试 + 失效自动切备源 + 告警（接 N4）。
- **交易日历感知**：用 `trading_session.py`，非交易日不跑盘中采集。

### 6.2 前端展示刷新频率（控制台轻量，不学行情高频）
> 控制台展示的是"运维健康"数据（SLA/源健康/任务/覆盖率），不是快变行情，**刷新要克制**，并对齐既有常量（监控 5 分钟 `MONITOR_REFRESH_INTERVAL_MS`）。

| 区块 | 刷新策略 | 间隔 |
|---|---|---|
| A 健康总览 / C 覆盖率 | 进页加载 + 可见时自动 | **5 分钟**（对齐监控） |
| B 数据源健康 | 手动 + 可见时自动（探测较重，勿频繁） | **5–10 分钟** |
| D 任务队列 | **仅当存在 running 任务**时轮询，完成即停 | running：**2–3 秒**；无任务：不轮询 |
| E 修复审计 | 触发修复后 + 手动 | 事件驱动 |
| F 单票巡检 | 用户查询时拉 | 不自动 |
| H 实盘前数据门 | 进页 + **每次自动下单前强制** + 可见时 | **5 分钟** + 下单前必检 |

### 6.3 通用频率原则（前端）
- 仅 `document.visibilityState==='visible'` 时自动刷新；后台标签页暂停（省源、省请求）。
- `useServerState`/TanStack `staleTime` 去重（默认 15s），避免多面板同窗重复打同一接口。
- 自动刷新只读；**写操作（同步/回补/修复/apply）永远手动触发**，绝不自动轮询触发。

---

## 7. 新增 / 改动文件清单（落位 + 行数预算）

| 文件 | 类型 | 预算行 | 说明 |
|---|---|---|---|
| `features/data-console/DataConsolePage.tsx` | 页面 | ≤300 | 布局 + 编排 |
| `features/data-console/DataHealthOverview.tsx` | 组件 | ≤120 | 模块 A |
| `features/data-console/DataSourceHealthPanel.tsx` | 组件 | ≤140 | 模块 B |
| `features/data-console/CoveragePanel.tsx` | 组件 | ≤200 | 模块 C |
| `features/data-console/CollectionJobsPanel.tsx` | 组件 | ≤220 | 模块 D |
| `features/data-console/DataRepairPanel.tsx` | 组件 | ≤180 | 模块 E（复用 DataQualityPanel 逻辑） |
| `features/data-console/InstrumentInspectorPanel.tsx` | 组件 | ≤200 | 模块 F |
| `features/data-console/TradeDataGateCard.tsx` | 组件 | ≤120 | 模块 H |
| `features/data-console/useDataConsole.ts` | hook | ≤200 | 取数编排 + 轮询 |
| `stores/dataConsoleUiStore.ts` | store | ≤120 | UI 态 |
| `api/dataSources.ts` | api | ≤40 | `/market/data-sources/health` |
| `api/runtimeTasks.ts` | api | ≤60 | runtime-task 列表/详情/触发 |
| `api/dataQuality.ts` | api(改) | +≤30 | 加 backfill / coverage / trade-gate |
| `app/router/webRouteDefinitions.tsx` | 路由(改) | +≤5 | `/data` |
| `features/trading-workspace/navConfig.tsx` | 导航(改) | +≤3 | 「数据」入口（isAdmin 门控） |
| 模块 G | 复用 | 0 | 内嵌 `EtfUniverseAdminCard` |

> `DataQualityPanel`（settings）可保留或在 settings 留一个"详见数据控制台"的跳转，避免两处重复维护（二选一，建议迁入控制台）。

---

## 8. 分批计划（每批可独立合并）

| 批次 | 范围 | 端点 | 验收重点 |
|---|---|---|---|
| **M1 只读 MVP** | A 总览 + B 源健康 + C 覆盖率（无钻取）+ D 队列（只读） | 全部已就绪 | 一页看清数据健康，0 写操作 |
| **M2 触发任务** | D 触发区（同步/收盘刷新/区间回补）+ admin 门控 | N2 backfill | 触发即建 runtime-task，进度轮询正确 |
| **M3 修复与钻取** | E 修复对账 + C 钻取明细 + F 单票巡检 | N1 coverage | dry-run→执行→审计闭环；缺失明细可查 |
| **M4 实盘前门** | H 数据门聚合 + B 源失效告警 | N3 trade-gate(+N4) | 红灯给原因；与（未来）实盘下单联动置灰 |
| **M5 移动端 + G** | 单列布局 + ETF universe 内嵌 | — | 375px 无横向溢出；G 行为等价 |

试点：先做 M1（纯只读、全用现成接口），验证信息架构后再推进。

---

## 9. 验收标准（命令分层）
- 前端改动：`npm run lint`、相关测试、`npm run build:web` 全绿；涉及新类型跑 `npm run api:check`（§6.11）。
- 响应式：`npm run smoke:responsive` 在新增 `/data` 路由 0 横向溢出（M5 含 375px）。
- 功能：
  - 非 admin 看不到「数据」入口；未填 adminToken 时写按钮禁用。
  - 一个源/一个接口失败不拖垮整页（独立错误态）。
  - 触发任务只建 runtime-task，Web 不执行重逻辑（代码评审确认无后台 loop）。
  - 缺数据显式（stale/missing/blocked/unavailable），无假绿灯。
  - 数据门红灯必带原因；修复必经 dry-run + 二次确认 + 审计。
- 测试最低要求（§6.5）：覆盖加载/空/错误/禁用态 + 触发任务交互 + 门控隐藏。

## 10. 回退方式
- 整页 feature flag / 路由开关：隐藏「数据」入口即完全回退，不影响 7 个核心页。
- 新薄端点独立可回退（前端 H 模块降级为前端聚合，不依赖 N3）。
- `DataQualityPanel` 若迁入控制台，保留 settings 旧入口一个版本周期再删（§6.10）。

## 11. 明确不做
- 不做数据血缘/目录/多租户/可视化 ETL 编排。
- 不在 Web 执行采集/修复/回补计算。
- 不重写 provider / data_quality / runtime-task / etf-universe 引擎。
- 不提供"假装已更新"的乐观绿灯。

## 12. 风险与处置
| 风险 | 处置 |
|---|---|
| 误把管理操作暴露给普通用户 | `isAdmin` 隐藏入口 + adminToken 禁用写按钮 + 后端鉴权双保险 |
| 轮询过多打接口 | 仅可见 + 仅有 running 任务时轮询；无任务即停 |
| 在 Web 偷偷跑重任务 | 一律 runtime-task；评审守卫"无新增后台 loop" |
| N1/N3 后端未就绪阻塞前端 | M1 全用现成接口；H 先前端聚合，N3 落地再切换 |
| 文件超行数阈值 | 按 §7 预算拆分，页面只编排不堆逻辑 |

---

## 附录 · 状态/空/错文案（通俗，禁内部术语）
- 综合灯：绿「数据正常，可放心使用」/ 黄「部分数据偏旧，注意甄别」/ 红「关键数据缺失或阻断，暂不建议据此下单」。
- 源异常：「该数据源暂时不可用，已自动切换，部分数据可能延迟」。
- 空态：「所有数据集覆盖正常」/「暂无采集任务」/「未找到该标的或暂无数据」。
- 修复确认：「将删除并重抓 X 数据集的异常数据（自动备份），由后台任务执行，确认继续？」
