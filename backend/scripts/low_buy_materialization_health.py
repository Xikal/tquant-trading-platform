from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.models.entities import DailyBarSnapshot, LowBuyResultSnapshot
from app.repositories.low_buy import LowBuyResultRepository
from app.services.low_buy.service import LowBuyScreenerService
from app.services.low_buy.shared import LOW_BUY_RESULT_VERSION
from app.services.low_buy.strategy_policy import (
    PRODUCTION_PRIORITY_STRATEGIES,
    STRONG_BUY_PAUSED_STRATEGIES,
)


@dataclass(frozen=True)
class StrategyHealth:
    strategy: str
    latest_trade_date: str
    status: str
    reason: str
    pool_size: int = 0
    result_rows: int = 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="低吸策略物化结果健康检查与重建")
    parser.add_argument(
        "--strategies",
        default=",".join(sorted(PRODUCTION_PRIORITY_STRATEGIES)),
        help="逗号分隔策略列表，默认生产策略",
    )
    parser.add_argument("--limit", type=int, default=16, help="物化读取返回数量")
    parser.add_argument("--scan-limit", type=int, default=480, help="全量扫描上限")
    parser.add_argument("--rebuild-latest", action="store_true", help="重建最新交易日物化结果")
    parser.add_argument(
        "--normalize-paused-strong-buy",
        action="store_true",
        help="将已暂停策略历史强买入物化行降级为接近买点",
    )
    parser.add_argument("--min-daily-symbols", type=int, default=3000, help="最新日线最少股票数")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        init_db()
        service = LowBuyScreenerService()
        strategies = [item.strip() for item in args.strategies.split(",") if item.strip()]
        if args.rebuild_latest:
            _rebuild_latest(service=service, strategies=strategies, limit=args.limit, scan_limit=args.scan_limit)

        with SessionLocal() as db:
            if args.normalize_paused_strong_buy:
                _normalize_paused_strong_buy_rows(db=db)
            daily_status = _daily_data_status(db=db, min_symbols=args.min_daily_symbols)
            strategy_status = [
                _strategy_health(db=db, service=service, strategy=strategy)
                for strategy in strategies
            ]
            paused_pollution = _paused_strong_buy_count(db=db)
    except SQLAlchemyError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "数据库连接失败，无法检查低吸物化结果",
                    "error": str(exc).splitlines()[0],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    payload = {
        "result_version": LOW_BUY_RESULT_VERSION,
        "daily_data": daily_status,
        "strategies": [item.__dict__ for item in strategy_status],
        "paused_strategy_strong_buy_rows": paused_pollution,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    ok = (
        daily_status["ok"]
        and all(item.status == "ok" for item in strategy_status)
        and paused_pollution == 0
    )
    return 0 if ok else 2


def _rebuild_latest(
    *,
    service: LowBuyScreenerService,
    strategies: list[str],
    limit: int,
    scan_limit: int,
) -> None:
    for strategy in strategies:
        payload = service.refresh_full_scan_cache(
            strategy=strategy,
            limit=limit,
            scan_limit=scan_limit,
            include_history=False,
            compute_performance=True,
            build_close_review=True,
        )
        print(
            json.dumps(
                {
                    "rebuilt": strategy,
                    "latest_trade_date": payload.latest_trade_date,
                    "pool_size": payload.pool_size,
                    "matched_count": payload.matched_count,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )


def _strategy_health(
    *,
    db,
    service: LowBuyScreenerService,
    strategy: str,
) -> StrategyHealth:
    repository = LowBuyResultRepository(db)
    summary = repository.fetch_latest_scan_summary(strategy_key=strategy)
    if summary is None:
        return StrategyHealth(strategy=strategy, latest_trade_date="", status="missing", reason="没有物化结果")

    latest_trade_date = str(summary.latest_trade_date)
    is_current = service._runtime._materialized_scan_is_current(  # noqa: SLF001 - ops script checks runtime contract.
        db=db,
        strategy=strategy,
        latest_trade_date=latest_trade_date,
        summary=summary,
    )
    rows = repository.fetch_results(latest_trade_date=latest_trade_date, strategy_key=strategy)
    if not is_current:
        return StrategyHealth(
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            status="stale",
            reason=f"物化结果不是当前版本 {LOW_BUY_RESULT_VERSION}",
            pool_size=int(summary.pool_size or 0),
            result_rows=len(rows),
        )
    if int(summary.pool_size or 0) <= 0:
        return StrategyHealth(
            strategy=strategy,
            latest_trade_date=latest_trade_date,
            status="empty_pool",
            reason="样本池为空",
            pool_size=0,
            result_rows=len(rows),
        )
    return StrategyHealth(
        strategy=strategy,
        latest_trade_date=latest_trade_date,
        status="ok",
        reason="物化结果可用",
        pool_size=int(summary.pool_size or 0),
        result_rows=len(rows),
    )


def _daily_data_status(*, db, min_symbols: int) -> dict:
    latest_trade_date = (
        db.execute(select(func.max(DailyBarSnapshot.trade_date)))
        .scalars()
        .first()
    )
    if not latest_trade_date:
        return {"ok": False, "latest_trade_date": "", "symbol_count": 0, "reason": "本地日线为空"}
    symbol_count = (
        db.execute(
            select(func.count(func.distinct(DailyBarSnapshot.symbol))).where(
                DailyBarSnapshot.trade_date == latest_trade_date,
                DailyBarSnapshot.instrument_type == "stock",
            )
        )
        .scalars()
        .first()
        or 0
    )
    return {
        "ok": int(symbol_count) >= min_symbols,
        "latest_trade_date": str(latest_trade_date),
        "symbol_count": int(symbol_count),
        "min_symbols": min_symbols,
        "reason": "日线覆盖充足" if int(symbol_count) >= min_symbols else "日线覆盖不足，回测/策略样本可能失真",
    }


def _paused_strong_buy_count(*, db) -> int:
    if not STRONG_BUY_PAUSED_STRATEGIES:
        return 0
    return int(
        db.execute(
            select(func.count(LowBuyResultSnapshot.id)).where(
                LowBuyResultSnapshot.strategy_key.in_(tuple(STRONG_BUY_PAUSED_STRATEGIES)),
                LowBuyResultSnapshot.buy_signal_state.in_(("buy_now", "soft_buy_now")),
            )
        )
        .scalars()
        .first()
        or 0
    )


def _normalize_paused_strong_buy_rows(*, db) -> None:
    if not STRONG_BUY_PAUSED_STRATEGIES:
        return
    rows = (
        db.execute(
            select(LowBuyResultSnapshot).where(
                LowBuyResultSnapshot.strategy_key.in_(tuple(STRONG_BUY_PAUSED_STRATEGIES)),
                LowBuyResultSnapshot.buy_signal_state.in_(("buy_now", "soft_buy_now")),
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        row.buy_signal_state = "near_entry"
        payload = _safe_payload(row.payload_json)
        if payload:
            payload["buy_signal_state"] = "near_entry"
            payload["buy_signal_text"] = "接近买点"
            payload["buy_signal_hint"] = "该策略当前处于观察/研究层，历史强买入已降级。"
            row.payload_json = json.dumps(payload, ensure_ascii=False)
    db.commit()


def _safe_payload(raw: str) -> dict:
    try:
        payload = json.loads(raw or "{}")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
