from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.paper_shared import agent_run_out, auto_trading_account_context
from app.core.admin_auth import require_admin_auth
from app.core.config import get_settings
from app.core.database import get_db
from app.core.paper_auth import require_paper_trading
from app.models.entities import PaperAgentRun, User
from app.models.schemas import PaperAgentRunOut
from app.services.paper import PaperAccountService
from app.services.paper.scheduler import (
    PaperAutoTrader,
    build_auto_trader_config,
    ensure_auto_trader,
    get_auto_trader,
    is_trading_time,
    start_auto_trader,
    stop_auto_trader,
)

router = APIRouter()


@router.get("/auto-trading/status")
def get_auto_trading_status(
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    trading_time = is_trading_time()
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    account_context = auto_trading_account_context(db, account.id)
    trader = ensure_auto_trader(build_auto_trader_config(settings)) if settings.paper_auto_trading_enabled else get_auto_trader()
    if trader is None:
        payload = {
            "running": False,
            "engine_running": False,
            "trading_time": trading_time,
            "reason": "非交易时段，交易时间自动开启" if settings.paper_auto_trading_enabled else "未启动",
        }
        payload.update(account_context)
        return payload
    payload = trader.state.to_dict()
    engine_running = bool(payload.get("running"))
    payload["engine_running"] = engine_running
    payload["trading_time"] = trading_time
    payload["running"] = engine_running and trading_time
    payload.update(account_context)
    if not trading_time:
        payload["reason"] = "非交易时段，交易时间自动开启"
    elif account_context.get("blocking_reason"):
        payload["reason"] = f"未买原因：{account_context['blocking_reason']}"
    elif not engine_running:
        payload["reason"] = "未启动"
    return payload


@router.get("/auto-trading/runs", response_model=list[PaperAgentRunOut])
def list_auto_trading_runs(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> list[PaperAgentRunOut]:
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    rows = db.execute(
        select(PaperAgentRun)
        .where(PaperAgentRun.account_id == account.id)
        .order_by(PaperAgentRun.id.desc())
        .limit(limit)
    ).scalars().all()
    return [agent_run_out(row) for row in rows]


@router.post("/auto-trading/start")
def start_auto_trading(
    dry_run: Optional[bool] = Query(None, description="是否以空跑模式启动；不传则使用系统默认配置"),
    current_user: User = Depends(require_paper_trading),
    _: None = Depends(require_admin_auth),
) -> dict:
    existing = get_auto_trader()
    if existing and existing.state.running:
        return {"started": False, "reason": "已在运行中"}
    settings = get_settings()
    trader = start_auto_trader(
        build_auto_trader_config(settings, dry_run=dry_run)
    )
    return {"started": True, "dry_run": trader.state.dry_run}


@router.post("/auto-trading/stop")
def stop_auto_trading(
    current_user: User = Depends(require_paper_trading),
    _: None = Depends(require_admin_auth),
) -> dict:
    trader = get_auto_trader()
    if trader is None or not trader.state.running:
        return {"stopped": False, "reason": "未在运行"}
    stop_auto_trader()
    return {"stopped": True}


@router.post("/auto-trading/dry-run")
def dry_run_auto_trading(
    limit: int = Query(20, ge=1, le=50, description="最多检查多少个优先级信号"),
    current_user: User = Depends(require_paper_trading),
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    trader = PaperAutoTrader(
        build_auto_trader_config(settings, dry_run=True)
    )
    account = PaperAccountService(db).get_or_create_default(current_user.id)
    return trader.run_once_for_preview(db=db, limit=limit, account_id=account.id)
