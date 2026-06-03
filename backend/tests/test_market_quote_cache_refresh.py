from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.entities import (
    DailyBarSnapshot,
    Instrument,
    LowBuyResultSnapshot,
    LowBuyScanSnapshot,
    PaperAccount,
    PaperPosition,
    StrategyTrackingSnapshot,
    User,
    UserWatchlist,
)
from app.models.schemas import QuoteSnapshot
import app.services.market_quote_cache_refresh as quote_refresh_module
from app.services.market_quote_cache_refresh import MarketQuoteCacheRefreshService
from app.services.market.local_quote_cache import (
    local_quote_cache_metrics_snapshot,
    record_quote_cache_demand_coverage,
    reset_local_quote_cache_metrics,
)
from app.services.market_quote_cache_refresh import maybe_send_quote_cache_coverage_alert


def _quote(symbol: str, *, source_quality: str = "fresh") -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol=symbol,
        name=symbol,
        market="CN",
        instrument_type="stock",
        last_price=10.0,
        change_pct=1.0,
        change_amount=0.1,
        open_price=9.9,
        high_price=10.2,
        low_price=9.8,
        prev_close=9.9,
        volume=1000,
        amount=10000,
        timestamp="2026-05-29",
        data_source="test",
        source_quality=source_quality,
        data_quality=source_quality,
        is_stale=source_quality == "stale",
    )


def test_target_symbols_keeps_core_hot_read_demand_before_liquidity_tail() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    with Session() as db:
        db.add(User(username="quote-cache-user", password_hash="hash"))
        db.flush()
        db.add(UserWatchlist(user_id=1, symbol="000001", name="自选"))
        db.add(PaperAccount(id=1, user_id=1, name="模拟账户"))
        db.add(
            PaperPosition(
                account_id=1,
                symbol="000002",
                name="纸面持仓",
                quantity=100,
                available_quantity=100,
                cost_basis=Decimal("10.0000"),
            )
        )
        db.add(
            LowBuyScanSnapshot(
                latest_trade_date="2026-05-29",
                strategy_key="first_board",
                strategy_title="首板",
                as_of_date="2026-05-29 15:00:00",
                matched_count=1,
            )
        )
        db.add(
            LowBuyResultSnapshot(
                latest_trade_date="2026-05-29",
                strategy_key="first_board",
                symbol="000003",
                name="优先榜候选",
                score=90,
                buy_signal_state="buy_now",
                payload_json="{}",
            )
        )
        db.add(
            StrategyTrackingSnapshot(
                snapshot_key="range=30",
                as_of_date="2026-05-29",
                range_days=30,
                status="fresh",
                payload_json='{"items":[{"symbol":"000010"},{"symbol":"000011"},{"symbol":"bad"}]}',
            )
        )
        for symbol, sector, amount in [
            ("000004", "半导体", 9000),
            ("000005", "半导体", 8000),
            ("000006", "半导体", 7000),
            ("000007", "半导体", 6000),
            ("000008", "半导体", 5000),
            ("000009", "半导体", 4000),
            ("000010", "半导体", 3000),
            ("000011", "半导体", 2000),
            ("600001", "银行", 100000),
            ("600002", "银行", 99000),
        ]:
            db.add(Instrument(symbol=symbol, name=f"{sector}{symbol}", sector_name=sector))
            db.add(
                DailyBarSnapshot(
                    symbol=symbol,
                    trade_date="2026-05-29",
                    close_price=10,
                    pre_close=9.8,
                    amount=amount,
                    volume=1000,
                    pct_chg=1.0,
                )
            )
        db.commit()

        symbols = MarketQuoteCacheRefreshService(db)._target_symbols(limit=4)

    assert {
        "000001",
        "000002",
        "000003",
        "000004",
        "000005",
        "000006",
        "000007",
        "000008",
        "000009",
        "000010",
        "000011",
    }.issubset(set(symbols))


def test_refresh_coverage_uses_daily_fallback_and_read_back(monkeypatch) -> None:
    reset_local_quote_cache_metrics()
    service = MarketQuoteCacheRefreshService(db=None)  # type: ignore[arg-type]
    symbols = ["000001", "000002", "000003"]
    stored: dict[str, QuoteSnapshot] = {}

    monkeypatch.setattr(service, "_target_symbols", lambda limit: symbols)
    monkeypatch.setattr(
        service,
        "_fetch_realtime_quotes",
        lambda requested: {"000001": _quote("000001"), "000002": _quote("000002")},
    )
    monkeypatch.setattr(service, "_daily_fallback_quotes", lambda requested: {"000003": _quote("000003", source_quality="stale")})
    monkeypatch.setattr(
        quote_refresh_module,
        "write_local_quote_snapshots",
        lambda quotes: stored.update(quotes) or len(quotes),
    )
    monkeypatch.setattr(quote_refresh_module, "read_local_quote_snapshot", lambda symbol: stored.get(symbol))
    monkeypatch.setattr(
        quote_refresh_module,
        "maybe_send_quote_cache_coverage_alert",
        lambda coverage: {"ok": True, "sent": False, "reason": "test"},
    )

    result = service.refresh(limit=3)

    assert result["requested_count"] == 3
    assert result["count"] == 3
    assert result["cached_count"] == 3
    assert result["missing_count"] == 0
    assert result["coverage"]["coverage_ratio_bps"] == 10000
    assert result["coverage"]["coverage_below_target"] is False


def test_refresh_coverage_reflects_actual_cache_read_back(monkeypatch) -> None:
    reset_local_quote_cache_metrics()
    service = MarketQuoteCacheRefreshService(db=None)  # type: ignore[arg-type]
    symbols = ["000001", "000002", "000003"]
    stored: dict[str, QuoteSnapshot] = {}

    monkeypatch.setattr(service, "_target_symbols", lambda limit: symbols)
    monkeypatch.setattr(
        service,
        "_fetch_realtime_quotes",
        lambda requested: {symbol: _quote(symbol) for symbol in symbols},
    )
    monkeypatch.setattr(service, "_daily_fallback_quotes", lambda requested: {})

    def write_without_third(quotes: dict[str, QuoteSnapshot]) -> int:
        stored.update({symbol: quote for symbol, quote in quotes.items() if symbol != "000003"})
        return len(stored)

    monkeypatch.setattr(quote_refresh_module, "write_local_quote_snapshots", write_without_third)
    monkeypatch.setattr(quote_refresh_module, "read_local_quote_snapshot", lambda symbol: stored.get(symbol))
    monkeypatch.setattr(
        quote_refresh_module,
        "maybe_send_quote_cache_coverage_alert",
        lambda coverage: {"ok": True, "sent": False, "reason": "test"},
    )

    result = service.refresh(limit=3)

    assert result["count"] == 3
    assert result["redis_written"] == 2
    assert result["cached_count"] == 2
    assert result["missing_count"] == 1
    assert result["coverage"]["coverage_ratio_bps"] == 6667
    assert result["coverage"]["coverage_below_target"] is True
    assert result["coverage"]["missing_symbols_sample"] == ["000003"]


def test_quote_cache_demand_coverage_marks_below_target_alert() -> None:
    reset_local_quote_cache_metrics()

    coverage = record_quote_cache_demand_coverage(
        requested_symbols=["000001", "000002", "000003", "000004"],
        cached_symbols=["000001"],
        target_ratio=0.9,
    )

    assert coverage["demand_count"] == 4
    assert coverage["covered_count"] == 1
    assert coverage["demand_miss_count"] == 3
    assert coverage["coverage_below_target"] is True
    assert coverage["alert_code"] == "quote_cache_coverage_below_target"
    metrics = local_quote_cache_metrics_snapshot()
    assert metrics["coverage_demand_total"] == 4
    assert metrics["coverage_demand_miss_total"] == 3
    assert metrics["coverage_ratio_bps"] == 2500


def test_quote_cache_coverage_alert_skips_without_notification_channel(monkeypatch) -> None:
    class StubNotificationService:
        def supports_channel(self, channel: str = "feishu") -> bool:
            return False

    monkeypatch.setattr(
        "app.services.market_quote_cache_refresh.AgentNotificationService",
        StubNotificationService,
    )

    result = maybe_send_quote_cache_coverage_alert(
        {
            "coverage_below_target": True,
            "coverage_ratio": 0.25,
            "demand_count": 4,
            "demand_miss_count": 3,
            "missing_symbols_sample": ["000002", "000003", "000004"],
        }
    )

    assert result == {"ok": True, "sent": False, "reason": "notification_channel_not_configured"}
