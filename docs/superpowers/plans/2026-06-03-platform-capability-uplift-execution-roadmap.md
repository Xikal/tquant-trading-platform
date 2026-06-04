# 平台能力提升 · 执行总图(2026-06-03)

> **For agentic workers**:REQUIRED SUB-SKILL — superpowers:executing-plans。本文是**执行总图(execution roadmap)**,**不是新需求**——所有具体规格已写在被引用的文档里,本文只串起来给执行序、硬边界、依赖与红线。
>
> **核心原则**(写在最前,所有决策必须遵守):
> 1. **先关账,后扩展**——P0/M1/SEC1 三件未关账,任何"新做"全部不做。
> 2. **执行不写新方案**——本文之外的"再加一份计划文档"在本期内**默认 ❌**。
> 3. **不动业务边界**——策略口径、生产门、买卖语义、合规底线一律不动。
> 4. **每步必有量化验收门**——红即停,绿即提交,失败即回退。

---

## 一、前置硬关账(必做,不关账→后面全部不做)

| ID | 关账项 | 依据文档 | 出口条件(必须全部满足) |
|---|---|---|---|
| **PRE-P0** | 生产策略分层一次性收口(8→3) | `p0-retiering-and-p1-analytics-landing-plan-2026-05-30.md` Part A | `pytest backend/tests` 全绿(含 A4 守卫);线上 `/api/screeners/low-buy/priority-board?strategy_variant=baseline` 不含已退出策略的 `buy_now/soft_buy_now`;研究面板仍可见(确认是重分层非删除) |
| **PRE-M1** | AKeyLevel 物化任务接调度器 | `docs/reports/a-key-level-engine-independent-code-review-2026-06-02.md` M1 + 辅助线需求 §20.2 G4 | 收盘后调度器 enqueue `a_key_level_materialization_refresh`;线上调 `/api/key-levels/stock/<sample>` 返回 `data_quality=ok`(非 `stale`);调度被登记的测试通过 |
| **PRE-SEC1** | 线上切域名 + HTTPS,关不安全 cookie | `docs/reports/full-project-latest-code-review-2026-05-30.md` P1-2 + `PRODUCTION_RUNBOOK.md` HTTPS 段 | `https://<domain>` 证书有效;线上 env `AUTH_COOKIE_SECURE=true`、`AUTH_ALLOW_INSECURE_HTTP_COOKIE` 未开;裸 IP HTTP 入口下线或仅供无账号演示 |

**红线**:PRE 三件**串行关账**,任一未达标就回到这一步,不进下面的 Phase 1。

---

## 二、执行串行链(5 件,依赖序明确)

```
PRE 关账(P0 + M1 + SEC1)
  └─▶ Phase 1  数据质量 SLA + 修复管道(D)            ← 地基,先做
          └─▶ Phase 2  战绩漂移监控(E)               ← 信任锚,依赖 D
                  └─▶ Phase 3  AKeyLevel/辅助线收尾    ← 用户可感
                          └─▶ Phase 4  策略晋级引擎闭环  ← 治理闭环
                                  └─▶ Phase 5  观察池/复盘套件 M1
```

**强制顺序的理由**(不可调换):
- D(数据 SLA)未建,E(漂移)的 realized 计算缺失值/脏行没人挡 → E 出来的结果不可信 → 信任锚反成"误导锚"。
- E(漂移)未建,Phase 4 晋级闭环就缺"实战证据"这一通道,只能靠 24M 报告单源。
- Phase 3 是用户可感的"已写完没接线"修复,做完后对外能讲故事;但**口径仍依赖 D 的 SLA**,所以放在 D/E 之后。
- Phase 4/5 是治理闭环和外围套件,必须在前 3 件稳了之后做,否则会被守卫打回。

---

## 三、Phase 1｜数据质量 SLA + 修复管道(D)

- **依据**:`docs/superpowers/plans/2026-05-30-trust-and-data-quality-expansion.md` Batch D(D1–D4)
- **工作量**:约 4–6 人日
- **不重复需求**(已在原文档),本节只给执行守则与红线:
  - 触发硬规则:`DATA_REPAIR_AUTO_ENABLED=false` **永久谨慎**;删除必须 `--apply` + admin。
  - **绝不臆造价格**:`audit.fabricated` 恒 `False`;`repair_invalid_ohlc.py` 必须备份 + 重抓 + 失败才删 + 审计 JSON,**幂等**。
  - SLA 作为生产/报告/漂移**单一数据门**:Phase 2 起所有 realized/漂移结果必须读它,不再各算各的。
- **验收门**(必须全部通过):
  - `pytest backend/tests/test_data_quality_sla.py test_data_quality_repair.py -q` 全绿。
  - 同 dataset 连跑 dry-run 修复**幂等**(第二次待修复 = 0)。
  - 24M 报告头新增"数据质量 SLA"段,失败时报告 `blocked_by_data`(已实现路径)。
  - 看板可见(设置/管理页懒加载)。
- **回退**:flag `DATA_QUALITY_SLA_ENABLED=false`,生产门回到既有 quality 检查。

---

## 四、Phase 2｜战绩漂移监控(E)— 最高 ROI 信任锚

- **依据**:`docs/superpowers/plans/2026-05-30-trust-and-data-quality-expansion.md` Batch E(E1–E5)
- **当下增量价值**(为什么是最高 ROI):生产集合只剩 3 策略,**只有 paper 真实成交 vs 24M expected 的持续漂移对照**能给这 3 个策略打信任戳;同时是 RESEARCH 策略"回到生产"(A7 "回来的路")的客观证据通道。
- **工作量**:约 5–8 人日
- **执行守则与红线**:
  - **复用 `portfolio_backtest_metrics` 单一组合口径**;有 paper 真实成交时 realized 以真实成交为准。
  - **账本 append-only、无未来函数**:`signal_time / data_cutoff_time / return_start_time` 必填;只统计 `buy_now / soft_buy_now`;`near_entry` 不进生产战绩。
  - **漂移仅产 advisory**:`drift_alerts` 不自动改 `strategy_policy`,只作为 Phase 4 晋级证据通道。
  - 默认 `DRIFT_ALERT_ENABLED=false`,阈值线上观察稳定后再放开告警推送。
- **验收门**:
  - `pytest backend/tests/test_track_record_*` 全绿。
  - 24M 报告新增"真实战绩 vs 回测"段,**无裸"总收益"**;关键策略 PF/avg/max5/max10 与回测对照展示。
  - 漂移结论入 `strategy_drift_snapshots`;`/api/track-record/drift` 只读可用。
  - 策略追踪页新增 `DriftMonitorPanel`(懒加载)。
- **回退**:flag `TRACK_RECORD_ENABLED=false / DRIFT_ALERT_ENABLED=false`,旧功能不受影响。

---

## 五、Phase 3｜AKeyLevel + 辅助线收尾(用户可感,无新功能)

- **依据**:
  - `docs/reports/a-key-level-engine-independent-code-review-2026-06-02.md` 复审 **M1/M3/M4**(物化接调度器 / 缓存换专用表 / 单 payload 治理)
  - `docs/auxiliary-lines-requirements-2026-06-03.md` **§20.1/§20.2(G1/G3/G4)**、**§21.6(L1 自适应选线 + 共振)**
- **当下增量价值**:已写完未接线 → 让线上从 `stale` 变 `ok`;再加 §21 L1 自适应/共振(确定性、零额外风险)= **用户可感的明显能力提升,且无新功能开发**。
- **工作量**:约 6–8 人日
- **执行守则与红线**:
  - **单一候选核心**:辅助线必须复用 `key_levels/engine.py` 的候选生成与合并/评分(§20.1 G1);**禁止第二套合并/评分实现**。
  - **缓存换专用表 + 单 payload 上限 + 精确键读**(§20.2 G3),**不得**沿用 `SystemSetting` 单行大 JSON。
  - **`/intraday/{symbol}` 改为读缓存 + `with_intraday` 叠加**(§20.3),GET 端点拒同步重算(沿用现 `_reject_request_time_refresh`)。
  - **L1 自适应/共振只是 `display_priority` + `confluence` 的可解释表达**,确定性、可复现、可解释。**L3 模型辅助本期不做**(§21.6 已写)。
  - **代理口径 = research_only**(§20.1 G24)。
  - **文案守卫不放过**:沿用既有"无 建议买入/卖出/低吸/必涨/突破即买"守卫,覆盖辅助线说明与 `smart_summary`。
- **验收门**:
  - `pytest backend/tests/test_key_levels_*` 全绿;调度任务已登记测试通过。
  - 线上 `/api/key-levels/stock/<sample>` 返回 `data_quality=ok`(非 `stale`);代理 scope 仍 `research_only`。
  - `/intraday` 端点不再做请求时全量日线重算(读缓存 + 叠加)。
  - 单 payload 体积、缓存条数有上界守卫;无 `LIKE prefix:%` 扫描。
- **回退**:flag `TQUANT_AUXILIARY_LINES_ENABLED=false / TQUANT_AUXILIARY_LINES_SMART_ENABLED=false`,前端入口隐藏。

---

## 六、Phase 4｜策略晋级引擎闭环(已有 + 打通)

- **依据**:`promotion_engine.py`(`can_apply_override=False` 永久)、`strategy_auto_governance.py:129-156`、A7 "回来的路"、辅助线需求 §20.4(防未来函数 + 数据冻结)
- **当下增量价值**:让"24M 报告 → 策略调整建议 → A4 守卫强制 `strategy_policy.py` 一致"真正闭环,**而不是手改常量**。退出生产的 5 策略(N 字 + 中军/分歧/涨停缩量)有客观回流路径。
- **工作量**:约 3–5 人日(主要是接调度 + 守卫断言 + 报告→分层流水)
- **执行守则与红线**(必须焊死):
  - **晋级仅产建议,绝不自动生效**:`PROMOTION_ENGINE_AUTO_APPLY_ENABLED` 永久 `false`;`can_apply_override` 恒 `false`。
  - **不绕过 `participates_in_priority_board` 单一门禁**;层级变更**唯一**路径 = 人工改 `strategy_policy.py` 常量 + A4 守卫测试。
  - **晋级证据 = 24M 报告 + Phase 2 漂移结论双源**(strategy_drift_snapshots 作为辅助证据)。
  - 自动治理(`strategy_auto_governance`)只在 MySQL 线上跑,基于"近期实盘快照";SQLite 默认不跑(沿用现有)。
- **验收门**:
  - `pytest backend/tests/test_decision_context_promotion_engine.py test_low_buy_strategy_replacement.py test_low_buy_production_scoring.py` 全绿。
  - 守卫测试 `test_core_aux_strategies_match_latest_24m_report` 通过(分层与最新 24M 报告一致)。
  - 晋级面板只显示建议、`can_apply_override=false`、无任何自动改层链路。
  - N 字守卫不回退:baseline 榜无 `n_pattern_*` 的 `buy_now/soft_buy_now`。
- **回退**:flag `DECISION_CONTEXT_ENABLED=false`,晋级面板隐藏,旧治理不受影响。

---

## 七、Phase 5｜观察池 / 复盘 / 纪律套件 M1(对外能力升级)

- **依据**:`docs/trading-experience-observation-suite-requirements-2026-06-02.md` M1(A / B / C 三个能力)
- **当下增量价值**:生产集合只 3 策略时,用户期待会落到"我自己持仓怎么办、复盘怎么做"——观察池/复盘/风险标签/相对强度**恰好定位于此**,且全部 flag-off 研究态、**不进生产排序**。
- **工作量**:M1 约 6–9 人日(A/B/C 分别 ~3 人日)
- **执行守则与红线**:
  - **全套 flag-off 研究态、不进 priority board 生产排序、不产 `production_score`、不喊买卖、不推荐个股**(沿用 PRD 硬边界 1–8)。
  - **复用既有引擎**:风险标签复用 AKeyLevel + distribution_signals + hard_risk;相对强度复用 sector/leader + 行情;复盘复用 strategy_tracking + 观察池;**禁止并行重建**。
  - **叙事转风险标签**:"出货/洗盘/吸筹" → 价量证据 + `info/warn` 标签 + 失效条件;文案守卫覆盖。
  - M2(D 持仓纪律)、M3(E 涨停后量价 / F 做 T 归因)**本期不做**,留待 Phase 5 验收稳定后单独评估。
- **验收门**:
  - `pytest backend/tests/test_observation_suite_*`(或既有命名)全绿。
  - 复盘页"入池→剔除→跟踪→自检"动线完整;用户操作日志可统计纪律达成率。
  - 量价风险标签**不写入 priority board 排序、不影响 `production_score`**(导入隔离硬断言)。
  - 相对强度榜大跌日可生成;补跌/抗跌仅作为观察事实,不预测涨跌。
- **回退**:对应 flag(`trade_review_suite_enabled / vp_position_tags_enabled / relative_strength_board_enabled`)关闭,入口隐藏。

---

## 八、明确不做(本期边界,违反 = 范围漂移)

- ❌ 不再加新选股策略——证据门禁还在卡 8→3。
- ❌ 不做"智能买卖点 / 智能止损 / 智能仓位"——越界为指令工具。
- ❌ 不加新数据源/新研究池——除非 Phase 1 D-SLA 已建好且达标。
- ❌ 不上 SSR/微前端/换栈/Kafka/K8s/Celery/Cython——反复论证 ROI 为负。
- ❌ 不再写新规划文档——现有方案已饱和,**该执行**。
- ❌ 不在脏 worktree 上开工(沿用 Phase 0 干净基座门)。
- ❌ 不绕过 `participates_in_priority_board` 单一生产门。
- ❌ 不在 Web 主进程新增后台 loop(沿用 `WEB_RUNTIME_BACKGROUND_JOBS_ENABLED=false`)。
- ❌ 不让 `near_entry`/RESEARCH 策略产生 `production_score`。
- ❌ 不在报告里使用裸"总收益"(必须"每日信号等权复利收益 + 真实组合 max5/max10")。

---

## 九、跨阶段硬边界保护清单(每个 Phase 都必跑)

每 Phase 合入前**必须全绿**,否则不进下一 Phase:

| 守卫 | 测试入口 | 防漂移项 |
|---|---|---|
| 策略分层与 24M 一致 | `test_core_aux_strategies_match_latest_24m_report` | A4 不回退 |
| 生产分仅 buy_now/soft_buy_now | `test_low_buy_production_scoring` | production_score 边界 |
| N 字不进 baseline 强买 | `test_baseline_board_excludes_non_production_strong_buy` | P0 不回退 |
| 晋级仅建议、不自动生效 | `test_decision_context_promotion_engine` | B3 边界 |
| 组合 max5/max10 单一实现 | `test_decision_context_portfolio_executor` | 唯一事实源 |
| 文案无买卖指令 | 文案守卫(KeyLevelPanel.test.tsx 等) | 越界文案 |
| 状态分离 / 前端零 useState | `check-state-separation.mjs` / `check-refactor-guard.mjs` | F-架构不回退 |
| 契约同步 | `npm run api:check` | OpenAPI 不漂移 |
| 数据 SLA(Phase 1 后) | `test_data_quality_sla` | 缺数据显式 |
| 战绩 parity(Phase 2 后) | `test_track_record_realized` | realized vs paper 一致 |

---

## 十、量化目标(可对外讲的"明显升级")

按 Phase 累积,**这些指标是改善与否的唯一判据**:

| 维度 | 基线 | 目标 |
|---|---|---|
| 生产策略数量 | 待定(预期 3) | 3(精而真) |
| 24M 报告口径 | 含裸"总收益"(P1-3) | **无裸总收益**;含真实组合 max5/max10 + walk-forward + OOS + 季度稳定性 |
| 数据 SLA fail→生产门 | 部分不显式 | **100% 显式 fail/degraded/blocked_by_data**,生产/报告/漂移共用 |
| 修复管道 | 手工运维 | **可复现脚本 + 强制备份 + `fabricated=false` + 幂等** |
| AKeyLevel 线上 data_quality | `stale` 偏多 | **`ok` 为主**;调度任务被登记 |
| 战绩可追溯 | 无账本 | **每条生产信号可追溯 realized vs expected**;漂移 advisory |
| 晋级闭环 | 手改常量 | **24M 报告 → 建议 → 守卫强一致**(不自动改) |
| 观察池/复盘/相对强度 | 无 | **flag-off 研究态可用**,不进生产排序 |
| HTTPS | 裸 IP HTTP | `https://<domain>` 证书有效,cookie 安全 |
| `pytest backend/tests` | 全绿 | **全绿且守卫覆盖更广** |

---

## 十一、进度与节奏(单人开发参考)

```
Week 1   PRE 关账(P0 + M1 + SEC1)
Week 2   Phase 1 D — 数据 SLA + 修复管道
Week 3-4 Phase 2 E — 战绩漂移监控
Week 5   Phase 3 AKeyLevel/辅助线收尾 + L1 自适应
Week 6   Phase 4 晋级闭环
Week 7-8 Phase 5 观察池/复盘/相对强度 M1
```

每周交付一份"Phase X 验收报告":贴出测试输出、`/metrics` 截图、线上接口抽测原文。**未达验收门 → 该周回退到上 Phase,不前推。**

---

## 十二、执行铁律(给实施 agent)

1. **不写新方案**——所有需求都在引用文档里,本文是路标。
2. **Phase 串行**——上一 Phase 验收门全绿才能开下一 Phase。
3. **每 Task 一 commit**——禁 `git add -A/.`;只显式 add。
4. **干净 worktree 开工**——脏改动先整理出独立提交,再开新工作。
5. **失败立即回退**——flag 关闭机制对每个 Phase 都已就绪。
6. **不做"看起来 OK"判断**——只贴真实输出做判读。
7. **不绕硬边界**——硬边界违反 = 立即停止 + 回退 + 报告,不"先做后修"。

---

## 十三、一句话总结

**这份总图的全部内容是"按 D→E→关键位收尾→晋级闭环→复盘套件 的顺序,把已经写好的方案逐一执行掉",不加新需求、不动业务边界、每 Phase 都有量化验收门和回退路径。** 关账三件(P0 + M1 + SEC1)是入场券;5 件 Phase 是路径;硬边界 + 量化目标是判据。**当前不缺方案,缺的是把方案执行干净。**
