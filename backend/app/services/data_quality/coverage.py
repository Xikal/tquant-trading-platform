from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import DailyBarSnapshot, DataQualitySnapshot, Instrument, MinuteBarSnapshot, TickTradeSnapshot
from app.services.data_quality.schemas import DataQualityCoverageResponse, DataQualityMissingSymbolOut
from app.services.data_quality.sla import SUPPORTED_DATASETS, SUPPORTED_SCOPES
from app.services.market.trading_calendar import is_a_share_trading_day


MODEL_BY_DATASET = {
    "daily_bars": DailyBarSnapshot,
    "minute_bars": MinuteBarSnapshot,
    "tick_trades": TickTradeSnapshot,
}


def build_data_quality_coverage(db: Session, *, dataset_key: str, scope: str) -> DataQualityCoverageResponse:
    resolved_dataset = _normalize(dataset_key, SUPPORTED_DATASETS)
    resolved_scope = _normalize(scope, SUPPORTED_SCOPES)
    snapshot = db.execute(
        select(DataQualitySnapshot)
        .where(DataQualitySnapshot.dataset_key == resolved_dataset)
        .where(DataQualitySnapshot.scope == resolved_scope)
        .order_by(DataQualitySnapshot.as_of_date.desc(), DataQualitySnapshot.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if snapshot is None:
        return DataQualityCoverageResponse(dataset_key=resolved_dataset, scope=resolved_scope)

    expected_dates = _expected_dates(snapshot.as_of_date, int(snapshot.expected_days or 0))
    model = MODEL_BY_DATASET[resolved_dataset]
    actual_dates = {
        _date_value(item)
        for item in db.execute(
            select(model.trade_date.distinct()).where(model.trade_date.in_(expected_dates))
        ).scalars().all()
        if _date_value(item) is not None
    }
    missing_dates = [item for item in expected_dates if item not in actual_dates]
    missing_symbols = _missing_symbols(db, model=model, expected_dates=expected_dates, scope=resolved_scope)
    return DataQualityCoverageResponse(
        dataset_key=resolved_dataset,
        scope=resolved_scope,
        missing_symbols=missing_symbols,
        missing_dates=missing_dates,
    )


def _missing_symbols(db: Session, *, model: Any, expected_dates: list[date], scope: str) -> list[DataQualityMissingSymbolOut]:
    if not expected_dates:
        return []
    instruments = db.execute(
        select(Instrument.symbol, Instrument.name)
        .where(Instrument.instrument_type == "stock")
        .where(Instrument.status == "active")
        .order_by(Instrument.symbol.asc())
        .limit(300)
    ).all()
    if scope == "production_universe":
        instruments = [
            item
            for item in instruments
            if not str(item.symbol).startswith(("300", "301", "688", "689"))
            and "ST" not in str(item.name)
            and "退" not in str(item.name)
        ]
    if not instruments:
        return []

    counts = dict(
        db.execute(
            select(model.symbol, func.count(func.distinct(model.trade_date)))
            .where(model.symbol.in_([item.symbol for item in instruments]))
            .where(model.trade_date.in_(expected_dates))
            .group_by(model.symbol)
        ).all()
    )
    expected_count = len(expected_dates)
    missing = []
    for item in instruments:
        missing_days = max(expected_count - int(counts.get(item.symbol, 0) or 0), 0)
        if missing_days:
            missing.append(DataQualityMissingSymbolOut(symbol=item.symbol, name=item.name or "", missing_days=missing_days))
    return missing


def _expected_dates(as_of: date, expected_days: int) -> list[date]:
    if expected_days <= 0:
        return []
    values: list[date] = []
    current = as_of
    while len(values) < expected_days:
        if is_a_share_trading_day(current):
            values.append(current)
        current -= timedelta(days=1)
    return sorted(values)


def _date_value(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _normalize(value: str, allowed: set[str]) -> str:
    normalized = str(value or "").strip()
    if normalized not in allowed:
        raise ValueError(f"unsupported data quality filter: {value}")
    return normalized
