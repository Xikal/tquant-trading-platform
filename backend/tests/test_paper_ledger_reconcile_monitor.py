from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import PaperAccount
from app.services.paper.ledger_reconcile_monitor import PaperLedgerReconcileMonitorService


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


class _Notifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def supports_channel(self, channel: str = "feishu") -> bool:
        return channel == "feishu"

    def send_test(self, payload):  # noqa: ANN001
        self.messages.append(payload.message)
        return SimpleNamespace(ok=True, message="ok")


def test_daily_preview_sends_alert_when_gap_exceeds_threshold(monkeypatch) -> None:
    db = _db()
    db.add(PaperAccount(name="测试账户", status="active"))
    db.commit()

    monkeypatch.setattr(
        "app.services.paper.ledger_reconcile_monitor.PaperLedgerRepairService.preview",
        lambda self, account_id: SimpleNamespace(reconciliation_gap_before=Decimal("2.35")),
    )
    notifier = _Notifier()

    result = PaperLedgerReconcileMonitorService(db, notifier=notifier).run_daily_preview(threshold=1.0)

    assert result["accounts_checked"] == 1
    assert result["alert_count"] == 1
    assert result["alerts_sent"] is True
    assert "测试账户" in notifier.messages[0]


def test_daily_preview_ignores_small_gap(monkeypatch) -> None:
    db = _db()
    db.add(PaperAccount(name="安全账户", status="active"))
    db.commit()

    monkeypatch.setattr(
        "app.services.paper.ledger_reconcile_monitor.PaperLedgerRepairService.preview",
        lambda self, account_id: SimpleNamespace(reconciliation_gap_before=Decimal("0.50")),
    )
    notifier = _Notifier()

    result = PaperLedgerReconcileMonitorService(db, notifier=notifier).run_daily_preview(threshold=1.0)

    assert result["alert_count"] == 0
    assert result["alerts_sent"] is False
    assert notifier.messages == []
