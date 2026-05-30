from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.models.base import Base
from app.models.entities import StrategyPromotionReview, StrategyTierOverride
from app.services.decision_context.promotion_engine import (
    PromotionEvidence,
    review_strategy_promotion,
)
from app.services.low_buy.strategy_policy import participates_in_priority_board


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as session:
        yield session


def test_promotion_engine_keeps_n_pattern_research_when_oos_missing(db_session) -> None:
    result = review_strategy_promotion(
        db_session,
        PromotionEvidence(
            strategy_key="n_pattern_long_wash",
            review_date=date(2026, 5, 30),
            sample_count=620,
            profit_factor=1.6,
            average_trade_pct=0.72,
            max_drawdown_pct=-6.0,
            max5_return_pct=12.0,
            max10_return_pct=9.0,
            quarterly_stability=0.8,
            walk_forward_pass=True,
            oos_pass=False,
        ),
    )

    assert result.recommendation == "stay_research"
    assert "OOS" in " ".join(result.blocking_reasons)
    assert result.can_apply_override is False
    assert participates_in_priority_board("n_pattern_long_wash") is False
    assert db_session.execute(select(StrategyPromotionReview)).scalar_one().recommendation == "stay_research"
    assert db_session.execute(select(StrategyTierOverride)).scalar_one_or_none() is None


def test_promotion_engine_recommends_aux_without_auto_apply(db_session) -> None:
    result = review_strategy_promotion(
        db_session,
        PromotionEvidence(
            strategy_key="n_pattern_long_wash",
            review_date=date(2026, 5, 30),
            sample_count=240,
            profit_factor=1.26,
            average_trade_pct=0.18,
            max_drawdown_pct=-8.5,
            max5_return_pct=4.2,
            max10_return_pct=5.0,
            quarterly_stability=0.64,
            walk_forward_pass=True,
            oos_pass=True,
        ),
    )

    assert result.recommendation == "promote_to_auxiliary_review"
    assert result.recommended_tier == "auxiliary"
    assert result.can_apply_override is False
    assert get_settings().promotion_engine_auto_apply_enabled is False
    assert db_session.execute(select(StrategyTierOverride)).scalar_one_or_none() is None


def test_promotion_engine_core_requires_stronger_portfolio_evidence(db_session) -> None:
    result = review_strategy_promotion(
        db_session,
        PromotionEvidence(
            strategy_key="n_pattern_long_wash",
            review_date=date(2026, 5, 30),
            sample_count=540,
            profit_factor=1.42,
            average_trade_pct=0.51,
            max_drawdown_pct=-7.5,
            max5_return_pct=8.0,
            max10_return_pct=6.5,
            quarterly_stability=0.74,
            walk_forward_pass=True,
            oos_pass=True,
            recent_quarter_returns_pct=(2.1, 1.4),
        ),
    )

    assert result.recommendation == "promote_to_core_review"
    assert result.recommended_tier == "core"
    assert result.can_apply_override is False
    assert db_session.execute(select(StrategyTierOverride)).scalar_one_or_none() is None
