from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import DailyBarSnapshot, NotificationEvent
from app.services import latest_data_watchdog as watchdog


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_watchdog_skips_before_close(monkeypatch):
    db = _db()
    monkeypatch.setattr(watchdog, "is_a_share_trading_day", lambda _date: True)
    sent = []

    result = watchdog.LatestDailyBarWatchdog(
        notification_service=SimpleNamespace(send_test=lambda payload: sent.append(payload) or SimpleNamespace(ok=True, message="sent"))
    ).run(db, now=datetime(2026, 6, 3, 14, 59, 0), notify=True)

    assert result["status"] == "skip_before_close"
    assert sent == []


def test_watchdog_can_bypass_time_gate_for_refresh_success_notification(monkeypatch):
    db = _db()
    monkeypatch.setattr(watchdog, "is_a_share_trading_day", lambda _date: True)
    sent = []
    for index in range(watchdog.MIN_STOCK_DAILY_BARS):
        db.add(
            DailyBarSnapshot(
                symbol=f"{index:06d}",
                trade_date="2026-06-03",
                close_price=10,
                pre_close=9.9,
                volume=1000,
                amount=10000,
                pct_chg=1.0,
                fetch_time="2026-06-03T15:05:00",
            )
        )
    db.commit()

    result = watchdog.LatestDailyBarWatchdog(
        notification_service=SimpleNamespace(
            supports_channel=lambda channel="feishu": True,
            send_test=lambda payload: sent.append(payload) or SimpleNamespace(ok=True, message="sent"),
        )
    ).run(
        db,
        now=datetime(2026, 6, 3, 15, 5, 0),
        notify=True,
        enforce_watchdog_time_gate=False,
    )

    assert result["ok"] is True
    assert result["status"] == "notification_sent"
    assert sent
    assert "日线已更新" in sent[0].message


def test_watchdog_sends_alert_when_after_close_daily_bars_missing(monkeypatch):
    db = _db()
    monkeypatch.setattr(watchdog, "is_a_share_trading_day", lambda _date: True)
    sent = []

    result = watchdog.LatestDailyBarWatchdog(
        notification_service=SimpleNamespace(
            supports_channel=lambda channel="feishu": True,
            send_test=lambda payload: sent.append(payload) or SimpleNamespace(ok=True, message="sent"),
        )
    ).run(db, now=datetime(2026, 6, 3, 15, 35, 0), notify=True)

    assert result["status"] == "alert_sent"
    assert result["expected_trade_date"] == "2026-06-03"
    assert result["daily_bar_count"] == 0
    assert sent
    assert "日线未更新" in sent[0].message
    assert "2026-06-03" in sent[0].message
    assert "0/4500" in sent[0].message
    event = db.execute(select(NotificationEvent)).scalar_one()
    assert event.event_type == "daily_bar_watchdog"
    assert event.strategy_key == "2026-06-03"
    assert event.notification_count == 1


def test_watchdog_sends_confirmation_when_daily_bars_are_complete(monkeypatch):
    db = _db()
    monkeypatch.setattr(watchdog, "is_a_share_trading_day", lambda _date: True)
    sent = []
    for index in range(watchdog.MIN_STOCK_DAILY_BARS):
        db.add(
            DailyBarSnapshot(
                symbol=f"{index:06d}",
                trade_date="2026-06-03",
                close_price=10,
                pre_close=9.9,
                volume=1000,
                amount=10000,
                pct_chg=1.0,
                fetch_time="2026-06-03T15:35:00",
            )
        )
    db.commit()

    result = watchdog.LatestDailyBarWatchdog(
        notification_service=SimpleNamespace(
            supports_channel=lambda channel="feishu": True,
            send_test=lambda payload: sent.append(payload) or SimpleNamespace(ok=True, message="sent"),
        )
    ).run(db, now=datetime(2026, 6, 3, 15, 35, 0), notify=True)

    assert result["ok"] is True
    assert result["status"] == "notification_sent"
    assert result["daily_bar_count"] == watchdog.MIN_STOCK_DAILY_BARS
    assert sent
    assert "日线已更新" in sent[0].message
    assert "2026-06-03" in sent[0].message
    assert "收盘后抓取覆盖：4500/4500" in sent[0].message


def test_watchdog_alerts_when_daily_bars_only_have_before_close_fetch_time(monkeypatch):
    db = _db()
    monkeypatch.setattr(watchdog, "is_a_share_trading_day", lambda _date: True)
    sent = []
    for index in range(watchdog.MIN_STOCK_DAILY_BARS):
        db.add(
            DailyBarSnapshot(
                symbol=f"{index:06d}",
                trade_date="2026-06-03",
                close_price=10,
                pre_close=9.9,
                volume=1000,
                amount=10000,
                pct_chg=1.0,
                fetch_time="2026-06-03T13:51:11",
            )
        )
    db.commit()

    result = watchdog.LatestDailyBarWatchdog(
        notification_service=SimpleNamespace(
            supports_channel=lambda channel="feishu": True,
            send_test=lambda payload: sent.append(payload) or SimpleNamespace(ok=True, message="sent"),
        )
    ).run(db, now=datetime(2026, 6, 3, 15, 35, 0), notify=True)

    assert result["ok"] is False
    assert result["status"] == "alert_sent"
    assert result["daily_bar_count"] == watchdog.MIN_STOCK_DAILY_BARS
    assert result["post_close_daily_bar_count"] == 0
    assert result["daily_bar_freshness_status"] == "stale_before_post_close"
    assert "日线未更新" in sent[0].message
    assert "收盘后抓取覆盖：0/4500" in sent[0].message


def test_watchdog_deduplicates_same_trade_date_alert(monkeypatch):
    db = _db()
    monkeypatch.setattr(watchdog, "is_a_share_trading_day", lambda _date: True)
    sent = []
    service = watchdog.LatestDailyBarWatchdog(
        notification_service=SimpleNamespace(
            supports_channel=lambda channel="feishu": True,
            send_test=lambda payload: sent.append(payload) or SimpleNamespace(ok=True, message="sent"),
        )
    )

    first = service.run(db, now=datetime(2026, 6, 3, 15, 35, 0), notify=True)
    second = service.run(db, now=datetime(2026, 6, 3, 15, 45, 0), notify=True)

    assert first["status"] == "alert_sent"
    assert second["status"] == "notification_suppressed"
    assert len(sent) == 1
    event = db.execute(select(NotificationEvent)).scalar_one()
    assert event.notification_count == 1


def test_watchdog_sends_success_after_prior_missing_alert(monkeypatch):
    db = _db()
    monkeypatch.setattr(watchdog, "is_a_share_trading_day", lambda _date: True)
    sent = []
    service = watchdog.LatestDailyBarWatchdog(
        notification_service=SimpleNamespace(
            supports_channel=lambda channel="feishu": True,
            send_test=lambda payload: sent.append(payload) or SimpleNamespace(ok=True, message="sent"),
        )
    )

    first = service.run(db, now=datetime(2026, 6, 3, 15, 35, 0), notify=True)
    for index in range(watchdog.MIN_STOCK_DAILY_BARS):
        db.add(
            DailyBarSnapshot(
                symbol=f"{index:06d}",
                trade_date="2026-06-03",
                close_price=10,
                pre_close=9.9,
                volume=1000,
                amount=10000,
                pct_chg=1.0,
                fetch_time="2026-06-03T15:50:00",
            )
        )
    db.commit()
    second = service.run(db, now=datetime(2026, 6, 3, 15, 55, 0), notify=True)

    assert first["status"] == "alert_sent"
    assert second["status"] == "notification_sent"
    assert len(sent) == 2
    assert "日线未更新" in sent[0].message
    assert "日线已更新" in sent[1].message
    event = db.execute(select(NotificationEvent)).scalar_one()
    assert event.notification_count == 2
    assert event.signal_state == "ok"


def test_watchdog_force_notify_bypasses_same_day_dedup(monkeypatch):
    db = _db()
    monkeypatch.setattr(watchdog, "is_a_share_trading_day", lambda _date: True)
    sent = []
    service = watchdog.LatestDailyBarWatchdog(
        notification_service=SimpleNamespace(
            supports_channel=lambda channel="feishu": True,
            send_test=lambda payload: sent.append(payload) or SimpleNamespace(ok=True, message="sent"),
        )
    )

    first = service.run(db, now=datetime(2026, 6, 3, 15, 35, 0), notify=True)
    second = service.run(db, now=datetime(2026, 6, 3, 15, 45, 0), notify=True, force_notify=True)

    assert first["status"] == "alert_sent"
    assert second["status"] == "alert_sent"
    assert len(sent) == 2
    event = db.execute(select(NotificationEvent)).scalar_one()
    assert event.notification_count == 2
