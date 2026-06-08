from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.paper_serializers import (
    account_out_with_positions_overlay,
    order_out,
    paper_position_live_overlays,
    position_out,
    trade_out,
)
from app.api.routes.paper_shared import agent_run_out, auto_trading_account_context, market_data
from app.core.config import get_settings
from app.models.entities import PaperAgentRun, PaperTrade
from app.models.schema_defs.paper import (
    PaperGroupedPerformanceOut,
    PaperPerformanceOut,
    PaperStockPnlResponse,
)
from app.models.schema_defs.research import RiskEventOut
from app.services.market.parameter_defaults import MARKET_SECTOR_ETF_T0_DEFAULTS
from app.services.paper import PaperAccountService, PaperOrderService, PaperPerformanceService, PaperPositionService
from app.services.paper.risk_circuit import PaperRiskCircuitBreaker
from app.services.paper.scheduler import build_auto_trader_config, ensure_auto_trader, get_auto_trader, is_trading_time
from app.services.paper.stock_pnl import PaperStockPnlService
from app.services.quant.runtime_parameters import get_market_sector_etf_t0


class AppMobilePaperMixin:
    def paper_summary(self, db: Session, *, user_id: int) -> dict:
        settings = get_settings()
        account_service = PaperAccountService(db)
        account = account_service.get_or_create_default(user_id)
        if settings.paper_auto_trading_enabled:
            account = account_service.resume_if_safe_for_auto_trading(account.id)
        account_service.update_market_value(account.id)
        db.commit()
        db.refresh(account)

        position_service = PaperPositionService(db)
        position_rows = position_service.get_positions(account.id)
        position_overlays = paper_position_live_overlays(position_rows, market_data=market_data)
        order_rows = PaperOrderService(db).get_orders(account_id=account.id, limit=80)
        trade_rows = (
            db.execute(
                select(PaperTrade)
                .where(PaperTrade.account_id == account.id)
                .order_by(PaperTrade.trade_time.desc())
                .limit(80)
            )
            .scalars()
            .all()
        )
        performance_service = PaperPerformanceService(db)
        stock_pnl = PaperStockPnlResponse(**PaperStockPnlService(db).summary(account.id))
        risk_events = PaperRiskCircuitBreaker(db).list_open_events(account.id, limit=8)

        return {
            "account": account_out_with_positions_overlay(account, position_rows, position_overlays, db=db),
            "positions": [
                position_out(row, db=db, quote_overlay=position_overlays.get(str(row.symbol or "")))
                for row in position_rows
            ],
            "orders": [order_out(row) for row in order_rows],
            "trades": [trade_out(row) for row in trade_rows],
            "performance": PaperPerformanceOut(**performance_service.compute_overall(account.id)),
            "strategy_performance": [
                PaperGroupedPerformanceOut(**item)
                for item in performance_service.compute_by_strategy(account.id)
            ],
            "market_performance": [
                PaperGroupedPerformanceOut(**item)
                for item in performance_service.compute_by_market_state(account.id)
            ],
            "stock_pnl": stock_pnl,
            "auto_trading_status": self._auto_trading_status(db, account.id),
            "recent_runs": self._recent_runs(db, account.id),
            "risk_events": [RiskEventOut.model_validate(item) for item in risk_events],
        }

    def _auto_trading_status(self, db: Session, account_id: int) -> dict:
        settings = get_settings()
        trading_time = is_trading_time()
        account_context = auto_trading_account_context(db, account_id)
        trader = (
            ensure_auto_trader(build_auto_trader_config(settings))
            if settings.paper_auto_trading_enabled
            else get_auto_trader()
        )
        if trader is None:
            payload = {
                "running": False,
                "engine_running": False,
                "trading_time": trading_time,
                "reason": "非交易时段，交易时间自动开启" if settings.paper_auto_trading_enabled else "未启动",
            }
        else:
            payload = trader.state.to_dict()
            engine_running = bool(payload.get("running"))
            payload["engine_running"] = engine_running
            payload["trading_time"] = trading_time
            payload["running"] = engine_running and trading_time
            if not trading_time:
                payload["reason"] = "非交易时段，交易时间自动开启"
            elif account_context.get("blocking_reason"):
                payload["reason"] = f"未买原因：{account_context['blocking_reason']}"
            elif not engine_running:
                payload["reason"] = "未启动"
        payload.update(self._sector_etf_t0_auto_config())
        payload.update(account_context)
        return payload

    def _recent_runs(self, db: Session, account_id: int) -> list[dict]:
        rows = (
            db.execute(
                select(PaperAgentRun)
                .where(PaperAgentRun.account_id == account_id)
                .order_by(PaperAgentRun.id.desc())
                .limit(8)
            )
            .scalars()
            .all()
        )
        return [agent_run_out(row).model_dump(mode="json") for row in rows]

    @staticmethod
    def _sector_etf_t0_auto_config() -> dict:
        try:
            values = get_market_sector_etf_t0()
        except Exception:
            values = {}
        params = {**MARKET_SECTOR_ETF_T0_DEFAULTS, **values} if isinstance(values, dict) else dict(MARKET_SECTOR_ETF_T0_DEFAULTS)
        return {
            "sector_etf_t0_auto_enabled": bool(params.get("paper_auto_enabled", True)),
            "sector_etf_t0_max_orders": int(params.get("paper_auto_max_orders") or 0),
            "sector_etf_t0_cash_pct": float(params.get("paper_auto_cash_pct") or 0.0) * 100,
            "sector_etf_t0_min_confidence": float(params.get("paper_auto_min_confidence") or 0.0),
            "sector_etf_t0_min_edge_pct": float(params.get("paper_auto_min_edge_pct") or 0.0),
        }
