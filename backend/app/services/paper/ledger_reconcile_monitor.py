from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import PaperAccount
from app.models.schema_defs.agent import AgentNotificationTestRequest
from app.services.agent_notification_service import AgentNotificationService
from app.services.paper.ledger_repair import PaperLedgerRepairService
from app.services.paper.money import to_decimal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LedgerReconcileAlert:
    account_id: int
    account_name: str
    reconciliation_gap: Decimal


class PaperLedgerReconcileMonitorService:
    """Daily preview-only reconciliation checks for paper accounts."""

    def __init__(
        self,
        db: Session,
        *,
        notifier: AgentNotificationService | None = None,
    ) -> None:
        self.db = db
        self.notifier = notifier or AgentNotificationService()

    def run_daily_preview(
        self,
        *,
        threshold: Decimal | float = Decimal("1.0"),
        channel: str = "feishu",
    ) -> dict[str, Any]:
        threshold_value = abs(to_decimal(threshold))
        alerts: list[LedgerReconcileAlert] = []
        errors: list[dict[str, Any]] = []
        accounts = self._active_accounts()
        preview_service = PaperLedgerRepairService(self.db)
        for account in accounts:
            try:
                result = preview_service.preview(account.id)
            except Exception as exc:  # pragma: no cover - defensive path
                logger.warning("paper ledger preview failed for account %s: %s", account.id, exc)
                errors.append({"account_id": account.id, "account_name": account.name, "error": str(exc)})
                continue
            gap = abs(to_decimal(result.reconciliation_gap_before))
            if gap >= threshold_value:
                alerts.append(
                    LedgerReconcileAlert(
                        account_id=account.id,
                        account_name=account.name,
                        reconciliation_gap=gap.quantize(Decimal("0.01")),
                    )
                )

        sent = False
        message = ""
        if alerts:
            message = self._build_message(alerts=alerts, threshold=threshold_value)
            if self.notifier.supports_channel(channel):
                response = self.notifier.send_test(AgentNotificationTestRequest(channel=channel, message=message))
                sent = bool(response.ok)
                if not response.ok:
                    logger.warning("paper ledger reconcile alert delivery failed: %s", response.message)
            else:
                logger.warning("paper ledger reconcile alert skipped: %s not configured", channel)

        return {
            "ok": True,
            "channel": channel,
            "accounts_checked": len(accounts),
            "alert_count": len(alerts),
            "alerts_sent": sent,
            "threshold": float(threshold_value),
            "alerts": [
                {
                    "account_id": item.account_id,
                    "account_name": item.account_name,
                    "reconciliation_gap": float(item.reconciliation_gap),
                }
                for item in alerts
            ],
            "errors": errors,
            "message": message,
        }

    def _active_accounts(self) -> list[PaperAccount]:
        return (
            self.db.execute(
                select(PaperAccount)
                .where(PaperAccount.status == "active")
                .order_by(PaperAccount.id.asc())
            )
            .scalars()
            .all()
        )

    def _build_message(self, *, alerts: list[LedgerReconcileAlert], threshold: Decimal) -> str:
        lines = [
            "TQuant 模拟盘自动对账告警",
            f"阈值: {threshold.quantize(Decimal('0.01'))} 元",
        ]
        for item in alerts[:10]:
            lines.append(
                f"- 账户 {item.account_name or item.account_id} (#{item.account_id}) 对账差额 {item.reconciliation_gap} 元"
            )
        if len(alerts) > 10:
            lines.append(f"- 其余 {len(alerts) - 10} 个账户请登录后台查看")
        return "\n".join(lines)
