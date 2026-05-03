from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.schema_defs.agent import (
    AgentSignalNotificationRequest,
    AgentSignalNotificationScanResponse,
)
from app.services.agent_notification_service import AgentNotificationService
from app.services.low_buy.service import LowBuyScreenerService

logger = logging.getLogger(__name__)


class AgentSignalScanService:
    """Scan existing signal snapshots and feed notification de-dup ledger.

    The service only consumes already-materialized priority-board signals. It
    does not trigger strategy scans and does not change trading decisions.
    """

    def __init__(self, notifier: AgentNotificationService | None = None) -> None:
        self.notifier = notifier or AgentNotificationService()

    def scan_priority_board(
        self,
        db: Session,
        *,
        limit: int = 12,
        channel: str = "feishu",
        user_id: int | None = None,
    ) -> AgentSignalNotificationScanResponse:
        board = LowBuyScreenerService().priority_board(db=db, limit=limit)
        items = list(getattr(board, "items", []) or [])
        stats = _ScanStats(channel=channel, scanned=len(items))

        for item in items:
            try:
                response = self.notifier.send_signal(
                    db,
                    _request_from_priority_item(item, channel=channel),
                    user_id=user_id,
                )
                if response.should_notify:
                    stats.sent += 1
                else:
                    stats.suppressed += 1
                if response.upgraded:
                    stats.upgraded += 1
            except Exception as exc:  # keep scan best-effort; details stay in logs
                logger.exception("agent signal notification scan failed for priority item")
                stats.errors.append(f"{getattr(item, 'symbol', '--')}: 通知处理失败")
        return stats.to_response()


class _ScanStats:
    def __init__(self, *, channel: str, scanned: int) -> None:
        self.channel = channel
        self.scanned = scanned
        self.sent = 0
        self.suppressed = 0
        self.upgraded = 0
        self.errors: list[str] = []

    def to_response(self) -> AgentSignalNotificationScanResponse:
        return AgentSignalNotificationScanResponse(
            ok=not self.errors,
            channel=self.channel,
            scanned=self.scanned,
            sent=self.sent,
            suppressed=self.suppressed,
            upgraded=self.upgraded,
            errors=self.errors,
            message=f"扫描 {self.scanned} 条，发送 {self.sent} 条，抑制 {self.suppressed} 条。",
        )


def _request_from_priority_item(item: Any, *, channel: str) -> AgentSignalNotificationRequest:
    payload = item.model_dump() if hasattr(item, "model_dump") else dict(item)
    strategy_titles = payload.get("strategy_titles") or []
    strategy_keys = payload.get("strategy_keys") or []
    strategy_title = str(strategy_titles[0]) if strategy_titles else str(payload.get("strategy_title") or "")
    strategy_key = str(strategy_keys[0]) if strategy_keys else str(payload.get("strategy_key") or "")
    signal_state = str(payload.get("buy_signal_state") or payload.get("action_state") or "watch")
    signal_text = str(payload.get("buy_signal_text") or payload.get("action_text") or "观察")
    symbol = str(payload.get("symbol") or "").strip()
    name = str(payload.get("name") or symbol).strip()
    return AgentSignalNotificationRequest(
        channel=channel,
        symbol=symbol,
        name=name,
        strategy_key=strategy_key,
        strategy_title=strategy_title,
        signal_state=signal_state,
        signal_text=signal_text,
        event_type="priority_board",
        payload=_compact_payload(payload),
        message=f"{name} {symbol} | {strategy_title or strategy_key or '优先级榜'} | {signal_text}",
    )


def _compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "rank",
        "symbol",
        "name",
        "priority_score",
        "latest_price",
        "change_pct",
        "buy_signal_state",
        "buy_signal_text",
        "entry_zone",
        "stop_loss",
        "suggested_position_text",
    )
    return {key: payload.get(key) for key in keys if key in payload}
