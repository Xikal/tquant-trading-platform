from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.services.low_buy.shared import PLAYBOOKS
from app.services.low_buy.strategy_policy import (
    StrategyTier,
    get_strategy_tier,
    participates_in_priority_board,
    requires_mainline_industry,
    strategy_layer,
    strong_buy_paused,
)
from app.services.low_buy.strategy_pool_config import StrategyPoolProfile, strategy_pool_profile

if TYPE_CHECKING:
    from app.services.low_buy.candidate_types import CandidateMetrics, StrategySetup
    from app.services.low_buy.shared import BoardCandidate


@dataclass(frozen=True)
class StrategyIdentity:
    key: str
    title: str
    subtitle: str = ""
    logic: str = ""
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class StrategyEntryContract:
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    take_profit: float


@dataclass(frozen=True)
class StrategyRiskContract:
    strong_buy_paused: bool
    requires_mainline_industry: bool
    participates_priority_board: bool
    status: str


class BaseStrategy(ABC):
    """Stable interface for low-buy strategies without changing existing rules."""

    key: str

    @property
    @abstractmethod
    def identity(self) -> StrategyIdentity:
        raise NotImplementedError

    @property
    def tier(self) -> StrategyTier:
        return get_strategy_tier(self.key)

    @property
    def layer(self) -> str:
        return strategy_layer(self.key)

    @property
    def status(self) -> str:
        if not self.pool_profile.enabled:
            return "paused"
        if self.tier == StrategyTier.CORE:
            return "active"
        if self.tier == StrategyTier.AUXILIARY:
            return "watch"
        return "research"

    @property
    def pool_profile(self) -> StrategyPoolProfile:
        return strategy_pool_profile(self.key)

    @property
    def requires_mainline_industry(self) -> bool:
        return requires_mainline_industry(self.key)

    @property
    def participates_priority_board(self) -> bool:
        return participates_in_priority_board(self.key)

    @property
    def strong_buy_paused(self) -> bool:
        return strong_buy_paused(self.key)

    @abstractmethod
    def passes_prefilter(self, *, item: "BoardCandidate", metrics: "CandidateMetrics") -> bool:
        raise NotImplementedError

    def score_candidate(
        self,
        *,
        item: "BoardCandidate",
        metrics: "CandidateMetrics",
        hot_industries: list[str],
    ) -> float:
        from app.services.low_buy.candidate_rules import score_candidate

        return score_candidate(
            strategy=self.key,
            item=item,
            metrics=metrics,
            hot_industries=hot_industries,
        )

    def build_setup(
        self,
        *,
        item: "BoardCandidate",
        metrics: "CandidateMetrics",
        score: float,
    ) -> "StrategySetup":
        from app.services.low_buy.candidate_rules import build_strategy_setup

        return build_strategy_setup(
            strategy=self.key,
            item=item,
            metrics=metrics,
            score=score,
        )

    def entry_contract(self, *, setup: "StrategySetup", stop_loss: float, take_profit: float) -> StrategyEntryContract:
        return StrategyEntryContract(
            entry_zone_low=setup.entry_zone_low,
            entry_zone_high=setup.entry_zone_high,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def exit_rules(
        self,
        *,
        metrics: "CandidateMetrics",
        setup: "StrategySetup",
        stop_loss: float,
        take_profit: float,
    ):
        from app.services.low_buy.exit_plan import build_exit_plan

        return build_exit_plan(
            strategy=self.key,
            metrics=metrics,
            setup=setup,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def risk_contract(self) -> StrategyRiskContract:
        return StrategyRiskContract(
            strong_buy_paused=self.strong_buy_paused,
            requires_mainline_industry=self.requires_mainline_industry,
            participates_priority_board=self.participates_priority_board,
            status=self.status,
        )


class RuleBackedLowBuyStrategy(BaseStrategy):
    """Native strategy class that delegates rule math to the existing rule module."""

    key: str

    @property
    def identity(self) -> StrategyIdentity:
        playbook = PLAYBOOKS[self.key]
        return StrategyIdentity(
            key=self.key,
            title=str(playbook.get("title") or self.key),
            subtitle=str(playbook.get("subtitle") or ""),
            logic=str(playbook.get("logic") or ""),
            notes=tuple(playbook.get("notes") or ()),
        )

    def passes_prefilter(self, *, item: "BoardCandidate", metrics: "CandidateMetrics") -> bool:
        from app.services.low_buy.candidate_rules import passes_strategy_prefilter

        return passes_strategy_prefilter(
            strategy=self.key,
            item=item,
            metrics=metrics,
        )


class ClassicRetraceStrategy(RuleBackedLowBuyStrategy):
    key = "classic_retrace"


class MaSupportStrategy(RuleBackedLowBuyStrategy):
    key = "ma_support"


class FirstBoardStrategy(RuleBackedLowBuyStrategy):
    key = "first_board"


class VolumeShrinkStrategy(RuleBackedLowBuyStrategy):
    key = "volume_shrink"


class LateSessionStrongSupportStrategy(RuleBackedLowBuyStrategy):
    key = "late_session_strong_support"


class CoreMidcapVwapMa5RetraceStrategy(RuleBackedLowBuyStrategy):
    key = "core_midcap_vwap_ma5_retrace"


class SectorMainlineFirstDivergenceStrategy(RuleBackedLowBuyStrategy):
    key = "sector_mainline_first_divergence_low_buy"


class MainlineLimitupShrinkRetraceReclaimStrategy(RuleBackedLowBuyStrategy):
    key = "mainline_limitup_shrink_retrace_reclaim"


class BreakoutSupportStrategy(RuleBackedLowBuyStrategy):
    key = "breakout_support"


class LimitUpBreakoutRetraceStrategy(RuleBackedLowBuyStrategy):
    key = "limit_up_breakout_retrace"


class DivergenceConsensusStrategy(RuleBackedLowBuyStrategy):
    key = "divergence_consensus"


class DeepPullbackStrategy(RuleBackedLowBuyStrategy):
    key = "deep_pullback"


class TrendReboundStrategy(RuleBackedLowBuyStrategy):
    key = "trend_rebound"


class MaChannelBandStrategy(RuleBackedLowBuyStrategy):
    key = "ma_channel_band"


class LeaderPullbackBandStrategy(RuleBackedLowBuyStrategy):
    key = "leader_pullback_band"


_STRATEGY_CLASSES: dict[str, type[BaseStrategy]] = {
    ClassicRetraceStrategy.key: ClassicRetraceStrategy,
    MaSupportStrategy.key: MaSupportStrategy,
    FirstBoardStrategy.key: FirstBoardStrategy,
    VolumeShrinkStrategy.key: VolumeShrinkStrategy,
    LateSessionStrongSupportStrategy.key: LateSessionStrongSupportStrategy,
    CoreMidcapVwapMa5RetraceStrategy.key: CoreMidcapVwapMa5RetraceStrategy,
    SectorMainlineFirstDivergenceStrategy.key: SectorMainlineFirstDivergenceStrategy,
    MainlineLimitupShrinkRetraceReclaimStrategy.key: MainlineLimitupShrinkRetraceReclaimStrategy,
    BreakoutSupportStrategy.key: BreakoutSupportStrategy,
    LimitUpBreakoutRetraceStrategy.key: LimitUpBreakoutRetraceStrategy,
    DivergenceConsensusStrategy.key: DivergenceConsensusStrategy,
    DeepPullbackStrategy.key: DeepPullbackStrategy,
    TrendReboundStrategy.key: TrendReboundStrategy,
    MaChannelBandStrategy.key: MaChannelBandStrategy,
    LeaderPullbackBandStrategy.key: LeaderPullbackBandStrategy,
}

_STRATEGY_CACHE: dict[str, BaseStrategy] = {}


def get_low_buy_strategy(strategy_key: str) -> BaseStrategy:
    if strategy_key not in PLAYBOOKS:
        raise KeyError(f"Unknown low-buy strategy: {strategy_key}")
    if strategy_key not in _STRATEGY_CACHE:
        strategy_class = _STRATEGY_CLASSES.get(strategy_key)
        if strategy_class is None:
            raise KeyError(f"No strategy class registered for: {strategy_key}")
        _STRATEGY_CACHE[strategy_key] = strategy_class()
    return _STRATEGY_CACHE[strategy_key]


def list_low_buy_strategies() -> list[BaseStrategy]:
    return [get_low_buy_strategy(strategy_key) for strategy_key in PLAYBOOKS]


def low_buy_strategy_exists(strategy_key: str) -> bool:
    return strategy_key in PLAYBOOKS
