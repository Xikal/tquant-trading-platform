from __future__ import annotations

from types import SimpleNamespace
import threading
import time

from redis.exceptions import RedisError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import DailyBarSnapshot, Instrument, SystemSetting
from app.services import daily_bar_refresh as refresh_module
from app.services.daily_bar_refresh import DailyBarRefreshService
from app.services.daily_bar_refresh_checkpoint import DailyBarRefreshCheckpoint, DailyBarRefreshCheckpointStore
from app.services.market.local_quote_cache import _increment, local_quote_cache_metrics_snapshot
from app.services.shared import distributed_cache
from app.services.shared import distributed_cache_state


def test_local_quote_cache_metrics_increment_is_thread_safe() -> None:
    before = int(local_quote_cache_metrics_snapshot().get("reads") or 0)

    def worker() -> None:
        for _ in range(200):
            _increment("reads")

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    after = int(local_quote_cache_metrics_snapshot().get("reads") or 0)
    assert after - before == 1600


def test_distributed_cache_unhealthy_marker_forces_short_recheck_window() -> None:
    distributed_cache_state.clear_distributed_cache_client_state()
    assert distributed_cache_state._HEALTHY_TTL_SECONDS == 60.0
    distributed_cache_state.mark_distributed_cache_unhealthy()
    assert distributed_cache_state._CLIENT is None
    assert distributed_cache_state._HEALTHY_UNTIL == 0.0
    assert distributed_cache_state._FAILED_UNTIL == 0.0


def test_distributed_cache_read_failure_resets_cached_health() -> None:
    distributed_cache_state.clear_distributed_cache_client_state()
    with distributed_cache_state._LOCK:
        distributed_cache_state._CLIENT = _FailingRedisClient()
        distributed_cache_state._HEALTHY_UNTIL = time.monotonic() + 60

    assert distributed_cache.get_text_cache("broken") is None
    assert distributed_cache_state._CLIENT is None
    assert distributed_cache_state._HEALTHY_UNTIL == 0.0


def test_daily_bar_refresh_resumes_from_checkpoint_and_prioritizes_liquid_symbols(monkeypatch) -> None:
    Session = _session_factory()
    with Session() as db:
        _seed_instruments(db)
        checkpoint_store = DailyBarRefreshCheckpointStore(db)
        checkpoint_store.save(
            DailyBarRefreshCheckpoint(
                trade_date="2026-05-13",
                limit=3,
                chunk_size=1,
                total_chunks=3,
                last_chunk_index=0,
                updated=1,
                skipped=0,
            )
        )
        db.commit()

        monkeypatch.setattr(refresh_module, "expected_low_buy_trade_date", lambda _: "2026-05-13")
        service = DailyBarRefreshService(db)
        fake_market = _FakeMarket()
        service.market = fake_market

        result = service.refresh_latest(limit=3, chunk_size=1)

        assert result["resumed"] is True
        assert result["updated"] == 3
        assert fake_market.calls == [["600003"], ["600001"]]
        stored = db.query(SystemSetting).filter(SystemSetting.key == "bar_refresh_checkpoint").one()
        assert '"status": "completed"' in stored.value


def test_daily_bar_refresh_reports_insufficient_daily_bars(monkeypatch) -> None:
    Session = _session_factory()
    with Session() as db:
        _seed_instruments(db)
        monkeypatch.setattr(refresh_module, "expected_low_buy_trade_date", lambda _: "2026-06-03")
        service = DailyBarRefreshService(db)
        service.market = _FakeMarket()

        result = service.refresh_latest(limit=3, chunk_size=2, expected_trade_date="2026-06-03")

        assert result["ok"] is False
        assert result["status"] == "insufficient_daily_bars"
        assert result["trade_date"] == "2026-06-03"
        assert result["daily_bar_count"] < result["min_daily_bar_count"]


def test_daily_bar_refresh_retries_completed_checkpoint_when_daily_bars_insufficient(monkeypatch) -> None:
    Session = _session_factory()
    with Session() as db:
        _seed_instruments(db)
        checkpoint_store = DailyBarRefreshCheckpointStore(db)
        checkpoint_store.save(
            DailyBarRefreshCheckpoint(
                trade_date="2026-06-03",
                limit=3,
                chunk_size=2,
                total_chunks=2,
                last_chunk_index=1,
                updated=3,
                skipped=0,
                status="completed",
            )
        )
        db.commit()
        monkeypatch.setattr(refresh_module, "expected_low_buy_trade_date", lambda _: "2026-06-03")
        service = DailyBarRefreshService(db)
        fake_market = _FakeMarket()
        service.market = fake_market

        result = service.refresh_latest(limit=3, chunk_size=2, expected_trade_date="2026-06-03")

        assert result["status"] == "insufficient_daily_bars"
        assert result["resumed"] is False
        assert fake_market.calls == [["600002", "600003"], ["600001"]]


def _session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def _seed_instruments(db) -> None:  # noqa: ANN001
    for symbol in ("600001", "600002", "600003"):
        db.add(Instrument(symbol=symbol, name=symbol, instrument_type="stock"))
    amounts = {"600001": 100.0, "600002": 500.0, "600003": 300.0}
    for symbol, amount in amounts.items():
        db.add(
            DailyBarSnapshot(
                symbol=symbol,
                trade_date="2026-05-12",
                open_price=10.0,
                high_price=10.2,
                low_price=9.8,
                close_price=10.1,
                volume=1000.0,
                amount=amount,
                pct_chg=1.0,
            )
        )
    db.commit()


class _FakeMarket:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def get_quotes_batch(self, symbols, **_) -> dict[str, SimpleNamespace]:  # noqa: ANN001
        chunk = list(symbols)
        self.calls.append(chunk)
        return {
            symbol: SimpleNamespace(
                symbol=symbol,
                last_price=10.0,
                open_price=9.9,
                high_price=10.2,
                low_price=9.8,
                volume=1000.0,
                amount=1_000_000.0,
                change_pct=1.0,
            )
            for symbol in chunk
        }


class _FailingRedisClient:
    def get(self, key: str) -> None:  # noqa: ARG002
        raise RedisError("redis down")
