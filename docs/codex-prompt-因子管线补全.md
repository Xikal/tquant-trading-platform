# Codex 任务：补全因子管线 —— 3 个已实现但未接入的因子

## 背景

因子扩容方案已实现 11 个因子中的 8 个完整接入。剩余 3 个因子（sector_flow、big_order_flow、event_risk）的核心逻辑在 `factor_external.py` 中已写好，`shared.py` 的 FACTOR_WEIGHTS 也已配好权重，但它们从未被调用，等于空转。

## 需要修改的文件（共 3 个）

1. `backend/app/services/low_buy/factor_types.py` —— 给 FactorContext 加两个字段
2. `backend/app/services/low_buy/screening.py` —— 填充 sector_flow_ranks；传入 symbol 和 retracement_days
3. `backend/app/services/low_buy/candidate.py` —— 在 _factor_scores 中调用 factor_external 的两个因子

---

## 修改 1：factor_types.py —— 扩展 FactorContext

**文件**：`backend/app/services/low_buy/factor_types.py`

**当前代码**（第 7-15 行）：
```python
@dataclass(frozen=True)
class FactorContext:
    """因子评估所需的跨候选上下文。"""

    sector_pass_counts: dict[str, int] = field(default_factory=dict)
    sector_flow_ranks: dict[str, float] = field(default_factory=dict)
    current_sector: str = ""
    confirmed_trade_date: str = ""
    current_date: str = ""
    total_strategies: int = 0
```

**修改为**：
```python
@dataclass(frozen=True)
class FactorContext:
    """因子评估所需的跨候选上下文。"""

    sector_pass_counts: dict[str, int] = field(default_factory=dict)
    sector_flow_ranks: dict[str, float] = field(default_factory=dict)
    current_sector: str = ""
    current_symbol: str = ""         # 新增：当前候选股代码，供 external 因子使用
    retracement_days: int = 0        # 新增：当前候选回撤天数，供 big_order_flow 因子使用
    confirmed_trade_date: str = ""
    current_date: str = ""
    total_strategies: int = 0
```

---

## 修改 2：screening.py —— 两处改动

**文件**：`backend/app/services/low_buy/screening.py`

### 2a：文件顶部的 import 区域（约第 18 行）

在现有 import 块中追加一行：

```python
from app.services.low_buy.factor_external import resolve_sector_flow_ranks
```

插入位置：放在 `from app.services.low_buy.factor_types import FactorContext` 下面即可。

### 2b：`_build_factor_context` 方法（约第 551-559 行）

**当前代码**：
```python
@staticmethod
def _build_factor_context(item, sector_counts: dict[str, int], latest_trade_date: str) -> FactorContext:
    return FactorContext(
        sector_pass_counts=sector_counts,
        current_sector=item.industry or "未分类",
        confirmed_trade_date=latest_trade_date,
        current_date=latest_trade_date,
        total_strategies=1,
    )
```

**修改为**：
```python
@staticmethod
def _build_factor_context(item, sector_counts: dict[str, int], latest_trade_date: str, sector_flow_ranks: dict[str, float] | None = None) -> FactorContext:
    return FactorContext(
        sector_pass_counts=sector_counts,
        sector_flow_ranks=sector_flow_ranks or {},
        current_sector=item.industry or "未分类",
        current_symbol=getattr(item, "symbol", ""),
        retracement_days=getattr(item, "retracement_days", 0),
        confirmed_trade_date=latest_trade_date,
        current_date=latest_trade_date,
        total_strategies=1,
    )
```

### 2c：`_screen_sync` 方法中构建 FactorContext 的调用点（约第 389-407 行）

**当前代码**：
```python
factor_sector_counts = self._build_factor_sector_counts(scan_targets)

evaluated: list[LowBuyCandidateOut] = []
for item in scan_targets:
    candidate = self._evaluate_candidate(
        item=item,
        latest_trade_date=latest_trade_date,
        history=histories.get(item.symbol),
        strategy=strategy,
        hot_industries=hot_industries,
        market_regime=market_regime,
        factor_context=self._build_factor_context(
            item=item,
            sector_counts=factor_sector_counts,
            latest_trade_date=latest_trade_date,
        ),
    )
```

**修改为**：
```python
factor_sector_counts = self._build_factor_sector_counts(scan_targets)

# 预获取板块资金流向排名（所有候选共享同一份数据）
sector_flow_ranks = resolve_sector_flow_ranks()

evaluated: list[LowBuyCandidateOut] = []
for item in scan_targets:
    # 给 item 附加回撤天数，供 _build_factor_context 使用
    if not hasattr(item, "retracement_days"):
        item.retracement_days = 0
    candidate = self._evaluate_candidate(
        item=item,
        latest_trade_date=latest_trade_date,
        history=histories.get(item.symbol),
        strategy=strategy,
        hot_industries=hot_industries,
        market_regime=market_regime,
        factor_context=self._build_factor_context(
            item=item,
            sector_counts=factor_sector_counts,
            latest_trade_date=latest_trade_date,
            sector_flow_ranks=sector_flow_ranks,
        ),
    )
```

---

## 修改 3：candidate.py —— 接入两个 external 因子

**文件**：`backend/app/services/low_buy/candidate.py`

### 3a：import 区域（约第 22-23 行）

在现有 `from app.services.low_buy.factor_types import FactorContext` 下面追加：

```python
from app.services.low_buy.factor_external import (
    evaluate_big_order_flow_factor,
    evaluate_event_risk_factor,
)
```

### 3b：`_factor_scores` 方法（约第 346-360 行）

**当前代码**：
```python
@staticmethod
def _factor_scores(metrics: CandidateMetrics, context: FactorContext | None = None) -> dict[str, float]:
    scores = {
        "deep_pullback_factor": evaluate_deep_pullback_factor(metrics),
        "trend_rebound_factor": evaluate_trend_rebound_factor(metrics),
        "shrink_quality_factor": evaluate_shrink_quality_factor(metrics),
        "gap_risk_factor": evaluate_gap_risk_factor(metrics),
        "volatility_regime_factor": evaluate_volatility_regime_factor(metrics),
        "time_efficiency_factor": evaluate_time_efficiency_factor(metrics),
        "price_structure_factor": evaluate_price_structure_factor(metrics),
        "sector_density_factor": evaluate_sector_density_factor(context),
        "sector_flow_factor": evaluate_sector_flow_factor(context),
        "signal_freshness_factor": evaluate_signal_freshness_factor(context),
        "absorption_quality_factor": evaluate_absorption_quality_factor(),
    }
    return {key: value for key, value in scores.items() if value > 0}
```

**修改为**：
```python
@staticmethod
def _factor_scores(metrics: CandidateMetrics, context: FactorContext | None = None) -> dict[str, float]:
    scores = {
        "deep_pullback_factor": evaluate_deep_pullback_factor(metrics),
        "trend_rebound_factor": evaluate_trend_rebound_factor(metrics),
        "shrink_quality_factor": evaluate_shrink_quality_factor(metrics),
        "gap_risk_factor": evaluate_gap_risk_factor(metrics),
        "volatility_regime_factor": evaluate_volatility_regime_factor(metrics),
        "time_efficiency_factor": evaluate_time_efficiency_factor(metrics),
        "price_structure_factor": evaluate_price_structure_factor(metrics),
        "sector_density_factor": evaluate_sector_density_factor(context),
        "sector_flow_factor": evaluate_sector_flow_factor(context),
        "signal_freshness_factor": evaluate_signal_freshness_factor(context),
        "absorption_quality_factor": evaluate_absorption_quality_factor(),
    }
    # 外部数据因子（仅在上下文可用时计算；盘后回测时 context 为 None 则跳过）
    if context is not None and context.current_symbol:
        scores["big_order_flow_factor"] = evaluate_big_order_flow_factor(
            symbol=context.current_symbol,
            retracement_days=context.retracement_days,
        )
        scores["event_risk_factor"] = evaluate_event_risk_factor(
            symbol=context.current_symbol,
        )
    return {key: value for key, value in scores.items() if value > 0}
```

---

## 验收标准

改完后跑以下检查确认管线接通：

```bash
# 1. 确认 factor_external 的导入存在于 candidate.py 和 screening.py
grep -n "factor_external" backend/app/services/low_buy/candidate.py
grep -n "factor_external" backend/app/services/low_buy/screening.py

# 2. 确认 FACTOR_WEIGHTS 中三个因子的 key 与 _factor_scores 输出的 key 一致
grep -n "big_order_flow_factor\|event_risk_factor\|sector_flow_factor" backend/app/services/low_buy/shared.py
grep -n "big_order_flow_factor\|event_risk_factor\|sector_flow_factor" backend/app/services/low_buy/candidate.py

# 3. 确认 FactorContext 中有 current_symbol 和 retracement_days 字段
grep -n "current_symbol\|retracement_days" backend/app/services/low_buy/factor_types.py

# 4. 确认 _build_factor_context 接受 sector_flow_ranks 参数
grep -n "sector_flow_ranks" backend/app/services/low_buy/screening.py
```

**逻辑验收**：启动后端，触发一次筛选，在日志或响应中确认 candidate.factor_scores 中出现 `big_order_flow_factor`、`event_risk_factor` 的 key（值可以是 0，但 key 必须存在）。

---

## 注意事项

- `evaluate_big_order_flow_factor` 内部有 akshare 网络请求，但它自带 5 分钟缓存（`_BIG_ORDER_CACHE`），同一只股票在缓存期内不会重复请求
- `evaluate_event_risk_factor` 同理，自带 30 分钟缓存
- `resolve_sector_flow_ranks` 在 `_screen_sync` 中只调用一次，结果共享给所有候选——不需要每只股票重新请求
- 修改 `FactorContext` 新增字段后，检查 `screening.py` 中所有构造 `FactorContext(...)` 的地方是否都已填充新字段（当前只有 `_build_factor_context` 一处构造）
- 如果 `BoardCandidate` 上没有 `retracement_days` 属性，screening.py 的修改 2c 已经做了 `hasattr` 保护，回退到 0（此时 big_order_flow 因子取最近 5 天数据，可以接受）
