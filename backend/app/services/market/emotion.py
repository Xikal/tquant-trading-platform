from __future__ import annotations

from dataclasses import dataclass
from app.core.timezone import beijing_today
from app.services.market.emotion_temperature import classify_emotion_temperature


@dataclass(frozen=True)
class MarketEmotionSnapshot:
    emotion_ready: bool
    limit_up_count: int
    previous_limit_up_count: int
    board_height: int
    previous_board_height: int
    promotion_ratio: float
    broken_board_ratio: float
    promotion_break_gap: float
    promotion_break_pressure: float
    high_flyer_retreat_ratio: float
    high_flyer_gap_speed: float
    emotion_distribution_pressure: float
    emotion_temperature: str = "unknown"
    emotion_temperature_text: str = "情绪温度数据不足"
    emotion_temperature_score: float = 0.0


class MarketEmotionMixin:
    def _resolve_regime_trade_date(self, latest_trade_date: str | None) -> str | None:
        if latest_trade_date:
            return latest_trade_date
        trade_dates = self._load_trade_dates()
        if not trade_dates:
            return None
        today = beijing_today().isoformat()
        eligible = [item for item in trade_dates if item <= today]
        return eligible[-1] if eligible else None

    def _resolve_previous_trade_date(self, latest_trade_date: str | None) -> str | None:
        if not latest_trade_date:
            return None
        trade_dates = self._load_trade_dates()
        if latest_trade_date not in trade_dates:
            return None
        index = trade_dates.index(latest_trade_date)
        if index <= 0:
            return None
        return trade_dates[index - 1]

    def _load_market_emotion_snapshot(
        self,
        latest_trade_date: str | None,
    ) -> MarketEmotionSnapshot:
        effective_trade_date = self._resolve_regime_trade_date(latest_trade_date)
        if not effective_trade_date:
            return self._empty_market_emotion_snapshot()
        cached = self._get_market_emotion_cache(effective_trade_date)
        if cached is not None:
            return cached

        previous_trade_date = self._resolve_previous_trade_date(effective_trade_date)
        if self._market_provider_router_enabled():
            routed = self.provider_router.fetch_market_emotion_pools(
                effective_trade_date,
                previous_trade_date,
            )
            if routed.usable and isinstance(routed.data, dict):
                snapshot = self._build_market_emotion_snapshot(
                    current_pool=routed.data.get("current"),
                    broken_pool=routed.data.get("broken"),
                    previous_board_pool=routed.data.get("previous_board"),
                    previous_limit_up_pool=routed.data.get("previous"),
                )
                self._set_market_emotion_cache(effective_trade_date, snapshot)
                return snapshot

        snapshot = self._empty_market_emotion_snapshot()
        self._set_market_emotion_cache(effective_trade_date, snapshot)
        return snapshot

    @staticmethod
    def _build_market_emotion_snapshot(
        *,
        current_pool,
        broken_pool,
        previous_board_pool,
        previous_limit_up_pool,
    ) -> MarketEmotionSnapshot:
        if current_pool is None or getattr(current_pool, "empty", True):
            return MarketEmotionSnapshot(
                emotion_ready=False,
                limit_up_count=0,
                previous_limit_up_count=0,
                board_height=0,
                previous_board_height=0,
                promotion_ratio=0.0,
                broken_board_ratio=0.0,
                promotion_break_gap=0.0,
                promotion_break_pressure=0.0,
                high_flyer_retreat_ratio=0.0,
                high_flyer_gap_speed=0.0,
                emotion_distribution_pressure=0.0,
            )

        current_limit_up_count = int(len(current_pool.index))
        current_board_height = int(current_pool["连板数"].fillna(1).astype(float).max()) if "连板数" in current_pool else 1
        current_two_plus = int((current_pool["连板数"].fillna(1).astype(float) >= 2).sum()) if "连板数" in current_pool else 0
        current_three_plus = int((current_pool["连板数"].fillna(1).astype(float) >= 3).sum()) if "连板数" in current_pool else 0
        previous_limit_up_count = int(len(previous_limit_up_pool.index)) if previous_limit_up_pool is not None and not previous_limit_up_pool.empty else 0
        previous_board_height = (
            int(previous_limit_up_pool["连板数"].fillna(1).astype(float).max())
            if previous_limit_up_pool is not None and not previous_limit_up_pool.empty and "连板数" in previous_limit_up_pool
            else 0
        )
        previous_three_plus = (
            int((previous_limit_up_pool["连板数"].fillna(1).astype(float) >= 3).sum())
            if previous_limit_up_pool is not None and not previous_limit_up_pool.empty and "连板数" in previous_limit_up_pool
            else 0
        )
        broken_count = int(len(broken_pool.index)) if broken_pool is not None and not broken_pool.empty else 0

        promotion_ratio = current_two_plus / max(previous_limit_up_count, 1)
        broken_board_ratio = broken_count / max(current_limit_up_count + broken_count, 1)
        promotion_failure_pressure = broken_count / max(previous_limit_up_count, 1)
        broken_to_promotion_pressure = broken_count / max(current_two_plus + broken_count, 1)
        promotion_break_pressure = _promotion_break_pressure(
            broken_board_ratio=broken_board_ratio,
            promotion_failure_pressure=promotion_failure_pressure,
            broken_to_promotion_pressure=broken_to_promotion_pressure,
        )
        promotion_break_gap = promotion_ratio - max(broken_board_ratio, broken_to_promotion_pressure * 0.72)

        high_flyer_retreat_ratio = 0.0
        if previous_board_pool is not None and not previous_board_pool.empty:
            board_series = previous_board_pool.get("昨日连板数")
            change_series = previous_board_pool.get("涨跌幅")
            if board_series is not None and change_series is not None:
                yesterday_boards = board_series.fillna(0).astype(float)
                today_changes = change_series.fillna(0).astype(float)
                mask = yesterday_boards >= 2
                count = int(mask.sum())
                if count > 0:
                    high_flyer_retreat_ratio = float((today_changes[mask] < 0).mean())
        board_height_drop = _ratio_drop(previous_board_height, current_board_height)
        high_board_layer_drop = _ratio_drop(previous_three_plus, current_three_plus)
        limit_up_count_drop = _ratio_drop(previous_limit_up_count, current_limit_up_count)
        base_gap_speed = (board_height_drop + high_board_layer_drop + high_flyer_retreat_ratio) / 3.0
        advanced_gap_speed = (
            board_height_drop * 0.26
            + high_board_layer_drop * 0.28
            + limit_up_count_drop * 0.12
            + high_flyer_retreat_ratio * 0.22
            + promotion_break_pressure * 0.12
        )
        high_flyer_gap_speed = max(base_gap_speed, advanced_gap_speed)
        emotion_distribution_pressure = (
            _clamp01(broken_board_ratio) * 0.30
            + _clamp01(high_flyer_retreat_ratio) * 0.25
            + _clamp01(high_flyer_gap_speed) * 0.25
            + _clamp01((0.0 - promotion_break_gap) / 0.3) * 0.20
        )
        temperature = classify_emotion_temperature(
            limit_up_count=current_limit_up_count,
            board_height=current_board_height,
            promotion_ratio=_clamp01(promotion_ratio),
            broken_board_ratio=_clamp01(broken_board_ratio),
            distribution_pressure=_clamp01(emotion_distribution_pressure),
        )

        return MarketEmotionSnapshot(
            emotion_ready=True,
            limit_up_count=current_limit_up_count,
            previous_limit_up_count=previous_limit_up_count,
            board_height=current_board_height,
            previous_board_height=previous_board_height,
            promotion_ratio=round(promotion_ratio, 4),
            broken_board_ratio=round(broken_board_ratio, 4),
            promotion_break_gap=round(promotion_break_gap, 4),
            promotion_break_pressure=round(promotion_break_pressure, 4),
            high_flyer_retreat_ratio=round(high_flyer_retreat_ratio, 4),
            high_flyer_gap_speed=round(high_flyer_gap_speed, 4),
            emotion_distribution_pressure=round(min(max(emotion_distribution_pressure, 0.0), 1.0), 4),
            emotion_temperature=temperature.key,
            emotion_temperature_text=temperature.text,
            emotion_temperature_score=temperature.score,
        )

    def _load_trade_dates(self) -> list[str]:
        cached = self._get_trade_date_cache("calendar")
        if cached is not None:
            return cached
        if self._market_provider_router_enabled():
            routed = self.provider_router.fetch_trade_dates()
            if routed.usable and routed.data:
                values = list(routed.data)
                self._set_trade_date_cache("calendar", values)
                return values
        return []

    def _get_market_emotion_cache(self, key: str) -> MarketEmotionSnapshot | None:
        return self._get_cached_snapshot(
            self._market_emotion_cache,
            self._market_emotion_cache_ttl,
            key,
        )

    def _set_market_emotion_cache(self, key: str, snapshot: MarketEmotionSnapshot) -> None:
        self._set_cached_snapshot(
            self._market_emotion_cache,
            self._market_emotion_cache_ttl,
            key,
            snapshot,
        )

    def _get_trade_date_cache(self, key: str) -> list[str] | None:
        return self._get_cached_snapshot(
            self._trade_dates_cache,
            self._trade_dates_cache_ttl,
            key,
        )

    def _set_trade_date_cache(self, key: str, values: list[str]) -> None:
        self._set_cached_snapshot(
            self._trade_dates_cache,
            self._trade_dates_cache_ttl,
            key,
            values,
        )

    @staticmethod
    def _empty_market_emotion_snapshot() -> MarketEmotionSnapshot:
        return MarketEmotionSnapshot(
            emotion_ready=False,
            limit_up_count=0,
            previous_limit_up_count=0,
            board_height=0,
            previous_board_height=0,
            promotion_ratio=0.0,
            broken_board_ratio=0.0,
            promotion_break_gap=0.0,
            promotion_break_pressure=0.0,
            high_flyer_retreat_ratio=0.0,
            high_flyer_gap_speed=0.0,
            emotion_distribution_pressure=0.0,
        )


def _clamp01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _ratio_drop(previous_value: int, current_value: int) -> float:
    if previous_value <= 0:
        return 0.0
    return _clamp01((previous_value - current_value) / previous_value)


def _promotion_break_pressure(
    *,
    broken_board_ratio: float,
    promotion_failure_pressure: float,
    broken_to_promotion_pressure: float,
) -> float:
    return _clamp01(
        broken_board_ratio * 0.45
        + promotion_failure_pressure * 0.20
        + broken_to_promotion_pressure * 0.35
    )
