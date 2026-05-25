from __future__ import annotations

import logging
from datetime import date, time as dt_time

from app.core.database import SessionLocal
from app.core.timezone import beijing_now, beijing_today
from app.services.paper.archive import PaperArchiveService

logger = logging.getLogger(__name__)
_paper_archive_last_run_date: date | None = None
_paper_midday_review_last_run_date: date | None = None


def archive_paper_performance_once(*, include_report: bool = True) -> None:
    global _paper_archive_last_run_date
    if not paper_archive_due():
        return
    today = beijing_today()
    if _paper_archive_last_run_date == today:
        return
    with SessionLocal() as db:
        service = PaperArchiveService(db)
        results = service.archive_all_active(include_report=include_report)
        _paper_archive_last_run_date = today
        logger.info("模拟盘绩效归档完成: %s", results)


def generate_midday_paper_review_once() -> None:
    global _paper_midday_review_last_run_date
    if not paper_midday_review_due():
        return
    today = beijing_today()
    if _paper_midday_review_last_run_date == today:
        return
    with SessionLocal() as db:
        results = PaperArchiveService(db).generate_review_reports_for_active(
            report_slot="midday",
            target_date=today,
        )
        _paper_midday_review_last_run_date = today
        logger.info("模拟盘午盘复盘完成: %s", results)


def paper_archive_due() -> bool:
    from app.core.config import get_settings

    settings = get_settings()
    try:
        hour, minute = [int(part) for part in settings.paper_perf_archive_time.split(":", 1)]
        archive_time = dt_time(hour=hour, minute=minute)
    except (TypeError, ValueError):
        logger.warning("PAPER_PERF_ARCHIVE_TIME 配置无效: %s", settings.paper_perf_archive_time)
        archive_time = dt_time(hour=15, minute=5)
    return beijing_now().time() >= archive_time


def paper_midday_review_due() -> bool:
    now = beijing_now()
    if now.weekday() >= 5:
        return False
    return now.time() >= dt_time(hour=11, minute=35)
