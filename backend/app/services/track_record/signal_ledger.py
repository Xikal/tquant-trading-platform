from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import ProductionSignalLedger
from app.services.low_buy.strategy_policy import participates_in_priority_board
from app.services.market.board_exclusions import is_growth_board_stock, normalize_a_share_symbol


PRODUCTION_SIGNAL_STATES = {"buy_now", "soft_buy_now"}


def capture_production_signals(
    db: Session,
    board_items: list[Any],
    *,
    as_of: date,
    signal_time: datetime | None = None,
    data_cutoff_time: datetime | None = None,
    return_start_time: datetime | None = None,
    source_version: str = "signal_ledger_capture:v1",
) -> dict[str, Any]:
    if not get_settings().track_record_enabled:
        return {"ok": True, "captured": 0, "skipped": len(board_items), "disabled": True}

    resolved_signal_time = signal_time or datetime.combine(as_of, time(hour=15, minute=1))
    resolved_cutoff = data_cutoff_time or datetime.combine(as_of, time(hour=15, minute=0))
    resolved_return_start = return_start_time or datetime.combine(as_of + timedelta(days=1), time(hour=9, minute=30))

    captured = 0
    duplicates = 0
    watch_only = 0
    non_production = 0
    excluded_board = 0
    for item in board_items:
        signal_state = _text_attr(item, "buy_signal_state")
        if signal_state not in PRODUCTION_SIGNAL_STATES:
            watch_only += 1
            continue
        strategy_key = _text_attr(item, "strategy_key")
        if not participates_in_priority_board(strategy_key):
            non_production += 1
            continue
        symbol = normalize_a_share_symbol(_text_attr(item, "symbol"))
        if is_growth_board_stock(symbol):
            excluded_board += 1
            continue
        if _ledger_exists(db, signal_date=as_of, strategy_key=strategy_key, symbol=symbol):
            duplicates += 1
            continue
        row = ProductionSignalLedger(
            signal_date=as_of,
            strategy_key=strategy_key,
            symbol=symbol,
            name=_text_attr(item, "name"),
            signal_state=signal_state,
            production_score=_float_or_none(getattr(item, "production_score", None)),
            priority_score=_float_attr(item, "priority_score"),
            entry_zone_low=_float_attr(item, "entry_zone_low"),
            entry_zone_high=_float_attr(item, "entry_zone_high"),
            stop_loss=_float_attr(item, "stop_loss"),
            expected_horizon_returns_json=json.dumps(_expected_horizon_returns(item), ensure_ascii=False, sort_keys=True),
            market_regime=_text_attr(item, "market_state_category"),
            front_row_tier=_text_attr(item, "front_row_tier"),
            data_quality=_text_attr(item, "data_quality", "unknown"),
            signal_time=resolved_signal_time,
            data_cutoff_time=resolved_cutoff,
            return_start_time=resolved_return_start,
            source_version=source_version,
        )
        db.add(row)
        db.flush()
        captured += 1

    skipped = duplicates + watch_only + non_production + excluded_board
    return {
        "ok": True,
        "captured": captured,
        "skipped": skipped,
        "duplicates": duplicates,
        "watch_only": watch_only,
        "non_production": non_production,
        "excluded_board": excluded_board,
    }


def capture_latest_priority_board(db: Session, *, as_of: date | None = None, limit: int = 30) -> dict[str, Any]:
    from app.services.low_buy.service import LowBuyScreenerService

    signal_date = as_of or date.today()
    board = LowBuyScreenerService().priority_board(db, limit=limit, refresh_mode="sync")
    latest_trade_date = str(getattr(board, "latest_trade_date", "") or signal_date.isoformat())
    try:
        signal_date = date.fromisoformat(latest_trade_date[:10])
    except ValueError:
        pass
    result = capture_production_signals(
        db,
        list(getattr(board, "items", []) or []),
        as_of=signal_date,
        source_version=f"priority_board:{latest_trade_date}",
    )
    db.commit()
    return result


def _expected_horizon_returns(item: Any) -> dict[str, float | int]:
    structured = getattr(item, "expected_horizon_returns", None)
    if isinstance(structured, dict) and structured:
        values: dict[str, float | int] = {
            str(key): round(float(value or 0.0), 4)
            for key, value in structured.items()
            if str(key) in {"1", "2", "3", "4", "5"}
        }
        values["avg_net_return_pct"] = round(_float_attr(item, "expected_avg_return_pct"), 4)
        values["profit_factor"] = round(_float_attr(item, "expected_profit_factor"), 4)
        values["sample_settled"] = int(_float_attr(item, "expected_sample_settled"))
        return values
    values = {
        "1": _float_from_text_or_attr(item, "avg_return_1d", horizon=1),
        "2": _float_from_text_or_attr(item, "avg_return_2d", horizon=2),
        "3": _float_from_text_or_attr(item, "avg_return_3d", horizon=3),
        "4": _float_from_text_or_attr(item, "avg_return_4d", horizon=4),
        "5": _float_from_text_or_attr(item, "avg_return_5d", horizon=5),
        "avg_net_return_pct": _float_from_text_or_attr(item, "avg_net_return_pct", label="均值"),
        "profit_factor": _float_from_text_or_attr(item, "profit_factor", label="PF"),
        "sample_settled": int(_float_from_text_or_attr(item, "sample_settled", label="样本") or 0),
    }
    return {key: value for key, value in values.items() if value not in {None, ""}}


def _ledger_exists(db: Session, *, signal_date: date, strategy_key: str, symbol: str) -> bool:
    return (
        db.execute(
            select(ProductionSignalLedger.id)
            .where(ProductionSignalLedger.signal_date == signal_date)
            .where(ProductionSignalLedger.strategy_key == strategy_key)
            .where(ProductionSignalLedger.symbol == symbol)
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def _float_from_text_or_attr(
    item: Any,
    attr_name: str,
    *,
    horizon: int | None = None,
    label: str | None = None,
) -> float:
    value = getattr(item, attr_name, None)
    if isinstance(value, (int, float)):
        return round(float(value), 4)
    text = _text_attr(item, "strategy_performance_text")
    if not text:
        return 0.0
    patterns: list[str] = []
    if horizon is not None:
        patterns.extend(
            [
                rf"{horizon}\s*[日dD][^\d\-]*(-?\d+(?:\.\d+)?)\s*%",
                rf"{horizon}\s*[日dD][^\d\-]*(-?\d+(?:\.\d+)?)",
            ]
        )
    if label:
        patterns.append(rf"{re.escape(label)}[^\d\-]*(-?\d+(?:\.\d+)?)")
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return round(float(match.group(1)), 4)
    return 0.0


def _text_attr(item: Any, name: str, default: str = "") -> str:
    value = getattr(item, name, default)
    return str(value or default).strip()


def _float_attr(item: Any, name: str, default: float = 0.0) -> float:
    return float(getattr(item, name, default) or default)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
