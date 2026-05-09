from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import PaperAccount
from app.services.market_data import MarketDataService
from app.services.paper.scheduler_helpers import (
    _beijing_now_naive,
    _float_param,
    _round_lot,
    _sector_etf_t0_params,
    _today_order_symbols,
)
from app.services.sector_etf_t0 import SectorEtfT0Service

logger = logging.getLogger(__name__)


def build_sector_etf_t0_orders(
    *,
    db: Session,
    account: PaperAccount,
    board: dict[str, Any],
    today_orders: list[dict[str, Any]],
    used_order_count: int,
    max_orders_per_cycle: int,
    etf_service_cls=SectorEtfT0Service,
) -> list[dict[str, Any]]:
    params = _sector_etf_t0_params()
    if not bool(params.get("paper_auto_enabled", True)):
        return []
    if str(board.get("market_state") or "") in set(params.get("paper_auto_blocked_market_states") or []):
        return []
    remaining_slots = min(
        max(int(params.get("paper_auto_max_orders") or 0), 0),
        max(max_orders_per_cycle - used_order_count, 0),
    )
    if remaining_slots <= 0 or float(account.cash_available or 0) <= 0:
        return []
    today_symbols = _today_order_symbols(today_orders)
    etf_service = etf_service_cls(market_data=MarketDataService(), low_buy=None)
    if db is not None:
        acceptance = etf_service.historical_acceptance(db, params=params)
        if not acceptance.get("production_ready"):
            logger.info(
                "ETF T+0 自动执行未通过统计验收：settled=%s success_rate=%.2f p=%.4f",
                acceptance.get("settled_count"),
                float(acceptance.get("success_rate_pct") or 0.0),
                float(acceptance.get("p_value") or 1.0),
            )
            return []
    response = etf_service.build_from_priority_board(
        board,
        limit=max(remaining_slots * 2, 2),
    )
    orders: list[dict[str, Any]] = []
    cash_budget = float(account.cash_available or 0) * _float_param(params, "paper_auto_cash_pct", 0.12)
    min_confidence = _float_param(params, "paper_auto_min_confidence", 68.0)
    min_edge = _float_param(params, "paper_auto_min_edge_pct", 0.9)
    now = _beijing_now_naive()
    for item in response.opportunities:
        if len(orders) >= remaining_slots:
            break
        if item.etf_symbol in today_symbols or item.bias != "positive_t":
            continue
        if item.confidence < min_confidence or item.expected_edge_pct < min_edge or item.last_price <= 0:
            continue
        quantity = _round_lot(cash_budget / item.last_price)
        if quantity < 100:
            continue
        orders.append(
            {
                "symbol": item.etf_symbol,
                "name": item.etf_name,
                "side": "buy",
                "order_type": "market",
                "quantity": quantity,
                "price": item.last_price,
                "current_price": item.last_price,
                "quote_time": now,
                "source": "auto_sector_etf_t0",
                "strategy_key": "sector_etf_t0",
                "reason": f"自动调入: 行业ETF T+0，{item.reason}",
                "signal_snapshot": {
                    **item.model_dump(),
                    "strategy_key": "sector_etf_t0",
                    "market_state": board.get("market_state"),
                    "position_cap_source": "sector_etf_t0_cash_budget",
                    "position_cap_reason": f"ETF T+0 单笔使用可用资金约 {cash_budget:.0f} 元上限",
                },
            }
        )
    return orders
