from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.sse_token_service import SseStreamTokenService


class SseStreamTokenServiceTest(unittest.TestCase):
    def test_signed_token_can_be_consumed_by_another_service_instance(self) -> None:
        settings = SimpleNamespace(auth_secret_key="test-stream-secret")
        with patch("app.services.sse_token_service.get_settings", return_value=settings):
            issuer = SseStreamTokenService(ttl_seconds=60, scope="strategy-progress")
            verifier = SseStreamTokenService(ttl_seconds=60, scope="strategy-progress")

            grant = issuer.issue(42)

            self.assertEqual(verifier.consume(grant.token), 42)

    def test_scope_mismatch_is_rejected(self) -> None:
        settings = SimpleNamespace(auth_secret_key="test-stream-secret")
        with patch("app.services.sse_token_service.get_settings", return_value=settings):
            grant = SseStreamTokenService(ttl_seconds=60, scope="intraday").issue(42)

            self.assertIsNone(SseStreamTokenService(ttl_seconds=60, scope="strategy-progress").consume(grant.token))


if __name__ == "__main__":
    unittest.main()
