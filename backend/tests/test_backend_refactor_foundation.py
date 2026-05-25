from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import Date, Numeric, create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import AppSettings
from app.models.base import Base
from app.models.entities import DailyBarSnapshot, MinuteBarSnapshot, PaperAccount, PaperPosition, PaperPositionLot
from app.models.schemas import KlineBar, QuoteSnapshot
from app.services.finance import rust_math
from app.services.low_buy import go_scan_shadow
from app.services.market import go_read_client
from app.services.market.minute_bar_store import MinuteBarSnapshotStore, parse_minute_trade_date
from app.services.paper.position import PaperPositionService


def test_backend_refactor_settings_expose_pool_and_bff_cache_controls() -> None:
    settings = AppSettings(
        database_url="mysql+pymysql://user:pass@localhost/db",
        auth_secret_key="x" * 64,
        tquant_settings_encryption_key="y" * 64,
        db_pool_size=5,
        db_max_overflow=7,
        db_pool_timeout=11,
        db_pool_recycle=120,
        bff_workspace_cache_enabled=True,
        bff_monitor_cache_ttl_seconds=9,
    )

    assert settings.db_pool_size == 5
    assert settings.db_max_overflow == 7
    assert settings.db_pool_timeout == 11
    assert settings.db_pool_recycle == 120
    assert settings.bff_workspace_cache_enabled is True
    assert settings.bff_monitor_cache_ttl_seconds == 9
    assert settings.tquant_bff_gateway_url == ""
    assert settings.tquant_bff_shadow_enabled is False
    assert settings.tquant_market_read_service_url == ""
    assert settings.tquant_go_scan_worker_url == ""
    assert settings.tquant_go_scan_shadow_enabled is False


def test_daily_bar_snapshot_uses_date_and_numeric_ohlcv_types() -> None:
    columns = DailyBarSnapshot.__table__.c

    assert isinstance(columns.trade_date.type.impl, Date)
    for name in ("open_price", "close_price", "high_price", "low_price", "volume", "amount"):
        assert isinstance(columns[name].type, Numeric)


def test_minute_bar_snapshot_has_trade_date_partition_key() -> None:
    columns = MinuteBarSnapshot.__table__.c

    assert isinstance(columns.trade_date.type.impl, Date)


def test_minute_bar_store_persists_trade_date_for_timeseries_queries() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    quote = QuoteSnapshot(
        symbol="510300",
        name="沪深300ETF",
        market="SH",
        instrument_type="etf",
        last_price=3.5,
        change_pct=0.8,
        change_amount=0.03,
        open_price=3.48,
        high_price=3.53,
        low_price=3.47,
        prev_close=3.47,
        volume=2200,
        amount=7724,
        timestamp="2026-05-24 10:31:00",
    )
    bars = [
        KlineBar(timestamp="2026-05-24 10:30", open=3.48, close=3.5, high=3.51, low=3.47, volume=1000, amount=3500),
        KlineBar(timestamp="2026-05-24 10:31", open=3.5, close=3.52, high=3.53, low=3.49, volume=1200, amount=4224),
    ]

    with Session() as db:
        persisted = MinuteBarSnapshotStore(db).persist(quote, bars)
        rows = MinuteBarSnapshotStore(db).list_bars(
            symbol="510300",
            trade_date=date(2026, 5, 24),
            limit=10,
        )

    assert persisted == 2
    assert [row.bar_timestamp for row in rows] == ["2026-05-24 10:31", "2026-05-24 10:30"]
    assert rows[0].trade_date == date(2026, 5, 24)
    assert parse_minute_trade_date("202605241031") == date(2026, 5, 24)


def test_paper_positions_eager_load_lots_without_n_plus_one() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    query_count = 0

    @event.listens_for(engine, "before_cursor_execute")
    def _count_queries(*args, **kwargs):
        nonlocal query_count
        query_count += 1

    with Session() as db:
        account = PaperAccount(name="test", initial_cash=Decimal("100000.00"), cash_available=Decimal("100000.00"))
        db.add(account)
        db.flush()
        for index in range(25):
            symbol = f"600{index:03d}"
            position = PaperPosition(
                account_id=account.id,
                symbol=symbol,
                name=symbol,
                quantity=100,
                available_quantity=100,
                cost_basis=Decimal("10.0000"),
            )
            db.add(position)
            db.flush()
            db.add(
                PaperPositionLot(
                    account_id=account.id,
                    position_id=position.id,
                    symbol=symbol,
                    quantity=100,
                    remaining=100,
                    available_date=date(2026, 5, 20),
                    cost_price=Decimal("10.0000"),
                )
            )
        db.commit()

    query_count = 0
    with Session() as db:
        rows = PaperPositionService(db).get_positions(1)
        assert len(rows) == 25
        assert sum(len(row.lots) for row in rows) == 25

    assert query_count <= 6


def test_optional_rust_math_is_disabled_by_default() -> None:
    assert rust_math.rust_available() is False
    assert rust_math.rust_max_drawdown([100.0, 90.0, 110.0]) is None
    assert rust_math.rust_rolling_mean([1.0, 2.0, 3.0], 2) is None
    assert rust_math.rust_atr_wilder([1.0], [1.0], [1.0], 14) is None


def test_go_market_read_client_is_disabled_without_url(monkeypatch) -> None:
    called = False

    def fake_remote(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(go_read_client, "remote_bff_get", fake_remote)
    monkeypatch.setattr(go_read_client, "get_settings", lambda: SimpleNamespace(tquant_market_read_service_url=""))

    assert go_read_client.load_go_market_read_quotes(["000001"]) == {}
    assert called is False


def test_go_market_read_client_parses_quote_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        go_read_client,
        "get_settings",
        lambda: SimpleNamespace(tquant_market_read_service_url="http://go-market-read-service:8092"),
    )
    monkeypatch.setattr(
        go_read_client,
        "remote_bff_get",
        lambda *args, **kwargs: {
            "items": [
                {
                    "data_quality": "fresh",
                    "quote": {
                        "symbol": "000001",
                        "name": "平安银行",
                        "market": "SZ",
                        "instrument_type": "stock",
                        "last_price": 10.1,
                        "change_pct": 1.2,
                        "change_amount": 0.12,
                        "open_price": 10.0,
                        "high_price": 10.2,
                        "low_price": 9.9,
                        "prev_close": 9.98,
                        "volume": 1000,
                        "amount": 10100,
                        "timestamp": "2026-05-23 10:00:00",
                    },
                }
            ]
        },
    )

    result = go_read_client.load_go_market_read_quotes(["000001"])

    assert result["000001"].last_price == 10.1
    assert result["000001"].data_source == "go_market_read_service"


def test_go_scan_shadow_is_disabled_without_config(monkeypatch) -> None:
    called = False

    def fake_remote(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(go_scan_shadow, "remote_bff_get", fake_remote)
    monkeypatch.setattr(
        go_scan_shadow,
        "get_settings",
        lambda: SimpleNamespace(tquant_go_scan_worker_url="", tquant_go_scan_shadow_enabled=False),
    )

    result = go_scan_shadow.trigger_go_scan_shadow(strategies=["first_board"], scan_limit=12, reason="test")

    assert result == {"enabled": False, "triggered": 0, "failed": 0}
    assert called is False


def test_go_scan_shadow_triggers_each_strategy(monkeypatch) -> None:
    calls = []

    def fake_remote(base_url, path, *, params=None, **kwargs):
        calls.append((base_url, path, params))
        return {"ok": True}

    monkeypatch.setattr(go_scan_shadow, "remote_bff_get", fake_remote)
    monkeypatch.setattr(
        go_scan_shadow,
        "get_settings",
        lambda: SimpleNamespace(
            tquant_go_scan_worker_url="http://go-scan-worker:8093",
            tquant_go_scan_shadow_enabled=True,
        ),
    )

    result = go_scan_shadow.trigger_go_scan_shadow(
        strategies=["volume_shrink", "first_board", "first_board"],
        scan_limit=72,
        reason="test",
    )

    assert result == {"enabled": True, "triggered": 2, "failed": 0}
    assert [item[2]["strategy"] for item in calls] == ["first_board", "volume_shrink"]
    assert calls[0][0] == "http://go-scan-worker:8093"
    assert calls[0][1] == "/api/scan-worker/v1/shadow/run"
