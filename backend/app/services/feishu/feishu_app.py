from __future__ import annotations

import secrets

from app.core.config import get_settings


class FeishuAppConfig:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.feishu_app_id and self.settings.feishu_app_secret)

    def verify_token(self, token: str) -> bool:
        expected = self.settings.feishu_verification_token.strip()
        if not expected:
            return False
        return secrets.compare_digest(token or "", expected)
