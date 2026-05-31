from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    DailyBarSnapshot,
    DataQualitySnapshot,
    Instrument,
    MinuteBarSnapshot,
    TickTradeSnapshot,
)
from app.services.analytics.quality import (
    count_invalid_daily_bar_ohlc_rows,
    minimum_expected_trade_days,
)


SUPPORTED_DATASETS = {"daily_bars", "minute_bars", "tick_trades"}
SUPPORTED_SCOPES = {"all", "production_universe"}


def compute_dataset_sla(
    db: Session,
    *,
    dataset_key: str,
    scope: str,
    as_of: date | None = None,
    start_date: date | None = None,
    expected_days: int | None = None,
) -> DataQualitySnapshot:
    resolved_dataset = _normalize_dataset_key(dataset_key)
    resolved_scope = _normalize_scope(scope)
    end = as_of or date.today()
    start = start_date or (end - timedelta(days=365 * 2))
    expected = int(expected_days if expected_days is not None else minimum_expected_trade_days(start, end))
    if resolved_dataset == "daily_bars":
        return _compute_daily_bars_sla(
            db,
            scope=resolved_scope,
            as_of=end,
            start_date=start,
            expected_days=expected,
        )
    return _compute_timeseries_sla(
        db,
        dataset_key=resolved_dataset,
        model=MinuteBarSnapshot if resolved_dataset == "minute_bars" else TickTradeSnapshot,
        scope=resolved_scope,
        as_of=end,
        start_date=start,
        expected_days=expected,
    )


def _compute_daily_bars_sla(
    db: Session,
    *,
    scope: str,
    as_of: date,
    start_date: date,
    expected_days: int,
) -> DataQualitySnapshot:
    filters = _daily_bar_base_filters(start_date=start_date, end_date=as_of)
    if scope == "production_universe":
        filters.extend(_production_universe_filters())
    per_day = db.execute(
        select(DailyBarSnapshot.trade_date, func.count(func.distinct(DailyBarSnapshot.symbol)))
        .where(*filters)
        .group_by(DailyBarSnapshot.trade_date)
        .order_by(DailyBarSnapshot.trade_date.asc())
    ).all()
    actual_days = len(per_day)
    duplicate_rows = _count_duplicate_daily_rows(db, filters)
    invalid_rows = count_invalid_daily_bar_ohlc_rows(
        db,
        start_date=start_date,
        end_date=as_of,
        extra_filters=_daily_bar_extra_filters_for_scope(scope),
    )
    blockers: list[str] = []
    if actual_days < expected_days:
        blockers.append("daily_bars_trade_days_below_expected")
    if duplicate_rows:
        blockers.append("daily_bars_duplicate_symbol_dates")
    if invalid_rows:
        blockers.append("daily_bars_invalid_ohlc")
    status = "fail" if blockers else "ok"
    return _upsert_snapshot(
        db,
        dataset_key="daily_bars",
        as_of=as_of,
        scope=scope,
        expected_days=expected_days,
        actual_days=actual_days,
        missing_days=max(expected_days - actual_days, 0),
        invalid_rows=invalid_rows,
        duplicate_rows=duplicate_rows,
        stale=False,
        coverage_pct=_coverage_pct(actual_days, expected_days),
        status=status,
        blockers=blockers,
    )


def _compute_timeseries_sla(
    db: Session,
    *,
    dataset_key: str,
    model: Any,
    scope: str,
    as_of: date,
    start_date: date,
    expected_days: int,
) -> DataQualitySnapshot:
    filters: list[Any] = [model.trade_date >= start_date, model.trade_date <= as_of]
    if scope == "production_universe" and hasattr(model, "instrument_type"):
        filters.append(model.instrument_type == "stock")
        filters.extend(_symbol_level_production_filters(model.symbol))
    actual_days = int(
        db.execute(select(func.count(func.distinct(model.trade_date))).where(*filters)).scalar_one()
        or 0
    )
    duplicate_rows = int(
        db.execute(
            select(func.count()).select_from(
                select(model.symbol, model.trade_date)
                .where(*filters)
                .group_by(model.symbol, model.trade_date)
                .having(func.count(model.id) > 1)
                .subquery()
            )
        ).scalar_one()
        or 0
    )
    blockers: list[str] = []
    if actual_days < expected_days:
        blockers.append(f"{dataset_key}_unavailable")
    if duplicate_rows:
        blockers.append(f"{dataset_key}_duplicate_symbol_dates")
    status = "unavailable" if blockers else "ok"
    return _upsert_snapshot(
        db,
        dataset_key=dataset_key,
        as_of=as_of,
        scope=scope,
        expected_days=expected_days,
        actual_days=actual_days,
        missing_days=max(expected_days - actual_days, 0),
        invalid_rows=0,
        duplicate_rows=duplicate_rows,
        stale=bool(blockers),
        coverage_pct=_coverage_pct(actual_days, expected_days),
        status=status,
        blockers=blockers,
    )


def _daily_bar_base_filters(*, start_date: date, end_date: date) -> list[Any]:
    return [
        DailyBarSnapshot.instrument_type == "stock",
        DailyBarSnapshot.trade_date >= start_date,
        DailyBarSnapshot.trade_date <= end_date,
    ]


def _daily_bar_extra_filters_for_scope(scope: str) -> list[Any]:
    if scope != "production_universe":
        return []
    return _production_universe_filters()


def _production_universe_filters() -> list[Any]:
    return [
        DailyBarSnapshot.is_st.is_(False),
        DailyBarSnapshot.is_delisted.is_(False),
        DailyBarSnapshot.symbol.not_like("300%"),
        DailyBarSnapshot.symbol.not_like("301%"),
        DailyBarSnapshot.symbol.not_like("688%"),
        DailyBarSnapshot.symbol.not_like("689%"),
        DailyBarSnapshot.symbol.not_in(
            select(Instrument.symbol).where(
                Instrument.instrument_type == "stock",
                (
                    (Instrument.is_st.is_(True))
                    | (Instrument.status != "active")
                    | (Instrument.name.like("%ST%"))
                    | (Instrument.name.like("%退%"))
                ),
            )
        ),
    ]


def _symbol_level_production_filters(symbol_column: Any) -> list[Any]:
    return [
        symbol_column.not_like("300%"),
        symbol_column.not_like("301%"),
        symbol_column.not_like("688%"),
        symbol_column.not_like("689%"),
        symbol_column.not_in(
            select(Instrument.symbol).where(
                Instrument.instrument_type == "stock",
                (
                    (Instrument.is_st.is_(True))
                    | (Instrument.status != "active")
                    | (Instrument.name.like("%ST%"))
                    | (Instrument.name.like("%退%"))
                ),
            )
        ),
    ]


def _count_duplicate_daily_rows(db: Session, filters: list[Any]) -> int:
    return int(
        db.execute(
            select(func.count()).select_from(
                select(DailyBarSnapshot.symbol, DailyBarSnapshot.trade_date)
                .where(*filters)
                .group_by(DailyBarSnapshot.symbol, DailyBarSnapshot.trade_date)
                .having(func.count(DailyBarSnapshot.id) > 1)
                .subquery()
            )
        ).scalar_one()
        or 0
    )


def _upsert_snapshot(
    db: Session,
    *,
    dataset_key: str,
    as_of: date,
    scope: str,
    expected_days: int,
    actual_days: int,
    missing_days: int,
    invalid_rows: int,
    duplicate_rows: int,
    stale: bool,
    coverage_pct: float,
    status: str,
    blockers: list[str],
) -> DataQualitySnapshot:
    blockers_json = json.dumps(blockers, ensure_ascii=False)
    existing = db.execute(
        select(DataQualitySnapshot).where(
            DataQualitySnapshot.dataset_key == dataset_key,
            DataQualitySnapshot.as_of_date == as_of,
            DataQualitySnapshot.scope == scope,
        )
    ).scalar_one_or_none()
    snapshot = existing or DataQualitySnapshot(dataset_key=dataset_key, as_of_date=as_of, scope=scope)
    snapshot.expected_days = expected_days
    snapshot.actual_days = actual_days
    snapshot.missing_days = missing_days
    snapshot.invalid_rows = invalid_rows
    snapshot.duplicate_rows = duplicate_rows
    snapshot.stale = stale
    snapshot.coverage_pct = coverage_pct
    snapshot.status = status
    snapshot.blockers_json = blockers_json
    if existing is None:
        db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def _coverage_pct(actual_days: int, expected_days: int) -> float:
    if expected_days <= 0:
        return 100.0 if actual_days else 0.0
    return round(min(actual_days / expected_days * 100.0, 100.0), 2)


def _normalize_dataset_key(dataset_key: str) -> str:
    normalized = str(dataset_key or "").strip()
    if normalized not in SUPPORTED_DATASETS:
        raise ValueError(f"unsupported data quality dataset: {dataset_key}")
    return normalized


def _normalize_scope(scope: str) -> str:
    normalized = str(scope or "").strip() or "all"
    if normalized not in SUPPORTED_SCOPES:
        raise ValueError(f"unsupported data quality scope: {scope}")
    return normalized
