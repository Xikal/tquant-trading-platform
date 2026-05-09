from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.models.entities import DailyBarSnapshot
from app.services.low_buy_screener import PLAYBOOKS, LowBuyScreenerService
from app.services.low_buy.shared import PERFORMANCE_FORWARD_DAYS
from app.services.low_buy.strategy_families import resolve_strategy_family, resolve_strategy_family_label

try:
    from .low_buy_market_backtest_pools import (
        build_ranked_pools_from_daily_rows as _build_ranked_pools_from_daily_rows,
        is_stock_symbol,
    )
    from .low_buy_market_backtest_runner import (
        run_fast_isolated_backtest,
        run_legacy_backtest,
    )
    from .low_buy_market_backtest_reporting import (
        CONFIRMED_STATES,
        StrategyBacktestStats,
        TradeOutcome,
        _signal_group_stats,
        build_report,
        history_window_days,
        render_markdown_report,
    )
except ImportError:
    from low_buy_market_backtest_pools import (
        build_ranked_pools_from_daily_rows as _build_ranked_pools_from_daily_rows,
        is_stock_symbol,
    )
    from low_buy_market_backtest_runner import (
        run_fast_isolated_backtest,
        run_legacy_backtest,
    )
    from low_buy_market_backtest_reporting import (
        CONFIRMED_STATES,
        StrategyBacktestStats,
        TradeOutcome,
        _signal_group_stats,
        build_report,
        history_window_days,
        render_markdown_report,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="低吸策略 A 股全市场回测")
    parser.add_argument("--months", type=int, default=3, help="回测月份数，默认 3")
    parser.add_argument("--scan-limit", type=int, default=480, help="每个交易日最大扫描样本")
    parser.add_argument("--limit", type=int, default=80, help="每个策略每天保留的候选数量")
    parser.add_argument("--target-profit-pct", type=float, default=3.0, help="5 日内命中目标涨幅")
    parser.add_argument("--forward-days", type=int, default=PERFORMANCE_FORWARD_DAYS, help="向后评估交易日数量")
    parser.add_argument("--strategies", default="all", help="逗号分隔策略 key，默认 all")
    parser.add_argument("--max-dates", type=int, default=0, help="调试用，只跑最近 N 个评估交易日")
    parser.add_argument(
        "--engine",
        choices=("fast", "legacy"),
        default="fast",
        help="fast=批量预加载候选池和日线；legacy=沿用旧的逐日逐策略回放。",
    )
    parser.add_argument(
        "--materialization-mode",
        choices=("isolated", "production", "read-only"),
        default="isolated",
        help="回测快照来源。isolated=隔离计算不写生产表；production=写入生产物化表；read-only=只读已有物化表。",
    )
    parser.add_argument("--no-materialize", action="store_true", help="兼容旧参数，等价于 --materialization-mode read-only")
    parser.add_argument("--output-dir", default=str(APP_DIR / "data" / "reports"), help="报告输出目录")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    materialization_mode = "read-only" if args.no_materialize else args.materialization_mode
    init_db()
    service = LowBuyScreenerService()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        trade_dates = service._get_recent_trade_dates(max(160, args.months * 31 + args.forward_days + 50))
        latest_completed = service._resolve_latest_completed_trade_date(trade_dates)
        evaluation_dates = _evaluation_dates(
            trade_dates=trade_dates,
            latest_completed=latest_completed,
            months=args.months,
            forward_days=args.forward_days,
        )
        if args.max_dates > 0:
            evaluation_dates = evaluation_dates[-args.max_dates :]
        strategy_keys = _resolve_strategy_keys(args.strategies)
        universe_count = _load_a_share_universe_count(db, service)
        stats = {
            strategy: StrategyBacktestStats(
                strategy_key=strategy,
                strategy_title=PLAYBOOKS[strategy]["title"],
                strategy_family=resolve_strategy_family(strategy),
                strategy_family_text=resolve_strategy_family_label(strategy),
            )
            for strategy in strategy_keys
        }

        if args.engine == "fast" and materialization_mode == "isolated":
            run_fast_isolated_backtest(
                db=db,
                service=service,
                stats=stats,
                trade_dates=trade_dates,
                evaluation_dates=evaluation_dates,
                latest_completed=latest_completed,
                strategy_keys=strategy_keys,
                scan_limit=args.scan_limit,
                limit=args.limit,
                forward_days=args.forward_days,
                history_window_days_value=history_window_days(args.months, args.forward_days),
                count_signal_state=_count_signal_state,
            )
        else:
            run_legacy_backtest(
                db=db,
                service=service,
                stats=stats,
                evaluation_dates=evaluation_dates,
                latest_completed=latest_completed,
                strategy_keys=strategy_keys,
                scan_limit=args.scan_limit,
                limit=args.limit,
                forward_days=args.forward_days,
                months=args.months,
                materialization_mode=materialization_mode,
                load_or_build_snapshot=_load_or_build_snapshot,
                count_signal_state=_count_signal_state,
            )

        report = build_report(
            universe_count=universe_count,
            latest_completed=latest_completed,
            evaluation_dates=evaluation_dates,
            target_profit_pct=args.target_profit_pct,
            scan_limit=args.scan_limit,
            months=args.months,
            materialization_mode=f"{materialization_mode}/{args.engine}",
            stats=list(stats.values()),
        )

    stem = (
        f"low_buy_market_backtest_{args.months}m_{evaluation_dates[0]}_{evaluation_dates[-1]}"
        if evaluation_dates
        else f"low_buy_market_backtest_{args.months}m_empty"
    )
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 0


def _resolve_strategy_keys(raw: str) -> list[str]:
    if raw == "all":
        return list(PLAYBOOKS.keys())
    keys = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = [item for item in keys if item not in PLAYBOOKS]
    if unknown:
        raise SystemExit(f"未知策略: {', '.join(unknown)}")
    return keys


def _evaluation_dates(
    *,
    trade_dates: list[str],
    latest_completed: str,
    months: int,
    forward_days: int,
) -> list[str]:
    start_date = date.today() - timedelta(days=max(1, months) * 31)
    completed_dates = [item for item in trade_dates if item <= latest_completed]
    if len(completed_dates) <= forward_days:
        return []
    last_evaluable = completed_dates[-1 - forward_days]
    return [
        item
        for item in completed_dates
        if item >= start_date.isoformat() and item <= last_evaluable
    ]


def _load_a_share_universe_count(db, service: LowBuyScreenerService) -> int:
    try:
        rows = db.execute(select(DailyBarSnapshot.symbol).distinct()).all()
        local_count = len([row[0] for row in rows if is_stock_symbol(str(row[0]))])
        if local_count:
            return int(local_count)
    except Exception:
        pass
    try:
        return int(service.market_data.get_total_instruments(db, kind="stock"))
    except Exception:
        return 0


def _load_or_build_snapshot(
    *,
    db,
    service: LowBuyScreenerService,
    strategy: str,
    trade_date: str,
    limit: int,
    scan_limit: int,
    materialization_mode: str,
):
    if materialization_mode == "isolated":
        print(f"[backtest] isolated compute {strategy} {trade_date}", flush=True)
        return service._screen_historical_sync(
            db=db,
            strategy=strategy,
            latest_trade_date=trade_date,
            limit=limit,
            scan_limit=scan_limit,
        )

    payload = service._load_materialized_full_result(
        db=db,
        strategy=strategy,
        latest_trade_date=trade_date,
        limit=limit,
        include_history=False,
    )
    if payload is not None or materialization_mode == "read-only":
        return payload
    print(f"[backtest] {materialization_mode} compute {strategy} {trade_date}", flush=True)
    payload = service._screen_historical_sync(
        db=db,
        strategy=strategy,
        latest_trade_date=trade_date,
        limit=limit,
        scan_limit=scan_limit,
    )
    if materialization_mode != "production":
        return payload
    service._persist_materialized_full_result(db=db, payload=payload)
    db.commit()
    return service._load_materialized_full_result(
        db=db,
        strategy=strategy,
        latest_trade_date=trade_date,
        limit=limit,
        include_history=False,
    )


def _count_signal_state(stat: StrategyBacktestStats, state: str) -> None:
    if state in CONFIRMED_STATES:
        stat.confirmed_count += 1
    elif state == "near_entry":
        stat.near_entry_count += 1
    elif state == "watch":
        stat.watch_count += 1
    elif state == "avoid":
        stat.avoid_count += 1


if __name__ == "__main__":
    raise SystemExit(main())
