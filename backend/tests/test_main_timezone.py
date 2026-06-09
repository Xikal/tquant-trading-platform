from __future__ import annotations

from datetime import datetime
import unittest
from unittest.mock import patch

from app.core.timezone import BEIJING_TZ
from app import main
from app.runtime import market_review_jobs


class MainTimezoneTests(unittest.TestCase):
    def test_market_close_review_due_uses_beijing_time(self) -> None:
        with patch("app.main.beijing_now", return_value=datetime(2026, 5, 6, 15, 6, tzinfo=BEIJING_TZ)):
            self.assertTrue(main._market_close_review_due())
        with patch("app.main.beijing_now", return_value=datetime(2026, 5, 6, 15, 4, tzinfo=BEIJING_TZ)):
            self.assertFalse(main._market_close_review_due())

    def test_agent_daily_report_due_uses_beijing_time_and_weekday(self) -> None:
        with patch("app.main.beijing_now", return_value=datetime(2026, 5, 6, 15, 11, tzinfo=BEIJING_TZ)):
            self.assertTrue(main._agent_daily_report_push_due())
        with patch("app.main.beijing_now", return_value=datetime(2026, 5, 6, 15, 9, tzinfo=BEIJING_TZ)):
            self.assertFalse(main._agent_daily_report_push_due())
        with patch("app.main.beijing_now", return_value=datetime(2026, 5, 9, 15, 30, tzinfo=BEIJING_TZ)):
            self.assertFalse(main._agent_daily_report_push_due())

    def test_midday_market_review_due_uses_beijing_time_and_weekday(self) -> None:
        with patch("app.runtime.market_review_jobs.beijing_now", return_value=datetime(2026, 5, 6, 11, 36, tzinfo=BEIJING_TZ)):
            self.assertTrue(market_review_jobs.market_midday_review_due())
        with patch("app.runtime.market_review_jobs.beijing_now", return_value=datetime(2026, 5, 6, 11, 34, tzinfo=BEIJING_TZ)):
            self.assertFalse(market_review_jobs.market_midday_review_due())
        with patch("app.runtime.market_review_jobs.beijing_now", return_value=datetime(2026, 5, 9, 11, 40, tzinfo=BEIJING_TZ)):
            self.assertFalse(market_review_jobs.market_midday_review_due())

    def test_main_midday_wrapper_remains_available(self) -> None:
        with patch("app.runtime.market_review_jobs.beijing_now", return_value=datetime(2026, 5, 6, 11, 36, tzinfo=BEIJING_TZ)):
            self.assertTrue(main._market_midday_review_due())


if __name__ == "__main__":
    unittest.main()
