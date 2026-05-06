from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.entities import NotificationEvent
from app.models.schema_defs.agent import (
    AgentNotificationTestRequest,
    AgentNotificationTestResponse,
    AgentSignalNotificationRequest,
)
from app.services.agent_notification_service import AgentNotificationService


class NotificationEventTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine, future=True)

    def test_signal_notification_deduplicates_until_upgrade(self) -> None:
        with self.Session() as db:
            service = AgentNotificationService()
            service.send_test = Mock(
                return_value=AgentNotificationTestResponse(ok=True, channel="feishu", message="notification sent")
            )
            first = service.send_signal(
                db,
                AgentSignalNotificationRequest(
                    symbol="510300",
                    name="沪深300ETF",
                    strategy_key="first_board",
                    strategy_title="首板回调",
                    signal_state="watch",
                ),
                user_id=7,
            )
            second = service.send_signal(
                db,
                AgentSignalNotificationRequest(
                    symbol="510300",
                    name="沪深300ETF",
                    strategy_key="first_board",
                    strategy_title="首板回调",
                    signal_state="watch",
                ),
                user_id=7,
            )
            upgraded = service.send_signal(
                db,
                AgentSignalNotificationRequest(
                    symbol="510300",
                    name="沪深300ETF",
                    strategy_key="first_board",
                    strategy_title="首板回调",
                    signal_state="near_entry",
                ),
                user_id=7,
            )
            rows = db.execute(select(NotificationEvent)).scalars().all()

            self.assertTrue(first.should_notify)
            self.assertFalse(first.upgraded)
            self.assertFalse(second.should_notify)
            self.assertTrue(upgraded.should_notify)
            self.assertTrue(upgraded.upgraded)
            self.assertEqual(upgraded.notification_count, 2)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].scope_key, "user:7")
            self.assertEqual(rows[0].previous_signal_state, "watch")
            self.assertEqual(rows[0].signal_state, "near_entry")

    def test_unconfigured_notification_does_not_count_signal(self) -> None:
        with self.Session() as db:
            service = AgentNotificationService()
            object.__setattr__(service.settings, "notification_feishu_webhook_url", "")
            object.__setattr__(service.settings, "hermes_api_url", "")

            with self.assertLogs("app.services.agent_notification_service", level="WARNING") as logs:
                result = service.send_test(AgentNotificationTestRequest(channel="feishu", message="test"))

            self.assertFalse(result.ok)
            self.assertEqual(result.code, "NOTIFICATION_NOT_CONFIGURED")
            self.assertIn("Notification channel not configured", "\n".join(logs.output))

            signal = service.send_signal(
                db,
                AgentSignalNotificationRequest(
                    symbol="510300",
                    name="沪深300ETF",
                    strategy_key="first_board",
                    strategy_title="首板回调",
                    signal_state="watch",
                ),
                user_id=7,
            )
            row = db.execute(select(NotificationEvent)).scalars().one()
            self.assertFalse(signal.ok)
            self.assertEqual(signal.error_code, "NOTIFICATION_NOT_CONFIGURED")
            self.assertTrue(signal.should_notify)
            self.assertEqual(signal.notification_count, 0)
            self.assertEqual(row.notification_count, 0)
            self.assertIsNone(row.last_notified_at)

    def test_feishu_business_error_is_not_success(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def getcode(self) -> int:
                return 200

            def read(self) -> bytes:
                return b'{"code":1,"msg":"invalid webhook"}'

        service = AgentNotificationService()
        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            result = service._send_feishu_text(webhook="https://example.test", message="hello", channel="feishu")

        self.assertFalse(result.ok)
        self.assertEqual(result.message, "invalid webhook")

    def test_hermes_error_marker_is_not_counted(self) -> None:
        with self.Session() as db:
            service = AgentNotificationService()
            service.send_test = Mock(
                return_value=AgentNotificationTestResponse(
                    ok=False,
                    channel="feishu",
                    message="hermes notification business failed",
                    code="HERMES_NOTIFICATION_FAILED",
                )
            )
            result = service.send_signal(
                db,
                AgentSignalNotificationRequest(
                    symbol="300059",
                    name="东方财富",
                    strategy_key="volume_shrink",
                    strategy_title="量能低吸",
                    signal_state="near_entry",
                ),
                user_id=8,
            )
            self.assertFalse(result.ok)
            self.assertEqual(result.error_code, "HERMES_NOTIFICATION_FAILED")
            self.assertEqual(result.notification_count, 0)


if __name__ == "__main__":
    unittest.main()
