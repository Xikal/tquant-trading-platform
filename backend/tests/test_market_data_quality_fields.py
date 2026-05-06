from __future__ import annotations

from app.models.schemas import QuoteSnapshot
from app.services.market.providers.quality import MarketDataQuality


def test_market_data_quality_values_are_frontend_safe() -> None:
    assert [item.value for item in MarketDataQuality] == [
        "fresh",
        "stale",
        "estimated",
        "unavailable",
    ]


def test_quote_snapshot_has_default_data_quality_fields() -> None:
    quote = QuoteSnapshot(
        symbol="510300",
        name="沪深300ETF",
        market="SH",
        instrument_type="etf",
        last_price=4.0,
        change_pct=0.0,
        change_amount=0.0,
        open_price=4.0,
        high_price=4.0,
        low_price=4.0,
        prev_close=4.0,
        volume=0.0,
        amount=0.0,
        timestamp="2026-05-06 15:00:00",
    )

    assert quote.data_quality == "fresh"
    assert quote.data_quality_message == ""
