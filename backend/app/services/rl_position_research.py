from __future__ import annotations

from collections import defaultdict
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import BacktestTrade


def run_offline_position_research(db: Session, run_id: int) -> dict:
    """Research-only offline position policy sketch from backtest outcomes."""

    samples = _load_samples(db, run_id)
    if not samples:
        return {
            "run_id": run_id,
            "production_enabled": False,
            "algorithm": "offline_q_policy_research",
            "policy": [],
            "summary": "暂无成交样本，不能生成仓位研究结论。",
        }
    grouped: dict[str, list[float]] = defaultdict(list)
    for sample in samples:
        grouped[_state_bucket(sample)].append(sample["pnl_pct"])
    policy = [_policy_row(state, values) for state, values in sorted(grouped.items())]
    return {
        "run_id": run_id,
        "production_enabled": False,
        "algorithm": "offline_q_policy_research",
        "policy": policy,
        "summary": "仅用于研究：根据历史成交胜负估算仓位倾向，不参与自动交易。",
    }


def _load_samples(db: Session, run_id: int) -> list[dict]:
    rows = db.execute(
        select(
            BacktestTrade.strategy_key,
            BacktestTrade.market_state,
            BacktestTrade.signal_state,
            BacktestTrade.pnl_pct,
        ).where(BacktestTrade.run_id == run_id)
    ).all()
    return [
        {
            "strategy_key": strategy or "unknown",
            "market_state": market_state or "unknown",
            "signal_state": signal_state or "unknown",
            "pnl_pct": float(pnl_pct or 0.0),
        }
        for strategy, market_state, signal_state, pnl_pct in rows
    ]


def _state_bucket(sample: dict) -> str:
    return f"{sample['market_state']}|{sample['signal_state']}"


def _policy_row(state: str, values: list[float]) -> dict:
    avg = mean(values)
    win_rate = sum(1 for value in values if value > 0) / max(len(values), 1)
    suggested_position_pct = _position_from_edge(avg, win_rate, len(values))
    return {
        "state": state,
        "sample_count": len(values),
        "avg_return_pct": round(avg, 4),
        "win_rate_pct": round(win_rate * 100, 2),
        "suggested_position_pct": suggested_position_pct,
    }


def _position_from_edge(avg: float, win_rate: float, sample_count: int) -> int:
    if sample_count < 30 or avg <= 0 or win_rate < 0.52:
        return 0
    if avg >= 1.0 and win_rate >= 0.6:
        return 15
    if avg >= 0.5:
        return 10
    return 5
