from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean, stdev

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import BacktestTrade
from app.services.black_litterman_optimizer import optimize_black_litterman_portfolio
from app.services.markowitz_optimizer import optimize_markowitz_portfolio

HEURISTIC_OPTIMIZER_METHOD = "risk_adjusted"
LEGACY_MEAN_VARIANCE_ALIAS = "mean_variance"
MARKOWITZ_METHOD = "markowitz"
BLACK_LITTERMAN_METHOD = "black_litterman"


def optimize_strategy_portfolio(db: Session, run_id: int, method: str = "hrp") -> dict:
    if (method or "").strip().lower() == MARKOWITZ_METHOD:
        return optimize_markowitz_portfolio(db, run_id=run_id)
    if (method or "").strip().lower() in {BLACK_LITTERMAN_METHOD, "bl"}:
        return optimize_black_litterman_portfolio(db, run_id=run_id)
    returns = _strategy_returns(db, run_id)
    normalized_method = normalize_optimizer_method(method)
    if not returns:
        return {
            "run_id": run_id,
            "method": normalized_method,
            "requested_method": method,
            "weights": [],
            "summary": "暂无可优化的策略成交样本",
        }
    stats = [_strategy_stats(key, values) for key, values in returns.items()]
    if normalized_method == HEURISTIC_OPTIMIZER_METHOD:
        weights = _risk_adjusted_weights(stats)
    else:
        weights = _inverse_risk_weights(stats)
    portfolio_sharpe = _portfolio_sharpe(stats, weights)
    return {
        "run_id": run_id,
        "method": normalized_method,
        "requested_method": method,
        "method_label": "风险调整启发式分配" if normalized_method == HEURISTIC_OPTIMIZER_METHOD else "HRP 风险平价",
        "weights": [
            {
                "strategy_key": item["strategy_key"],
                "weight_pct": round(weights.get(item["strategy_key"], 0.0) * 100, 2),
                "avg_return_pct": round(item["avg"], 4),
                "volatility_pct": round(item["vol"], 4),
                "sample_count": item["count"],
            }
            for item in stats
        ],
        "portfolio_sharpe": round(portfolio_sharpe, 4),
        "summary": "研究用途：当前为风险调整启发式分配，不是 Markowitz 均值-方差优化，不自动用于实盘或模拟盘。",
    }


def normalize_optimizer_method(method: str) -> str:
    cleaned = (method or "hrp").strip().lower()
    if cleaned == LEGACY_MEAN_VARIANCE_ALIAS:
        return HEURISTIC_OPTIMIZER_METHOD
    if cleaned == "bl":
        return BLACK_LITTERMAN_METHOD
    if cleaned in {"hrp", HEURISTIC_OPTIMIZER_METHOD, MARKOWITZ_METHOD, BLACK_LITTERMAN_METHOD}:
        return cleaned
    return "hrp"


def _strategy_returns(db: Session, run_id: int) -> dict[str, list[float]]:
    rows = db.execute(
        select(BacktestTrade.strategy_key, BacktestTrade.pnl_pct)
        .where(BacktestTrade.run_id == run_id, BacktestTrade.strategy_key != "")
    ).all()
    grouped: dict[str, list[float]] = defaultdict(list)
    for strategy_key, pnl_pct in rows:
        if pnl_pct is None:
            continue
        grouped[str(strategy_key)].append(float(pnl_pct))
    return {key: values for key, values in grouped.items() if values}


def _strategy_stats(strategy_key: str, values: list[float]) -> dict:
    avg = mean(values)
    vol = stdev(values) if len(values) > 1 else max(abs(avg), 0.01)
    sharpe = avg / max(vol, 0.01)
    return {"strategy_key": strategy_key, "avg": avg, "vol": vol, "sharpe": sharpe, "count": len(values)}


def _inverse_risk_weights(stats: list[dict]) -> dict[str, float]:
    raw = {item["strategy_key"]: 1.0 / max(float(item["vol"]), 0.01) for item in stats}
    return _normalize(raw)


def _risk_adjusted_weights(stats: list[dict]) -> dict[str, float]:
    raw = {
        item["strategy_key"]: max(float(item["avg"]), 0.0) / max(float(item["vol"]) ** 2, 0.0001)
        for item in stats
    }
    if not any(value > 0 for value in raw.values()):
        return _inverse_risk_weights(stats)
    return _normalize(raw)


def _portfolio_sharpe(stats: list[dict], weights: dict[str, float]) -> float:
    expected = sum(weights.get(item["strategy_key"], 0.0) * float(item["avg"]) for item in stats)
    risk = math.sqrt(sum((weights.get(item["strategy_key"], 0.0) * float(item["vol"])) ** 2 for item in stats))
    return expected / max(risk, 0.0001)


def _normalize(raw: dict[str, float]) -> dict[str, float]:
    total = sum(max(value, 0.0) for value in raw.values())
    if total <= 0:
        equal = 1.0 / max(len(raw), 1)
        return {key: equal for key in raw}
    return {key: max(value, 0.0) / total for key, value in raw.items()}
