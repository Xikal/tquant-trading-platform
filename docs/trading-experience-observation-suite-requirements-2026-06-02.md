# 交易经验观察与复盘套件 · 需求文档（PRD）

状态：草案（待评审）
适用范围：基于 `docs/reports/zhangmengzhu-16-articles-analysis-2026-06-02.md` 结论，为平台新增“观察 / 复盘 / 风险标签 / 持仓纪律”能力
最后核验日期：2026-06-02
结论入口：本套件**全部为研究/观察层，默认 feature flag 关闭，不进生产排序、不产 `production_score`、不喊买卖、不推荐个股**；任何形态/买卖点/做 T 结论须经 24M 回测 + 样本外 + 模拟盘三道验证后才可标“可参考”。
合规声明：本套件仅辅助观察与复盘，不构成投资建议，不推荐任何标的；“主力出货/洗盘/吸筹”一律转为可计算的价量**风险标签**，不作为事实或交易指令。

---

## 1. 背景与定位

16 篇文章分析显示：平台在“选股信号/买点/支撑压力/大盘与板块过滤”上**已基本覆盖**（low_buy、priority board、AKeyLevel、market gate、sector/leader），重复造选股引擎价值低。报告真正的增量在四个**尚未成体系**的方向：**每日复盘闭环、量价-位置风险标签、相对强度/抗跌观察、持仓纪律助手**，以及两个**需先验证**的方向：涨停后量价跟踪、做 T 纪律与效果归因。

本套件把这些做成统一的“观察与复盘”能力层，**复用既有引擎**，不污染生产，帮助用户“看懂位置、守住纪律、坚持复盘”。

## 2. 目标 / 非目标

**目标**
- 把交易经验沉淀为**可观察、可验证、可复盘**的功能，而非新的买卖建议。
- 提供每日复盘闭环 + 交易纪律日志，形成“入池→剔除→跟踪→自检”习惯。
- 用可计算价量信号给个股/持仓打**风险标签**与**相对强度**，辅助“看懂位置”。
- 给持仓提供**纪律提示**（移动止盈、禁向下补仓、破位 vs 情绪回调）。
- 为“涨停后形态/做 T 是否有效”提供**先证伪、再采信**的研究与归因工具。

**非目标**
- 不新增进入生产排序的选股策略或 `production_score`。
- 不输出买入/卖出/加仓/必涨等交易指令，不代客操作，不推荐个股。
- 不把“主力”叙事当事实，不做做 T 推荐器，不做否定基本面类功能。
- 不重建 low_buy/AKeyLevel/sector-leader 等既有引擎的并行实现。

## 3. 硬边界（不可跑偏 · 实现期必须始终成立）

1. **观察/复盘/风险/纪律层定位**：默认 flag-off；不进 priority board 生产排序、不产 `production_score`、不改 `strategy_policy` 与打分边界。
2. **叙事转标签**：“出货/洗盘/吸筹/对敲”→ 价量风险标签（`info`/`warn`），文案为“需警惕/观察/留意”，**禁止**“建议买入/卖出/低吸/必涨/突破即买”等越界文案（沿用前端文案守卫测试）。
3. **不荐股、不建议**：全程无个股推荐、无投资建议；所有界面带风险提示。
4. **先验证再采信**：涨停形态、买卖点有效性、做 T 降成本等结论，进入“可参考”前必须 24M+ 回测 + 样本外 + 模拟盘，披露胜率/盈亏比/最大回撤/样本量/分季度稳定性；不达标只做展示，标 `research_only`。
5. **复用既有引擎**：风险标签复用 AKeyLevel + distribution_signals + hard_risk；相对强度复用 sector/leader + 行情；纪律复用 paper risk + AKeyLevel 破位；复盘复用 strategy tracking + 观察池；做 T 复用 ETF smart-T/intraday。**禁止并行重建。**
6. **缺数据显式降级**：`insufficient`/`research_only`/`no_data`/`blocked`/`stale`，禁空分、假分、TODO 占位。
7. **无未来函数**：所有标签/分类只用“信号日及之前可见数据”；复盘与效果归因的前向数据仅作**事后测量**，不回灌进当日判断。
8. **工程规范**：重计算走 worker（不新增 Web 后台 loop）；前端走 `DataTable`/`VirtualCardList`、零 `useState/useReducer`、新面板懒加载；契约类型来自 generated。

## 4. 与现有能力的关系（复用映射，避免重建）

| 本套件能力 | 复用的现有模块 | 仅新增 |
|---|---|---|
| 量价风险标签 B | AKeyLevel、`distribution_signals`、`hard_risk`、日线行情 | 标签状态机 + schema + 展示 |
| 相对强度/抗跌榜 C | `leader_strength`、`mainline_strength`、指数/板块行情 | RS 计算 + 榜单视图 |
| 每日复盘/日志 A | `strategy_tracking`、观察池、paper | 复盘动线 + 用户交易日志 |
| 持仓纪律助手 D | paper `risk_circuit`、AKeyLevel 破位 | 每持仓纪律提示引擎 |
| 涨停后量价跟踪 E | 日线 + 涨停标记、24M 回测 | 形态分类 + 回测门 |
| 做 T 纪律与归因 F | ETF smart-T、intraday、paper 成交 | 做 T 归因 + 纪律提示 |

---

## 5. 能力需求清单

> 命名：FR=功能需求，AC=验收标准。所有输出字段默认 `snake_case`，含 `data_quality` / `as_of` / `engine_version`。

### A. 每日复盘工作流 + 交易纪律日志（来源：文章 12 / 6 / 15）｜最高优先

**用户故事**：作为短线用户，我希望每天收盘后自动得到“强势观察池”，次日自动剔除转弱标的，并记录我自己的操作与是否守纪律，从而形成稳定复盘习惯。

**FR**
- FR-A1 收盘自动构建“强势观察池”：当日涨幅 ≥ 可配置阈值（默认 8%）入池，记 `pool_date`、`reason`、入池时量价快照。
- FR-A2 次日自动剔除：池内放量破位 / 跌幅居前 / 跌破强势结构者标 `dropped` 并记原因。
- FR-A3 优质标的跟踪 ≥N 日（默认 3）：未破强势结构、量能承接在的标 `retained`。
- FR-A4 用户交易日志：用户可记录每笔（paper 或手填）操作的理由、信号来源、是否符合自定纪律（顺势/止损/未补仓/未追无量）。
- FR-A5 复盘小结：按日/周聚合“入池命中、剔除、自我纪律达成率”，纯回顾，无建议。

**数据契约**
- 输入：日线 `OHLCV`、涨跌幅、量比、均线、AKeyLevel 破位标记、用户操作记录（paper/手填）。
- 输出 `review_pool_item`：`pool_date, symbol, status(in_pool|retained|dropped), entry_pct, volume_ratio, drop_reason, tracked_days, data_quality, as_of`。
- 输出 `trade_journal_entry`：`entry_id, user_id, symbol, action(buy|sell|trim|add|t_trade), reason_text, signal_source, discipline_flags{trend_follow,stop_loss_set,no_add_down,no_chase_noliquidity}, created_at`。

**AC**
- 收盘后 worker 产出当日观察池，次日产出剔除/留存；缺数据标 `insufficient` 而非空列表。
- 日志支持增删改查、按纪律维度统计达成率；**不产生任何买卖建议**。
- flag 关闭时复盘页隐藏，核心流程不受影响。

**flag**：`trade_review_suite_enabled`（默认 false）。
**UI**：策略跟踪/工作台新增“复盘”页签（懒加载），表走 `DataTable`。
**测试**：入池/剔除规则、阈值边界、缺数据降级、纪律统计、flag-off 隐藏。

### B. 量价-位置风险标签层（来源：文章 1 / 7 / 9）

**用户故事**：作为用户，我希望在个股/持仓详情看到“当前价量位置是良性还是需警惕”的**风险标签 + 证据**，而不是被“主力出货”这类说法吓到或误导。

**FR**
- FR-B1 输出位置-量价风险标签集合，覆盖：`high_vol_distribution_risk`（高位放量需警惕）、`low_vol_grind_down_risk`（高位缩量阴跌-派发风险）、`healthy_pullback_observe`（缩量回踩-良性观察）、`up_shrink_down_expand_risk`（涨缩跌放-警示）、`blowoff_overheat_risk`（加速过热）、`price_volume_divergence_risk`（量价背离）。
- FR-B2 每个标签带 `evidence`（触发的可计算条件：位置分位、量比、均线偏离、上下量比等）与 `level`（`info`/`warn`）。
- FR-B3 标签仅作风险提示，**不附带买卖动作**；文案过“无越界”守卫。

**数据契约**
- 输入：日线 `OHLCV`、近 120/250 日滚动分位、MA5/10/20/30/60、均线偏离、上/下行日量能比、AKeyLevel 支撑压力/破位、`distribution_signals`。
- 输出 `vp_position_tag`：`symbol, trade_date, tag_code, level(info|warn), evidence[], explanation, data_quality, as_of, engine_version`。

**口径（主观→可验证，节选；阈值均为待回测参数）**
- 高位放量需警惕：收盘 ≥ 近120日80%分位 且 量 ≥ 近10日均量×K1 且 当日/次日收阴。
- 高位缩量阴跌：高分位 + 连续≥3日小阴 + 量温和 + 跌破 MA5/MA10。
- 缩量回踩良性：价>MA20 且均线多头 且 回调量<前5日均量×K2 且 回踩 MA5/MA10 不破。
- 涨缩跌放：区间内（上涨日均量÷下跌日均量）< 1。
- 加速过热：近3日累计涨幅 > 前20日日均涨幅×K3 且 收盘偏离 MA10 > P%。
- 量价背离：价创N日新高但量 < 前高对应量。

**AC**
- 同一标的可同时命中多个标签；缺数据标 `insufficient` 不造标签。
- 标签文案通过越界文案守卫（无“买入/卖出/低吸/必涨”等）。
- **不写入 priority board 排序，不影响 `production_score`。**

**flag**：`vp_position_tags_enabled`（默认 false）。
**UI**：监控页/个股详情/持仓详情的只读标签条（懒加载/折叠）。
**测试**：每个标签的触发/不触发用例、缺数据降级、文案守卫、与生产排序隔离断言。

### C. 相对强度 / 抗跌榜（来源：文章 5）

**用户故事**：大盘大跌日，我想看哪些标的逆势抗跌（相对强度高），作为观察，而不是被告知“它会暴涨”。

**FR**
- FR-C1 计算相对强度：`rs_vs_index = 个股涨跌幅 − 指数涨跌幅`、`rs_vs_sector = 个股 − 所属板块`。
- FR-C2 大跌日（指数跌幅 ≤ 阈值）输出“抗跌榜”，标 `resilient`（逆势抗跌/收红）或 `follow_down`（同步补跌）。
- FR-C3 仅展示相对强度事实与排名，**不预测后续涨跌**。

**数据契约**：输入 个股+指数+板块日线；输出 `relative_strength_item`：`symbol, trade_date, rs_vs_index, rs_vs_sector, sector_rank, resilience_flag, data_quality, as_of`。

**AC**：大跌日榜单可生成；标签为观察事实；不进生产排序；缺指数/板块数据标 `insufficient`。
**flag**：`relative_strength_board_enabled`（默认 false）。**UI**：监控页观察看板（虚拟化表）。
**测试**：RS 计算正确、大跌日触发、补跌/抗跌分类、缺数据降级。

### D. 持仓纪律助手（来源：文章 10 / 13 / 15）

**用户故事**：作为持仓用户，我希望系统按客观规则提示“是否破位该减、是否到移动止盈、是否在向下补仓”，帮我守纪律。

**FR**
- FR-D1 移动止盈提示：盈利 ≥ 阈值后，建议防守位抬到成本上方/跟踪 MA（仅提示，不代操作）。
- FR-D2 禁止向下补仓守卫：持仓破位后，对“加仓”动作给出**纪律警告**（不阻断真实交易，平台不下真单）。
- FR-D3 破位 vs 情绪回调区分：用 AKeyLevel 客观破位规则标 `break_down` 或 `emotional_pullback`。
- FR-D4 盯盘节奏提示：提示“按计划复盘频率”而非实时盯盘。

**数据契约**：输入 持仓成本、日线、AKeyLevel 破位/支撑；输出 `holding_discipline_hint`：`symbol, hint_code(trailing_stop|no_add_down_warning|break_down|emotional_pullback|watch_cadence), level, evidence[], data_quality, as_of`。

**AC**：每持仓给出客观规则提示；破位用 AKeyLevel 规则定义（非情绪）；提示无“快卖/抄底”等指令；flag-off 隐藏。
**flag**：`holding_discipline_assistant_enabled`（默认 false）。**UI**：paper/持仓详情面板增强。
**测试**：移动止盈触发、补仓警告、破位/回调分类、缺数据降级。

### E. 涨停后量价跟踪器（来源：文章 8）｜需回测门

**用户故事**：我想跟踪近期涨停标的的 3-5 日量价演化并看到形态分类，但我知道这些形态需要先被验证。

**FR**
- FR-E1 对近5日有涨停的标的，跟踪后续3-5日量价，分类：`three_yin_floor`/`half_volume_signal`/`four_star_consolidation`/`probe_updown`/`volume_stall_warning`。
- FR-E2 每形态附 `evidence` 与 `data_quality`。
- FR-E3 **回测门**：每个形态在最近 24M 报告中输出胜率/盈亏比/样本量/分季度稳定性；未达门槛标 `research_only`，**不进任何打分或排序**。

**数据契约**：输入 日线 + 涨停标记（涨停价/封板）；输出 `limit_up_followthrough_item`：`symbol, limit_up_date, pattern_code, days_since, evidence[], backtest_winrate, backtest_pf, sample_count, status(research_only|observed), data_quality, as_of`。

**AC**：形态分类可复现；**默认 research_only**；只有回测达标才允许标“可参考观察”，仍不进生产排序；高过拟合风险在 UI 标注。
**flag**：`limit_up_followthrough_enabled`（默认 false）。**UI**：研究/观察页（懒加载），标注“研究态，需验证”。
**测试**：形态分类、回测指标接入、未达标降级、与生产隔离。

### F. 做 T 纪律助手 + 效果归因（来源：文章 16）｜需数据门 + 证伪优先

**用户故事**：我想要做 T 的纪律提示，更重要的是想知道“我做 T 到底有没有真的降成本”。

**FR**
- FR-F1 做 T 纪律视图：底仓/T 仓分离、3-5% 差价目标、破位停 T、上升趋势才做 T（仅提示）。
- FR-F2 **效果归因（核心）**：对比“做 T vs 不做 T”的真实成本/收益、胜率、被卖飞次数，基于 paper 真实成交。
- FR-F3 数据门：分钟/盘中数据覆盖率不足时，做 T 模块降级为 `no_data`，只做底仓趋势提示。

**数据契约**：输入 分钟/盘中（需覆盖率验证）、paper 成交、AKeyLevel 破位；输出 `t_trade_attribution`：`symbol, period, t_trade_count, realized_cost_delta, win_rate, sell_fly_count, vs_no_t_trade_return_delta, data_quality, as_of`。

**AC**：归因以 paper 真实成交为准；**先呈现“做 T 是否有效”的客观结论（含可能为负）**，而非鼓励做 T；分钟数据不足显式降级。
**flag**：`t_trade_discipline_enabled`（默认 false）。**UI**：paper 页做 T 面板（懒加载）。
**测试**：归因计算、卖飞统计、数据不足降级、纪律提示无买卖指令。

---

## 6. 数据依赖总表

| 数据 | 来源 | 用于 |
|---|---|---|
| 日线 OHLCV / 涨跌幅 / 量比 | 已有日线快照 | A/B/C/D/E |
| 滚动分位、均线 MA5–60、均线偏离 | 派生（已有指标） | B/D/E |
| AKeyLevel 支撑/压力/破位 | AKeyLevel Engine | B/D |
| 指数 / 板块行情、板块成分 | 已有 market/sector | C |
| 涨停价 / 封板标记 | 已有行情/标记 | E |
| 分钟 / 盘中（需覆盖率验证） | minute/tick（覆盖率待验证） | F |
| paper 成交 / 持仓成本 | paper 服务 | A/D/F |
| 24M 回测指标 | 既有 24M 回测 + portfolio_backtest_metrics | E 回测门 |

## 7. 研究 → 生产 晋级流程（统一门禁）

1. 本套件所有能力默认 **research/观察态、flag-off**。
2. 涉及“有效性结论”的（E 形态、F 做 T、未来若把任何标签接入打分）必须出 24M 回测 + 样本外 + 模拟盘报告（胜率/盈亏比/最大回撤/样本量/分季度稳定性），口径区分候选池/真实组合 max5/max10/观察池，**无裸“总收益”**。
3. 仅当达标且经评审，才考虑作为“可参考观察”升级展示；**进入生产排序/打分需另走既有 `strategy_policy` 门禁与守卫测试**，本套件不自动晋级。

## 8. 分批路线图

- **M1（观察/复盘，最低风险）**：A 每日复盘+日志 → B 量价风险标签 → C 相对强度/抗跌榜。
- **M2（纪律增强）**：D 持仓纪律助手。
- **M3（需回测/数据门）**：E 涨停后量价跟踪（先回测）→ F 做 T 归因（先验证分钟数据 + 证伪）。

## 9. 验收命令 / 回退

- 后端：相关 `pytest`（各能力单测 + 缺数据 + 与生产隔离断言 + 文案守卫）。
- 前端：`api:check` + `lint`（含 refactor/state-separation guard）+ 相关 `vitest` + `build` + `analyze`（首屏不退化）。
- 回退：每能力独立 flag，关闭即回到既有行为；新表/新任务可停而不影响核心流程与 paper/回测。

## 10. 不做清单（明确排除）

- 不输出买入/卖出/加仓/必涨/喊单，不代客操作，不推荐个股。
- 不把“主力出货/洗盘/吸筹”做成事实判定或交易指令。
- 不把未回测形态/买卖点接入生产排序或 `production_score`。
- 不做做 T 推荐器（只做纪律提示 + 效果证伪）。
- 不做否定基本面类功能；不重建 low_buy/AKeyLevel/sector-leader 并行引擎。

## 11. 风险与合规

- **过拟合/幸存者偏差**：E/F 及任何形态结论必须回测+样本外，UI 标“研究态需验证”。
- **误导风险**：标签/榜单只呈现可计算事实与证据，文案受越界守卫约束。
- **数据不足**：F 依赖分钟数据，覆盖率不足显式降级，不造假分。
- **合规**：全程风险提示“仅辅助观察与复盘，不构成投资建议，需历史回测+样本外+实盘观察验证”。
