from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import DailyBarSnapshot
from app.models.schema_defs.phase4 import RuntimeTaskCreate
from app.services.tasks import RuntimeTaskQueue


MIN_FULL_MARKET_SYMBOLS = 3000
RECENT_DATA_GRACE_DAYS = 7


@dataclass(frozen=True)
class DailyBarsQualityResult:
    dataset_key: str
    period_start: str
    period_end: str
    expected_days: int
    actual_days: int
    missing_days: int
    duplicate_rows: int
    invalid_ohlc_rows: int
    row_count: int
    symbol_count: int
    complete_trade_day_count: int
    actual_start: str
    actual_end: str
    status: str
    blockers: list[str] = field(default_factory=list)
    backfill_task_id: int | None = None

    def as_dict(self) -> dict[str, Any]:
        coverage_pct = (
            round(float(self.actual_days) / float(self.expected_days) * 100.0, 4)
            if self.expected_days
            else 0.0
        )
        complete_coverage_pct = (
            round(float(self.complete_trade_day_count) / float(self.expected_days) * 100.0, 4)
            if self.expected_days
            else 0.0
        )
        return {
            "dataset_key": self.dataset_key,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "expected_days": self.expected_days,
            "actual_days": self.actual_days,
            "missing_days": self.missing_days,
            "coverage_pct": coverage_pct,
            "complete_coverage_pct": complete_coverage_pct,
            "duplicate_rows": self.duplicate_rows,
            "invalid_ohlc_rows": self.invalid_ohlc_rows,
            "row_count": self.row_count,
            "symbol_count": self.symbol_count,
            "complete_trade_day_count": self.complete_trade_day_count,
            "actual_start": self.actual_start,
            "actual_end": self.actual_end,
            "status": self.status,
            "canonical_status": normalized_quality_status(self),
            "blockers": list(self.blockers),
            "backfill_task_id": self.backfill_task_id,
        }


def period_for_months(end_date: date, months: int) -> tuple[date, date]:
    return _subtract_months(end_date, max(months, 1)), end_date


def check_daily_bars_24m_quality(
    db: Session,
    *,
    months: int = 24,
    end_date: date | None = None,
    min_symbols_per_day: int = MIN_FULL_MARKET_SYMBOLS,
    create_backfill_task: bool = False,
) -> DailyBarsQualityResult:
    resolved_end = end_date or date.today()
    start, end = period_for_months(resolved_end, months)
    row_count, min_date, max_date, symbol_count = db.execute(
        select(
            func.count(DailyBarSnapshot.id),
            func.min(DailyBarSnapshot.trade_date),
            func.max(DailyBarSnapshot.trade_date),
            func.count(func.distinct(DailyBarSnapshot.symbol)),
        ).where(
            DailyBarSnapshot.instrument_type == "stock",
            DailyBarSnapshot.trade_date >= start,
            DailyBarSnapshot.trade_date <= end,
        )
    ).one()
    per_day = db.execute(
        select(DailyBarSnapshot.trade_date, func.count(func.distinct(DailyBarSnapshot.symbol)))
        .where(
            DailyBarSnapshot.instrument_type == "stock",
            DailyBarSnapshot.trade_date >= start,
            DailyBarSnapshot.trade_date <= end,
        )
        .group_by(DailyBarSnapshot.trade_date)
        .order_by(DailyBarSnapshot.trade_date.asc())
    ).all()
    actual_days = len(per_day)
    expected_days = _minimum_expected_trade_days(start, end)
    complete_trade_day_count = sum(1 for _, count in per_day if int(count or 0) >= min_symbols_per_day)
    duplicate_rows = int(
        db.execute(
            select(func.count()).select_from(
                select(DailyBarSnapshot.symbol, DailyBarSnapshot.trade_date)
                .where(
                    DailyBarSnapshot.instrument_type == "stock",
                    DailyBarSnapshot.trade_date >= start,
                    DailyBarSnapshot.trade_date <= end,
                )
                .group_by(DailyBarSnapshot.symbol, DailyBarSnapshot.trade_date)
                .having(func.count(DailyBarSnapshot.id) > 1)
                .subquery()
            )
        ).scalar_one()
        or 0
    )
    invalid_ohlc_rows = count_invalid_daily_bar_ohlc_rows(
        db,
        start_date=start,
        end_date=end,
        min_symbols_per_day=None,
    )
    actual_start = str(min_date or "")
    actual_end = str(max_date or "")
    blockers: list[str] = []
    if not row_count:
        blockers.append("daily_bars_empty")
    if not actual_start or date.fromisoformat(actual_start) > start + timedelta(days=RECENT_DATA_GRACE_DAYS):
        blockers.append("daily_bars_start_after_required_window")
    if not actual_end or date.fromisoformat(actual_end) < end - timedelta(days=RECENT_DATA_GRACE_DAYS):
        blockers.append("daily_bars_end_before_required_window")
    if actual_days < expected_days:
        blockers.append("daily_bars_trade_days_below_expected")
    if complete_trade_day_count < max(int(expected_days * 0.9), 1):
        blockers.append("daily_bars_full_market_coverage_below_90pct")
    if duplicate_rows:
        blockers.append("daily_bars_duplicate_symbol_dates")
    if invalid_ohlc_rows:
        blockers.append("daily_bars_invalid_ohlc")

    backfill_task_id = None
    if blockers and create_backfill_task:
        backfill_start, backfill_end = _backfill_range(
            required_start=start,
            required_end=end,
            actual_start=actual_start,
            actual_end=actual_end,
        )
        task = RuntimeTaskQueue(db).enqueue(
            RuntimeTaskCreate(
                task_type="data_backfill_24m",
                payload={
                    "queue": "analytics",
                    "dataset": "daily_bars",
                    "months": months,
                    "required_start_date": start.isoformat(),
                    "required_end_date": end.isoformat(),
                    "start_date": backfill_start,
                    "end_date": backfill_end,
                    "min_symbols_per_day": min_symbols_per_day,
                    "blockers": blockers,
                    "command": (
                        "PYTHONPATH=backend:. python backend/scripts/backfill_daily_history.py "
                        f"--months {months} --start-date {backfill_start} --end-date {backfill_end} --scope all-stock"
                    ),
                },
                priority=20,
                idempotency_key=f"data_backfill_24m:daily_bars:{backfill_start}:{backfill_end}",
                max_attempts=1,
            )
        )
        backfill_task_id = task.id

    return DailyBarsQualityResult(
        dataset_key="daily_bars",
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        expected_days=expected_days,
        actual_days=actual_days,
        missing_days=max(expected_days - actual_days, 0),
        duplicate_rows=duplicate_rows,
        invalid_ohlc_rows=invalid_ohlc_rows,
        row_count=int(row_count or 0),
        symbol_count=int(symbol_count or 0),
        complete_trade_day_count=complete_trade_day_count,
        actual_start=actual_start,
        actual_end=actual_end,
        status="fail" if blockers else "ok",
        blockers=blockers,
        backfill_task_id=backfill_task_id,
    )


def normalized_quality_status(quality: DailyBarsQualityResult | dict[str, Any]) -> str:
    """Map legacy quality fail/ok into product-facing data states."""

    status = _quality_value(quality, "status")
    blockers = [str(item) for item in (_quality_value(quality, "blockers") or [])]
    row_count = int(_quality_value(quality, "row_count") or 0)
    actual_days = int(_quality_value(quality, "actual_days") or 0)
    if status == "ok" and not blockers:
        return "ok"
    if row_count <= 0 or "daily_bars_empty" in blockers:
        return "no_data"
    if "daily_bars_end_before_required_window" in blockers:
        return "stale"
    if actual_days > 0:
        return "partial"
    return "blocked"


def _quality_value(quality: DailyBarsQualityResult | dict[str, Any], key: str) -> Any:
    if isinstance(quality, dict):
        return quality.get(key)
    return getattr(quality, key)


def _subtract_months(value: date, months: int) -> date:
    month_index = value.month - months
    year = value.year + (month_index - 1) // 12
    month = (month_index - 1) % 12 + 1
    day = min(value.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - timedelta(days=1)).day


def _minimum_expected_trade_days(start: date, end: date) -> int:
    weekdays = sum(1 for offset in range((end - start).days + 1) if (start + timedelta(days=offset)).weekday() < 5)
    return max(int(weekdays * 0.68), 1)


def minimum_expected_trade_days(start: date, end: date) -> int:
    return _minimum_expected_trade_days(start, end)


def daily_bar_invalid_ohlc_filter():
    return (
        (DailyBarSnapshot.open_price <= 0)
        | (DailyBarSnapshot.close_price <= 0)
        | (DailyBarSnapshot.high_price < DailyBarSnapshot.low_price)
        | (DailyBarSnapshot.high_price < DailyBarSnapshot.open_price)
        | (DailyBarSnapshot.high_price < DailyBarSnapshot.close_price)
        | (DailyBarSnapshot.low_price > DailyBarSnapshot.open_price)
        | (DailyBarSnapshot.low_price > DailyBarSnapshot.close_price)
    )


def count_invalid_daily_bar_ohlc_rows(
    db: Session,
    *,
    start_date: date,
    end_date: date,
    extra_filters: list[Any] | None = None,
    min_symbols_per_day: int | None = MIN_FULL_MARKET_SYMBOLS,
) -> int:
    filters: list[Any] = [
        DailyBarSnapshot.instrument_type == "stock",
        DailyBarSnapshot.trade_date >= start_date,
        DailyBarSnapshot.trade_date <= end_date,
        daily_bar_invalid_ohlc_filter(),
    ]
    if extra_filters:
        filters.extend(extra_filters)
    return int(
        db.execute(select(func.count(DailyBarSnapshot.id)).where(*filters)).scalar_one()
        or 0
    )


def _backfill_range(*, required_start: date, required_end: date, actual_start: str, actual_end: str) -> tuple[str, str]:
    start = required_start
    end = required_end
    if actual_start:
        parsed_start = date.fromisoformat(actual_start)
        if parsed_start <= required_start + timedelta(days=RECENT_DATA_GRACE_DAYS):
            start = required_end
    if actual_end:
        parsed_end = date.fromisoformat(actual_end)
        if parsed_end < required_end:
            start = min(start, parsed_end + timedelta(days=1))
    if start > end:
        start = required_start
    return start.isoformat(), end.isoformat()
