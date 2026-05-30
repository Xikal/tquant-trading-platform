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
from app.services.low_buy.candidate_rule_params import research_prefilter_overrides
from app.services.low_buy.execution_simulation import ExecutionSimulationOverride
from app.services.low_buy.front_row_filter import FrontRowFilterConfig
from app.services.low_buy_screener import PLAYBOOKS, LowBuyScreenerService
from app.services.low_buy.shared import PERFORMANCE_FORWARD_DAYS
from app.services.low_buy.strategy_families import resolve_strategy_family, resolve_strategy_family_label

try:
    from .low_buy_market_backtest_pools import (
        build_ranked_pools_from_daily_rows as _build_ranked_pools_from_daily_rows,
        is_stock_symbol,
    )
    from .low_buy_market_backtest_signal_stats import signal_group_stats
    from .low_buy_market_backtest_market_guard import (
        DEFAULT_RETREAT_STATES,
        MarketGuardOverride,
        market_guard_label,
        market_guard_stem,
    )
    from .low_buy_market_backtest_runner import (
        run_fast_isolated_backtest,
        run_legacy_backtest,
    )
    from .low_buy_market_backtest_reporting import (
        CONFIRMED_STATES,
        EVALUATED_STATES,
        StrategyBacktestStats,
        TradeOutcome,
        build_report,
        history_window_days,
        render_markdown_report,
    )
except ImportError:
    from low_buy_market_backtest_pools import (
        build_ranked_pools_from_daily_rows as _build_ranked_pools_from_daily_rows,
        is_stock_symbol,
    )
    from low_buy_market_backtest_signal_stats import signal_group_stats
    from low_buy_market_backtest_market_guard import (
        DEFAULT_RETREAT_STATES,
        MarketGuardOverride,
        market_guard_label,
        market_guard_stem,
    )
    from low_buy_market_backtest_runner import (
        run_fast_isolated_backtest,
        run_legacy_backtest,
    )
    from low_buy_market_backtest_reporting import (
        CONFIRMED_STATES,
        EVALUATED_STATES,
        StrategyBacktestStats,
        TradeOutcome,
        build_report,
        history_window_days,
        render_markdown_report,
    )

_signal_group_stats = signal_group_stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="低吸策略 A 股全市场回测")
    parser.add_argument("--months", type=int, default=3, help="回测月份数，默认 3")
    parser.add_argument("--start", default="", help="可选，显式回测开始日期 YYYY-MM-DD；设置后优先于 --months 的开始窗口")
    parser.add_argument("--end", default="", help="可选，显式回测结束日期 YYYY-MM-DD；会自动避开 forward-days 未完成区间")
    parser.add_argument("--scan-limit", type=int, default=480, help="每个交易日最大扫描样本")
    parser.add_argument("--limit", type=int, default=80, help="每个策略每天保留的候选数量")
    parser.add_argument("--target-profit-pct", type=float, default=3.0, help="5 日内命中目标涨幅")
    parser.add_argument("--forward-days", type=int, default=PERFORMANCE_FORWARD_DAYS, help="向后评估交易日数量")
    parser.add_argument("--strategies", default="all", help="逗号分隔策略 key，默认 all")
    parser.add_argument(
        "--states",
        default="all",
        help="逗号分隔待评估信号状态，默认 all=buy_now,soft_buy_now,observe_confirmed,near_entry；可用于 buy_now 专项回测。",
    )
    parser.add_argument("--stop-loss-pct", type=float, default=None, help="研究回测覆盖：按入场价百分比设置固定止损，例如 -3")
    parser.add_argument("--atr-stop-multiplier", type=float, default=None, help="研究回测覆盖：按 candidate.atr_pct * multiplier 设置动态止损")
    parser.add_argument("--first-take-profit-pct", type=float, default=None, help="研究回测覆盖：按入场价百分比设置首次止盈")
    parser.add_argument("--trailing-stop-pct", type=float, default=None, help="研究回测覆盖：按入场价百分比设置移动防守线")
    parser.add_argument("--max-holding-days-override", type=int, default=None, help="研究回测覆盖：最大持有交易日")
    parser.add_argument("--force-t1-exit", action="store_true", help="研究回测覆盖：最迟 T+1 收盘退出")
    parser.add_argument("--force-t2-exit", action="store_true", help="研究回测覆盖：最迟 T+2 收盘退出")
    parser.add_argument(
        "--market-guard-mode",
        choices=("none", "degrade_retreat", "block_retreat"),
        default="none",
        help="研究回测覆盖：退潮/高位分化保护。none=关闭；degrade_retreat=降级；block_retreat=阻断。",
    )
    parser.add_argument(
        "--market-guard-states",
        default=",".join(DEFAULT_RETREAT_STATES),
        help="研究回测覆盖：逗号分隔触发市场状态，默认 high_flyer_retreat,risk_release。",
    )
    parser.add_argument(
        "--market-guard-degrade-to",
        choices=("near_entry", "watch", "avoid"),
        default="near_entry",
        help="degrade_retreat 模式下降级到的状态；block_retreat 固定阻断为 avoid。",
    )
    parser.add_argument(
        "--market-guard-min-strength",
        type=float,
        default=0.0,
        help="研究回测覆盖：市场状态强度低于该值时不触发保护。",
    )
    parser.add_argument(
        "--prefilter-override",
        action="append",
        default=[],
        help="研究回测覆盖：策略预筛参数覆盖，格式 strategy.param=value，可重复。例如 first_board.max_distribution_risk_score=5.2。",
    )
    parser.add_argument(
        "--front-row-only",
        action="store_true",
        help="研究回测覆盖：只保留龙头/强跟随/核心热点/核心主线候选，默认关闭。",
    )
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
        if args.end:
            latest_completed = min(latest_completed, date.fromisoformat(args.end).isoformat())
        evaluation_dates = _evaluation_dates(
            trade_dates=trade_dates,
            latest_completed=latest_completed,
            months=args.months,
            forward_days=args.forward_days,
            start=args.start,
            end=args.end,
        )
        if args.max_dates > 0:
            evaluation_dates = evaluation_dates[-args.max_dates :]
        strategy_keys = _resolve_strategy_keys(args.strategies)
        evaluated_states = _resolve_evaluated_states(args.states)
        execution_override = _execution_override_from_args(args)
        market_guard = _market_guard_from_args(args)
        prefilter_overrides = _prefilter_overrides_from_args(args.prefilter_override)
        front_row_filter = FrontRowFilterConfig(enabled=True) if args.front_row_only else None
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

        with research_prefilter_overrides(prefilter_overrides):
            if args.engine == "fast" and materialization_mode == "isolated":
                run_fast_isolated_backtest(
                    db=db,
                    service=service,
                    stats=stats,
                    trade_dates=trade_dates,
                    evaluation_dates=evaluation_dates,
                    latest_completed=latest_completed,
                    strategy_keys=strategy_keys,
                    evaluated_states=evaluated_states,
                    execution_override=execution_override,
                    market_guard=market_guard,
                    scan_limit=args.scan_limit,
                    limit=args.limit,
                    forward_days=args.forward_days,
                    history_window_days_value=history_window_days(args.months, args.forward_days),
                    count_signal_state=_count_signal_state,
                    front_row_filter=front_row_filter,
                )
            else:
                run_legacy_backtest(
                    db=db,
                    service=service,
                    stats=stats,
                    evaluation_dates=evaluation_dates,
                    latest_completed=latest_completed,
                    strategy_keys=strategy_keys,
                    evaluated_states=evaluated_states,
                    execution_override=execution_override,
                    market_guard=market_guard,
                    scan_limit=args.scan_limit,
                    limit=args.limit,
                    forward_days=args.forward_days,
                    months=args.months,
                    materialization_mode=materialization_mode,
                    load_or_build_snapshot=_load_or_build_snapshot,
                    count_signal_state=_count_signal_state,
                    front_row_filter=front_row_filter,
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
            requested_start=args.start,
            requested_end=args.end,
            selected_states=evaluated_states,
            execution_model_label=_execution_model_label(execution_override),
            market_guard_label=market_guard_label(market_guard),
            prefilter_override_label=_prefilter_override_label(prefilter_overrides, front_row_only=args.front_row_only),
        )

    guard_stem = market_guard_stem(market_guard)
    prefilter_stem = _prefilter_override_stem(prefilter_overrides)
    front_row_stem = "front_row" if args.front_row_only else "all_rows"
    stem = (
        f"low_buy_market_backtest_{args.months}m_{_states_stem(evaluated_states)}_{_execution_model_stem(execution_override)}_{guard_stem}_{prefilter_stem}_{front_row_stem}_{evaluation_dates[0]}_{evaluation_dates[-1]}"
        if evaluation_dates
        else f"low_buy_market_backtest_{args.months}m_{_states_stem(evaluated_states)}_{_execution_model_stem(execution_override)}_{guard_stem}_{prefilter_stem}_{front_row_stem}_empty"
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


def _resolve_evaluated_states(raw: str) -> set[str]:
    if not raw or raw.strip().lower() == "all":
        return set(EVALUATED_STATES)
    aliases = {
        "confirmed": CONFIRMED_STATES,
        "buy_now": {"buy_now"},
        "soft_buy_now": {"soft_buy_now"},
        "observe_confirmed": {"observe_confirmed"},
        "near_entry": {"near_entry"},
    }
    states: set[str] = set()
    unknown: list[str] = []
    for item in raw.split(","):
        key = item.strip()
        if not key:
            continue
        if key in aliases:
            states.update(aliases[key])
        else:
            unknown.append(key)
    if unknown:
        raise SystemExit(f"未知信号状态: {', '.join(unknown)}")
    if not states:
        raise SystemExit("至少需要指定一个有效信号状态")
    return states


def _states_stem(states: set[str]) -> str:
    if states == set(EVALUATED_STATES):
        return "all_states"
    if states == set(CONFIRMED_STATES):
        return "confirmed"
    return "_".join(sorted(states)).replace("/", "_")


def _execution_override_from_args(args) -> ExecutionSimulationOverride | None:
    if bool(args.force_t1_exit) and bool(args.force_t2_exit):
        raise SystemExit("--force-t1-exit 和 --force-t2-exit 不能同时启用")
    values = {
        "stop_loss_pct": args.stop_loss_pct,
        "atr_stop_multiplier": args.atr_stop_multiplier,
        "first_take_profit_pct": args.first_take_profit_pct,
        "trailing_stop_pct": args.trailing_stop_pct,
        "max_holding_days": args.max_holding_days_override,
        "force_t1_exit": bool(args.force_t1_exit),
        "force_t2_exit": bool(args.force_t2_exit),
    }
    if not any(value not in {None, False} for value in values.values()):
        return None
    return ExecutionSimulationOverride(**values)


def _market_guard_from_args(args) -> MarketGuardOverride | None:
    if args.market_guard_mode == "none":
        return None
    states = tuple(item.strip() for item in str(args.market_guard_states or "").split(",") if item.strip())
    if not states:
        raise SystemExit("启用 --market-guard-mode 时至少需要一个 --market-guard-states")
    return MarketGuardOverride(
        mode=args.market_guard_mode,
        states=states,
        degrade_to=args.market_guard_degrade_to,
        min_strength=float(args.market_guard_min_strength or 0.0),
    )


def _prefilter_overrides_from_args(raw_items: list[str] | None) -> dict[str, dict[str, object]]:
    overrides: dict[str, dict[str, object]] = {}
    for raw in raw_items or []:
        item = str(raw or "").strip()
        if not item:
            continue
        if "=" not in item or "." not in item.split("=", 1)[0]:
            raise SystemExit(f"预筛参数覆盖格式错误: {item}，应为 strategy.param=value")
        path, raw_value = item.split("=", 1)
        strategy, param = path.split(".", 1)
        strategy = strategy.strip()
        param = param.strip()
        if strategy not in PLAYBOOKS:
            raise SystemExit(f"未知策略预筛覆盖: {strategy}")
        if not param:
            raise SystemExit(f"预筛参数名不能为空: {item}")
        overrides.setdefault(strategy, {})[param] = _parse_override_value(raw_value)
    return overrides


def _parse_override_value(raw: str) -> object:
    text = str(raw).strip()
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def _prefilter_override_label(overrides: dict[str, dict[str, object]], *, front_row_only: bool = False) -> str:
    if not overrides and not front_row_only:
        return "none"
    parts: list[str] = []
    for strategy in sorted(overrides):
        for key in sorted(overrides[strategy]):
            parts.append(f"{strategy}.{key}={overrides[strategy][key]}")
    if front_row_only:
        parts.append("front_row_only=true")
    return ",".join(parts)


def _prefilter_override_stem(overrides: dict[str, dict[str, object]]) -> str:
    if not overrides:
        return "no_prefilter_override"
    parts: list[str] = []
    for strategy in sorted(overrides):
        for key in sorted(overrides[strategy]):
            parts.append(f"{strategy}_{key}_{_stem_value(overrides[strategy][key])}")
    return "prefilter_" + "_".join(parts)


def _execution_model_label(override: ExecutionSimulationOverride | None) -> str:
    if override is None:
        return "candidate_exit_plan"
    parts: list[str] = []
    if override.stop_loss_pct is not None:
        parts.append(f"fixed_stop={override.stop_loss_pct}%")
    if override.atr_stop_multiplier is not None:
        parts.append(f"atr_stop={override.atr_stop_multiplier}x")
    if override.first_take_profit_pct is not None:
        parts.append(f"first_tp={override.first_take_profit_pct}%")
    if override.trailing_stop_pct is not None:
        parts.append(f"trailing={override.trailing_stop_pct}%")
    if override.max_holding_days is not None:
        parts.append(f"max_hold={override.max_holding_days}")
    if override.force_t1_exit:
        parts.append("force_t1_exit")
    if override.force_t2_exit:
        parts.append("force_t2_exit")
    return ",".join(parts) if parts else "candidate_exit_plan"


def _execution_model_stem(override: ExecutionSimulationOverride | None) -> str:
    if override is None:
        return "default_exit"
    parts: list[str] = []
    if override.stop_loss_pct is not None:
        parts.append(f"fixed_stop_{_stem_number(override.stop_loss_pct)}pct")
    if override.atr_stop_multiplier is not None:
        parts.append(f"atr_stop_{_stem_number(override.atr_stop_multiplier)}x")
    if override.first_take_profit_pct is not None:
        parts.append(f"first_tp_{_stem_number(override.first_take_profit_pct)}pct")
    if override.trailing_stop_pct is not None:
        parts.append(f"trailing_{_stem_number(override.trailing_stop_pct)}pct")
    if override.max_holding_days is not None:
        parts.append(f"max_hold_{int(override.max_holding_days)}")
    if override.force_t1_exit:
        parts.append("force_t1_exit")
    if override.force_t2_exit:
        parts.append("force_t2_exit")
    return "_".join(parts) if parts else "default_exit"


def _stem_number(value: float) -> str:
    text = f"{float(value):g}"
    return text.replace("-", "m").replace(".", "p")


def _stem_value(value: object) -> str:
    return str(value).replace("-", "m").replace(".", "p").replace("/", "_").replace(" ", "_")


def _evaluation_dates(
    *,
    trade_dates: list[str],
    latest_completed: str,
    months: int,
    forward_days: int,
    start: str = "",
    end: str = "",
) -> list[str]:
    start_date = date.fromisoformat(start) if start else date.today() - timedelta(days=max(1, months) * 31)
    explicit_end = date.fromisoformat(end).isoformat() if end else ""
    completed_dates = [item for item in trade_dates if item <= latest_completed]
    if len(completed_dates) <= forward_days:
        return []
    last_evaluable = completed_dates[-1 - forward_days]
    if explicit_end:
        last_evaluable = min(last_evaluable, explicit_end)
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
    stat.record_signal_state(state)
    if state in CONFIRMED_STATES:
        stat.confirmed_count += 1
    elif state == "observe_confirmed":
        stat.observe_confirmed_count += 1
    elif state == "near_entry":
        stat.near_entry_count += 1
    elif state == "watch":
        stat.watch_count += 1
    elif state == "avoid":
        stat.avoid_count += 1


if __name__ == "__main__":
    raise SystemExit(main())
