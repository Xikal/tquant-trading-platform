from __future__ import annotations

from datetime import datetime
import unittest
from unittest.mock import patch

from app.core.timezone import BEIJING_TZ
from app import main


class MainTimezoneTests(unittest.TestCase):
    def test_paper_archive_due_uses_beijing_time(self) -> None:
        with patch("app.main.beijing_now", return_value=datetime(2026, 5, 6, 15, 6, tzinfo=BEIJING_TZ)):
            self.assertTrue(main._paper_archive_due())
        with patch("app.main.beijing_now", return_value=datetime(2026, 5, 6, 15, 4, tzinfo=BEIJING_TZ)):
            self.assertFalse(main._paper_archive_due())

    def test_agent_daily_report_due_uses_beijing_time_and_weekday(self) -> None:
        with patch("app.main.beijing_now", return_value=datetime(2026, 5, 6, 15, 11, tzinfo=BEIJING_TZ)):
            self.assertTrue(main._agent_daily_report_push_due())
        with patch("app.main.beijing_now", return_value=datetime(2026, 5, 6, 15, 9, tzinfo=BEIJING_TZ)):
            self.assertFalse(main._agent_daily_report_push_due())
        with patch("app.main.beijing_now", return_value=datetime(2026, 5, 9, 15, 30, tzinfo=BEIJING_TZ)):
            self.assertFalse(main._agent_daily_report_push_due())


if __name__ == "__main__":
    unittest.main()
