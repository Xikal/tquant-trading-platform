# 集合竞价辅助能力 · 完整需求文档（PRD）

状态：草案（待评审）
日期：2026-06-10
适用范围：利用 A 股集合竞价（9:15–9:25）信息，为**已持仓票**提供晨间风险提示、为**策略推荐票**提供次日入场确认门
关联文档：`docs/strategy-success-rate-optimization-plan-2026-06-10.md`（本能力即其 **S4b**，与 S4 盘中确认同框架）、`TRADING_QUANT_LEAD_PLAYBOOK.md`、`docs/engineering-conventions.md`
结论入口：分三阶段落地——**Phase 1（可历史回测的 gap 确认门）→ Phase 2（竞价采集 + 持仓晨间风险哨）→ Phase 3（竞价过程信号前向验证）**；全部默认 feature flag 关闭、研究态先行、过 A1 证据门才进生产。
合规声明：本能力仅提供**观察提示与入场确认过滤**，不构成买卖指令、不自动交易、不修改生产排序与策略语义。

---

## 1. 背景与定位

平台信号链的硬规则是**收盘后发布、次日入场**（前视守卫）。集合竞价是入场前的第一份新信息，当前完全未被利用：

- `next_day_event_model.py` 已按策略生成"次日事件计划"，其中提及竞价但**仅为文案提示**，不可执行；
- `intraday_confirmation.py` 已有 VWAP 确认与尾盘确认两类集合（`VWAP_CONFIRMATION_STRATEGIES`、`LATE_SESSION_CONFIRMATION_STRATEGIES`），**竞价确认是天然的第三类**，插同一框架；
- 24M 证据显示 first_board 最近季度 OOS 代理 PF 0.75（46 笔）——首板次日竞价行为（承接强弱）是该策略最直接的可观察修复杠杆之一；
- 已持仓票（paper 持仓 + 自选）目前在开盘前没有任何风险预警通道。

**定位**：竞价信息 = 既有确认框架的扩展 + 持仓观察层的晨间哨兵。**不是新策略、不是预测工具。**

---

## 2. 目标 / 非目标

**目标**
1. 推荐票：为生产策略提供"次日竞价确认门"——竞价形态不利时**跳过/降权当日入场**，提升净胜率（联动 S 计划）。
2. 持仓票：开盘前对 paper 持仓与自选给出**竞价风险/强势提示**（联动 AKeyLevel 止损位与 S1 分层止盈）。
3. 建立竞价数据采集与质量口径，为前向验证积累样本。

**非目标**
- 不做"竞价抢筹=必涨"类预测断言；不输出买卖指令；不自动交易。
- 不修改 `strategy_policy.py`、生产排序、`production_score`、风控阈值。
- 不在 Web 请求线程拉取竞价数据。
- 不依赖 9:15–9:20 可撤单段做任何决策（诱导单噪声）。

---

## 3. A 股竞价机制事实基础（口径锚点）

| 时段 | 规则 | 本需求的使用方式 |
|---|---|---|
| 9:15–9:20 | 可挂可撤（**诱多/诱空高发**） | **禁止**作为决策输入；仅可采集存档用于研究 |
| 9:20–9:25 | 可挂**不可撤** | 竞价过程信号的唯一有效窗口（Phase 3） |
| 9:25 | 撮合产出开盘价、竞价成交量/额 | Phase 1/2 的主输入（结果层） |
| 9:25–9:30 | 可挂单不撮合 | 不使用 |

衍生指标（全部为**待标定参数**，阈值由回测确定，不得拍脑袋）：
- `gap_pct`：开盘价 vs 昨收涨跌幅
- `auction_volume_ratio`：竞价成交量 / 昨日全天成交量
- `auction_amount`：竞价成交额（流动性门槛联动 S5）
- Phase 3 过程指标：9:20–9:25 虚拟撮合价斜率、未匹配量变化、最后一分钟价量突变

---

## 4. 能力需求

### A. 推荐票次日入场确认门（核心，联动 S 计划 S4b）

**用户故事**：作为使用生产榜的用户，我希望推荐票在次日竞价明显不利时被标记"今日跳过/降权"，避免在弱承接日入场。

**FR-A1** 新增竞价确认类型：`intraday_confirmation.py` 增加 `AUCTION_CONFIRMATION_STRATEGIES` 集合与 `auction_confirmation_passes(strategy_key, auction)` 判定，与 VWAP/尾盘确认同框架、同 seam。
**FR-A2** 按策略的确认规则（**研究变体先行，阈值待回测标定**）：
- `first_board`：竞价弱承接（`gap_pct < G1_low` 或 `gap_pct` 在区间内但 `auction_volume_ratio < V1`）→ 当日 `auction_reject`；温和高开 + 放量 → `auction_confirmed`。
- `volume_shrink`：`gap_pct > G2_high`（大幅高开破坏低吸前提）→ 当日 `auction_reject`。
- `late_session_strong_support`：暂不纳入（样本稀，先观察）。
**FR-A3** 确认结果仅影响**当日入场标记**（`auction_state: confirmed | rejected | not_evaluated | no_data`），不改信号本身、不改榜单排序；被 reject 的信号仍可见，标注原因文案（观察语义，如"竞价弱承接，今日不入场"）。
**FR-A4** 与 `next_day_event_model` 联动：把现有竞价文案升级为引用真实 `auction_state` 的可执行说明。

### B. 持仓晨间风险哨（advisory 层）

**用户故事**：作为持仓用户，我希望 9:25 后、开盘前看到持仓票的竞价风险提示，辅助晨间决策。

**FR-B1** 对 paper 持仓 + 自选股，9:25 后生成竞价提示：
- `auction_break_risk`：开盘价（竞价）< AKeyLevel 止损位/关键支撑 → "竞价已破风险线，开盘评估"（warn）
- `auction_gap_strength`：高开 ≥ 阈值且竞价放量 → 联动 S1 分层止盈提示（info）
- `auction_gap_down`：低开 ≥ 阈值未破位 → 观察提示（info）
**FR-B2** 提示为**纯展示/advisory**，复用既有 StatusPill/Tag 观察语义；文案过越界守卫（禁"建议买入/卖出/必涨/低吸"）。
**FR-B3** 展示位：`/next/paper` 持仓卡、`/next/monitor` 自选区；9:25 前显示 `not_evaluated`，缺数据显示 `no_data`，不伪造。

### C. 竞价数据采集（Phase 2 基建）

**FR-C1** 新增盘前竞价 provider（candidate：akshare `stock_zh_a_hist_pre_min_em` 或东财盘前分时），按既有 provider 模式（ProviderResult + circuit + 限频）。
**FR-C2** 采集编排：RuntimeTask 定时任务，**仅在交易日 9:20–9:25 窗口**对目标集合采集（目标集合 = paper 持仓 ∪ 自选 ∪ 最新优先榜候选，复用 `build_quote_cache_demand_symbols` 同源需求集），9:25:30 截止。每日窗口约 5 分钟，资源极小。
**FR-C3** 落库：`auction_snapshots` 表（见数据契约），含采集时刻、来源、`data_quality`；任务登记进 `RUNTIME_TASK_REGISTRY`（owner/worker/重试/幂等键，遵守注册表治理）。
**FR-C4** 历史竞价过程数据**不可回补**——采集自上线日起前向积累，文档与 UI 显式标注样本起始日。

---

## 5. 数据契约（snake_case，含 data_quality/as_of）

**auction_snapshot（采集层）**
```
symbol, trade_date, captured_at, phase("locked_0920_0925"|"result_0925"),
ref_price(虚拟撮合/开盘价), matched_volume, unmatched_volume?, amount,
prev_close, gap_pct, auction_volume_ratio?, source, data_quality(ok|partial|no_data), as_of
```

**auction_confirmation（确认层，FR-A）**
```
symbol, strategy_key, signal_trade_date(信号发布交易日), entry_trade_date(次日),
auction_state(confirmed|rejected|not_evaluated|no_data), reject_reason_text,
gap_pct, auction_volume_ratio, thresholds_version, evaluated_at, engine_version
```

**auction_position_hint（持仓哨，FR-B）**
```
symbol, trade_date, hint_code(auction_break_risk|auction_gap_strength|auction_gap_down),
level(info|warn), evidence[](gap_pct/量比/破位价/止损价), key_level_source(AKeyLevel),
data_quality, as_of
```

规则：所有时间为交易日历口径（非自然日）；停牌/新股/无昨收 → `no_data`；OpenAPI/generated types 同步（契约优先）。

---

## 6. 数据可得性与回测约束（诚实声明）

| 数据 | 可得性 | 回测能力 |
|---|---|---|
| 9:25 结果（开盘价/gap） | ✅ 日线 `open` 已有 | **可 24M 历史回测**（Phase 1 依此先行） |
| 竞价量/额 | ⚠️ 分钟首 bar 近似或快照 | 基本可回测（近似口径需在报告披露） |
| 9:20–9:25 过程分时 | ❌ 需新 provider，**历史不可回补** | 仅前向验证（Phase 3，N 周样本后评估） |

**含义**：Phase 1 的 gap 确认门可以直接用既有 24M 数据走 A1 证据门；Phase 3 的过程信号必须"先采集后验证"，期间只进研究面板，不参与任何确认判定。

---

## 7. 架构契合（复用既有，禁止并行重建）

| 本能力 | 复用 |
|---|---|
| 确认框架 | `intraday_confirmation.py` 第三类集合（同 seam、同测试模式） |
| 次日计划 | `next_day_event_model.py` 文案升级为引用真实状态 |
| 止损/支撑位 | AKeyLevel（`key_levels`）已有快照 |
| 目标集合 | `build_quote_cache_demand_symbols` 同源需求集 |
| 采集编排 | RuntimeTaskQueue + 任务注册表（不进 Web 线程，不新增 Web loop） |
| 展示 | frontend-next 既有 StatusPill/Tag/观察语义；paper/monitor 页 |
| 回测验证 | 既有 24M 回测框架 + `portfolio_backtest_metrics`（唯一组合事实源） |

---

## 8. Feature Flags（默认全关）

- `auction_confirmation_enabled = false`（FR-A，Phase 1 回测达标后才允许开）
- `auction_position_hints_enabled = false`（FR-B）
- `auction_snapshot_collection_enabled = false`（FR-C）
- Phase 3 过程信号研究：`auction_process_research_enabled = false`

关闭时：确认判定返回 `not_evaluated`（不影响既有入场行为）、持仓哨隐藏、采集任务不入队；核心流程回到现状，无空态假态。

---

## 9. 测试要求

**后端**
1. 竞价确认判定单测：confirmed/rejected/not_evaluated/no_data 四态 + 阈值边界 + 停牌/新股缺昨收降级。
2. **防未来函数**：确认只用 `entry_trade_date` 当日 9:25 及之前数据；信号发布日数据不得使用次日竞价（时间戳断言）。
3. 交易日历：周末/节假日不评估、不报"缺数据"；`signal_trade_date → entry_trade_date` 用交易日推进。
4. 采集任务：注册表登记守卫、幂等键稳定、仅 9:20–9:25 窗口入队、失败重试上限。
5. **生产隔离硬断言**：竞价模块零 import `production_scoring/priority_board/strategy_policy` 写路径；`auction_state` 不影响 `production_score` 与榜单排序（golden：开关前后榜单字段 sha256 一致）。
6. Phase 1 回测：确认门变体 vs 基线对照表（胜率/PF/净期望/回撤/样本留存）。

**前端（frontend-next）**
1. 四态渲染 + `no_data/not_evaluated` 不伪造；9:25 前状态正确。
2. 文案越界守卫（无"建议买入/卖出/必涨"）。
3. reject 标注不隐藏信号本身（仍可见 + 原因）。

---

## 10. 验收标准（按 Phase）

**Phase 1（gap 确认门，~2 人日 + 回测）**
- 24M 回测产出对照报告：first_board / volume_shrink 各确认门变体 vs 基线，含 OOS 与 walk-forward；
- **采纳门（A1 对齐）**：净期望与 PF 不低于基线、胜率提升、样本留存 ≥60%、回撤不放大；任一不达 → 该策略不启用竞价确认（记录结论）；
- 守卫测试全绿；榜单排序 sha256 零漂移。

**Phase 2（采集 + 持仓哨，~3 人日）**
- 交易日 9:20–9:25 采集成功率 ≥95%（目标集合）；
- 持仓哨在 paper/monitor 正确展示四态；破位提示与 AKeyLevel 数值一致；
- 资源：采集窗口外零常驻开销；任务注册表/观测面板可见心跳与失败。

**Phase 3（过程信号前向验证，采集 ≥4 周后）**
- 前向样本报告：9:20–9:25 过程指标与次日收益的关系统计（研究态）；
- 仅当统计显著且稳定才提议升级确认规则，重新走 Phase 1 同款采纳门。

---

## 11. 风险与降级

| 风险 | 处置 |
|---|---|
| 9:15–9:20 诱导单污染 | 决策输入硬编码排除该段；仅存档研究 |
| 竞价数据源限频/失败 | provider circuit + 当日 `no_data`（确认门放行=保持现状行为，不因缺数据误拦） |
| 高开确认后秒杀回落（竞价骗炮） | 确认门只解决"是否入场"，入场后由既有止损/S1 出场管；报告需统计 confirmed 后的失败率 |
| 阈值过拟合 | 阈值带 `thresholds_version`；OOS/walk-forward 必测；季度复核 |
| 停牌/新股/科创北交不同涨跌幅 | 按板块规则归一化 gap 口径；缺昨收 → `no_data` |
| 采集任务漂移 | 注册表 + 幂等键 + 观测面板心跳（复用既有治理） |

---

## 12. 不做什么

- 不做竞价排名/竞价选股榜（避免变成新的噪声策略源）。
- 不用 9:15–9:20 数据做任何判定。
- 不自动交易、不输出买卖指令、不改生产排序与策略语义。
- 不在 Web 请求线程拉竞价；不新增 Web 后台 loop。
- 不臆造历史竞价过程数据回测；近似口径必须在报告披露。
- Phase 1 未达采纳门的策略不强行启用。

---

## 13. 实施排期建议

```
Phase 1（先行，纯回测，不依赖新数据源）：
  W1：gap/量比近似指标构建 + first_board/volume_shrink 确认门变体 24M 回测 → 对照报告 → 采纳/不采纳结论
Phase 2（基建 + 哨兵）：
  W2：竞价 provider + 采集任务（注册表/幂等/观测）+ auction_snapshots 落库
  W2-W3：持仓晨间风险哨（paper/monitor，flag-off → 内部验证 → 开 advisory）
Phase 3（前向验证）：
  采集满 4 周后出过程信号研究报告，决定是否升级确认规则
```

与 `strategy-success-rate-optimization-plan-2026-06-10.md` 的关系：Phase 1 即 **S4b**，建议与 S2（first_board OOS 诊断）联动执行——若诊断显示失效集中在弱承接日，竞价确认门就是直接对症的修复项。
