from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.paper_serializers import account_out, order_out, position_out, trade_out
from app.api.routes.paper_shared import agent_run_out, auto_trading_account_context
from app.core.config import get_settings
from app.core.timezone import beijing_now_string
from app.models.entities import PaperAgentRun, PaperTrade, User
from app.models.schema_defs.bff import BffPartialError, PaperWorkspaceBffResponse
from app.models.schema_defs.paper import (
    PaperGroupedPerformanceOut,
    PaperPerformanceOut,
    PaperSectorEtfT0PerformanceOut,
    PaperStockPnlResponse,
    PaperTagPerformanceOut,
)
from app.models.schema_defs.research import RiskEventOut
from app.services.market_model_observation_service import MarketModelObservationService
from app.services.paper import PaperAccountService, PaperOrderService, PaperPerformanceService, PaperPositionService
from app.services.paper.risk_circuit import PaperRiskCircuitBreaker
from app.services.paper.scheduler import build_auto_trader_config, ensure_auto_trader, get_auto_trader, is_trading_time
from app.services.paper.stock_pnl import PaperStockPnlService


def build_paper_workspace(
    db: Session,
    *,
    current_user: User,
    order_limit: int,
    trade_limit: int,
    run_limit: int,
) -> PaperWorkspaceBffResponse:
    """Build the paper trading first-screen payload in one BFF read."""

    errors: list[BffPartialError] = []
    account = _safe("account", errors, lambda: _account(db, current_user))
    account_id = account.id if account is not None else None
    return PaperWorkspaceBffResponse(
        generated_at=beijing_now_string(),
        account=account,
        positions=_safe("positions", errors, lambda: _positions(db, account_id)) or [],
        orders=_safe("orders", errors, lambda: _orders(db, account_id, order_limit)) or [],
        trades=_safe("trades", errors, lambda: _trades(db, account_id, trade_limit)) or [],
        stock_pnl=_safe("stock_pnl", errors, lambda: _stock_pnl(db, account_id)),
        performance=_safe("performance", errors, lambda: _performance(db, account_id)),
        sector_etf_t0_performance=_safe("sector_etf_t0", errors, lambda: _sector_etf_t0(db, account_id)),
        strategy_performance=_safe("strategy_performance", errors, lambda: _strategy_performance(db, account_id)) or [],
        market_performance=_safe("market_performance", errors, lambda: _market_performance(db, account_id)) or [],
        tag_performance=_safe("tag_performance", errors, lambda: _tag_performance(db, account_id)) or [],
        risk_events=_safe("risk_events", errors, lambda: _risk_events(db, account_id)) or [],
        auto_trading_status=_safe("auto_trading_status", errors, lambda: _auto_trading_status(db, account_id)) or {},
        auto_trading_runs=_safe("auto_trading_runs", errors, lambda: _auto_trading_runs(db, account_id, run_limit)) or [],
        partial_errors=errors,
    )


def _account(db: Session, current_user: User):
    service = PaperAccountService(db)
    account = service.get_or_create_default(current_user.id)
    if get_settings().paper_auto_trading_enabled:
        account = service.resume_if_safe_for_auto_trading(account.id)
    service.update_market_value(account.id)
    db.commit()
    db.refresh(account)
    return account_out(account, db=db)


def _positions(db: Session, account_id: int | None):
    if account_id is None:
        return []
    return [position_out(row, db=db) for row in PaperPositionService(db).get_positions(account_id)]


def _orders(db: Session, account_id: int | None, limit: int):
    if account_id is None:
        return []
    rows = PaperOrderService(db).get_orders(account_id=account_id, limit=limit)
    return [order_out(row) for row in rows]


def _trades(db: Session, account_id: int | None, limit: int):
    if account_id is None:
        return []
    rows = db.execute(
        select(PaperTrade)
        .where(PaperTrade.account_id == account_id)
        .order_by(PaperTrade.trade_time.desc())
        .limit(limit)
    ).scalars().all()
    return [trade_out(row) for row in rows]


def _stock_pnl(db: Session, account_id: int | None):
    if account_id is None:
        return None
    PaperAccountService(db).update_market_value(account_id)
    return PaperStockPnlResponse(**PaperStockPnlService(db).summary(account_id))


def _performance(db: Session, account_id: int | None):
    if account_id is None:
        return None
    service = PaperPerformanceService(db)
    payload = service.compute_overall(account_id)
    payload["portfolio_execution_preview"] = service.compute_portfolio_execution_preview(account_id)
    return PaperPerformanceOut(**payload)


def _sector_etf_t0(db: Session, account_id: int | None):
    if account_id is None:
        return None
    simulated = PaperPerformanceService(db).compute_sector_etf_t0(account_id)
    shadow = MarketModelObservationService().summarize(db, model_key="sector_etf_t0", lookback_days=60)
    return PaperSectorEtfT0PerformanceOut(
        **simulated,
        shadow_sample_count=int(shadow["sample_count"]),
        shadow_settled_count=int(shadow["settled_count"]),
        shadow_pending_count=int(shadow["pending_count"]),
        shadow_success_rate_pct=round(float(shadow["success_rate_pct"] or 0.0), 2),
        shadow_avg_return_1d_pct=round(float(shadow["avg_return_1d_pct"] or 0.0), 2),
        shadow_avg_return_3d_pct=round(float(shadow["avg_return_3d_pct"] or 0.0), 2),
    )


def _strategy_performance(db: Session, account_id: int | None):
    return _grouped(db, account_id, "strategy")


def _market_performance(db: Session, account_id: int | None):
    return _grouped(db, account_id, "market")


def _tag_performance(db: Session, account_id: int | None):
    if account_id is None:
        return []
    return [PaperTagPerformanceOut(**item) for item in PaperPerformanceService(db).compute_by_tag(account_id)]


def _grouped(db: Session, account_id: int | None, kind: str):
    if account_id is None:
        return []
    service = PaperPerformanceService(db)
    rows = service.compute_by_strategy(account_id) if kind == "strategy" else service.compute_by_market_state(account_id)
    return [PaperGroupedPerformanceOut(**item) for item in rows]


def _risk_events(db: Session, account_id: int | None):
    if account_id is None:
        return []
    return [RiskEventOut(**row.__dict__) for row in PaperRiskCircuitBreaker(db).evaluate_account(account_id)]


def _auto_trading_runs(db: Session, account_id: int | None, limit: int):
    if account_id is None:
        return []
    rows = db.execute(
        select(PaperAgentRun)
        .where(PaperAgentRun.account_id == account_id)
        .order_by(PaperAgentRun.id.desc())
        .limit(limit)
    ).scalars().all()
    return [agent_run_out(row) for row in rows]


def _auto_trading_status(db: Session, account_id: int | None) -> dict:
    if account_id is None:
        return {}
    settings = get_settings()
    trading_time = is_trading_time()
    trader = ensure_auto_trader(build_auto_trader_config(settings)) if settings.paper_auto_trading_enabled else get_auto_trader()
    account_context = auto_trading_account_context(db, account_id)
    if trader is None:
        payload = {"running": False, "engine_running": False, "trading_time": trading_time}
    else:
        payload = trader.state.to_dict()
        engine_running = bool(payload.get("running"))
        payload.update({"engine_running": engine_running, "trading_time": trading_time, "running": engine_running and trading_time})
    payload.update(account_context)
    return payload


def _safe(source: str, errors: list[BffPartialError], loader):
    try:
        return loader()
    except Exception:
        errors.append(BffPartialError(source=source, detail="数据暂时不可用"))
        return None
