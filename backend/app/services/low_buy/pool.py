from __future__ import annotations

import time

from app.models.entities import LowBuyPoolSnapshot
from app.repositories.low_buy import (
    DailyHistoryRepository,
    LowBuyPoolRepository,
    LowBuyResultRepository,
)
from app.services.low_buy.shared import (
    Any,
    BoardCandidate,
    DataSourceError,
    INTRADAY_STRUCTURE_START_HOUR,
    INTRADAY_STRUCTURE_START_MINUTE,
    LowBuyScreenerResponse,
    PLAYBOOKS,
    Session,
    SessionLocal,
    ak,
    date,
    datetime,
)
from app.services.low_buy.strategy_policy import requires_mainline_industry
from app.services.low_buy.strategy_pool_builder import StrategyPoolBuilder
from app.services.low_buy.strategy_pool_config import (
    strategy_pool_profile,
    strategy_pool_title,
    strategy_uses_daily_scan_pool,
)


_STRATEGY_BOARD_WINDOW_DAYS = {
    "divergence_consensus": 13,
    "late_session_strong_support": 14,
    "core_midcap_vwap_ma5_retrace": 14,
    "sector_mainline_first_divergence_low_buy": 14,
}

_STRATEGY_RETRACEMENT_DAYS_MAX = {
    "classic_retrace": 7,
    "divergence_consensus": 12,
    "late_session_strong_support": 8,
    "core_midcap_vwap_ma5_retrace": 8,
    "sector_mainline_first_divergence_low_buy": 8,
}

class LowBuyPoolMixin:
    def _build_retracement_buckets(
        self,
        ranked_pool: list[BoardCandidate],
        completed_trade_dates: list[str],
        latest_trade_date: str,
        max_days: int = 7,
    ) -> dict[int, list[BoardCandidate]]:
        trade_date_index = {trade_date: index for index, trade_date in enumerate(completed_trade_dates)}
        latest_index = trade_date_index.get(latest_trade_date)
        buckets = {days: [] for days in range(1, max_days + 1)}
        if latest_index is None:
            return buckets
        for item in ranked_pool:
            board_index = trade_date_index.get(item.board_date)
            if board_index is None:
                continue
            retracement_days = latest_index - board_index
            if 1 <= retracement_days <= max_days:
                buckets[retracement_days].append(item)
        return buckets

    def _resolve_active_structure_trade_date(
        self,
        trade_dates: list[str],
        latest_completed_trade_date: str,
    ) -> str:
        if not trade_dates:
            return latest_completed_trade_date
        today = date.today().isoformat()
        if today <= latest_completed_trade_date or today not in trade_dates:
            return latest_completed_trade_date
        now = datetime.now()
        after_structure_open = (now.hour, now.minute) >= (
            INTRADAY_STRUCTURE_START_HOUR,
            INTRADAY_STRUCTURE_START_MINUTE,
        )
        during_session = (now.hour, now.minute) >= (9, 30) and (now.hour, now.minute) <= (15, 10)
        return today if after_structure_open and during_session else latest_completed_trade_date

    def _build_balanced_scan_pool(
        self,
        retracement_buckets: dict[int, list[BoardCandidate]],
        scan_limit: int,
    ) -> list[BoardCandidate]:
        max_days = max(retracement_buckets) if retracement_buckets else 7
        day_priority = [2, 3, 4, 1, 5, 6, 7, *range(8, max_days + 1)]
        available_days = [day for day in day_priority if retracement_buckets.get(day)]
        if not available_days:
            return []

        selected: list[BoardCandidate] = []
        cursor_by_day = {day: 0 for day in available_days}
        base_quota = max(1, scan_limit // len(available_days))
        for day in available_days:
            batch = retracement_buckets[day][:base_quota]
            selected.extend(batch)
            cursor_by_day[day] = len(batch)

        while len(selected) < scan_limit:
            progressed = False
            for day in day_priority:
                if day not in cursor_by_day:
                    continue
                cursor = cursor_by_day[day]
                bucket = retracement_buckets[day]
                if cursor >= len(bucket):
                    continue
                selected.append(bucket[cursor])
                cursor_by_day[day] = cursor + 1
                progressed = True
                if len(selected) >= scan_limit:
                    break
            if not progressed:
                break
        return selected[:scan_limit]

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

    def _resolve_latest_completed_trade_date(self, trade_dates: list[str]) -> str:
        latest_completed_fallback = trade_dates[-2]
        try:
            with SessionLocal() as db:
                repository = DailyHistoryRepository(db)
                latest_complete_trade_date = repository.latest_complete_trade_date(
                    max_trade_date=trade_dates[-1],
                    min_stock_count=4500,
                )
                latest_stored_trade_date = repository.latest_trade_date_for_symbol("000001")
                latest_stored_count = (
                    repository.stock_count_by_trade_date(latest_stored_trade_date)
                    if latest_stored_trade_date
                    else 0
                )
        except Exception:
            latest_complete_trade_date = None
            latest_stored_trade_date = None
            latest_stored_count = 0
        if latest_complete_trade_date and latest_complete_trade_date >= latest_completed_fallback:
            return str(latest_complete_trade_date)
        if (
            latest_stored_trade_date
            and latest_stored_trade_date >= latest_completed_fallback
            and latest_stored_count >= 4500
        ):
            return str(latest_stored_trade_date)
        latest_artifact_trade_date = self._load_latest_low_buy_artifact_trade_date(trade_dates)
        if latest_artifact_trade_date and latest_artifact_trade_date >= latest_completed_fallback:
            return latest_artifact_trade_date

        probe = self._load_daily_history("000001", trade_dates[-1], history_window_days=20)
        if probe is not None and not probe.empty:
            probe_trade_date = str(probe["date"].iloc[-1])
            if self._has_complete_local_daily_bars(probe_trade_date):
                return probe_trade_date

        # Stage 6: walk backward through trade_dates to find a date with sufficient data.
        # The raw fallback (trade_dates[-2]) may have incomplete daily bar data (e.g.
        # only 420 stocks instead of 4500+).  Blindly returning it produces zero-filled
        # performance snapshots for daily-history strategies, which misleads the frontend
        # into showing 0% 达标率 when the real issue is incomplete data, not strategy failure.
        try:
            with SessionLocal() as db:
                repo = DailyHistoryRepository(db)
                for candidate_date in reversed(trade_dates[:-1]):
                    if repo.stock_count_by_trade_date(candidate_date) >= 4500:
                        return candidate_date
        except Exception:
            pass
        return latest_completed_fallback

    @staticmethod
    def _has_complete_local_daily_bars(trade_date: str, min_stock_count: int = 4500) -> bool:
        try:
            with SessionLocal() as db:
                return DailyHistoryRepository(db).stock_count_by_trade_date(trade_date) >= min_stock_count
        except Exception:
            return False

    def _load_latest_low_buy_artifact_trade_date(self, trade_dates: list[str]) -> str | None:
        if not trade_dates:
            return None
        try:
            with SessionLocal() as db:
                latest_trade_date = LowBuyResultRepository(db).fetch_latest_trade_date()
        except Exception:
            return None
        if latest_trade_date is None:
            return None
        normalized = str(latest_trade_date)
        return normalized if normalized in trade_dates else None

    def _get_recent_trade_dates(self, count: int) -> list[str]:
        cache_key = f"recent-trade-dates:{count}:{date.today().isoformat()}"
        cached = getattr(self, "_trade_dates_cache", {}).get(cache_key)
        now = time.monotonic()
        if cached and cached[0] > now:
            return list(cached[1])

        local_values = self._load_recent_trade_dates_from_local_store(count)
        if len(local_values) >= min(count, 3):
            return self._cache_recent_trade_dates(cache_key, local_values)

        trade_df = self.market_data._call_akshare(ak.tool_trade_date_hist_sina, purpose="trade_dates")
        values = [item.isoformat() if hasattr(item, "isoformat") else str(item) for item in trade_df["trade_date"].tolist()]
        today = date.today().isoformat()
        return self._cache_recent_trade_dates(cache_key, [item for item in values if item <= today][-count:])

    def _load_recent_trade_dates_from_local_store(self, count: int) -> list[str]:
        try:
            with SessionLocal() as db:
                values = DailyHistoryRepository(db).fetch_recent_trade_dates(count)
        except Exception:
            return []
        today = date.today().isoformat()
        return [item for item in values if item <= today][-count:]

    def _cache_recent_trade_dates(self, cache_key: str, values: list[str]) -> list[str]:
        cache = getattr(self, "_trade_dates_cache", None)
        if cache is None:
            cache = {}
            setattr(self, "_trade_dates_cache", cache)
        ttl = float(getattr(self, "_trade_dates_cache_ttl", 3600.0))
        cache[cache_key] = (time.monotonic() + ttl, list(values))
        return list(values)

    def _load_recent_limit_up_pool(self, trade_dates: list[str]) -> dict[str, BoardCandidate]:
        pooled: dict[str, BoardCandidate] = {}
        for trade_date in reversed(trade_dates):
            frame = self.market_data._call_akshare(
                ak.stock_zt_pool_em,
                date=trade_date.replace("-", ""),
                purpose="limit_pool",
            )
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
        return sorted(
            [item for item in candidates.values() if item.board_date < latest_trade_date],
            key=lambda item: (item.board_date, item.board_count == 1, item.amount),
            reverse=True,
        )

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
        seen: set[str] = set()
        result: list[BoardCandidate] = []
        for item in items:
            if item.symbol in seen:
                continue
            seen.add(item.symbol)
            result.append(item)
        return result

    @staticmethod
    def _merge_candidates(*groups: list[BoardCandidate]) -> list[BoardCandidate]:
        merged: list[BoardCandidate] = []
        seen: set[str] = set()
        for group in groups:
            for item in group:
                if item.symbol in seen:
                    continue
                seen.add(item.symbol)
                merged.append(item)
        return merged

    @staticmethod
    def _dedupe_candidates(items: list[LowBuyCandidateOut]) -> list[LowBuyCandidateOut]:
        deduped: dict[str, LowBuyCandidateOut] = {}
        for item in items:
            current = deduped.get(item.symbol)
            if current is None or item.score > current.score:
                deduped[item.symbol] = item
        return list(deduped.values())
