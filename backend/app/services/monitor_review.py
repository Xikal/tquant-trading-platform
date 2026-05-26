from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.schema_defs.market import MarketReviewReportOut, MarketReviewStatusOut
from app.services.market.review import build_market_review_summary, list_market_review_history


def build_monitor_review_summary(
    db: Session,
    *,
    user_id: int | None = None,
    target_date: date | None = None,
) -> tuple[MarketReviewStatusOut, list[MarketReviewReportOut]]:
    # user_id is accepted for backward compatibility; market reviews are not account-scoped.
    _ = user_id
    return build_market_review_summary(db, target_date=target_date)


def list_monitor_review_history(
    db: Session,
    *,
    user_id: int | None = None,
    limit: int = 20,
) -> list[MarketReviewReportOut]:
    _ = user_id
    return list_market_review_history(db, limit=limit)
