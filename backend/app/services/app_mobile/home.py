from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.schemas import AppHomeResponse, AppHomeSummary
from app.services.app_mobile.common import collect_warning_messages, now_string
from app.services.app_mobile.low_buy_projection import build_priority_board
from app.services.low_buy.shared import DEFAULT_PRODUCTION_LOW_BUY_STRATEGY
from app.services.user_sector_preferences import UserSectorPreferenceService, filter_low_buy_screener_response


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
        priority_board = None
        try:
            screener_payload = self.low_buy_screener.mobile_snapshot(
                db=db,
                strategy=DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
                limit=12,
                fallback_scan_limit=72,
            )
            if user_id is not None:
                excluded = UserSectorPreferenceService(db).get_excluded_sector_set(user_id)
                screener_payload = filter_low_buy_screener_response(screener_payload, excluded)
            priority_board = build_priority_board(screener_payload, limit=8)
        except Exception:
            warnings = collect_warning_messages([*warnings, "优先榜暂时不可用，当前仅展示持仓监控。"])

        today_action_title, today_action_note = _today_action(cards, priority_board)
        return AppHomeResponse(
            summary=summary,
            items=cards,
            priority_board=priority_board,
            today_action_title=today_action_title,
            today_action_note=today_action_note,
            updated_at=now_string(),
            is_stale=any(card.is_stale for card in cards) or bool(priority_board and any(item.data_quality != "fresh" for item in priority_board.items)),
            warnings=warnings,
        )


def _today_action(cards, priority_board) -> tuple[str, str]:
    high_risk = next((item for item in cards if item.signal.risk_level == "high"), None)
    if high_risk is not None:
        return (
            f"{high_risk.name} 需要先控风险",
            high_risk.headline_blocker or high_risk.plain_action_reason or "今天先不要追加，优先看风险信号。",
        )
    positive_t = next((item for item in cards if item.signal.action == "positive_t"), None)
    if positive_t is not None:
        return (
            f"{positive_t.name} 可以优先做 T",
            positive_t.plain_execution_text or positive_t.plain_action_reason or "按计划先卖后接回，不追价。",
        )
    top = priority_board.items[0] if priority_board and priority_board.items else None
    if top is not None:
        return (
            f"今天主看 {top.name}",
            top.next_action_text or top.action_summary or "只在建议买点区内处理。",
        )
    return ("今天先观察", "当前没有明确的高优先级动作，先等新信号。")
