from __future__ import annotations

import logging
from datetime import date, time as dt_time

from app.core.database import SessionLocal
from app.core.timezone import beijing_now, beijing_today
from app.services.market.review import MarketReviewService

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
        report = MarketReviewService(db).generate_review_report(report_slot="midday", target_date=today)
        db.commit()
        _market_midday_review_last_run_date = today
        logger.info("全市场午盘复盘完成: report_id=%s date=%s", report.id, today.isoformat())


def generate_close_market_review_once() -> None:
    global _market_close_review_last_run_date
    if not market_close_review_due():
        return
    today = beijing_today()
    if _market_close_review_last_run_date == today:
        return
    with SessionLocal() as db:
        report = MarketReviewService(db).generate_review_report(report_slot="close", target_date=today)
        db.commit()
        _market_close_review_last_run_date = today
        logger.info("全市场收盘复盘完成: report_id=%s date=%s", report.id, today.isoformat())


def market_midday_review_due() -> bool:
    now = beijing_now()
    if now.weekday() >= 5:
        return False
    return dt_time(hour=11, minute=35) <= now.time() < dt_time(hour=15, minute=0)


def market_close_review_due() -> bool:
    now = beijing_now()
    if now.weekday() >= 5:
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
