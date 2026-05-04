from __future__ import annotations

from app.services.low_buy.signal_resolution import build_signal_update
from app.services.low_buy.signal_confirmation import (
    intraday_daily_signal_veto,
    is_end_of_day_stop_confirmed,
    is_intraday_stop_confirmed,
)
from app.services.low_buy.signal_entry import (
    below_zone_hard_buy_allowed,
    entry_position,
    is_strict_in_zone_strategy,
    near_above_soft_buy_allowed,
    near_entry_positions,
    should_avoid_on_entry_position,
)
from app.services.low_buy.signal_refresh import refresh_buy_signal, refresh_historical_buy_signal
from app.services.low_buy.signal_rules import (
    can_hard_buy_now,
    can_show_research_near_entry,
    can_soft_buy_now,
    market_block_can_keep_research,
    research_near_entry_hint,
    signal_block_hint,
    weak_market_thematic_block_reason,
)
from app.services.low_buy.signal_live import apply_live_quotes, load_live_quote_intraday_bars
from app.services.low_buy.signal_market import market_buy_restricted, restricted_market_track_allowed
from app.services.low_buy.signal_quality import (
    base_quality_clear,
    has_distribution_hard_block,
    has_distribution_soft_block,
    strategy_hard_buy_quality_gate,
    strategy_soft_buy_quality_gate,
)
from app.services.low_buy.signal_state import resolve_signal_state
from app.services.low_buy.signal_thresholds import hard_buy_min_score, soft_buy_min_score
from app.services.low_buy.shared import Any, LowBuyCandidateOut, LowBuyQuoteRefreshOut, pd
from app.services.low_buy.strategy_governance import cached_auto_governance_override


class LowBuySignalMixin:
    def _refresh_buy_signal(
        self,
        candidate: LowBuyCandidateOut,
        quote: Any | None = None,
        intraday_bars: list[Any] | None = None,
        require_intraday_structure: bool = False,
    ) -> LowBuyCandidateOut:
        return refresh_buy_signal(
            builder=self,
            candidate=candidate,
            quote=quote,
            intraday_bars=intraday_bars,
            require_intraday_structure=require_intraday_structure,
        )

    def _refresh_historical_buy_signal(self, candidate: LowBuyCandidateOut, latest_bar: pd.Series) -> LowBuyCandidateOut:
        return refresh_historical_buy_signal(builder=self, candidate=candidate, latest_bar=latest_bar)

    def _resolve_signal_state(
        self,
        candidate: LowBuyCandidateOut,
        entry_position: str,
        entry_distance: float,
        hard_confirmed: bool,
        soft_confirmed: bool,
        historical: bool,
        intraday_confirmed: bool = True,
        intraday_hint: str = "",
        intraday_veto_hint: str = "",
        confirmed_trade_date: str | None = None,
    ) -> LowBuyCandidateOut:
        return resolve_signal_state(
            resolver=self,
            candidate=candidate,
            entry_position=entry_position,
            entry_distance=entry_distance,
            hard_confirmed=hard_confirmed,
            soft_confirmed=soft_confirmed,
            historical=historical,
            intraday_confirmed=intraday_confirmed,
            intraday_hint=intraday_hint,
            intraday_veto_hint=intraday_veto_hint,
            confirmed_trade_date=confirmed_trade_date,
        )

    def _signal_update(
        self,
        candidate: LowBuyCandidateOut,
        state: str,
        text: str,
        hint: str,
        entry_distance: float,
        confirmed_trade_date: str | None = None,
    ) -> LowBuyCandidateOut:
        updated = build_signal_update(
            candidate=candidate,
            state=state,
            text=text,
            hint=hint,
            entry_distance=entry_distance,
            confirmed_trade_date=confirmed_trade_date,
            position_resolver=self._position_advice_for_signal,
        )
        if hasattr(self, "_execution_quality"):
            score, quality_text = self._execution_quality(updated)
            return updated.model_copy(
                update={
                    "execution_quality_score": score,
                    "execution_quality_text": quality_text,
                }
            )
        return updated

    def _can_hard_buy_now(
        self,
        candidate: LowBuyCandidateOut,
        entry_position: str,
        hard_confirmed: bool,
    ) -> bool:
        return can_hard_buy_now(
            candidate=candidate,
            entry_position=entry_position,
            hard_confirmed=hard_confirmed,
            auto_governance_blocks_buy=self._auto_governance_blocks_buy,
            weak_market_thematic_block_reason=self._weak_market_thematic_block_reason,
            has_distribution_hard_block=self._has_distribution_hard_block,
            strategy_hard_buy_quality_gate=self._strategy_hard_buy_quality_gate,
            hard_buy_min_score=self._hard_buy_min_score,
            is_strict_in_zone_strategy=self._is_strict_in_zone_strategy,
            below_zone_hard_buy_allowed=self._below_zone_hard_buy_allowed,
        )

    @staticmethod
    def _strategy_hard_buy_quality_gate(candidate: LowBuyCandidateOut) -> bool:
        return strategy_hard_buy_quality_gate(candidate)

    @staticmethod
    def _signal_block_hint(candidate: LowBuyCandidateOut) -> str:
        return signal_block_hint(
            candidate=candidate,
            auto_override=cached_auto_governance_override(candidate.strategy_key),
            weak_market_thematic_block_reason=LowBuySignalMixin._weak_market_thematic_block_reason,
        )

    @staticmethod
    def _market_block_can_keep_research(candidate: LowBuyCandidateOut) -> bool:
        return market_block_can_keep_research(candidate)

    @staticmethod
    def _market_buy_restricted(candidate: LowBuyCandidateOut) -> bool:
        return market_buy_restricted(candidate)

    @staticmethod
    def _restricted_market_track_allowed(
        candidate: LowBuyCandidateOut,
        entry_position: str,
        entry_distance: float,
    ) -> bool:
        return restricted_market_track_allowed(candidate, entry_position, entry_distance)

    def _can_soft_buy_now(
        self,
        candidate: LowBuyCandidateOut,
        entry_position: str,
        soft_confirmed: bool,
    ) -> bool:
        return can_soft_buy_now(
            candidate=candidate,
            entry_position=entry_position,
            soft_confirmed=soft_confirmed,
            auto_governance_blocks_buy=self._auto_governance_blocks_buy,
            weak_market_thematic_block_reason=self._weak_market_thematic_block_reason,
            has_distribution_soft_block=self._has_distribution_soft_block,
            strategy_soft_buy_quality_gate=self._strategy_soft_buy_quality_gate,
            soft_buy_min_score=self._soft_buy_min_score,
            is_strict_in_zone_strategy=self._is_strict_in_zone_strategy,
            near_above_soft_buy_allowed=self._near_above_soft_buy_allowed,
        )

    @staticmethod
    def _strategy_soft_buy_quality_gate(candidate: LowBuyCandidateOut) -> bool:
        return strategy_soft_buy_quality_gate(candidate)

    @staticmethod
    def _auto_governance_blocks_buy(candidate: LowBuyCandidateOut) -> bool:
        auto_override = cached_auto_governance_override(candidate.strategy_key)
        if not auto_override:
            return False
        return str(auto_override.get("status") or "") in {"paused", "watch"}

    @staticmethod
    def _base_quality_clear(candidate: LowBuyCandidateOut, distribution_limit: float) -> bool:
        return base_quality_clear(candidate, distribution_limit)

    @staticmethod
    def _is_strict_in_zone_strategy(strategy_key: str) -> bool:
        return is_strict_in_zone_strategy(strategy_key)

    @staticmethod
    def _can_show_research_near_entry(candidate: LowBuyCandidateOut, entry_position: str) -> bool:
        return can_show_research_near_entry(candidate, entry_position)

    @staticmethod
    def _research_near_entry_hint(candidate: LowBuyCandidateOut, entry_position: str, historical: bool) -> str:
        return research_near_entry_hint(candidate, entry_position)

    @staticmethod
    def _below_zone_hard_buy_allowed(candidate: LowBuyCandidateOut) -> bool:
        return below_zone_hard_buy_allowed(candidate)

    @staticmethod
    def _near_above_soft_buy_allowed(candidate: LowBuyCandidateOut) -> bool:
        return near_above_soft_buy_allowed(candidate)

    @staticmethod
    def _weak_market_thematic_block_reason(candidate: LowBuyCandidateOut) -> str:
        return weak_market_thematic_block_reason(candidate)

    def _near_entry_positions(self, strategy_key: str) -> set[str]:
        return near_entry_positions(strategy_key)

    def _should_avoid_on_entry_position(self, strategy_key: str, entry_position: str) -> bool:
        return should_avoid_on_entry_position(strategy_key, entry_position)

    @staticmethod
    def _has_distribution_hard_block(candidate: LowBuyCandidateOut) -> bool:
        return has_distribution_hard_block(candidate)

    @staticmethod
    def _has_distribution_soft_block(candidate: LowBuyCandidateOut) -> bool:
        return has_distribution_soft_block(candidate)

    @staticmethod
    def _hard_buy_min_score(candidate: LowBuyCandidateOut) -> float:
        return hard_buy_min_score(candidate)

    @staticmethod
    def _soft_buy_min_score(strategy: str, entry_position: str, threshold_shift: float = 0.0) -> float:
        return soft_buy_min_score(strategy, entry_position, threshold_shift)

    def _is_intraday_stop_confirmed(
        self,
        candidate: LowBuyCandidateOut,
        quote: Any | None = None,
        *,
        intraday_bars: list[Any] | None = None,
        vwap_value: float = 0.0,
        require_intraday_structure: bool = False,
    ) -> bool:
        return is_intraday_stop_confirmed(
            candidate=candidate,
            quote=quote,
            intraday_bars=intraday_bars,
            vwap_value=vwap_value,
            require_intraday_structure=require_intraday_structure,
        )

    def _is_end_of_day_stop_confirmed(self, candidate: LowBuyCandidateOut, latest_bar: pd.Series) -> bool:
        return is_end_of_day_stop_confirmed(candidate, latest_bar)

    @staticmethod
    def _intraday_daily_signal_veto(
        *,
        candidate: LowBuyCandidateOut,
        quote: Any | None,
        intraday_bars: list[Any] | None,
        vwap_value: float,
    ) -> str:
        return intraday_daily_signal_veto(
            candidate=candidate,
            quote=quote,
            intraday_bars=intraday_bars,
            vwap_value=vwap_value,
        )

    def _entry_position(self, candidate: LowBuyCandidateOut, latest_price: float) -> str:
        tolerance_pct = self._get_entry_tolerance_pct(candidate.strategy_key)
        return entry_position(candidate, latest_price, tolerance_pct)

    def _apply_live_quotes(self, candidates: list[LowBuyCandidateOut], quote_map: dict[str, Any] | None = None) -> list[LowBuyCandidateOut]:
        return apply_live_quotes(builder=self, candidates=candidates, quote_map=quote_map)

    def _load_live_quote_intraday_bars(
        self,
        candidates: list[LowBuyCandidateOut],
        quote_map: dict[str, Any],
        *,
        max_symbols: int = 24,
    ) -> dict[str, list[Any]]:
        return load_live_quote_intraday_bars(
            builder=self,
            candidates=candidates,
            quote_map=quote_map,
            max_symbols=max_symbols,
        )
