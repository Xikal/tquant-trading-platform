from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import PaperAccount, RiskEvent
from app.models.schema_defs.research import RiskEventOut
from app.services.paper.performance import PaperPerformanceService


class PaperRiskCircuitBreaker:
    """Persist plain-language risk events for the paper account."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate_account(self, account_id: int) -> list[RiskEventOut]:
        events = []
        overall = PaperPerformanceService(self.db).compute_overall(account_id)
        drawdown = float(overall.get("max_drawdown_pct") or 0.0)
        net_win_rate = float(overall.get("net_win_rate_pct") or 0.0)
        if drawdown <= -8:
            events.append(
                self._ensure_event(
                    account_id=account_id,
                    event_type="drawdown_limit",
                    severity="high" if drawdown <= -12 else "medium",
                    message=f"模拟盘最大回撤 {drawdown:.2f}%，建议暂停新增委托并复盘。",
                    payload={"max_drawdown_pct": drawdown},
                )
            )
        if net_win_rate < -20 and int(overall.get("total_trades") or 0) >= 8:
            events.append(
                self._ensure_event(
                    account_id=account_id,
                    event_type="negative_expectancy",
                    severity="medium",
                    message=f"模拟盘净胜率 {net_win_rate:.2f}%，近期策略执行质量偏弱。",
                    payload={"net_win_rate_pct": net_win_rate},
                )
            )
        streak = self._recent_loss_streak(account_id)
        if streak >= 3:
            events.append(
                self._ensure_event(
                    account_id=account_id,
                    event_type="loss_streak",
                    severity="high",
                    message=f"最近连续 {streak} 次卖出亏损，模拟账户已暂停新增委托，请先复盘。",
                    payload={"loss_streak": streak},
                )
            )
        if any(item.severity == "high" for item in events):
            self._pause_account(account_id)
        self.db.commit()
        return [_event_out(row) for row in events]

    def list_open_events(self, account_id: int, limit: int = 50) -> list[RiskEventOut]:
        rows = (
            self.db.execute(
                select(RiskEvent)
                .where(RiskEvent.account_id == account_id, RiskEvent.status == "open")
                .order_by(RiskEvent.triggered_at.desc())
                .limit(max(1, min(limit, 100)))
            )
            .scalars()
            .all()
        )
        return [_event_out(row) for row in rows]

    def _ensure_event(
        self,
        *,
        account_id: int,
        event_type: str,
        severity: str,
        message: str,
        payload: dict,
    ) -> RiskEvent:
        row = (
            self.db.execute(
                select(RiskEvent).where(
                    RiskEvent.account_id == account_id,
                    RiskEvent.event_type == event_type,
                    RiskEvent.status == "open",
                )
            )
            .scalars()
            .first()
        )
        if row is None:
            row = RiskEvent(account_id=account_id, event_type=event_type, status="open")
            self.db.add(row)
        row.severity = severity
        row.message = message
        row.payload_json = json.dumps(payload, ensure_ascii=False)
        row.triggered_at = datetime.now()
        return row

    def _recent_loss_streak(self, account_id: int) -> int:
        rows = PaperPerformanceService(self.db).sell_return_records(account_id)[-6:]
        streak = 0
        for row in reversed(rows):
            if row.return_pct < 0:
                streak += 1
                continue
            break
        return streak

    def _pause_account(self, account_id: int) -> None:
        account = self.db.get(PaperAccount, account_id)
        if account is not None:
            account.status = "paused"


def _event_out(row: RiskEvent) -> RiskEventOut:
    return RiskEventOut(
        id=row.id,
        account_id=row.account_id,
        symbol=row.symbol or "",
        event_type=row.event_type,
        severity=row.severity,
        status=row.status,
        message=row.message,
        triggered_at=row.triggered_at,
    )
