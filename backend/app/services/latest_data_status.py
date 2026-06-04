from __future__ import annotations

import json
from datetime import date, datetime, time as dt_time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now, beijing_now_string
from app.models.entities import DailyBarSnapshot, SystemSetting
from app.repositories.low_buy import DailyHistoryRepository, LowBuyResultRepository
from app.services.low_buy.strategy_policy import PRODUCTION_PRIORITY_STRATEGIES
from app.services.market.trading_calendar import is_a_share_trading_day

SETTING_KEY = "low_buy.latest_data"
MIN_STOCK_DAILY_BARS = 4500
PUBLISH_AFTER = dt_time(hour=15, minute=1)
POST_CLOSE_FETCH_AFTER = dt_time(hour=15, minute=1)


def expected_low_buy_trade_date(db: Session) -> str:
    now = beijing_now()
    today = now.date()
    today_iso = today.isoformat()
    local_dates = DailyHistoryRepository(db).fetch_recent_trade_dates(20)
    if is_a_share_trading_day(today) and now.time() >= PUBLISH_AFTER:
        return today_iso
    previous_dates = [item for item in local_dates if item < today_iso]
    if previous_dates:
        return previous_dates[-1]
    return local_dates[-1] if local_dates else today_iso


def latest_data_status(db: Session, strategies: list[str] | None = None) -> dict[str, Any]:
    expected = expected_low_buy_trade_date(db)
    required = _required_strategies(strategies)
    published = _read_state(db)
    freshness = daily_bar_freshness_status(db, expected) if expected else _empty_daily_bar_freshness("")
    daily_count = int(freshness.get("daily_bar_count") or 0)
    missing = _missing_strategy_snapshots(db, expected, required)
    ready = bool(expected and _daily_bars_ready(freshness) and not missing)
    status = "success" if ready else "pending"
    if ready and published.get("published_trade_date") == expected and published.get("status") == "success":
        status = "success"
    return {
        "expected_trade_date": expected,
        "published_trade_date": str(published.get("published_trade_date") or ""),
        "status": status,
        "daily_bar_count": daily_count,
        "min_daily_bar_count": MIN_STOCK_DAILY_BARS,
        "post_close_daily_bar_count": int(freshness.get("post_close_daily_bar_count") or 0),
        "post_close_fetch_cutoff": str(freshness.get("post_close_fetch_cutoff") or ""),
        "latest_daily_bar_fetch_time": str(freshness.get("latest_daily_bar_fetch_time") or ""),
        "post_close_daily_bars_ready": bool(freshness.get("post_close_daily_bars_ready")),
        "daily_bar_freshness_status": str(freshness.get("daily_bar_freshness_status") or ""),
        "missing_strategies": missing,
        "required_strategies": required,
        "updated_at": str(published.get("updated_at") or ""),
    }


def published_low_buy_trade_date(db: Session, strategies: list[str] | None = None) -> str:
    expected = expected_low_buy_trade_date(db)
    state = _read_state(db)
    if state.get("published_trade_date") == expected and state.get("status") == "success":
        return str(state.get("published_trade_date") or "")
    return ""


def publish_latest_trade_date_if_ready(db: Session, strategies: list[str] | None = None) -> dict[str, Any]:
    expected = expected_low_buy_trade_date(db)
    required = _required_strategies(strategies)
    freshness = daily_bar_freshness_status(db, expected) if expected else _empty_daily_bar_freshness("")
    daily_count = int(freshness.get("daily_bar_count") or 0)
    missing = _missing_strategy_snapshots(db, expected, required)
    ready = bool(expected and _daily_bars_ready(freshness) and not missing)
    payload = {
        "expected_trade_date": expected,
        "published_trade_date": expected if ready else "",
        "status": "success" if ready else "pending",
        "daily_bar_count": daily_count,
        "min_daily_bar_count": MIN_STOCK_DAILY_BARS,
        "post_close_daily_bar_count": int(freshness.get("post_close_daily_bar_count") or 0),
        "post_close_fetch_cutoff": str(freshness.get("post_close_fetch_cutoff") or ""),
        "latest_daily_bar_fetch_time": str(freshness.get("latest_daily_bar_fetch_time") or ""),
        "post_close_daily_bars_ready": bool(freshness.get("post_close_daily_bars_ready")),
        "daily_bar_freshness_status": str(freshness.get("daily_bar_freshness_status") or ""),
        "missing_strategies": missing,
        "required_strategies": required,
        "updated_at": beijing_now_string(),
    }
    _write_state(db, payload)
    return payload


def daily_bar_freshness_status(db: Session, trade_date: str) -> dict[str, Any]:
    expected = str(trade_date or "").strip()
    if not expected:
        return _empty_daily_bar_freshness("")
    cutoff = post_close_fetch_cutoff(expected)
    normalized_fetch_time = func.replace(DailyBarSnapshot.fetch_time, " ", "T")
    daily_count = DailyHistoryRepository(db).stock_count_by_trade_date(expected)
    post_close_count = int(
        db.execute(
            select(func.count(DailyBarSnapshot.id)).where(
                DailyBarSnapshot.trade_date == expected,
                normalized_fetch_time >= cutoff,
            )
        ).scalar()
        or 0
    )
    latest_fetch_time = str(
        db.execute(
            select(func.max(normalized_fetch_time)).where(DailyBarSnapshot.trade_date == expected)
        ).scalar()
        or ""
    )
    count_ready = daily_count >= MIN_STOCK_DAILY_BARS
    post_close_ready = post_close_count >= MIN_STOCK_DAILY_BARS
    if post_close_ready:
        status = "post_close_complete"
    elif count_ready:
        status = "stale_before_post_close"
    else:
        status = "insufficient_daily_bars"
    return {
        "daily_bar_count": int(daily_count or 0),
        "min_daily_bar_count": MIN_STOCK_DAILY_BARS,
        "post_close_daily_bar_count": post_close_count,
        "post_close_fetch_cutoff": cutoff,
        "latest_daily_bar_fetch_time": latest_fetch_time,
        "post_close_daily_bars_ready": post_close_ready,
        "daily_bar_freshness_status": status,
    }


def post_close_fetch_cutoff(trade_date: str) -> str:
    parsed = _parse_trade_date(trade_date)
    return datetime.combine(parsed, POST_CLOSE_FETCH_AFTER).isoformat(timespec="seconds")


def _required_strategies(strategies: list[str] | None) -> list[str]:
    values = strategies or sorted(PRODUCTION_PRIORITY_STRATEGIES)
    return sorted({str(item) for item in values if item})


def _daily_bars_ready(freshness: dict[str, Any]) -> bool:
    return bool(
        int(freshness.get("daily_bar_count") or 0) >= MIN_STOCK_DAILY_BARS
        and int(freshness.get("post_close_daily_bar_count") or 0) >= MIN_STOCK_DAILY_BARS
    )


def _empty_daily_bar_freshness(trade_date: str) -> dict[str, Any]:
    cutoff = post_close_fetch_cutoff(trade_date) if trade_date else ""
    return {
        "daily_bar_count": 0,
        "min_daily_bar_count": MIN_STOCK_DAILY_BARS,
        "post_close_daily_bar_count": 0,
        "post_close_fetch_cutoff": cutoff,
        "latest_daily_bar_fetch_time": "",
        "post_close_daily_bars_ready": False,
        "daily_bar_freshness_status": "missing_trade_date" if not trade_date else "insufficient_daily_bars",
    }


def _parse_trade_date(raw: str) -> date:
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return beijing_now().date()


def _missing_strategy_snapshots(db: Session, trade_date: str, strategies: list[str]) -> list[str]:
    if not trade_date:
        return list(strategies)
    repository = LowBuyResultRepository(db)
    missing: list[str] = []
    for strategy in strategies:
        if repository.fetch_scan_summary(latest_trade_date=trade_date, strategy_key=strategy) is None:
            missing.append(strategy)
    return missing


def _read_state(db: Session) -> dict[str, Any]:
    row = db.execute(select(SystemSetting).where(SystemSetting.key == SETTING_KEY)).scalar_one_or_none()
    if row is None or not row.value:
        return {}
    try:
        value = json.loads(row.value)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _write_state(db: Session, payload: dict[str, Any]) -> None:
    row = db.execute(select(SystemSetting).where(SystemSetting.key == SETTING_KEY)).scalar_one_or_none()
    raw = json.dumps(payload, ensure_ascii=False, default=str)
    if row is None:
        db.add(SystemSetting(key=SETTING_KEY, value=raw))
    else:
        row.value = raw
    db.flush()
