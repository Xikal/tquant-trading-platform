from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from app.services import latest_data_close_refresh as close_refresh
from app.runtime import background_jobs


class _FakeRepo:
    count = 0

    def __init__(self, _db) -> None:
        pass

    def stock_count_by_trade_date(self, _trade_date: str) -> int:
        return self.count


class _FakeQueue:
    last_payload = None

    def __init__(self, _db) -> None:
        pass

    def enqueue(self, payload):
        self.__class__.last_payload = payload
        return SimpleNamespace(id=7, status="queued")


def _patch_base(monkeypatch, *, expected: str = "2026-05-18") -> None:
    monkeypatch.setattr(close_refresh, "is_a_share_trading_day", lambda _date: True)
    monkeypatch.setattr(close_refresh, "expected_low_buy_trade_date", lambda _db: expected)
    monkeypatch.setattr(close_refresh, "DailyHistoryRepository", _FakeRepo)
    monkeypatch.setattr(close_refresh, "RuntimeTaskQueue", _FakeQueue)


def test_after_close_enqueues_daily_bar_refresh_when_daily_bars_missing(monkeypatch) -> None:
    _patch_base(monkeypatch)
    _FakeRepo.count = 0
    _FakeQueue.last_payload = None

    result = close_refresh.enqueue_latest_data_close_refresh(
        object(),
        now=datetime(2026, 5, 18, 15, 2),
        strategies=["first_board"],
    )

    assert result["action"] == "enqueue_daily_bar_refresh"
    assert result["task_status"] == "queued"
    assert _FakeQueue.last_payload.task_type == "daily_bar_refresh"
    assert _FakeQueue.last_payload.idempotency_key == "daily_bar_refresh:2026-05-18"


def test_after_close_enqueues_materialization_when_strategy_snapshots_missing(monkeypatch) -> None:
    _patch_base(monkeypatch)
    _FakeRepo.count = close_refresh.MIN_STOCK_DAILY_BARS
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        close_refresh,
        "latest_data_status",
        lambda _db, strategies: {"missing_strategies": ["volume_shrink"]},
    )
    monkeypatch.setattr(
        close_refresh,
        "enqueue_low_buy_materialization",
        lambda _db, **kwargs: captured.update(kwargs),
    )

    result = close_refresh.enqueue_latest_data_close_refresh(
        object(),
        now=datetime(2026, 5, 18, 15, 2),
        strategies=["volume_shrink"],
    )

    assert result["action"] == "enqueue_low_buy_materialization"
    assert result["missing_strategies"] == ["volume_shrink"]
    assert captured["reason"] == "after_close_latest_data"
    assert captured["commit"] is True


def test_after_close_publishes_when_latest_data_is_complete(monkeypatch) -> None:
    _patch_base(monkeypatch)
    _FakeRepo.count = close_refresh.MIN_STOCK_DAILY_BARS
    _FakeQueue.last_payload = None
    monkeypatch.setattr(close_refresh, "latest_data_status", lambda _db, strategies: {"missing_strategies": []})
    monkeypatch.setattr(
        close_refresh,
        "publish_latest_trade_date_if_ready",
        lambda _db, strategies: {"status": "success", "published_trade_date": "2026-05-18"},
    )
    db = SimpleNamespace(committed=False, commit=lambda: setattr(db, "committed", True))

    result = close_refresh.enqueue_latest_data_close_refresh(
        db,
        now=datetime(2026, 5, 18, 15, 2),
        strategies=["volume_shrink"],
    )

    assert result["ok"] is True
    assert result["action"] == "publish_latest_trade_date"
    assert result["strategy_tracking_snapshot_task_status"] == "queued"
    assert _FakeQueue.last_payload.task_type == "strategy_tracking_snapshot_refresh"
    assert _FakeQueue.last_payload.payload["range_days"] == 30
    assert db.committed is True


def test_after_close_skips_when_already_published(monkeypatch) -> None:
    _patch_base(monkeypatch)
    _FakeRepo.count = close_refresh.MIN_STOCK_DAILY_BARS
    _FakeQueue.last_payload = None
    monkeypatch.setattr(
        close_refresh,
        "latest_data_status",
        lambda _db, strategies: {
            "status": "success",
            "published_trade_date": "2026-05-18",
            "missing_strategies": [],
        },
    )
    monkeypatch.setattr(
        close_refresh,
        "publish_latest_trade_date_if_ready",
        lambda _db, strategies: (_ for _ in ()).throw(AssertionError("should not republish")),
    )

    result = close_refresh.enqueue_latest_data_close_refresh(
        object(),
        now=datetime(2026, 5, 18, 15, 2),
        strategies=["volume_shrink"],
    )

    assert result["ok"] is True
    assert result["action"] == "already_latest"
    assert result["strategy_tracking_snapshot_task_status"] == "queued"
    assert _FakeQueue.last_payload.task_type == "strategy_tracking_snapshot_refresh"
    assert _FakeQueue.last_payload.payload["reason"] == "after_close_latest_data_already_latest"


def test_before_close_skips_without_touching_queue(monkeypatch) -> None:
    _patch_base(monkeypatch)
    _FakeQueue.last_payload = None

    result = close_refresh.enqueue_latest_data_close_refresh(
        object(),
        now=datetime(2026, 5, 18, 14, 59),
        strategies=["first_board"],
    )

    assert result["action"] == "skip_before_close"
    assert _FakeQueue.last_payload is None


def test_latest_data_watchdog_enqueue_skips_when_same_trade_date_already_notified(monkeypatch) -> None:
    captured = []

    class _Queue:
        def __init__(self, _db) -> None:
            pass

        def enqueue(self, payload):
            captured.append(payload)
            return SimpleNamespace(id=9, status="queued")

    class _Repo:
        def __init__(self, _db) -> None:
            pass

        def already_notified(self, *, trade_date: str, channel: str = "feishu") -> bool:
            assert trade_date == "2026-05-18"
            assert channel == "feishu"
            return True

    monkeypatch.setattr(background_jobs, "_latest_data_watchdog_due", lambda: True)
    monkeypatch.setattr(background_jobs, "expected_low_buy_trade_date", lambda _db: "2026-05-18")
    monkeypatch.setattr(background_jobs, "LatestDataWatchdogLedger", _Repo)
    monkeypatch.setattr(background_jobs, "RuntimeTaskQueue", _Queue)
    monkeypatch.setattr(background_jobs, "SessionLocal", lambda: _ContextDb())

    background_jobs._enqueue_latest_data_watchdog_once()

    assert captured == []


class _ContextDb:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False
