from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.models.entities import StrategyDriftSnapshot
from app.models.schema_defs.agent import AgentNotificationTestRequest
from app.services.agent_notification_service import AgentNotificationService


def maybe_send_drift_alert(snapshot: StrategyDriftSnapshot, *, channel: str = "feishu") -> dict[str, Any]:
    if snapshot.drift_flag == "insufficient_sample":
        return {"ok": True, "sent": False, "reason": "insufficient_sample"}
    if snapshot.drift_flag in {"", "ok"}:
        return {"ok": True, "sent": False, "reason": "no_advisory_drift"}
    if not get_settings().drift_alert_enabled:
        return {"ok": True, "sent": False, "reason": "DRIFT_ALERT_ENABLED=false"}
    service = AgentNotificationService()
    if not service.supports_channel(channel):
        return {"ok": True, "sent": False, "reason": "notification_channel_not_configured"}
    response = service.send_test(
        AgentNotificationTestRequest(
            channel=channel,
            message=(
                "生产信号漂移 advisory："
                f"{snapshot.strategy_key} window={snapshot.window_days}d "
                f"settled={snapshot.sample_settled} "
                f"PF {snapshot.realized_pf}/{snapshot.expected_pf} "
                f"decay={snapshot.decay_pct:.2f}%"
            ),
        )
    )
    return {"ok": bool(response.ok), "sent": bool(response.ok), "reason": snapshot.drift_flag}
