from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "backend"
BACKTEST_SCRIPT = ROOT_DIR / "backend" / "scripts" / "low_buy_market_backtest.py"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.core.database import SessionLocal, init_db
from app.services.low_buy.candidate_rule_params import research_prefilter_overrides
from app.services.low_buy.execution_simulation import ExecutionSimulationOverride
from app.services.low_buy_screener import PLAYBOOKS, LowBuyScreenerService
from app.services.low_buy.strategy_families import resolve_strategy_family, resolve_strategy_family_label

try:
    from .low_buy_market_backtest import (
        _count_signal_state,
        _load_a_share_universe_count,
        _resolve_evaluated_states,
        _resolve_strategy_keys,
    )
    from .low_buy_market_backtest_market_guard import market_guard_label
    from .low_buy_market_backtest_reporting import StrategyBacktestStats, build_report, history_window_days
    from .low_buy_market_backtest_runner import run_fast_isolated_execution_matrix_backtest
except ImportError:
    from low_buy_market_backtest import (
        _count_signal_state,
        _load_a_share_universe_count,
        _resolve_evaluated_states,
        _resolve_strategy_keys,
    )
    from low_buy_market_backtest_market_guard import market_guard_label
    from low_buy_market_backtest_reporting import StrategyBacktestStats, build_report, history_window_days
    from low_buy_market_backtest_runner import run_fast_isolated_execution_matrix_backtest


@dataclass(frozen=True)
class ExecutionVariant:
    key: str
    title: str
    purpose: str
    args: tuple[str, ...] = ()

    @property
    def execution_model_label(self) -> str:
        if not self.args:
            return "candidate_exit_plan"
        pairs = list(self.args)
        values: dict[str, str | bool] = {}
        index = 0
        while index < len(pairs):
            key = pairs[index]
            if key in {"--force-t1-exit", "--force-t2-exit"}:
                values[key] = True
                index += 1
                continue
            if index + 1 >= len(pairs):
                break
            values[key] = pairs[index + 1]
            index += 2
        parts: list[str] = []
        if "--stop-loss-pct" in values:
            parts.append(f"fixed_stop={_label_float(values['--stop-loss-pct'])}%")
        if "--atr-stop-multiplier" in values:
            parts.append(f"atr_stop={_label_float(values['--atr-stop-multiplier'])}x")
        if "--first-take-profit-pct" in values:
            parts.append(f"first_tp={_label_float(values['--first-take-profit-pct'])}%")
        if "--trailing-stop-pct" in values:
            parts.append(f"trailing={_label_float(values['--trailing-stop-pct'])}%")
        if "--max-holding-days-override" in values:
            parts.append(f"max_hold={int(float(str(values['--max-holding-days-override'])))}")
        if values.get("--force-t1-exit"):
            parts.append("force_t1_exit")
        if values.get("--force-t2-exit"):
            parts.append("force_t2_exit")
        return ",".join(parts) if parts else "candidate_exit_plan"


VARIANTS: tuple[ExecutionVariant, ...] = (
    ExecutionVariant(
        key="default_exit",
        title="候选原始退出计划",
        purpose="作为当前生产/研究候选退出计划基线。",
    ),
    ExecutionVariant(
        key="fixed_stop_m2p5",
        title="固定 -2.5% 止损",
        purpose="验证更紧止损能否降低回撤和止损拖累。",
        args=("--stop-loss-pct", "-2.5"),
    ),
    ExecutionVariant(
        key="fixed_stop_m3p5",
        title="固定 -3.5% 止损",
        purpose="验证放宽止损能否减少噪声止损且不扩大回撤。",
        args=("--stop-loss-pct", "-3.5"),
    ),
    ExecutionVariant(
        key="atr_stop_0p8",
        title="ATR 0.8x 动态止损",
        purpose="验证按标的波动缩放止损的保守版本。",
        args=("--atr-stop-multiplier", "0.8"),
    ),
    ExecutionVariant(
        key="atr_stop_1p0",
        title="ATR 1.0x 动态止损",
        purpose="验证按标的波动缩放止损的中性版本。",
        args=("--atr-stop-multiplier", "1.0"),
    ),
    ExecutionVariant(
        key="atr_stop_1p2",
        title="ATR 1.2x 动态止损",
        purpose="验证按标的波动缩放止损的放宽版本。",
        args=("--atr-stop-multiplier", "1.2"),
    ),
    ExecutionVariant(
        key="force_t1_close",
        title="最迟 T+1 收盘退出",
        purpose="验证次日兑现纪律能否减少冲高回落。",
        args=("--force-t1-exit", "--first-take-profit-pct", "8"),
    ),
    ExecutionVariant(
        key="force_t2_close",
        title="最迟 T+2 收盘退出",
        purpose="验证短持仓窗口能否提升资金效率。",
        args=("--force-t2-exit", "--first-take-profit-pct", "8"),
    ),
    ExecutionVariant(
        key="quick_tp3_trailing1",
        title="3% 首次止盈 + 1% 移动防守 + 最多 3 天",
        purpose="验证短线冲高兑现和更紧防守线的组合。",
        args=("--first-take-profit-pct", "3", "--trailing-stop-pct", "1", "--max-holding-days-override", "3"),
    ),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="低吸策略执行模型矩阵回测")
    parser.add_argument("--months", type=int, default=24)
    parser.add_argument("--start", default="")
    parser.add_argument("--end", default="")
    parser.add_argument("--train-start", default="")
    parser.add_argument("--train-end", default="")
    parser.add_argument("--validation-start", default="")
    parser.add_argument("--validation-end", default="")
    parser.add_argument("--purged-gap-start", default="")
    parser.add_argument("--purged-gap-end", default="")
    parser.add_argument("--strategies", default="all")
    parser.add_argument("--states", default="confirmed")
    parser.add_argument("--scan-limit", type=int, default=480)
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--target-profit-pct", type=float, default=3.0)
    parser.add_argument("--forward-days", type=int, default=5)
    parser.add_argument("--max-dates", type=int, default=0)
    parser.add_argument("--engine", choices=("fast", "legacy"), default="fast")
    parser.add_argument("--materialization-mode", choices=("isolated", "production", "read-only"), default="isolated")
    parser.add_argument("--output-dir", default=str(ROOT_DIR / "backend" / "data" / "reports" / "execution_matrix"))
    parser.add_argument("--matrix-output-dir", default=str(ROOT_DIR / "backend" / "data" / "reports" / "execution_matrix"))
    parser.add_argument(
        "--resume-existing",
        action="store_true",
        help="复用同 scope 下已生成的单变体 low_buy_market_backtest JSON，只运行缺失变体。",
    )
    parser.add_argument(
        "--resume-search-dir",
        action="append",
        default=[],
        help="额外搜索已有单变体 JSON 的目录；可重复。默认搜索 output-dir 和 matrix-output-dir。",
    )
    parser.add_argument(
        "--variants",
        default="default_exit,fixed_stop_m2p5,fixed_stop_m3p5,atr_stop_0p8,atr_stop_1p0,atr_stop_1p2,force_t1_close,force_t2_close,quick_tp3_trailing1",
        help="逗号分隔矩阵 key；默认跑全部内置执行模型。",
    )
    parser.add_argument("--python", default=sys.executable)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    _validate_temporal_splits(args)
    selected = _resolve_variants(args.variants)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix_output_dir = Path(args.matrix_output_dir)
    matrix_output_dir.mkdir(parents=True, exist_ok=True)

    if _can_run_batched_matrix(args):
        rows = _run_batched_fast_matrix(args=args, variants=selected)
        report = _build_matrix_report(args=args, rows=rows)
        _write_matrix_report(args=args, report=report, matrix_output_dir=matrix_output_dir)
        return 0

    rows: list[dict[str, Any]] = []
    for variant in selected:
        source = "computed"
        payload = None
        if args.resume_existing:
            payload = _find_existing_variant_payload(args=args, variant=variant, output_dir=output_dir, matrix_output_dir=matrix_output_dir)
            if payload is not None:
                source = "resumed"
                print(f"[matrix] reuse {variant.key}: {_existing_report_path(payload)}", flush=True)
        if payload is None:
            payload = _run_variant(args=args, variant=variant, output_dir=output_dir)
        rows.append(_matrix_row(variant=variant, payload=payload, source=source))

    report = _build_matrix_report(args=args, rows=rows)
    _write_matrix_report(args=args, report=report, matrix_output_dir=matrix_output_dir)
    return 0


def _write_matrix_report(
    *,
    args: argparse.Namespace,
    report: dict[str, Any],
    matrix_output_dir: Path,
) -> None:
    stem = _matrix_stem(args)
    json_path = matrix_output_dir / f"{stem}.json"
    md_path = matrix_output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {"json": str(json_path), "markdown": str(md_path), "variant_count": len(report.get("rows", []))},
            ensure_ascii=False,
            indent=2,
        )
    )


def _can_run_batched_matrix(args: argparse.Namespace) -> bool:
    return (
        args.engine == "fast"
        and args.materialization_mode == "isolated"
        and not args.resume_existing
    )


def _run_batched_fast_matrix(*, args: argparse.Namespace, variants: list[ExecutionVariant]) -> list[dict[str, Any]]:
    init_db()
    service = LowBuyScreenerService()
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
        universe_count = _load_a_share_universe_count(db, service)
        stats_by_variant = {
            variant.key: _new_stats_for_strategies(strategy_keys)
            for variant in variants
        }
        execution_overrides = {
            variant.key: _execution_override_from_variant(variant)
            for variant in variants
        }
        print(
            f"[matrix] batched fast run variants={len(variants)} strategies={len(strategy_keys)} dates={len(evaluation_dates)}",
            flush=True,
        )
        with research_prefilter_overrides({}):
            run_fast_isolated_execution_matrix_backtest(
                db=db,
                service=service,
                stats_by_variant=stats_by_variant,
                trade_dates=trade_dates,
                evaluation_dates=evaluation_dates,
                latest_completed=latest_completed,
                strategy_keys=strategy_keys,
                evaluated_states=evaluated_states,
                execution_overrides=execution_overrides,
                market_guard=None,
                scan_limit=args.scan_limit,
                limit=args.limit,
                forward_days=args.forward_days,
                history_window_days_value=history_window_days(args.months, args.forward_days),
                count_signal_state=_count_signal_state,
            )
        rows: list[dict[str, Any]] = []
        for variant in variants:
            report = build_report(
                universe_count=universe_count,
                latest_completed=latest_completed,
                evaluation_dates=evaluation_dates,
                target_profit_pct=args.target_profit_pct,
                scan_limit=args.scan_limit,
                months=args.months,
                materialization_mode=f"{args.materialization_mode}/{args.engine}",
                stats=list(stats_by_variant[variant.key].values()),
                requested_start=args.start,
                requested_end=args.end,
                selected_states=evaluated_states,
                execution_model_label=variant.execution_model_label,
                market_guard_label=market_guard_label(None),
                prefilter_override_label="none",
            )
            rows.append(_matrix_row(variant=variant, payload=report, source="batched"))
        return rows


def _new_stats_for_strategies(strategy_keys: list[str]) -> dict[str, StrategyBacktestStats]:
    return {
        strategy: StrategyBacktestStats(
            strategy_key=strategy,
            strategy_title=PLAYBOOKS[strategy]["title"],
            strategy_family=resolve_strategy_family(strategy),
            strategy_family_text=resolve_strategy_family_label(strategy),
        )
        for strategy in strategy_keys
    }


def _execution_override_from_variant(variant: ExecutionVariant) -> ExecutionSimulationOverride | None:
    if not variant.args:
        return None
    values: dict[str, float | int | bool | None] = {
        "stop_loss_pct": None,
        "atr_stop_multiplier": None,
        "first_take_profit_pct": None,
        "trailing_stop_pct": None,
        "max_holding_days": None,
        "force_t1_exit": False,
        "force_t2_exit": False,
    }
    index = 0
    args = list(variant.args)
    while index < len(args):
        key = args[index]
        if key == "--force-t1-exit":
            values["force_t1_exit"] = True
            index += 1
            continue
        if key == "--force-t2-exit":
            values["force_t2_exit"] = True
            index += 1
            continue
        if index + 1 >= len(args):
            break
        raw_value = args[index + 1]
        if key == "--stop-loss-pct":
            values["stop_loss_pct"] = float(raw_value)
        elif key == "--atr-stop-multiplier":
            values["atr_stop_multiplier"] = float(raw_value)
        elif key == "--first-take-profit-pct":
            values["first_take_profit_pct"] = float(raw_value)
        elif key == "--trailing-stop-pct":
            values["trailing_stop_pct"] = float(raw_value)
        elif key == "--max-holding-days-override":
            values["max_holding_days"] = int(raw_value)
        index += 2
    return ExecutionSimulationOverride(**values)


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


def _resolve_variants(raw: str) -> list[ExecutionVariant]:
    by_key = {item.key: item for item in VARIANTS}
    keys = [item.strip() for item in raw.split(",") if item.strip()]
    if not keys:
        raise SystemExit("至少需要指定一个执行模型矩阵 key")
    unknown = [key for key in keys if key not in by_key]
    if unknown:
        raise SystemExit(f"未知执行模型矩阵 key: {', '.join(unknown)}")
    return [by_key[key] for key in keys]


def _run_variant(*, args: argparse.Namespace, variant: ExecutionVariant, output_dir: Path) -> dict[str, Any]:
    cmd = [
        args.python,
        str(BACKTEST_SCRIPT),
        "--months",
        str(args.months),
        "--strategies",
        args.strategies,
        "--states",
        args.states,
        "--scan-limit",
        str(args.scan_limit),
        "--limit",
        str(args.limit),
        "--target-profit-pct",
        str(args.target_profit_pct),
        "--forward-days",
        str(args.forward_days),
        "--engine",
        args.engine,
        "--materialization-mode",
        args.materialization_mode,
        "--output-dir",
        str(output_dir),
        *variant.args,
    ]
    if args.start:
        cmd.extend(["--start", args.start])
    if args.end:
        cmd.extend(["--end", args.end])
    if args.max_dates > 0:
        cmd.extend(["--max-dates", str(args.max_dates)])

    env = dict(os.environ)
    env["PYTHONPATH"] = _append_pythonpath(env.get("PYTHONPATH", ""), str(ROOT_DIR / "backend"), str(ROOT_DIR))
    print(f"[matrix] running {variant.key}: {' '.join(cmd)}", flush=True)
    completed = subprocess.run(cmd, cwd=ROOT_DIR, env=env, check=True, capture_output=True, text=True)
    try:
        result = _extract_json_output(completed.stdout)
    except json.JSONDecodeError as exc:
        tail = "\n".join(
            item for item in (completed.stdout[-1000:], completed.stderr[-1000:]) if item
        )
        raise SystemExit(f"{variant.key} 回测输出不是 JSON: {tail}") from exc
    report_path = Path(result["json"])
    return json.loads(report_path.read_text(encoding="utf-8"))


def _find_existing_variant_payload(
    *,
    args: argparse.Namespace,
    variant: ExecutionVariant,
    output_dir: Path,
    matrix_output_dir: Path,
) -> dict[str, Any] | None:
    search_dirs = _resume_search_dirs(args=args, output_dir=output_dir, matrix_output_dir=matrix_output_dir)
    for path in _iter_candidate_reports(search_dirs):
        payload = _load_json_report(path)
        if payload is None:
            continue
        if _matches_variant_scope(args=args, variant=variant, payload=payload):
            payload.setdefault("_matrix_resume_source", str(path))
            return payload
    return None


def _resume_search_dirs(*, args: argparse.Namespace, output_dir: Path, matrix_output_dir: Path) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for raw in [output_dir, matrix_output_dir, *(Path(item) for item in args.resume_search_dir)]:
        path = raw if raw.is_absolute() else ROOT_DIR / raw
        path = path.resolve()
        if path in seen or not path.exists():
            continue
        seen.add(path)
        result.append(path)
    return result


def _iter_candidate_reports(search_dirs: list[Path]) -> list[Path]:
    result: list[Path] = []
    for directory in search_dirs:
        result.extend(sorted(directory.glob("low_buy_market_backtest_*.json")))
    return result


def _load_json_report(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) and isinstance(payload.get("summary"), dict) else None


def _matches_variant_scope(*, args: argparse.Namespace, variant: ExecutionVariant, payload: dict[str, Any]) -> bool:
    summary = payload.get("summary", {})
    if _execution_model_tokens(summary.get("execution_model")) != _execution_model_tokens(variant.execution_model_label):
        return False
    if int(summary.get("backtest_window_months") or 0) != int(args.months):
        return False
    if str(summary.get("requested_start") or "") != str(args.start or ""):
        return False
    if str(summary.get("requested_end") or "") != str(args.end or ""):
        return False
    if str(summary.get("materialization_mode") or "") != f"{args.materialization_mode}/{args.engine}":
        return False
    if int(summary.get("scan_limit_per_day") or 0) != int(args.scan_limit):
        return False
    if _states_label(summary.get("selected_signal_states")) != _states_label(_resolve_states_for_match(args.states)):
        return False
    if str(summary.get("market_guard") or "none") != "none":
        return False
    if str(summary.get("prefilter_overrides") or "none") != "none":
        return False
    if args.strategies != "all" and not _strategy_scope_matches(args.strategies, payload):
        return False
    return True


def _strategy_scope_matches(raw: str, payload: dict[str, Any]) -> bool:
    expected = sorted(item.strip() for item in raw.split(",") if item.strip())
    actual = sorted(str(item.get("strategy_key") or "") for item in payload.get("strategies", []) if isinstance(item, dict))
    return actual == expected


def _resolve_states_for_match(raw: str) -> list[str]:
    if not raw or raw.strip().lower() == "all":
        return ["buy_now", "near_entry", "observe_confirmed", "soft_buy_now"]
    aliases = {
        "confirmed": ["buy_now", "soft_buy_now"],
        "buy_now": ["buy_now"],
        "soft_buy_now": ["soft_buy_now"],
        "observe_confirmed": ["observe_confirmed"],
        "near_entry": ["near_entry"],
    }
    states: list[str] = []
    for item in raw.split(","):
        key = item.strip()
        states.extend(aliases.get(key, [key]))
    return states


def _states_label(values: Any) -> str:
    if not isinstance(values, list):
        return ""
    return ",".join(sorted(str(item) for item in values if item))


def _execution_model_tokens(value: Any) -> tuple[str, ...]:
    text = str(value or "").strip()
    if not text:
        return ()
    return tuple(sorted(_normalize_execution_model_token(item) for item in text.split(",") if item.strip()))


def _normalize_execution_model_token(value: str) -> str:
    item = value.strip()
    if "=" not in item:
        return item
    key, raw_value = item.split("=", 1)
    suffix = ""
    if raw_value.endswith(("%", "x")):
        suffix = raw_value[-1]
        raw_value = raw_value[:-1]
    try:
        normalized = f"{float(raw_value):g}{suffix}"
    except ValueError:
        normalized = raw_value + suffix
    return f"{key}={normalized}"


def _existing_report_path(payload: dict[str, Any]) -> str:
    return str(payload.get("_matrix_resume_source") or "")


def _extract_json_output(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start < 0 or end < start:
        raise json.JSONDecodeError("no JSON object found", stdout, 0)
    return json.loads(stdout[start : end + 1])


def _append_pythonpath(existing: str, *items: str) -> str:
    parts = [item for item in items if item]
    if existing:
        parts.append(existing)
    return os.pathsep.join(parts)


def _matrix_row(*, variant: ExecutionVariant, payload: dict[str, Any], source: str = "computed") -> dict[str, Any]:
    summary = payload.get("summary", {})
    metrics = summary.get("backtest_metrics", {})
    total = summary.get("total_evaluated_result", {})
    confirmed = summary.get("confirmed_result", {})
    coverage = summary.get("data_coverage", {})
    return {
        "variant_key": variant.key,
        "title": variant.title,
        "purpose": variant.purpose,
        "source": source,
        "source_path": _existing_report_path(payload),
        "execution_model": summary.get("execution_model", ""),
        "evaluation_start": summary.get("evaluation_start", ""),
        "evaluation_end": summary.get("evaluation_end", ""),
        "coverage_pct": coverage.get("coverage_pct", 0.0),
        "coverage_status": coverage.get("status", "unknown"),
        "evaluated_count": total.get("evaluated_count", summary.get("evaluated_count", 0)),
        "filled_count": total.get("filled_count", summary.get("filled_count", 0)),
        "net_win_rate": total.get("net_win_rate", summary.get("net_win_rate", 0.0)),
        "avg_net_return_pct": total.get("avg_net_return_pct", summary.get("avg_net_return_pct", 0.0)),
        "stop_loss_rate": total.get("stop_loss_rate", summary.get("stop_loss_rate", 0.0)),
        "execution_profit_factor": total.get("execution_profit_factor", 0.0),
        "total_return_pct": metrics.get("total_return_pct", 0.0),
        "annualized_return_pct": metrics.get("annualized_return_pct", 0.0),
        "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
        "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
        "profit_loss_ratio": metrics.get("profit_loss_ratio", 0.0),
        "profit_factor": metrics.get("profit_factor", 0.0),
        "avg_holding_days": metrics.get("avg_holding_days", 0.0),
        "drawdown_recovery_status": metrics.get("drawdown_recovery_status", ""),
        "t1_high_3_hit_rate": confirmed.get("t1_high_3_hit_rate", 0.0),
        "avg_t1_high_return_pct": confirmed.get("avg_t1_high_return_pct", 0.0),
        "avg_t1_close_return_pct": confirmed.get("avg_t1_close_return_pct", 0.0),
        "filled_exit_reason_counts": summary.get("filled_exit_reason_counts", {}),
    }


def _build_matrix_report(*, args: argparse.Namespace, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "title": "低吸策略执行模型矩阵回测",
        "scope": {
            "months": args.months,
            "start": args.start,
            "end": args.end,
            "train_start": args.train_start,
            "train_end": args.train_end,
            "validation_start": args.validation_start,
            "validation_end": args.validation_end,
            "purged_gap_start": args.purged_gap_start,
            "purged_gap_end": args.purged_gap_end,
            "split_plan_encoded": _split_plan_encoded(args),
            "purged_gap_days": _purged_gap_days(args),
            "purged_gap_temporal_order_passed": _split_plan_temporal_order_passed(args),
            "strategies": args.strategies,
            "states": args.states,
            "scan_limit": args.scan_limit,
            "limit": args.limit,
            "forward_days": args.forward_days,
            "engine": args.engine,
            "materialization_mode": args.materialization_mode,
            "max_dates": args.max_dates,
        },
        "rows": rows,
        "best_by_profit_factor": _best_key(rows, "profit_factor"),
        "best_by_drawdown": _best_key(rows, "max_drawdown_pct"),
        "best_by_avg_net_return": _best_key(rows, "avg_net_return_pct"),
        "warning": _coverage_warning(rows),
    }


def _validate_temporal_splits(args: argparse.Namespace) -> None:
    fields = (
        args.train_start,
        args.train_end,
        args.validation_start,
        args.validation_end,
        args.purged_gap_start,
        args.purged_gap_end,
        args.start,
        args.end,
    )
    provided = [item for item in fields if item]
    if not provided:
        return
    if len(provided) != len(fields):
        raise SystemExit("train/validation/purged-gap/oos 边界必须同时提供。")
    if not _split_plan_temporal_order_passed(args):
        raise SystemExit("train/validation/purged-gap/oos 边界时间顺序不合法。")


def _split_plan_encoded(args: argparse.Namespace) -> bool:
    return all(
        [
            args.train_start,
            args.train_end,
            args.validation_start,
            args.validation_end,
            args.purged_gap_start,
            args.purged_gap_end,
            args.start,
            args.end,
        ]
    )


def _split_plan_temporal_order_passed(args: argparse.Namespace) -> bool:
    if not _split_plan_encoded(args):
        return False
    values = [
        args.train_start,
        args.train_end,
        args.validation_start,
        args.validation_end,
        args.purged_gap_start,
        args.purged_gap_end,
        args.start,
        args.end,
    ]
    parsed = [date.fromisoformat(item) for item in values]
    return all(parsed[index] <= parsed[index + 1] for index in range(len(parsed) - 1))


def _purged_gap_days(args: argparse.Namespace) -> int:
    if not args.purged_gap_start or not args.purged_gap_end:
        return 0
    return (date.fromisoformat(args.purged_gap_end) - date.fromisoformat(args.purged_gap_start)).days + 1


def _best_key(rows: list[dict[str, Any]], field: str, *, reverse: bool = True) -> str:
    if not rows:
        return ""
    return str(sorted(rows, key=lambda item: float(item.get(field, 0.0) or 0.0), reverse=reverse)[0]["variant_key"])


def _coverage_warning(rows: list[dict[str, Any]]) -> str:
    if any(str(row.get("coverage_status")) != "complete" for row in rows):
        return "至少一个矩阵报告数据覆盖不足 90%，只能作为部分区间研究基线，不能替代完整 24 个月验收。"
    return ""


def _matrix_stem(args: argparse.Namespace) -> str:
    states = str(args.states or "all").replace(",", "_").replace("/", "_")
    strategies = str(args.strategies or "all").replace(",", "_").replace("/", "_")
    start = args.start or "auto"
    end = args.end or "auto"
    suffix = f"_{args.max_dates}d" if args.max_dates > 0 else ""
    return f"low_buy_execution_matrix_{args.months}m_{states}_{strategies}_{start}_{end}{suffix}"


def _render_markdown(report: dict[str, Any]) -> str:
    scope = report.get("scope", {})
    lines = [
        f"# {report.get('title', '低吸策略执行模型矩阵回测')}",
        "",
        "## 结论",
        "",
        f"- 范围：{scope.get('months')}个月，策略 `{scope.get('strategies')}`，信号状态 `{scope.get('states')}`，引擎 `{scope.get('engine')}`。",
        f"- Profit Factor 最优：`{report.get('best_by_profit_factor', '')}`。",
        f"- 最大回撤最优：`{report.get('best_by_drawdown', '')}`。",
        f"- 均净收益最优：`{report.get('best_by_avg_net_return', '')}`。",
        *( [f"- 警告：{report['warning']}"] if report.get("warning") else [] ),
        "",
        "## 矩阵结果",
        "",
        "| 模型 | 来源 | 成交 | 胜率 | 均净收益 | 止损率 | 执行PF | 总收益 | 最大回撤 | Sharpe | 盈亏比 | PF | 平均持仓 | 覆盖率 | 退出原因 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report.get("rows", []):
        lines.append(
            "| {title} | {source} | {filled} | {win}% | {avg}% | {stop}% | {epf} | {total}% | {dd}% | {sharpe} | {pl} | {pf} | {hold} | {coverage}% | {reasons} |".format(
                title=row.get("title", row.get("variant_key", "")),
                source="复用" if row.get("source") == "resumed" else "新跑",
                filled=row.get("filled_count", 0),
                win=row.get("net_win_rate", 0.0),
                avg=row.get("avg_net_return_pct", 0.0),
                stop=row.get("stop_loss_rate", 0.0),
                epf=row.get("execution_profit_factor", 0.0),
                total=row.get("total_return_pct", 0.0),
                dd=row.get("max_drawdown_pct", 0.0),
                sharpe=row.get("sharpe_ratio", 0.0),
                pl=row.get("profit_loss_ratio", 0.0),
                pf=row.get("profit_factor", 0.0),
                hold=row.get("avg_holding_days", 0.0),
                coverage=row.get("coverage_pct", 0.0),
                reasons=_render_counts(row.get("filled_exit_reason_counts", {})),
            )
        )
    lines.extend(
        [
            "",
            "## 模型说明",
            "",
        ]
    )
    for row in report.get("rows", []):
        lines.append(f"- `{row.get('variant_key')}`：{row.get('title')}。{row.get('purpose')}")
    return "\n".join(lines) + "\n"


def _render_counts(values: dict[str, int] | None, *, limit: int = 4) -> str:
    rows = list((values or {}).items())
    if not rows:
        return "-"
    head = [f"{key}: {value}" for key, value in rows[:limit]]
    if len(rows) > limit:
        head.append(f"其余 {len(rows) - limit} 项")
    return "；".join(head)


def _label_float(value: object) -> str:
    return f"{float(str(value)):g}"


if __name__ == "__main__":
    raise SystemExit(main())
