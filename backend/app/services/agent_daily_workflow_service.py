from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now
from app.models.entities import NotificationEvent
from app.models.schema_defs.agent import (
    AgentDailyReportPushResponse,
    AgentDailyReportResponse,
    AgentNotificationTestRequest,
)
from app.services.agent_notification_service import AgentNotificationService
from app.services.agent_report_service import AgentReportService


DAILY_REPORT_EVENT_TYPE = "daily_report"
DAILY_REPORT_SYMBOL = "daily_report"


class AgentDailyWorkflowService:
    """Generate and push the deterministic Agent daily report.

    This workflow intentionally uses the existing rule-based report service
    and notification adapter only. It does not invoke any LLM provider.
    """

    def __init__(
        self,
        *,
        report_service: AgentReportService | None = None,
        notification_service: AgentNotificationService | None = None,
    ) -> None:
        self.reports = report_service or AgentReportService()
        self.notifications = notification_service or AgentNotificationService()

    def push_daily_report(self, db: Session, *, channel: str = "feishu") -> AgentDailyReportPushResponse:
        channel = (channel or "feishu").strip().lower()
        report = self.reports.daily_report(db)
        markdown = _daily_report_message(report)
        if channel != "feishu":
            return _response(
                report,
                channel=channel,
                ok=False,
                message=f"daily report notification channel {channel} is not supported",
                markdown=markdown,
            )

        event = _load_daily_event(db, channel=channel, trade_date=report.trade_date)
        if event is not None and int(event.notification_count or 0) > 0:
            event.last_seen_at = beijing_now()
            db.commit()
            return _response(
                report,
                channel=channel,
                ok=True,
                duplicate=True,
                notification_count=int(event.notification_count or 0),
                message="daily report notification suppressed by daily de-dup ledger",
                markdown=markdown,
            )

        if not _notification_channel_available(self.notifications, channel):
            return _response(
                report,
                channel=channel,
                ok=True,
                message="daily report notification skipped: feishu notification channel not configured",
                markdown=markdown,
            )

        send_result = self.notifications.send_test(AgentNotificationTestRequest(channel=channel, message=markdown))
        if not send_result.ok:
            return _response(
                report,
                channel=channel,
                ok=False,
                should_notify=True,
                message=send_result.message,
                markdown=markdown,
            )

        now = beijing_now()
        if event is None:
            event = NotificationEvent(
                scope_key="global",
                channel=channel,
                event_type=DAILY_REPORT_EVENT_TYPE,
                symbol=DAILY_REPORT_SYMBOL,
                name="Agent 研究日报",
                strategy_key=report.trade_date,
                strategy_title="每日 Agent 研究日报",
                signal_state="sent",
                signal_rank=0,
                previous_signal_state="",
                upgraded=False,
                payload_json="{}",
                last_seen_at=now,
            )
            db.add(event)
            db.flush()
        event.name = "Agent 研究日报"
        event.strategy_title = "每日 Agent 研究日报"
        event.signal_state = "sent"
        event.payload_json = json.dumps(
            {
                "trade_date": report.trade_date,
                "generated_at": report.generated_at,
                "headline": report.headline,
            },
            ensure_ascii=False,
        )
        event.last_seen_at = now
        event.last_notified_at = now
        event.notification_count = int(event.notification_count or 0) + 1
        db.commit()
        return _response(
            report,
            channel=channel,
            ok=True,
            sent=True,
            should_notify=True,
            notification_count=int(event.notification_count or 0),
            message=send_result.message,
            markdown=markdown,
        )


def _load_daily_event(db: Session, *, channel: str, trade_date: str) -> NotificationEvent | None:
    return (
        db.execute(
            select(NotificationEvent).where(
                NotificationEvent.scope_key == "global",
                NotificationEvent.channel == channel,
                NotificationEvent.event_type == DAILY_REPORT_EVENT_TYPE,
                NotificationEvent.symbol == DAILY_REPORT_SYMBOL,
                NotificationEvent.strategy_key == trade_date,
            )
        )
        .scalars()
        .first()
    )


def _daily_report_message(report: AgentDailyReportResponse) -> str:
    markdown = (report.markdown or "").strip()
    if markdown:
        return markdown
    return f"# TQuant 每日决策报告\n\n{report.headline}".strip()


def _notification_channel_available(notification_service: AgentNotificationService, channel: str) -> bool:
    checker = getattr(notification_service, "supports_channel", None)
    if callable(checker):
        return bool(checker(channel))
    settings = getattr(notification_service, "settings", None)
    return bool(getattr(settings, "notification_feishu_webhook_url", "").strip())


def _response(
    report: AgentDailyReportResponse,
    *,
    channel: str,
    ok: bool,
    sent: bool = False,
    should_notify: bool = False,
    duplicate: bool = False,
    notification_count: int = 0,
    message: str,
    markdown: str,
) -> AgentDailyReportPushResponse:
    return AgentDailyReportPushResponse(
        ok=ok,
        channel=channel,
        trade_date=report.trade_date,
        generated_at=report.generated_at,
        sent=sent,
        should_notify=should_notify,
        duplicate=duplicate,
        notification_count=notification_count,
        message=message,
        markdown=markdown,
    )
