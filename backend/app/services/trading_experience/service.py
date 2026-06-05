from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.shared.feature_flags import feature_enabled
from app.services.trading_experience import holding_discipline, limit_up_followthrough, relative_strength, review_pool, review_workspace, t_trade_attribution, trade_journal, volume_position_tags
from app.services.trading_experience.config import ENGINE_VERSION, TRADING_EXPERIENCE_FLAGS
from app.services.trading_experience.guards import validate_observation_payload
from app.services.trading_experience.schemas import (
    BoardFilter,
    HoldingDisciplineResponse,
    LimitUpFollowthroughResponse,
    RelativeStrengthResponse,
    ReviewPoolResponse,
    ReviewWorkspaceResponse,
    TTradeAttributionResponse,
    TradeJournalEntryCreate,
    TradeJournalEntryUpdate,
    TradeJournalResponse,
    TradingExperienceReadinessResponse,
    VolumePositionTagResponse,
)

WORKER_TASK_TYPES = [
    "trading_experience_review_refresh",
    "trading_experience_tag_materialization",
    "trading_experience_relative_strength_refresh",
    "trading_experience_limit_up_backtest",
    "trading_experience_t_attribution_refresh",
]


class TradingExperienceService:
    def __init__(self, db: Session):
        self.db = db

    def readiness(self) -> TradingExperienceReadinessResponse:
        flags = self.flags()
        enabled = flags["trading_experience_suite_enabled"]
        response = TradingExperienceReadinessResponse(
            enabled=enabled,
            flags=flags,
            disabled_reasons=[] if enabled else ["trading_experience_suite_disabled"],
            worker_task_types=WORKER_TASK_TYPES,
            data_quality="ok" if enabled else "blocked",
            as_of=datetime.now(),
            engine_version=ENGINE_VERSION,
            source="settings",
            research_only=True,
        )
        return self._validated(response)

    def review_pool(self, *, pool_date: date | None, limit: int, board_filter: BoardFilter = "include_all") -> ReviewPoolResponse:
        if not self._enabled("trade_review_suite_enabled"):
            return self._disabled_review_pool()
        items = review_pool.list_review_pool(self.db, pool_date=pool_date, limit=limit, board_filter=board_filter)
        response = ReviewPoolResponse(
            enabled=True,
            pool_date=items[0].pool_date if items else (pool_date.isoformat() if pool_date else None),
            board_filter=board_filter,
            items=items,
            total=len(items),
            data_quality="ok" if items else "insufficient",
            as_of=datetime.now(),
            engine_version=ENGINE_VERSION,
            source="daily_bar_snapshots",
            research_only=True,
        )
        return self._validated(response)

    def review_workspace(
        self,
        *,
        pool_date: date | None,
        limit: int,
        board_filter: BoardFilter = "include_all",
        user_id: int | None,
    ) -> ReviewWorkspaceResponse:
        flags = self.flags()
        review_enabled = flags["trading_experience_suite_enabled"] and flags.get("trade_review_suite_enabled", False)
        rs_enabled = flags["trading_experience_suite_enabled"] and flags.get("relative_strength_board_enabled", False)
        if not review_enabled:
            return self._validated(
                review_workspace.disabled_workspace(
                    review_enabled=review_enabled,
                    relative_strength_enabled=rs_enabled,
                    board_filter=board_filter,
                )
            )
        return self._validated(
            review_workspace.build_workspace(
                self.db,
                pool_date=pool_date,
                limit=limit,
                board_filter=board_filter,
                relative_strength_enabled=rs_enabled,
                user_id=user_id,
            )
        )

    def trade_journal(self, *, user_id: int | None, account_id: int | None, symbol: str | None, limit: int) -> TradeJournalResponse:
        if not self._enabled("trade_review_suite_enabled"):
            return self._disabled_trade_journal()
        items = trade_journal.list_entries(self.db, user_id=user_id, account_id=account_id, symbol=symbol, limit=limit)
        response = TradeJournalResponse(
            enabled=True,
            items=items,
            total=len(items),
            data_quality="ok",
            as_of=datetime.now(),
            engine_version=ENGINE_VERSION,
            source="trade_journal",
            research_only=True,
        )
        return self._validated(response)

    def create_trade_journal(self, payload: TradeJournalEntryCreate, *, user_id: int | None):
        if not self._enabled("trade_review_suite_enabled"):
            raise ValueError("trade_review_suite_disabled")
        return self._validated(trade_journal.create_entry(self.db, payload, user_id=user_id))

    def update_trade_journal(self, entry_id: int, payload: TradeJournalEntryUpdate, *, user_id: int | None):
        if not self._enabled("trade_review_suite_enabled"):
            raise ValueError("trade_review_suite_disabled")
        return self._validated(trade_journal.update_entry(self.db, entry_id, payload, user_id=user_id))

    def delete_trade_journal(self, entry_id: int, *, user_id: int | None) -> None:
        if not self._enabled("trade_review_suite_enabled"):
            raise ValueError("trade_review_suite_disabled")
        trade_journal.delete_entry(self.db, entry_id, user_id=user_id)

    def volume_position_tags(self, symbol: str, *, trade_date: date | None) -> VolumePositionTagResponse:
        if not self._enabled("vp_position_tags_enabled"):
            return self._validated(VolumePositionTagResponse(enabled=False, symbol=symbol, items=[], data_quality="blocked", as_of=datetime.now(), engine_version=ENGINE_VERSION, source="feature_flag", research_only=True))
        items = volume_position_tags.build_tags(self.db, symbol, trade_date=trade_date)
        return self._validated(VolumePositionTagResponse(enabled=True, symbol=symbol, items=items, data_quality=items[0].data_quality if items else "insufficient", as_of=datetime.now(), engine_version=ENGINE_VERSION, source="daily_bar_snapshots", research_only=True))

    def relative_strength(self, *, trade_date: date | None, limit: int) -> RelativeStrengthResponse:
        if not self._enabled("relative_strength_board_enabled"):
            return self._validated(RelativeStrengthResponse(enabled=False, items=[], total=0, data_quality="blocked", as_of=datetime.now(), engine_version=ENGINE_VERSION, source="feature_flag", research_only=True))
        items = relative_strength.build_board(self.db, trade_date=trade_date, limit=limit)
        return self._validated(RelativeStrengthResponse(enabled=True, items=items, total=len(items), data_quality="ok" if items else "insufficient", as_of=datetime.now(), engine_version=ENGINE_VERSION, source="daily_bar_snapshots", research_only=True))

    def holding_discipline(self, *, account_id: int | None, user_id: int | None = None) -> HoldingDisciplineResponse:
        if not self._enabled("holding_discipline_assistant_enabled"):
            return self._validated(HoldingDisciplineResponse(enabled=False, account_id=account_id, items=[], total=0, data_quality="blocked", as_of=datetime.now(), engine_version=ENGINE_VERSION, source="feature_flag", research_only=True))
        resolved_account_id, items = holding_discipline.build_hints(self.db, account_id=account_id, user_id=user_id)
        return self._validated(HoldingDisciplineResponse(enabled=True, account_id=resolved_account_id, items=items, total=len(items), data_quality="ok" if items else "insufficient", as_of=datetime.now(), engine_version=ENGINE_VERSION, source="paper_positions", research_only=True))

    def limit_up_followthrough(self, *, trade_date: date | None, limit: int) -> LimitUpFollowthroughResponse:
        if not self._enabled("limit_up_followthrough_enabled"):
            return self._validated(LimitUpFollowthroughResponse(enabled=False, items=[], total=0, data_quality="blocked", as_of=datetime.now(), engine_version=ENGINE_VERSION, source="feature_flag", research_only=True))
        report = limit_up_followthrough.read_cached_backtest_report(self.db, trade_date=trade_date)
        gate = str((report or {}).get("backtest_gate") or "blocked")
        reasons = [str(item) for item in (report or {}).get("gate_reasons") or ["24m_backtest_not_available"]]
        items = limit_up_followthrough.build_items(self.db, trade_date=trade_date, limit=limit, backtest_report=report)
        response_quality = "blocked" if gate == "blocked" else "research_only" if gate == "failed" else "ok"
        return self._validated(
            LimitUpFollowthroughResponse(
                enabled=True,
                items=items,
                total=len(items),
                data_quality=response_quality,
                as_of=datetime.now(),
                engine_version=ENGINE_VERSION,
                source="trading_experience_snapshots" if report else "daily_bar_snapshots",
                research_only=True,
                backtest_gate=gate,  # type: ignore[arg-type]
                gate_reasons=reasons,
                backtest_window_months=int((report or {}).get("window_months") or 24),
            )
        )

    def t_trade_attribution(self, *, account_id: int | None, days: int, user_id: int | None = None) -> TTradeAttributionResponse:
        if not self._enabled("t_trade_discipline_enabled"):
            return self._validated(TTradeAttributionResponse(enabled=False, account_id=account_id, items=[], total=0, data_quality="blocked", as_of=datetime.now(), engine_version=ENGINE_VERSION, source="feature_flag", research_only=True))
        resolved_account_id, items = t_trade_attribution.build_attribution(self.db, account_id=account_id, user_id=user_id, days=days)
        quality = "ok" if items and all(item.data_quality == "ok" for item in items) else "no_data"
        return self._validated(TTradeAttributionResponse(enabled=True, account_id=resolved_account_id, items=items, total=len(items), data_quality=quality, as_of=datetime.now(), engine_version=ENGINE_VERSION, source="paper_trades", research_only=True))

    def flags(self) -> dict[str, bool]:
        settings = get_settings()
        return {
            key: feature_enabled(self.db, key, bool(getattr(settings, key, False)))
            for key in TRADING_EXPERIENCE_FLAGS
        }

    def _enabled(self, flag: str) -> bool:
        flags = self.flags()
        return flags["trading_experience_suite_enabled"] and flags.get(flag, False)

    def _disabled_review_pool(self) -> ReviewPoolResponse:
        return self._validated(ReviewPoolResponse(enabled=False, items=[], total=0, data_quality="blocked", as_of=datetime.now(), engine_version=ENGINE_VERSION, source="feature_flag", research_only=True))

    def _disabled_trade_journal(self) -> TradeJournalResponse:
        return self._validated(TradeJournalResponse(enabled=False, items=[], total=0, data_quality="blocked", as_of=datetime.now(), engine_version=ENGINE_VERSION, source="feature_flag", research_only=True))

    def _validated(self, response):
        validate_observation_payload(response.model_dump(mode="json") if hasattr(response, "model_dump") else response)
        return response
