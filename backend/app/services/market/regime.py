from __future__ import annotations

from dataclasses import asdict, replace
import json
import logging
import threading
import time

import pandas as pd
from sqlalchemy import desc, func, select

from app.core.database import SessionLocal
from app.models.entities import DailyBarSnapshot, MarketRegimeSnapshotCache
from app.services.market.regime_scoring import (
    classify_market_regime,
    clone_snapshot_with_state,
    market_breadth_sequence_key,
    market_regime_text,
    normalize_board_frame,
)
from app.services.market.regime_helpers import (
    clean_hot_sequences,
    ranked_hot_overlap_score,
    regime_data_quality,
    snapshot_from_payload,
    transition_risk as calculate_transition_risk,
)
from app.services.market.regime_types import (
    STATE_CONFIG,
    STYLE_PROXY_GROUPS,
    MarketBreadthSnapshot,
    MarketRegimeSnapshot,
)


logger = logging.getLogger(__name__)


class MarketRegimeMixin:
    _recent_hot_industries_cache: tuple[float, list[str]] = (0.0, [])
    _recent_hot_industries_ttl_seconds = 300.0

    def get_market_regime(
        self,
        *,
        latest_trade_date: str | None = None,
        hot_industries: list[str] | None = None,
        hot_industry_source: str = "",
        hot_industry_source_text: str = "",
        recent_hot_sequences: list[list[str]] | None = None,
    ) -> MarketRegimeSnapshot:
        trade_date = latest_trade_date or self._resolve_regime_trade_date(None) or "intraday"
        cached = self._get_compatible_regime_cache(trade_date, hot_industries)
        if cached is not None:
            return cached

        board_frame = self._load_board_breadth_frame()
        snapshot = classify_market_regime(
            board_frame,
            limit_down_count=self._load_limit_down_count_cached(
                trade_date if trade_date != "intraday" else None
            ),
            hot_industries=self._resolve_hot_industries(board_frame, hot_industries),
            hot_industry_source=hot_industry_source
            or ("board_strength" if board_frame is not None else "unavailable"),
            hot_industry_source_text=hot_industry_source_text
            or (
                "热点来源：板块涨幅实时榜"
                if board_frame is not None
                else "热点来源：暂无有效归因"
            ),
            breadth_snapshot=self._load_market_breadth_snapshot(recent_hot_sequences),
            emotion_snapshot=self._load_market_emotion_snapshot(
                trade_date if trade_date != "intraday" else None
            ),
        )
        snapshot = self._stabilize_market_regime(
            snapshot,
            self._peek_market_regime_snapshot(trade_date),
        )
        snapshot = self._apply_market_readiness_guard(snapshot)
        snapshot = self._apply_regime_continuity(
            snapshot,
            self._peek_market_regime_snapshot(trade_date),
        )
        snapshot = replace(snapshot, snapshot_source="live", snapshot_source_text="实时市场快照")
        self._set_market_regime_cache(trade_date, snapshot)
        self._persist_market_regime_snapshot(trade_date, snapshot)
        return snapshot

    def get_market_regime_fast(
        self,
        *,
        latest_trade_date: str | None = None,
        hot_industries: list[str] | None = None,
        hot_industry_source: str = "",
        hot_industry_source_text: str = "",
        recent_hot_sequences: list[list[str]] | None = None,
    ) -> MarketRegimeSnapshot:
        trade_date = latest_trade_date or self._resolve_regime_trade_date(None) or "intraday"
        cached = self._get_compatible_regime_cache(trade_date, hot_industries)
        if cached is not None:
            return cached
        self._warm_market_regime_snapshot_async(
            trade_date=trade_date,
            hot_industries=hot_industries or [],
            hot_industry_source=hot_industry_source,
            hot_industry_source_text=hot_industry_source_text,
            recent_hot_sequences=recent_hot_sequences or [],
        )
        persisted = self._load_persisted_market_regime_snapshot(trade_date, hot_industries)
        if persisted is not None:
            self._set_market_regime_cache(trade_date, persisted)
            return persisted
        return self._build_lightweight_market_regime(
            hot_industries=hot_industries or [],
            hot_industry_source=hot_industry_source,
            hot_industry_source_text=hot_industry_source_text,
        )

    def _warm_market_regime_snapshot_async(
        self,
        *,
        trade_date: str,
        hot_industries: list[str],
        hot_industry_source: str,
        hot_industry_source_text: str,
        recent_hot_sequences: list[list[str]],
    ) -> None:
        with self._cache_lock:
            if trade_date in self._market_regime_jobs:
                return
            self._market_regime_jobs.add(trade_date)

        def runner() -> None:
            try:
                self.get_market_regime(
                    latest_trade_date=None if trade_date == "intraday" else trade_date,
                    hot_industries=hot_industries,
                    hot_industry_source=hot_industry_source,
                    hot_industry_source_text=hot_industry_source_text,
                    recent_hot_sequences=recent_hot_sequences,
                )
            finally:
                with self._cache_lock:
                    self._market_regime_jobs.discard(trade_date)

        threading.Thread(target=runner, name=f"market-regime-{trade_date}", daemon=True).start()

    @staticmethod
    def _build_lightweight_market_regime(
        *,
        hot_industries: list[str],
        hot_industry_source: str,
        hot_industry_source_text: str,
    ) -> MarketRegimeSnapshot:
        snapshot = classify_market_regime(
            None,
            limit_down_count=None,
            hot_industries=hot_industries,
            hot_industry_source=hot_industry_source or "cached_fallback",
            hot_industry_source_text=hot_industry_source_text or "热点来源：后台补齐中",
        )
        return replace(
            snapshot,
            snapshot_source="warming",
            snapshot_source_text="市场状态正在刷新，暂用轻量快照",
        )

    def _get_compatible_regime_cache(
        self,
        cache_key: str,
        hot_industries: list[str] | None,
    ) -> MarketRegimeSnapshot | None:
        cached = self._get_market_regime_cache(cache_key)
        if cached is not None and (not hot_industries or hot_industries == cached.hot_industries):
            return cached
        return None

    @classmethod
    def _resolve_hot_industries(
        cls,
        board_frame: pd.DataFrame | None,
        hot_industries: list[str] | None,
    ) -> list[str]:
        if hot_industries:
            cls._remember_hot_industries(hot_industries)
            return hot_industries
        if board_frame is None:
            return cls._recent_hot_industries()
        resolved = board_frame.head(3)["industry"].tolist()
        cls._remember_hot_industries(resolved)
        return resolved

    @classmethod
    def _remember_hot_industries(cls, industries: list[str]) -> None:
        values = [item for item in industries if item]
        if values:
            cls._recent_hot_industries_cache = (
                time.monotonic() + cls._recent_hot_industries_ttl_seconds,
                values,
            )

    @classmethod
    def _recent_hot_industries(cls) -> list[str]:
        expires_at, values = cls._recent_hot_industries_cache
        if time.monotonic() < expires_at:
            return list(values)
        return []

    def _stabilize_market_regime(
        self,
        snapshot: MarketRegimeSnapshot,
        previous_snapshot: MarketRegimeSnapshot | None,
    ) -> MarketRegimeSnapshot:
        if previous_snapshot is None or previous_snapshot.state == snapshot.state:
            return snapshot
        if abs(snapshot.regime_score - previous_snapshot.regime_score) >= 6.0:
            return snapshot
        if previous_snapshot.state_strength < snapshot.state_strength:
            return snapshot
        return clone_snapshot_with_state(
            snapshot,
            state=previous_snapshot.state,
            state_strength=previous_snapshot.state_strength,
            regime_score=previous_snapshot.regime_score,
        )

    @staticmethod
    def _apply_regime_continuity(
        snapshot: MarketRegimeSnapshot,
        previous_snapshot: MarketRegimeSnapshot | None,
    ) -> MarketRegimeSnapshot:
        if previous_snapshot is None:
            return snapshot
        transition_risk = calculate_transition_risk(snapshot, previous_snapshot)
        persistence_days = previous_snapshot.state_persistence_days if snapshot.state == previous_snapshot.state else 1
        confidence = max(0.0, min(1.0, snapshot.regime_confidence - transition_risk * 0.18))
        return replace(
            snapshot,
            state_persistence_days=max(1, persistence_days),
            transition_risk=transition_risk,
            regime_confidence=round(confidence, 4),
        )

    def _apply_market_readiness_guard(self, snapshot: MarketRegimeSnapshot) -> MarketRegimeSnapshot:
        if snapshot.breadth_ready and snapshot.emotion_ready:
            return snapshot
        if snapshot.state not in self._guarded_states():
            return snapshot
        return clone_snapshot_with_state(
            snapshot,
            state="low_volume_wait",
            state_strength=min(snapshot.state_strength, 0.35),
            regime_score=min(snapshot.regime_score, 42.0),
            description_suffix="环境快照仍在补齐，先按中性偏防守处理。",
        )

    @staticmethod
    def _guarded_states() -> set[str]:
        return {
            "broad_rally",
            "repair",
            "weight_support",
            "weight_support_active",
            "high_flyer_retreat",
            "risk_release",
        }

    def _load_board_breadth_frame(self) -> pd.DataFrame | None:
        result = self.provider_router.fetch_board_breadth_frame()
        if result.usable and result.data is not None:
            return normalize_board_frame(result.data)
        return None

    def _load_market_breadth_snapshot(
        self,
        recent_hot_sequences: list[list[str]] | None = None,
    ) -> MarketBreadthSnapshot:
        sequences = recent_hot_sequences or []
        cache_key = self._market_breadth_cache_key(sequences)
        cached = self._get_market_breadth_cache(cache_key)
        if cached is not None:
            return cached

        snapshot_map = self._get_spot_snapshot_cache("stock") or {}
        if not snapshot_map:
            self._warm_market_breadth_snapshot_async(cache_key, sequences)
            local_snapshot = self._load_local_daily_breadth_snapshot(sequences)
            if local_snapshot is not None:
                self._set_market_breadth_cache(cache_key, local_snapshot)
                return local_snapshot
            return self._build_market_breadth_snapshot(
                snapshot_map={},
                recent_hot_sequences=sequences,
                breadth_ready=False,
            )

        snapshot = self._build_market_breadth_snapshot(
            snapshot_map=snapshot_map,
            recent_hot_sequences=sequences,
            breadth_ready=True,
        )
        self._set_market_breadth_cache(cache_key, snapshot)
        return snapshot

    def _load_local_daily_breadth_snapshot(
        self,
        recent_hot_sequences: list[list[str]],
    ) -> MarketBreadthSnapshot | None:
        """Fallback breadth from local daily bars when real-time breadth is unavailable."""

        try:
            with SessionLocal() as db:
                candidates = db.execute(
                    select(DailyBarSnapshot.trade_date, func.count(DailyBarSnapshot.id).label("row_count"))
                    .where(DailyBarSnapshot.instrument_type == "stock")
                    .group_by(DailyBarSnapshot.trade_date)
                    .order_by(desc(DailyBarSnapshot.trade_date))
                    .limit(5)
                ).all()
                trade_date = next(
                    (
                        row.trade_date
                        for row in candidates
                        if int(row._mapping.get("row_count") or 0) >= 1000
                    ),
                    None,
                )
                if not trade_date:
                    return None
                rows = db.execute(
                    select(DailyBarSnapshot.pct_chg)
                    .where(
                        DailyBarSnapshot.instrument_type == "stock",
                        DailyBarSnapshot.trade_date == trade_date,
                    )
                ).all()
        except Exception:
            logger.exception("failed to load local daily breadth fallback")
            return None
        changes = [float(row.pct_chg or 0.0) for row in rows]
        if not changes:
            return None
        frame = pd.Series(changes, dtype="float64")
        largecap_change, smallcap_change = self._load_style_proxy_changes()
        return MarketBreadthSnapshot(
            breadth_ready=True,
            stock_up_ratio=round(float((frame > 0).mean()), 4),
            stock_median_change=round(float(frame.median()), 4),
            largecap_change=largecap_change,
            smallcap_change=smallcap_change,
            style_divergence=round(largecap_change - smallcap_change, 4),
            hot_turnover=self._compute_hot_turnover(recent_hot_sequences),
            hot_overlap_ratio=self._compute_hot_overlap_ratio(recent_hot_sequences),
        )

    def _warm_market_breadth_snapshot_async(
        self,
        cache_key: str,
        recent_hot_sequences: list[list[str]],
    ) -> None:
        with self._cache_lock:
            if cache_key in self._market_breadth_jobs:
                return
            self._market_breadth_jobs.add(cache_key)

        def runner() -> None:
            try:
                snapshot = self._build_market_breadth_snapshot(
                    snapshot_map={},
                    recent_hot_sequences=recent_hot_sequences,
                    breadth_ready=False,
                )
                self._set_market_breadth_cache(cache_key, snapshot)
            finally:
                with self._cache_lock:
                    self._market_breadth_jobs.discard(cache_key)

        threading.Thread(target=runner, name=f"market-breadth-{cache_key}", daemon=True).start()

    def _build_market_breadth_snapshot(
        self,
        *,
        snapshot_map,
        recent_hot_sequences: list[list[str]],
        breadth_ready: bool,
    ) -> MarketBreadthSnapshot:
        changes = [item.change_pct for item in snapshot_map.values()] if snapshot_map else []
        frame = pd.Series(changes, dtype="float64") if changes else pd.Series(dtype="float64")
        stock_up_ratio = round(float((frame > 0).mean()), 4) if not frame.empty else 0.0
        stock_median_change = round(float(frame.median()), 4) if not frame.empty else 0.0
        largecap_change, smallcap_change = self._load_style_proxy_changes()
        return MarketBreadthSnapshot(
            breadth_ready=breadth_ready,
            stock_up_ratio=stock_up_ratio,
            stock_median_change=stock_median_change,
            largecap_change=largecap_change,
            smallcap_change=smallcap_change,
            style_divergence=round(largecap_change - smallcap_change, 4),
            hot_turnover=self._compute_hot_turnover(recent_hot_sequences),
            hot_overlap_ratio=self._compute_hot_overlap_ratio(recent_hot_sequences),
        )

    @staticmethod
    def _market_breadth_cache_key(recent_hot_sequences: list[list[str]] | None) -> str:
        return market_breadth_sequence_key(recent_hot_sequences or [])

    def _load_style_proxy_changes(self) -> tuple[float, float]:
        symbols = list({symbol for values in STYLE_PROXY_GROUPS.values() for symbol in values})
        quote_map = self.get_quotes_batch(symbols)
        return (
            self._average_quote_change(quote_map, STYLE_PROXY_GROUPS["large"]),
            self._average_quote_change(quote_map, STYLE_PROXY_GROUPS["small"]),
        )

    @staticmethod
    def _average_quote_change(quote_map, symbols: tuple[str, ...]) -> float:
        values = [
            float(getattr(quote_map.get(symbol), "change_pct", 0.0) or 0.0)
            for symbol in symbols
            if quote_map.get(symbol) is not None
        ]
        if not values:
            return 0.0
        return round(sum(values) / len(values), 4)

    @staticmethod
    def _compute_hot_turnover(sequences: list[list[str]]) -> float:
        cleaned = clean_hot_sequences(sequences)
        if len(cleaned) < 2:
            return 0.0
        turnovers: list[float] = []
        for left, right in zip(cleaned, cleaned[1:]):
            turnovers.append(1.0 - ranked_hot_overlap_score(left, right))
        if not turnovers:
            return 0.0
        return round(sum(turnovers) / len(turnovers), 4)

    @staticmethod
    def _compute_hot_overlap_ratio(sequences: list[list[str]]) -> float:
        cleaned = clean_hot_sequences(sequences)
        if len(cleaned) < 2:
            return 0.0
        latest, previous = cleaned[0], cleaned[1]
        return round(ranked_hot_overlap_score(latest, previous), 4)

    def _load_limit_down_count_cached(self, latest_trade_date: str | None) -> int | None:
        cache_key = latest_trade_date or "intraday"
        cached = self._get_limit_down_cache(cache_key)
        if cached is not None:
            return cached
        if not latest_trade_date:
            return None
        try:
            frame = None
            if self._market_provider_router_enabled():
                routed = self.provider_router.fetch_limit_down_pool(latest_trade_date)
                if routed.usable:
                    frame = routed.data
                else:
                    return None
            else:
                return None
        except Exception:
            return None
        count = int(len(frame.index)) if frame is not None else 0
        self._set_limit_down_cache(cache_key, count)
        return count

    def _get_market_regime_cache(self, key: str) -> MarketRegimeSnapshot | None:
        return self._get_cached_snapshot(
            self._market_regime_cache,
            self._market_regime_cache_ttl,
            key,
        )

    def _peek_market_regime_snapshot(self, key: str) -> MarketRegimeSnapshot | None:
        with self._cache_lock:
            cached = self._market_regime_cache.get(key)
            if cached is None:
                return None
            return cached[1]

    def _get_market_breadth_cache(self, key: str) -> MarketBreadthSnapshot | None:
        return self._get_cached_snapshot(
            self._market_breadth_cache,
            self._market_breadth_cache_ttl,
            key,
        )

    def _set_market_breadth_cache(self, key: str, snapshot: MarketBreadthSnapshot) -> None:
        self._set_cached_snapshot(
            self._market_breadth_cache,
            self._market_breadth_cache_ttl,
            key,
            snapshot,
        )

    def _set_market_regime_cache(self, key: str, snapshot: MarketRegimeSnapshot) -> None:
        self._set_cached_snapshot(
            self._market_regime_cache,
            self._market_regime_cache_ttl,
            key,
            snapshot,
        )

    def _persist_market_regime_snapshot(self, key: str, snapshot: MarketRegimeSnapshot) -> None:
        try:
            payload = json.dumps(asdict(snapshot), ensure_ascii=False)
            with SessionLocal() as db:
                row = db.execute(
                    select(MarketRegimeSnapshotCache).where(MarketRegimeSnapshotCache.cache_key == key)
                ).scalar_one_or_none()
                if row is None:
                    row = MarketRegimeSnapshotCache(cache_key=key)
                    db.add(row)
                row.trade_date = key
                row.state = snapshot.state
                row.breadth_ready = bool(snapshot.breadth_ready)
                row.emotion_ready = bool(snapshot.emotion_ready)
                row.hot_industry_source = snapshot.hot_industry_source
                row.data_quality = regime_data_quality(snapshot)
                row.payload_json = payload
                db.commit()
        except Exception:
            logger.exception("failed to persist market regime snapshot")

    def _load_persisted_market_regime_snapshot(
        self,
        key: str,
        hot_industries: list[str] | None,
    ) -> MarketRegimeSnapshot | None:
        try:
            with SessionLocal() as db:
                row = db.execute(
                    select(MarketRegimeSnapshotCache).where(MarketRegimeSnapshotCache.cache_key == key)
                ).scalar_one_or_none()
                if row is not None and not (row.breadth_ready or row.emotion_ready):
                    row = None
                if row is None:
                    row = db.execute(
                        select(MarketRegimeSnapshotCache)
                        .where(MarketRegimeSnapshotCache.breadth_ready.is_(True))
                        .order_by(desc(MarketRegimeSnapshotCache.trade_date), desc(MarketRegimeSnapshotCache.updated_at))
                        .limit(1)
                    ).scalar_one_or_none()
                if row is None:
                    return None
                snapshot = snapshot_from_payload(row.payload_json)
        except Exception:
            logger.exception("failed to load persisted market regime snapshot")
            return None
        if snapshot is None:
            return None
        if hot_industries and snapshot.hot_industries and hot_industries != snapshot.hot_industries:
            return None
        return replace(
            snapshot,
            snapshot_source="cached",
            snapshot_source_text=f"使用 {row.trade_date} 最近完整市场快照，后台正在刷新实时情绪",
        )

    def _get_limit_down_cache(self, key: str) -> int | None:
        return self._get_cached_snapshot(self._limit_down_cache, self._limit_down_cache_ttl, key)

    def _set_limit_down_cache(self, key: str, value: int) -> None:
        self._set_cached_snapshot(self._limit_down_cache, self._limit_down_cache_ttl, key, value)

    def _get_cached_snapshot(self, store: dict[str, tuple[float, object]], ttl: float, key: str):
        with self._cache_lock:
            cached = store.get(key)
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= time.monotonic():
                store.pop(key, None)
                return None
            return payload

    def _set_cached_snapshot(
        self,
        store: dict[str, tuple[float, object]],
        ttl: float,
        key: str,
        payload: object,
    ) -> None:
        with self._cache_lock:
            store[key] = (time.monotonic() + ttl, payload)

__all__ = [
    "MarketBreadthSnapshot",
    "MarketRegimeMixin",
    "MarketRegimeSnapshot",
    "STATE_CONFIG",
    "classify_market_regime",
    "market_regime_text",
    "normalize_board_frame",
]
