# Main Force Model Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将“主力结构识别 + 买点分级 + 风险解释”模型从当前旁路组件升级为生产可用能力，先进入生产只读展示、模拟盘只读展示和 Shadow 记录，再在样本外与 Shadow 验证达标后受控影响候选排序和模拟盘小仓建议。

**Architecture:** 复用现有低吸候选主路径、`MarketModelObservation` Shadow 观测表、策略治理、模拟盘推荐导入路径和前端选股宝典卡片体系。模型不新建独立交易通道，不绕过低吸候选、风控、模拟盘和自动交易约束；所有生产影响通过配置开关、排序加权上限、模拟盘建议开关、观测指标和回滚开关控制。

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic、React + TypeScript + Ant Design、pytest/Vitest/Playwright、SQLite/MySQL 兼容、现有 `market_model_observations` Shadow 表。

---

## 1. 背景与当前状态

当前代码库已有主力模型基础文件：

- `backend/app/services/low_buy/main_force_model_features.py`
- `backend/app/services/low_buy/main_force_model_labels.py`
- `backend/app/services/low_buy/main_force_model_schema.py`
- `backend/app/services/low_buy/main_force_model_advisor.py`
- `backend/scripts/main_force_model_dataset.py`
- `backend/tests/test_main_force_model_features.py`
- `backend/tests/test_main_force_model_labels.py`
- `docs/reports/main-force-accumulation-washout-markup-model-report-2026-05-28.md`

但当前实现仍是旁路状态：

- `MainForceAdvice.shadow_only=True`。
- `MainForceAdvice.production_effect="none"`。
- 没有接入 `LowBuyCandidateOut` schema。
- 没有接入 `/screeners/low-buy`、`/app/low-buy`、BFF 或前端页面。
- 没有每日 Shadow 记录、结算和晋级报告。
- 没有排序影响、没有生产命中指标、没有线上展示入口。

本开发目标不是直接自动交易，而是把模型纳入生产系统的可观测、可回滚、可验证路径。

## 2. 生产使用定义

“投入生产使用”分三档，必须逐档晋级：

| 档位 | 名称 | 用户可见 | 影响排序 | 影响交易 | 进入条件 |
|---|---|---:|---:|---:|---|
| P0 | 生产旁路展示 | 是 | 否 | 否 | 后端可稳定生成 advice，前端只读展示，Shadow 自动记录 |
| P1 | 生产排序加权 | 是 | 是，权重受限 | 否 | 样本外 + Shadow 达标，配置开关启用 |
| P2 | 模拟盘小仓建议 | 是 | 是 | 仅模拟盘建议，不自动实盘、不自动下单 | 至少 3 个月 Shadow 达标，策略治理允许 |

本轮开发文档目标覆盖 P0、P1 和 P2 的完整工程路径。P2 默认先做模拟盘只读展示与 Shadow 对账，只有达标后才允许打开模拟盘小仓建议。

硬约束：

- 不直接实盘下单。
- 不突破现有风险阻断。
- 不覆盖硬止损、ST/退市/停牌、数据质量异常、退潮市场阻断。
- 不使用未来数据。
- 不把 `blocked`、`distribution_risk` 当作正向排序因素。
- 不让模型直接生成模拟盘自动委托；模拟盘首发只能展示建议和记录对账。
- 所有 fallback 必须写入指标或 Shadow payload。

## 3. 目标行为

### 3.1 后端输出

每个低吸候选可带一个只读字段：

```json
{
  "main_force_advice": {
    "model": "main-force-accumulation-washout-markup-v1",
    "stage": "washout",
    "stage_text": "洗盘确认",
    "action": "buy_probe",
    "action_text": "小仓试买",
    "score": 68.5,
    "confidence": 0.685,
    "buy_zone": [10.12, 10.42],
    "stop_loss": 9.72,
    "take_profit_plan": [
      { "level": "first", "price": 11.18, "action": "sell_30" }
    ],
    "reasons": ["近 10 日出现适中回撤，符合洗盘候选。"],
    "risk_flags": [],
    "feature_snapshot": {},
    "shadow_only": true,
    "production_effect": "readonly_shadow",
    "fallback_reason": null
  }
}
```

### 3.2 前端展示

选股宝典和策略工作台候选详情展示：

- 主力阶段：建仓 / 洗盘 / 拉升确认 / 出货风险 / 不可用。
- 买点分级：观察 / 等确认 / 小仓试买 / 确认买点 / 阻断。
- 分数与置信度。
- 买点区间、止损位、止盈计划。
- 3 条以内证据。
- 风险阻断原因。
- 数据质量与模型状态。
- 明确标识：`旁路观察，不自动下单` 或 `已参与排序，权重 X%`。

### 3.3 Shadow 记录

每天对生产候选记录：

- symbol/name/strategy_key/trade_date。
- 当前低吸规则信号。
- 主力模型 stage/action/score/confidence。
- 模型建议买点、止损、止盈计划。
- 特征快照。
- fallback reason。
- 后续 1/3/5/10/20/40 日收益和最大不利波动。
- 是否先到止盈、是否先到止损。
- 是否相对原排序改善。

### 3.4 模拟盘接入

模拟盘接入分两层：

1. 只读展示与对账：在模拟盘持仓、今日动作、从今日推荐导入弹窗中展示主力模型建议；不改变自动交易、不自动生成委托。
2. 小仓建议：Shadow 和样本外验证达标后，只允许影响模拟盘的“建议仓位上限、导入推荐优先级、风险提示”，仍不直接下单。

模拟盘展示字段：

- `main_force_advice.stage_text`：建仓、洗盘、拉升确认、出货风险。
- `main_force_advice.action_text`：观察、等确认、小仓试买、确认买点、阻断。
- `main_force_advice.score` / `confidence`。
- `main_force_advice.buy_zone`、`stop_loss`、`take_profit_plan`。
- `reasons` 和 `risk_flags`。
- `production_effect`：`paper_readonly_shadow`、`paper_small_position_suggestion`、`none`。

模拟盘小仓建议必须满足：

- 原低吸候选已经可买或接近买点。
- 模型 action 为 `buy_probe` 或 `buy_confirmed`。
- 模型 risk_flags 为空。
- 当前模拟盘风控允许买入。
- 单票仓位不超过现有模拟盘风控上限和模型建议上限的较小值。
- 不覆盖现有硬止损、日亏损暂停、最大持仓数、最低现金保留。

## 4. 配置开关

在 `backend/app/core/config.py` 增加：

```python
main_force_model_enabled: bool = True
main_force_model_shadow_enabled: bool = True
main_force_model_display_enabled: bool = True
main_force_model_ranking_enabled: bool = False
main_force_model_paper_display_enabled: bool = True
main_force_model_paper_shadow_enabled: bool = True
main_force_model_paper_suggestion_enabled: bool = False
main_force_model_max_rank_bonus: float = 4.0
main_force_model_min_confidence: float = 0.58
main_force_model_min_score: float = 55.0
main_force_model_paper_max_position_pct: float = 3.0
main_force_model_paper_min_confidence: float = 0.62
main_force_model_shadow_sample_min: int = 300
main_force_model_shadow_settled_min: int = 120
main_force_model_min_success_rate_pct: float = 52.0
main_force_model_min_profit_factor: float = 1.35
main_force_model_allowed_strategies: str = "leader_pullback_band,volume_shrink,breakout_support,n_pattern_long_wash,core_midcap_vwap_ma5_retrace"
```

生产默认：

- 展示和 Shadow 可开启。
- 排序影响默认关闭。
- 模拟盘只读展示和 Shadow 可开启。
- 模拟盘小仓建议默认关闭。
- 排序影响只能由管理员配置开启。
- 模拟盘小仓建议只能由管理员配置开启。
- 排序 bonus 有硬上限。
- 模拟盘仓位建议有硬上限。

## 5. 涉及文件

### 后端新增

- `backend/app/services/low_buy/main_force_model_shadow.py`
  - 负责记录、读取、汇总、结算主力模型 Shadow。
- `backend/app/services/low_buy/main_force_model_enrichment.py`
  - 负责从候选和日线历史生成 advice，并挂到候选。
- `backend/scripts/main_force_model_backtest.py`
  - 最近两年规则模型 walk-forward/样本外验证脚本。
- `backend/scripts/evaluate_main_force_model_shadow.py`
  - Shadow 结算和晋级评估脚本。
- `backend/app/services/paper/main_force_paper_advisor.py`
  - 负责把主力模型 advice 转成模拟盘只读提示和小仓建议。
- `backend/tests/test_main_force_model_shadow.py`
  - Shadow upsert、summary、settle 测试。
- `backend/tests/test_main_force_model_enrichment.py`
  - 候选增强、fallback、排序不开启时不改变 score 测试。
- `backend/tests/test_main_force_model_temporal_guard.py`
  - 防未来函数测试。
- `backend/tests/test_main_force_model_paper_advisor.py`
  - 模拟盘只读展示、小仓建议门槛、风控不覆盖测试。

### 后端修改

- `backend/app/core/config.py`
  - 增加配置项。
- `backend/app/models/schema_defs/screener_parts/candidate.py`
  - `LowBuyCandidateOut` 增加 `main_force_advice: dict[str, Any] = Field(default_factory=dict)`。
- `backend/app/services/low_buy/main_force_model_schema.py`
  - 增加文本字段、生产影响枚举、观测 key、排序字段。
- `backend/app/services/low_buy/main_force_model_advisor.py`
  - 不再写死 production effect；按配置输出 `readonly_shadow` 或 `ranking_bonus`。
- `backend/app/services/low_buy/candidate.py`
  - 在候选构建完成后调用 enrichment。
- `backend/app/services/low_buy/priority_scoring.py`
  - 在排序开启且达标时应用受限 bonus。
- `backend/app/services/strategy_improvement/report.py`
  - 增加主力模型 Shadow 状态。
- `backend/app/api/routes/screeners.py`
  - 保持字段兼容，必要时增加 `include_main_force=true` 参数，默认启用展示。
- `backend/app/api/routes/backtests.py`
  - 增加管理员研究接口或脚本入口，返回主力模型验证报告。
- `backend/app/api/routes/paper_serializers.py`
  - 持仓序列化时附加 `main_force_advice` 或 `main_force_paper_advice` 只读字段。
- `backend/app/services/paper/scheduler.py`
  - 从今日推荐导入或自动扫描时记录模型对账，不直接自动下单。
- `backend/app/services/paper/admission.py`
  - 小仓建议启用后，仍先走原模拟盘准入和风控校验。
- `backend/app/services/paper/risk_control.py`
  - 确认模型建议不能突破单票仓位、日亏损暂停、最大持仓数、最低现金保留。

### 前端修改

- `frontend/src/types/playbookCore.ts`
  - 增加 `MainForceAdvice` 类型和 `LowBuyCandidate.main_force_advice?`。
- `frontend/src/features/workspace-shared/workspaceViewModels.ts`
  - 候选卡片 view model 增加主力模型摘要。
- `frontend/src/features/playbook/PlaybookPage.tsx`
  - 候选列表/详情展示主力阶段和买点等级。
- `frontend/src/features/trading-workspace/WorkspacePageContent.tsx`
  - 策略工作台候选卡片展示只读模型摘要。
- `frontend/src/types/paper.ts`
  - 增加模拟盘 `main_force_advice` / `main_force_paper_advice` 类型。
- `frontend/src/features/paper/PaperTradingSections.tsx`
  - 持仓和今日动作中展示主力模型只读建议。
- `frontend/src/features/paper/PaperOrderEntryModal.tsx`
  - 从今日推荐导入时展示主力模型阶段、风险和建议仓位，不自动提交订单。
- `frontend/src/features/paper/PaperDetailTabs.tsx`
  - 增加或复用子页展示主力模型 Shadow 对账。
- `frontend/src/mobile/mobileSections.tsx`
  - 移动端候选详情展示压缩版主力模型提示。

## 6. 数据与表设计

优先复用 `market_model_observations`，不新增表。

模型 key：

```text
main_force_accumulation_washout_markup_v1
```

`signal_state` 映射：

| advice.action | signal_state |
|---|---|
| observe | observe |
| wait_confirm | wait_confirm |
| buy_probe | buy_probe |
| buy_confirmed | buy_confirmed |
| blocked | blocked |

`payload_json` 必须包含：

```json
{
  "as_of": "2026-05-28",
  "strategy_key": "volume_shrink",
  "rule_score_before": 75.2,
  "rule_signal_state": "near_entry",
  "model_advice": {},
  "feature_snapshot": {},
  "fallback_reason": null,
  "production_effect": "readonly_shadow",
  "rank_bonus": 0.0,
  "outcome": {}
}
```

结算 outcome：

```json
{
  "return_1d_pct": 0.0,
  "return_3d_pct": 0.0,
  "return_5d_pct": 0.0,
  "return_10d_pct": 0.0,
  "return_20d_pct": 0.0,
  "return_40d_pct": 0.0,
  "max_favorable_20d_pct": 0.0,
  "max_adverse_20d_pct": 0.0,
  "hit_stop_loss_20d": false,
  "first_profit_before_stop": false,
  "success": false
}
```

## 7. 排序影响规则

排序影响必须满足全部条件：

- `main_force_model_ranking_enabled=True`。
- `shadow_summary.promotion_ready=True`。
- strategy 在 `main_force_model_allowed_strategies`。
- candidate 数据质量为 fresh/verified/ok。
- advice.action in `buy_probe`, `buy_confirmed`。
- advice.stage in `washout`, `markup_confirm`。
- advice.confidence >= `main_force_model_min_confidence`。
- advice.score >= `main_force_model_min_score`。
- risk_flags 为空。
- candidate.risk_tier != `block`。

bonus 计算：

```text
raw_bonus = (advice.score - min_score) / (100 - min_score) * max_rank_bonus
action_multiplier = 1.0 for buy_confirmed, 0.65 for buy_probe
rank_bonus = min(max_rank_bonus, max(0, raw_bonus * action_multiplier))
```

阻断规则：

- `blocked` 不扣分，只写风险解释，避免二次污染原策略。
- `distribution_risk` 不加分。
- fallback 不加分。
- 排序 bonus 不得改变候选的止损、止盈和硬风险结论。

## 8. 开发任务

### Task 1: Schema 与配置

**Files:**

- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/low_buy/main_force_model_schema.py`
- Modify: `backend/app/models/schema_defs/screener_parts/candidate.py`
- Modify: `frontend/src/types/playbookCore.ts`

- [ ] **Step 1: 后端配置测试**

新增测试断言默认展示/Shadow 开启、排序关闭：

```python
def test_main_force_model_defaults_are_safe():
    from app.core.config import get_settings

    settings = get_settings()
    assert settings.main_force_model_enabled is True
    assert settings.main_force_model_shadow_enabled is True
    assert settings.main_force_model_display_enabled is True
    assert settings.main_force_model_ranking_enabled is False
    assert settings.main_force_model_max_rank_bonus <= 4.0
```

- [ ] **Step 2: 增加 `LowBuyCandidateOut.main_force_advice`**

字段默认空 dict，保证老 payload 可反序列化：

```python
main_force_advice: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 3: 前端类型补齐**

增加：

```ts
export interface MainForceAdvice {
  model?: string;
  stage?: "accumulation" | "washout" | "markup_confirm" | "distribution_risk" | "unavailable" | string;
  stage_text?: string;
  action?: "observe" | "wait_confirm" | "buy_probe" | "buy_confirmed" | "blocked" | string;
  action_text?: string;
  score?: number;
  confidence?: number;
  buy_zone?: [number, number] | number[];
  stop_loss?: number;
  take_profit_plan?: Array<{ level?: string; price?: number; action?: string }>;
  reasons?: string[];
  risk_flags?: string[];
  shadow_only?: boolean;
  production_effect?: string;
  fallback_reason?: string | null;
}
```

并在 `LowBuyCandidate` 增加：

```ts
main_force_advice?: MainForceAdvice;
```

- [ ] **Step 4: 运行测试**

```bash
cd /Users/j/Documents/gupiao
pytest backend/tests/test_backend_refactor_foundation.py -q
npm --prefix frontend test -- --run frontend/src/features/trading-workspace/workspaceViewModels.test.ts
```

### Task 2: 主力模型候选增强服务

**Files:**

- Create: `backend/app/services/low_buy/main_force_model_enrichment.py`
- Modify: `backend/app/services/low_buy/candidate.py`
- Test: `backend/tests/test_main_force_model_enrichment.py`

- [ ] **Step 1: 写候选增强测试**

覆盖：

- 展示开启时候选含 `main_force_advice`。
- 排序关闭时 score 不变。
- 数据不足时 advice 为 unavailable/blocked 且带 fallback。
- 风险 flags 存在时不加分。

- [ ] **Step 2: 实现 enrichment**

核心接口：

```python
def enrich_candidate_with_main_force_model(
    db: Session,
    *,
    candidate: LowBuyCandidateOut,
    history_rows: Iterable[Any],
    market_state: str,
    sector_strength: float,
    market_strength: float,
) -> LowBuyCandidateOut:
    ...
```

实现要求：

- 使用 `build_main_force_features()`。
- 使用 `MainForceAdvisor().advise()`。
- advice 写入 `candidate.main_force_advice`。
- 不在此处直接 commit。
- 异常时返回原 candidate，并写 fallback advice。

- [ ] **Step 3: 接入候选构建**

在 `LowBuyCandidateMixin._evaluate_candidate()` 构建 `LowBuyCandidateOut` 并完成定位后调用 enrichment。

注意：

- 历史数据必须只取 `trade_date <= metrics.latest_trade_date`。
- 不得改变原始 `entry_zone_low/high`、`stop_loss`、`take_profit`。
- 不得绕过 `context_adjustment.execution_blocked`。

- [ ] **Step 4: 运行测试**

```bash
pytest backend/tests/test_main_force_model_enrichment.py -q
pytest backend/tests/test_low_buy_strategy_replacement.py -q
```

### Task 3: Shadow 记录与结算

**Files:**

- Create: `backend/app/services/low_buy/main_force_model_shadow.py`
- Create: `backend/tests/test_main_force_model_shadow.py`
- Modify: `backend/app/services/low_buy/main_force_model_enrichment.py`
- Modify: `backend/app/services/strategy_improvement/model_shadow.py`
- Modify: `backend/app/services/strategy_improvement/report.py`

- [ ] **Step 1: 写 Shadow upsert 测试**

同一 `model_key + symbol + trade_date + signal_state` 重复记录应更新，不新增。

- [ ] **Step 2: 实现 `record_main_force_shadow()`**

复用 `MarketModelObservationService.record()`：

```python
MAIN_FORCE_MODEL_OBSERVATION_KEY = "main_force_accumulation_washout_markup_v1"
```

记录字段：

- `signal_state=advice.action`
- `confidence=advice.confidence`
- `score=advice.score`
- `expected_edge_pct=rank_bonus` 或 0
- payload 存完整 advice 和候选上下文

- [ ] **Step 3: 实现 `summarize_main_force_shadow()`**

输出：

```json
{
  "model_key": "main_force_accumulation_washout_markup_v1",
  "status": "insufficient_shadow_samples",
  "record_count": 0,
  "settled_count": 0,
  "success_rate_pct": 0.0,
  "profit_factor": 0.0,
  "avg_return_20d_pct": 0.0,
  "max_adverse_20d_pct": 0.0,
  "fallback_count": 0,
  "promotion_ready": false,
  "promotion_blockers": []
}
```

- [ ] **Step 4: 接入 enrichment 自动记录**

在 `main_force_model_shadow_enabled=True` 时记录 Shadow。

事务规则：

- 低吸主流程不因 Shadow 写入失败而失败。
- Shadow 写入失败必须 log warning，并在 advice fallback/metrics 体现。

- [ ] **Step 5: 策略闭环报告加入状态**

在策略改进报告中新增 `main_force_model_shadow`，展示：

- 样本数。
- 已结算数。
- 胜率。
- PF。
- 晋级阻断项。
- 当前生产影响。

- [ ] **Step 6: 运行测试**

```bash
pytest backend/tests/test_main_force_model_shadow.py -q
pytest backend/tests/test_strategy_improvement_closed_loop.py -q
```

### Task 4: 排序加权受控接入

**Files:**

- Modify: `backend/app/services/low_buy/priority_scoring.py`
- Modify: `backend/app/services/low_buy/priority_merging.py`
- Test: `backend/tests/test_main_force_model_ranking.py`

- [ ] **Step 1: 写排序保护测试**

覆盖：

- 默认配置下候选排序完全不变。
- ranking enabled 但 Shadow 未达标，不加分。
- 达标且 advice 为 `buy_confirmed` 时加分不超过上限。
- `blocked`、`distribution_risk`、fallback 不加分。

- [ ] **Step 2: 实现 bonus 计算函数**

建议函数：

```python
def main_force_rank_bonus(candidate: LowBuyCandidateOut, *, shadow_status: dict[str, Any]) -> float:
    ...
```

- [ ] **Step 3: 接入 priority scoring**

只在最终排序分里加 `rank_bonus`，不要改变候选原始 `score` 字段。可以新增：

```python
candidate.factor_scores["main_force_rank_bonus"] = bonus
```

或在 priority item payload 中体现。

- [ ] **Step 4: 运行测试**

```bash
pytest backend/tests/test_main_force_model_ranking.py -q
pytest backend/tests/test_strategy_safety_layers.py -q
```

### Task 5: 前端只读展示

**Files:**

- Modify: `frontend/src/types/playbookCore.ts`
- Modify: `frontend/src/features/workspace-shared/workspaceViewModels.ts`
- Modify: `frontend/src/features/playbook/PlaybookPage.tsx`
- Modify: `frontend/src/mobile/mobileSections.tsx`
- Test: `frontend/src/features/playbook/PlaybookPage.test.tsx`
- Test: `frontend/src/features/trading-workspace/workspaceViewModels.test.ts`

- [ ] **Step 1: view model 测试**

断言候选含 `main_force_advice` 时输出：

- `主力洗盘`
- `小仓试买`
- `旁路观察`

- [ ] **Step 2: 选股宝典展示**

在候选行或详情折叠区域增加紧凑展示：

```text
主力：洗盘确认 · 小仓试买 · 68.5
证据：回撤适中；量能未失控；站回均线
风险：无 / 板块强度不足
状态：旁路观察
```

不新增大面积卡片，不破坏当前高密度布局。

- [ ] **Step 3: 移动端展示**

在候选详情中显示一行摘要和一个可折叠说明。

- [ ] **Step 4: 运行测试**

```bash
npm --prefix frontend test -- --run frontend/src/features/playbook/PlaybookPage.test.tsx frontend/src/features/trading-workspace/workspaceViewModels.test.ts
npm --prefix frontend run build
```

### Task 6: 回测、样本外和防未来函数

**Files:**

- Create: `backend/scripts/main_force_model_backtest.py`
- Create: `backend/tests/test_main_force_model_temporal_guard.py`
- Modify: `backend/scripts/main_force_model_dataset.py`
- Create: `docs/reports/main-force-model-production-readiness-2026-05-28.md`

- [ ] **Step 1: 防未来函数测试**

测试必须证明：

- 特征 `max_source_date <= as_of_date`。
- 标签 `label_start_date > as_of_date`。
- T+1 价格不能改变 T 日特征。
- `future_*` 字段不会进入 features。

- [ ] **Step 2: walk-forward 脚本**

脚本参数：

```bash
python backend/scripts/main_force_model_backtest.py \
  --database backend/data/t_quant.db \
  --start 2024-05-28 \
  --end 2026-05-28 \
  --train-months 12 \
  --valid-months 3 \
  --test-months 3 \
  --purged-gap-days 10 \
  --output docs/reports/main-force-model-production-readiness-2026-05-28.json
```

输出：

- 总体胜率。
- PF。
- 平均收益。
- 最大不利波动。
- 分策略表现。
- 分行业表现。
- 分市场状态表现。
- 参数稳定性。
- 未来函数检查结果。

- [ ] **Step 3: 晋级门槛**

进入排序加权必须满足：

| 指标 | 门槛 |
|---|---:|
| 样本外 Profit Factor | >= 1.35 |
| 样本外胜率 | >= 52% |
| 平均单笔收益 | > 交易成本 2 倍 |
| 最大回撤 | 不高于现有低吸基线 |
| 最差市场状态 | 不失控 |
| Shadow 已结算样本 | >= 120 |
| Shadow 观察样本 | >= 300 |
| fallback rate | <= 15% |

- [ ] **Step 4: 运行验证**

```bash
pytest backend/tests/test_main_force_model_temporal_guard.py -q
python backend/scripts/main_force_model_dataset.py --database backend/data/t_quant.db --max-samples 5000
python backend/scripts/main_force_model_backtest.py --database backend/data/t_quant.db --output docs/reports/main-force-model-production-readiness-2026-05-28.json
```

### Task 7: 管理与监控

**Files:**

- Modify: `backend/app/api/routes/backtests.py`
- Modify: `backend/app/api/routes/settings.py`
- Modify: `frontend/src/features/settings/QuantParameterCards.tsx` 或现有参数卡片文件
- Test: `backend/tests/test_main_force_model_admin_routes.py`

- [ ] **Step 1: 管理接口**

管理员可查看：

- 当前配置。
- Shadow 状态。
- 是否允许排序加权。
- 最近 fallback。
- 最近 Top advice。

- [ ] **Step 2: 设置页配置**

新增参数区：

- 主力模型展示。
- 主力模型 Shadow。
- 主力模型排序加权。
- 最大排序加分。
- 最低置信度。
- 允许策略列表。

敏感和高风险开关：

- `main_force_model_ranking_enabled` 必须需要管理员权限。
- 变更写入 FeatureFlagAuditLog 或现有设置审计。

- [ ] **Step 3: 监控指标**

日志/metrics 至少包含：

- `main_force_model.hit`
- `main_force_model.fallback`
- `main_force_model.shadow_recorded`
- `main_force_model.rank_bonus_applied`
- `main_force_model.blocked`

### Task 8: 模拟盘只读展示与小仓建议

**Files:**

- Create: `backend/app/services/paper/main_force_paper_advisor.py`
- Modify: `backend/app/api/routes/paper_serializers.py`
- Modify: `backend/app/services/paper/scheduler.py`
- Modify: `backend/app/services/paper/admission.py`
- Modify: `backend/app/services/paper/risk_control.py`
- Modify: `frontend/src/types/paper.ts`
- Modify: `frontend/src/features/paper/PaperTradingSections.tsx`
- Modify: `frontend/src/features/paper/PaperOrderEntryModal.tsx`
- Modify: `frontend/src/features/paper/PaperDetailTabs.tsx`
- Test: `backend/tests/test_main_force_model_paper_advisor.py`
- Test: `frontend/src/features/trading-workspace/PaperTradingPage.test.tsx`

- [ ] **Step 1: 写模拟盘 advisor 测试**

覆盖：

- `main_force_model_paper_display_enabled=True` 时输出只读 advice。
- `main_force_model_paper_suggestion_enabled=False` 时不生成建议委托、不改变 draft。
- advice 为 `blocked` 或存在 risk_flags 时不给小仓建议。
- 小仓建议不得超过 `main_force_model_paper_max_position_pct`。
- 小仓建议不得超过 `PaperRiskControl` 允许的单票仓位、最大持仓数、最低现金保留。

- [ ] **Step 2: 实现 `main_force_paper_advisor.py`**

核心接口：

```python
def build_main_force_paper_advice(
    *,
    candidate: LowBuyCandidateOut | None,
    main_force_advice: dict[str, Any],
    risk_allowed: bool,
    current_position_pct: float = 0.0,
) -> dict[str, Any]:
    ...
```

输出：

```json
{
  "visible": true,
  "mode": "readonly_shadow",
  "suggestion_enabled": false,
  "action_text": "旁路观察",
  "position_cap_pct": 0.0,
  "order_intent": "none",
  "reasons": [],
  "risk_flags": []
}
```

小仓建议启用且达标时：

```json
{
  "visible": true,
  "mode": "paper_small_position_suggestion",
  "suggestion_enabled": true,
  "action_text": "模拟盘小仓观察",
  "position_cap_pct": 3.0,
  "order_intent": "manual_import_only",
  "reasons": ["主力模型为洗盘确认，且低吸候选已接近买点。"],
  "risk_flags": []
}
```

- [ ] **Step 3: 接入持仓序列化**

在 `paper_serializers.py` 复用当前 `exit_model_shadow` 模式，附加：

```python
"main_force_paper_advice": build_main_force_paper_advice(...)
```

持仓没有对应低吸候选时：

- 返回 `visible=False` 或 `mode="unavailable"`。
- 不让页面报错。

- [ ] **Step 4: 接入今日推荐导入**

在 `PaperOrderEntryModal.tsx` 的“从今日推荐导入”列表里显示：

```text
主力：洗盘确认 · 小仓试买 · 分数 68.5
模拟盘：旁路观察，不自动下单
```

当 `paper_small_position_suggestion` 开启时：

- 只调整建议仓位展示。
- 用户仍需手动点选和提交。
- 不自动调用下单 API。

- [ ] **Step 5: 接入模拟盘详情**

在 `PaperTradingSections.tsx` 或 `PaperDetailTabs.tsx` 中增加紧凑只读块：

- 主力阶段。
- 买点等级。
- 模型止损。
- 止盈计划。
- 风险解释。
- Shadow 状态。

避免新增大面积卡片；默认折叠详细证据。

- [ ] **Step 6: 运行测试**

```bash
pytest backend/tests/test_main_force_model_paper_advisor.py -q
npm --prefix frontend test -- --run frontend/src/features/trading-workspace/PaperTradingPage.test.tsx
```

### Task 9: 上线与回滚

**Files:**

- Modify: `docs/deployment-runbook.md` 或新增 `docs/main-force-model-production-runbook-2026-05-28.md`
- Modify: `.env.example` 如存在
- Test: 线上 smoke

- [ ] **Step 1: 本地完整验证**

```bash
pytest backend/tests/test_main_force_model_features.py backend/tests/test_main_force_model_labels.py backend/tests/test_main_force_model_enrichment.py backend/tests/test_main_force_model_shadow.py backend/tests/test_main_force_model_ranking.py backend/tests/test_main_force_model_temporal_guard.py -q
pytest backend/tests/test_main_force_model_paper_advisor.py -q
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

- [ ] **Step 2: 生产配置首发**

首发配置：

```env
MAIN_FORCE_MODEL_ENABLED=true
MAIN_FORCE_MODEL_SHADOW_ENABLED=true
MAIN_FORCE_MODEL_DISPLAY_ENABLED=true
MAIN_FORCE_MODEL_RANKING_ENABLED=false
MAIN_FORCE_MODEL_PAPER_DISPLAY_ENABLED=true
MAIN_FORCE_MODEL_PAPER_SHADOW_ENABLED=true
MAIN_FORCE_MODEL_PAPER_SUGGESTION_ENABLED=false
MAIN_FORCE_MODEL_MAX_RANK_BONUS=4.0
```

- [ ] **Step 3: 线上 smoke**

验证：

- `/screeners/low-buy` 返回候选，含 `main_force_advice`。
- 选股宝典展示主力阶段。
- `market_model_observations` 出现 `main_force_accumulation_washout_markup_v1`。
- Shadow 写入失败不会导致低吸接口 500。
- 排序关闭时候选顺序和旧版本一致。
- 模拟盘持仓或今日推荐导入中显示主力模型只读建议。
- 模拟盘没有自动生成主力模型委托。

- [ ] **Step 4: 回滚**

紧急回滚只需配置：

```env
MAIN_FORCE_MODEL_ENABLED=false
MAIN_FORCE_MODEL_DISPLAY_ENABLED=false
MAIN_FORCE_MODEL_RANKING_ENABLED=false
MAIN_FORCE_MODEL_PAPER_DISPLAY_ENABLED=false
MAIN_FORCE_MODEL_PAPER_SUGGESTION_ENABLED=false
```

如果仅关闭排序：

```env
MAIN_FORCE_MODEL_RANKING_ENABLED=false
```

## 9. 验收标准

### P0 生产旁路展示验收

- 后端候选含 `main_force_advice`。
- 前端选股宝典/策略工作台可读展示。
- Shadow 每天自动记录。
- 数据不足、风险阻断、fallback 可见。
- 低吸接口 P95 不明显劣化，建议新增耗时不超过 300ms/批。
- 排序关闭时候选顺序不变。
- 测试全部通过。

### P1 生产排序加权验收

- 排序开关默认关闭。
- 开启前必须满足样本外和 Shadow 门槛。
- 排序 bonus 不超过配置上限。
- 加权前后 diff 可审计。
- 任何硬风险阻断优先级高于模型建议。
- 可一键关闭并恢复原排序。

### P2 模拟盘建议验收

- 模拟盘首发只显示建议，不自动下单。
- 模拟盘今日推荐导入弹窗可显示主力阶段、买点等级、风险解释和建议仓位。
- 建议必须带止损、止盈、风险解释、模型状态。
- `main_force_model_paper_suggestion_enabled=False` 时不会生成小仓建议。
- 开启小仓建议前必须至少 3 个月 Shadow 达标，推荐 6 个月。
- 小仓建议不得超过 `main_force_model_paper_max_position_pct`。
- 小仓建议不得突破模拟盘风险控制、日亏损暂停、最大持仓数、最低现金保留。
- 不影响实盘接口。

## 10. 风险与控制

| 风险 | 控制 |
|---|---|
| 过拟合大涨样本 | 时间切分、walk-forward、purged gap、行业/市场分层 |
| 未来函数 | `max_source_date <= as_of_date` 单测和脚本门禁 |
| 模型污染原策略 | 默认不改 score；排序加权用独立 bonus 字段 |
| 错误买点误导用户 | 显示风险解释和 Shadow 状态，不承诺必涨 |
| 数据质量不足 | data_quality 非 fresh/verified/ok 时 blocked/fallback |
| 前端信息过载 | 主列表只显示一行摘要，详情折叠 |
| 性能劣化 | 批量历史查询、缓存、限候选增强、fallback |
| 模拟盘误触发下单 | `paper_suggestion_enabled` 默认关闭，只允许手动导入，不自动提交订单 |
| 线上异常 | 独立开关：enabled/display/ranking/paper_display/paper_suggestion |

## 11. 不做事项

本阶段明确不做：

- 不接实盘自动交易。
- 不用模型覆盖硬止损。
- 不把 blocked 变成负向惩罚污染原策略。
- 不让模型绕过模拟盘原有风控或自动交易约束。
- 不让模型直接创建模拟盘自动委托。
- 不使用逐笔/盘口/龙虎榜作为硬依赖。
- 不训练深度模型。
- 不把所有策略一次性接入排序加权。

## 12. 建议执行顺序

1. Schema 与配置。
2. Enrichment 只读接入。
3. Shadow 记录与结算。
4. 前端只读展示。
5. 回测和防未来函数。
6. 策略闭环报告。
7. 模拟盘只读展示与 Shadow 对账。
8. 排序加权灰度。
9. 模拟盘小仓建议灰度。
10. 线上 smoke 与回滚演练。

## 13. 完成定义

当以下条件全部满足，可认为“已投入生产使用 P0”：

- 线上 `/screeners/low-buy` 候选包含 `main_force_advice`。
- 选股宝典和策略工作台能看到主力结构解释。
- `market_model_observations` 持续记录主力模型 Shadow。
- 排序关闭时原低吸候选结果不变。
- 模型 fallback、blocked、data_quality 都可观测。
- 本地和线上 smoke 通过。

当以下条件全部满足，可认为“已投入生产使用 P1”：

- 样本外和 Shadow 达到晋级门槛。
- 管理员开启 `MAIN_FORCE_MODEL_RANKING_ENABLED=true`。
- 候选排序出现可审计的 `main_force_rank_bonus`。
- 回滚开关验证成功。

当以下条件全部满足，可认为“已投入生产使用 P2”：

- 模拟盘持仓和今日推荐导入能看到 `main_force_paper_advice`。
- `MAIN_FORCE_MODEL_PAPER_SUGGESTION_ENABLED=false` 时只读展示，不产生建议委托。
- 管理员开启 `MAIN_FORCE_MODEL_PAPER_SUGGESTION_ENABLED=true` 后，只给出手动导入的小仓建议。
- 小仓建议受模拟盘风控、现金、持仓数、日亏损暂停约束。
- 模拟盘 Shadow 对账能统计模型建议后的收益、止损、止盈和误判。
