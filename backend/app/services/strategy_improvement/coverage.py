from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select

from app.models.entities import DailyBarSnapshot, MinuteBarSnapshot
from app.services.etf.universe import list_etf_profiles
from app.services.strategy_improvement.provider_diagnostics import load_etf_minute_provider_diagnostics
from app.services.strategy_improvement.types import MIN_DAILY_COVERAGE_PCT, MIN_ETF_MINUTE_COVERAGE_PCT


def latest_daily_trade_date(db) -> str:
    value = db.execute(select(func.max(DailyBarSnapshot.trade_date))).scalar_one_or_none()
    return str(value or "")


def daily_coverage(db, *, start: str, end: str, min_stock_symbols: int) -> dict[str, Any]:
    count, min_date, max_date, symbol_count = db.execute(
        select(
            func.count(DailyBarSnapshot.id),
            func.min(DailyBarSnapshot.trade_date),
            func.max(DailyBarSnapshot.trade_date),
            func.count(func.distinct(DailyBarSnapshot.symbol)),
        ).where(DailyBarSnapshot.instrument_type == "stock")
    ).one()
    per_day_rows = db.execute(
        select(DailyBarSnapshot.trade_date, func.count(func.distinct(DailyBarSnapshot.symbol)))
        .where(DailyBarSnapshot.instrument_type == "stock", DailyBarSnapshot.trade_date >= start, DailyBarSnapshot.trade_date <= end)
        .group_by(DailyBarSnapshot.trade_date)
        .order_by(DailyBarSnapshot.trade_date.asc())
    ).all()
    complete_days = [str(row[0]) for row in per_day_rows if int(row[1] or 0) >= min_stock_symbols]
    trade_dates = [str(row[0]) for row in per_day_rows]
    thin_days = [(str(row[0]), int(row[1] or 0)) for row in per_day_rows if int(row[1] or 0) < min_stock_symbols]
    requested_days = max((date.fromisoformat(end) - date.fromisoformat(start)).days + 1, 1)
    actual_start = str(min_date or "")
    actual_end = str(max_date or "")
    covered_start = max(date.fromisoformat(start), date.fromisoformat(actual_start)) if actual_start else None
    covered_days = (date.fromisoformat(actual_end) - covered_start).days + 1 if covered_start and actual_end else 0
    calendar_span_pct = round(max(min(covered_days / requested_days * 100.0, 100.0), 0.0), 2)
    full_market_coverage_pct = round(float(len(complete_days)) / float(len(per_day_rows)) * 100.0, 2) if per_day_rows else 0.0
    coverage_pct = min(calendar_span_pct, full_market_coverage_pct)
    status = "complete" if coverage_pct >= MIN_DAILY_COVERAGE_PCT and int(symbol_count or 0) >= min_stock_symbols else "partial"
    return {
        "status": status,
        "bar_count": int(count or 0),
        "symbol_count": int(symbol_count or 0),
        "actual_start": actual_start,
        "actual_end": actual_end,
        "requested_start": start,
        "requested_end": end,
        "requested_calendar_days": requested_days,
        "covered_calendar_days": max(covered_days, 0),
        "coverage_pct": coverage_pct,
        "calendar_span_coverage_pct": calendar_span_pct,
        "full_market_trade_day_coverage_pct": full_market_coverage_pct,
        "trade_day_count": len(per_day_rows),
        "complete_trade_day_count": len(complete_days),
        "trade_dates": trade_dates,
        "first_missing_calendar_range": missing_range(start, actual_start),
        "missing_detail_sample": daily_missing_detail_sample(db, thin_days=thin_days, min_stock_symbols=min_stock_symbols),
        "thin_trade_dates_sample": [
            {"trade_date": trade_date, "symbol_count": symbol_count}
            for trade_date, symbol_count in thin_days
        ][:20],
    }


def minute_coverage(db, *, start: str, end: str, bar_period: str = "5m") -> dict[str, Any]:
    count, min_date, max_date, symbol_count = db.execute(
        select(
            func.count(MinuteBarSnapshot.id),
            func.min(MinuteBarSnapshot.trade_date),
            func.max(MinuteBarSnapshot.trade_date),
            func.count(func.distinct(MinuteBarSnapshot.symbol)),
        ).where(MinuteBarSnapshot.bar_period == bar_period)
    ).one()
    profiles = [item for item in list_etf_profiles() if item.same_day_sell_allowed]
    symbols = [item.symbol for item in profiles]
    expected_trade_days = db.execute(
        select(func.count(func.distinct(DailyBarSnapshot.trade_date))).where(
            DailyBarSnapshot.instrument_type == "stock",
            DailyBarSnapshot.trade_date >= start,
            DailyBarSnapshot.trade_date <= end,
        )
    ).scalar_one()
    rows = []
    out_of_window_rows = []
    if symbols:
        rows = db.execute(
            select(
                MinuteBarSnapshot.symbol,
                func.count(MinuteBarSnapshot.id),
                func.count(func.distinct(MinuteBarSnapshot.trade_date)),
                func.min(MinuteBarSnapshot.trade_date),
                func.max(MinuteBarSnapshot.trade_date),
            )
            .where(
                MinuteBarSnapshot.symbol.in_(symbols),
                MinuteBarSnapshot.trade_date >= start,
                MinuteBarSnapshot.trade_date <= end,
                MinuteBarSnapshot.bar_period == bar_period,
            )
            .group_by(MinuteBarSnapshot.symbol)
        ).all()
        out_of_window_rows = db.execute(
            select(
                MinuteBarSnapshot.symbol,
                func.count(MinuteBarSnapshot.id),
                func.min(MinuteBarSnapshot.trade_date),
                func.max(MinuteBarSnapshot.trade_date),
            )
            .where(
                MinuteBarSnapshot.symbol.in_(symbols),
                ((MinuteBarSnapshot.trade_date < start) | (MinuteBarSnapshot.trade_date > end)),
                MinuteBarSnapshot.bar_period == bar_period,
            )
            .group_by(MinuteBarSnapshot.symbol)
        ).all()
    by_symbol = {str(row[0]): int(row[1] or 0) for row in rows}
    trade_days_by_symbol = {str(row[0]): int(row[2] or 0) for row in rows}
    ranges_by_symbol = {
        str(row[0]): {
            "rows": int(row[1] or 0),
            "trade_days": int(row[2] or 0),
            "actual_start": str(row[3] or ""),
            "actual_end": str(row[4] or ""),
        }
        for row in rows
    }
    covered = sum(1 for symbol in symbols if by_symbol.get(symbol, 0) > 0)
    sufficient = sum(
        1
        for symbol in symbols
        if expected_trade_days and round(float(trade_days_by_symbol.get(symbol, 0)) / float(expected_trade_days) * 100.0, 2) >= MIN_ETF_MINUTE_COVERAGE_PCT
    )
    any_coverage_pct = round(float(covered) / float(len(symbols)) * 100.0, 2) if symbols else 0.0
    coverage_pct = round(float(sufficient) / float(len(symbols)) * 100.0, 2) if symbols else 0.0
    raw_status = "complete" if count and coverage_pct >= MIN_ETF_MINUTE_COVERAGE_PCT else "empty" if not count else "partial"
    status = "complete" if raw_status == "complete" else "blocked_by_data"
    blocked_reason = "" if status == "complete" else ("no_minute_data" if raw_status == "empty" else "insufficient_window_trade_day_coverage")
    return {
        "status": status,
        "raw_data_status": raw_status,
        "blocked_reason": blocked_reason,
        "bar_period": bar_period,
        "bar_count": int(count or 0),
        "symbol_count": int(symbol_count or 0),
        "window_bar_count": sum(by_symbol.values()),
        "out_of_window_bar_count": sum(int(row[1] or 0) for row in out_of_window_rows),
        "actual_start": str(min_date or ""),
        "actual_end": str(max_date or ""),
        "expected_trade_day_count": int(expected_trade_days or 0),
        "eligible_etf_count": len(symbols),
        "eligible_etf_with_minutes": covered,
        "eligible_etf_with_sufficient_window_minutes": sufficient,
        "eligible_etf_any_minute_coverage_pct": any_coverage_pct,
        "eligible_etf_minute_coverage_pct": coverage_pct,
        "missing_etf_symbols": [
            {
                "symbol": profile.symbol,
                "name": profile.name,
                "category": profile.category.value,
                "reason": minute_gap_reason(ranges_by_symbol.get(profile.symbol, {}).get("rows", 0), trade_days_by_symbol.get(profile.symbol, 0), int(expected_trade_days or 0)),
                "trade_day_coverage_pct": trade_day_coverage_pct(trade_days_by_symbol.get(profile.symbol, 0), int(expected_trade_days or 0)),
            }
            for profile in profiles
            if not expected_trade_days or trade_day_coverage_pct(trade_days_by_symbol.get(profile.symbol, 0), int(expected_trade_days or 0)) < MIN_ETF_MINUTE_COVERAGE_PCT
        ],
        "coverage_by_symbol_sample": [
            {
                "symbol": profile.symbol,
                "name": profile.name,
                "category": profile.category.value,
                "rows": ranges_by_symbol.get(profile.symbol, {}).get("rows", 0),
                "trade_days": ranges_by_symbol.get(profile.symbol, {}).get("trade_days", 0),
                "trade_day_coverage_pct": trade_day_coverage_pct(trade_days_by_symbol.get(profile.symbol, 0), int(expected_trade_days or 0)),
                "actual_start": ranges_by_symbol.get(profile.symbol, {}).get("actual_start", ""),
                "actual_end": ranges_by_symbol.get(profile.symbol, {}).get("actual_end", ""),
                "reason": minute_gap_reason(ranges_by_symbol.get(profile.symbol, {}).get("rows", 0), trade_days_by_symbol.get(profile.symbol, 0), int(expected_trade_days or 0)),
            }
            for profile in profiles
        ][:30],
        "out_of_window_symbol_sample": [
            {"symbol": str(row[0]), "rows": int(row[1] or 0), "actual_start": str(row[2] or ""), "actual_end": str(row[3] or "")}
            for row in out_of_window_rows
        ][:20],
        "provider_diagnostics": load_etf_minute_provider_diagnostics(),
    }


def trade_day_coverage_pct(actual: int, expected: int) -> float:
    return round(float(actual) / float(expected) * 100.0, 2) if expected else 0.0


def minute_gap_reason(rows: int, actual_trade_days: int, expected_trade_days: int) -> str:
    if rows <= 0:
        return "no_minute_data"
    if expected_trade_days <= 0:
        return "no_expected_trade_days"
    if trade_day_coverage_pct(actual_trade_days, expected_trade_days) < MIN_ETF_MINUTE_COVERAGE_PCT:
        return "insufficient_window_trade_day_coverage"
    return "ok"


def daily_missing_detail_sample(db, *, thin_days: list[tuple[str, int]], min_stock_symbols: int) -> list[dict[str, Any]]:
    if not thin_days:
        return []
    sample: list[dict[str, Any]] = []
    for trade_date, symbol_count in thin_days[:10]:
        rows = db.execute(
            select(DailyBarSnapshot.symbol)
            .where(
                DailyBarSnapshot.instrument_type == "stock",
                DailyBarSnapshot.trade_date == trade_date,
            )
            .order_by(DailyBarSnapshot.symbol.asc())
            .limit(12)
        ).scalars().all()
        sample.append(
            {
                "trade_date": trade_date,
                "symbol_count": symbol_count,
                "threshold": min_stock_symbols,
                "missing_symbol_estimate": max(min_stock_symbols - symbol_count, 0),
                "present_symbol_sample": [str(item) for item in rows],
                "missing_fields": ["OHLCV", "amount", "adjusted_mode", "source", "fetch_time", "checksum", "data_quality"],
                "reason": "below_full_market_symbol_threshold",
            }
        )
    return sample


def missing_range(requested_start: str, actual_start: str) -> str:
    if not actual_start:
        return f"{requested_start} 至最新可用日前均缺失"
    if actual_start <= requested_start:
        return ""
    end = date.fromisoformat(actual_start) - timedelta(days=1)
    return f"{requested_start} 至 {end.isoformat()}"
