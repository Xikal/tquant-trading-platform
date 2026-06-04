from __future__ import annotations

import json
from datetime import datetime, time as dt_time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now
from app.models.entities import NotificationEvent
from app.models.schema_defs.agent import AgentNotificationTestRequest
from app.services.agent_notification_service import AgentNotificationService
from app.services.latest_data_status import MIN_STOCK_DAILY_BARS, daily_bar_freshness_status
from app.services.market.trading_calendar import is_a_share_trading_day

CLOSE_WATCHDOG_AFTER = dt_time(hour=15, minute=20)
EVENT_TYPE = "daily_bar_watchdog"
SYMBOL = "daily_bar_watchdog"


class LatestDailyBarWatchdog:
    """Post-close daily bar freshness notifier.

    This service is intentionally small and deterministic so Hermes cron,
    manual scripts, and runtime-worker tasks all use the same data check and
    notification de-duplication path.
    """

    def __init__(self, *, notification_service: AgentNotificationService | None = None) -> None:
        self.notifications = notification_service or AgentNotificationService()

    def run(
        self,
        db: Session,
        *,
        trade_date: str | None = None,
        now: datetime | None = None,
        notify: bool = True,
        force_notify: bool = False,
        channel: str = "feishu",
    ) -> dict[str, Any]:
        current = now or beijing_now()
        if current.time() < CLOSE_WATCHDOG_AFTER:
            return {
                "ok": True,
                "status": "skip_before_close",
                "message": "未到收盘后日线巡查时间",
                "checked_at": current.isoformat(),
            }
        if not is_a_share_trading_day(current.date()):
            return {
                "ok": True,
                "status": "skip_non_trading_day",
                "message": "非 A 股交易日，跳过日线巡查",
                "checked_at": current.isoformat(),
            }

        expected = (trade_date or current.date().isoformat()).strip()
        freshness = daily_bar_freshness_status(db, expected)
        daily_count = int(freshness.get("daily_bar_count") or 0)
        post_close_count = int(freshness.get("post_close_daily_bar_count") or 0)
        complete = daily_count >= MIN_STOCK_DAILY_BARS and post_close_count >= MIN_STOCK_DAILY_BARS
        message = _message(
            expected_trade_date=expected,
            daily_count=daily_count,
            post_close_daily_count=post_close_count,
            latest_fetch_time=str(freshness.get("latest_daily_bar_fetch_time") or ""),
            post_close_cutoff=str(freshness.get("post_close_fetch_cutoff") or ""),
            complete=complete,
            checked_at=current,
        )
        base = {
            "ok": complete,
            "status": "ok" if complete else "missing_daily_bars",
            "expected_trade_date": expected,
            "daily_bar_count": daily_count,
            "min_daily_bar_count": MIN_STOCK_DAILY_BARS,
            "post_close_daily_bar_count": post_close_count,
            "post_close_fetch_cutoff": freshness.get("post_close_fetch_cutoff"),
            "latest_daily_bar_fetch_time": freshness.get("latest_daily_bar_fetch_time"),
            "daily_bar_freshness_status": freshness.get("daily_bar_freshness_status"),
            "checked_at": current.isoformat(),
            "message": message,
        }
        if not notify:
            return {**base, "status": "checked_no_notify"}

        signal_state = "ok" if complete else "missing_daily_bars"
        event = _load_event(db, channel=channel, trade_date=expected)
        if (
            event is not None
            and int(event.notification_count or 0) > 0
            and str(event.signal_state or "") == signal_state
            and not force_notify
        ):
            event.last_seen_at = current
            db.commit()
            return {**base, "status": "notification_suppressed", "duplicate": True}

        if not _notification_channel_available(self.notifications, channel):
            return {**base, "status": "notification_skipped", "notification_message": "notification channel not configured"}

        send_result = self.notifications.send_test(AgentNotificationTestRequest(channel=channel, message=message))
        if not send_result.ok:
            return {
                **base,
                "status": "notification_failed",
                "notification_message": send_result.message,
                "notification_code": send_result.code,
            }

        if event is None:
            event = NotificationEvent(
                scope_key="global",
                channel=channel,
                event_type=EVENT_TYPE,
                symbol=SYMBOL,
                name="日线刷新巡查",
                strategy_key=expected,
                strategy_title="每日收盘日线刷新巡查",
                signal_state=signal_state,
                signal_rank=0 if complete else 3,
                previous_signal_state="",
                upgraded=False,
                payload_json="{}",
                last_seen_at=current,
            )
            db.add(event)
            db.flush()
        event.name = "日线刷新巡查"
        event.strategy_title = "每日收盘日线刷新巡查"
        event.signal_state = signal_state
        event.signal_rank = 0 if complete else 3
        event.payload_json = json.dumps(
            {
                "expected_trade_date": expected,
                "daily_bar_count": daily_count,
                "min_daily_bar_count": MIN_STOCK_DAILY_BARS,
                "post_close_daily_bar_count": post_close_count,
                "post_close_fetch_cutoff": freshness.get("post_close_fetch_cutoff"),
                "latest_daily_bar_fetch_time": freshness.get("latest_daily_bar_fetch_time"),
                "daily_bar_freshness_status": freshness.get("daily_bar_freshness_status"),
                "checked_at": current.isoformat(),
                "complete": complete,
            },
            ensure_ascii=False,
        )
        event.last_seen_at = current
        event.last_notified_at = current
        event.notification_count = int(event.notification_count or 0) + 1
        db.commit()
        return {
            **base,
            "status": "notification_sent" if complete else "alert_sent",
            "sent": True,
            "notification_message": send_result.message,
            "notification_count": int(event.notification_count or 0),
        }


class LatestDataWatchdogLedger:
    def __init__(self, db: Session) -> None:
        self.db = db

    def already_notified(self, *, trade_date: str, channel: str = "feishu") -> bool:
        event = _load_event(self.db, channel=channel, trade_date=trade_date)
        return bool(event is not None and int(event.notification_count or 0) > 0 and event.signal_state == "ok")


def _load_event(db: Session, *, channel: str, trade_date: str) -> NotificationEvent | None:
    return (
        db.execute(
            select(NotificationEvent).where(
                NotificationEvent.scope_key == "global",
                NotificationEvent.channel == channel,
                NotificationEvent.event_type == EVENT_TYPE,
                NotificationEvent.symbol == SYMBOL,
                NotificationEvent.strategy_key == trade_date,
            )
        )
        .scalars()
        .first()
    )


def _notification_channel_available(notification_service: AgentNotificationService, channel: str) -> bool:
    checker = getattr(notification_service, "supports_channel", None)
    if callable(checker):
        return bool(checker(channel))
    return False


def _message(
    *,
    expected_trade_date: str,
    daily_count: int,
    post_close_daily_count: int,
    latest_fetch_time: str,
    post_close_cutoff: str,
    complete: bool,
    checked_at: datetime,
) -> str:
    status = "日线已更新" if complete else "日线未更新"
    level = "正常" if complete else "告警"
    action = "低吸榜可继续等待策略物化结果。" if complete else "请检查 runtime-worker、数据源和 daily_bar_refresh 任务；收盘后必须重新抓取完整日线。"
    return "\n".join(
        [
            f"【TQuant 收盘日线巡查｜{level}】{status}",
            f"交易日：{expected_trade_date}",
            f"日线数量：{daily_count}/{MIN_STOCK_DAILY_BARS}",
            f"收盘后抓取覆盖：{post_close_daily_count}/{MIN_STOCK_DAILY_BARS}",
            f"收盘后阈值北京时间：{post_close_cutoff or '-'}",
            f"最新抓取时间：{latest_fetch_time or '-'}",
            f"检查时间：{checked_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"处理建议：{action}",
        ]
    )
