from __future__ import annotations

import threading
import time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import UserWatchlist, Watchlist
from app.models.schemas import (
    AppMutationResponse,
    AppWatchlistCard,
    AppWatchlistDetailResponse,
    AppWatchlistDetailSections,
    AppWatchlistResponse,
    AppWatchlistUpsertRequest,
    WatchlistItemOut,
)
from app.services.app_mobile.common import (
    collect_warning_messages,
    derive_stale_flag,
    headline_blocker,
    headline_reason,
    now_string,
)


class AppMobileWatchlistMixin:
    _user_watchlist_card_cache: dict[int, tuple[float, str, list[AppWatchlistCard]]] = {}
    _user_watchlist_card_cache_lock = threading.Lock()
    _user_watchlist_card_cache_ttl_seconds = 12.0

    def list_watchlist(self, db: Session, user_id: int | None = None) -> AppWatchlistResponse:
        rows = self._list_watchlist_rows(db, user_id=user_id)
        items = [self._to_watchlist_item(row) for row in rows]
        return AppWatchlistResponse(
            items=items,
            updated_at=now_string(),
            is_stale=False,
            warnings=[],
        )

    def upsert_watchlist(
        self,
        payload: AppWatchlistUpsertRequest,
        db: Session,
        user_id: int | None = None,
    ) -> AppMutationResponse:
        row = self._get_watchlist_row(db, payload.symbol, user_id=user_id)
        if row is None:
            values = payload.model_dump()
            row = UserWatchlist(user_id=user_id, **values) if user_id is not None else Watchlist(**values)
            db.add(row)
        else:
            row.name = payload.name or row.name
            row.base_position = payload.base_position
            row.available_position = payload.available_position
            row.cost_basis = payload.cost_basis
            row.memo = payload.memo
        db.commit()
        if user_id is None:
            self.watchlist_signal_service.ensure_background_refresh(force=True)
        else:
            self._invalidate_user_watchlist_cache(user_id)
        return self._mutation_response(message="自选股已保存", symbol=payload.symbol)

    def delete_watchlist(
        self,
        symbol: str,
        db: Session,
        user_id: int | None = None,
    ) -> AppMutationResponse:
        row = self._get_watchlist_row(db, symbol, user_id=user_id)
        if row is None:
            raise LookupError("自选股不存在")
        db.delete(row)
        db.commit()
        if user_id is None:
            self.watchlist_signal_service.invalidate_symbol(symbol)
            self.watchlist_signal_service.ensure_background_refresh(force=True)
        else:
            self._invalidate_user_watchlist_cache(user_id)
        return self._mutation_response(message="已删除", symbol=symbol)

    def get_watchlist_detail(
        self,
        symbol: str,
        db: Session,
        user_id: int | None = None,
    ) -> AppWatchlistDetailResponse:
        cards = self._build_watchlist_cards(db, user_id=user_id)
        for card in cards:
            if card.symbol != symbol:
                continue
            return AppWatchlistDetailResponse(
                symbol=card.symbol,
                name=card.name,
                base_position=card.base_position,
                available_position=card.available_position,
                cost_basis=card.cost_basis,
                memo=card.memo,
                quote=card.quote,
                signal=card.signal,
                rules=card.rules,
                detail_sections=AppWatchlistDetailSections(
                    reasons=list(card.signal.reasons),
                    blocking_rules=list(card.signal.blocking_rules),
                    strategy_notes=card.signal.strategy_notes,
                ),
                updated_at=card.updated_at,
                is_stale=card.is_stale,
                warnings=[card.error] if card.error else [],
            )
        raise LookupError("自选股不存在")

    def _build_watchlist_cards(self, db: Session, user_id: int | None = None) -> list[AppWatchlistCard]:
        if user_id is not None:
            return self._build_user_watchlist_cards(db, user_id)
        payloads = self.watchlist_signal_service.list_signals(db)
        return self._cards_from_payloads(payloads)

    def _build_user_watchlist_cards(self, db: Session, user_id: int) -> list[AppWatchlistCard]:
        rows = self._list_watchlist_rows(db, user_id=user_id)
        if not rows:
            return []
        fingerprint = self._watchlist_rows_fingerprint(rows)
        cached = self._get_cached_user_watchlist_cards(user_id, fingerprint)
        if cached is not None:
            return cached
        payloads = self.watchlist_signal_service.build_live_signals(db, rows)
        cards = self._cards_from_payloads(payloads)
        self._set_cached_user_watchlist_cards(user_id, fingerprint, cards)
        return cards

    @staticmethod
    def _cards_from_payloads(payloads: list[dict]) -> list[AppWatchlistCard]:
        cards: list[AppWatchlistCard] = []
        for item in payloads:
            quote_payload = dict(item.get("quote") or {})
            signal_payload = dict(item.get("signal") or {})
            rules_payload = dict(item.get("rules") or {})
            item_error = item.get("error")
            updated_at = quote_payload.get("timestamp") or now_string()
            is_stale = derive_stale_flag(item_error, quote_payload.get("timestamp"))
            cards.append(
                AppWatchlistCard(
                    symbol=item["symbol"],
                    name=item["name"],
                    base_position=item["base_position"],
                    available_position=item["available_position"],
                    cost_basis=item.get("cost_basis"),
                    memo=item.get("memo", ""),
                    quote=quote_payload,
                    signal=signal_payload,
                    rules=rules_payload,
                    headline_reason=headline_reason(signal_payload),
                    headline_blocker=headline_blocker(signal_payload),
                    plain_action_text=_plain_action_text(signal_payload),
                    plain_action_reason=_plain_action_reason(signal_payload),
                    plain_execution_text=_plain_execution_text(signal_payload),
                    plain_invalid_condition=_plain_invalid_condition(signal_payload),
                    error=item_error,
                    updated_at=updated_at,
                    is_stale=is_stale,
                )
            )
        return cards

    def _list_watchlist_rows(self, db: Session, user_id: int | None = None) -> list:
        if user_id is None:
            return db.execute(select(Watchlist).order_by(Watchlist.id.desc())).scalars().all()
        return (
            db.execute(
                select(UserWatchlist)
                .where(UserWatchlist.user_id == user_id)
                .order_by(UserWatchlist.id.desc())
            )
            .scalars()
            .all()
        )

    def _get_watchlist_row(self, db: Session, symbol: str, user_id: int | None = None):
        if user_id is None:
            return db.execute(select(Watchlist).where(Watchlist.symbol == symbol)).scalar_one_or_none()
        return (
            db.execute(
                select(UserWatchlist).where(
                    UserWatchlist.user_id == user_id,
                    UserWatchlist.symbol == symbol,
                )
            )
            .scalar_one_or_none()
        )

    @staticmethod
    def _to_watchlist_item(row: Watchlist) -> WatchlistItemOut:
        return WatchlistItemOut(
            symbol=row.symbol,
            name=row.name,
            base_position=row.base_position,
            available_position=row.available_position,
            cost_basis=row.cost_basis,
            memo=row.memo,
            created_at=row.created_at,
        )

    def _watchlist_response_warnings(self, cards: list[AppWatchlistCard]) -> list[str]:
        return collect_warning_messages(card.error for card in cards)

    @staticmethod
    def _mutation_response(message: str, symbol: str) -> AppMutationResponse:
        return AppMutationResponse(message=message, symbol=symbol)

    @staticmethod
    def _watchlist_rows_fingerprint(rows: list) -> str:
        return "|".join(
            f"{row.symbol}:{row.base_position}:{row.available_position}:{row.cost_basis}:{row.name}:{row.memo}"
            for row in rows
        )

    def _get_cached_user_watchlist_cards(
        self,
        user_id: int,
        fingerprint: str,
    ) -> list[AppWatchlistCard] | None:
        now = time.monotonic()
        with self._user_watchlist_card_cache_lock:
            cached = self._user_watchlist_card_cache.get(user_id)
            if cached is None:
                return None
            expires_at, cached_fingerprint, cards = cached
            if expires_at <= now or cached_fingerprint != fingerprint:
                self._user_watchlist_card_cache.pop(user_id, None)
                return None
            return cards

    def _set_cached_user_watchlist_cards(
        self,
        user_id: int,
        fingerprint: str,
        cards: list[AppWatchlistCard],
    ) -> None:
        with self._user_watchlist_card_cache_lock:
            self._user_watchlist_card_cache[user_id] = (
                time.monotonic() + self._user_watchlist_card_cache_ttl_seconds,
                fingerprint,
                cards,
            )

    def _invalidate_user_watchlist_cache(self, user_id: int) -> None:
        with self._user_watchlist_card_cache_lock:
            self._user_watchlist_card_cache.pop(user_id, None)


def _plain_action_text(signal_payload: dict) -> str:
    direct = _clean_text(signal_payload.get("plain_action_text"))
    if direct:
        return direct
    action = str(signal_payload.get("action") or "hold")
    risk_level = str(signal_payload.get("risk_level") or "")
    if risk_level == "high":
        return "风险偏高，先别加仓"
    if action == "positive_t":
        return "现在能买回"
    if action == "negative_t":
        return "现在能卖一部分"
    return "今天别动"


def _plain_action_reason(signal_payload: dict) -> str:
    direct = _clean_text(signal_payload.get("plain_action_reason"))
    if direct:
        return direct
    action = str(signal_payload.get("action") or "hold")
    reasons = signal_payload.get("reasons")
    first_reason = str(reasons[0]) if isinstance(reasons, list) and reasons else ""
    if action == "positive_t":
        trigger = signal_payload.get("entry_price")
        return f"触发价 {float(trigger):.3f} 附近出现承接。" if isinstance(trigger, (int, float)) else first_reason
    if action == "negative_t":
        trigger = signal_payload.get("exit_price")
        return f"冲高到 {float(trigger):.3f} 附近可先减一部分。" if isinstance(trigger, (int, float)) else first_reason
    blockers = signal_payload.get("blocking_rules")
    if isinstance(blockers, list) and blockers:
        return str(blockers[0])
    return first_reason or "价格还没到触发位。"


def _plain_execution_text(signal_payload: dict) -> str:
    direct = _clean_text(signal_payload.get("plain_execution_text"))
    if direct:
        return direct
    action = str(signal_payload.get("action") or "hold")
    entry = signal_payload.get("entry_price")
    exit_price = signal_payload.get("exit_price")
    if action == "positive_t" and isinstance(entry, (int, float)) and isinstance(exit_price, (int, float)):
        return f"等 {float(entry):.3f} 附近买入，反抽到 {float(exit_price):.3f} 附近卖出同等底仓。"
    if action == "negative_t" and isinstance(entry, (int, float)) and isinstance(exit_price, (int, float)):
        return f"冲高到 {float(entry):.3f} 附近先卖，回落到 {float(exit_price):.3f} 附近才接回。"
    return "没有足够确定的价差，先不做T。"


def _plain_invalid_condition(signal_payload: dict) -> str:
    direct = _clean_text(signal_payload.get("plain_invalid_condition"))
    if direct:
        return direct
    stop_loss = signal_payload.get("stop_loss")
    if isinstance(stop_loss, (int, float)) and stop_loss > 0:
        return f"跌破 {float(stop_loss):.3f} 先处理。"
    return "如果跌破关键支撑或放量走弱，先降级观察。"


def _clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()
