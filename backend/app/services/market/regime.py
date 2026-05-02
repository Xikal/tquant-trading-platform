from __future__ import annotations

from dataclasses import replace
import threading
import time

import pandas as pd

from app.services.market.shared import ak
from app.services.market.regime_scoring import (
    classify_market_regime,
    clone_snapshot_with_state,
    market_breadth_sequence_key,
    market_regime_text,
    normalize_board_frame,
)
from app.services.market.regime_types import (
    STATE_CONFIG,
    STYLE_PROXY_GROUPS,
    MarketBreadthSnapshot,
    MarketRegimeSnapshot,
)


class MarketRegimeMixin:
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
        self._set_market_regime_cache(trade_date, snapshot)
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
        return classify_market_regime(
            None,
            limit_down_count=None,
            hot_industries=hot_industries,
            hot_industry_source=hot_industry_source or "cached_fallback",
            hot_industry_source_text=hot_industry_source_text or "热点来源：后台补齐中",
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

    @staticmethod
    def _resolve_hot_industries(
        board_frame: pd.DataFrame | None,
        hot_industries: list[str] | None,
    ) -> list[str]:
        if hot_industries:
            return hot_industries
        if board_frame is None:
            return []
        return board_frame.head(3)["industry"].tolist()

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
        transition_risk = _transition_risk(snapshot, previous_snapshot)
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
        if not self.ak_available:
            return None
        try:
            frame = self._get_industry_board_frame()
        except Exception:
            return None
        return normalize_board_frame(frame)

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
                snapshot_map = self._load_spot_snapshot_map("stock")
                snapshot = self._build_market_breadth_snapshot(
                    snapshot_map=snapshot_map,
                    recent_hot_sequences=recent_hot_sequences,
                    breadth_ready=bool(snapshot_map),
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
        cleaned = _clean_hot_sequences(sequences)
        if len(cleaned) < 2:
            return 0.0
        turnovers: list[float] = []
        for left, right in zip(cleaned, cleaned[1:]):
            turnovers.append(1.0 - _ranked_hot_overlap_score(left, right))
        if not turnovers:
            return 0.0
        return round(sum(turnovers) / len(turnovers), 4)

    @staticmethod
    def _compute_hot_overlap_ratio(sequences: list[list[str]]) -> float:
        cleaned = _clean_hot_sequences(sequences)
        if len(cleaned) < 2:
            return 0.0
        latest, previous = cleaned[0], cleaned[1]
        return round(_ranked_hot_overlap_score(latest, previous), 4)

    def _load_limit_down_count_cached(self, latest_trade_date: str | None) -> int | None:
        cache_key = latest_trade_date or "intraday"
        cached = self._get_limit_down_cache(cache_key)
        if cached is not None:
            return cached
        if not self.ak_available or not latest_trade_date:
            return None
        try:
            frame = self._call_akshare(
                ak.stock_zt_pool_dtgc_em,
                date=latest_trade_date.replace("-", ""),
                purpose="market_breadth",
            )
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


def _transition_risk(snapshot: MarketRegimeSnapshot, previous_snapshot: MarketRegimeSnapshot) -> float:
    state_changed = snapshot.state != previous_snapshot.state
    score_gap = abs(snapshot.regime_score - previous_snapshot.regime_score)
    strength_gap = abs(snapshot.state_strength - previous_snapshot.state_strength)
    raw = (0.40 if state_changed else 0.08) + min(score_gap / 40.0, 0.35) + min(strength_gap, 0.25)
    if snapshot.hot_turnover >= 0.65:
        raw += 0.12
    if snapshot.distribution_pressure >= 55.0:
        raw += 0.10
    return round(max(0.0, min(1.0, raw)), 4)


def _clean_hot_sequences(sequences: list[list[str]]) -> list[list[str]]:
    cleaned: list[list[str]] = []
    for sequence in sequences:
        row = [item.strip() for item in sequence if item and item.strip()]
        if row:
            cleaned.append(row[:3])
    return cleaned


def _ranked_hot_overlap_score(latest: list[str], previous: list[str]) -> float:
    if not latest or not previous:
        return 0.0
    latest_top = latest[:3]
    previous_top = previous[:3]
    latest_set = set(latest_top)
    previous_set = set(previous_top)
    common = latest_set & previous_set
    set_score = len(common) / max(len(latest_set | previous_set), 1)
    top1_score = 1.0 if latest_top[0] == previous_top[0] else 0.0
    rank_score = _rank_continuity_score(latest_top, previous_top, common)
    return round(top1_score * 0.36 + set_score * 0.44 + rank_score * 0.20, 4)


def _rank_continuity_score(latest: list[str], previous: list[str], common: set[str]) -> float:
    if not common:
        return 0.0
    latest_rank = {industry: index for index, industry in enumerate(latest)}
    previous_rank = {industry: index for index, industry in enumerate(previous)}
    scores = [
        max(0.0, 1.0 - abs(latest_rank[industry] - previous_rank[industry]) / 3.0)
        for industry in common
    ]
    return sum(scores) / len(scores)


__all__ = [
    "MarketBreadthSnapshot",
    "MarketRegimeMixin",
    "MarketRegimeSnapshot",
    "STATE_CONFIG",
    "classify_market_regime",
    "market_regime_text",
    "normalize_board_frame",
]
