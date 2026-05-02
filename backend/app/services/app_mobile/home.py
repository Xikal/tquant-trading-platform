from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.schemas import AppHomeResponse, AppHomeSummary
from app.services.app_mobile.common import collect_warning_messages, now_string


class AppMobileHomeMixin:
    def home(self, db: Session, user_id: int | None = None) -> AppHomeResponse:
        cards = self._build_watchlist_cards(db, user_id=user_id)
        summary = AppHomeSummary(
            total=len(cards),
            positive_t_count=sum(1 for item in cards if item.signal.action == "positive_t"),
            negative_t_count=sum(1 for item in cards if item.signal.action == "negative_t"),
            hold_count=sum(1 for item in cards if item.signal.action == "hold"),
            high_risk_count=sum(1 for item in cards if item.signal.risk_level == "high"),
        )
        warnings = collect_warning_messages(card.error for card in cards)
        return AppHomeResponse(
            summary=summary,
            items=cards,
            updated_at=now_string(),
            is_stale=any(card.is_stale for card in cards),
            warnings=warnings,
        )
