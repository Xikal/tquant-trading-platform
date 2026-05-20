from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import BacktestRun, BacktestTrade, MarketEventCache, PaperAccount, PaperTrade
from app.services.alternative_data import AlternativeDataSentimentService
from app.services.arbitrage_research import build_multi_exchange_arbitrage_research
from app.services.backtest.broker import BacktestBroker, ExecutionRequest
from app.services.backtest.data_provider import DailyBar
from app.services.black_litterman_optimizer import optimize_black_litterman_portfolio
from app.services.live_backtest_monitor import build_live_backtest_comparison
from app.services.low_buy.position_sizing import KellyPosition
from app.services.paper.admission import AdmissionResult
from app.services.paper.sizing import PositionSizer


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def _bar(symbol: str = "600000") -> DailyBar:
    return DailyBar(
        symbol=symbol,
        trade_date="2026-05-18",
        open_price=10.0,
        close_price=10.5,
        high_price=10.8,
        low_price=9.9,
        pre_close=9.8,
        volume=1_000_000,
        amount=10_250_000,
        pct_chg=1.0,
    )


def test_black_litterman_optimizer_returns_research_weights() -> None:
    db = _db()
    for idx in range(1, 13):
        db.add(BacktestTrade(run_id=1, trade_date=f"2026-04-{idx:02d}", symbol=f"600{idx:03d}", side="sell", strategy_key="first_board", pnl_pct=1.0))
        db.add(BacktestTrade(run_id=1, trade_date=f"2026-04-{idx:02d}", symbol=f"000{idx:03d}", side="sell", strategy_key="volume_shrink", pnl_pct=0.5))
    db.commit()

    result = optimize_black_litterman_portfolio(db, run_id=1, monte_carlo_samples=32)

    assert result["method"] == "black_litterman"
    assert result["weights"]
    assert result["efficient_frontier"]
    assert result["summary"].startswith("研究用途")


def test_twap_and_implementation_shortfall_execution_models_fill_with_costs() -> None:
    broker = BacktestBroker()

    twap = broker.execute(ExecutionRequest(trade_date="2026-05-18", symbol="600000", side="buy", quantity=100, bar=_bar(), execution_model="twap"))
    shortfall = broker.execute(
        ExecutionRequest(trade_date="2026-05-18", symbol="600000", side="buy", quantity=100, bar=_bar(), execution_model="implementation_shortfall")
    )

    assert twap.status == "filled"
    assert twap.execution_model == "twap"
    assert shortfall.status == "filled"
    assert shortfall.execution_model == "implementation_shortfall"
    assert shortfall.requested_price is not None and shortfall.requested_price >= twap.requested_price


def test_position_sizer_applies_kelly_atr_and_portfolio_caps() -> None:
    candidate = AdmissionResult(
        passed=True,
        symbol="600000",
        priority_score=90,
        reason="通过",
        signal={
            "symbol": "600000",
            "name": "浦发银行",
            "latest_price": 10.0,
            "strategy_key": "first_board",
            "volatility_position_pct": 6.0,
            "portfolio_weight_scale": 0.5,
        },
        kelly_position=KellyPosition(
            full_kelly=0.16,
            half_kelly=0.08,
            quarter_kelly=0.04,
            win_rate=0.58,
            avg_win_pct=2.0,
            avg_loss_pct=-1.0,
            expected_value=0.74,
        ),
    )

    orders = PositionSizer(max_position_pct=0.2, max_cash_pct=1.0).calculate(
        candidates=[candidate],
        total_assets=100_000,
        available_cash=100_000,
        max_orders=1,
    )

    assert orders[0].quantity == 600
    assert orders[0].signal_snapshot["position_cap_source"] == "volatility_atr"
    assert orders[0].signal_snapshot["kelly_position_text"]


def test_live_backtest_comparison_flags_degraded_strategy() -> None:
    db = _db()
    account = PaperAccount(user_id=1, initial_cash=Decimal("100000"), total_assets=Decimal("100000"))
    db.add(account)
    db.flush()
    db.add(BacktestRun(id=1, owner_user_id=1, status="succeeded", name="recent"))
    for idx in range(4):
        db.add(BacktestTrade(run_id=1, trade_date=f"2026-05-{idx + 1:02d}", symbol=f"600{idx:03d}", side="sell", strategy_key="first_board", pnl_pct=2.0))
        db.add(PaperTrade(order_id=idx + 1, account_id=account.id, symbol=f"600{idx:03d}", side="buy", price=Decimal("10"), quantity=100, gross_amount=Decimal("1000"), net_amount=Decimal("1000"), strategy_key="first_board"))
        db.add(PaperTrade(order_id=idx + 11, account_id=account.id, symbol=f"600{idx:03d}", side="sell", price=Decimal("9.8"), quantity=100, gross_amount=Decimal("980"), net_amount=Decimal("980"), strategy_key="first_board"))
    db.commit()

    result = build_live_backtest_comparison(db, user_id=1, account_id=account.id, days=365, min_trades=3)

    item = result["items"][0]
    assert item["status"] == "degraded"
    assert result["alerts"]


def test_alternative_sentiment_and_arbitrage_are_research_only() -> None:
    db = _db()
    db.add(MarketEventCache(symbol="600000", title="公司公告回购并获得大额订单", source="news", risk_level="low"))
    db.commit()

    sentiment = AlternativeDataSentimentService(db).build(symbols=["600000"])
    arbitrage = build_multi_exchange_arbitrage_research(["600000"])

    assert sentiment["items"][0]["sentiment_label"] == "positive"
    assert sentiment["mode"] == "research_only"
    assert arbitrage["production_enabled"] is False
    assert arbitrage["tradable"] is False
