from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import BacktestTrade
from app.models.schema_defs.backtest import BacktestValidationCreate
from app.models.schema_defs.phase4 import MLSignalTrainRequest
from app.services.backtest.regime_parameter_promotion import promote_regime_parameter_versions
from app.services.markowitz_optimizer import _daily_strategy_return_matrix, optimize_markowitz_portfolio
from app.services.ml_signal.modeling import promotion_blocks
from app.services.ml_signal.promotion_quality import binomial_accuracy_p_value
from app.services.position_policy_research import run_position_policy_research
from app.services.quant import QuantParameterVersionService
from app.services.quant.runtime_parameters import clear_quant_parameter_cache
from app.services.quant.state_scope import reset_market_state_scope, set_market_state_scope


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_validation_p_value_blocks_weak_ml_promotion() -> None:
    assert binomial_accuracy_p_value(80, 100) < 0.05
    blocks = promotion_blocks(
        payload=MLSignalTrainRequest(promote=True, min_samples=100, max_validation_p_value=0.05),
        metrics={"validation_accuracy": 0.52, "validation_accuracy_p_value": 0.72, "cv_accuracy_std": 0.01},
        sample_count=200,
    )
    assert any("validation_accuracy_p_value" in item for item in blocks)


def test_validation_request_accepts_explicit_state_param_promotion_flag() -> None:
    payload = BacktestValidationCreate(
        strategy_key="first_board",
        start_date="2025-01-01",
        end_date="2025-12-31",
        auto_promote_state_params=True,
    )

    assert payload.auto_promote_state_params is True


def test_markowitz_optimizer_returns_real_weights_and_frontier() -> None:
    db = _db()
    for idx in range(1, 8):
        db.add(
            BacktestTrade(
                run_id=1,
                trade_date=f"2026-04-{idx:02d}",
                symbol=f"60000{idx}",
                side="sell",
                strategy_key="first_board",
                pnl_pct=1.0 + idx * 0.1,
            )
        )
        db.add(
            BacktestTrade(
                run_id=1,
                trade_date=f"2026-04-{idx:02d}",
                symbol=f"00000{idx}",
                side="sell",
                strategy_key="volume_shrink",
                pnl_pct=0.4 - idx * 0.05,
            )
        )
    db.commit()

    result = optimize_markowitz_portfolio(db, run_id=1, monte_carlo_samples=32)

    assert result["method"] == "markowitz"
    assert result["weights"]
    assert result["efficient_frontier"]
    assert abs(sum(item["weight_pct"] for item in result["weights"]) - 100.0) < 0.2


def test_markowitz_daily_returns_are_not_summed_trade_percentages() -> None:
    db = _db()
    db.add_all(
        [
            BacktestTrade(run_id=11, trade_date="2026-04-01", symbol="600001", side="sell", strategy_key="first_board", pnl_pct=10.0),
            BacktestTrade(run_id=11, trade_date="2026-04-01", symbol="600002", side="sell", strategy_key="first_board", pnl_pct=-10.0),
            BacktestTrade(
                run_id=11,
                trade_date="2026-04-01",
                symbol="600003",
                side="sell",
                strategy_key="volume_shrink",
                pnl_amount=50.0,
                gross_amount=5000.0,
                pnl_pct=8.0,
            ),
        ]
    )
    db.commit()

    matrix, strategies = _daily_strategy_return_matrix(db, run_id=11)

    first_board_index = strategies.index("first_board")
    volume_index = strategies.index("volume_shrink")
    assert matrix[0, first_board_index] == 0.0
    assert round(float(matrix[0, volume_index]), 4) == 0.01


def test_market_state_scoped_parameters_override_default() -> None:
    db = _db()
    service = QuantParameterVersionService(db)
    service.create(
        payload=_param_payload("default-low-buy", "", 75),
        created_by="tester",
    )
    service.create(
        payload=_param_payload("repair-low-buy", "repair", 88),
        created_by="tester",
    )
    clear_quant_parameter_cache()

    token = set_market_state_scope("repair")
    try:
        assert service.current(scope="low_buy", market_state_scope="repair").params["low_buy"]["min_priority_score"] == 88
    finally:
        reset_market_state_scope(token)


def test_regime_parameter_promotion_uses_only_stable_state_buckets() -> None:
    db = _db()
    result = promote_regime_parameter_versions(
        db,
        validation_result={
            "best_params_by_market_state": {
                "repair": {"min_score": 84, "max_position_pct": 20},
                "risk_release": {"min_score": 90},
            },
            "by_market_state": {
                "repair": {"window_count": 2, "pass_rate": 0.5},
                "risk_release": {"window_count": 1, "pass_rate": 1.0},
            },
        },
        strategy_key="first_board",
        operator="tester",
    )

    assert result["promoted_count"] == 1
    assert result["skipped_count"] == 1


def test_position_policy_research_includes_rl_shadow_payload() -> None:
    db = _db()
    for idx in range(10):
        db.add(
            BacktestTrade(
                run_id=7,
                trade_date=f"2026-05-{idx + 1:02d}",
                symbol=f"600{idx:03d}",
                side="sell",
                strategy_key="first_board",
                signal_state="buy_now",
                market_state="repair",
                pnl_pct=1.0 if idx % 2 == 0 else -0.6,
            )
        )
    db.commit()

    result = run_position_policy_research(db, run_id=7)

    shadow = result["shadow_reinforcement_learning"]
    assert result["production_enabled"] is False
    assert shadow["algorithm"] == "ppo_shadow_mode"
    assert shadow["production_enabled"] is False


def _param_payload(version: str, market_state_scope: str, min_score: int):
    from app.models.schema_defs.phase4 import QuantParameterSetCreate

    return QuantParameterSetCreate(
        version=version,
        scope="low_buy",
        market_state_scope=market_state_scope,
        params={"low_buy": {"min_priority_score": min_score}},
        activate=True,
    )
