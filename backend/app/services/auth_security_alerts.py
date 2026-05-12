from __future__ import annotations

import logging

from app.models.schema_defs.agent import AgentNotificationTestRequest
from app.services.agent_notification_service import AgentNotificationService

logger = logging.getLogger(__name__)


def notify_login_lockout(*, username: str, locked_until: object) -> None:
    """Best-effort security alert for repeated login failures."""

    message = f"安全提醒：账号 {username} 因连续登录失败已临时锁定，锁定至 {locked_until}。"
    try:
        AgentNotificationService().send_test(
            AgentNotificationTestRequest(channel="feishu", message=message)
        )
    except Exception:
        logger.warning("failed to send login lockout notification for user=%s", username)
