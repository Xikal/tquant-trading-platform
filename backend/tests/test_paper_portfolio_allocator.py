from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.services.paper.performance import SellReturnRecord
from app.services.paper.portfolio_allocator import PaperStrategyPortfolioAllocator
from app.services.paper.sizing import PositionSizer


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def _records(days: int = 60) -> list[SellReturnRecord]:
    start = datetime(2026, 1, 1, 14, 30)
    rows: list[SellReturnRecord] = []
    for index in range(days):
        trade_time = start + timedelta(days=index)
        rows.append(
            SellReturnRecord(
                trade_id=index * 2 + 1,
                return_pct=1.0 + (index % 5) * 0.2,
                strategy_key="first_board",
                market_state="repair",
                trade_time=trade_time,
            )
        )
        rows.append(
            SellReturnRecord(
                trade_id=index * 2 + 2,
                return_pct=0.7 + (index % 5) * 0.15,
                strategy_key="volume_shrink",
                market_state="repair",
                trade_time=trade_time,
            )
        )
    return rows


def test_allocator_requires_enough_closed_trades(monkeypatch) -> None:
    db = _db()
    monkeypatch.setattr(
        "app.services.paper.portfolio_allocator.PaperPerformanceService.sell_return_records",
        lambda self, account_id: _records(days=20),
    )

    result = PaperStrategyPortfolioAllocator(db).build_strategy_scales(account_id=1)

    assert result == {}


def test_allocator_builds_scales_and_position_sizer_applies_them(monkeypatch) -> None:
    db = _db()
    monkeypatch.setattr(
        "app.services.paper.portfolio_allocator.PaperPerformanceService.sell_return_records",
        lambda self, account_id: _records(days=60),
    )

    decisions = PaperStrategyPortfolioAllocator(db).build_strategy_scales(account_id=1)

    assert "first_board" in decisions
    assert "volume_shrink" in decisions
    candidate = type(
        "Candidate",
        (),
        {
            "symbol": "510300",
            "name": "300ETF",
            "priority_score": 92,
            "signal": {
                "symbol": "510300",
                "name": "300ETF",
                "latest_price": 10,
                "strategy_key": "volume_shrink",
                "buy_signal_state": "buy_now",
                "portfolio_weight_scale": float(decisions["volume_shrink"].scale),
                "portfolio_weight_reason": decisions["volume_shrink"].reason,
            },
            "kelly_position": None,
        },
    )()

    sized = PositionSizer(max_position_pct=0.10, max_cash_pct=1.0).calculate(
        candidates=[candidate],
        total_assets=100000,
        available_cash=100000,
        max_orders=1,
    )

    assert len(sized) == 1
    assert sized[0].signal_snapshot["position_cap_source"] == "portfolio_markowitz"
    assert sized[0].quantity <= 1000
