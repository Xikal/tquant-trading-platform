from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now
from app.models.entities import PaperAccount, PaperAgentRun, PaperTrade, RiskEvent
from app.models.schemas import PaperAgentRunOut, PaperOrderCreate
from app.services.market_data import DataSourceError, MarketDataService

market_data = MarketDataService()


def resolve_quote(payload: PaperOrderCreate) -> tuple[Decimal, datetime, str]:
    if payload.current_price:
        current_price = Decimal(str(payload.current_price))
        if current_price <= 0:
            raise HTTPException(status_code=400, detail="模拟撮合价格无效。")
        return current_price, payload.quote_time or beijing_now_naive(), payload.name
    try:
        quote = market_data.get_quote(payload.symbol)
    except DataSourceError as exc:
        raise HTTPException(status_code=400, detail=f"无法获取模拟撮合行情: {exc}") from exc
    if bool(getattr(quote, "is_stale", False)):
        raise HTTPException(status_code=400, detail="实时行情时间已过期，模拟委托暂不撮合。")
    quote_price = Decimal(str(quote.last_price))
    if quote_price <= 0:
        raise HTTPException(status_code=400, detail="实时行情价格无效，模拟委托暂不撮合。")
    return quote_price, parse_quote_time(quote.timestamp), quote.name


def parse_quote_time(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return beijing_now_naive()


def beijing_now_naive() -> datetime:
    return beijing_now().replace(tzinfo=None)


def agent_run_out(row: PaperAgentRun) -> PaperAgentRunOut:
    return PaperAgentRunOut(
        id=row.id,
        account_id=row.account_id,
        provider=row.provider,
        run_type=row.run_type,
        status=row.status,
        request=json_dict(row.request_json),
        response=json_dict(row.response_json),
        error_message=row.error_message,
        created_at=row.created_at,
    )


def auto_trading_account_context(db: Session, account_id: int) -> dict[str, object]:
    blocking_reason = latest_blocking_reason(db, account_id)
    account = db.get(PaperAccount, account_id)
    latest_runs = (
        db.execute(
            select(PaperAgentRun)
            .where(PaperAgentRun.account_id == account_id)
            .order_by(PaperAgentRun.id.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )
    latest_skip: dict[str, object] = {}
    latest_skip_at = ""
    for run in latest_runs:
        candidate = extract_latest_skip(run)
        if candidate.get("reason"):
            latest_skip = candidate
            latest_skip_at = run.created_at.isoformat(sep=" ")
            break
    return {
        "account_status": str(account.status if account is not None else ""),
        "blocking_reason": blocking_reason,
        "last_skip_reason": latest_skip.get("reason", ""),
        "last_skip_symbol": latest_skip.get("symbol", ""),
        "last_skip_at": latest_skip_at,
        "last_skip_reasons": latest_skip.get("reasons", []),
    }


def latest_blocking_reason(db: Session, account_id: int) -> str:
    row = (
        db.execute(
            select(RiskEvent)
            .where(
                RiskEvent.account_id == account_id,
                RiskEvent.status == "open",
                RiskEvent.severity.in_(["high", "critical"]),
            )
            .order_by(RiskEvent.triggered_at.desc(), RiskEvent.id.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    return str(row.message or "").strip() if row is not None else ""


def extract_latest_skip(row: PaperAgentRun) -> dict[str, object]:
    payload = json_dict(row.response_json)
    skipped = payload.get("skipped")
    reasons: list[dict[str, str]] = []
    if isinstance(skipped, list):
        for item in skipped:
            if not isinstance(item, dict):
                continue
            reason = str(item.get("reason") or "").strip()
            if not reason:
                continue
            reasons.append(
                {
                    "symbol": str(item.get("symbol") or "").strip(),
                    "reason": reason,
                }
            )
    if not reasons:
        filtered_reasons = payload.get("filtered_reasons")
        if isinstance(filtered_reasons, list):
            for item in filtered_reasons:
                if not isinstance(item, dict):
                    continue
                reason = str(item.get("reason") or "").strip()
                if reason:
                    reasons.append({"symbol": str(item.get("symbol") or "").strip(), "reason": reason})
    first = reasons[0] if reasons else {}
    return {
        "symbol": first.get("symbol", ""),
        "reason": first.get("reason", ""),
        "reasons": reasons[:3],
    }


def json_dict(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def ensure_trade_belongs_to_account(db: Session, trade_id: int, account_id: int) -> PaperTrade:
    trade = db.get(PaperTrade, trade_id)
    if trade is None or trade.account_id != account_id:
        raise HTTPException(status_code=404, detail="模拟成交不存在")
    return trade
