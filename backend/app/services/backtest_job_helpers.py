from __future__ import annotations

import json
import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.backtest_entities import BacktestDailySnapshot, BacktestTrade


def _strategy_list(raw_value: str | None) -> list[str]:
    return [item.strip() for item in (raw_value or "").split(",") if item.strip()]


def _json_dict(raw_value: str | None) -> dict[str, Any]:
    try:
        value = json.loads(raw_value or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _json_dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _result_summary_metrics(result: dict[str, Any]) -> dict[str, Any]:
    """Expose compact metrics in list responses so task cards can show results."""

    if not isinstance(result, dict):
        return {}
    summary = result.get("summary")
    metrics = result.get("metrics")
    merged: dict[str, Any] = {}
    if isinstance(summary, dict):
        merged.update(summary)
    if isinstance(metrics, dict):
        merged.update(metrics)
    _copy_alias(merged, "total_return_pct", ("total_return", "return_pct"))
    _copy_alias(merged, "win_rate_pct", ("win_rate",))
    _copy_alias(merged, "max_drawdown_pct", ("max_drawdown",))
    _copy_alias(merged, "trade_count", ("total_trades",))
    return {
        key: merged.get(key)
        for key in (
            "total_return_pct",
            "benchmark_return_pct",
            "benchmark_alpha_pct",
            "max_drawdown_pct",
            "sharpe",
            "sharpe_ratio",
            "sortino_ratio",
            "calmar_ratio",
            "information_ratio",
            "win_rate_pct",
            "total_trades",
            "trade_count",
            "filled_order_count",
            "rejected_order_count",
            "profit_factor",
            "avg_trade_return_pct",
            "initial_cash",
            "final_equity",
        )
        if key in merged
    }


def _copy_alias(target: dict[str, Any], canonical: str, aliases: tuple[str, ...]) -> None:
    if canonical in target:
        return
    for alias in aliases:
        if alias not in target:
            continue
        value = target.get(alias)
        if alias == "win_rate":
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                target[canonical] = value
                return
            target[canonical] = numeric * 100 if abs(numeric) <= 1 else numeric
            return
        target[canonical] = value
        return


def _result_attribution(result: dict[str, Any]) -> dict[str, Any]:
    attribution = result.get("attribution")
    if isinstance(attribution, dict):
        return attribution
    metrics = result.get("metrics")
    if isinstance(metrics, dict) and isinstance(metrics.get("attribution"), dict):
        return metrics["attribution"]
    return {}


def _result_quality(result: dict[str, Any]) -> dict[str, Any]:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else result
    if not isinstance(summary, dict):
        summary = {}
    total_trades = int(float(summary.get("total_trades") or summary.get("filled_count") or 0))
    final_equity = float(summary.get("final_equity") or 0.0)
    warnings: list[str] = []
    if total_trades <= 0:
        warnings.append("无成交样本，结果仅可作为数据连通性检查。")
    if final_equity <= 0:
        warnings.append("缺少有效最终权益，需检查行情或执行模型。")
    return {
        "sample_level": "thin" if total_trades < 30 else "normal",
        "total_trades": total_trades,
        "warnings": warnings,
        "usable_for_decision": total_trades >= 30 and not warnings,
    }


def _monthly_returns(rows: list[BacktestDailySnapshot]) -> list[dict[str, Any]]:
    grouped: dict[str, list[BacktestDailySnapshot]] = {}
    for row in rows:
        grouped.setdefault(str(row.trade_date)[:7], []).append(row)
    output: list[dict[str, Any]] = []
    for month in sorted(grouped):
        items = grouped[month]
        start_equity = float(items[0].equity or 0.0)
        end_equity = float(items[-1].equity or 0.0)
        return_pct = 0.0 if start_equity <= 0 else (end_equity / start_equity - 1) * 100
        output.append(
            {
                "month": month,
                "start_equity": round(start_equity, 2),
                "end_equity": round(end_equity, 2),
                "return_pct": round(return_pct, 4),
                "trading_days": len(items),
            }
        )
    return output


def _strategy_attribution(trades: list[BacktestTrade], result: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = result.get("metrics")
    by_strategy = metrics.get("by_strategy") if isinstance(metrics, dict) else None
    if isinstance(by_strategy, dict) and by_strategy:
        return [
            {"strategy_key": str(strategy), **dict(payload)}
            for strategy, payload in sorted(by_strategy.items())
            if isinstance(payload, dict)
        ]
    return [
        {"strategy_key": item["bucket"], **{key: value for key, value in item.items() if key != "bucket"}}
        for item in _bucket_trades(trades, "strategy_key")
    ]


def _bucket_trades(trades: list[BacktestTrade], attr_name: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[BacktestTrade]] = {}
    for trade in trades:
        bucket = str(getattr(trade, attr_name, "") or "unknown")
        grouped.setdefault(bucket, []).append(trade)
    output = []
    for bucket, items in sorted(grouped.items()):
        winners = [trade for trade in items if float(trade.pnl_amount or 0.0) > 0]
        output.append(
            {
                "bucket": bucket,
                "trade_count": len(items),
                "win_count": len(winners),
                "win_rate_pct": round(len(winners) / max(len(items), 1) * 100, 4),
                "avg_return_pct": round(sum(float(trade.pnl_pct or 0.0) for trade in items) / max(len(items), 1), 4),
                "net_pnl": round(sum(float(trade.pnl_amount or 0.0) for trade in items), 2),
                "fee_amount": round(sum(float(trade.fee_amount or 0.0) for trade in items), 2),
            }
        )
    return output


def _compare_equity_points(run_id: int, db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        select(BacktestDailySnapshot)
        .where(BacktestDailySnapshot.run_id == run_id)
        .order_by(BacktestDailySnapshot.trade_date.asc())
    ).scalars().all()
    return [
        {
            "trade_date": row.trade_date,
            "equity": float(row.equity or 0.0),
            "daily_return_pct": float(row.daily_return_pct or 0.0),
            "drawdown_pct": float(row.drawdown_pct or 0.0),
        }
        for row in rows
    ]


def _strategy_correlation(strategies: list[str], trades: list[BacktestTrade]) -> list[dict[str, Any]]:
    normalized = sorted({strategy for strategy in strategies if strategy})
    if not normalized:
        normalized = sorted({trade.strategy_key for trade in trades if trade.strategy_key})
    dates = sorted({trade.trade_date for trade in trades})
    pnl_by_key = {(trade.strategy_key, trade.trade_date): 0.0 for trade in trades}
    for trade in trades:
        key = (trade.strategy_key, trade.trade_date)
        pnl_by_key[key] = pnl_by_key.get(key, 0.0) + float(trade.pnl_amount or 0.0)
    series = {
        strategy: [pnl_by_key.get((strategy, trade_date), 0.0) for trade_date in dates]
        for strategy in normalized
    }
    rows: list[dict[str, Any]] = []
    for left in normalized:
        correlations: dict[str, float] = {}
        p_values: dict[str, float] = {}
        sample_counts: dict[str, int] = {}
        notes: dict[str, str] = {}
        for right in normalized:
            stats = _pearson_stats(series.get(left, []), series.get(right, []), same=left == right)
            correlations[right] = stats["correlation"]
            p_values[right] = stats["p_value"]
            sample_counts[right] = stats["sample_count"]
            if stats["sample_count"] < 30 and left != right:
                notes[right] = "样本少于30个交易日，相关性仅供参考。"
            elif stats["p_value"] > 0.05 and left != right:
                notes[right] = "显著性不足，不能据此判断策略联动。"
        rows.append(
            {
                "strategy_key": left,
                "correlations": correlations,
                "p_values": p_values,
                "sample_counts": sample_counts,
                "significance_notes": notes,
            }
        )
    return rows


def _pearson_stats(left: list[float], right: list[float], *, same: bool) -> dict[str, float | int]:
    if same:
        return {"correlation": 1.0, "p_value": 0.0, "sample_count": len(left)}
    pairs = [(l, r) for l, r in zip(left, right) if abs(l) > 0 or abs(r) > 0]
    if len(pairs) < 2:
        return {"correlation": 0.0, "p_value": 1.0, "sample_count": len(pairs)}
    left_avg = sum(item[0] for item in pairs) / len(pairs)
    right_avg = sum(item[1] for item in pairs) / len(pairs)
    numerator = sum((left_item - left_avg) * (right_item - right_avg) for left_item, right_item in pairs)
    left_var = sum((left_item - left_avg) ** 2 for left_item, _ in pairs)
    right_var = sum((right_item - right_avg) ** 2 for _, right_item in pairs)
    denominator = math.sqrt(left_var * right_var)
    if denominator <= 0:
        return {"correlation": 0.0, "p_value": 1.0, "sample_count": len(pairs)}
    correlation = max(-0.999999, min(numerator / denominator, 0.999999))
    return {
        "correlation": round(correlation, 4),
        "p_value": round(_pearson_p_value(correlation, len(pairs)), 6),
        "sample_count": len(pairs),
    }


def _pearson_p_value(correlation: float, sample_count: int) -> float:
    if sample_count < 4:
        return 1.0
    z_score = abs(math.atanh(correlation)) * math.sqrt(max(sample_count - 3, 1))
    return max(0.0, min(1.0, math.erfc(z_score / math.sqrt(2))))


def _safe_error_message(exc: Exception) -> str:
    message = str(exc).strip()
    return (message or "回测执行失败")[:240]
