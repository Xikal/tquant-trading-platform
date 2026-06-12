from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import RuntimeTask
from app.services import low_buy_materialization
from app.services import latest_data_close_refresh as close_refresh
from app.runtime import background_jobs


class _FakeRepo:
    count = 0
    post_close_count = 0

    def __init__(self, _db) -> None:
        pass

    def stock_count_by_trade_date(self, _trade_date: str) -> int:
        return self.count


class _FakeQueue:
    last_payload = None
    payloads = []

    def __init__(self, _db) -> None:
        pass

    def enqueue(self, payload):
        self.__class__.last_payload = payload
        self.__class__.payloads.append(payload)
        return SimpleNamespace(id=7, status="queued")


def _patch_base(monkeypatch, *, expected: str = "2026-05-18") -> None:
    monkeypatch.setattr(close_refresh, "is_a_share_trading_day", lambda _date: True)
    monkeypatch.setattr(close_refresh, "expected_low_buy_trade_date", lambda _db: expected)
    monkeypatch.setattr(close_refresh, "RuntimeTaskQueue", _FakeQueue)
    monkeypatch.setattr(close_refresh, "_market_review_exists", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(close_refresh, "_daily_bar_sla_exists", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(close_refresh, "_succeeded_task_exists", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        close_refresh,
        "daily_bar_freshness_status",
        lambda _db, trade_date: {
            "daily_bar_count": _FakeRepo.count,
            "post_close_daily_bar_count": _FakeRepo.post_close_count,
            "min_daily_bar_count": close_refresh.MIN_STOCK_DAILY_BARS,
            "daily_bar_freshness_status": "post_close_complete"
            if _FakeRepo.post_close_count >= close_refresh.MIN_STOCK_DAILY_BARS
            else "stale_before_post_close",
            "post_close_fetch_cutoff": f"{trade_date}T15:01:00",
            "latest_daily_bar_fetch_time": f"{trade_date}T13:51:11",
        },
    )


def _sqlite_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def test_after_close_enqueues_daily_bar_refresh_when_daily_bars_missing(monkeypatch) -> None:
    _patch_base(monkeypatch)
    _FakeRepo.count = 0
    _FakeRepo.post_close_count = 0
    _FakeQueue.last_payload = None
    _FakeQueue.payloads = []

    result = close_refresh.enqueue_latest_data_close_refresh(
        object(),
        now=datetime(2026, 5, 18, 15, 2),
        strategies=["first_board"],
    )

    assert result["action"] == "enqueue_daily_bar_refresh"
    assert result["task_status"] == "queued"
    assert _FakeQueue.last_payload.task_type == "daily_bar_refresh"
    assert _FakeQueue.last_payload.idempotency_key == "daily_bar_refresh:2026-05-18:after_close_latest_data"


def test_after_close_enqueues_daily_bar_refresh_when_only_before_close_fetch_exists(monkeypatch) -> None:
    _patch_base(monkeypatch)
    _FakeRepo.count = close_refresh.MIN_STOCK_DAILY_BARS
    _FakeRepo.post_close_count = 0
    _FakeQueue.last_payload = None
    _FakeQueue.payloads = []

    result = close_refresh.enqueue_latest_data_close_refresh(
        object(),
        now=datetime(2026, 5, 18, 15, 2),
        strategies=["first_board"],
    )

    assert result["action"] == "enqueue_daily_bar_refresh"
    assert result["daily_bar_count"] == close_refresh.MIN_STOCK_DAILY_BARS
    assert result["post_close_daily_bar_count"] == 0
    assert result["daily_bar_freshness_status"] == "stale_before_post_close"
    assert _FakeQueue.last_payload.task_type == "daily_bar_refresh"
    assert _FakeQueue.last_payload.payload["reason"] == "after_close_stale_fetch_time"
    assert _FakeQueue.last_payload.idempotency_key == "daily_bar_refresh:2026-05-18:after_close_stale_fetch_time"


def test_after_close_enqueues_materialization_when_strategy_snapshots_missing(monkeypatch) -> None:
    _patch_base(monkeypatch)
    _FakeRepo.count = close_refresh.MIN_STOCK_DAILY_BARS
    _FakeRepo.post_close_count = close_refresh.MIN_STOCK_DAILY_BARS
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
    _FakeRepo.post_close_count = close_refresh.MIN_STOCK_DAILY_BARS
    _FakeQueue.last_payload = None
    _FakeQueue.payloads = []
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
    followup_types = [item.task_type for item in _FakeQueue.payloads]
    assert "market_review_report" not in followup_types
    assert "paper_review_report" not in followup_types
    assert "data_quality_sla_refresh" in followup_types
    assert "low_buy_materialization_refresh" in followup_types
    close_review_payload = next(item.payload for item in _FakeQueue.payloads if item.payload.get("build_close_review"))
    assert close_review_payload["expected_trade_date"] == "2026-05-18"
    assert db.committed is True


def test_after_close_skips_when_already_published(monkeypatch) -> None:
    _patch_base(monkeypatch)
    _FakeRepo.count = close_refresh.MIN_STOCK_DAILY_BARS
    _FakeRepo.post_close_count = close_refresh.MIN_STOCK_DAILY_BARS
    _FakeQueue.last_payload = None
    _FakeQueue.payloads = []
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
    followup_types = [item.task_type for item in _FakeQueue.payloads]
    assert "data_quality_sla_refresh" in followup_types
    assert "low_buy_materialization_refresh" in followup_types


def test_after_close_skips_data_quality_sla_when_disabled(monkeypatch) -> None:
    _patch_base(monkeypatch)
    _FakeRepo.count = close_refresh.MIN_STOCK_DAILY_BARS
    _FakeRepo.post_close_count = close_refresh.MIN_STOCK_DAILY_BARS
    _FakeQueue.last_payload = None
    _FakeQueue.payloads = []
    monkeypatch.setattr(
        close_refresh,
        "settings",
        SimpleNamespace(data_quality_sla_enabled=False),
    )
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

    followup_types = [item.task_type for item in _FakeQueue.payloads]
    assert result["ok"] is True
    assert result["followups"]["data_quality_sla"] == {
        "action": "skipped_disabled",
        "trade_date": "2026-05-18",
        "dataset_key": "daily_bars",
    }
    assert "data_quality_sla_refresh" not in followup_types
    assert "low_buy_materialization_refresh" in followup_types
    assert "strategy_tracking_snapshot_refresh" in followup_types


def test_after_close_reuses_succeeded_core_tasks_without_requeue(monkeypatch) -> None:
    db = _sqlite_db()
    db.add(
        RuntimeTask(
            id=101,
            task_type=close_refresh.A_KEY_LEVEL_MATERIALIZATION_TASK,
            status="succeeded",
            idempotency_key="a_key_level_materialization_refresh:2026-05-18",
            payload_json='{"trade_date":"2026-05-18"}',
            result_json='{"ok":true}',
            priority=45,
            progress_pct=100,
            finished_at=datetime(2026, 5, 18, 15, 20),
        )
    )
    db.add(
        RuntimeTask(
            id=102,
            task_type=close_refresh.STRATEGY_TRACKING_SNAPSHOT_TASK,
            status="succeeded",
            idempotency_key="strategy_tracking_snapshot_refresh:2026-05-18:30",
            payload_json='{"range_days":30}',
            result_json='{"ok":true}',
            priority=35,
            progress_pct=100,
            finished_at=datetime(2026, 5, 18, 15, 21),
        )
    )
    db.commit()
    monkeypatch.setattr(close_refresh, "is_a_share_trading_day", lambda _date: True)
    monkeypatch.setattr(close_refresh, "expected_low_buy_trade_date", lambda _db: "2026-05-18")
    monkeypatch.setattr(
        close_refresh,
        "daily_bar_freshness_status",
        lambda _db, _trade_date: {
            "daily_bar_count": close_refresh.MIN_STOCK_DAILY_BARS,
            "post_close_daily_bar_count": close_refresh.MIN_STOCK_DAILY_BARS,
            "daily_bar_freshness_status": "post_close_complete",
        },
    )
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
        "enqueue_after_close_followups",
        lambda _db, **_kwargs: {"ok": True, "action": "stubbed_for_test"},
    )

    result = close_refresh.enqueue_latest_data_close_refresh(
        db,
        now=datetime(2026, 5, 18, 15, 30),
        strategies=["volume_shrink"],
    )

    assert result["action"] == "already_latest"
    assert result["a_key_level_materialization_task_id"] == 101
    assert result["a_key_level_materialization_task_status"] == "succeeded"
    assert result["strategy_tracking_snapshot_task_id"] == 102
    assert result["strategy_tracking_snapshot_task_status"] == "succeeded"
    assert db.query(RuntimeTask).count() == 2


def test_before_close_skips_without_touching_queue(monkeypatch) -> None:
    _patch_base(monkeypatch)
    _FakeQueue.last_payload = None
    _FakeQueue.payloads = []

    result = close_refresh.enqueue_latest_data_close_refresh(
        object(),
        now=datetime(2026, 5, 18, 14, 59),
        strategies=["first_board"],
    )

    assert result["action"] == "skip_before_close"
    assert result["metric"] == "latest_data_close_refresh.skip_before_close"
    assert _FakeQueue.last_payload is None


def test_non_trading_day_skips_with_specific_action(monkeypatch) -> None:
    _patch_base(monkeypatch)
    monkeypatch.setattr(close_refresh, "is_a_share_trading_day", lambda _date: False)
    _FakeQueue.last_payload = None
    _FakeQueue.payloads = []

    result = close_refresh.enqueue_latest_data_close_refresh(
        object(),
        now=datetime(2026, 6, 6, 15, 30),
        strategies=["first_board"],
    )

    assert result["action"] == "skip_non_trading_day"
    assert result["metric"] == "latest_data_close_refresh.skip_non_trading_day"
    assert _FakeQueue.last_payload is None


def test_after_close_enqueues_review_reports_after_review_time(monkeypatch) -> None:
    _patch_base(monkeypatch)
    _FakeRepo.count = close_refresh.MIN_STOCK_DAILY_BARS
    _FakeRepo.post_close_count = close_refresh.MIN_STOCK_DAILY_BARS
    _FakeQueue.last_payload = None
    _FakeQueue.payloads = []
    monkeypatch.setattr(
        close_refresh,
        "latest_data_status",
        lambda _db, strategies: {
            "status": "success",
            "published_trade_date": "2026-05-18",
            "missing_strategies": [],
        },
    )

    result = close_refresh.enqueue_latest_data_close_refresh(
        object(),
        now=datetime(2026, 5, 18, 15, 10),
        strategies=["volume_shrink"],
    )

    assert result["action"] == "already_latest"
    review_tasks = [(item.task_type, item.payload["report_slot"]) for item in _FakeQueue.payloads if "review_report" in item.task_type]
    assert review_tasks == [
        ("market_review_report", "midday"),
        ("market_review_report", "close"),
    ]


def test_after_close_followups_skip_reports_that_already_exist(monkeypatch) -> None:
    _patch_base(monkeypatch)
    _FakeQueue.last_payload = None
    _FakeQueue.payloads = []
    monkeypatch.setattr(close_refresh, "_market_review_exists", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(close_refresh, "_daily_bar_sla_exists", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(close_refresh, "_succeeded_task_exists", lambda *_args, **_kwargs: True)

    result = close_refresh.enqueue_after_close_followups(
        object(),
        trade_date="2026-05-18",
        now=datetime(2026, 5, 18, 15, 10),
        strategies=["first_board"],
    )

    assert [item["action"] for item in result["market_review"]] == ["exists", "exists"]
    assert "paper_review" not in result
    assert result["data_quality_sla"]["action"] == "exists"
    assert result["low_buy_close_review"]["action"] == "succeeded_task_exists"
    assert _FakeQueue.payloads == []


def test_after_close_followups_do_not_requeue_blocked_low_buy_snapshots() -> None:
    db = _sqlite_db()
    db.add(
        RuntimeTask(
            id=201,
            task_type=close_refresh.LOW_BUY_MATERIALIZATION_TASK,
            status="skipped",
            idempotency_key="low_buy_materialization_refresh:2026-05-18:close_review:first_board",
            payload_json='{"expected_trade_date":"2026-05-18","strategies":["first_board"]}',
            result_json=(
                '{"ok":true,"skipped":true,'
                '"status":"blocked_missing_required_snapshots",'
                '"reason":"missing_required_strategy_snapshots",'
                '"missing_required_strategies":["first_board"]}'
            ),
            priority=24,
            progress_pct=100,
            finished_at=datetime(2026, 5, 18, 15, 20),
        )
    )
    db.commit()
    _FakeQueue.last_payload = None
    _FakeQueue.payloads = []

    result = close_refresh.enqueue_after_close_followups(
        db,
        trade_date="2026-05-18",
        now=datetime(2026, 5, 18, 15, 30),
        strategies=["first_board"],
    )

    assert result["low_buy_close_review"] == {
        "action": "blocked_missing_required_snapshots",
        "trade_date": "2026-05-18",
        "strategies": ["first_board"],
        "task_id": 201,
    }
    assert "low_buy_materialization_refresh" not in [item.task_type for item in _FakeQueue.payloads]


def test_low_buy_materialization_enqueue_reuses_blocked_trade_date_task(monkeypatch) -> None:
    db = _sqlite_db()
    db.add(
        RuntimeTask(
            id=202,
            task_type=close_refresh.LOW_BUY_MATERIALIZATION_TASK,
            status="skipped",
            idempotency_key="low_buy_materialization_refresh:2026-05-18",
            payload_json='{"expected_trade_date":"2026-05-18"}',
            result_json=(
                '{"ok":true,"skipped":true,'
                '"status":"blocked_missing_required_snapshots",'
                '"reason":"missing_required_strategy_snapshots",'
                '"missing_required_strategies":["first_board"]}'
            ),
            priority=35,
            progress_pct=100,
            finished_at=datetime(2026, 5, 18, 15, 20),
        )
    )
    db.commit()
    _FakeQueue.last_payload = None
    _FakeQueue.payloads = []
    monkeypatch.setattr(low_buy_materialization, "expected_low_buy_trade_date", lambda _db: "2026-05-18")
    monkeypatch.setattr(low_buy_materialization, "RuntimeTaskQueue", _FakeQueue)

    low_buy_materialization.enqueue_low_buy_materialization(db, reason="after_close_latest_data", commit=True)

    assert db.query(RuntimeTask).count() == 1
    assert _FakeQueue.payloads == []


def test_after_close_followups_skip_non_trading_day(monkeypatch) -> None:
    _patch_base(monkeypatch)
    _FakeQueue.last_payload = None
    _FakeQueue.payloads = []
    monkeypatch.setattr(close_refresh, "is_a_share_trading_day", lambda _date: False)

    result = close_refresh.enqueue_after_close_followups(
        object(),
        trade_date="2026-06-06",
        now=datetime(2026, 6, 6, 15, 10),
        strategies=["first_board"],
    )

    assert result["action"] == "skip_non_trading_day"
    assert _FakeQueue.payloads == []


def test_after_close_followups_catch_up_previous_trade_date_reviews(monkeypatch) -> None:
    _patch_base(monkeypatch)
    _FakeQueue.last_payload = None
    _FakeQueue.payloads = []

    result = close_refresh.enqueue_after_close_followups(
        object(),
        trade_date="2026-05-18",
        now=datetime(2026, 5, 19, 10, 30),
        strategies=["first_board"],
    )

    assert result["ok"] is True
    review_tasks = [(item.task_type, item.payload["report_slot"]) for item in _FakeQueue.payloads if "review_report" in item.task_type]
    assert review_tasks == [
        ("market_review_report", "midday"),
        ("market_review_report", "close"),
    ]


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
