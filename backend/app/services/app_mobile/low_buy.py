from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import UserWatchlist, Watchlist
from app.models.schemas import (
    AppFavoriteStatus,
    AppLowBuyDetailResponse,
    AppLowBuyFavoriteRequest,
    AppLowBuyResponse,
    AppLowBuyStrategySummary,
    AppLowBuySummary,
    AppMutationResponse,
    WatchlistCreate,
)
from app.services.app_mobile.common import collect_warning_messages, now_string
from app.services.app_mobile.low_buy_projection import build_priority_board
from app.services.low_buy.shared import DEFAULT_PRODUCTION_LOW_BUY_STRATEGY
from app.services.strategy_metadata_service import StrategyMetadataService
from app.services.user_sector_preferences import (
    UserSectorPreferenceService,
    candidate_matches_excluded_sector,
    filter_low_buy_screener_response,
)


class AppMobileLowBuyMixin:
    def low_buy(
        self,
        db: Session,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        limit: int = 12,
        scan_limit: int = 48,
        scan_mode: str = "quick",
        user_id: int | None = None,
    ) -> AppLowBuyResponse:
        _ensure_app_strategy_allowed(db, strategy)
        screener_payload = self.low_buy_screener.mobile_snapshot(
            db=db,
            strategy=strategy,
            limit=limit,
            fallback_scan_limit=scan_limit,
        )
        if user_id is not None:
            excluded = UserSectorPreferenceService(db).get_excluded_sector_set(user_id)
            screener_payload = filter_low_buy_screener_response(screener_payload, excluded)
        priority_board = build_priority_board(screener_payload, limit=min(limit, 12))
        warnings = collect_warning_messages(
            [
                "移动端未命中全量物化结果，当前返回为快速候选视图。"
                if scan_mode == "full" and screener_payload.response_mode != "full"
                else None,
                "当前返回为快速候选视图，完整结果依赖后台物化任务。"
                if screener_payload.response_mode == "quick" and not screener_payload.full_scan_ready
                else None,
            ]
        )
        return AppLowBuyResponse(
            strategy=AppLowBuyStrategySummary(
                strategy_key=screener_payload.strategy_key,
                strategy_title=screener_payload.strategy_title,
                strategy_subtitle=screener_payload.strategy_subtitle,
                strategy_logic=screener_payload.strategy_logic,
            ),
            summary=AppLowBuySummary(
                as_of_date=screener_payload.as_of_date,
                latest_trade_date=screener_payload.latest_trade_date,
                pool_size=screener_payload.pool_size,
                scanned_count=screener_payload.scanned_count,
                matched_count=screener_payload.matched_count,
                full_scan_ready=screener_payload.full_scan_ready,
                full_scan_in_progress=screener_payload.full_scan_in_progress,
            ),
            priority_board=priority_board,
            confirmed_candidates=screener_payload.confirmed_candidates,
            watch_candidates=screener_payload.candidates,
            updated_at=screener_payload.full_scan_updated_at or screener_payload.as_of_date or now_string(),
            is_stale=screener_payload.response_mode == "quick" and not screener_payload.full_scan_ready,
            warnings=warnings,
        )

    def get_low_buy_detail(
        self,
        symbol: str,
        db: Session,
        strategy: str = DEFAULT_PRODUCTION_LOW_BUY_STRATEGY,
        scan_limit: int = 72,
        user_id: int | None = None,
    ) -> AppLowBuyDetailResponse:
        _ensure_app_strategy_allowed(db, strategy)
        detail_scan_limit = min(max(scan_limit, 24), 160)
        candidate, screener_payload = self.low_buy_screener.mobile_candidate_by_symbol(
            db=db,
            symbol=symbol,
            strategy=strategy,
            detail_limit=24,
            fallback_scan_limit=detail_scan_limit,
        )
        if candidate is None:
            raise LookupError("候选标的不存在")
        if user_id is not None:
            excluded = UserSectorPreferenceService(db).get_excluded_sector_set(user_id)
            if candidate_matches_excluded_sector(candidate, excluded):
                raise LookupError("该标的所属板块已被当前用户过滤")

        row = self._get_favorite_row(db, symbol=symbol, user_id=user_id)
        favorite_status = AppFavoriteStatus(
            in_watchlist=row is not None,
            watchlist_symbol=row.symbol if row is not None else None,
        )
        warnings = collect_warning_messages(
            [
                "当前详情来自快速候选视图，最终结果以后台物化快照为准。"
                if screener_payload.response_mode == "quick" and not screener_payload.full_scan_ready
                else None,
            ]
        )
        return AppLowBuyDetailResponse(
            candidate=candidate,
            favorite_status=favorite_status,
            updated_at=candidate.quote_timestamp or now_string(),
            is_stale=not bool(candidate.quote_timestamp),
            warnings=warnings,
        )

    def favorite_low_buy(
        self,
        symbol: str,
        payload: AppLowBuyFavoriteRequest,
        db: Session,
        user_id: int | None = None,
    ) -> AppMutationResponse:
        request = WatchlistCreate(
            symbol=symbol,
            name=payload.name,
            base_position=payload.base_position,
            available_position=payload.available_position,
            cost_basis=payload.cost_basis,
            memo=payload.memo,
        )
        return self.upsert_watchlist(request, db, user_id=user_id)

    @staticmethod
    def _get_favorite_row(db: Session, *, symbol: str, user_id: int | None):
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


def _ensure_app_strategy_allowed(db: Session, strategy_key: str) -> None:
    meta = StrategyMetadataService(db).list_strategy_meta().strategies
    allowed = {
        item.key
        for item in meta
        if item.enabled
        and item.visibility == "full"
        and item.tier in {"core", "auxiliary"}
    }
    if strategy_key not in allowed:
        raise ValueError("App 端仅支持生产层低吸策略")
