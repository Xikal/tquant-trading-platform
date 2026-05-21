from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import beijing_now
from app.models.entities import BacktestRun, BacktestTrade, PaperAccount
from app.services.paper.performance import PaperPerformanceService


def build_live_backtest_comparison(
    db: Session,
    *,
    user_id: int,
    account_id: int | None = None,
    days: int = 60,
    min_trades: int = 3,
) -> dict[str, Any]:
    account = _resolve_account(db, user_id=user_id, account_id=account_id)
    if account is None:
        return {"ok": True, "items": [], "alerts": [], "summary": "未找到模拟账户，无法对比实盘/回测损耗。"}
    live = _live_strategy_returns(db, int(account.id), days=max(days, 1))
    backtest = _latest_backtest_strategy_returns(db, user_id=user_id)
    items: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    for strategy_key in sorted(set(live) | set(backtest)):
        live_values = live.get(strategy_key, [])
        bt_values = backtest.get(strategy_key, [])
        item = _comparison_item(strategy_key, live_values, bt_values, min_trades=min_trades)
        items.append(item)
        if item["status"] in {"degraded", "insufficient_live"}:
            alerts.append(
                {
                    "strategy_key": strategy_key,
                    "level": "warning" if item["status"] == "degraded" else "info",
                    "message": item["message"],
                }
            )
    return {
        "ok": True,
        "account_id": int(account.id),
        "lookback_days": max(days, 1),
        "items": items,
        "alerts": alerts,
        "summary": _summary(items, alerts),
        "generated_at": beijing_now().isoformat(timespec="seconds"),
    }


def _resolve_account(db: Session, *, user_id: int | None, account_id: int | None) -> PaperAccount | None:
    if user_id is None:
        return None
    if account_id is not None:
        row = db.get(PaperAccount, int(account_id))
        if row is not None and row.user_id in {None, user_id}:
            return row
        return None
    statement = select(PaperAccount).order_by(PaperAccount.id.asc())
    statement = statement.where(PaperAccount.user_id.in_([user_id, None]))
    return db.execute(statement.limit(1)).scalars().first()


def _live_strategy_returns(db: Session, account_id: int, *, days: int) -> dict[str, list[float]]:
    cutoff = beijing_now().date() - timedelta(days=days)
    records = PaperPerformanceService(db).sell_return_records(account_id)
    grouped: dict[str, list[float]] = defaultdict(list)
    for item in records:
        if item.trade_time and item.trade_time.date() < cutoff:
            continue
        grouped[item.strategy_key or "未分类"].append(float(item.return_pct))
    return dict(grouped)


def _latest_backtest_strategy_returns(db: Session, *, user_id: int) -> dict[str, list[float]]:
    run_statement = (
        select(BacktestRun.id)
        .where(BacktestRun.status.in_(["succeeded", "completed"]), BacktestRun.deleted_at.is_(None))
        .order_by(BacktestRun.finished_at.desc().nullslast(), BacktestRun.id.desc())
        .limit(5)
    )
    run_statement = run_statement.where(BacktestRun.owner_user_id.in_([user_id, None]))
    run_ids = [int(value) for value in db.execute(run_statement).scalars().all()]
    if not run_ids:
        return {}
    rows = db.execute(
        select(BacktestTrade.strategy_key, BacktestTrade.pnl_pct)
        .where(BacktestTrade.run_id.in_(run_ids), BacktestTrade.strategy_key != "")
    ).all()
    grouped: dict[str, list[float]] = defaultdict(list)
    for strategy_key, pnl_pct in rows:
        if pnl_pct is not None:
            grouped[str(strategy_key)].append(float(pnl_pct))
    return dict(grouped)


def _comparison_item(strategy_key: str, live_values: list[float], backtest_values: list[float], *, min_trades: int) -> dict[str, Any]:
    live_avg = _avg(live_values)
    bt_avg = _avg(backtest_values)
    gap = live_avg - bt_avg if live_values and backtest_values else 0.0
    status = "ok"
    message = "模拟成交与最近回测表现基本一致。"
    if len(live_values) < min_trades:
        status = "insufficient_live"
        message = f"模拟成交样本不足：{len(live_values)}/{min_trades}。"
    elif backtest_values and gap < -1.0:
        status = "degraded"
        message = f"模拟成交均收低于回测 {abs(gap):.2f} 个百分点，建议复盘滑点和信号失效。"
    return {
        "strategy_key": strategy_key,
        "live_trade_count": len(live_values),
        "backtest_trade_count": len(backtest_values),
        "live_avg_return_pct": round(live_avg, 3),
        "backtest_avg_return_pct": round(bt_avg, 3),
        "return_gap_pct": round(gap, 3),
        "status": status,
        "message": message,
    }


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _summary(items: list[dict[str, Any]], alerts: list[dict[str, Any]]) -> str:
    if not items:
        return "暂无可对比的模拟成交和回测样本。"
    if alerts:
        return f"发现 {len(alerts)} 条策略表现差异或样本不足提示。"
    return "模拟成交与最近回测口径未发现明显偏离。"
