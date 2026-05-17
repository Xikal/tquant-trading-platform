from __future__ import annotations

from typing import Protocol

from app.services.low_buy.intraday_confirmation import strategy_requires_intraday_confirmation
from app.services.low_buy.signal_helpers import (
    below_stop_hint,
    buy_now_hint,
    mature_watch_hint,
    near_entry_hint,
    observe_confirmed_hint,
    restricted_market_avoid_hint,
    strict_strategy_avoid_hint,
    structure_pending_hint,
)
from app.services.low_buy.strategy_policy import is_observation_layer_strategy
from app.services.low_buy.shared import LowBuyCandidateOut


class SignalStateResolver(Protocol):
    def _signal_block_hint(self, candidate: LowBuyCandidateOut) -> str: ...

    def _signal_update(
        self,
        candidate: LowBuyCandidateOut,
        state: str,
        text: str,
        hint: str,
        entry_distance: float,
        confirmed_trade_date: str | None = None,
    ) -> LowBuyCandidateOut: ...

    def _market_buy_restricted(self, candidate: LowBuyCandidateOut) -> bool: ...

    def _can_hard_buy_now(
        self,
        candidate: LowBuyCandidateOut,
        entry_position: str,
        hard_confirmed: bool,
    ) -> bool: ...

    def _can_soft_buy_now(
        self,
        candidate: LowBuyCandidateOut,
        entry_position: str,
        soft_confirmed: bool,
    ) -> bool: ...

    def _restricted_market_track_allowed(
        self,
        candidate: LowBuyCandidateOut,
        entry_position: str,
        entry_distance: float,
    ) -> bool: ...

    def _can_show_research_near_entry(self, candidate: LowBuyCandidateOut, entry_position: str) -> bool: ...

    def _research_near_entry_hint(
        self,
        candidate: LowBuyCandidateOut,
        entry_position: str,
        historical: bool,
    ) -> str: ...

    def _should_avoid_on_entry_position(self, strategy_key: str, entry_position: str) -> bool: ...

    def _near_entry_positions(self, strategy_key: str) -> set[str]: ...


def resolve_signal_state(
    *,
    resolver: SignalStateResolver,
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
    block_hint = resolver._signal_block_hint(candidate)
    if block_hint:
        return resolver._signal_update(
            candidate=candidate,
            state="avoid",
            text="今日放弃" if not historical else "暂不跟踪",
            hint=block_hint,
            entry_distance=entry_distance,
        )
    if intraday_veto_hint:
        return resolver._signal_update(
            candidate=candidate,
            state="avoid" if not historical else "watch",
            text="今日放弃" if not historical else "继续观察",
            hint=intraday_veto_hint,
            entry_distance=entry_distance,
        )
    buy_restricted = resolver._market_buy_restricted(candidate)
    if resolver._can_hard_buy_now(candidate, entry_position, hard_confirmed and intraday_confirmed):
        return resolver._signal_update(
            candidate=candidate,
            state="buy_now",
            text="确定买入",
            hint=buy_now_hint(entry_position, historical, soft=False),
            entry_distance=entry_distance,
            confirmed_trade_date=confirmed_trade_date if historical else None,
        )
    if resolver._can_soft_buy_now(candidate, entry_position, soft_confirmed and intraday_confirmed):
        return resolver._signal_update(
            candidate=candidate,
            state="soft_buy_now",
            text="确定买入",
            hint=buy_now_hint(entry_position, historical, soft=True),
            entry_distance=entry_distance,
            confirmed_trade_date=confirmed_trade_date if historical else None,
        )
    if candidate.execution_ready and entry_position in resolver._near_entry_positions(candidate.strategy_key):
        if buy_restricted and not resolver._restricted_market_track_allowed(candidate, entry_position, entry_distance):
            return resolver._signal_update(
                candidate=candidate,
                state="avoid",
                text="今日放弃" if not historical else "暂不跟踪",
                hint=restricted_market_avoid_hint(historical),
                entry_distance=entry_distance,
            )
        state = "observe_confirmed" if is_observation_layer_strategy(candidate.strategy_key) else "near_entry"
        text = "观察确认" if state == "observe_confirmed" else "接近买点"
        hint = (
            observe_confirmed_hint(entry_position, historical)
            if state == "observe_confirmed"
            else intraday_hint or near_entry_hint(entry_position, entry_distance, historical)
        )
        return resolver._signal_update(
            candidate=candidate,
            state=state,
            text=text,
            hint=hint,
            entry_distance=entry_distance,
        )
    if (
        is_observation_layer_strategy(candidate.strategy_key)
        and entry_position in resolver._near_entry_positions(candidate.strategy_key)
        and candidate.score >= 78
    ):
        if buy_restricted and not resolver._restricted_market_track_allowed(candidate, entry_position, entry_distance):
            return resolver._signal_update(
                candidate=candidate,
                state="avoid",
                text="今日放弃" if not historical else "暂不跟踪",
                hint=restricted_market_avoid_hint(historical),
                entry_distance=entry_distance,
            )
        return resolver._signal_update(
            candidate=candidate,
            state="near_entry",
            text="接近买点",
            hint=intraday_hint or near_entry_hint(entry_position, entry_distance, historical),
            entry_distance=entry_distance,
        )
    if resolver._can_show_research_near_entry(candidate, entry_position):
        return resolver._signal_update(
            candidate=candidate,
            state="near_entry",
            text="接近买点",
            hint=resolver._research_near_entry_hint(candidate, entry_position, historical),
            entry_distance=entry_distance,
        )
    if candidate.execution_ready and resolver._should_avoid_on_entry_position(candidate.strategy_key, entry_position):
        return resolver._signal_update(
            candidate=candidate,
            state="avoid",
            text="今日放弃" if not historical else "暂不跟踪",
            hint=strict_strategy_avoid_hint(entry_position, historical),
            entry_distance=entry_distance,
        )
    if candidate.execution_ready and entry_position == "below_stop":
        return resolver._signal_update(
            candidate=candidate,
            state="avoid",
            text="今日放弃" if not historical else "暂不跟踪",
            hint=below_stop_hint(historical),
            entry_distance=entry_distance,
        )
    if candidate.execution_ready:
        if not historical and strategy_requires_intraday_confirmation(candidate.strategy_key) and intraday_hint:
            return resolver._signal_update(
                candidate=candidate,
                state="watch",
                text="继续观察",
                hint=intraday_hint,
                entry_distance=entry_distance,
            )
        if buy_restricted and not resolver._restricted_market_track_allowed(candidate, entry_position, entry_distance):
            return resolver._signal_update(
                candidate=candidate,
                state="avoid",
                text="今日放弃" if not historical else "暂不跟踪",
                hint=restricted_market_avoid_hint(historical),
                entry_distance=entry_distance,
            )
        return resolver._signal_update(
            candidate=candidate,
            state="watch",
            text="继续观察",
            hint=mature_watch_hint(entry_distance, historical),
            entry_distance=entry_distance,
        )
    if resolver._should_avoid_on_entry_position(candidate.strategy_key, entry_position):
        return resolver._signal_update(
            candidate=candidate,
            state="avoid",
            text="今日放弃" if not historical else "暂不跟踪",
            hint=strict_strategy_avoid_hint(entry_position, historical),
            entry_distance=entry_distance,
        )
    if entry_position in {"in_zone", "below_zone"}:
        if buy_restricted and not resolver._restricted_market_track_allowed(candidate, entry_position, entry_distance):
            return resolver._signal_update(
                candidate=candidate,
                state="avoid",
                text="今日放弃" if not historical else "暂不跟踪",
                hint=restricted_market_avoid_hint(historical),
                entry_distance=entry_distance,
            )
        state = "watch" if candidate.score >= 82 else "avoid"
        return resolver._signal_update(
            candidate=candidate,
            state=state,
            text="继续观察" if state == "watch" else ("今日放弃" if not historical else "暂不跟踪"),
            hint=structure_pending_hint(entry_position, historical),
            entry_distance=entry_distance,
        )
    if candidate.score < 82:
        return resolver._signal_update(
            candidate=candidate,
            state="avoid",
            text="暂不跟踪",
            hint="结构和位置都不够优，今天不做。",
            entry_distance=entry_distance,
        )
    return resolver._signal_update(
        candidate=candidate,
        state="watch",
        text="继续观察",
        hint="趋势还在，但缩量、位置或承接还差一步。",
        entry_distance=entry_distance,
    )
