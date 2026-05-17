from __future__ import annotations

from datetime import date

from app.models.entities import LowBuyPoolSnapshot
from app.repositories.low_buy import (
    DailyHistoryRepository,
    LowBuyPoolRepository,
)
from app.services.low_buy.shared import (
    Any,
    BoardCandidate,
    DataSourceError,
    LowBuyScreenerResponse,
    PLAYBOOKS,
    Session,
    SessionLocal,
)
from app.services.low_buy.pool_helpers import (
    build_balanced_scan_pool,
    build_retracement_buckets,
    dedupe_board_candidates,
    dedupe_candidates,
    merge_board_candidates,
    rank_pool_candidates,
)
from app.services.low_buy.pool_trade_dates import LowBuyTradeDateMixin
from app.services.low_buy.strategy_policy import requires_mainline_industry
from app.services.low_buy.strategy_pool_builder import StrategyPoolBuilder
from app.services.low_buy.strategy_pool_config import (
    strategy_pool_profile,
    strategy_pool_title,
    strategy_uses_daily_scan_pool,
)
from app.services.shared.feature_flags import feature_enabled


_STRATEGY_BOARD_WINDOW_DAYS = {
    "divergence_consensus": 13,
    "late_session_strong_support": 14,
    "core_midcap_vwap_ma5_retrace": 14,
    "sector_mainline_first_divergence_low_buy": 14,
    "mainline_limitup_shrink_retrace_reclaim": 18,
    "ma_channel_band": 30,
    "leader_pullback_band": 18,
    "n_pattern_long_wash": 24,
    "n_pattern_short_wash": 10,
}

_STRATEGY_RETRACEMENT_DAYS_MAX = {
    "classic_retrace": 7,
    "divergence_consensus": 12,
    "late_session_strong_support": 8,
    "core_midcap_vwap_ma5_retrace": 8,
    "sector_mainline_first_divergence_low_buy": 8,
    "mainline_limitup_shrink_retrace_reclaim": 8,
    "ma_channel_band": 14,
    "leader_pullback_band": 8,
    "n_pattern_long_wash": 15,
    "n_pattern_short_wash": 5,
}

class LowBuyPoolMixin(LowBuyTradeDateMixin):
    def _build_retracement_buckets(
        self,
        ranked_pool: list[BoardCandidate],
        completed_trade_dates: list[str],
        latest_trade_date: str,
        max_days: int = 7,
    ) -> dict[int, list[BoardCandidate]]:
        return build_retracement_buckets(
            ranked_pool=ranked_pool,
            completed_trade_dates=completed_trade_dates,
            latest_trade_date=latest_trade_date,
            max_days=max_days,
        )

    def _build_balanced_scan_pool(
        self,
        retracement_buckets: dict[int, list[BoardCandidate]],
        scan_limit: int,
    ) -> list[BoardCandidate]:
        return build_balanced_scan_pool(retracement_buckets, scan_limit)

    @staticmethod
    def _strategy_board_window_days(strategy: str) -> int:
        return _STRATEGY_BOARD_WINDOW_DAYS.get(strategy, 10)

    @staticmethod
    def _strategy_retracement_days_max(strategy: str) -> int:
        return _STRATEGY_RETRACEMENT_DAYS_MAX.get(strategy, 7)

    @staticmethod
    def _strategy_pool_profile_text(strategy: str) -> str:
        return strategy_pool_title(strategy)

    @staticmethod
    def _strategy_uses_local_daily_pool(strategy: str) -> bool:
        return strategy_uses_daily_scan_pool(strategy)

    def _load_strategy_scan_pool(
        self,
        *,
        db: Session,
        strategy: str,
        latest_trade_date: str,
        scan_limit: int,
        hot_industries: list[str],
        ranked_pool: list[BoardCandidate] | None = None,
    ) -> list[BoardCandidate] | None:
        profile = strategy_pool_profile(strategy)
        if not profile.enabled or not feature_enabled(db, f"strategy_{strategy}_enabled", profile.enabled):
            return []
        if requires_mainline_industry(strategy) and not hot_industries:
            return []

        builder = StrategyPoolBuilder(db)
        persisted = builder.load_persisted(
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            scan_limit=scan_limit,
        )
        if persisted is not None:
            return persisted

        if not profile.uses_daily_scan:
            if ranked_pool is None:
                return None
            candidates = builder.build_from_ranked(
                strategy=strategy,
                ranked_pool=ranked_pool,
                scan_limit=scan_limit,
            )
            builder.persist(
                latest_trade_date=latest_trade_date,
                strategy=strategy,
                candidates=candidates,
            )
            db.commit()
            return candidates

        candidates = builder.build_from_daily_history(
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            scan_limit=scan_limit,
            hot_industries=hot_industries,
            board_window_days=self._strategy_board_window_days(strategy),
            retracement_days_max=self._strategy_retracement_days_max(strategy),
        )
        builder.persist(
            latest_trade_date=latest_trade_date,
            strategy=strategy,
            candidates=candidates,
        )
        db.commit()
        return candidates

    def _prepare_strategy_scan_targets(
        self,
        *,
        strategy: str,
        scan_targets: list[BoardCandidate],
        hot_industries: list[str],
    ) -> list[BoardCandidate]:
        if not requires_mainline_industry(strategy):
            return scan_targets
        if not hot_industries:
            return []
        hot_set = {industry.strip() for industry in hot_industries if industry.strip()}
        if not hot_set:
            return []
        return [item for item in scan_targets if item.industry and item.industry in hot_set]

    def _load_recent_limit_up_pool(self, trade_dates: list[str]) -> dict[str, BoardCandidate]:
        pooled: dict[str, BoardCandidate] = {}
        for trade_date in reversed(trade_dates):
            routed = self.market_data.provider_router.fetch_limit_up_pool(trade_date)
            frame = routed.data if routed.usable else None
            if frame is None:
                continue
            if frame.empty:
                continue
            for row in frame.to_dict("records"):
                symbol = str(row.get("代码") or "").strip()
                if not symbol:
                    continue
                current = pooled.get(symbol)
                next_item = BoardCandidate(
                    symbol=symbol,
                    name=str(row.get("名称") or symbol).strip(),
                    board_date=trade_date,
                    board_count=int(float(row.get("连板数") or 1)),
                    amount=float(row.get("成交额") or 0.0),
                    industry=str(row.get("所属行业") or "").strip(),
                )
                if current is None or current.board_date < next_item.board_date:
                    pooled[symbol] = next_item
        return pooled

    def _load_ranked_pool(
        self,
        db: Session,
        latest_trade_date: str,
        board_dates: list[str],
    ) -> list[BoardCandidate]:
        persisted = self._load_persisted_pool(db=db, latest_trade_date=latest_trade_date)
        if persisted is not None:
            ranked = self._rank_pool_candidates(persisted, latest_trade_date)
            if ranked:
                return ranked
            fallback = self._load_latest_valid_persisted_pool(
                db=db,
                latest_trade_date=latest_trade_date,
                exclude_dates={latest_trade_date},
            )
            if fallback:
                merged = {**fallback, **persisted}
                self._persist_pool(db=db, latest_trade_date=latest_trade_date, pooled_candidates=merged)
                ranked = self._rank_pool_candidates(merged, latest_trade_date)
                if ranked:
                    return ranked

        if persisted is None:
            persisted = self._load_recent_limit_up_pool(board_dates)
            self._persist_pool(db=db, latest_trade_date=latest_trade_date, pooled_candidates=persisted)
        return self._rank_pool_candidates(persisted, latest_trade_date)

    @staticmethod
    def _rank_pool_candidates(
        candidates: dict[str, BoardCandidate],
        latest_trade_date: str,
    ) -> list[BoardCandidate]:
        return rank_pool_candidates(candidates, latest_trade_date)

    def _load_latest_valid_persisted_pool(
        self,
        db: Session,
        latest_trade_date: str,
        exclude_dates: set[str] | None = None,
    ) -> dict[str, BoardCandidate]:
        excluded = exclude_dates or set()
        repository = LowBuyPoolRepository(db)
        for trade_date in repository.fetch_recent_dates(latest_trade_date=latest_trade_date, limit=8):
            if trade_date in excluded:
                continue
            persisted = self._load_persisted_pool(db=db, latest_trade_date=trade_date)
            if not persisted:
                continue
            if self._rank_pool_candidates(persisted, latest_trade_date):
                return persisted
        return {}

    def _load_persisted_pool(
        self,
        db: Session,
        latest_trade_date: str,
    ) -> dict[str, BoardCandidate] | None:
        rows = LowBuyPoolRepository(db).fetch(latest_trade_date=latest_trade_date)
        if not rows:
            return None
        return {
            row.symbol: BoardCandidate(
                symbol=row.symbol,
                name=row.name,
                board_date=row.board_date,
                board_count=row.board_count,
                amount=row.amount,
                industry=row.industry,
            )
            for row in rows
        }

    def _persist_pool(
        self,
        db: Session,
        latest_trade_date: str,
        pooled_candidates: dict[str, BoardCandidate],
    ) -> None:
        rows = [
            LowBuyPoolSnapshot(
                latest_trade_date=latest_trade_date,
                symbol=item.symbol,
                name=item.name,
                board_date=item.board_date,
                board_count=item.board_count,
                amount=item.amount,
                industry=item.industry,
            )
            for item in pooled_candidates.values()
        ]
        LowBuyPoolRepository(db).replace(latest_trade_date=latest_trade_date, rows=rows)
        db.commit()

    def _get_playbook(self, strategy: str) -> dict[str, Any]:
        playbook = PLAYBOOKS.get(strategy)
        if playbook is None:
            raise DataSourceError(f"未知选股策略: {strategy}")
        return playbook

    def _is_excluded_symbol(self, symbol: str, name: str) -> bool:
        upper_name = name.upper()
        return "ST" in upper_name or symbol.startswith(("68", "4", "8"))

    @staticmethod
    def _dedupe_board_candidates(items: list[BoardCandidate]) -> list[BoardCandidate]:
        return dedupe_board_candidates(items)

    @staticmethod
    def _merge_candidates(*groups: list[BoardCandidate]) -> list[BoardCandidate]:
        return merge_board_candidates(*groups)

    @staticmethod
    def _dedupe_candidates(items: list[LowBuyCandidateOut]) -> list[LowBuyCandidateOut]:
        return dedupe_candidates(items)
