from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


StrategyAction = Literal["retain", "downgrade", "default_off", "delete_candidate"]


@dataclass(frozen=True)
class StrategyRecommendation:
    strategy_key: str
    action: StrategyAction
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_payload(self) -> dict[str, Any]:
        return asdict(self)


def recommend_strategy_action(metrics: dict[str, Any]) -> StrategyRecommendation:
    key = str(metrics.get("strategy_key") or "")
    filled = int(metrics.get("filled_count") or metrics.get("sample_count") or 0)
    profit_factor = _float(metrics.get("profit_factor"))
    avg_trade = _float(metrics.get("avg_trade_return_pct"))
    max_drawdown = _float(metrics.get("max_drawdown_pct"))
    max5 = _float(metrics.get("max5_portfolio_return_pct"))
    max10 = _float(metrics.get("max10_portfolio_return_pct"))
    evidence = {
        "filled_count": filled,
        "profit_factor": profit_factor,
        "avg_trade_return_pct": avg_trade,
        "max_drawdown_pct": max_drawdown,
        "max5_portfolio_return_pct": max5,
        "max10_portfolio_return_pct": max10,
    }
    if key == "n_pattern_short_wash" or profit_factor < 0.9 or avg_trade < -0.1:
        return StrategyRecommendation(key, "delete_candidate", "PF 低于 0.9 或平均单笔为明显负值", evidence)
    if filled < 100:
        return StrategyRecommendation(key, "default_off", "成交样本不足 100", evidence)
    if profit_factor < 1.05 or avg_trade <= 0 or max_drawdown <= -50:
        return StrategyRecommendation(key, "default_off", "收益质量弱或回撤过大", evidence)
    if min(max5, max10) <= 0:
        return StrategyRecommendation(key, "downgrade", "真实组合 max5/max10 未同时为正", evidence)
    return StrategyRecommendation(key, "retain", "样本、PF、平均单笔、回撤和真实组合口径通过", evidence)


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
