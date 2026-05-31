from __future__ import annotations

import json
from datetime import date, timedelta
from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import ProductionSignalLedger, SignalRealizedOutcome, StrategyDriftSnapshot


PRODUCTION_SIGNAL_STATES = {"buy_now", "soft_buy_now"}


def compute_strategy_drift(
    db: Session,
    strategy_key: str,
    *,
    window_days: int = 60,
    as_of: date | None = None,
    min_sample: int = 20,
) -> StrategyDriftSnapshot:
    end = as_of or date.today()
    start = end - timedelta(days=max(int(window_days or 1), 1))
    rows = (
        db.execute(
            select(ProductionSignalLedger, SignalRealizedOutcome)
            .join(SignalRealizedOutcome, SignalRealizedOutcome.ledger_id == ProductionSignalLedger.id)
            .where(ProductionSignalLedger.strategy_key == strategy_key)
            .where(ProductionSignalLedger.signal_state.in_(PRODUCTION_SIGNAL_STATES))
            .where(ProductionSignalLedger.signal_date >= start)
            .where(ProductionSignalLedger.signal_date <= end)
            .where(SignalRealizedOutcome.settled.is_(True))
            .where(SignalRealizedOutcome.data_quality == "ok")
        )
        .all()
    )
    realized = [float(outcome.return_pct or 0.0) for _, outcome in rows]
    expected_payloads = [_expected_payload(ledger) for ledger, _ in rows]
    expected_avg_values = [float(item.get("avg_net_return_pct", 0.0) or 0.0) for item in expected_payloads]
    expected_pf_values = [float(item.get("profit_factor", 0.0) or 0.0) for item in expected_payloads]
    expected_max5_values = [float(item.get("5", 0.0) or 0.0) for item in expected_payloads]
    expected_max10_values = [float(item.get("10", 0.0) or 0.0) for item in expected_payloads]

    realized_pf = _profit_factor(realized)
    expected_pf = _mean_positive(expected_pf_values)
    realized_avg = round(mean(realized), 4) if realized else 0.0
    expected_avg = round(mean(expected_avg_values), 4) if expected_avg_values else 0.0
    realized_winrate = _win_rate(realized)
    expected_winrate = _win_rate(expected_avg_values)
    realized_max5 = round(mean(realized), 4) if realized else 0.0
    backtest_max5 = round(mean(expected_max5_values), 4) if expected_max5_values else 0.0
    realized_max10 = round(mean(realized), 4) if realized else 0.0
    backtest_max10 = round(mean(expected_max10_values), 4) if expected_max10_values else 0.0
    tracking_error = round(realized_avg - expected_avg, 4)
    decay_pct = _decay_pct(realized_avg, expected_avg)
    sample_settled = len(realized)
    drift_flag = _drift_flag(
        sample_settled=sample_settled,
        min_sample=min_sample,
        realized_pf=realized_pf,
        expected_pf=expected_pf,
        decay_pct=decay_pct,
    )
    snapshot = (
        db.execute(
            select(StrategyDriftSnapshot)
            .where(StrategyDriftSnapshot.strategy_key == strategy_key)
            .where(StrategyDriftSnapshot.as_of_date == end)
            .where(StrategyDriftSnapshot.window_days == window_days)
        )
        .scalar_one_or_none()
    )
    if snapshot is None:
        snapshot = StrategyDriftSnapshot(strategy_key=strategy_key, as_of_date=end, window_days=window_days)
        db.add(snapshot)
    snapshot.realized_pf = realized_pf
    snapshot.expected_pf = expected_pf
    snapshot.realized_avg = realized_avg
    snapshot.expected_avg = expected_avg
    snapshot.realized_winrate = realized_winrate
    snapshot.expected_winrate = expected_winrate
    snapshot.realized_max5 = realized_max5
    snapshot.backtest_max5 = backtest_max5
    snapshot.realized_max10 = realized_max10
    snapshot.backtest_max10 = backtest_max10
    snapshot.tracking_error = tracking_error
    snapshot.decay_pct = decay_pct
    snapshot.drift_flag = drift_flag
    snapshot.sample_settled = sample_settled
    db.flush()
    return snapshot


def compute_all_strategy_drift(
    db: Session,
    *,
    window_days: int = 60,
    as_of: date | None = None,
    min_sample: int = 20,
) -> list[StrategyDriftSnapshot]:
    end = as_of or date.today()
    strategy_keys = (
        db.execute(
            select(ProductionSignalLedger.strategy_key)
            .where(ProductionSignalLedger.signal_state.in_(PRODUCTION_SIGNAL_STATES))
            .where(ProductionSignalLedger.signal_date <= end)
            .distinct()
            .order_by(ProductionSignalLedger.strategy_key.asc())
        )
        .scalars()
        .all()
    )
    return [
        compute_strategy_drift(db, key, window_days=window_days, as_of=end, min_sample=min_sample)
        for key in strategy_keys
    ]


def _expected_payload(ledger: ProductionSignalLedger) -> dict[str, Any]:
    try:
        loaded = json.loads(ledger.expected_horizon_returns_json or "{}")
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _profit_factor(values: list[float]) -> float | None:
    wins = [value for value in values if value > 0]
    losses = [abs(value) for value in values if value < 0]
    if not values:
        return None
    gross_loss = sum(losses)
    if gross_loss <= 0:
        return None
    return round(sum(wins) / gross_loss, 4)


def _mean_positive(values: list[float]) -> float | None:
    scoped = [value for value in values if value > 0]
    return round(mean(scoped), 4) if scoped else None


def _win_rate(values: list[float]) -> float:
    return round(sum(1 for value in values if value > 0) / len(values) * 100.0, 4) if values else 0.0


def _decay_pct(realized_avg: float, expected_avg: float) -> float:
    if expected_avg == 0:
        return 0.0
    return round((realized_avg - expected_avg) / abs(expected_avg) * 100.0, 4)


def _drift_flag(
    *,
    sample_settled: int,
    min_sample: int,
    realized_pf: float | None,
    expected_pf: float | None,
    decay_pct: float,
) -> str:
    if sample_settled < min_sample:
        return "insufficient_sample"
    if expected_pf and realized_pf is not None and realized_pf < expected_pf * 0.7:
        return "decay_advisory"
    if decay_pct <= -30.0:
        return "decay_advisory"
    return "ok"
