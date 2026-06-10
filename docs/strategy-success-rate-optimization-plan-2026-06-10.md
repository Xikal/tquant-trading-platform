# 策略成功率优化执行计划（2026-06-10）

> 状态：方案（待执行）。**本文只出方案与验证门，不直接改策略代码。**
> 目标：在不破坏既有证据门禁的前提下，提升三个生产策略的净胜率与稳定性，并给退役策略一条证据驱动的回归路。
> 依据：`docs/reports/strategy_24m_duckdb_report.md`（24M 全策略回测，2026-05-30）、`docs/reports/market-state-guard-walk-forward-2026-05-28`、`backend/app/services/low_buy/intraday_confirmation.py`、`backend/app/services/decision_context/market_gate.py`、`backend/app/services/strategy_improvement/{walkforward,temporal_guard}.py`、`TRADING_QUANT_LEAD_PLAYBOOK.md`。
> 最后核验日期：2026-06-10（本文所有现状数字为当日实测/报告原文）。

---

## 0. 两条纪律（先于一切优化）

1. **胜率仅作辅助指标**（playbook §5 原文：盈亏比核心、期望收益扣费后）。任何"提胜率"的改动必须同时验证 **净期望、PF、最大回撤** 不劣化——分层止盈会提胜率但削峰，不为胜率牺牲期望。
2. **所有改动走证据门（A1 门禁）**：先做 research variant / shadow → 24M 回测 + walk-forward + OOS + 守卫测试全绿 → 才允许进生产。**不直接改 `strategy_policy.py`、生产排序、`production_score`、风控阈值**；生产分层变更只能由最新 24M 报告驱动 + A4 守卫测试同步。

---

## 1. 现状短板画像（24M 实测，优化空间所在）

| 策略 | 层级 | 成交 | PF | 单笔 | 回撤 | 季度稳定 | walk-forward | OOS（quarter_proxy） | 短板 |
|---|---|---:|---:|---:|---:|---|---|---|---|
| 首板回调 `first_board` | CORE | 1064 | 2.63 | 1.122% | -5.42% | 7/8 正 | **7/7 pass** | **46 笔，PF 0.75，-1.01%** | 样本内极强、**最近季度代理失效**——最大红旗 |
| 量能低吸 `volume_shrink` | CORE | 510 | 1.66 | **0.619%** | **-13.24%** | 7/8 正 | 6/7 pass | 15 笔，PF 0.90 | 回撤最大、单笔最薄（成本敏感）、OOS<1 |
| 收盘强势承接 `late_session_strong_support` | AUX(限权) | 58 | 2.24 | 1.347% | -7.74% | 6/8 正 | **0/7 pass** | 5 笔，PF 2.56 | 时序极不稳 + 样本稀，限权是对的 |

退役在研：`n_pattern_long_wash`（PF 1.15，-51%）、`n_pattern_short_wash`（PF 0.72，-88%，删除候选）、`core_midcap_vwap_ma5_retrace`（PF 0.68）、两个主线策略（各 2 笔不可评估）。

---

## 2. 工作包（S1–S8，按预期 ROI 排序）

### S1 出场优化：分层止盈 + 移动止损 + 时间止损（全局最大胜率杠杆）

- **依据**：回测已记录 `max_gain_5d` vs `return_5d`（`low_buy_market_backtest_reporting.py:52-54`），策略追踪大量"冲高未止盈"标签——**浮盈回吐是吃掉胜率的主因**。当前出场为固定 5 日口径 + 单一 `stop_loss/take_profit`（`base_strategy.py:36-37`），无分层/移动/时间止损（playbook §4 明文要求三件套）。
- **动作**（研究态回测，不动生产）：
  1. 量化"回吐池"：统计三策略中 `max_gain_5d ≥ 3%` 但 `return_5d ≤ 0` 的占比（先确认杠杆大小再设计规则）；
  2. 回测三个出场变体：A=+3% 止盈一半+剩余移动止损至成本上；B=纯移动止损（浮盈 2% 后回撤 1.5% 离场）；C=时间止损（3 日未达 +1% 离场）+ 原规则；
  3. 对照表：每变体 × 每策略输出 胜率/PF/净期望/回撤/max5 组合收益，与基线并排。
- **验证门**：净期望与 PF 不得低于基线 95%；回撤不得放大；max5 真实组合收益不降。任一不达即弃。
- **预期**：volume_shrink（单笔 0.619%）受益最大——锁住一半冲高利润可能把 PF 1.66 拉上一档。
- **工作量**：2–3 人日（回测脚本扩展出场参数化）。

### S2 first_board OOS 失效诊断（最优先，先诊断后动手）

- **依据**：OOS quarter_proxy **PF 0.75 / -1.01%（46 笔）** vs 样本内 PF 2.63——必须先回答"为什么"，否则任何优化都是对着错误病灶下药。
- **动作**：用既有 `strategy_improvement/walkforward.py + temporal_guard.py`，把最近季度 46 笔按 **月份 × market_state × 板块** 拆亏损分布，区分三种假设：① retreat/panic 态未被门控住；② 首板生态变化（炸板率/连板高度）；③ 成本滑点占比异常。
- **验证门**：产出一页诊断报告（`docs/reports/first-board-oos-diagnosis-2026-06-XX.md`），结论必须指向 S3（补门控）或降权或"样本期特例"三选一，**不允许无结论调参**。
- **工作量**：1 人日。

### S3 分市场状态门控精细化（策略 × 状态胜率矩阵）

- **依据**：`market_gate.py` 已有 block/reduce 状态机（reduce 系数 0.62，`RETREAT_STATES` 五态：high_flyer_retreat/risk_release/retreat/weak_market/panic），且 2026-05-28 已做过 block_retreat 的 walk-forward 研究。但当前门控是**全局的**，未按策略区分。
- **动作**：
  1. 出"策略 × 市场状态"胜率/PF 矩阵（24M 数据按 market_state 分桶）；
  2. 若证实 volume_shrink 的 -13.24% 回撤集中于 retreat/panic 态 → 回测"该策略在该状态单独暂停/降权"的变体（first_board 不强制同样处理）；
  3. 与 S2 诊断结论联动（first_board 若是 ① 假设，同样在此处理）。
- **验证门**：变体在 24M + walk-forward 上回撤显著收窄且净期望不降；守卫测试 `test_low_buy_production_scoring` 等全绿；门控规则进 `market_gate` 须带状态级守卫测试。
- **工作量**：2 人日。

### S4 盘中确认扩展至 volume_shrink

- **依据**：`intraday_confirmation.py` 已实现 VWAP 确认 + 尾盘确认（`strategy_requires_intraday_confirmation`），但仅覆盖部分策略集合；N 字家族的 observe_confirmed 模式已有先例与测试（`test_n_pattern_observe_confirmed`、`test_low_buy_intraday_confirmation`）。
- **动作**：回测"volume_shrink + 尾盘站上 VWAP 才确认"变体——预期砍掉一批假信号，代价是样本减少。
- **验证门**：确认后样本 ≥ 原样本 60%（防过滤过度）；胜率与 PF 同升；OOS 复验 PF ≥1。达标才把 volume_shrink 加入确认集合。
- **工作量**：1 人日。

### S5 成本/滑点分桶 + 流动性门槛（playbook §4/§P1 明文项）

- **依据**：volume_shrink 单笔 0.619%——统一滑点常数下，成本误差足以吞掉优势；playbook 要求"按流动性分桶建模，不使用统一滑点常数"。
- **动作**：
  1. 回测端滑点按成交额分桶（如 <5000 万 / 5000 万–2 亿 / >2 亿 三档）重算三策略净期望；
  2. 若薄流动性桶净期望为负 → 抬高候选最低流动性门槛（prefilter 层），把"薄流动性亏损单"在入场前筛掉。
- **验证门**：分桶后报告披露执行假设敏感性区间（S3 报告口径规范）；门槛变体净胜率提升且样本留存 ≥70%。
- **工作量**：1.5 人日。

### S6 信号去相关（组合层）

- **依据**：first_board 1064 + volume_shrink 510 笔，同日同票/同板块重叠会放大组合回撤；`portfolio_backtest_metrics` 已有同票冷却/同板块约束，但**入场端**无重叠统计。
- **动作**：统计两核心策略的同日同票重叠率与重叠笔的相关收益；重叠率 >15% 且重叠笔拖累组合时，回测"同票同日仅保留分高者"变体。
- **验证门**：max5/max10 组合收益与回撤改善；单策略口径不变（只影响组合执行层）。
- **工作量**：1 人日。

### S7 退役策略的"回来的路"（证据驱动，不人工捞）

- **late_session_strong_support**：唯一问题是样本 58 + walk-forward 0/7。**不做人工干预**——继续累积样本，达到 A1 门（成交 ≥100 且 walk-forward ≥4/7）时由守卫测试驱动升权。
- **N 字家族**：raw 信号已证伪（-88%/-51%），但 **"N 字 + 次日确认"observe_confirmed 变体** 值得作为研究候选重新走 24M 回测——确认机制可能正是缺的那块。**研究态，不进生产候选。**
- **验证门**：与所有新策略相同的 A1 门禁（成交 ≥50、PF ≥1.2、回撤 ≥-25%、平均单笔 >0），无例外。
- **工作量**：N 字变体回测 1 人日；late_session 零成本（等样本）。

### S8 打开真实战绩漂移监控（实战反馈闭环）

- **依据**：`track_record_drift` 迁移已就绪但未启用——不开它，线上真实胜率 vs 回测的偏离是盲区，S1–S6 的任何优化都没有实战验证闭环。
- **动作**：启用 track record 账本（仅 `buy_now/soft_buy_now` 入账，复用 `portfolio_backtest_metrics` 口径），月度出"实盘 vs 回测"漂移对照；`DRIFT_ALERT_ENABLED` 保持 false 观察一个月再放开告警。
- **验证门**：账本 append-only、无未来函数（`signal_time/data_cutoff_time` 必填）；漂移结论仅 advisory，不自动改分层。
- **工作量**：已有方案（`2026-05-30-trust-and-data-quality-expansion.md` Batch E），执行 3–5 人日。

---

## 3. 执行顺序

```
S2 诊断（1d，最优先）──→ 结论喂给 S3
S1 出场回测（2-3d，与 S2 并行）──→ 最大全局杠杆
S3 状态门控矩阵（2d，依赖 S2）
S4 确认扩展 / S5 成本分桶 / S6 去相关（各 1-1.5d，可并行）
S7 N 字变体研究（1d，随时可做，研究态）
S8 漂移监控（3-5d，独立，建议尽早启动以便 S1-S6 上线后有实战对照）
```

全部变体回测产物落 `docs/reports/strategy-exit-variants-2026-06-XX.md` 等，口径遵守报告规范：候选池/每日信号等权/真实组合 max5/max10 分列，**无裸"总收益"**。

---

## 4. 硬边界（全程不可破）

1. 不直接改 `strategy_policy.py`、生产排序、`production_score`、风控阈值——分层变更只能由新 24M 报告 + A4 守卫驱动。
2. 所有变体先 research/shadow，过 A1 证据门才进生产；`strategy_engine` 保持 shadow-only。
3. 回测口径不变：前视守卫（信号次日入场）、T+1、真实费用、涨跌停/停牌拒单、`portfolio_backtest_metrics` 唯一组合事实源（出场变体在引擎参数层实现，不并行造引擎）。
4. 缺数据显式降级，不造样本、不裁剪亏损样本。
5. 守卫测试不回退：`test_low_buy_production_scoring`、priority variants、N 字非生产强买、execution model boundary 等 67 项必须全绿。

---

## 5. Definition of Done

- [ ] S2 诊断报告落档，first_board OOS 失效有明确归因（三选一结论）
- [ ] S1 出场变体对照表落档；至少一个变体净期望+胜率+回撤三项同步不劣化才进入生产评审
- [ ] S3 策略×状态矩阵落档；状态级门控（如采纳）带守卫测试
- [ ] S4/S5/S6 各自变体回测有明确"采纳/不采纳"结论与数据
- [ ] S7 N 字 observe_confirmed 变体有 24M 结论（研究态）
- [ ] S8 漂移账本上线，首月对照报告产出
- [ ] 全程 `pytest backend/tests` 全绿；生产口径零漂移；任何生产变更附新 24M 报告证据
