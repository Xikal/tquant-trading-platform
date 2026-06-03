from __future__ import annotations

from datetime import date

from app.models.entities import DailyBarSnapshot, Instrument
from app.services.trading_experience.relative_strength import build_board
from backend.tests.trading_experience_fixtures import seed_daily_bars, session_factory


def test_relative_strength_board_outputs_fact_metrics_only() -> None:
    Session = session_factory()
    db = Session()
    seed_daily_bars(db, "600000", pct=2.0, sector="银行")
    seed_daily_bars(db, "600001", pct=-5.0, sector="银行")
    db.add(Instrument(symbol="600002", name="抗跌股", instrument_type="stock", sector_name="科技", status="active"))
    db.add(
        DailyBarSnapshot(
            symbol="600002",
            trade_date=date(2026, 5, 27),
            instrument_type="stock",
            open_price=10,
            close_price=10.1,
            high_price=10.2,
            low_price=9.9,
            volume=1000,
            amount=10000,
            pct_chg=0.5,
            pre_close=10,
            data_quality="ok",
        )
    )
    db.commit()

    items = build_board(db, trade_date=date(2026, 5, 27), limit=5)

    assert items
    assert items[0].rs_vs_index is not None
    assert all(item.resilience_flag in {"resilient", "follow_down", "neutral"} for item in items)
