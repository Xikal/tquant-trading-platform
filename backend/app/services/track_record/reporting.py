from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import StrategyDriftSnapshot


def track_record_drift_payload(db: Session, *, limit: int = 80) -> dict:
    rows = (
        db.execute(
            select(StrategyDriftSnapshot)
            .order_by(
                StrategyDriftSnapshot.as_of_date.desc(),
                StrategyDriftSnapshot.strategy_key.asc(),
                StrategyDriftSnapshot.window_days.asc(),
            )
            .limit(max(1, min(int(limit or 80), 200)))
        )
        .scalars()
        .all()
    )
    return {"items": [_drift_payload(row) for row in rows], "total": len(rows)}


def _drift_payload(row: StrategyDriftSnapshot) -> dict:
    return {
        "strategy_key": row.strategy_key,
        "as_of_date": row.as_of_date.isoformat() if row.as_of_date else "",
        "window_days": int(row.window_days or 0),
        "sample_settled": int(row.sample_settled or 0),
        "realized_pf": float(row.realized_pf) if row.realized_pf is not None else None,
        "expected_pf": float(row.expected_pf) if row.expected_pf is not None else None,
        "realized_avg": float(row.realized_avg or 0.0),
        "expected_avg": float(row.expected_avg or 0.0),
        "realized_winrate": float(row.realized_winrate or 0.0),
        "expected_winrate": float(row.expected_winrate or 0.0),
        "realized_max5": float(row.realized_max5 or 0.0),
        "backtest_max5": float(row.backtest_max5 or 0.0),
        "realized_max10": float(row.realized_max10 or 0.0),
        "backtest_max10": float(row.backtest_max10 or 0.0),
        "tracking_error": float(row.tracking_error or 0.0),
        "decay_pct": float(row.decay_pct or 0.0),
        "drift_flag": row.drift_flag or "insufficient_sample",
    }
