from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.low_buy import SystemSettingRepository
from app.services.low_buy.strategy_governance import (
    AUTO_GOVERNANCE_SETTING_KEY,
    _strategy_health,
    latest_strategy_performance_map,
)


MIN_AUTO_GOVERNANCE_FILLED_SIGNALS = 20
WATCH_HEALTH_THRESHOLD = 55.0
PAUSE_HEALTH_THRESHOLD = 35.0


def refresh_low_buy_strategy_auto_governance(db: Session) -> dict[str, Any]:
    """Persist automatic strategy downgrade/pause decisions.

    The task is intentionally conservative: only strategies with enough real
    filled samples can be auto-downgraded. Missing or sparse samples remain
    visible as research/watch data but do not trigger persistent overrides.
    """

    performances = latest_strategy_performance_map(db)
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    items: dict[str, dict[str, Any]] = {}
    for strategy_key, performance in performances.items():
        health_score, _ = _strategy_health(performance)
        decision = _auto_governance_decision(
            filled_signals=performance.filled_signals,
            health_score=health_score,
            stop_loss_rate=performance.stop_loss_rate,
            avg_net_return_pct=performance.avg_net_return_pct,
        )
        if decision is None:
            continue
        items[strategy_key] = {
            "status": decision["status"],
            "reason": decision["reason"],
            "health_score": health_score,
            "filled_signals": performance.filled_signals,
            "updated_at": updated_at,
        }

    payload = {
        "version": 1,
        "updated_at": updated_at,
        "min_filled_signals": MIN_AUTO_GOVERNANCE_FILLED_SIGNALS,
        "items": items,
    }
    SystemSettingRepository(db).upsert(
        AUTO_GOVERNANCE_SETTING_KEY,
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )
    db.commit()
    return payload


def _auto_governance_decision(
    *,
    filled_signals: int,
    health_score: float,
    stop_loss_rate: float,
    avg_net_return_pct: float,
) -> dict[str, str] | None:
    if filled_signals < MIN_AUTO_GOVERNANCE_FILLED_SIGNALS:
        return None
    if health_score < PAUSE_HEALTH_THRESHOLD or (stop_loss_rate >= 32.0 and avg_net_return_pct < 0):
        return {
            "status": "paused",
            "reason": "真实成交绩效偏弱，自动暂停强信号",
        }
    if health_score < WATCH_HEALTH_THRESHOLD or stop_loss_rate >= 24.0:
        return {
            "status": "watch",
            "reason": "真实成交绩效一般，自动降级观察",
        }
    return None
