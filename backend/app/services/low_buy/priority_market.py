from __future__ import annotations

from typing import Protocol

from app.services.low_buy.priority_types import PriorityMarketContext
from app.services.low_buy.shared import Session


class PriorityMarketBuilder(Protocol):
    market_data: object

    def _load_persisted_pool(self, db: Session, latest_trade_date: str) -> dict | None: ...

    def _resolve_hot_industries_cached(
        self,
        db: Session,
        latest_trade_date: str,
        pooled_candidates: dict,
    ) -> tuple[list[str], str, str]: ...

    def _load_recent_hot_industry_sequences(self, db: Session, latest_trade_date: str) -> list: ...

    def _rank_hot_industries(self, hot_industries: list[str]) -> dict[str, int]: ...


def build_market_context(
    *,
    builder: PriorityMarketBuilder,
    db: Session,
    latest_trade_date: str,
) -> PriorityMarketContext:
    persisted_pool = builder._load_persisted_pool(db=db, latest_trade_date=latest_trade_date) or {}
    if not latest_trade_date and not persisted_pool:
        return empty_priority_market_context()
    hot_industries, hot_industry_source, hot_industry_source_text = builder._resolve_hot_industries_cached(
        db=db,
        latest_trade_date=latest_trade_date,
        pooled_candidates=persisted_pool,
    )
    regime = builder.market_data.get_market_regime_fast(
        latest_trade_date=latest_trade_date,
        hot_industries=hot_industries,
        hot_industry_source=hot_industry_source,
        hot_industry_source_text=hot_industry_source_text,
        recent_hot_sequences=builder._load_recent_hot_industry_sequences(
            db=db,
            latest_trade_date=latest_trade_date,
        ),
    )
    return PriorityMarketContext(
        market_state=regime.state,
        market_bonus=regime.ranking_bonus,
        market_state_strength=regime.state_strength,
        regime_confidence=regime.regime_confidence,
        state_persistence_days=regime.state_persistence_days,
        transition_risk=regime.transition_risk,
        market_state_label=regime.label,
        market_state_description=regime.description,
        breadth_ready=regime.breadth_ready,
        emotion_ready=regime.emotion_ready,
        stock_up_ratio=regime.stock_up_ratio,
        stock_median_change=regime.stock_median_change,
        style_divergence=regime.style_divergence,
        hot_turnover=regime.hot_turnover,
        hot_overlap_ratio=regime.hot_overlap_ratio,
        limit_down_count=regime.limit_down_count,
        limit_up_count=regime.limit_up_count,
        board_height=regime.board_height,
        previous_board_height=regime.previous_board_height,
        promotion_ratio=regime.promotion_ratio,
        broken_board_ratio=regime.broken_board_ratio,
        promotion_break_gap=regime.promotion_break_gap,
        promotion_break_pressure=regime.promotion_break_pressure,
        high_flyer_retreat_ratio=regime.high_flyer_retreat_ratio,
        high_flyer_gap_speed=regime.high_flyer_gap_speed,
        distribution_pressure=regime.distribution_pressure,
        emotion_temperature=regime.emotion_temperature,
        emotion_temperature_text=regime.emotion_temperature_text,
        emotion_temperature_score=regime.emotion_temperature_score,
        hot_industries=regime.hot_industries,
        hot_industry_source=regime.hot_industry_source,
        hot_industry_source_text=regime.hot_industry_source_text,
        mainline_lifecycle_state=regime.mainline_lifecycle_state,
        mainline_lifecycle_text=regime.mainline_lifecycle_text,
        industry_ranks=builder._rank_hot_industries(regime.hot_industries),
    )


def empty_priority_market_context() -> PriorityMarketContext:
    return PriorityMarketContext(
        market_state="low_volume_wait",
        market_bonus=0.0,
        market_state_label="缩量无主线",
        market_state_description="当前还没有可用样本，先按中性偏防守环境处理。",
        regime_confidence=0.0,
        state_persistence_days=1,
        transition_risk=0.0,
        breadth_ready=False,
        emotion_ready=False,
        stock_up_ratio=0.0,
        stock_median_change=0.0,
        style_divergence=0.0,
        hot_turnover=0.0,
        hot_overlap_ratio=0.0,
        limit_down_count=None,
        limit_up_count=0,
        board_height=0,
        previous_board_height=0,
        promotion_ratio=0.0,
        broken_board_ratio=0.0,
        promotion_break_gap=0.0,
        promotion_break_pressure=0.0,
        high_flyer_retreat_ratio=0.0,
        high_flyer_gap_speed=0.0,
        distribution_pressure=0.0,
        emotion_temperature="unknown",
        emotion_temperature_text="情绪温度数据不足",
        emotion_temperature_score=0.0,
        hot_industries=[],
        hot_industry_source="unavailable",
        hot_industry_source_text="热点来源：暂无有效归因",
        mainline_lifecycle_state="unknown",
        mainline_lifecycle_text="主线阶段：热点归因不足",
        industry_ranks={},
        market_state_strength=0.0,
    )
