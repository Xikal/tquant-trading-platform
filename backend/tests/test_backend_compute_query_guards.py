from __future__ import annotations

from sqlalchemy import create_engine, event

from backend.tests.test_low_buy_read_paths import _candidate, _performance
from app.models.base import Base
from app.services.low_buy.priority_items import build_priority_items
from app.services.low_buy.priority_types import PriorityCandidate, PriorityMarketContext, StrategyHit


def test_priority_items_build_keeps_query_budget_at_zero() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _count_sql(_conn, _cursor, statement, _parameters, _context, _executemany):  # noqa: ANN001
        statements.append(statement)

    try:
        items = build_priority_items(
            rows=[
                PriorityCandidate(
                    symbol=f"600{index:03d}",
                    hits=[
                        StrategyHit(
                            strategy_key="first_board",
                            strategy_title="首板回调",
                            family_key="first_board",
                            candidate=_candidate(
                                strategy_key="first_board",
                                strategy_title="首板回调",
                                symbol=f"600{index:03d}",
                                market="SH",
                                score=88.0 + index,
                                buy_signal_state="watch",
                                buy_signal_text="观察",
                            ),
                            strategy_weight_score=88.0 + index,
                            context_bonus=0.0,
                            performance=_performance(),
                        )
                    ],
                )
                for index in range(12)
            ],
            market_context=_market_context(),
            builder=_PriorityBuilder(),
        )
    finally:
        event.remove(engine, "before_cursor_execute", _count_sql)

    assert len(items) == 12
    assert statements == []


class _PriorityBuilder:
    def _aggregate_strategy_weight(self, hits: list[StrategyHit]) -> float:
        return sum(hit.strategy_weight_score for hit in hits)

    def _effective_strategy_count(self, hits: list[StrategyHit]) -> int:
        return len(hits)

    def _effective_family_count(self, hits: list[StrategyHit]) -> int:
        return len({hit.family_key for hit in hits})

    def _final_rank_score(
        self,
        *,
        candidate,
        aggregate_weight: float,
        family_count: int,
        strategy_weight: float,
        market_context: PriorityMarketContext,
    ) -> float:  # noqa: ANN001
        return float(candidate.score + aggregate_weight + family_count + strategy_weight + market_context.market_bonus)

    def _sector_rotation_bonus(self, candidate, market_context: PriorityMarketContext) -> float:  # noqa: ANN001
        return 0.0

    def _industry_rotation_text(self, candidate, market_context: PriorityMarketContext, bonus: float) -> str:  # noqa: ANN001
        return ""

    def _priority_action_summary(self, candidate) -> str:  # noqa: ANN001
        return "观察"

    def _priority_blocked_reason(self, candidate) -> str:  # noqa: ANN001
        return ""

    def _display_strategy_titles(self, hits: list[StrategyHit]) -> list[str]:
        return [hit.strategy_title for hit in hits]


def _market_context() -> PriorityMarketContext:
    return PriorityMarketContext(
        market_state="repair",
        market_bonus=1.0,
        market_state_strength=0.5,
        regime_confidence=0.8,
        state_persistence_days=2,
        transition_risk=0.1,
        market_state_label="修复",
        market_state_description="测试",
        breadth_ready=True,
        emotion_ready=True,
        stock_up_ratio=0.55,
        stock_median_change=0.4,
        style_divergence=0.2,
        hot_turnover=0.8,
        hot_overlap_ratio=0.5,
        limit_down_count=0,
        limit_up_count=12,
        board_height=2,
        previous_board_height=2,
        promotion_ratio=0.4,
        broken_board_ratio=0.2,
        promotion_break_gap=0.1,
        promotion_break_pressure=0.2,
        high_flyer_retreat_ratio=0.1,
        high_flyer_gap_speed=0.1,
        distribution_pressure=12.0,
        emotion_temperature="neutral",
        emotion_temperature_text="中性",
        emotion_temperature_score=50.0,
        hot_industries=[],
        hot_industry_source="historical_cache",
        hot_industry_source_text="测试",
        mainline_lifecycle_state="repair",
        mainline_lifecycle_text="主线阶段：测试",
        industry_ranks={},
    )
