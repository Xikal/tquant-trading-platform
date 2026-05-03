from __future__ import annotations

from decimal import Decimal
import logging

from app.services.intraday_confirmation_service import IntradayConfirmationService
from app.services.paper.order import PaperOrderService


logger = logging.getLogger(__name__)


class PaperTradingExecutor:
    def __init__(self, order_service: PaperOrderService) -> None:
        self.order_service = order_service

    def execute_plan(self, *, account_id: int, planned_orders: list[dict], max_orders: int = 5, dry_run: bool = False) -> dict:
        executed: list[dict] = []
        skipped: list[dict] = []
        try:
            for payload in planned_orders[:max_orders]:
                if dry_run:
                    skipped.append({"symbol": payload.get("symbol"), "reason": "dry_run，仅校验不执行"})
                    continue
                try:
                    with self.order_service.db.begin_nested():
                        intraday_confirmed = self._intraday_confirmed(payload)
                        order = self.order_service.create_order(
                            account_id=account_id,
                            symbol=str(payload["symbol"]),
                            name=str(payload.get("name") or payload["symbol"]),
                            side=str(payload.get("side") or "buy"),
                            order_type=str(payload.get("order_type") or "market"),
                            quantity=int(payload["quantity"]),
                            price=Decimal(str(payload["price"])) if payload.get("price") else None,
                            source=str(payload.get("source") or "scheduled"),
                            strategy_key=str(payload.get("strategy_key") or ""),
                            reason=str(payload.get("reason") or ""),
                            signal_snapshot=dict(payload.get("signal_snapshot") or {}),
                            current_price=Decimal(str(payload["current_price"])),
                            quote_time=payload["quote_time"],
                            is_suspended=bool(payload.get("is_suspended") or False),
                            intraday_confirmed=intraday_confirmed,
                            commit=False,
                        )
                    executed.append({"order_id": order.id, "symbol": order.symbol, "status": order.status})
                except ValueError as exc:
                    skipped.append({"symbol": payload.get("symbol"), "reason": str(exc)})
            self.order_service.db.commit()
        except Exception:
            self.order_service.db.rollback()
            logger.exception("paper auto execution batch failed and was rolled back")
            raise
        return {
            "executed": executed,
            "skipped": skipped,
            "summary": f"执行 {len(executed)} 条，跳过 {len(skipped)} 条。",
        }

    def _intraday_confirmed(self, payload: dict) -> bool:
        if payload.get("side", "buy") != "buy" or not payload.get("require_intraday_confirmation"):
            return True
        symbol = str(payload.get("symbol") or "").strip()
        if not symbol:
            return False
        confirmations = IntradayConfirmationService(self.order_service.db).confirm_symbols(
            [symbol],
            period="1m",
            limit=120,
        )
        return bool(confirmations and (confirmations[0].confirmed or confirmations[0].late_confirmed))
