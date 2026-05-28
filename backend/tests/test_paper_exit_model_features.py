from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.models.entities import PaperPosition
from app.services.paper.exit_model_features import build_exit_model_features
from app.services.paper.exit_types import PaperExitDecision
from app.services.paper.quote_quality import PaperQuotePrice
from app.services.paper.smart_exit_context import PaperExitContext


def test_exit_model_features_capture_position_market_and_rule_context() -> None:
    now = datetime(2026, 5, 28, 10, 30)
    position = PaperPosition(
        account_id=1,
        symbol="600000",
        name="浦发银行",
        quantity=1000,
        available_quantity=800,
        cost_basis=Decimal("10.0000"),
        latest_price=Decimal("10.8000"),
        strategy_sources='["first_board"]',
        opened_at=now - timedelta(days=3),
    )
    decision = PaperExitDecision(
        quantity=300,
        reason="保护性止盈",
        code="take_profit",
        pnl_pct=8.0,
        hold_days=3,
        sell_ratio=0.3,
        strategy_key="first_board",
        action_signal="profit_take",
    )
    quote = PaperQuotePrice(symbol="600000", price=10.8, quality="fresh", high_price=11.2, prev_close=10.2)
    context = PaperExitContext(
        vwap=10.5,
        above_vwap=True,
        intraday_usable=True,
        volume_release_ratio=1.3,
        high_pullback_ratio=0.25,
        trailing_high_price=11.2,
        trailing_stop_price=10.7,
    )
    bars = [
        SimpleNamespace(open=10.0, high=10.3, low=9.9, close=10.1, volume=1000 + idx * 10, amount=(1000 + idx * 10) * 10.1)
        for idx in range(30)
    ]

    features = build_exit_model_features(
        position=position,
        decision=decision,
        price=10.8,
        now=now,
        quote=quote,
        context=context,
        intraday_bars=bars,
        account_total_assets=100_000,
        market_context={"market_state": "broad_rally", "market_strength": 0.72, "sector_strength": 0.64},
    )

    assert features.symbol == "600000"
    assert features.strategy_key == "first_board"
    assert features.rule_action == "sell_30"
    assert features.data_quality == "fresh"
    assert features.position_pct == 10.8
    assert features.pnl_pct == 8.0
    assert features.pullback_from_high_pct > 0
    assert features.vwap_deviation_pct > 0
    assert features.feature_values["available_ratio"] == 0.8
    assert features.feature_values["market_strength"] == 0.72
    assert features.risk_flags == []


def test_exit_model_features_degrade_on_invalid_or_stale_data() -> None:
    now = datetime(2026, 5, 28, 10, 30)
    position = PaperPosition(
        account_id=1,
        symbol="600001",
        name="测试",
        quantity=100,
        available_quantity=100,
        cost_basis=Decimal("10.0000"),
        latest_price=Decimal("0.0000"),
        opened_at=now,
    )
    decision = PaperExitDecision(
        quantity=0,
        reason="持有",
        code="hold",
        pnl_pct=0,
        hold_days=0,
        sell_ratio=0,
        strategy_key="",
    )

    features = build_exit_model_features(
        position=position,
        decision=decision,
        price=0,
        now=now,
        quote=PaperQuotePrice(symbol="600001", price=0, quality="stale"),
        intraday_bars=[SimpleNamespace(close=0)],
    )

    assert features.data_quality == "unavailable"
    assert "invalid_price" in features.risk_flags
    assert "quote_stale" in features.risk_flags
    assert features.rule_action == "hold"
