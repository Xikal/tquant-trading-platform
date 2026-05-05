from __future__ import annotations

from typing import Any

from app.services.backtest.data_provider import BacktestSignal
from app.services.backtest.engine import BacktestConfig
from app.services.backtest_job_service import BacktestJobService


def build_backtest_config(value: BacktestConfig | dict[str, Any]) -> BacktestConfig:
    """Compatibility helper for tests/scripts that construct engine configs."""

    if isinstance(value, BacktestConfig):
        return value
    payload = dict(value)
    signals = payload.get("signals") or []
    payload["signals"] = [_signal_from_dict(item) for item in signals if isinstance(item, dict)]
    return BacktestConfig(**payload)


def _signal_from_dict(payload: dict[str, Any]) -> BacktestSignal:
    return BacktestSignal(
        signal_date=str(payload.get("signal_date") or payload.get("trade_date") or ""),
        symbol=str(payload.get("symbol") or ""),
        strategy_key=str(payload.get("strategy_key") or "custom"),
        score=_float(payload.get("score"), 0.0),
        name=str(payload.get("name") or payload.get("symbol") or ""),
        signal_state=str(payload.get("signal_state") or "watch"),
        entry_zone_low=_optional_float(payload.get("entry_zone_low")),
        entry_zone_high=_optional_float(payload.get("entry_zone_high")),
        stop_loss=_optional_float(payload.get("stop_loss")),
        take_profit=_optional_float(payload.get("take_profit")),
        max_holding_days=int(payload.get("max_holding_days") or 5),
        position_pct=_optional_float(payload.get("position_pct")),
        metadata=dict(payload.get("metadata") or {}),
    )


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return _float(value, 0.0)


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
