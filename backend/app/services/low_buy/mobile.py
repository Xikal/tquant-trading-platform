from __future__ import annotations

from typing import Optional

from app.repositories.low_buy.results import LowBuyResultRepository
from app.services.latest_data_status import expected_low_buy_trade_date, published_low_buy_trade_date
from app.services.low_buy_materialization import enqueue_low_buy_materialization
from app.services.low_buy.shared import (
    DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
    LowBuyCandidateOut,
    LowBuyScreenerResponse,
    Session,
)
from app.services.low_buy.screening_helpers import build_pending_full_response


class LowBuyMobileReadMixin:
    def _build_pending_full_response(
        self,
        strategy: str,
        latest_trade_date: str,
        requested_scan_limit: int,
        performance,
        full_scan_in_progress: bool,
    ) -> LowBuyScreenerResponse:
        return build_pending_full_response(
            strategy=strategy,
            playbook=self._get_playbook(strategy),
            latest_trade_date=latest_trade_date,
            requested_scan_limit=requested_scan_limit,
            performance=performance,
            full_scan_in_progress=full_scan_in_progress,
        )

    def _mobile_quick_history_timeout(self) -> float:
        timeout_seconds = float(getattr(self.market_data.settings, "app_mobile_quick_history_timeout", 6.0) or 6.0)
        return max(timeout_seconds, 1.0)

    def mobile_snapshot(
        self,
        db: Session,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        limit: int = 12,
        fallback_scan_limit: int = 24,
        history_wait_timeout_seconds: float | None = None,
    ) -> LowBuyScreenerResponse:
        normalized_limit = max(limit, 12)
        latest_trade_date = self._resolve_mobile_target_trade_date(db)
        materialized = self._load_cached_full_result(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            limit=normalized_limit,
            include_history=False,
        )
        if materialized is not None:
            materialized = self._attach_strategy_performance(
                db=db,
                payload=materialized,
                build_if_missing=False,
            )
            return self._normalize_mobile_snapshot(materialized)

        if db is not None:
            enqueue_low_buy_materialization(db, reason="mobile_latest_missing", commit=True)
        performance = self._load_strategy_performance_snapshot(
            db=db,
            strategy=strategy,
            latest_trade_date=latest_trade_date,
        ) or self._empty_strategy_performance(target_profit_pct=self._load_stock_profit_target_pct(db))
        is_running = False
        if hasattr(self, "_is_full_scan_running"):
            is_running = self._is_full_scan_running(
                strategy=strategy,
                latest_trade_date=latest_trade_date,
                limit=normalized_limit,
                include_history=False,
            )
        pending_builder = getattr(self, "_build_pending_full_response", None)
        if callable(pending_builder) and hasattr(self, "_get_playbook"):
            pending = pending_builder(
                strategy=strategy,
                latest_trade_date=latest_trade_date,
                requested_scan_limit=max(normalized_limit, fallback_scan_limit),
                performance=performance,
                full_scan_in_progress=is_running,
            )
            return self._normalize_mobile_snapshot(pending)

        fallback_payload = getattr(self, "payload", None)
        if fallback_payload is not None:
            return self._normalize_mobile_snapshot(
                fallback_payload.model_copy(
                    update={
                        "requested_mode": "quick",
                        "response_mode": "full",
                        "full_scan_ready": True,
                        "full_scan_in_progress": False,
                        "full_scan_updated_at": fallback_payload.as_of_date,
                    }
                )
            )
        raise RuntimeError("mobile snapshot requires materialized data or pending response builder")

    def _resolve_mobile_target_trade_date(self, db: Session) -> str:
        return published_low_buy_trade_date(db) or expected_low_buy_trade_date(db)

    def mobile_candidate_by_symbol(
        self,
        db: Session,
        symbol: str,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        detail_limit: int = 24,
        fallback_scan_limit: int = 24,
        history_wait_timeout_seconds: float | None = None,
    ) -> tuple[Optional[LowBuyCandidateOut], LowBuyScreenerResponse]:
        target_trade_date = self._resolve_mobile_target_trade_date(db)
        cached_candidate, cached_payload = self._load_cached_candidate_snapshot_by_symbol_any_mode(
            strategy=strategy,
            symbol=symbol,
        )
        if cached_candidate is not None and cached_payload is not None and cached_payload.latest_trade_date == target_trade_date:
            return cached_candidate, self._normalize_mobile_snapshot(cached_payload)

        materialized = self._load_latest_materialized_candidate_by_symbol(
            db=db,
            strategy=strategy,
            symbol=symbol,
            latest_trade_date=target_trade_date,
        )
        if materialized is not None:
            snapshot = self.mobile_snapshot(
                db=db,
                strategy=strategy,
                limit=12,
                fallback_scan_limit=min(max(fallback_scan_limit, 24), 48),
                history_wait_timeout_seconds=history_wait_timeout_seconds,
            )
            return materialized, snapshot

        snapshot_limit = min(max(detail_limit, 12), 24)
        snapshot = self.mobile_snapshot(
            db=db,
            strategy=strategy,
            limit=snapshot_limit,
            fallback_scan_limit=min(max(fallback_scan_limit, snapshot_limit), 48),
            history_wait_timeout_seconds=history_wait_timeout_seconds,
        )
        candidate = self._find_candidate(snapshot, symbol)
        if candidate is not None:
            return candidate, snapshot

        cached_candidate = self._load_cached_candidates_by_symbol_any_mode(
            strategy=strategy,
            latest_trade_date=snapshot.latest_trade_date,
            symbols=[symbol],
        ).get(symbol)
        if cached_candidate is not None:
            return cached_candidate, snapshot
        return None, snapshot

    def _load_latest_materialized_candidate_by_symbol(
        self,
        db: Session,
        strategy: str,
        symbol: str,
        latest_trade_date: str,
    ) -> Optional[LowBuyCandidateOut]:
        summary = LowBuyResultRepository(db).fetch_scan_summary(
            latest_trade_date=latest_trade_date,
            strategy_key=strategy,
        )
        if summary is None:
            return None
        materialized = self._load_materialized_candidates_by_symbol(
            db=db,
            strategy=strategy,
            latest_trade_date=summary.latest_trade_date,
            symbols=[symbol],
        )
        return materialized.get(symbol)

    @staticmethod
    def _find_candidate(payload: LowBuyScreenerResponse, symbol: str) -> Optional[LowBuyCandidateOut]:
        for item in payload.confirmed_candidates + payload.candidates:
            if item.symbol == symbol:
                return item
        return None

    @staticmethod
    def _normalize_mobile_snapshot(payload: LowBuyScreenerResponse) -> LowBuyScreenerResponse:
        updated_at = payload.full_scan_updated_at or payload.as_of_date
        return payload.model_copy(
            update={
                "requested_mode": "quick",
                "full_scan_ready": True,
                "full_scan_in_progress": False,
                "full_scan_updated_at": updated_at,
            }
        )
