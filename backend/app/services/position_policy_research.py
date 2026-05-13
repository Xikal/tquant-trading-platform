from __future__ import annotations

from collections import defaultdict
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import BacktestTrade
from app.services.rl.position_shadow import PositionSample, run_position_shadow

POSITION_POLICY_ALGORITHM = "ppo_shadow_position_policy"
LEGACY_POSITION_POLICY_ALIAS = "offline_q_policy_research"


def run_position_policy_research(db: Session, run_id: int, *, train_shadow: bool = False) -> dict:
    samples = _load_samples(db, run_id)
    if not samples:
        return {
            "run_id": run_id,
            "production_enabled": False,
            "algorithm": POSITION_POLICY_ALGORITHM,
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
        "algorithm": POSITION_POLICY_ALGORITHM,
        "policy": policy,
        "shadow_reinforcement_learning": _shadow_payload(samples, train_shadow=train_shadow),
        "summary": "仅用于研究：统计仓位倾向 + PPO shadow 对照均不参与自动交易。",
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


def _shadow_payload(samples: list[dict], *, train_shadow: bool) -> dict:
    if len(samples) < 30:
        return run_position_shadow(_position_samples(samples))
    if not train_shadow:
        return {
            "algorithm": "ppo_sac_shadow_mode",
            "production_enabled": False,
            "trained": False,
            "training_required": True,
            "sample_count": len(samples),
            "policy": _fallback_shadow_policy(samples),
            "summary": "样本已满足 shadow 研究门槛；为避免阻塞接口，PPO/SAC 训练需由后台任务或显式研究流程执行。",
        }
    return run_position_shadow(_position_samples(samples))


def _position_samples(samples: list[dict]) -> list[PositionSample]:
    return [
        PositionSample(
            market_state=str(item.get("market_state") or "unknown"),
            signal_state=str(item.get("signal_state") or "unknown"),
            pnl_pct=float(item.get("pnl_pct") or 0.0),
        )
        for item in samples
    ]


def _fallback_shadow_policy(samples: list[dict]) -> list[dict]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for item in samples:
        buckets[_state_bucket(item)].append(float(item.get("pnl_pct") or 0.0))
    return [_policy_row(state, values) for state, values in sorted(buckets.items())][:20]
