from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import subprocess
import time
from datetime import timedelta
from pathlib import Path
import urllib.error
import urllib.request

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timezone import beijing_now
from app.models.entities import NotificationEvent
from app.models.schema_defs.agent import (
    AgentNotificationTestRequest,
    AgentNotificationTestResponse,
    AgentSignalNotificationRequest,
    AgentSignalNotificationResponse,
)


logger = logging.getLogger(__name__)

SIGNAL_RANKS = {
    "avoid": 0,
    "blocked": 0,
    "research": 1,
    "watch": 2,
    "track": 2,
    "near_entry": 3,
    "focus": 3,
    "soft_buy_now": 4,
    "buy_now": 5,
    "immediate": 5,
}


class AgentNotificationService:
    """Small notification adapter used only through Agent notify tools."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def supports_channel(self, channel: str = "feishu") -> bool:
        """Return whether a notification path is configured for the channel."""

        channel = channel.strip().lower() or "feishu"
        if channel != "feishu":
            return False
        if self.settings.notification_feishu_webhook_url.strip():
            return True
        return _hermes_cli_path(self.settings.hermes_api_url) is not None

    def send_test(self, payload: AgentNotificationTestRequest) -> AgentNotificationTestResponse:
        channel = payload.channel.strip().lower() or "feishu"
        if channel != "feishu":
            return AgentNotificationTestResponse(
                ok=False,
                channel=payload.channel,
                message=f"notification channel {payload.channel} is not supported",
            )
        webhook = self.settings.notification_feishu_webhook_url.strip()
        if webhook:
            return self._send_feishu_text(webhook=webhook, message=payload.message, channel=payload.channel)
        hermes_path = _hermes_cli_path(self.settings.hermes_api_url)
        if hermes_path is not None:
            return self._send_hermes_feishu_text(hermes_path=hermes_path, message=payload.message, channel=payload.channel)
        logger.warning("Notification channel not configured, skipping signal notification: channel=%s", channel)
        return AgentNotificationTestResponse(
            ok=False,
            channel=payload.channel,
            message="notification adapter not configured",
        )

    def send_signal(
        self,
        db: Session,
        payload: AgentSignalNotificationRequest,
        *,
        user_id: int | None = None,
    ) -> AgentSignalNotificationResponse:
        """Record and optionally send a signal notification.

        The database ledger is the source of truth for duplicate suppression
        and signal upgrade detection.  Stronger signal states notify
        immediately; unchanged signals respect a cooldown.
        """

        channel = payload.channel.strip().lower() or "feishu"
        event = self._upsert_signal_event(db=db, payload=payload, channel=channel, user_id=user_id)
        should_notify = self._should_notify(event)
        send_ok = True
        if should_notify:
            message = payload.message.strip() or _default_signal_message(payload, upgraded=event.upgraded)
            send_result = self.send_test(AgentNotificationTestRequest(channel=channel, message=message))
            send_ok = bool(send_result.ok)
            if send_result.ok:
                event.notification_count += 1
                event.last_notified_at = beijing_now()
            else:
                logger.warning(
                    "Notification send failed, signal ledger not counted: channel=%s symbol=%s strategy=%s reason=%s",
                    channel,
                    payload.symbol,
                    payload.strategy_key,
                    send_result.message,
                )
            response_message = send_result.message
        else:
            response_message = "signal notification suppressed by cooldown"
        event.last_seen_at = beijing_now()
        db.commit()
        return AgentSignalNotificationResponse(
            ok=send_ok,
            channel=channel,
            symbol=payload.symbol,
            strategy_key=payload.strategy_key,
            signal_state=payload.signal_state,
            should_notify=should_notify,
            upgraded=bool(event.upgraded),
            notification_count=int(event.notification_count or 0),
            message=response_message,
        )

    def _send_feishu_text(self, *, webhook: str, message: str, channel: str) -> AgentNotificationTestResponse:
        body = {
            "msg_type": "text",
            "content": {"text": message[:2000]},
        }
        if self.settings.notification_feishu_secret.strip():
            body.update(_feishu_signature(self.settings.notification_feishu_secret.strip()))
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            webhook,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=max(self.settings.agent_timeout_seconds, 1)) as response:
                status = response.getcode()
                raw_body = response.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as exc:
            logger.error("Feishu notification request failed: %s", exc)
            return AgentNotificationTestResponse(ok=False, channel=channel, message="notification request failed")
        ok, response_message = _feishu_delivery_status(status=status, raw_body=raw_body)
        if not ok:
            logger.error("Feishu notification business failure: status=%s body=%s", status, raw_body[:500])
        return AgentNotificationTestResponse(
            ok=ok,
            channel=channel,
            message=response_message,
        )

    def _send_hermes_feishu_text(self, *, hermes_path: Path, message: str, channel: str) -> AgentNotificationTestResponse:
        prompt = _hermes_feishu_prompt(message)
        timeout = max(int(self.settings.agent_timeout_seconds or 10) * 6, 60)
        env = os.environ.copy()
        env["HERMES_ACCEPT_HOOKS"] = "1"
        try:
            result = subprocess.run(
                [str(hermes_path), "-z", prompt],
                cwd=str(Path(__file__).resolve().parents[3]),
                env=env,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.error("Hermes notification request failed: %s", exc)
            return AgentNotificationTestResponse(ok=False, channel=channel, message="hermes notification request failed")
        if result.returncode != 0:
            logger.error("Hermes notification exited with non-zero status: returncode=%s stderr=%s", result.returncode, result.stderr[:500])
            return AgentNotificationTestResponse(ok=False, channel=channel, message="hermes notification request failed")
        if _hermes_output_has_error_marker(result.stdout) or _hermes_output_has_error_marker(result.stderr):
            logger.error(
                "Hermes notification output indicates failure: stdout=%s stderr=%s",
                result.stdout[:500],
                result.stderr[:500],
            )
            return AgentNotificationTestResponse(ok=False, channel=channel, message="hermes notification business failed")
        return AgentNotificationTestResponse(ok=True, channel=channel, message="notification sent via hermes")

    def _upsert_signal_event(
        self,
        *,
        db: Session,
        payload: AgentSignalNotificationRequest,
        channel: str,
        user_id: int | None,
    ) -> NotificationEvent:
        scope_key = f"user:{user_id}" if user_id else "global"
        event_type = payload.event_type.strip() or "signal"
        strategy_key = payload.strategy_key.strip()
        row = (
            db.execute(
                select(NotificationEvent).where(
                    NotificationEvent.scope_key == scope_key,
                    NotificationEvent.channel == channel,
                    NotificationEvent.event_type == event_type,
                    NotificationEvent.symbol == payload.symbol.strip(),
                    NotificationEvent.strategy_key == strategy_key,
                )
            )
            .scalars()
            .first()
        )
        rank = _signal_rank(payload.signal_state)
        now = beijing_now()
        payload_json = json.dumps(payload.payload, ensure_ascii=False, default=str)
        if row is None:
            row = NotificationEvent(
                scope_key=scope_key,
                user_id=user_id,
                channel=channel,
                event_type=event_type,
                symbol=payload.symbol.strip(),
                name=payload.name.strip(),
                strategy_key=strategy_key,
                strategy_title=payload.strategy_title.strip(),
                signal_state=payload.signal_state.strip(),
                signal_rank=rank,
                previous_signal_state="",
                upgraded=False,
                payload_json=payload_json,
                last_seen_at=now,
            )
            db.add(row)
            db.flush()
            return row

        previous_rank = int(row.signal_rank or 0)
        previous_state = row.signal_state or ""
        row.previous_signal_state = previous_state
        row.upgraded = rank > previous_rank
        row.user_id = user_id
        row.name = payload.name.strip() or row.name
        row.strategy_title = payload.strategy_title.strip() or row.strategy_title
        row.signal_state = payload.signal_state.strip()
        row.signal_rank = rank
        row.payload_json = payload_json
        row.last_seen_at = now
        return row

    def _should_notify(self, event: NotificationEvent) -> bool:
        if event.last_notified_at is None:
            return True
        if event.upgraded:
            return True
        cooldown = timedelta(minutes=max(int(self.settings.notification_signal_cooldown_minutes), 1))
        return _elapsed_since(event.last_notified_at) >= cooldown


def _feishu_signature(secret: str) -> dict[str, str]:
    timestamp = str(int(time.time()))
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), b"", hashlib.sha256).digest()
    return {"timestamp": timestamp, "sign": base64.b64encode(digest).decode("utf-8")}


def _feishu_delivery_status(*, status: int, raw_body: str) -> tuple[bool, str]:
    if not 200 <= status < 300:
        return False, "notification request failed"
    try:
        payload = json.loads(raw_body or "{}")
    except json.JSONDecodeError:
        return False, "notification response invalid"
    code = payload.get("code")
    if code == 0 or str(code) == "0":
        return True, "notification sent"
    return False, str(payload.get("msg") or payload.get("message") or "notification business failed")


def _hermes_output_has_error_marker(output: str | None) -> bool:
    text = (output or "").strip().lower()
    if not text:
        return False
    markers = (
        "error",
        "failed",
        "failure",
        "exception",
        "traceback",
        "invalid",
        "not configured",
        "permission denied",
        "timeout",
        "timed out",
        "失败",
        "错误",
        "未配置",
        "无权限",
        "超时",
    )
    return any(marker in text for marker in markers)


def _signal_rank(signal_state: str) -> int:
    return SIGNAL_RANKS.get(signal_state.strip().lower(), 0)


def _default_signal_message(payload: AgentSignalNotificationRequest, *, upgraded: bool) -> str:
    prefix = "信号升级" if upgraded else "信号提醒"
    name = payload.name or payload.symbol
    strategy = payload.strategy_title or payload.strategy_key or "未指定策略"
    signal = payload.signal_text or payload.signal_state or "未指定状态"
    return f"{prefix}: {name} {payload.symbol} | {strategy} | {signal}"


def _hermes_cli_path(hermes_api_url: str) -> Path | None:
    value = (hermes_api_url or "").strip()
    if not value.startswith("hermes-cli://"):
        return None
    raw_path = value.replace("hermes-cli://", "", 1).strip() or "/Users/j/.local/bin/hermes"
    path = Path(raw_path).expanduser()
    return path if path.exists() else None


def _hermes_feishu_prompt(message: str) -> str:
    content = (message or "").strip()[:3500]
    return (
        "你是 TQuant 通知转发器。请把下面这条 TQuant 通知发送到已经接入的飞书机器人或飞书会话。"
        "不要改写为投资建议，不要添加收益承诺；发送完成后只回复一句：已发送。\n\n"
        f"通知内容：\n{content}"
    )


def _elapsed_since(moment) -> timedelta:
    now = beijing_now()
    if getattr(moment, "tzinfo", None) is None:
        now = now.replace(tzinfo=None)
    return now - moment
