from __future__ import annotations

import json
import logging
from dataclasses import replace

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.entities import PaperAccount, RiskEvent
from app.models.schema_defs.agent import AgentNotificationTestRequest
from app.services.agent_notification_service import AgentNotificationService
from app.services.paper.dynamic_exit import evaluate_paper_exit
from app.services.paper.position import PaperPositionService
from app.services.paper.scheduler_exit import latest_intraday_bars, latest_prices
from app.services.paper.smart_exit_context import build_exit_context
from app.services.paper.trailing_stop_state import update_position_trailing_high
from app.services.paper.scheduler_helpers import _beijing_now_naive
from app.services.quant.runtime_parameters import get_paper_dynamic_exit

logger = logging.getLogger(__name__)


def review_portfolios_on_regime_change(previous_state: str, current_state: str) -> None:
    if not _is_risk_jump(previous_state, current_state):
        return
    try:
        _review_all_accounts(previous_state=previous_state, current_state=current_state)
    except Exception:
        logger.warning("市场状态跳变持仓复核失败", exc_info=True)


def _review_all_accounts(*, previous_state: str, current_state: str) -> None:
    with SessionLocal() as db:
        accounts = db.execute(select(PaperAccount).where(PaperAccount.status == "active")).scalars().all()
        for account in accounts:
            _review_account(db, account=account, previous_state=previous_state, current_state=current_state)
        db.commit()


def _review_account(db, *, account: PaperAccount, previous_state: str, current_state: str) -> None:
    positions = PaperPositionService(db).get_positions(account.id)
    if not positions:
        return
    prices = latest_prices([row.symbol for row in positions])
    bars = latest_intraday_bars([row.symbol for row in positions])
    params = get_paper_dynamic_exit()
    trailing_stop_pct = float(params.get("trailing_stop_pct", 2.0) or 2.0)
    now = _beijing_now_naive()
    messages: list[str] = []
    for row in positions:
        quote = prices.get(row.symbol)
        if quote is None or not quote.usable:
            continue
        context = build_exit_context(quote, bars.get(row.symbol))
        high = update_position_trailing_high(
            db,
            account_id=int(account.id),
            position=row,
            current_price=max(float(quote.price or 0.0), float(getattr(quote, "high_price", 0.0) or 0.0)),
        )
        context = replace(
            context,
            trailing_high_price=round(high, 4),
            trailing_stop_price=round(high * (1 - trailing_stop_pct / 100.0), 4) if high > 0 else 0.0,
        )
        decision = evaluate_paper_exit(row, price=quote.price, now=now, context=context)
        if decision.action_signal not in {"scale_out", "profit_take", "hard_stop"} or decision.quantity <= 0:
            continue
        messages.append(f"{row.name or row.symbol}({row.symbol})：{decision.action_text}，建议卖出 {decision.quantity} 股。")
        db.add(
            RiskEvent(
                account_id=account.id,
                symbol=row.symbol,
                event_type="regime_jump_position_review",
                severity="high",
                status="open",
                message=f"市场从 {previous_state} 跳变为 {current_state}，{decision.reason}",
                payload_json=json.dumps(
                    {
                        "previous_state": previous_state,
                        "current_state": current_state,
                        "decision": decision.__dict__,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
        )
    if messages:
        AgentNotificationService().send_test(
            AgentNotificationTestRequest(
                channel="feishu",
                message=f"市场状态跳变：{previous_state} → {current_state}。持仓复核建议：\n" + "\n".join(messages[:8]),
            )
        )


def _is_risk_jump(previous_state: str, current_state: str) -> bool:
    return _risk_rank(current_state) - _risk_rank(previous_state) >= 2


def _risk_rank(state: str) -> int:
    return {
        "broad_rally": 0,
        "repair": 1,
        "weight_support_active": 2,
        "low_volume_wait": 3,
        "weight_support": 3,
        "fast_rotation": 4,
        "high_flyer_retreat": 5,
        "risk_release": 6,
    }.get(state or "", 3)
