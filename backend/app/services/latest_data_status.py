from __future__ import annotations

import json
from datetime import time as dt_time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now, beijing_now_string
from app.models.entities import SystemSetting
from app.repositories.low_buy import DailyHistoryRepository, LowBuyResultRepository
from app.services.low_buy.strategy_policy import PRODUCTION_PRIORITY_STRATEGIES
from app.services.market.trading_calendar import is_a_share_trading_day

SETTING_KEY = "low_buy.latest_data"
MIN_STOCK_DAILY_BARS = 4500
PUBLISH_AFTER = dt_time(hour=15, minute=1)


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
    daily_count = DailyHistoryRepository(db).stock_count_by_trade_date(expected) if expected else 0
    missing = _missing_strategy_snapshots(db, expected, required)
    ready = bool(expected and daily_count >= MIN_STOCK_DAILY_BARS and not missing)
    status = "success" if ready else "pending"
    if published.get("published_trade_date") == expected and published.get("status") == "success":
        status = "success"
    return {
        "expected_trade_date": expected,
        "published_trade_date": str(published.get("published_trade_date") or ""),
        "status": status,
        "daily_bar_count": daily_count,
        "min_daily_bar_count": MIN_STOCK_DAILY_BARS,
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
    daily_count = DailyHistoryRepository(db).stock_count_by_trade_date(expected) if expected else 0
    missing = _missing_strategy_snapshots(db, expected, required)
    ready = bool(expected and daily_count >= MIN_STOCK_DAILY_BARS and not missing)
    payload = {
        "expected_trade_date": expected,
        "published_trade_date": expected if ready else "",
        "status": "success" if ready else "pending",
        "daily_bar_count": daily_count,
        "min_daily_bar_count": MIN_STOCK_DAILY_BARS,
        "missing_strategies": missing,
        "required_strategies": required,
        "updated_at": beijing_now_string(),
    }
    _write_state(db, payload)
    return payload


def _required_strategies(strategies: list[str] | None) -> list[str]:
    values = strategies or sorted(PRODUCTION_PRIORITY_STRATEGIES)
    return sorted({str(item) for item in values if item})


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
