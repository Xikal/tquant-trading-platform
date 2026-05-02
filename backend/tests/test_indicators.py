import math
import unittest

from app.services.indicators import sanitize_metrics


class IndicatorSanitizeTests(unittest.TestCase):
    def test_sanitize_metrics_keeps_text_and_cleans_numbers(self):
        payload = sanitize_metrics(
            {
                "score": 12.34567,
                "bad_number": math.inf,
                "flag": True,
                "scene": "回踩承接",
            }
        )

        self.assertEqual(payload["score"], 12.3457)
        self.assertEqual(payload["bad_number"], 0.0)
        self.assertIs(payload["flag"], True)
        self.assertEqual(payload["scene"], "回踩承接")


if __name__ == "__main__":
    unittest.main()
