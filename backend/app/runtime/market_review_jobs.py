from __future__ import annotations

import logging
from datetime import date, time as dt_time

from app.core.database import SessionLocal
from app.core.timezone import beijing_now, beijing_today
from app.services.latest_data_close_refresh import enqueue_market_review_reports_if_missing
from app.services.market.trading_calendar import is_a_share_trading_day

logger = logging.getLogger(__name__)
_market_midday_review_last_run_date: date | None = None
_market_close_review_last_run_date: date | None = None


def generate_midday_market_review_once() -> None:
    global _market_midday_review_last_run_date
    if not market_midday_review_due():
        return
    today = beijing_today()
    if _market_midday_review_last_run_date == today:
        return
    with SessionLocal() as db:
        result = enqueue_market_review_reports_if_missing(
            db,
            trade_date=today.isoformat(),
            slots=["midday"],
            reason="runtime_scheduler_midday_review",
        )
        _market_midday_review_last_run_date = today
        logger.info("全市场午盘复盘任务已确认: date=%s result=%s", today.isoformat(), result)


def generate_close_market_review_once() -> None:
    global _market_close_review_last_run_date
    if not market_close_review_due():
        return
    today = beijing_today()
    if _market_close_review_last_run_date == today:
        return
    with SessionLocal() as db:
        result = enqueue_market_review_reports_if_missing(
            db,
            trade_date=today.isoformat(),
            slots=["close"],
            reason="runtime_scheduler_close_review",
        )
        _market_close_review_last_run_date = today
        logger.info("全市场收盘复盘任务已确认: date=%s result=%s", today.isoformat(), result)


def market_midday_review_due() -> bool:
    now = beijing_now()
    if not is_a_share_trading_day(now.date()):
        return False
    return dt_time(hour=11, minute=35) <= now.time() < dt_time(hour=15, minute=0)


def market_close_review_due() -> bool:
    now = beijing_now()
    if not is_a_share_trading_day(now.date()):
        return False
    return now.time() >= _configured_close_review_time()


def _configured_close_review_time() -> dt_time:
    from app.core.config import get_settings

    settings = get_settings()
    try:
        hour, minute = [int(part) for part in settings.paper_perf_archive_time.split(":", 1)]
        return dt_time(hour=hour, minute=minute)
    except (TypeError, ValueError):
        logger.warning("PAPER_PERF_ARCHIVE_TIME 配置无效: %s", settings.paper_perf_archive_time)
        return dt_time(hour=15, minute=5)
