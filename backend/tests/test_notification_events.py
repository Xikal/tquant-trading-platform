from __future__ import annotations

import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.entities import NotificationEvent
from app.models.schema_defs.agent import AgentSignalNotificationRequest
from app.services.agent_notification_service import AgentNotificationService


class NotificationEventTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine, future=True)

    def test_signal_notification_deduplicates_until_upgrade(self) -> None:
        with self.Session() as db:
            service = AgentNotificationService()
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


if __name__ == "__main__":
    unittest.main()
