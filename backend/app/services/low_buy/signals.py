from __future__ import annotations

from app.services.low_buy.signal_resolution import (
    build_signal_update,
    end_of_day_soft_confirmation,
    intraday_soft_confirmation,
)
from app.services.low_buy.intraday_confirmation import (
    build_intraday_confirmation,
    calculate_intraday_vwap,
    intraday_confirmation_hint,
    intraday_confirmation_passes,
    strategy_requires_intraday_confirmation,
)
from app.services.low_buy.market_state_rules import hard_buy_allowed, resolve_strategy_market_profile, soft_buy_allowed
from app.services.low_buy.shared import Any, LowBuyCandidateOut, LowBuyQuoteRefreshOut, pd
from app.services.low_buy.strategy_policy import strategy_layer, strong_buy_paused


class LowBuySignalMixin:
    def _refresh_buy_signal(
        self,
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
        entry_position = self._entry_position(refreshed_candidate, latest_price)
        vwap_value = calculate_intraday_vwap(intraday_bars)
        intraday_confirmation = build_intraday_confirmation(intraday_bars)
        intraday_veto_hint = self._intraday_daily_signal_veto(
            candidate=refreshed_candidate,
            quote=quote,
            intraday_bars=intraday_bars,
            vwap_value=vwap_value,
        )
        stop_confirmed = self._is_intraday_stop_confirmed(
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
        entry_distance = self._distance_to_entry_zone_pct(refreshed_candidate, latest_price)
        return self._resolve_signal_state(
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

    def _refresh_historical_buy_signal(self, candidate: LowBuyCandidateOut, latest_bar: pd.Series) -> LowBuyCandidateOut:
        close_price = float(latest_bar["close"])
        refreshed_candidate = candidate.model_copy(
            update={
                "latest_price": close_price,
                "change_pct": float(latest_bar["pct_chg"]),
                "quote_timestamp": str(latest_bar["date"]),
            }
        )
        entry_position = self._entry_position(refreshed_candidate, close_price)
        stop_confirmed = self._is_end_of_day_stop_confirmed(refreshed_candidate, latest_bar)
        soft_confirmed = end_of_day_soft_confirmation(refreshed_candidate, latest_bar)
        entry_distance = self._distance_to_entry_zone_pct(refreshed_candidate, close_price)
        return self._resolve_signal_state(
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
        block_hint = self._signal_block_hint(candidate)
        if block_hint:
            return self._signal_update(
                candidate=candidate,
                state="avoid",
                text="今日放弃" if not historical else "暂不跟踪",
                hint=block_hint,
                entry_distance=entry_distance,
            )
        if intraday_veto_hint:
            return self._signal_update(
                candidate=candidate,
                state="avoid" if not historical else "watch",
                text="今日放弃" if not historical else "继续观察",
                hint=intraday_veto_hint,
                entry_distance=entry_distance,
            )
        buy_restricted = self._market_buy_restricted(candidate)
        if self._can_hard_buy_now(candidate, entry_position, hard_confirmed and intraday_confirmed):
            return self._signal_update(
                candidate=candidate,
                state="buy_now",
                text="确定买入",
                hint=_buy_now_hint(entry_position, historical, soft=False),
                entry_distance=entry_distance,
                confirmed_trade_date=confirmed_trade_date if historical else None,
            )
        if self._can_soft_buy_now(candidate, entry_position, soft_confirmed and intraday_confirmed):
            return self._signal_update(
                candidate=candidate,
                state="soft_buy_now",
                text="确定买入",
                hint=_buy_now_hint(entry_position, historical, soft=True),
                entry_distance=entry_distance,
                confirmed_trade_date=confirmed_trade_date if historical else None,
            )
        if candidate.execution_ready and entry_position in self._near_entry_positions(candidate.strategy_key):
            if buy_restricted and not self._restricted_market_track_allowed(candidate, entry_position, entry_distance):
                return self._signal_update(
                    candidate=candidate,
                    state="avoid",
                    text="今日放弃" if not historical else "暂不跟踪",
                    hint=_restricted_market_avoid_hint(historical),
                    entry_distance=entry_distance,
                )
            return self._signal_update(
                candidate=candidate,
                state="near_entry",
                text="接近买点",
                hint=intraday_hint or _near_entry_hint(entry_position, entry_distance, historical),
                entry_distance=entry_distance,
            )
        if self._can_show_research_near_entry(candidate, entry_position):
            return self._signal_update(
                candidate=candidate,
                state="near_entry",
                text="接近买点",
                hint=self._research_near_entry_hint(candidate, entry_position, historical),
                entry_distance=entry_distance,
            )
        if candidate.execution_ready and self._should_avoid_on_entry_position(candidate.strategy_key, entry_position):
            return self._signal_update(
                candidate=candidate,
                state="avoid",
                text="今日放弃" if not historical else "暂不跟踪",
                hint=_strict_strategy_avoid_hint(entry_position, historical),
                entry_distance=entry_distance,
            )
        if candidate.execution_ready and entry_position == "below_stop":
            return self._signal_update(
                candidate=candidate,
                state="avoid",
                text="今日放弃" if not historical else "暂不跟踪",
                hint=_below_stop_hint(historical),
                entry_distance=entry_distance,
            )
        if candidate.execution_ready:
            if (
                not historical
                and strategy_requires_intraday_confirmation(candidate.strategy_key)
                and intraday_hint
            ):
                return self._signal_update(
                    candidate=candidate,
                    state="watch",
                    text="继续观察",
                    hint=intraday_hint,
                    entry_distance=entry_distance,
                )
            if buy_restricted and not self._restricted_market_track_allowed(candidate, entry_position, entry_distance):
                return self._signal_update(
                    candidate=candidate,
                    state="avoid",
                    text="今日放弃" if not historical else "暂不跟踪",
                    hint=_restricted_market_avoid_hint(historical),
                    entry_distance=entry_distance,
                )
            return self._signal_update(
                candidate=candidate,
                state="watch",
                text="继续观察",
                hint=_mature_watch_hint(entry_distance, historical),
                entry_distance=entry_distance,
            )
        if self._should_avoid_on_entry_position(candidate.strategy_key, entry_position):
            return self._signal_update(
                candidate=candidate,
                state="avoid",
                text="今日放弃" if not historical else "暂不跟踪",
                hint=_strict_strategy_avoid_hint(entry_position, historical),
                entry_distance=entry_distance,
            )
        if entry_position in {"in_zone", "below_zone"}:
            if buy_restricted and not self._restricted_market_track_allowed(candidate, entry_position, entry_distance):
                return self._signal_update(
                    candidate=candidate,
                    state="avoid",
                    text="今日放弃" if not historical else "暂不跟踪",
                    hint=_restricted_market_avoid_hint(historical),
                    entry_distance=entry_distance,
                )
            state = "watch" if candidate.score >= 82 else "avoid"
            return self._signal_update(
                candidate=candidate,
                state=state,
                text="继续观察" if state == "watch" else ("今日放弃" if not historical else "暂不跟踪"),
                hint=_structure_pending_hint(entry_position, historical),
                entry_distance=entry_distance,
            )
        if candidate.score < 82:
            return self._signal_update(
                candidate=candidate,
                state="avoid",
                text="暂不跟踪",
                hint="结构和位置都不够优，今天不做。",
                entry_distance=entry_distance,
            )
        return self._signal_update(
            candidate=candidate,
            state="watch",
            text="继续观察",
            hint="趋势还在，但缩量、位置或承接还差一步。",
            entry_distance=entry_distance,
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
        if strong_buy_paused(candidate.strategy_key):
            return False
        if not candidate.execution_ready:
            return False
        if candidate.risk_tier == "block":
            return False
        if self._weak_market_thematic_block_reason(candidate):
            return False
        if not hard_buy_allowed(
            candidate.strategy_key,
            candidate.market_state,
            candidate.market_state_strength,
        ):
            return False
        if self._has_distribution_hard_block(candidate):
            return False
        if not self._strategy_hard_buy_quality_gate(candidate):
            return False
        if candidate.score < self._hard_buy_min_score(candidate):
            return False
        if self._is_strict_in_zone_strategy(candidate.strategy_key):
            return entry_position == "in_zone" and hard_confirmed
        if entry_position == "in_zone":
            return hard_confirmed
        if entry_position == "below_zone":
            return hard_confirmed and self._below_zone_hard_buy_allowed(candidate)
        return False

    @staticmethod
    def _strategy_hard_buy_quality_gate(candidate: LowBuyCandidateOut) -> bool:
        if candidate.strategy_key == "first_board":
            return (
                candidate.distribution_risk_score < 5.2
                and not candidate.false_breakout_flag
                and not candidate.intraday_reversal_flag
            )
        if candidate.strategy_key == "volume_shrink":
            return (
                candidate.latest_price >= candidate.ma20 * 0.998
                and candidate.support_distance_pct <= 2.5
                and candidate.volume_shrink_ratio <= 1.08
                and candidate.distribution_risk_score < 5.0
                and not candidate.false_breakout_flag
                and not candidate.intraday_reversal_flag
            )
        if candidate.strategy_key == "late_session_strong_support":
            return (
                candidate.support_distance_pct <= 2.4
                and candidate.volume_shrink_ratio <= 1.08
                and candidate.distribution_risk_score < 4.8
                and _is_hot_frontline_candidate(candidate)
                and not candidate.false_breakout_flag
                and not candidate.intraday_reversal_flag
            )
        if candidate.strategy_key == "core_midcap_vwap_ma5_retrace":
            return (
                _is_hot_frontline_candidate(candidate)
                and candidate.support_distance_pct <= 1.8
                and candidate.volume_shrink_ratio <= 1.12
                and candidate.distribution_risk_score < 4.8
                and not candidate.false_breakout_flag
                and not candidate.intraday_reversal_flag
            )
        if candidate.strategy_key == "sector_mainline_first_divergence_low_buy":
            return (
                candidate.market_state in {"broad_rally", "repair"}
                and _is_hot_frontline_candidate(candidate)
                and candidate.support_distance_pct <= 2.0
                and candidate.volume_shrink_ratio <= 1.10
                and candidate.distribution_risk_score < 4.8
                and not candidate.false_breakout_flag
                and not candidate.intraday_reversal_flag
            )
        return True

    @staticmethod
    def _signal_block_hint(candidate: LowBuyCandidateOut) -> str:
        if candidate.risk_tier == "block":
            return "风险分层已触发阻断，即使价格到位也不执行。"
        profile = resolve_strategy_market_profile(
            candidate.strategy_key,
            candidate.market_state,
            candidate.market_state_strength,
        )
        if profile.execution_blocked:
            if LowBuySignalMixin._market_block_can_keep_research(candidate):
                return ""
            return f"当前{candidate.market_state_text or '市场环境'}明确阻断这类策略执行，先放弃本轮。"
        weak_market_reason = LowBuySignalMixin._weak_market_thematic_block_reason(candidate)
        if weak_market_reason:
            if LowBuySignalMixin._market_block_can_keep_research(candidate):
                return ""
            return weak_market_reason
        return ""

    @staticmethod
    def _market_block_can_keep_research(candidate: LowBuyCandidateOut) -> bool:
        return (
            strategy_layer(candidate.strategy_key) == "research"
            and candidate.risk_tier != "block"
            and not candidate.false_breakout_flag
            and not candidate.intraday_reversal_flag
            and candidate.distribution_risk_score < 6.5
        )

    @staticmethod
    def _market_buy_restricted(candidate: LowBuyCandidateOut) -> bool:
        hard_allowed = hard_buy_allowed(
            candidate.strategy_key,
            candidate.market_state,
            candidate.market_state_strength,
        )
        soft_allowed = soft_buy_allowed(
            candidate.strategy_key,
            candidate.market_state,
            candidate.market_state_strength,
        )
        return not hard_allowed and not soft_allowed

    @staticmethod
    def _restricted_market_track_allowed(
        candidate: LowBuyCandidateOut,
        entry_position: str,
        entry_distance: float,
    ) -> bool:
        if candidate.risk_tier in {"block", "degrade"}:
            return False
        if candidate.distribution_risk_score >= 5.8:
            return False
        if candidate.false_breakout_flag or candidate.intraday_reversal_flag:
            return False
        if entry_position == "below_zone" and entry_distance > 0.8:
            return False
        if candidate.score >= 92.0 and entry_position in {"in_zone", "below_zone", "near_above_zone"}:
            return True
        if candidate.score >= 88.0 and entry_position == "near_above_zone" and entry_distance <= 0.65:
            return True
        return (
            candidate.score >= 94.0
            and candidate.leader_rank in {"leader", "strong_follow"}
            and entry_position in {"in_zone", "near_above_zone"}
            and entry_distance <= 0.8
        )

    def _can_soft_buy_now(
        self,
        candidate: LowBuyCandidateOut,
        entry_position: str,
        soft_confirmed: bool,
    ) -> bool:
        if strong_buy_paused(candidate.strategy_key):
            return False
        if not candidate.execution_ready or not soft_confirmed:
            return False
        if candidate.risk_tier == "block":
            return False
        if self._weak_market_thematic_block_reason(candidate):
            return False
        if not soft_buy_allowed(
            candidate.strategy_key,
            candidate.market_state,
            candidate.market_state_strength,
        ):
            return False
        if self._has_distribution_soft_block(candidate):
            return False
        if not self._strategy_soft_buy_quality_gate(candidate):
            return False
        min_score = self._soft_buy_min_score(
            candidate.strategy_key,
            entry_position,
            candidate.dynamic_threshold_adjustment,
        )
        if self._is_strict_in_zone_strategy(candidate.strategy_key):
            return entry_position == "in_zone" and candidate.score >= min_score
        if entry_position == "in_zone":
            return candidate.score >= min_score
        if entry_position == "near_above_zone":
            return self._near_above_soft_buy_allowed(candidate) and candidate.score >= min_score
        return False

    @staticmethod
    def _strategy_soft_buy_quality_gate(candidate: LowBuyCandidateOut) -> bool:
        if candidate.strategy_key == "first_board":
            return (
                candidate.distribution_risk_score < 5.8
                and not candidate.false_breakout_flag
                and not candidate.intraday_reversal_flag
            )
        if candidate.strategy_key == "volume_shrink":
            return (
                candidate.latest_price >= candidate.ma20 * 0.992
                and candidate.support_distance_pct <= 2.8
                and candidate.volume_shrink_ratio <= 1.15
                and candidate.distribution_risk_score < 5.6
                and not candidate.false_breakout_flag
                and not candidate.intraday_reversal_flag
            )
        if candidate.strategy_key == "late_session_strong_support":
            return (
                candidate.support_distance_pct <= 2.8
                and candidate.volume_shrink_ratio <= 1.15
                and candidate.distribution_risk_score < 5.4
                and _is_hot_frontline_candidate(candidate)
                and not candidate.false_breakout_flag
                and not candidate.intraday_reversal_flag
            )
        if candidate.strategy_key == "core_midcap_vwap_ma5_retrace":
            return (
                _is_hot_frontline_candidate(candidate)
                and candidate.support_distance_pct <= 2.2
                and candidate.volume_shrink_ratio <= 1.18
                and candidate.distribution_risk_score < 5.2
                and not candidate.false_breakout_flag
                and not candidate.intraday_reversal_flag
            )
        if candidate.strategy_key == "sector_mainline_first_divergence_low_buy":
            return (
                candidate.market_state not in {"risk_release", "high_flyer_retreat"}
                and _is_hot_frontline_candidate(candidate)
                and candidate.support_distance_pct <= 2.4
                and candidate.volume_shrink_ratio <= 1.18
                and candidate.distribution_risk_score < 5.2
                and not candidate.false_breakout_flag
                and not candidate.intraday_reversal_flag
            )
        return True

    @staticmethod
    def _is_strict_in_zone_strategy(strategy_key: str) -> bool:
        return strategy_key in {"limit_up_breakout_retrace", "divergence_consensus"}

    @staticmethod
    def _can_show_research_near_entry(candidate: LowBuyCandidateOut, entry_position: str) -> bool:
        if strategy_layer(candidate.strategy_key) != "research":
            return False
        if candidate.research_stage not in {"near_entry", "buy_ready"}:
            return False
        if candidate.risk_tier == "block" or candidate.false_breakout_flag:
            return False
        if candidate.distribution_risk_score >= 6.5:
            return False
        if candidate.strategy_key == "divergence_consensus":
            return entry_position in {"in_zone", "near_above_zone"}
        return entry_position in {"in_zone", "near_above_zone", "below_zone"}

    @staticmethod
    def _research_near_entry_hint(candidate: LowBuyCandidateOut, entry_position: str, historical: bool) -> str:
        if candidate.research_stage == "buy_ready":
            return "研究策略确认条件基本满足，但当前仍暂停强买，只做接近买点提醒。"
        if candidate.strategy_key == "divergence_consensus":
            return "接近分歧高点确认位，等放量站稳且不冲高回落。"
        if entry_position == "below_zone":
            return "已回踩关键区下沿，必须快速收回支撑位才继续观察。"
        return "接近平台回踩关键位，等缩量承接和重新转强。"

    @staticmethod
    def _below_zone_hard_buy_allowed(candidate: LowBuyCandidateOut) -> bool:
        return candidate.strategy_key in {"classic_retrace", "ma_support", "breakout_support"}

    @staticmethod
    def _near_above_soft_buy_allowed(candidate: LowBuyCandidateOut) -> bool:
        return candidate.strategy_key in {"classic_retrace", "ma_support", "breakout_support"}

    @staticmethod
    def _weak_market_thematic_block_reason(candidate: LowBuyCandidateOut) -> str:
        weak_states = {"fast_rotation", "high_flyer_retreat", "risk_release"}
        if candidate.market_state not in weak_states or candidate.instrument_type != "stock":
            return ""
        if candidate.market_state == "risk_release":
            return "风险释放期不新增题材股低吸，先等市场止跌和情绪修复。"
        is_mainline = candidate.leader_rank in {"leader", "strong_follow"} and candidate.industry_tier in {
            "core_hot",
            "secondary_hot",
        }
        if not is_mainline:
            return "轮动过快/高位退潮时，只保留主线龙头或强跟随的热点行业票。"
        if candidate.distribution_risk_score >= 5.2 or candidate.false_breakout_flag or candidate.intraday_reversal_flag:
            return "弱市场里只做分歧释放后的确认，当前派发或冲高回落风险未解除。"
        if candidate.market_state == "high_flyer_retreat" and candidate.strategy_key not in {
            "classic_retrace",
            "ma_support",
            "breakout_support",
        }:
            return "高位退潮期不做右侧突破、深回撤或后排结构，只保留主线支撑型低吸。"
        return ""

    def _near_entry_positions(self, strategy_key: str) -> set[str]:
        if self._is_strict_in_zone_strategy(strategy_key):
            return {"in_zone"}
        return {"in_zone", "below_zone", "near_above_zone"}

    def _should_avoid_on_entry_position(self, strategy_key: str, entry_position: str) -> bool:
        if not self._is_strict_in_zone_strategy(strategy_key):
            return False
        return entry_position in {"below_zone", "below_stop"}

    @staticmethod
    def _has_distribution_hard_block(candidate: LowBuyCandidateOut) -> bool:
        if candidate.risk_tier == "block":
            return True
        if candidate.false_breakout_flag:
            if candidate.strategy_key in {"classic_retrace", "ma_support", "breakout_support"}:
                return candidate.distribution_risk_score >= 6.8
            return True
        if candidate.strategy_key in {"classic_retrace", "ma_support", "breakout_support"}:
            if candidate.distribution_risk_score >= 8.6:
                return True
            return candidate.intraday_reversal_flag and candidate.distribution_risk_score >= 7.0
        if candidate.distribution_risk_score >= 7.0:
            return True
        return candidate.intraday_reversal_flag and candidate.distribution_risk_score >= 5.0

    @staticmethod
    def _has_distribution_soft_block(candidate: LowBuyCandidateOut) -> bool:
        if candidate.risk_tier in {"block", "degrade"} and candidate.distribution_risk_score >= 5.5:
            return True
        if candidate.false_breakout_flag:
            if candidate.strategy_key in {"classic_retrace", "ma_support", "breakout_support"}:
                return candidate.distribution_risk_score >= 6.2
            return True
        if candidate.strategy_key in {"classic_retrace", "ma_support", "breakout_support"}:
            if candidate.distribution_risk_score >= 8.0:
                return True
            return candidate.intraday_reversal_flag and candidate.distribution_risk_score >= 6.4
        if candidate.stall_after_volume_flag and candidate.distribution_risk_score >= 5.0:
            return True
        return candidate.intraday_reversal_flag and candidate.distribution_risk_score >= 4.0

    @staticmethod
    def _hard_buy_min_score(candidate: LowBuyCandidateOut) -> float:
        base = {
            "limit_up_breakout_retrace": 88.0,
            "divergence_consensus": 90.0,
        }.get(candidate.strategy_key, 80.0)
        if candidate.risk_tier == "degrade":
            base += 3.0
        return base + max(candidate.dynamic_threshold_adjustment, 0.0)

    @staticmethod
    def _soft_buy_min_score(strategy: str, entry_position: str, threshold_shift: float = 0.0) -> float:
        thresholds = {
            "classic_retrace": {"in_zone": 84.0, "near_above_zone": 88.0},
            "ma_support": {"in_zone": 84.0, "near_above_zone": 87.0},
            "first_board": {"in_zone": 86.0, "near_above_zone": 90.0},
            "volume_shrink": {"in_zone": 85.0, "near_above_zone": 89.0},
            "late_session_strong_support": {"in_zone": 86.0, "near_above_zone": 90.0},
            "core_midcap_vwap_ma5_retrace": {"in_zone": 84.0, "near_above_zone": 88.0},
            "sector_mainline_first_divergence_low_buy": {"in_zone": 87.0, "near_above_zone": 91.0},
            "breakout_support": {"in_zone": 84.0, "near_above_zone": 88.0},
            "limit_up_breakout_retrace": {"in_zone": 90.0, "near_above_zone": 94.0},
            "divergence_consensus": {"in_zone": 92.0},
            "deep_pullback": {"in_zone": 88.0, "near_above_zone": 92.0},
            "trend_rebound": {"in_zone": 84.0, "near_above_zone": 87.0},
        }
        strategy_thresholds = thresholds.get(strategy, {})
        return strategy_thresholds.get(entry_position, 88.0) + max(threshold_shift, 0.0)

    def _is_intraday_stop_confirmed(
        self,
        candidate: LowBuyCandidateOut,
        quote: Any | None = None,
        *,
        intraday_bars: list[Any] | None = None,
        vwap_value: float = 0.0,
        require_intraday_structure: bool = False,
    ) -> bool:
        if quote is None:
            return False
        if require_intraday_structure and not intraday_bars:
            return False
        last_price = float(getattr(quote, "last_price", 0.0) or 0.0)
        open_price = float(getattr(quote, "open_price", 0.0) or 0.0)
        prev_close = float(getattr(quote, "prev_close", 0.0) or 0.0)
        low_price = float(getattr(quote, "low_price", 0.0) or 0.0)
        high_price = float(getattr(quote, "high_price", 0.0) or 0.0)
        change_pct = float(getattr(quote, "change_pct", 0.0) or 0.0)
        if last_price <= 0 or low_price <= 0 or last_price <= candidate.stop_loss * 1.006 or change_pct <= -6.5:
            return False
        intraday_range = max(high_price - low_price, 0.01)
        rebound_ratio = (last_price - low_price) / intraday_range
        held_reference = True
        if open_price > 0:
            held_reference = held_reference and last_price >= open_price * 0.995
        if prev_close > 0:
            held_reference = held_reference and last_price >= prev_close * 0.982
        if rebound_ratio < 0.35 or not held_reference:
            return False
        if intraday_bars:
            if vwap_value <= 0:
                vwap_value = calculate_intraday_vwap(intraday_bars)
            return intraday_soft_confirmation(
                candidate,
                quote,
                intraday_bars=intraday_bars,
                vwap_value=vwap_value,
                require_intraday_structure=require_intraday_structure,
            )
        return True

    def _is_end_of_day_stop_confirmed(self, candidate: LowBuyCandidateOut, latest_bar: pd.Series) -> bool:
        close_price = float(latest_bar["close"])
        open_price = float(latest_bar["open"])
        low_price = float(latest_bar["low"])
        high_price = float(latest_bar["high"])
        pct_chg = float(latest_bar["pct_chg"])
        if close_price <= candidate.stop_loss * 1.006 or pct_chg <= -6.5:
            return False
        intraday_range = max(high_price - low_price, 0.01)
        rebound_ratio = (close_price - low_price) / intraday_range
        return rebound_ratio >= 0.35 and close_price >= open_price * 0.995

    @staticmethod
    def _intraday_daily_signal_veto(
        *,
        candidate: LowBuyCandidateOut,
        quote: Any | None,
        intraday_bars: list[Any] | None,
        vwap_value: float,
    ) -> str:
        if quote is None:
            return ""
        last_price = float(getattr(quote, "last_price", 0.0) or 0.0)
        open_price = float(getattr(quote, "open_price", 0.0) or 0.0)
        volume_ratio = float(getattr(quote, "volume_ratio", 0.0) or 0.0)
        if last_price <= 0:
            return ""
        if volume_ratio >= 2.2 and open_price > 0 and last_price < open_price * 0.995:
            return "盘中放量但价格跌回开盘价下方，日线缩量承接口径已走坏，今日不执行。"
        if intraday_bars and _recent_intraday_distribution(intraday_bars, vwap_value):
            return "盘中最近几根分时放量走弱，没有守住分时均价，否决日线候选信号。"
        return ""

    def _entry_position(self, candidate: LowBuyCandidateOut, latest_price: float) -> str:
        if latest_price <= 0:
            return "unknown"
        if latest_price <= candidate.stop_loss * 1.003:
            return "below_stop"
        if candidate.entry_zone_low <= latest_price <= candidate.entry_zone_high:
            return "in_zone"
        if latest_price < candidate.entry_zone_low:
            return "below_zone"
        tolerance_pct = self._get_entry_tolerance_pct(candidate.strategy_key)
        if tolerance_pct > 0 and latest_price <= candidate.entry_zone_high * (1 + tolerance_pct / 100):
            return "near_above_zone"
        return "above_zone"

    @staticmethod
    def _distance_to_entry_zone_pct(candidate: LowBuyCandidateOut, latest_price: float) -> float:
        if candidate.entry_zone_low <= latest_price <= candidate.entry_zone_high:
            return 0.0
        if latest_price > candidate.entry_zone_high:
            return round(((latest_price - candidate.entry_zone_high) / max(candidate.entry_zone_high, 0.01)) * 100, 3)
        return round(((candidate.entry_zone_low - latest_price) / max(candidate.entry_zone_low, 0.01)) * 100, 3)

    def _apply_live_quotes(self, candidates: list[LowBuyCandidateOut], quote_map: dict[str, Any] | None = None) -> list[LowBuyCandidateOut]:
        if not candidates:
            return []
        enriched_by_symbol: dict[str, LowBuyCandidateOut] = {}
        batch_quotes = quote_map or self.market_data.get_quotes_batch([candidate.symbol for candidate in candidates])
        intraday_bars_by_symbol = self._load_live_quote_intraday_bars(candidates, batch_quotes)
        for candidate in candidates:
            quote = batch_quotes.get(candidate.symbol)
            if quote is None:
                enriched_by_symbol[candidate.symbol] = candidate
                continue
            refreshed = candidate.model_copy(update={"latest_price": round(float(quote.last_price), 3), "change_pct": round(float(quote.change_pct), 3), "quote_timestamp": str(quote.timestamp)})
            enriched_by_symbol[candidate.symbol] = self._refresh_buy_signal(
                refreshed,
                quote=quote,
                intraday_bars=intraday_bars_by_symbol.get(candidate.symbol),
                require_intraday_structure=True,
            )
        return [enriched_by_symbol.get(candidate.symbol, candidate) for candidate in candidates]

    def _load_live_quote_intraday_bars(
        self,
        candidates: list[LowBuyCandidateOut],
        quote_map: dict[str, Any],
        *,
        max_symbols: int = 24,
    ) -> dict[str, list[Any]]:
        symbols: list[str] = []
        for candidate in candidates:
            quote = quote_map.get(candidate.symbol)
            if quote is None:
                continue
            latest_price = float(getattr(quote, "last_price", 0.0) or 0.0)
            if latest_price <= 0:
                continue
            entry_position = self._entry_position(candidate, latest_price)
            if entry_position not in {"in_zone", "below_zone", "near_above_zone"}:
                continue
            symbols.append(candidate.symbol)
            if len(symbols) >= max_symbols:
                break
        return self.market_data.get_intraday_bars_batch(
            symbols=symbols,
            period="1m",
            limit=30,
            max_workers=8,
        )


def _is_hot_frontline_candidate(candidate: LowBuyCandidateOut) -> bool:
    return (
        candidate.leader_rank in {"leader", "strong_follow"}
        and candidate.industry_tier in {"core_hot", "secondary_hot"}
    )


def _recent_intraday_distribution(intraday_bars: list[Any], vwap_value: float) -> bool:
    recent = list(intraday_bars or [])[-5:]
    if len(recent) < 4:
        return False
    latest = recent[-1]
    latest_close = _bar_float(latest, "close")
    latest_open = _bar_float(latest, "open")
    if latest_close <= 0:
        return False
    volumes = [_bar_float(bar, "volume") for bar in recent]
    previous_avg = sum(volumes[:-1]) / max(len(volumes) - 1, 1)
    latest_volume_expanded = volumes[-1] >= max(previous_avg, 1.0) * 1.55
    below_vwap = vwap_value > 0 and latest_close < vwap_value * 0.998
    weak_bar = latest_close < latest_open * 0.998
    lows = [_bar_float(bar, "low") for bar in recent if _bar_float(bar, "low") > 0]
    lower_low = len(lows) >= 3 and lows[-1] < min(lows[:-1]) * 0.998
    return latest_volume_expanded and (below_vwap or weak_bar or lower_low)


def _bar_float(bar: Any, field: str) -> float:
    return float(getattr(bar, field, 0.0) or 0.0)


def _buy_now_hint(entry_position: str, historical: bool, soft: bool) -> str:
    if soft:
        if historical:
            return "收盘价已进入买点区，软确认成立，可按轻仓试错处理。"
        if entry_position == "near_above_zone":
            return "价格接近买点区上沿且软确认成立，可先轻仓试错，强确认后再补。"
        return "价格已进入买点区，软确认成立，可先轻仓试错，强确认后再补。"
    if historical:
        return "收盘价已进入买点区，且日线止跌确认成立。" if entry_position == "in_zone" else "收盘价已经跌入并略穿买点区，但日线止跌确认成立。"
    return "价格已进入买点区，且日内止跌确认基本成立，可按 2-3 成仓分批试仓，跌破止损位离场。" if entry_position == "in_zone" else "价格已经跌入并略穿买点区，但承接已企稳，可按 3-4 成仓分批试仓，跌破止损位离场。"


def _strict_strategy_avoid_hint(entry_position: str, historical: bool) -> str:
    if entry_position == "below_stop":
        return _below_stop_hint(historical)
    if historical:
        return "收盘价已跌穿买点区，这类涨停突破回踩不做下方硬接，暂不跟踪。"
    return "价格已跌穿买点区，这类涨停突破回踩只做区间内确认，不做下方硬接。"


def _near_entry_hint(entry_position: str, entry_distance: float, historical: bool) -> str:
    if entry_position == "in_zone":
        return "价格到位了，但收盘确认还不够。" if historical else "价格已进入买点区，但日内止跌确认还不够，先等承接稳定。"
    if entry_position == "below_zone":
        return "价格已经跌入并略穿买点区，但收盘确认还不够。" if historical else "价格已经跌入并略穿买点区，但还没止跌确认，不能机械接刀。"
    return f"历史回放里距离买点区上沿只差 {entry_distance:.2f}%。" if historical else f"离买点区上沿只差 {entry_distance:.2f}%，承接确认后可准备试仓。"


def _below_stop_hint(historical: bool) -> str:
    return "历史回放里价格已逼近止损线，本次低吸逻辑失效。" if historical else "价格已经逼近或跌破止损线，低吸逻辑失效，今天不再接。"


def _restricted_market_avoid_hint(historical: bool) -> str:
    if historical:
        return "历史回放处于弱市场状态，只有高分且贴近买点的票才保留跟踪。"
    return "当前市场偏弱，只保留高分且贴近买点的票；这只暂不进入执行观察。"


def _mature_watch_hint(entry_distance: float, historical: bool) -> str:
    return f"历史回放里还没到买点区，距离约 {entry_distance:.2f}%。" if historical else f"结构已经成熟，但当前价距买点区还有 {entry_distance:.2f}%，不追高。"


def _structure_pending_hint(entry_position: str, historical: bool) -> str:
    if historical:
        return "历史回放里价格到了买点区，但结构条件还没全部满足。" if entry_position == "in_zone" else "历史回放里价格跌入并略穿买点区，但结构还没成熟。"
    return "价格已经到买点区，但结构条件还没全部满足，先等缩量、承接或趋势确认。" if entry_position == "in_zone" else "价格已经跌入并略穿买点区，但结构还没成熟，不能只因为便宜就买。"
