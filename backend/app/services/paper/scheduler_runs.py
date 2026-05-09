from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import PaperAgentRun
from app.services.paper.scheduler_helpers import _beijing_now_naive
from app.services.paper.scheduler_state import AutoTraderState

logger = logging.getLogger(__name__)


def start_agent_run(
    db: Session,
    *,
    account_id: int,
    board: dict[str, Any],
    state: AutoTraderState,
) -> PaperAgentRun:
    row = PaperAgentRun(
        account_id=account_id,
        provider="paper_auto_trader",
        run_type="auto_trade_cycle",
        status="running",
        request_json=json.dumps(
            {
                "dry_run": state.dry_run,
                "max_orders_per_cycle": state.max_orders_per_cycle,
                "min_score": state.min_score,
                "signal_count": len(board.get("items") or []),
                "market_state": board.get("market_state"),
                "directional_bias": board.get("directional_bias"),
            },
            ensure_ascii=False,
            default=str,
        ),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def finish_agent_run(
    db: Session,
    run: PaperAgentRun,
    *,
    status: str,
    response: dict[str, Any],
    error: str = "",
) -> None:
    run.status = status
    run.response_json = json.dumps(response, ensure_ascii=False, default=str)
    run.error_message = error[:240]
    db.add(run)
    db.commit()


def record_cycle(
    state: AutoTraderState,
    *,
    passed: int,
    filtered: int,
    summary: str,
    executed: int = 0,
    skipped: int = 0,
) -> None:
    state.last_cycle_at = _beijing_now_naive().isoformat(timespec="seconds")
    state.last_cycle_passed = passed
    state.last_cycle_filtered = filtered
    state.last_cycle_executed = executed
    state.last_cycle_skipped = skipped
    state.last_cycle_summary = summary
    state.total_cycles += 1
    state.total_executed += executed
    if executed > 0:
        logger.info("自动交易循环：%s，通过%d，执行%d", summary, passed, executed)
    elif passed > 0:
        logger.info("自动交易循环：%s，通过%d，跳过%d", summary, passed, skipped)
