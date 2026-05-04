from __future__ import annotations

from typing import Protocol

from app.services.low_buy.intraday_confirmation import (
    build_intraday_confirmation,
    calculate_intraday_vwap,
    intraday_confirmation_hint,
    intraday_confirmation_passes,
)
from app.services.low_buy.signal_resolution import end_of_day_soft_confirmation, intraday_soft_confirmation
from app.services.low_buy.shared import Any, LowBuyCandidateOut, pd


class SignalRefreshBuilder(Protocol):
    def _entry_position(self, candidate: LowBuyCandidateOut, latest_price: float) -> str: ...

    def _intraday_daily_signal_veto(
        self,
        *,
        candidate: LowBuyCandidateOut,
        quote: Any | None,
        intraday_bars: list[Any] | None,
        vwap_value: float,
    ) -> str: ...

    def _is_intraday_stop_confirmed(
        self,
        candidate: LowBuyCandidateOut,
        quote: Any | None = None,
        *,
        intraday_bars: list[Any] | None = None,
        vwap_value: float = 0.0,
        require_intraday_structure: bool = False,
    ) -> bool: ...

    def _is_end_of_day_stop_confirmed(self, candidate: LowBuyCandidateOut, latest_bar: pd.Series) -> bool: ...

    def _distance_to_entry_zone_pct(self, candidate: LowBuyCandidateOut, latest_price: float) -> float: ...

    def _signal_update(
        self,
        candidate: LowBuyCandidateOut,
        state: str,
        text: str,
        hint: str,
        entry_distance: float,
        confirmed_trade_date: str | None = None,
    ) -> LowBuyCandidateOut: ...

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
    ) -> LowBuyCandidateOut: ...


def refresh_buy_signal(
    *,
    builder: SignalRefreshBuilder,
    candidate: LowBuyCandidateOut,
    quote: Any | None = None,
    intraday_bars: list[Any] | None = None,
    require_intraday_structure: bool = False,
) -> LowBuyCandidateOut:
    refreshed_candidate = candidate
    latest_price = candidate.latest_price
    if quote is not None:
        latest_price = float(getattr(quote, "last_price", candidate.latest_price) or candidate.latest_price)
        refreshed_candidate = candidate.model_copy(
            update={
                "latest_price": latest_price,
                "change_pct": float(getattr(quote, "change_pct", candidate.change_pct) or candidate.change_pct),
                "quote_timestamp": str(getattr(quote, "timestamp", candidate.quote_timestamp) or candidate.quote_timestamp),
            }
        )
    entry_position = builder._entry_position(refreshed_candidate, latest_price)
    vwap_value = calculate_intraday_vwap(intraday_bars)
    intraday_confirmation = build_intraday_confirmation(intraday_bars)
    intraday_veto_hint = builder._intraday_daily_signal_veto(
        candidate=refreshed_candidate,
        quote=quote,
        intraday_bars=intraday_bars,
        vwap_value=vwap_value,
    )
    stop_confirmed = builder._is_intraday_stop_confirmed(
        refreshed_candidate,
        quote,
        intraday_bars=intraday_bars,
        vwap_value=vwap_value,
        require_intraday_structure=require_intraday_structure,
    )
    soft_confirmed = intraday_soft_confirmation(
        refreshed_candidate,
        quote,
        intraday_bars=intraday_bars,
        vwap_value=vwap_value,
        require_intraday_structure=require_intraday_structure,
    )
    entry_distance = builder._distance_to_entry_zone_pct(refreshed_candidate, latest_price)
    if quote is not None and bool(getattr(quote, "is_stale", False)):
        return builder._signal_update(
            candidate=refreshed_candidate,
            state="watch",
            text="继续观察",
            hint="实时行情时间已过期，只更新价格参考，不触发买入信号。",
            entry_distance=entry_distance,
        )
    return builder._resolve_signal_state(
        candidate=refreshed_candidate,
        entry_position=entry_position,
        entry_distance=entry_distance,
        hard_confirmed=stop_confirmed,
        soft_confirmed=soft_confirmed,
        intraday_confirmed=intraday_confirmation_passes(refreshed_candidate.strategy_key, intraday_confirmation),
        intraday_hint=intraday_confirmation_hint(refreshed_candidate.strategy_key, intraday_confirmation),
        historical=False,
        intraday_veto_hint=intraday_veto_hint,
    )


def refresh_historical_buy_signal(
    *,
    builder: SignalRefreshBuilder,
    candidate: LowBuyCandidateOut,
    latest_bar: pd.Series,
) -> LowBuyCandidateOut:
    close_price = float(latest_bar["close"])
    refreshed_candidate = candidate.model_copy(
        update={
            "latest_price": close_price,
            "change_pct": float(latest_bar["pct_chg"]),
            "quote_timestamp": str(latest_bar["date"]),
        }
    )
    entry_position = builder._entry_position(refreshed_candidate, close_price)
    stop_confirmed = builder._is_end_of_day_stop_confirmed(refreshed_candidate, latest_bar)
    soft_confirmed = end_of_day_soft_confirmation(refreshed_candidate, latest_bar)
    entry_distance = builder._distance_to_entry_zone_pct(refreshed_candidate, close_price)
    return builder._resolve_signal_state(
        candidate=refreshed_candidate,
        entry_position=entry_position,
        entry_distance=entry_distance,
        hard_confirmed=stop_confirmed,
        soft_confirmed=soft_confirmed,
        intraday_confirmed=True,
        intraday_hint="",
        historical=True,
        confirmed_trade_date=str(latest_bar["date"]),
    )
