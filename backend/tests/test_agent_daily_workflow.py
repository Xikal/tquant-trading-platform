from __future__ import annotations

import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.entities import NotificationEvent
from app.models.schema_defs.agent import AgentDailyReportResponse, AgentNotificationTestResponse
from app.services.agent_daily_workflow_service import AgentDailyWorkflowService


class _ReportServiceStub:
    def daily_report(self, db):  # noqa: ANN001, ARG002
        return AgentDailyReportResponse(
            trade_date="2026-05-04",
            generated_at="2026-05-04 15:10:00",
            headline="今日可执行信号 1 个，全策略优先候选 2 个。",
            markdown="# TQuant 每日决策报告\n\n- 今日可执行信号 1 个。",
        )


class _NotificationServiceStub:
    def __init__(self, webhook_url: str) -> None:
        self.settings = SimpleNamespace(notification_feishu_webhook_url=webhook_url)
        self.calls = []

    def send_test(self, payload):  # noqa: ANN001
        self.calls.append(payload)
        return AgentNotificationTestResponse(ok=True, channel=payload.channel, message="notification sent")


class _HermesNotificationServiceStub(_NotificationServiceStub):
    def supports_channel(self, channel: str = "feishu") -> bool:
        return channel == "feishu"


class AgentDailyWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine, future=True)

    def test_daily_report_push_skips_safely_without_feishu_webhook(self) -> None:
        notifier = _NotificationServiceStub(webhook_url="")
        service = AgentDailyWorkflowService(
            report_service=_ReportServiceStub(),
            notification_service=notifier,
        )

        with self.Session() as db:
            result = service.push_daily_report(db, channel="feishu")
            events = db.execute(select(NotificationEvent)).scalars().all()

        self.assertTrue(result.ok)
        self.assertFalse(result.sent)
        self.assertFalse(result.should_notify)
        self.assertFalse(result.duplicate)
        self.assertIn("not configured", result.message)
        self.assertEqual(result.trade_date, "2026-05-04")
        self.assertEqual(len(notifier.calls), 0)
        self.assertEqual(events, [])

    def test_daily_report_push_can_use_hermes_fallback_without_webhook(self) -> None:
        notifier = _HermesNotificationServiceStub(webhook_url="")
        service = AgentDailyWorkflowService(
            report_service=_ReportServiceStub(),
            notification_service=notifier,
        )

        with self.Session() as db:
            result = service.push_daily_report(db, channel="feishu")
            events = db.execute(select(NotificationEvent)).scalars().all()

        self.assertTrue(result.ok)
        self.assertTrue(result.sent)
        self.assertTrue(result.should_notify)
        self.assertEqual(len(notifier.calls), 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].notification_count, 1)

    def test_daily_report_push_sends_markdown_once_per_trade_date_and_channel(self) -> None:
        notifier = _NotificationServiceStub(webhook_url="https://example.test/feishu")
        service = AgentDailyWorkflowService(
            report_service=_ReportServiceStub(),
            notification_service=notifier,
        )

        with self.Session() as db:
            first = service.push_daily_report(db, channel="feishu")
            second = service.push_daily_report(db, channel="feishu")
            events = db.execute(select(NotificationEvent)).scalars().all()

        self.assertTrue(first.ok)
        self.assertTrue(first.sent)
        self.assertTrue(first.should_notify)
        self.assertFalse(first.duplicate)
        self.assertTrue(second.ok)
        self.assertFalse(second.sent)
        self.assertFalse(second.should_notify)
        self.assertTrue(second.duplicate)
        self.assertEqual(len(notifier.calls), 1)
        self.assertIn("# TQuant 每日决策报告", notifier.calls[0].message)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "daily_report")
        self.assertEqual(events[0].symbol, "daily_report")
        self.assertEqual(events[0].strategy_key, "2026-05-04")
        self.assertEqual(events[0].notification_count, 1)


if __name__ == "__main__":
    unittest.main()
